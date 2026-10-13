"""
Layer 1 filter: pull Reddit comments/submissions matching
(AI term) AND (fear/conspiracy/misinformation term)
from the open-index/arctic Hugging Face Parquet mirror of Arctic Shift.

No download of the full 1.3TB dataset needed — DuckDB reads Parquet
directly over HTTP from Hugging Face and only pulls bytes it needs
for the filter + selected columns.

Design principle: this is the CHEAP filtering stage. Cast a wide net,
prune hard later with Stage 2 (dedup/score/subreddit weighting) and
Stage 3+ (embeddings/LLM) only on survivors.

Usage:
    python layer1_filter.py --start-year 2016 --end-year 2018

Split work across teammates by --start-year/--end-year,
then merge all output files with pandas at the end.
"""

import duckdb
import argparse
import time

# --- Keyword pools -----------------------------------------------------

POOL_A_AI = [
    "AI", "artificial intelligence", "ChatGPT", "GPT", "LLM",
    "machine learning", "AGI", "ASI", "superintelligence", "chatbot",
    "robot", "OpenAI", "Anthropic", "Claude", "Gemini", "Copilot",
    "neural network", "algorithm", "singularity", "automation",
    "deepfake", "bot",
]

POOL_B_FEAR = [
    "conspiracy", "cover up", "coverup", "hidden", "secret", "secretly",
    "they don't want you to know", "fake", "hoax", "propaganda",
    "misinformation", "disinformation", "fearmongering", "panic",
    "scare", "scary", "dangerous", "threat", "doom", "apocalypse",
    "control", "manipulate", "manipulation", "surveillance", "deceive",
    "deception", "lie", "lying", "distrust", "don't trust", "skeptic",
    "debunk", "myth", "paranoid", "tinfoil", "sentient", "alive",
    "awakening", "uprising", "takeover", "replace us", "replacing us",
    "extinction", "end of the world", "end times", "elite", "agenda",
    "whistleblower", "leaked", "banned", "censored", "suppressed",
]

BASE_URL = "hf://datasets/open-index/arctic/data"


def build_regex(terms, word_boundary=False):
    """Build a case-insensitive alternation regex from a term list.
    Escapes regex special chars in each term (mostly relevant for
    parens/apostrophes like "they don't want you to know").
    word_boundary=True wraps each term in \\b so short terms like
    "AI" or "bot" don't match inside unrelated words (e.g. "said",
    "Aiden", "robot" catching "bot")."""
    import re
    escaped = [re.escape(t) for t in terms]
    if word_boundary:
        escaped = [rf"\b{t}\b" for t in escaped]
    return "(?i)(" + "|".join(escaped) + ")"


def run_filter(start_year, end_year):
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")

    regex_a = build_regex(POOL_A_AI, word_boundary=True)
    regex_b = build_regex(POOL_B_FEAR, word_boundary=False)

    for year in range(start_year, end_year + 1):
        year_frames = []
        for data_type in ["comments", "submissions"]:
            if data_type == "comments":
                text_expr = "body"
                select_cols = """
                    id, author, subreddit, body AS text, score,
                    created_utc, created_at, link_id, parent_id
                """
            else:  # submissions
                text_expr = "(title || ' ' || COALESCE(selftext, ''))"
                select_cols = """
                    id, author, subreddit,
                    (title || CASE WHEN selftext IS NOT NULL AND selftext != ''
                                    THEN ' || ' || selftext ELSE '' END) AS text,
                    score, created_utc, created_at, num_comments, url
                """

            glob_path = f"{BASE_URL}/{data_type}/{year}/**/*.parquet"
            query = f"""
                SELECT {select_cols}, '{year}' AS source_year, '{data_type}' AS data_type
                FROM read_parquet('{glob_path}', union_by_name=True)
                WHERE regexp_matches({text_expr}, '{regex_a.replace("'", "''")}')
                  AND regexp_matches({text_expr}, '{regex_b.replace("'", "''")}')
            """
            print(f"Querying {data_type} {year} ...")
            t0 = time.time()
            
            max_retries = 5
            base_delay = 10
            df = None
            
            for attempt in range(max_retries):
                try:
                    df = con.execute(query).fetchdf()
                    break  # Success
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg or "Too Many Requests" in error_msg or "Could not connect" in error_msg or "aborted" in error_msg.lower():
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            print(f"  Network/Rate limit error. Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                            time.sleep(delay)
                        else:
                            print(f"  Max retries reached. Skipping {data_type} {year}.")
                    else:
                        print(f"  No data / read error for {data_type} {year}: {e}")
                        break

            if df is None:
                continue
                
            elapsed = time.time() - t0
            print(f"  {len(df)} matches in {elapsed:.1f}s")
            if len(df) > 0:
                year_frames.append(df)
        
        if year_frames:
            import pandas as pd
            combined_df = pd.concat(year_frames, ignore_index=True)
            csv_path = f"{year}.csv"
            combined_df.to_csv(csv_path, index=False)
            print(f"  Saved {len(combined_df)} combined rows for {year} to {csv_path}\n")
        else:
            print(f"  No matches found for year {year}.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    args = parser.parse_args()

    run_filter(args.start_year, args.end_year)