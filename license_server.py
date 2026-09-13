import os, secrets, string
from datetime import datetime, timezone, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL", "")
ADMIN_KEY = os.environ.get("VF_ADMIN_KEY", "")

def now():
    return datetime.now(timezone.utc)

def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not configured")
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init():
    with db() as c:
        with c.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS licenses (
                license_key TEXT PRIMARY KEY, client TEXT NOT NULL, plan TEXT NOT NULL,
                machine_id TEXT, activated_at TIMESTAMPTZ,
                expires_at TIMESTAMPTZ NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE')""")

def admin_ok():
    return bool(ADMIN_KEY) and request.headers.get("X-Admin-Key","") == ADMIN_KEY

def make_key():
    chars = string.ascii_uppercase + string.digits
    while True:
        k = "VF-" + "-".join("".join(secrets.choice(chars) for _ in range(4)) for _ in range(3))
        with db() as c:
            with c.cursor() as cur:
                cur.execute("SELECT 1 FROM licenses WHERE license_key=%s", (k,))
                if cur.fetchone() is None: return k

@app.get("/health")
def health():
    try:
        with db() as c:
            with c.cursor() as cur:
                cur.execute("SELECT 1")
        return jsonify(ok=True, service="VF License Server", database="connected", time=now().isoformat())
    except Exception as e:
        return jsonify(ok=False, service="VF License Server", database="error", error=str(e)), 500

@app.post("/admin/generate")
def generate():
    if not admin_ok(): return jsonify(error="unauthorized"), 401
    d = request.get_json(silent=True) or {}
    client = str(d.get("client","")).strip()
    plan = str(d.get("plan","MENSAL")).upper().strip()
    machine = str(d.get("machine_id","")).strip() or None
    days = {"MENSAL":30, "TRIMESTRAL":90}.get(plan)
    if not client: return jsonify(error="client required"), 400
    if not days: return jsonify(error="plan must be MENSAL or TRIMESTRAL"), 400
    t, e, k = now(), now()+timedelta(days=days), make_key()
    with db() as c:
        with c.cursor() as cur:
            cur.execute("""INSERT INTO licenses
            (license_key,client,plan,machine_id,activated_at,expires_at,status)
            VALUES (%s,%s,%s,%s,%s,%s,'ACTIVE')""",
            (k,client,plan,machine,t if machine else None,e))
    return jsonify(ok=True,license_key=k,client=client,plan=plan,expires_at=e.isoformat())

@app.post("/validate")
def validate():
    d = request.get_json(silent=True) or {}
    key = str(d.get("license_key","")).strip().upper()
    machine = str(d.get("machine_id","")).strip()
    if not key or not machine: return jsonify(valid=False,reason="missing data"),400
    with db() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM licenses WHERE license_key=%s",(key,))
            r = cur.fetchone()
            if not r: return jsonify(valid=False,reason="invalid")
            if r["status"] != "ACTIVE": return jsonify(valid=False,reason="blocked")
            if r["expires_at"] <= now():
                cur.execute("UPDATE licenses SET status='EXPIRED' WHERE license_key=%s",(key,))
                return jsonify(valid=False,reason="expired")
            if r["machine_id"] and r["machine_id"] != machine:
                return jsonify(valid=False,reason="machine_mismatch")
            if not r["machine_id"]:
                cur.execute("UPDATE licenses SET machine_id=%s,activated_at=%s WHERE license_key=%s",
                            (machine,now(),key))
            return jsonify(valid=True,client=r["client"],plan=r["plan"],expires_at=r["expires_at"].isoformat())

@app.post("/admin/block")
def block():
    if not admin_ok(): return jsonify(error="unauthorized"),401
    key = str((request.get_json(silent=True) or {}).get("license_key","")).strip().upper()
    with db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE licenses SET status='BLOCKED' WHERE license_key=%s",(key,))
            if cur.rowcount == 0: return jsonify(ok=False,error="license not found"),404
    return jsonify(ok=True,status="BLOCKED",license_key=key)

@app.post("/admin/unblock")
def unblock():
    if not admin_ok(): return jsonify(error="unauthorized"),401
    key = str((request.get_json(silent=True) or {}).get("license_key","")).strip().upper()
    with db() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT expires_at FROM licenses WHERE license_key=%s",(key,))
            r = cur.fetchone()
            if not r: return jsonify(ok=False,error="license not found"),404
            if r["expires_at"] <= now(): return jsonify(ok=False,error="license expired"),400
            cur.execute("UPDATE licenses SET status='ACTIVE' WHERE license_key=%s",(key,))
    return jsonify(ok=True,status="ACTIVE",license_key=key)

try: init()
except Exception as e: print("Database initialization warning:", e)

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","8080")))
