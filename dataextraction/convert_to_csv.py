import pandas as pd
import sys

def convert():
    if len(sys.argv) < 2:
        print("Usage: python convert_to_csv.py <input.parquet>")
        print("Example: python convert_to_csv.py submissions_2005_2015.parquet")
        sys.exit(1)
        
    parquet_file = sys.argv[1]
    csv_file = parquet_file.replace('.parquet', '') + '.csv'
    
    print(f"Loading {parquet_file}...")
    try:
        df = pd.read_parquet(parquet_file)
        print(f"Loaded {len(df)} rows. Saving to {csv_file}...")
        df.to_csv(csv_file, index=False)
        print(f"\nSuccess! You can now open {csv_file} to view all data.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    convert()
