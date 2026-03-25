import os
import kuzu

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "context_graph_kuzu")

def get_graph_json():
    db = kuzu.Database(DB_PATH)
    conn = kuzu.Connection(db)
    
    nodes_dict = {}
    links = []

    def add_node(nid, label, title, extras=None):
        if nid not in nodes_dict:
            node_data = {"id": nid, "label": label, "title": title}
            if extras:
                node_data.update(extras)
            nodes_dict[nid] = node_data

    # Customers
    res = conn.execute("MATCH (n:business_partners) RETURN n.businessPartner, n.businessPartnerName")
    while res.has_next():
        row = res.get_next()
        add_node(f"Customer_{row[0]}", "Customer", row[1] or "Unknown Customer")
        
    # Products
    res = conn.execute("MATCH (n:products) RETURN n.product")
    while res.has_next():
        row = res.get_next()
        add_node(f"Product_{row[0]}", "Product", f"Product {row[0]}")

    # Plants
    res = conn.execute("MATCH (n:plants) RETURN n.plant, n.plantName")
    while res.has_next():
        row = res.get_next()
        add_node(f"Plant_{row[0]}", "Plant", row[1] or f"Plant {row[0]}")
        
    # SalesOrders
    res = conn.execute("MATCH (n:sales_order_headers) RETURN n.salesOrder")
    while res.has_next():
        row = res.get_next()
        add_node(f"SalesOrder_{row[0]}", "SalesOrder", f"SO {row[0]}")
        
    # Deliveries
    res = conn.execute("MATCH (n:outbound_delivery_items) RETURN n.deliveryDocument")
    while res.has_next():
        row = res.get_next()
        add_node(f"Delivery_{row[0]}", "Delivery", f"Delivery {row[0]}")

    # BillingDocuments
    res = conn.execute("MATCH (n:billing_document_items) RETURN n.billingDocument")
    while res.has_next():
        row = res.get_next()
        add_node(f"BillingDocument_{row[0]}", "BillingDocument", f"Billing {row[0]}")

    # JournalEntries
    res = conn.execute("""
        MATCH (n:journal_entry_items_accounts_receivable) 
        RETURN n.accountingDocument, n.companyCode, n.fiscalYear, n.glAccount, n.referenceDocument, 
               n.costCenter, n.profitCenter, n.transactionCurrency, n.amountInTransactionCurrency, 
               n.companyCodeCurrency, n.amountInCompanyCodeCurrency, n.postingDate, n.documentDate, 
               n.accountingDocumentType, n.accountingDocumentItem
    """)
    while res.has_next():
        row = res.get_next()
        extras = {
            "CompanyCode": row[1], "FiscalYear": row[2], "AccountingDocument": row[0],
            "GlAccount": row[3], "ReferenceDocument": row[4], "CostCenter": row[5],
            "ProfitCenter": row[6], "TransactionCurrency": row[7], "AmountInTransactionCurrency": row[8],
            "CompanyCodeCurrency": row[9], "AmountInCompanyCodeCurrency": row[10], "PostingDate": row[11],
            "DocumentDate": row[12], "AccountingDocumentType": row[13], "AccountingDocumentItem": row[14]
        }
        add_node(f"JournalEntry_{row[0]}", "JournalEntry", f"JE {row[0]}", extras)

    # Payments
    res = conn.execute("MATCH (n:payments_accounts_receivable) RETURN n.clearingAccountingDocument")
    while res.has_next():
        row = res.get_next()
        add_node(f"Payment_{row[0]}", "Payment", f"Payment {row[0]}")

    # Relationships
    rel_queries = [
        ("MATCH (a:business_partners)-[:PLACED]->(b:sales_order_headers) RETURN a.businessPartner, b.salesOrder", "Customer", "SalesOrder", "PLACED"),
        ("MATCH (so:sales_order_headers)-[:CONTAINS]->(p:products) RETURN so.salesOrder, p.product", "SalesOrder", "Product", "CONTAINS"),
        ("MATCH (d:outbound_delivery_items)-[:FULFILLS]->(so:sales_order_headers) RETURN d.deliveryDocument, so.salesOrder", "Delivery", "SalesOrder", "FULFILLS"),
        ("MATCH (d:outbound_delivery_items)-[:SHIPS_FROM]->(p:plants) RETURN d.deliveryDocument, p.plant", "Delivery", "Plant", "SHIPS_FROM"),
        ("MATCH (b:billing_document_items)-[:BILLS_DELIVERY]->(d:outbound_delivery_items) RETURN b.billingDocument, d.deliveryDocument", "BillingDocument", "Delivery", "BILLS"),
        ("MATCH (b:billing_document_items)-[:BILLS_ORDER]->(so:sales_order_headers) RETURN b.billingDocument, so.salesOrder", "BillingDocument", "SalesOrder", "BILLS"),
        ("MATCH (j:journal_entry_items_accounts_receivable)-[:ACCOUNTS_FOR]->(c:business_partners) RETURN j.accountingDocument, c.businessPartner", "JournalEntry", "Customer", "ACCOUNTS_FOR"),
        ("MATCH (p:payments_accounts_receivable)-[:CLEARS]->(j:journal_entry_items_accounts_receivable) RETURN p.clearingAccountingDocument, j.accountingDocument", "Payment", "JournalEntry", "CLEARS")
    ]
    
    for q, source_type, target_type, rel_name in rel_queries:
        try:
            res = conn.execute(q)
            while res.has_next():
                row = res.get_next()
                source_id = f"{source_type}_{row[0]}"
                target_id = f"{target_type}_{row[1]}"
                if source_id in nodes_dict and target_id in nodes_dict:
                    links.append({
                        "source": source_id,
                        "target": target_id,
                        "label": rel_name
                    })
        except Exception as e:
            pass

    return {"nodes": list(nodes_dict.values()), "links": links}

if __name__ == "__main__":
    data = get_graph_json()
    print(f"Graph created with {len(data['nodes'])} nodes and {len(data['links'])} links.")
