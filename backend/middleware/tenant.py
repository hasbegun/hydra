"""
Tenant isolation middleware.

Extracts tenant context from Anima JWT tokens and injects a
``TenantContext`` into ``request.state.tenant`` for downstream route
handlers to use.

Two operating modes controlled by ``TENANT_MODE``:

* ``single`` (default) — No JWT required. All requests get a default
  tenant context.  Backward-compatible with existing deployments that
  don't have Anima.
* ``multi`` — Every request (except health/docs) must carry a valid
  Anima JWT.  Tenant ID, user ID, and roles are extracted from claims.
"""
import base64
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths that never require auth (health checks, docs, OpenAPI schema)
_PUBLIC_PATHS = frozenset({
    "/", "/health", "/version",
    "/api/docs", "/api/redoc", "/openapi.json",
})

# Default tenant ID for single-tenant mode and backfill
DEFAULT_TENANT_ID = "default"


@dataclass(frozen=True)
class TenantContext:
    """Immutable tenant context attached to every request.

    Attributes:
        tenant_id: Identifier for the tenant (from JWT ``tenant_id`` or
                   ``org_id`` claim, or ``"default"`` in single-tenant mode).
        user_id:   Identifier for the acting user (from JWT ``sub`` claim).
        roles:     List of role strings (from JWT ``roles`` claim).
    """
    tenant_id: str = DEFAULT_TENANT_ID
    user_id: str = ""
    roles: List[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        """True if the user holds the SYSTEM_ADMIN role."""
        return "SYSTEM_ADMIN" in self.roles


def _decode_jwt_payload(token: str) -> dict:
    """Decode the payload section of a JWT without signature verification.

    This is intentionally *not* verifying the signature — that
    responsibility belongs to the Anima JWKS integration (future phase).
    For Phase 1, we trust tokens that reach the backend because they
    passed through the API gateway / Anima proxy.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed JWT: expected 3 dot-separated parts")

    # JWT base64url decoding: add padding and decode
    payload_b64 = parts[1]
    # Add padding
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding

    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    return json.loads(payload_bytes)


def _extract_tenant_context(token: str) -> TenantContext:
    """Build a TenantContext from a JWT Bearer token string."""
    claims = _decode_jwt_payload(token)

    # tenant_id: try 'tenant_id' first (Anima convention), then 'org_id'
    tenant_id = claims.get("tenant_id") or claims.get("org_id") or DEFAULT_TENANT_ID

    # user_id: standard 'sub' claim
    user_id = claims.get("sub", "")

    # roles: try 'roles' (list), then 'role' (single string)
    roles_claim = claims.get("roles")
    if isinstance(roles_claim, list):
        roles = roles_claim
    elif isinstance(roles_claim, str):
        roles = [roles_claim]
    else:
        role_single = claims.get("role")
        roles = [role_single] if role_single else []

    return TenantContext(tenant_id=tenant_id, user_id=user_id, roles=roles)


class TenantMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that injects ``TenantContext`` into every request.

    Args:
        app: The ASGI application.
        tenant_mode: ``"single"`` (no auth required) or ``"multi"``
                     (Anima JWT required).
    """

    def __init__(self, app, tenant_mode: str = "single"):
        super().__init__(app)
        self.tenant_mode = tenant_mode
        logger.info(f"TenantMiddleware initialized in '{tenant_mode}' mode")

    async def dispatch(self, request: Request, call_next):
        # Public paths bypass auth in all modes
        if request.url.path in _PUBLIC_PATHS:
            request.state.tenant = TenantContext()
            return await call_next(request)

        if self.tenant_mode == "single":
            # Single-tenant: no auth required, default context.
            # Still try to extract tenant from JWT if present — allows
            # gradual migration to multi-tenant without breaking callers.
            tenant = self._try_extract_from_header(request)
            request.state.tenant = tenant or TenantContext()
            return await call_next(request)

        # Multi-tenant mode: JWT required
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
            )

        token = auth_header[7:].strip()
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Empty Bearer token"},
            )

        try:
            tenant = _extract_tenant_context(token)
        except (ValueError, json.JSONDecodeError, Exception) as exc:
            logger.warning(f"JWT decode failed: {exc}")
            return JSONResponse(
                status_code=401,
                content={"detail": f"Invalid token: {exc}"},
            )

        request.state.tenant = tenant
        return await call_next(request)

    @staticmethod
    def _try_extract_from_header(request: Request) -> Optional[TenantContext]:
        """Best-effort JWT extraction from Authorization header.

        Returns None if no valid JWT is found (non-error in single mode).
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:].strip()
        if not token:
            return None
        try:
            return _extract_tenant_context(token)
        except Exception:
            return None


def get_tenant(request: Request) -> TenantContext:
    """Extract TenantContext from a request.

    Use in route handlers:
        @router.post("/scan/start")
        async def start_scan(request: Request, config: ScanConfigRequest):
            tenant = get_tenant(request)
            ...
    """
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        return TenantContext()
    return tenant
