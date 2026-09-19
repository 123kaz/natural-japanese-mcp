from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl


DEFAULT_RESOURCE_SERVER_URL = "https://natural-japanese-mcp.onrender.com/mcp"
DEFAULT_REQUIRED_SCOPE = "natural-japanese:use"


@dataclass(frozen=True)
class OAuthConfig:
    issuer_url: str
    resource_server_url: str
    audience: str
    required_scope: str


def load_oauth_config() -> OAuthConfig:
    issuer_url = os.environ.get("AUTH0_ISSUER_URL", "").strip()
    if not issuer_url:
        raise RuntimeError("AUTH0_ISSUER_URL is required")

    issuer_url = issuer_url.rstrip("/") + "/"
    resource_server_url = os.environ.get(
        "MCP_PUBLIC_URL", DEFAULT_RESOURCE_SERVER_URL
    ).strip()
    audience = os.environ.get("AUTH0_AUDIENCE", resource_server_url).strip()
    required_scope = os.environ.get(
        "MCP_REQUIRED_SCOPE", DEFAULT_REQUIRED_SCOPE
    ).strip()

    if not resource_server_url:
        raise RuntimeError("MCP_PUBLIC_URL must not be empty")
    if audience != resource_server_url:
        raise RuntimeError(
            "AUTH0_AUDIENCE must equal MCP_PUBLIC_URL so the Auth0 API audience "
            "matches the MCP RFC 8707 resource identifier"
        )
    if not required_scope:
        raise RuntimeError("MCP_REQUIRED_SCOPE must not be empty")

    return OAuthConfig(
        issuer_url=issuer_url,
        resource_server_url=resource_server_url,
        audience=audience,
        required_scope=required_scope,
    )


class Auth0TokenVerifier(TokenVerifier):
    def __init__(self, config: OAuthConfig) -> None:
        self._config = config
        self._jwks_client = PyJWKClient(
            f"{config.issuer_url}.well-known/jwks.json"
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token).key
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._config.audience,
                issuer=self._config.issuer_url,
            )
        except Exception:
            return None

        raw_scope = claims.get("scope", "")
        if isinstance(raw_scope, str):
            scopes = [scope for scope in raw_scope.split() if scope]
        elif isinstance(raw_scope, list):
            scopes = [str(scope) for scope in raw_scope if scope]
        else:
            scopes = []

        client_id = claims.get("azp") or claims.get("client_id") or claims.get("sub")
        if not isinstance(client_id, str) or not client_id:
            return None

        subject = claims.get("sub")
        expires_at = claims.get("exp")

        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=int(expires_at) if isinstance(expires_at, (int, float)) else None,
            resource=self._config.resource_server_url,
            subject=subject if isinstance(subject, str) else None,
            claims={"iss": claims.get("iss")},
        )


def build_auth_settings(config: OAuthConfig) -> AuthSettings:
    return AuthSettings(
        issuer_url=AnyHttpUrl(config.issuer_url),
        resource_server_url=AnyHttpUrl(config.resource_server_url),
        required_scopes=[config.required_scope],
        validate_token_resource=True,
    )
