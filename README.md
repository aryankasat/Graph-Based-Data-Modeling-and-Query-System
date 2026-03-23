# Context Graph System

This project is a context graph system that allows you to interactively explore an ERP dataset (Sales Orders, Deliveries, Billing, Customers, Products, etc.) using a 3D/2D visual graph and query it via a natural language Chat Interface powered by an LLM.

## Features

- **Data Ingestion**: Parses JSONL files and dynamically loads them into an SQLite database.
- **Graph Modeling**: Converts the relational ERP data into a NetworkX graph representation, linking Orders to Customers, Products, Deliveries, and Billing Documents.
- **Graph Visualization**: A modern glassmorphism UI utilizing `react-force-graph` (via standard JS) to explore nodes and relationships.
- **Conversational Interface**: Takes natural language queries, dynamically translates them into SQL using Groq's LLM API (Llama3-70b), executes the SQL query, and returns a natural language, data-backed answer.
- **Guardrails**: Strictly constrained to answer questions related only to the provided dataset domain. Rejects unrelated or creative prompts.

## Architecture Decisions

1. **Backend**: Built with **FastAPI** (`main.py`) to provide a lightweight, high-performance web server.
2. **Frontend**: A custom **Vanilla JS/HTML/CSS** application served directly by FastAPI. It has a split-screen design. The CSS implements modern glassmorphism and subtle glowing aesthetics for a visually premium experience without bloated UI frameworks.
3. **Database Choice**: 
   - We used an **in-memory SQLite Database** (`context_graph.db`) dynamically created from the JSONL files (`ingest.py`). SQLite was chosen because ERP data inherently follows a relational tabular structure, making it the perfect target for standard **Text-to-SQL logic**, which LLMs excel at.
   - We used **NetworkX** (`graph_builder.py`) to parse the SQLite database and construct an explicitly directional graph mapping (e.g., `Delivery -> FULFILLS -> SalesOrder`) which is served to the frontend visualization (`react-force-graph`).
4. **LLM Prompting Strategy**: 
   - **Text-to-SQL Generation**: The first prompt passes the SQLite table schema generated via `PRAGMA` / `sqlite_master` to the LLM. It asks the LLM to output ONLY a SQL query based on the user's natural language question.
   - **Data-Backed Summarization**: Once the backend executes the SQL, the result rows are given to a second LLM prompt to generate a concise, human-readable answer. This ensures no hallucinated data—answers are strictly grounded in execution results.
5. **Guardrails**:
   - The System Prompt injects a strict rule enforcing domain boundaries.
   - If a prompt asks for general knowledge, creative writing, or outside topics, the LLM is explicitly instructed to reply with the exact phrase: *"This system is designed to answer questions related to the provided dataset only."*
   - The backend checks for this specific string and short-circuits execution if found, guaranteeing security and correctness.

## Setup & Running Locally

### Prerequisites
- Python 3.9+
- Provide a free API key from [Groq](https://console.groq.com/keys)

### Installation

1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Place the dataset inside the `/dataset` directory.
3. Run the Data Ingestion script (this will create `context_graph.db`):
   ```bash
   python ingest.py
   ```
4. Set your Groq API key:
   ```bash
   export GROQ_API_KEY="your_groq_api_key_here"
   ```
   *Alternatively, create a `.env` file in the root directory with `GROQ_API_KEY=...`*
5. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```
   Or explicitly via `python main.py`
6. Open your browser and navigate to: `http://localhost:8000`

## Example Queries to Try

- "Which products are associated with the highest number of billing documents?"
- "Trace the full flow of billing document 9000000001"
- "Identify sales orders that have broken or incomplete flows"
- "What is the capital of France?" *(will trigger the guardrail)*