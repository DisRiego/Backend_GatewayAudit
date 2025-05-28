import os, warnings, httpx, datetime, asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
from src.middlewares import AuthMiddleware
from src.audit_mw import AuditMiddleware
from src.audit_db import fetch_all

load_dotenv()

MICROSERVICES = {
    "maintenance": os.getenv("MAINTENANCE_URL"),
    "iot":         os.getenv("IOT_URL"),
    "disriego":    os.getenv("DISRIEGO_URL"),
    "facturation": os.getenv("FACTURATION_URL"),
}

app = FastAPI(title="Mini API Gateway")
app.add_middleware(AuthMiddleware)
app.add_middleware(AuditMiddleware)

client = httpx.AsyncClient(timeout=10, headers={"Accept-Encoding":"identity"})

HOP = {"connection","keep-alive","proxy-authenticate","proxy-authorization",
       "te","trailers","transfer-encoding","upgrade","content-length",
       "host","content-encoding"} 

def clean(h: dict[str,str], *, keep_auth: bool) -> dict[str,str]:
    """Filtra headers hop-by-hop; opcionalmente deja Authorization."""
    skip = HOP if not keep_auth else HOP - {"authorization"}
    return {k:v for k,v in h.items() if k.lower() not in skip}

@app.get("/health", include_in_schema=False)
async def health(): return {"status":"ok","ts":datetime.datetime.utcnow().isoformat()}

@app.get("/_audit")
async def read_audit():
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(None, fetch_all, "audit")
    return rows

@app.get("/_audit_detail")
async def read_detail():
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(None, fetch_all, "audit_detail")
    return rows

async def _proxy(request: Request, base: str, alias: str, tail: str):
    try:
        upstream = await client.request(
            request.method,
            f"{base}/{tail}",
            params=request.query_params,
            headers=clean(dict(request.headers), keep_auth=(alias == "disriego")),
            content=await request.body(),
        )
    except httpx.RequestError as exc:
        return JSONResponse({"detail": f"Upstream error: {exc}"}, status_code=502)

    body = await upstream.aread()

    return Response(
        content=body,
        status_code=upstream.status_code,
        
        headers=clean(dict(upstream.headers), keep_auth=False),
        media_type=upstream.headers.get("content-type"),
    )

for alias, target in MICROSERVICES.items():
    if not target:
        warnings.warn(f"[gateway] alias '{alias}' sin URL, ignorado.")
        continue

    @app.api_route(f"/{alias}/{{path:path}}",
                   methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"])
    async def _proxy_route(path: str, request: Request, _t=target, _a=alias):
        return await _proxy(request, _t, _a, path)
