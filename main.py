import os
import json
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from groq import Groq
from dotenv import load_dotenv
import kuzu
import graph_builder

load_dotenv()

try:
    groq_client = Groq()
except Exception as e:
    print("Warning: GROQ_API_KEY not found or invalid.")
    groq_client = None

DB_PATH = "context_graph_kuzu"
kuzu_db = None
SCHEMA_TEXT = ""

@asynccontextmanager
async def lifespan(app: FastAPI):
    global kuzu_db, SCHEMA_TEXT
    try:
        kuzu_db = kuzu.Database(DB_PATH)
        SCHEMA_TEXT = get_database_schema()
        print("Connected to Kùzu DB successfully!")
    except Exception as e:
        print("Error connecting to Kùzu DB:", e)
    yield
    kuzu_db = None

app = FastAPI(title="Context Graph System", lifespan=lifespan)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    query: str

def get_database_schema():
    if not kuzu_db: return ""
    conn = kuzu.Connection(kuzu_db)
    res = conn.execute("CALL show_tables() RETURN *")
    schema_lines = []
    while res.has_next():
        row = res.get_next()
        table_name = row[1]
        type_of_table = row[2]
        
        sub_res = conn.execute(f"CALL table_info('{table_name}') RETURN *")
        cols = []
        while sub_res.has_next():
            c_row = sub_res.get_next()
            # Handle possible difference in internal structure length
            cols.append(f"{c_row[1]} {c_row[2]}")
        schema_lines.append(f"{type_of_table} TABLE {table_name} ({', '.join(cols)})")
    
    return "\n".join(schema_lines)


GUARDRAIL_PROMPT = """You are an AI assistant for a Context Graph System covering an ERP dataset (Sales Orders, Products, Customers, Deliveries, Billing, Journal Entries, Payments).
Your primary job is to translate user questions into openCypher queries to run against a natively structured Kùzu Graph database, or answer based on the retrieved data.
You MUST restrict all answers to the provided dataset and domain.
If the user asks an unrelated question (e.g., general knowledge, creative writing, programming help outside this domain), you MUST reject it by saying EXACTLY:
"This system is designed to answer questions related to the provided dataset only."
"""

def get_cypher_prompt():
    return f"""{GUARDRAIL_PROMPT}

Here is the Kùzu Graph database structure (Node and Rel Tables):
{SCHEMA_TEXT}

Given the user's question, write a valid Cypher query using `MATCH` to extract the needed information. 
IMPORTANT KÙZU/CYPHER RULES:
1. Return ONLY the Cypher query in a markdown code block (```cypher ... ```). Do not explain the query.
2. If using variable-length paths, the `*` MUST be INSIDE the relationship brackets, e.g., `MATCH (a)-[:REL*1..3]->(b)`. DO NOT put the `*` outside the brackets (e.g., `[:REL]*` is INVALID).
3. Do NOT use `ORDER BY` inside a `WITH` clause unless it is immediately followed by a `LIMIT` or `SKIP`. In most cases, you should just put `ORDER BY` at the very end of your query after the `RETURN` clause.
4. If the question is unrelated to the dataset, reply with the exact rejection phrase instead of Cypher.
"""

def extract_cypher(llm_response: str) -> str:
    if "```cypher" in llm_response:
        try:
            return llm_response.split("```cypher")[1].split("```")[0].strip()
        except:
            pass
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
    if llm_response.strip().upper().startswith("MATCH"):
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

@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    if not groq_client:
        raise HTTPException(status_code=500, detail="LLM not configured (missing GROQ_API_KEY)")
    if not kuzu_db:
        raise HTTPException(status_code=500, detail="Kùzu Database not initialized.")
    
    user_query = request.query
    
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": get_cypher_prompt()},
                {"role": "user", "content": user_query}
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        cypher_response = completion.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")
    
    if "This system is designed to answer questions related to the provided dataset only" in cypher_response:
        def stream_reject():
            yield json.dumps({"type": "chunk", "content": "This system is designed to answer questions related to the provided dataset only."}) + "\n"
        return StreamingResponse(stream_reject(), media_type="application/x-ndjson")

    cypher_query = extract_cypher(cypher_response)
    if not cypher_query:
        def stream_fallback():
            yield json.dumps({"type": "chunk", "content": cypher_response}) + "\n"
        return StreamingResponse(stream_fallback(), media_type="application/x-ndjson")
        
    conn = kuzu.Connection(kuzu_db)
    try:
        q_res = conn.execute(cypher_query)
        names = q_res.get_column_names()
        rows = []
        while q_res.has_next() and len(rows) < 100:
            row_vals = q_res.get_next()
            rows.append(dict(zip(names, row_vals)))
    except Exception as e:
        error_msg = str(e)
        def stream_error():
            yield json.dumps({"type": "metadata", "sql_query": cypher_query}) + "\n"
            yield json.dumps({"type": "chunk", "content": f"I tried to run a graph query to answer your question, but encountered an error.\nCypher: {cypher_query}\nError: {error_msg}"}) + "\n"
        return StreamingResponse(stream_error(), media_type="application/x-ndjson")
    
    ANSWER_PROMPT = f"""{GUARDRAIL_PROMPT}

The user asked: "{user_query}"

I executed the following Cypher query:
```cypher
{cypher_query}
```

And got the following results (JSON):
{json.dumps(rows[:100], indent=2, default=str)}

Using this data, provide a clear, natural language answer to the user's question. Be concise but informative. If the data is empty, state that no matching records were found.
"""

    def generate_response():
        # Ensure we sanitize datetime objects internally handled by kuzu just in case
        yield json.dumps({"type": "metadata", "sql_query": cypher_query, "data": rows[:10]}, default=str) + "\n"
        try:
            stream = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a helpful data analyst. Analyze the data and answer concisely."},
                    {"role": "user", "content": ANSWER_PROMPT}
                ],
                temperature=0.3,
                max_tokens=1024,
                stream=True,
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content is not None:
                    yield json.dumps({"type": "chunk", "content": content}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "chunk", "content": f"\n\n[Data retrieved, but failed to generate summary. LLM Stream Error: {str(e)}]"}) + "\n"

    return StreamingResponse(generate_response(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
