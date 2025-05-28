import re
from typing import NamedTuple, Iterable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette import status
from src.auth import verify_token

PUBLIC_SERVICES = {"disriego"}   # alias completo público

class PublicEP(NamedTuple):
    service: str
    method: str
    regex:  re.Pattern

PUBLIC_ENDPOINTS: Iterable[PublicEP] = []   # ninguna adicional

def _is_public(service: str, method: str, tail: str) -> bool:
    if service in PUBLIC_SERVICES:
        return True
    for ep in PUBLIC_ENDPOINTS:
        if ep.service and ep.service != service:
            continue
        if ep.method != "*" and ep.method != method:
            continue
        if ep.regex.match(tail):
            return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        raw = request.url.path.lstrip("/")
        service, tail = ("", raw) if "/" not in raw else raw.split("/",1)
        if service == "" and tail == "health":
            return await call_next(request)

        if _is_public(service, request.method.upper(), tail):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return JSONResponse({"detail":"Token requerido"}, status_code=401)

        token = auth.split(" ",1)[1]
        if not verify_token(token):
            return JSONResponse({"detail":"Token inválido"}, status_code=401)

        return await call_next(request)
