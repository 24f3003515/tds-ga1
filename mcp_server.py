from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import hashlib

EMAIL = "24f3003515@ds.study.iitm.ac.in"
NORMALIZED = EMAIL.strip().lower()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"ok": True, "mcp": "/mcp"}

@app.get("/mcp")
async def mcp_get():
    return {"ok": True}

@app.post("/mcp")
async def mcp_post(request: Request):
    # read challenge header (case-insensitive via starlette)
    challenge = request.headers.get("x-exam-challenge", "")
    body = await request.json()
    # handle batch? assume single
    def rpc_result(rid, result):
        return {"jsonrpc": "2.0", "id": rid, "result": result}
    def rpc_error(rid, code, msg):
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}
    # notifications/initialized has no id
    if isinstance(body, list):
        # batch not expected, handle first
        body = body[0]
    method = body.get("method", "")
    rid = body.get("id")
    params = body.get("params", {}) or {}
    # notification
    if method == "notifications/initialized":
        return JSONResponse(status_code=202, content={})
    if method == "initialize":
        pv = params.get("protocolVersion", "2024-11-05")
        return rpc_result(rid, {
            "protocolVersion": pv,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "exam-mcp", "version": "1.0"}
        })
    if method == "tools/list":
        return rpc_result(rid, {
            "tools": [{
                "name": "solve_challenge",
                "description": "Solves exam challenge",
                "inputSchema": {"type": "object", "properties": {}}
            }]
        })
    if method == "tools/call":
        tool = params.get("name", "")
        if tool != "solve_challenge":
            return rpc_error(rid, -32602, f"unknown tool {tool}")
        if not challenge:
            return rpc_error(rid, -32602, "missing X-Exam-Challenge header")
        text = hashlib.sha256(f"{challenge}:{NORMALIZED}".encode()).hexdigest()[:16].lower()
        return rpc_result(rid, {"content": [{"type": "text", "text": text}]})
    return rpc_error(rid, -32601, f"unknown method {method}")
