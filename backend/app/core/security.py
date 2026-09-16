import os
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
import jwt
from app.config import settings

# Fallback robust password hashing using HMAC-SHA256 with salt if passlib has bcrypt version issues on Python 3.14
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    USE_PASSLIB = True
except Exception:
    USE_PASSLIB = False


def hash_password(password: str) -> str:
    """Hash a plain text password safely."""
    if USE_PASSLIB:
        try:
            return pwd_context.hash(password)
        except Exception:
            pass
    # Fallback salt-based HMAC-SHA256 hashing
    salt = os.urandom(16).hex()
    hashed = hmac.new(salt.encode('utf-8'), password.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"sha256${salt}${hashed}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password string."""
    if hashed_password.startswith("sha256$"):
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
        _, salt, expected_hash = parts
        computed = hmac.new(salt.encode('utf-8'), plain_password.encode('utf-8'), hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, expected_hash)
    
    if USE_PASSLIB:
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False
    return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": now
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")
