import os, sqlite3, secrets, string
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
app=Flask(__name__)
DB=os.environ.get("VF_DB","licenses.db")
ADMIN_KEY=os.environ.get("VF_ADMIN_KEY","")
def now(): return datetime.now(timezone.utc)
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
    c=db(); c.execute("""CREATE TABLE IF NOT EXISTS licenses(
    license_key TEXT PRIMARY KEY, client TEXT NOT NULL, plan TEXT NOT NULL,
    machine_id TEXT, activated_at TEXT, expires_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE')"""); c.commit(); c.close()
def admin_ok(): return bool(ADMIN_KEY) and request.headers.get("X-Admin-Key","")==ADMIN_KEY
def make_key():
    a=string.ascii_uppercase+string.digits
    while True:
        k="VF-"+"-".join("".join(secrets.choice(a) for _ in range(4)) for _ in range(3))
        c=db(); x=c.execute("SELECT 1 FROM licenses WHERE license_key=?",(k,)).fetchone(); c.close()
        if not x: return k
@app.get("/health")
def health(): return jsonify(ok=True,service="VF License Server",time=now().isoformat())
@app.post("/admin/generate")
def generate():
    if not admin_ok(): return jsonify(error="unauthorized"),401
    d=request.get_json(silent=True) or {}; client=str(d.get("client","")).strip()
    plan=str(d.get("plan","MENSAL")).upper().strip(); machine=str(d.get("machine_id","")).strip() or None
    days={"MENSAL":30,"TRIMESTRAL":90}.get(plan)
    if not client: return jsonify(error="client required"),400
    if not days: return jsonify(error="plan must be MENSAL or TRIMESTRAL"),400
    t=now(); e=t+timedelta(days=days); k=make_key(); c=db()
    c.execute("INSERT INTO licenses VALUES(?,?,?,?,?,?,?)",(k,client,plan,machine,None,e.isoformat(),"ACTIVE"))
    c.commit(); c.close()
    return jsonify(ok=True,license_key=k,client=client,plan=plan,expires_at=e.isoformat())
@app.post("/validate")
def validate():
    d=request.get_json(silent=True) or {}; key=str(d.get("license_key","")).strip().upper()
    machine=str(d.get("machine_id","")).strip()
    if not key or not machine: return jsonify(valid=False,reason="missing data"),400
    c=db(); r=c.execute("SELECT * FROM licenses WHERE license_key=?",(key,)).fetchone()
    if not r: c.close(); return jsonify(valid=False,reason="invalid")
    if r["status"]!="ACTIVE": c.close(); return jsonify(valid=False,reason="blocked")
    e=datetime.fromisoformat(r["expires_at"])
    if e<=now():
        c.execute("UPDATE licenses SET status='EXPIRED' WHERE license_key=?",(key,)); c.commit(); c.close()
        return jsonify(valid=False,reason="expired")
    if r["machine_id"] and r["machine_id"]!=machine:
        c.close(); return jsonify(valid=False,reason="machine_mismatch")
    if not r["machine_id"]:
        c.execute("UPDATE licenses SET machine_id=?,activated_at=? WHERE license_key=?",(machine,now().isoformat(),key)); c.commit()
    c.close(); return jsonify(valid=True,client=r["client"],plan=r["plan"],expires_at=r["expires_at"])
@app.post("/admin/block")
def block():
    if not admin_ok(): return jsonify(error="unauthorized"),401
    k=str((request.get_json(silent=True) or {}).get("license_key","")).strip().upper(); c=db()
    n=c.execute("UPDATE licenses SET status='BLOCKED' WHERE license_key=?",(k,)).rowcount; c.commit(); c.close()
    return jsonify(ok=n>0)
@app.post("/admin/unblock")
def unblock():
    if not admin_ok(): return jsonify(error="unauthorized"),401
    k=str((request.get_json(silent=True) or {}).get("license_key","")).strip().upper(); c=db()
    n=c.execute("UPDATE licenses SET status='ACTIVE' WHERE license_key=?",(k,)).rowcount; c.commit(); c.close()
    return jsonify(ok=n>0)
init()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT","8080")))
