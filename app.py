import gradio as gr
from agent import ask, load_csv, DB_PATH, MAX_UPLOAD_MB

DEFAULT_STATUS = "Using the sample e-commerce data. Upload a CSV above to ask about your own data."
EXAMPLES = [
    "Which region earned the most revenue in 2024?",
    "Top 5 product categories by revenue, with their average discount",
    "Show monthly revenue for 2025 and the growth from the previous month",
    "Which brand sells the most units in Electronics?",
]


def on_upload(path):
    if not path:  # file removed: go back to the sample data
        return None, DEFAULT_STATUS
    try:
        db_path, summary = load_csv(path)
    except ValueError as e:
        return None, f"Could not use that file: {e}\n\nStill using the sample e-commerce data."
    return db_path, summary


def answer(question, db_path):
    if not question.strip():
        return "", None, "Type a question first."
    try:
        result, df, failed = ask(question, db_path or DB_PATH)
    except Exception as e:
        return "", None, f"Sorry, I couldn't answer that: {e}"
    note = f"\n\n(Fixed its own SQL after {failed} failed attempt(s).)" if failed else ""
    return result.sql, df, result.explanation + note


with gr.Blocks(title="Text-to-SQL Analyst Agent") as demo:
    gr.Markdown("# Text-to-SQL Analyst Agent\nAsk a question about your data in plain English. "
                "The agent writes the SQL, runs it read-only, and shows the result.")
    db_state = gr.State(None)  # path of this visitor's uploaded database, or None for the sample data
    upload = gr.File(label=f"Optional: upload your own CSV (max {MAX_UPLOAD_MB} MB)",
                     file_types=[".csv"], type="filepath")
    status = gr.Markdown(DEFAULT_STATUS)
    q = gr.Textbox(label="Your question", placeholder="Which region earned the most revenue in 2024?")
    go = gr.Button("Ask", variant="primary")
    gr.Examples(EXAMPLES, inputs=q, label="Examples for the sample data")
    explanation = gr.Markdown()
    sql = gr.Code(label="Generated SQL", language="sql")
    table = gr.Dataframe(label="Result")

    upload.change(on_upload, upload, [db_state, status])
    go.click(answer, [q, db_state], [sql, table, explanation])
    q.submit(answer, [q, db_state], [sql, table, explanation])

if __name__ == "__main__":
    demo.launch()
