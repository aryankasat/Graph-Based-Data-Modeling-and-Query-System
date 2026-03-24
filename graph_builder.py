import sqlite3
import networkx as nx

DB_PATH = "context_graph.db"

def build_graph():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    G = nx.DiGraph()
    
    # 1. Customers
    try:
        cursor.execute("SELECT businessPartner, businessPartnerName FROM business_partners")
        for row in cursor.fetchall():
            G.add_node(f"Customer_{row['businessPartner']}", label="Customer", title=row['businessPartnerName'] or "Unknown Customer")
    except Exception as e: print("Error customers", e)

    # 2. Products
    try:
        cursor.execute("SELECT product FROM products")
        for row in cursor.fetchall():
            G.add_node(f"Product_{row['product']}", label="Product", title=f"Product {row['product']}")
    except Exception as e: print("Error products", e)

    # 3. Plants
    try:
        cursor.execute("SELECT plant, plantName FROM plants")
        for row in cursor.fetchall():
            G.add_node(f"Plant_{row['plant']}", label="Plant", title=row['plantName'] or f"Plant {row['plant']}")
    except Exception as e: print("Error plants", e)

    # 4. Sales Orders
    try:
        cursor.execute("SELECT salesOrder, soldToParty FROM sales_order_headers")
        for row in cursor.fetchall():
            so_id = f"SalesOrder_{row['salesOrder']}"
            G.add_node(so_id, label="SalesOrder", title=f"SO {row['salesOrder']}")
            if row['soldToParty']:
                G.add_edge(f"Customer_{row['soldToParty']}", so_id, type="PLACED")
    except Exception as e: print("Error SO headers", e)

    try:
        cursor.execute("SELECT salesOrder, material FROM sales_order_items")
        for row in cursor.fetchall():
            if row['material']:
                G.add_edge(f"SalesOrder_{row['salesOrder']}", f"Product_{row['material']}", type="CONTAINS")
    except Exception as e: print("Error SO items", e)

    # 5. Outbound Deliveries
    try:
        cursor.execute("SELECT deliveryDocument, referenceSdDocument, plant FROM outbound_delivery_items")
        for row in cursor.fetchall():
            deliv_id = f"Delivery_{row['deliveryDocument']}"
            if not G.has_node(deliv_id):
                G.add_node(deliv_id, label="Delivery", title=f"Delivery {row['deliveryDocument']}")
            
            if row['referenceSdDocument']:
                G.add_edge(deliv_id, f"SalesOrder_{row['referenceSdDocument']}", type="FULFILLS")
            if row['plant']:
                G.add_edge(deliv_id, f"Plant_{row['plant']}", type="SHIPS_FROM")
    except Exception as e: print("Error Delivery", e)

    # 6. Billing Documents
    try:
        cursor.execute("SELECT billingDocument, referenceSdDocument FROM billing_document_items")
        for row in cursor.fetchall():
            bill_id = f"Billing_{row['billingDocument']}"
            if not G.has_node(bill_id):
                G.add_node(bill_id, label="BillingDocument", title=f"Billing {row['billingDocument']}")
            
            ref = row['referenceSdDocument']
            if ref:
                # reference could be SO or Delivery
                # Check which one it is (heuristically or link to both if we don't know, we'll try Delivery first)
                G.add_edge(bill_id, f"Delivery_{ref}", type="BILLS")
                G.add_edge(bill_id, f"SalesOrder_{ref}", type="BILLS")
    except Exception as e: print("Error Billing", e)

    # 7. Journal Entries
    try:
        cursor.execute("""
            SELECT 
                accountingDocument, customer, companyCode, fiscalYear, glAccount,
                referenceDocument, costCenter, profitCenter, transactionCurrency,
                amountInTransactionCurrency, companyCodeCurrency, amountInCompanyCodeCurrency,
                postingDate, documentDate, accountingDocumentType, accountingDocumentItem
            FROM journal_entry_items_accounts_receivable
        """)
        for row in cursor.fetchall():
            je_id = f"JournalEntry_{row['accountingDocument']}"
            if not G.has_node(je_id):
                G.add_node(
                    je_id, 
                    label="JournalEntry", 
                    title=f"JE {row['accountingDocument']}",
                    CompanyCode=row['companyCode'],
                    FiscalYear=row['fiscalYear'],
                    AccountingDocument=row['accountingDocument'],
                    GlAccount=row['glAccount'],
                    ReferenceDocument=row['referenceDocument'],
                    CostCenter=row['costCenter'],
                    ProfitCenter=row['profitCenter'],
                    TransactionCurrency=row['transactionCurrency'],
                    AmountInTransactionCurrency=row['amountInTransactionCurrency'],
                    CompanyCodeCurrency=row['companyCodeCurrency'],
                    AmountInCompanyCodeCurrency=row['amountInCompanyCodeCurrency'],
                    PostingDate=row['postingDate'],
                    DocumentDate=row['documentDate'],
                    AccountingDocumentType=row['accountingDocumentType'],
                    AccountingDocumentItem=row['accountingDocumentItem']
                )
            if row['customer']:
                G.add_edge(je_id, f"Customer_{row['customer']}", type="ACCOUNTS_FOR")
    except Exception as e: print("Error Journal", e)

    # 8. Payments
    try:
        cursor.execute("SELECT clearingAccountingDocument, accountingDocument FROM payments_accounts_receivable")
        for row in cursor.fetchall():
            pay_id = f"Payment_{row['clearingAccountingDocument']}"
            if not G.has_node(pay_id):
                G.add_node(pay_id, label="Payment", title=f"Payment {row['clearingAccountingDocument']}")
            if row['accountingDocument']:
                G.add_edge(pay_id, f"JournalEntry_{row['accountingDocument']}", type="CLEARS")
    except Exception as e: print("Error Payment", e)
    
    conn.close()
    return G

def get_graph_json():
    G = build_graph()
    
    # We only want to return nodes and links that are somewhat connected or real.
    # Due to some heuristic linking (like Billing -> Delivery OR SalesOrder), some dangling nodes might exist.
    nodes = []
    for node, data in G.nodes(data=True):
        node_data = {"id": node}
        node_data.update(data)
        # Ensure label and title have fallbacks if missing
        if "label" not in node_data:
            node_data["label"] = "Unknown"
        if "title" not in node_data:
            node_data["title"] = node
        nodes.append(node_data)
        
    links = []
    for source, target, data in G.edges(data=True):
        # only add link if both source and target exist in nodes
        if G.has_node(source) and G.has_node(target):
            links.append({
                "source": source,
                "target": target,
                "label": data.get("type", "")
            })
            
    return {"nodes": nodes, "links": links}

if __name__ == "__main__":
    data = get_graph_json()
    print(f"Graph created with {len(data['nodes'])} nodes and {len(data['links'])} links.")
