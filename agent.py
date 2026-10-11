"""Text-to-SQL agent: question in, safe SQL out, results back.
An NVIDIA NIM model writes the SQL as JSON, Pydantic validates the shape,
a read-only connection enforces safety, and failed queries are sent back to the model to fix."""
import os, re, json, tempfile
import duckdb
from openai import OpenAI  # NVIDIA NIM speaks the OpenAI API
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "ecommerce.duckdb")
BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")
MAX_ATTEMPTS = 3
ROW_LIMIT = 500
MAX_UPLOAD_MB = 5
DEFAULT_NOTE = "Revenue is in Indian rupees."


class SQLAnswer(BaseModel):
    sql: str = Field(description="One read-only DuckDB SELECT statement that answers the question")
    explanation: str = Field(description="One or two plain-English sentences on what the query does")


BLOCKED = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|install|load|export|call|set"
    r"|read_csv|read_csv_auto|read_parquet|read_json|read_text|read_blob|glob)\b", re.I
)


def connect(db_path: str):
    """Read-only connection with file and network access switched off, so generated
    SQL can only ever read the tables inside this one database."""
    return duckdb.connect(db_path, read_only=True, config={"enable_external_access": False})


def get_schema(db_path: str) -> str:
    """Describe every table, with three sample rows so the model sees real values."""
    con = connect(db_path)
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY 1").fetchall()]
    parts = []
    for t in tables:
        cols = con.execute(f"DESCRIBE {t}").fetchall()
        sample = con.execute(f"SELECT * FROM {t} LIMIT 3").fetchall()
        parts.append(f"{t}({', '.join(f'{c[0]} {c[1]}' for c in cols)})\n  sample rows: {sample}")
    con.close()
    return "\n".join(parts)


def check_safe(sql: str) -> str:
    """Allow a single SELECT (or WITH ... SELECT) and nothing else."""
    sql = sql.strip().rstrip(";").strip()
    if ";" in sql:
        raise ValueError("Only one statement is allowed")
    if not re.match(r"^(select|with)\b", sql, re.I):
        raise ValueError("Only SELECT queries are allowed")
    if BLOCKED.search(sql):
        raise ValueError("Query contains a blocked keyword")
    return sql


def run_sql(sql: str, db_path: str):
    con = connect(db_path)
    try:
        return con.execute(f"SELECT * FROM ({sql}) LIMIT {ROW_LIMIT}").df()
    finally:
        con.close()


def parse_answer(text: str) -> SQLAnswer:
    """Pull the JSON object out of the model's reply (handles code fences and <think> blocks)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("the reply was not a JSON object")
    return SQLAnswer(**json.loads(match.group(0)))


def ask(question: str, db_path: str = DB_PATH):
    """Returns (SQLAnswer, DataFrame, number_of_failed_attempts)."""
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY is missing. Add it to your .env file.")
    client = OpenAI(base_url=BASE_URL, api_key=key)
    system = (
        "You are a careful data analyst. Write DuckDB SQL for the user's question using only "
        "the tables below. Use clear column aliases. "
        + (DEFAULT_NOTE if db_path == DB_PATH else "") + "\n\n" + get_schema(db_path)
        + '\n\nReply with ONLY a JSON object and no other text, in exactly this form:\n'
        '{"sql": "<one SELECT statement>", "explanation": "<one or two plain-English sentences>"}'
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0, max_tokens=1000)
        text = resp.choices[0].message.content or ""
        try:
            answer = parse_answer(text)
            answer.sql = check_safe(answer.sql)
            return answer, run_sql(answer.sql, db_path), attempt
        except Exception as e:  # feed the error back so the model can repair its own reply
            last_error = e
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"That failed: {e}. Reply again with only the corrected JSON object."},
            ]
    raise RuntimeError(f"Could not produce a working query: {last_error}")


def load_csv(csv_path: str):
    """Load an uploaded CSV into its own temporary database. Returns (db_path, summary)."""
    size_mb = os.path.getsize(csv_path) / 1_000_000
    if size_mb > MAX_UPLOAD_MB:
        raise ValueError(f"File is {size_mb:.1f} MB. The limit is {MAX_UPLOAD_MB} MB.")
    name = re.sub(r"\W+", "_", os.path.splitext(os.path.basename(csv_path))[0]).strip("_").lower() or "uploaded_data"
    if name[0].isdigit():
        name = "t_" + name
    db_path = os.path.join(tempfile.mkdtemp(), "upload.duckdb")
    con = duckdb.connect(db_path)  # normal connection, only used here to read the file
    try:
        con.execute(f'CREATE TABLE "{name}" AS SELECT * FROM read_csv_auto(?, sample_size=-1)', [csv_path])
        rows = con.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
        cols = [c[0] for c in con.execute(f'DESCRIBE "{name}"').fetchall()]
    except Exception as e:
        raise ValueError(f"Could not read that file as a CSV: {e}")
    finally:
        con.close()
    return db_path, f"Loaded **{name}**: {rows:,} rows, columns: {', '.join(cols)}"
