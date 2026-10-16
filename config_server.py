from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Your assigned layers for 24f3003515@ds.study.iitm.ac.in ---
DEFAULTS = {"port": 8000, "workers": 1, "debug": False, "log_level": "info", "api_key": "default-secret-000"}
FILE_YAML = {"workers": 12, "api_key": "key-79ev1sbfzp"}
DOTENV = {"api_key": "key-q0d4twjo6x"}  # displayed as APP_API_KEY
OS_ENV = {"workers": 7, "debug": True, "log_level": "warning", "api_key": "key-yi22siauc1"}  # APP_* prefix

def coerce(key, val):
    if key in ("port", "workers"):
        return int(val)
    if key == "debug":
        return str(val).lower() in ("1", "true", "yes", "on")
    return str(val)

def base_merged():
    m = dict(DEFAULTS)
    m.update(FILE_YAML)
    # alias NUM_WORKERS -> workers for .env layer
    d = dict(DOTENV)
    if "NUM_WORKERS" in d:
        d["workers"] = d.pop("NUM_WORKERS")
    m.update(d)
    m.update(OS_ENV)
    # coerce types
    for k in list(m.keys()):
        if k in ("port", "workers", "debug", "log_level", "api_key"):
            m[k] = coerce(k, m[k])
    return m

@app.get("/effective-config")
async def effective_config(request: Request):
    merged = base_merged()
    # CLI overrides: ?set=key=value (repeatable)
    for item in request.query_params.getlist("set"):
        if "=" in item:
            k, v = item.split("=", 1)
            k = k.strip()
            # allow any key, but coerce known ones
            if k in ("port", "workers", "debug", "log_level", "api_key"):
                merged[k] = coerce(k, v)
            else:
                merged[k] = v
    merged["api_key"] = "****"
    # ensure only the 5 keys + any extra? spec wants all five present
    out = {k: merged[k] for k in ["port", "workers", "debug", "log_level", "api_key"] if k in merged}
    return JSONResponse(content=out)

@app.get("/")
async def root():
    return {"ok": True}
