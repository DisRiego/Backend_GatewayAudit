import asyncio, os, datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from jose import jwt, JWTError
from src.audit_db import insert_audit

JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM  = "HS256"

# alias → module_id  (coinciden con tu tabla module)
MODULE_MAP = {
    "maintenance": 1,
    "iot":         2,
    "disriego":    3,
    "facturation": 4,
}

# método → type_of_event_id
EVENT_MAP = {"POST": 1, "DELETE": 2, "PUT": 3, "PATCH": 4, "GET": 5}


def get_user_id(auth_header: str | None) -> int | None:
    """
    Intenta sacar el identificador de usuario del JWT.
    Acepta las claves  id , user_id  o  sub  (la que exista primero).
    Devuelve None si el header falta o no contiene un ID numérico.
    """
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        return None

    for key in ("id", "user_id", "sub"):
        val = payload.get(key)
        if val is None:
            continue

        return int(val)



class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # ---- lee y cachea el cuerpo ANTES de pasarlo a la siguiente capa ----
        raw_body = await request.body()

        # ---- continúa la cadena y captura respuesta ------------------------
        response = await call_next(request)

        # ---- determina alias, módulo, evento --------------------------------
        raw_path = request.url.path.lstrip("/")
        if "/" not in raw_path:                         # /health, /_audit, etc.
            return response
        alias, tail = raw_path.split("/", 1)
        module_id = MODULE_MAP.get(alias)
        if not module_id:                              # alias no mapeado
            return response

        user_id  = get_user_id(request.headers.get("authorization"))
        event_id = EVENT_MAP.get(request.method, 99)

        # ---- log de depuración ---------------------------------------------
        print(
            f"[audit] user={user_id} module={module_id} event={event_id} "
            f"tail='{tail}' ts={datetime.datetime.utcnow().isoformat()}",
            flush=True
        )

        # ---- inserta en segundo plano --------------------------------------
        loop = asyncio.get_running_loop()

        async def _run():
            try:
                insert_audit(user_id, event_id, module_id, tail, raw_body)
            except Exception as e:
                print("[audit] error hilo:", repr(e), flush=True)

        loop.run_in_executor(None, lambda: asyncio.run(_run()))

        return response
