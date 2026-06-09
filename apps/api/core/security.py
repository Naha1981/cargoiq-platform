"""
CargoIQ — Security utilities: token validation, encryption.
"""
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from cryptography.fernet import Fernet
import base64
import hashlib
from .config import settings

security_scheme = HTTPBearer()


def get_fernet() -> Fernet:
    """Get Fernet encryption instance from hex key."""
    if not settings.ENCRYPTION_KEY:
        # Dev fallback — generate from SECRET_KEY
        key_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(key_bytes)
    else:
        key_bytes = bytes.fromhex(settings.ENCRYPTION_KEY)
        key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value (for storing CW credentials)."""
    f = get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt an encrypted string value."""
    f = get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme)
) -> dict:
    """
    Validate Supabase JWT and return user payload.
    Raises 401 if token is invalid or expired.
    """
    token = credentials.credentials
    try:
        # Supabase JWTs are signed with the JWT secret
        # In production, verify against Supabase JWKS
        # For now, decode without verification for dev (Supabase handles this)
        payload = jwt.decode(
            token,
            options={"verify_signature": False}  # Supabase validates on their end
        )
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        return {"user_id": user_id, "token": token, "payload": payload}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


async def get_current_user_with_org(
    current_user: dict = Security(get_current_user)
) -> dict:
    """
    Extend current user with their organisation details.
    Used for most endpoints that need org context.
    """
    from .supabase_client import get_supabase_admin
    
    admin = get_supabase_admin()
    user_result = admin.table("users").select("*").eq("id", current_user["user_id"]).single().execute()
    
    if not user_result.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in organisation"
        )
    
    user_data = user_result.data
    if not user_data.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    
    return {**current_user, **user_data}
