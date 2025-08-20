
import os, sqlite3, json
from datetime import datetime

DB_PATH = os.getenv("ORDER_DB_PATH", "data/orders.db")

def ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            client_ip TEXT,
            email TEXT,
            hs_code TEXT,
            coo TEXT,
            dest TEXT,
            incoterm TEXT,
            line_items INTEGER,
            totals_json TEXT,
            stripe_session TEXT
        );
        """)

def log_order(client_ip: str, email: str, hs_code: str, coo: str, dest: str, incoterm: str,
              line_items_count: int, totals: dict, stripe_session: str | None = None) -> None:
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO orders (created_at, client_ip, email, hs_code, coo, dest, incoterm, line_items, totals_json, stripe_session) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
                client_ip or "",
                email or "",
                hs_code or "",
                coo or "",
                dest or "",
                incoterm or "",
                int(line_items_count or 0),
                json.dumps(totals or {}, separators=(",", ":")),
                stripe_session or "",
            )
        )
