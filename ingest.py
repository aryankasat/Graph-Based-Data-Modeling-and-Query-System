import os
import json
import sqlite3
from pathlib import Path

# Paths
DATASET_DIR = Path("dataset")
DB_PATH = "context_graph.db"

def infer_sql_type(value):
    if isinstance(value, bool):
        return "BOOLEAN"
    elif isinstance(value, int):
        return "INTEGER"
    elif isinstance(value, float):
        return "REAL"
    else:
        return "TEXT"

def create_table_from_schema(cursor, table_name, sample_record):
    columns = []
    for key, value in sample_record.items():
        sql_type = infer_sql_type(value)
        columns.append(f'"{key}" {sql_type}')
    
    columns_def = ", ".join(columns)
    create_stmt = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({columns_def});'
    cursor.execute(create_stmt)

def ingest_directory(cursor, directory_path):
    table_name = directory_path.name
    print(f"Ingesting into table: {table_name}")
    
    jsonl_files = list(directory_path.glob("*.jsonl"))
    if not jsonl_files:
        return

    # Infer schema from first file, first line
    with open(jsonl_files[0], 'r') as f:
        first_line = f.readline()
        if not first_line:
            return
        sample_record = json.loads(first_line)
    
    # Drop table if exists to start fresh
    cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    
    # Create table
    create_table_from_schema(cursor, table_name, sample_record)
    
    # Insert data
    for file_path in jsonl_files:
        with open(file_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                keys = list(record.keys())
                values = []
                for k in keys:
                    v = record[k]
                    if isinstance(v, (dict, list)):
                        values.append(json.dumps(v))
                    else:
                        values.append(v)
                
                placeholders = ", ".join(["?"] * len(keys))
                cols = ", ".join([f'"{k}"' for k in keys])
                insert_stmt = f'INSERT INTO "{table_name}" ({cols}) VALUES ({placeholders})'
                try:
                    cursor.execute(insert_stmt, values)
                except Exception as e:
                    print(f"Error inserting into {table_name}: {e}")

def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for dir_path in DATASET_DIR.iterdir():
        if dir_path.is_dir():
            ingest_directory(cursor, dir_path)
            
    conn.commit()
    conn.close()
    print("Ingestion complete. Database is saved at:", DB_PATH)

if __name__ == "__main__":
    main()
