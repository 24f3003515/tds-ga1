import re, json, sqlite3
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

db_conn = sqlite3.connect(":memory:", check_same_thread=False)

def init_database():
    usd_rates = {"USD": 1, "EUR": 1.11, "INR": 0.01227}
    rows = [json.loads(l) for l in open("ledger_export.jsonl", encoding="utf-8") if l.strip()]
    print(f"raw: {len(rows)}")
    df = pd.DataFrame(rows)
    df["created_at_utc"] = pd.to_datetime(df["created_at"], format="ISO8601", utc=True)
    df["updated_at_utc"] = pd.to_datetime(df["updated_at"], format="ISO8601", utc=True)
    df = df.sort_values("updated_at_utc", kind="mergesort").drop_duplicates(subset=["id"], keep="last").copy()
    print(f"dedup: {len(df)}")
    ist = df["created_at_utc"].dt.tz_convert("Asia/Kolkata")
    df["created_date"] = ist.dt.strftime("%Y-%m-%d")
    df["created_month"] = ist.dt.strftime("%Y-%m")
    df["created_year"] = ist.dt.year
    df["rate_to_usd"] = df["currency"].map(usd_rates)
    df["amount_usd"] = df["amount"] * df["rate_to_usd"]
    df.drop(columns=["created_at_utc", "updated_at_utc"]).to_sql("orders", db_conn, index=False, if_exists="replace")
    print("db ready")

init_database()

MONTH_MAP = {"january":"01","february":"02","march":"03","april":"04","may":"05","june":"06","july":"07","august":"08","september":"09","october":"10","november":"11","december":"12"}
PRODUCTS = ["Air Fryer","Rice Cooker","Juicer","Toaster","Mixer","Kettle","Blender","Grinder"]
REGIONS = ["North","South","East","West","Central"]

def parse_question_to_sql(question: str):
    q_low = question.lower()
    conditions = []
    if re.search(r"\brefund(ed|s)?\b", q_low):
        conditions.append("status = 'refunded'")
    elif re.search(r"\b(void|voided|cancel|cancelled)\b", q_low):
        conditions.append("status = 'void'")
    else:
        conditions.append("status = 'paid'")
    for reg in REGIONS:
        if re.search(rf"\b{reg.lower()}\b", q_low):
            conditions.append(f"region = '{reg}'")
            break
    for prod in PRODUCTS:
        if re.search(rf"\b{re.escape(prod.lower())}s?\b", q_low):
            conditions.append(f"product = '{prod}'")
            break
    m = re.search(r"\b(c\d{4})\b", q_low)
    if m:
        conditions.append(f"customer = '{m.group(1).upper()}'")
    ym = re.search(r"\b(202\d)\b", q_low)
    ys = ym.group(1) if ym else "2026"
    mn = None
    for k, v in MONTH_MAP.items():
        if re.search(rf"\b{k}\b", q_low):
            mn = v
            break
    if mn:
        conditions.append(f"created_month = '{ys}-{mn}'")
    elif ym:
        conditions.append(f"created_year = {ys}")
    where = " AND ".join(conditions) if conditions else "1=1"
    if any(p in q_low for p in ["which product","what product","top-selling product","best-selling product","product earned the most"]):
        metric = "SUM(qty)" if any(w in q_low for w in ["qty","quantity","units"]) else "SUM(amount_usd)"
        return f"SELECT product FROM orders WHERE {where} GROUP BY product ORDER BY {metric} DESC LIMIT 1", "string"
    if any(p in q_low for p in ["which customer","what customer","top customer","customer spent the most"]):
        return f"SELECT customer FROM orders WHERE {where} GROUP BY customer ORDER BY SUM(amount_usd) DESC LIMIT 1", "string"
    if any(p in q_low for p in ["which region","what region","top region","region earned the most"]):
        return f"SELECT region FROM orders WHERE {where} GROUP BY region ORDER BY SUM(amount_usd) DESC LIMIT 1", "string"
    if any(p in q_low for p in ["distinct customer","different customer","unique customer","how many customer"]):
        return f"SELECT COUNT(DISTINCT customer) FROM orders WHERE {where}", "int"
    if "average" in q_low:
        return f"SELECT ROUND(COALESCE(AVG(amount_usd),0),2) FROM orders WHERE {where}", "money"
    if any(p in q_low for p in ["how many orders","count the","number of orders","how many refunded"]):
        return f"SELECT COUNT(*) FROM orders WHERE {where}", "int"
    if any(p in q_low for p in ["how many units","total quantity","total units"]):
        return f"SELECT COALESCE(SUM(qty),0) FROM orders WHERE {where}", "int"
    return f"SELECT ROUND(COALESCE(SUM(amount_usd),0),2) FROM orders WHERE {where}", "money"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/")
async def answer_question(request: Request):
    body = await request.json()
    q = body.get("question","")
    sql, typ = parse_question_to_sql(q)
    cur = db_conn.cursor()
    cur.execute(sql)
    row = cur.fetchone()
    val = row[0] if row and row[0] is not None else 0
    if typ == "string":
        res = str(val)
    elif typ == "int":
        res = int(val)
    else:
        res = round(float(val),2)
    return {"answer": res}
