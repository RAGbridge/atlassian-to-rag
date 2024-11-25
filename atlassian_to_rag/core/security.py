import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt


@dataclass
class SecurityConfig:
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry: timedelta = timedelta(hours=1)
    api_key_header: str = "X-API-Key"
    allowed_origins: list[str] = None


class Security:
    def __init__(self, config: SecurityConfig):
        self.config = config

    def create_jwt(self, payload: Dict[str, Any]) -> str:
        """Create a JWT token."""
        exp = datetime.utcnow() + self.config.jwt_expiry
        payload["exp"] = exp
        return jwt.encode(payload, self.config.jwt_secret, algorithm=self.config.jwt_algorithm)

    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a JWT token."""
        try:
            return jwt.decode(token, self.config.jwt_secret, algorithms=[self.config.jwt_algorithm])
        except jwt.InvalidTokenError:
            return None

    def verify_api_key(self, api_key: str, stored_key: str) -> bool:
        """Verify an API key using constant-time comparison."""
        return hmac.compare_digest(
            hashlib.sha256(api_key.encode()).hexdigest(),
            hashlib.sha256(stored_key.encode()).hexdigest(),
        )

    def is_allowed_origin(self, origin: str) -> bool:
        """Check if the origin is allowed."""
        if not self.config.allowed_origins:
            return False
        return origin in self.config.allowed_origins or "*" in self.config.allowed_origins
