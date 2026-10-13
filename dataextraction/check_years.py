import duckdb

def check_years():
    con = duckdb.connect()
    con.execute('INSTALL httpfs; LOAD httpfs;')
    
    print("Checking available older years in open-index/arctic...")
    years = range(2005, 2018)
    
    for year in years:
        try:
            query = f"SELECT * FROM glob('hf://datasets/open-index/arctic/data/submissions/{year}/**/*.parquet')"
            res = con.execute(query).fetchall()
            if len(res) > 0:
                print(f"- {year}: FOUND ({len(res)} files)")
            else:
                print(f"- {year}: No files found")
        except Exception as e:
            if "HTTP 404" in str(e):
                print(f"- {year}: Not available (HTTP 404)")
            else:
                print(f"- {year}: Error ({e})")

if __name__ == "__main__":
    check_years()
