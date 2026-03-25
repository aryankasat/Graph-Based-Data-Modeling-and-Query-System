import pytest
from main import extract_cypher

def test_extract_cypher_standard():
    llm_response = """
Here is the Cypher query:
```cypher
MATCH (n:business_partners) RETURN n.businessPartnerName
```
"""
    expected = "MATCH (n:business_partners) RETURN n.businessPartnerName"
    assert extract_cypher(llm_response) == expected

def test_extract_cypher_sql_block():
    llm_response = """
I wrote it in SQL block by mistake:
```sql
MATCH (n:products) RETURN n.product
```
"""
    expected = "MATCH (n:products) RETURN n.product"
    assert extract_cypher(llm_response) == expected

def test_extract_cypher_generic_block():
    llm_response = """
```
MATCH (n:plants) RETURN n.plantName
```
"""
    expected = "MATCH (n:plants) RETURN n.plantName"
    assert extract_cypher(llm_response) == expected

def test_extract_cypher_no_block():
    llm_response = "MATCH (n:sales_order_headers) RETURN n.salesOrder"
    expected = "MATCH (n:sales_order_headers) RETURN n.salesOrder"
    assert extract_cypher(llm_response) == expected

def test_extract_cypher_invalid():
    llm_response = "I don't know the answer."
    assert extract_cypher(llm_response) is None
