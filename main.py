import os
import json
import sqlite3
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from groq import Groq
from dotenv import load_dotenv
import graph_builder

load_dotenv()

# Initialize GROQ Client
# Assumes GROQ_API_KEY is in environment or .env
try:
    groq_client = Groq()
except Exception as e:
    print("Warning: GROQ_API_KEY not found or invalid.")
    groq_client = None

DB_PATH = "context_graph.db"

app = FastAPI(title="Context Graph System")

# Serve the static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str
    sql_query: str = None
    data: list = None

def get_database_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
    schema = "\n".join([row[0] for row in cursor.fetchall() if row[0] is not None])
    conn.close()
    return schema

SCHEMA_TEXT = get_database_schema()

GUARDRAIL_PROMPT = """You are an AI assistant for a Context Graph System covering an ERP dataset (Sales Orders, Products, Customers, Deliveries, Billing, Journal Entries, Payments).
Your primary job is to translate user questions into SQL to run against an SQLite database, or answer based on the retrieved data.
You MUST restrict all answers to the provided dataset and domain.
If the user asks an unrelated question (e.g., general knowledge, creative writing, programming help outside this domain), you MUST reject it by saying EXACTLY:
"This system is designed to answer questions related to the provided dataset only."
"""

SQL_GENERATION_PROMPT = f"""{GUARDRAIL_PROMPT}

Here is the SQLite database schema:
{SCHEMA_TEXT}

Given the user's question, write a valid SQLite query to extract the needed information. 
Return ONLY the SQL query in a markdown code block (```sql ... ```). Do not explain the query.
If the question is unrelated to the dataset, reply with the exact rejection phrase instead of SQL.
"""

def extract_sql(llm_response: str) -> str:
    if "```sql" in llm_response:
        try:
            return llm_response.split("```sql")[1].split("```")[0].strip()
        except:
            pass
    if "```" in llm_response:
        try:
            return llm_response.split("```")[1].split("```")[0].strip()
        except:
            pass
    # If no code block, assume the whole response might be SQL if it starts with SELECT
    if llm_response.strip().upper().startswith("SELECT"):
        return llm_response.strip()
    return None

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.get("/api/graph")
def get_graph():
    try:
        data = graph_builder.get_graph_json()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    if not groq_client:
        raise HTTPException(status_code=500, detail="LLM not configured (missing GROQ_API_KEY)")
    
    user_query = request.query
    
    # 1. Ask LLM to generate SQL or reject
    try:
        completion = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": SQL_GENERATION_PROMPT},
                {"role": "user", "content": user_query}
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        sql_response = completion.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")
    
    if "This system is designed to answer questions related to the provided dataset only" in sql_response:
        return ChatResponse(response="This system is designed to answer questions related to the provided dataset only.")

    sql_query = extract_sql(sql_response)
    if not sql_query:
        # Fallback if LLM just answered
        return ChatResponse(response=sql_response)
        
    # 2. Execute SQL
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query)
        rows = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        conn.close()
        # If SQL fails, return the error elegantly
        return ChatResponse(
            response=f"I tried to run a query to answer your question, but encountered an error.\nSQL: {sql_query}\nError: {str(e)}",
            sql_query=sql_query
        )
    conn.close()
    
    # 3. Ask LLM to formulate final answer based on data
    ANSWER_PROMPT = f"""{GUARDRAIL_PROMPT}

The user asked: "{user_query}"

I executed the following SQL query:
```sql
{sql_query}
```

And got the following results (JSON):
{json.dumps(rows[:100], indent=2)}  # Limit to 100 rows just in case

Using this data, provide a clear, natural language answer to the user's question. Be concise but informative. If the data is empty, state that no matching records were found.
"""

    try:
        final_completion = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": "You are a helpful data analyst. Analyze the data and answer concisely."},
                {"role": "user", "content": ANSWER_PROMPT}
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        final_answer = final_completion.choices[0].message.content.strip()
    except Exception as e:
        final_answer = f"Data retrieved, but failed to generate summary. Data: {str(rows[:5])}"

    return ChatResponse(response=final_answer, sql_query=sql_query, data=rows[:10])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
