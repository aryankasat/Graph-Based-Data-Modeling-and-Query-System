import os
import json
import shutil
import kuzu
from pathlib import Path

# Paths
DATASET_DIR = Path("dataset")
DB_PATH = "context_graph_kuzu"

def infer_kuzu_type(value):
    if isinstance(value, bool):
        return "BOOLEAN"
    elif isinstance(value, int):
        return "INT64"
    elif isinstance(value, float):
        return "DOUBLE"
    else:
        return "STRING"

def create_node_table_from_schema(conn, table_name, sample_record):
    columns = []
    columns.append("kuzu_id SERIAL")
    for key, value in sample_record.items():
        kuzu_type = infer_kuzu_type(value)
        columns.append(f'{key} {kuzu_type}')
        
    columns_def = ", ".join(columns)
    create_stmt = f'CREATE NODE TABLE {table_name} ({columns_def}, PRIMARY KEY(kuzu_id))'
    try:
        conn.execute(create_stmt)
    except Exception as e:
        print(f"Skipping table creation (may exist): {e}")

def ingest_directory(conn, directory_path):
    table_name = directory_path.name
    print(f"Ingesting into node table: {table_name}")
    
    jsonl_files = list(directory_path.glob("*.jsonl"))
    if not jsonl_files:
        return

    # Infer schema from first file, first line
    with open(jsonl_files[0], 'r') as f:
        first_line = f.readline()
        if not first_line:
            return
        sample_record = json.loads(first_line)
    
    create_node_table_from_schema(conn, table_name, sample_record)
    
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
                
                placeholders = ", ".join(["$"+str(i) for i in range(len(keys))])
                insert_stmt = f'CREATE (n:{table_name} {{{", ".join([f"{k}: ${k}" for k in keys])}}})'
                
                params = {k: v for k, v in zip(keys, values)}
                try:
                    conn.execute(insert_stmt, parameters=params)
                except Exception as e:
                    pass

def create_relationships(conn):
    print("Building relationships...")
    rels = [
        # Customer placed SalesOrder
        "CREATE REL TABLE PLACED (FROM business_partners TO sales_order_headers)",
        "MATCH (a:business_partners), (b:sales_order_headers) WHERE a.businessPartner = b.soldToParty CREATE (a)-[:PLACED]->(b)",
        
        # SalesOrder contains Product
        "CREATE REL TABLE CONTAINS (FROM sales_order_headers TO products)",
        "MATCH (so:sales_order_headers), (soi:sales_order_items), (p:products) WHERE so.salesOrder = soi.salesOrder AND soi.material = p.product CREATE (so)-[:CONTAINS]->(p)",
        
        # Delivery fulfills SalesOrder
        "CREATE REL TABLE FULFILLS (FROM outbound_delivery_items TO sales_order_headers)",
        "MATCH (d:outbound_delivery_items), (so:sales_order_headers) WHERE d.referenceSdDocument = so.salesOrder CREATE (d)-[:FULFILLS]->(so)",
        
        # Delivery ships from Plant
        "CREATE REL TABLE SHIPS_FROM (FROM outbound_delivery_items TO plants)",
        "MATCH (d:outbound_delivery_items), (p:plants) WHERE d.plant = p.plant CREATE (d)-[:SHIPS_FROM]->(p)",
        
        # Billing bills Delivery
        "CREATE REL TABLE BILLS_DELIVERY (FROM billing_document_items TO outbound_delivery_items)",
        "MATCH (b:billing_document_items), (d:outbound_delivery_items) WHERE b.referenceSdDocument = d.deliveryDocument CREATE (b)-[:BILLS_DELIVERY]->(d)",
        
        # Billing bills SalesOrder
        "CREATE REL TABLE BILLS_ORDER (FROM billing_document_items TO sales_order_headers)",
        "MATCH (b:billing_document_items), (so:sales_order_headers) WHERE b.referenceSdDocument = so.salesOrder CREATE (b)-[:BILLS_ORDER]->(so)",
        
        # Journal accounts for Customer
        "CREATE REL TABLE ACCOUNTS_FOR (FROM journal_entry_items_accounts_receivable TO business_partners)",
        "MATCH (j:journal_entry_items_accounts_receivable), (c:business_partners) WHERE j.customer = c.businessPartner CREATE (j)-[:ACCOUNTS_FOR]->(c)",
        
        # Payment clears journal
        "CREATE REL TABLE CLEARS (FROM payments_accounts_receivable TO journal_entry_items_accounts_receivable)",
        "MATCH (p:payments_accounts_receivable), (j:journal_entry_items_accounts_receivable) WHERE p.accountingDocument = j.accountingDocument CREATE (p)-[:CLEARS]->(j)"
    ]
    
    for q in rels:
        try:
            conn.execute(q)
        except Exception as e:
            print(f"Rel warning: {e}")

def main():
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)
        
    db = kuzu.Database(DB_PATH)
    conn = kuzu.Connection(db)
    
    for dir_path in DATASET_DIR.iterdir():
        if dir_path.is_dir():
            ingest_directory(conn, dir_path)
            
    create_relationships(conn)
    print("Ingestion complete. Database is saved at:", DB_PATH)

if __name__ == "__main__":
    main()

