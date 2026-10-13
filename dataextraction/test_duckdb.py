import duckdb
con = duckdb.connect()
con.execute('INSTALL httpfs; LOAD httpfs;')
res = con.execute("SELECT * FROM glob('hf://datasets/open-index/arctic/data/submissions/2023/*/**/*.parquet')").fetchall()
print(f'Total files (using * for month): {len(res)}')

try:
    res11 = con.execute("SELECT * FROM glob('hf://datasets/open-index/arctic/data/submissions/2023/11/**/*.parquet')").fetchall()
    print(f'Total in month 11: {len(res11)}')
except Exception as e:
    print("Month 11 error:", e)
