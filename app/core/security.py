"""
Security Configuration
──────────────────────────────────────────────────────────────────────────
Implements security features including authentication, rate limiting, and CORS.
"""

import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Any, Callable

from jwt import jwt
from fastapi import HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.pydanticConfig.settings import get_settings

cfg = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
security = HTTPBearer()
SECRET_KEY = cfg.SECRET_KEY or "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Rate limiter
limiter = Limiter(key_func=get_remote_address)



class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Custom rate limiting middleware with different limits per endpoint.
    """

    def __init__(self, app, default_limit: str = "100/minute"):
        super().__init__(app)
        self.default_limit = default_limit
        self.endpoint_limits = {
            "/backtest": "10/minute",
            "/grid-search": "5/minute",
            "/graphql": "200/minute",
            "/api/symbols": "1000/minute"
        }
        self.request_counts = {}

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = get_remote_address(request)

        # Get endpoint-specific limit
        path = request.url.path
        limit = self.default_limit
        for endpoint, endpoint_limit in self.endpoint_limits.items():
            if path.startswith(endpoint):
                limit = endpoint_limit
                break

        # Check rate limit
        if not self._check_rate_limit(client_ip, path, limit):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={"Retry-After": "60"}
            )

        # Process request
        response = await call_next(request)
        return response

    def _check_rate_limit(self, client_ip: str, path: str, limit: str) -> bool:
        """Check if request is within rate limit."""
        # Parse limit (e.g., "100/minute")
        count, period = limit.split("/")
        count = int(count)

        # Convert period to seconds
        period_seconds = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400
        }.get(period, 60)

        # Get current timestamp
        current_time = time.time()

        # Create key for this client/endpoint
        key = f"{client_ip}:{path}"

        # Clean old entries
        if key in self.request_counts:
            self.request_counts[key] = [
                timestamp for timestamp in self.request_counts[key]
                if current_time - timestamp < period_seconds
            ]
        else:
            self.request_counts[key] = []

        # Check if limit exceeded
        if len(self.request_counts[key]) >= count:
            return False

        # Add current request
        self.request_counts[key].append(current_time)
        return True


class SecurityHeaders(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict):
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Get current user from JWT token."""
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"username": username, "user_id": payload.get("user_id")}


def require_api_key(api_key: str = Security(HTTPBearer())):
    """Validate API key for certain endpoints."""
    if api_key.credentials != cfg.API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return api_key


# Decorator for rate limiting specific endpoints
def rate_limit(limit: str):
    """
    Decorator to apply rate limiting to specific endpoints.

    Usage:
        @router.get("/endpoint")
        @rate_limit("10/minute")
        async def endpoint():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Rate limiting logic would go here
            # For now, just pass through
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


# IP Whitelist/Blacklist
class IPFilterMiddleware(BaseHTTPMiddleware):
    """IP-based access control."""

    def __init__(self, app, whitelist: Optional[list] = None, blacklist: Optional[list] = None):
        super().__init__(app)
        self.whitelist = whitelist or []
        self.blacklist = blacklist or []

    async def dispatch(self, request: Request, call_next):
        client_ip = get_remote_address(request)

        # Check blacklist
        if self.blacklist and client_ip in self.blacklist:
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied"}
            )

        # Check whitelist (if configured, only whitelisted IPs allowed)
        if self.whitelist and client_ip not in self.whitelist:
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied"}
            )

        response = await call_next(request)
        return response


# Request validation
class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Validate and sanitize incoming requests."""

    async def dispatch(self, request: Request, call_next):
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > cfg.MAX_REQUEST_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request entity too large"}
            )

        # Validate content type for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith(("application/json", "multipart/form-data")):
                return JSONResponse(
                    status_code=415,
                    content={"detail": "Unsupported media type"}
                )

        response = await call_next(request)
        return response


# CORS configuration
def get_cors_config():
    """Get CORS configuration based on environment."""
    if cfg.ENVIRONMENT == "production":
        return {
            "allow_origins": cfg.ALLOWED_ORIGINS,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["*"],
            "max_age": 3600
        }
    else:
        # Development: allow all origins
        return {
            "allow_origins": ["*"],
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"]
        }


# API Key management
class APIKeyManager:
    """Manage API keys for different clients."""

    @staticmethod
    async def validate_api_key(api_key: str) -> Optional[Dict[str, Any]]:
        """Validate API key and return associated metadata."""
        # In production, this would check against database
        # For now, simple validation
        if api_key == cfg.API_KEY:
            return {
                "client_id": "default",
                "rate_limit": "1000/hour",
                "permissions": ["read", "write"]
            }
        return None

    @staticmethod
    async def create_api_key(client_id: str, permissions: list) -> str:
        """Create new API key for client."""
        # In production, generate secure key and store in database
        import secrets
        return secrets.token_urlsafe(32)