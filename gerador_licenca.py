import os, requests
URL=os.environ.get("VF_SERVER_URL","").rstrip("/")
KEY=os.environ.get("VF_ADMIN_KEY","")
if not URL or not KEY: raise SystemExit("Defina VF_SERVER_URL e VF_ADMIN_KEY.")
client=input("Cliente: ").strip()
plan=(input("Plano [MENSAL/TRIMESTRAL]: ").strip().upper() or "MENSAL")
machine=input("Machine ID (opcional): ").strip()
r=requests.post(URL+"/admin/generate",headers={"X-Admin-Key":KEY},
 json={"client":client,"plan":plan,"machine_id":machine},timeout=15)
print(r.status_code); print(r.text)
