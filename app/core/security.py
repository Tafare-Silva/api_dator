from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"


def criar_token(data: dict, expira_minutos: int | None = None) -> str:
    payload = data.copy()
    minutos = expira_minutos or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expiracao = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    payload.update({"exp": expiracao})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
