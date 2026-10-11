# Text-to-SQL Analyst Agent

Ask a question about e-commerce data in plain English. The agent writes the SQL, runs it safely, and shows the answer.

## How it works
1. **Schema in the prompt:** the agent reads every table, its columns, and three sample rows, so the model sees real values.
2. **Structured output:** an LLM on NVIDIA NIM (Llama 3.3 70B by default) replies with JSON, validated by a Pydantic model (`sql`, `explanation`).
3. **Safety:** only a single `SELECT` or `WITH` is allowed, dangerous keywords are blocked, and the database connection is read-only with file and network access switched off, so generated SQL can only read the tables in that database.
4. **Self-correction:** if a query fails, the error goes back to the model, which fixes its own SQL (up to 3 attempts).

## Use your own data
Upload a CSV (max 5 MB) above the question box. The agent loads it into a temporary database for that visitor only, reads its columns, and answers questions about it. Removing the file switches back to the sample e-commerce data. Uploaded files are not stored in the project folder.

## Run it
```bash
pip install -r requirements.txt
cp .env.example .env        # then paste your NVIDIA API key (starts with nvapi-)
python generate_data.py     # builds a sample star schema (20,000 orders)
python app.py               # opens the Gradio app
```

## Try these questions
- Which region earned the most revenue in 2024?
- Top 5 product categories by revenue, with their average discount
- Show monthly revenue for 2025 and the growth from the previous month

## Next steps (these are what make it stand out)
- [x] CSV upload for any dataset
- [ ] Point `agent.py` at your Databricks Gold tables (use the `databricks-sql-connector` package).
- [ ] Add a chart: when the result has a date or category plus a number, draw a bar or line chart.
- [ ] Add 20 test questions with known answers, and report how many the agent gets right.
- [ ] Deploy on Hugging Face Spaces (add `NVIDIA_API_KEY` as a Space secret).

## Stack
Python, NVIDIA NIM (OpenAI-compatible API, Llama 3.3 70B), Pydantic, DuckDB, Gradio
