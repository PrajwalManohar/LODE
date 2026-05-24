"""Supabase JWT verification for protecting FastAPI routes.

The frontend sends the user's Supabase access token as `Authorization: Bearer
<jwt>`. We verify it with the project's JWT secret (HS256) and expose the
caller's id + role as a dependency.

Backwards-compatible: when SUPABASE_JWT_SECRET is unset (e.g. local SQLite
demo), verification is skipped and routes run unauthenticated. Set the secret
in production to enforce auth at the API layer as well as via RLS.

Usage:
    from backend.auth import require_user, require_admin, CurrentUser

    @router.get("/admin/audit")
    def audit(user: CurrentUser = Depends(require_admin)): ...
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vein.config import settings

try:
    import jwt  # PyJWT
except ImportError:  # pragma: no cover - dependency added in requirements.txt
    jwt = None  # type: ignore

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: Optional[str]
    email: Optional[str]
    role: str  # "user" | "admin" | "anon"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _decode(token: str) -> dict:
    if jwt is None:
        raise HTTPException(status_code=500, detail="PyJWT not installed")
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except Exception as exc:  # invalid / expired / wrong signature
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        )


def current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> CurrentUser:
    """Resolve the caller. Permissive when JWT verification is not configured."""
    if not settings.supabase_jwt_secret:
        return CurrentUser(id=None, email=None, role="anon")
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    claims = _decode(creds.credentials)
    # Supabase puts custom claims under app_metadata / user_metadata; role here
    # mirrors the profiles.role we set. Fall back to the built-in 'role' claim.
    meta = claims.get("app_metadata") or {}
    role = meta.get("role") or claims.get("user_role") or "user"
    return CurrentUser(id=claims.get("sub"), email=claims.get("email"), role=role)


def require_user(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if settings.supabase_jwt_secret and user.id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    # When auth is unconfigured (demo), don't hard-block admin routes.
    if not settings.supabase_jwt_secret:
        return user
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
