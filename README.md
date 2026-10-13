# BTP: AI fear, conspiracy and misinformation on Reddit

B.Tech project by Sahil and Piyush. We are building a dataset of Reddit posts and comments that link AI with fear, conspiracy theories or misinformation, from 2005 onwards.

## Folder structure

```
BTP/
├── dataextraction/              <- current pipeline (what we actually use)
│   ├── extract_threads.py       matched posts + all comments under them (used for 2005-2015)
│   ├── script.py                matched posts and matched comments, one CSV per year (used for 2016-2019)
│   ├── check_years.py           checks which years exist in the dataset
│   ├── test_duckdb.py           connection test (counts 2023 files)
│   ├── convert_to_csv.py        converts a .parquet output to .csv
│   └── sample_50_matched.csv    50 random matched records for manual checking
├── reddit-scraper/              first attempt: Reddit official API (asyncpraw)
├── reddit-universal-scraper/    second attempt: scraping through Tor / proxies
├── ps.txt                       original problem statement
└── requirements.txt
```

The two scraper folders are kept only as a record of our first attempts. Both were blocked by Reddit's CAPTCHA and bot checks and produced no data. `reddit-scraper` is Piyush's repo ([RScrap](https://github.com/piyushzsharma/RScrap)). `reddit-universal-scraper` is a Reddit scraping tool with custom Tor integration, including run_with_tor.bat, scraper/tier_engine.py, and modifications to config.py and main.py to support scraping through Tor.

## Data source

We use the [Arctic Shift Reddit archive](https://huggingface.co/datasets/open-index/arctic) on Hugging Face (`open-index/arctic`). It holds every public Reddit post and comment since 2005, stored as monthly Parquet files (about 1.3 TB in total). It comes from the Pushshift / [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) dumps.

We don't download the archive. DuckDB reads the Parquet files over HTTP, one year at a time, and only the rows that match are saved.

## How the filter works

A post (title + body) or a comment is kept if it contains:

- at least one word from **List A** (AI terms: AI, ChatGPT, robot, algorithm, bot, ...), matched as a whole word, case-insensitive, **and**
- at least one word from **List B** (fear/conspiracy terms: conspiracy, hoax, fake, surveillance, takeover, ...), matched anywhere in the text, case-insensitive.

The full lists are at the top of `dataextraction/script.py`.

## How to run

```bash
pip install -r requirements.txt
cd dataextraction

# full threads (what we did for 2005-2015)
python extract_threads.py --start-year 2005 --end-year 2015 --out threads_2005_2015.parquet

# one CSV per year (what we did for 2016-2019)
python script.py --start-year 2016 --end-year 2019
```

You need a stable internet connection. Each year takes several hours.

## Output (not in this repo)

The output files are too large for GitHub (about 8.6 GB), so they are only stored locally:

| File | Rows | Size |
| --- | --- | --- |
| threads_2005_2015.csv / .parquet | 2,526,907 | 1.7 GB / 0.9 GB |
| 2016.csv | 177,140 | 0.6 GB |
| 2017.csv | 2,507,007 | 3.6 GB |
| 2018.csv | 312,679 | 1.1 GB |
| 2019.csv | 281,892 | 1.0 GB |

Columns: id, author, subreddit, text, score, created_utc, created_at, url, link_id, parent_id, record type, source_year.

## Known issues (to fix next)

- Comments are missing for 2013, 2015, 2016, 2018 and 2019. The comment query failed in those years and the scripts carried on without stopping.
- The keywords are too loose. "bot" and "lie" cause most of the matches ("lie" matches inside "believe", "replies", "earlier"), and bots such as AutoModerator and autotldr make up a large share of the rows.
- 2005-2015 has full threads, while 2016-2019 has only individual matched rows. These need to use the same method.
- There is no run log yet, and the dataset version (commit) is not pinned.
- The Hugging Face copy has no comments after July 2022 and no posts from Aug 2022 to Nov 2023. Those months will have to come from the Arctic Shift torrents.
