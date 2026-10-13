import duckdb
import argparse
import time
import pandas as pd
import re
import os

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
    escaped = [re.escape(t) for t in terms]
    if word_boundary:
        escaped = [rf"\b{t}\b" for t in escaped]
    return "(?i)(" + "|".join(escaped) + ")"

def run_extraction(start_year, end_year, out_path):
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    
    regex_a = build_regex(POOL_A_AI, word_boundary=True).replace("'", "''")
    regex_b = build_regex(POOL_B_FEAR, word_boundary=False).replace("'", "''")

    csv_out = out_path.replace('.parquet', '') + '.csv'
    
    if os.path.exists(csv_out):
        print(f"Warning: Output file {csv_out} already exists! Appending to it...")

    all_data = []

    for year in range(start_year, end_year + 1):
        print(f"\n--- Processing Year {year} ---")
        
        chunk_data = []

        # ========================================================= # STAGE 1: Extract Submissions
        # =========================================================
        subs_glob = f"{BASE_URL}/submissions/{year}/**/*.parquet"
        text_expr = "(title || ' ' || COALESCE(selftext, ''))"
        subs_query = f"""
            SELECT 
                id, author, subreddit, 
                (title || CASE WHEN selftext IS NOT NULL AND selftext != '' THEN ' || ' || selftext ELSE '' END) AS text, 
                score, created_utc, created_at, 
                url, 
                NULL AS link_id, NULL AS parent_id,
                'submission' AS record_type,
                '{year}' AS source_year
            FROM read_parquet('{subs_glob}', union_by_name=True)
            WHERE regexp_matches({text_expr}, '{regex_a}')
              AND regexp_matches({text_expr}, '{regex_b}')
        """
        
        print(f"Stage 1: Fetching submissions for {year}...")
        t0 = time.time()
        try:
            df_subs = con.execute(subs_query).fetchdf()
            print(f"  -> Found {len(df_subs)} matching submissions in {time.time() - t0:.1f}s")
            if len(df_subs) > 0:
                chunk_data.append(df_subs)
        except Exception as e:
            print(f"  -> No submission data or network error for {year}: {e}")
            continue
            
        if len(df_subs) > 0:
            # ========================================================= # STAGE 2: Extract Related Comments
            # =========================================================
            print(f"Stage 2: Scanning giant comments archive for {len(df_subs)} posts...")
            con.register('matched_subs', df_subs)
            comments_glob = f"{BASE_URL}/comments/{year}/**/*.parquet"
            
            cmts_query = f"""
                SELECT 
                    c.id, c.author, c.subreddit, c.body AS text, c.score, c.created_utc, c.created_at,
                    NULL AS url,
                    c.link_id, c.parent_id,
                    'comment' AS record_type,
                    '{year}' AS source_year
                FROM read_parquet('{comments_glob}', union_by_name=True) c
                JOIN matched_subs s ON c.link_id = 't3_' || s.id
            """
            
            t0 = time.time()
            try:
                df_cmts = con.execute(cmts_query).fetchdf()
                print(f"  -> Found {len(df_cmts)} related thread comments in {time.time() - t0:.1f}s")
                if len(df_cmts) > 0:
                    chunk_data.append(df_cmts)
            except Exception as e:
                print(f"  -> No comments found or network error for {year}: {e}")
                
            con.unregister('matched_subs')

        # ========================================================= # ITERATIVE SAVE
        # =========================================================
        if chunk_data:
            df_year = pd.concat(chunk_data, ignore_index=True)
            all_data.append(df_year)
            
            needs_header = not os.path.exists(csv_out)
            df_year.to_csv(csv_out, mode='a', header=needs_header, index=False)
            print(f"==> PROGRESSIVELY SAVED {len(df_year)} records for {year} into {csv_out}!")

    if not all_data:
        print("\nNo data found across the given range.")
        return

    print(f"\nFinal export to Parquet...")
    result = pd.concat(all_data, ignore_index=True)
    result.to_parquet(out_path, index=False)
    print(f"Saved {len(result)} total records (posts+comments) to {out_path} and {csv_out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract unified submission + threads")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()
    
    run_extraction(args.start_year, args.end_year, args.out)
