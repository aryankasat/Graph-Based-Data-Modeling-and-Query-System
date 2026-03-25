import pytest
import os
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def sample_cypher_response():
    return """Here is the query:
```cypher
MATCH (n:business_partners) RETURN n.businessPartnerName
```
"""

@pytest.fixture
def sample_sql_response():
    return """Here is the query:
```sql
MATCH (n:products) RETURN n.product
```
"""
