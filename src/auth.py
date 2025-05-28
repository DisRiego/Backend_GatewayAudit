import os
from jose import jwt, JWTError

SECRET    = os.getenv("JWT_SECRET", "dev-secret")
ALGORITHM = "HS256"

def verify_token(token: str) -> bool:
    try:
        jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return True
    except JWTError:
        return False
