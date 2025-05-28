import os, contextlib, psycopg2, psycopg2.extras, datetime

DSN = os.getenv("DATABASE_URL")
psycopg2.extras.register_default_json()  # deja JSON como texto plano

@contextlib.contextmanager
def get_conn():
    conn = psycopg2.connect(DSN, sslmode="require")
    try:
        yield conn
    finally:
        conn.close()


def insert_audit(user_id: int | None,
                 event_id: int,
                 module_id: int,
                 tail: str,
                 body: bytes):
    fecha = datetime.datetime.utcnow()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO audit (user_id, fecha, type_of_event_id, module_id)"
            " VALUES (%s,%s,%s,%s) RETURNING id",
            (user_id, fecha, event_id, module_id)
        )
        audit_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO audit_detail (audit_id, field_name, before_value, after_value)"
            " VALUES (%s,%s,%s,%s)",
            (audit_id, tail, None, body.decode()[:4000])
        )
        conn.commit()


def fetch_all(table: str):
    with get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 100")
        return cur.fetchall()
