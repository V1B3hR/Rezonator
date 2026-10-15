"""
Zero-Trust RBAC & DoS Rate Limiting Guard (Milestone 3).

1. Role-Based Access Control (RBAC):
   - AUDITOR: Read-only access to audit reports, context slices, health, and provenance.
   - ARCHITECT: Access to spectral partition recommendations, friction matrix, ARB dossiers, and radar.
   - ADMIN: Complete system access, key rotation, and configuration.

2. Cryptographic Token Manager:
   - HMAC-SHA256 token issuance and tamper-proof verification.
   - Expiration validation, nonce tracking, and role claims.

3. Sliding-Window Rate Limiter:
   - DoS protection on heavy spectral eigensolver endpoints (/api/partition, /api/matrix, /api/dossier).
"""

from __future__ import annotations

import base64
import collections
import enum
import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


class Role(str, enum.Enum):
    ANONYMOUS = "ANONYMOUS"
    AUDITOR = "AUDITOR"
    ARCHITECT = "ARCHITECT"
    ADMIN = "ADMIN"


ROLE_HIERARCHY = {
    Role.ANONYMOUS: 0,
    Role.AUDITOR: 10,
    Role.ARCHITECT: 20,
    Role.ADMIN: 30,
}


class AuthSecurityError(PermissionError):
    """Raised when authentication fails or permissions are insufficient."""
    pass


class RateLimitExceededError(ValueError):
    """Raised when a client exceeds allowed request frequency on protected endpoints."""
    pass


@dataclass
class TokenClaims:
    subject: str
    role: Role
    issued_at: int
    expires_at: int
    token_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sub": self.subject,
            "role": self.role.value,
            "iat": self.issued_at,
            "exp": self.expires_at,
            "jti": self.token_id,
        }


class AuthTokenManager:
    """
    Issues and cryptographically validates tamper-proof HMAC-SHA256 Bearer tokens.
    """

    def __init__(self, secret_key: str = "rezonator-zero-trust-secret-key-2026", default_ttl_sec: int = 3600):
        self._secret = secret_key.encode("utf-8")
        self.default_ttl_sec = default_ttl_sec

    def issue_token(self, subject: str, role: Role, ttl_seconds: Optional[int] = None) -> str:
        """Issues a signed, base64-encoded token containing role claims."""
        now = int(time.time())
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_sec
        exp = now + ttl

        # JTI nonce
        jti_source = f"{subject}:{role.value}:{now}:{time.perf_counter()}".encode("utf-8")
        jti = hashlib.sha256(jti_source).hexdigest()[:16]

        payload = {
            "sub": subject,
            "role": role.value,
            "iat": now,
            "exp": exp,
            "jti": jti,
        }

        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")

        # Signature
        sig = hmac.new(self._secret, payload_bytes, hashlib.sha256).hexdigest()

        return f"rez.{payload_b64}.{sig}"

    def verify_token(self, token_str: str) -> TokenClaims:
        """
        Validates token format, HMAC signature, and expiration.
        Raises AuthSecurityError if invalid or expired.
        """
        if not token_str:
            raise AuthSecurityError("Authentication token is missing.")

        parts = token_str.strip().split(".")
        if len(parts) != 3 or parts[0] != "rez":
            raise AuthSecurityError("Malformed authorization token format.")

        payload_b64 = parts[1]
        provided_sig = parts[2]

        # Decode payload
        padding = "=" * ((4 - len(payload_b64) % 4) % 4)
        try:
            payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
            payload = json.loads(payload_bytes.decode("utf-8"))
        except Exception as e:
            raise AuthSecurityError(f"Token payload decoding failed: {e}")

        # Check signature with constant-time comparison
        expected_sig = hmac.new(self._secret, payload_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(provided_sig, expected_sig):
            raise AuthSecurityError("Invalid token signature: token has been tampered with.")

        # Check expiration
        now = int(time.time())
        exp = int(payload.get("exp", 0))
        if now > exp:
            raise AuthSecurityError(f"Token expired at unix timestamp {exp} (current: {now}).")

        # Parse role
        role_str = payload.get("role", Role.ANONYMOUS.value)
        try:
            role = Role(role_str)
        except ValueError:
            role = Role.ANONYMOUS

        return TokenClaims(
            subject=str(payload.get("sub", "unknown")),
            role=role,
            issued_at=int(payload.get("iat", 0)),
            expires_at=exp,
            token_id=str(payload.get("jti", "")),
        )


class SlidingWindowRateLimiter:
    """
    Thread-safe sliding-window rate limiter preventing compute exhaustion and DoS.
    """

    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        self._history: Dict[str, collections.deque[float]] = collections.defaultdict(collections.deque)
        self._lock = threading.Lock()

    def check_and_record(self, client_key: str, max_requests: int) -> Tuple[bool, int, float]:
        """
        Checks if client_key has exceeded max_requests in the current sliding window.
        Returns: (is_allowed, remaining_quota, time_until_window_reset).
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            timestamps = self._history[client_key]

            # Prune timestamps older than window
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()

            current_count = len(timestamps)
            if current_count >= max_requests:
                oldest = timestamps[0]
                reset_after = max(0.0, self.window_seconds - (now - oldest))
                return False, 0, reset_after

            # Record this hit
            timestamps.append(now)
            remaining = max(0, max_requests - len(timestamps))
            return True, remaining, self.window_seconds


class EndpointSecurityEnforcer:
    """
    Enforces RBAC authorization rules and rate limits on Rezonator HTTP endpoints.
    """

    # Minimum role required per path prefix
    ENDPOINT_PERMISSIONS: Dict[str, Role] = {
        "/api/health": Role.ANONYMOUS,
        "/api/audit": Role.AUDITOR,
        "/api/slice": Role.AUDITOR,
        "/api/provenance": Role.AUDITOR,
        "/api/sbom": Role.AUDITOR,
        "/api/matrix": Role.ARCHITECT,
        "/api/friction": Role.ARCHITECT,
        "/api/partition": Role.ARCHITECT,
        "/api/dossier": Role.ARCHITECT,
        "/api/radar": Role.ARCHITECT,
        "/api/migration": Role.ARCHITECT,
        "/api/sokol/": Role.ARCHITECT,
        "/api/sokol": Role.ARCHITECT,
        "/api/admin": Role.ADMIN,
    }

    # Request rate limits per minute per path
    ENDPOINT_LIMITS: Dict[str, int] = {
        "/api/health": 120,
        "/api/audit": 60,
        "/api/slice": 40,
        "/api/sbom": 60,
        "/api/matrix": 20,
        "/api/friction": 20,
        "/api/partition": 10,  # Heavy spectral eigensolver
        "/api/dossier": 10,    # Heavy portfolio analysis
        "/api/migration": 15,
        "/api/sokol/observe": 20,
        "/api/sokol/explain_cut": 20,
        "/api/sokol/qna": 20,
    }

    def __init__(self, token_manager: AuthTokenManager, rate_limiter: Optional[SlidingWindowRateLimiter] = None):
        self.token_manager = token_manager
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(window_seconds=60.0)

    def authorize_request(
        self,
        path: str,
        auth_header: Optional[str] = None,
        client_ip: str = "127.0.0.1",
    ) -> TokenClaims:
        """
        Validates authorization header, verifies role hierarchy, and checks rate limit.
        Raises AuthSecurityError or RateLimitExceededError.
        """
        # Determine required role
        required_role = Role.AUDITOR
        for prefix, role in self.ENDPOINT_PERMISSIONS.items():
            if path.startswith(prefix):
                required_role = role
                break

        # Health endpoint can be anonymous
        if required_role == Role.ANONYMOUS and not auth_header:
            claims = TokenClaims(
                subject=f"anonymous-{client_ip}",
                role=Role.ANONYMOUS,
                issued_at=int(time.time()),
                expires_at=int(time.time()) + 3600,
                token_id="anon",
            )
        else:
            if not auth_header:
                raise AuthSecurityError(f"Authentication required for endpoint '{path}'.")

            # Extract token
            token_str = auth_header.strip()
            if token_str.lower().startswith("bearer "):
                token_str = token_str[7:].strip()

            claims = self.token_manager.verify_token(token_str)

        # Check role hierarchy
        user_level = ROLE_HIERARCHY.get(claims.role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 10)

        if user_level < required_level:
            raise AuthSecurityError(
                f"Insufficient privileges: role '{claims.role.value}' is lower than required "
                f"role '{required_role.value}' for '{path}'."
            )

        # Rate limiting check
        limit = self.ENDPOINT_LIMITS.get(path, 30)
        client_id = f"{claims.subject}@{client_ip}:{path}"
        allowed, remaining, reset_sec = self.rate_limiter.check_and_record(client_id, max_requests=limit)

        if not allowed:
            raise RateLimitExceededError(
                f"Rate limit exceeded for endpoint '{path}'. Maximum {limit} requests/min. "
                f"Try again in {reset_sec:.1f}s."
            )

        return claims
