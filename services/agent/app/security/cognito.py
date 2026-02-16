import logging
import time
from typing import Any, Dict, Optional

import requests
from aiohttp import web
from jose.jwk import construct
from jose.jws import get_unverified_headers
from jose.jwt import get_unverified_claims
from jose.utils import base64url_decode

from ..config.settings import Settings


logger = logging.getLogger(__name__)


class _JWKCache:
    def __init__(self) -> None:
        self.kid_to_key: Dict[str, Dict[str, Any]] = {}
        self.expires_at: float = 0.0

    def is_valid(self) -> bool:
        return time.time() < self.expires_at and bool(self.kid_to_key)

    def set(self, keys: Dict[str, Dict[str, Any]], ttl_seconds: int = 3600) -> None:
        self.kid_to_key = keys
        self.expires_at = time.time() + ttl_seconds


class CognitoAuthService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._cache = _JWKCache()

    def _fetch_jwks(self) -> Dict[str, Dict[str, Any]]:
        region = self.settings.REGION
        user_pool_id = self.settings.USER_POOL_ID
        if not region or not user_pool_id:
            raise web.HTTPInternalServerError(text="Cognito settings missing")
        url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        keys = resp.json().get("keys", [])
        return {key["kid"]: key for key in keys}

    def _get_public_keys(self) -> Dict[str, Dict[str, Any]]:
        if self._cache.is_valid():
            return self._cache.kid_to_key
        keys = self._fetch_jwks()
        self._cache.set(keys)
        return keys

    def _verify_token(self, token: str) -> Dict[str, Any]:
        headers = get_unverified_headers(token)
        kid = headers.get("kid")
        if not kid:
            raise web.HTTPUnauthorized()

        keys = self._get_public_keys()
        key = keys.get(kid)
        if not key:
            # refresh once in case of rotation
            keys = self._fetch_jwks()
            self._cache.set(keys, ttl_seconds=300)
            key = keys.get(kid)
            if not key:
                raise web.HTTPUnauthorized()

        message, encoded_signature = str(token).rsplit(".", 1)
        decoded_signature = base64url_decode(encoded_signature.encode("utf-8"))
        public_key = construct(key)
        verified = public_key.verify(message.encode("utf-8"), decoded_signature)
        if not verified:
            raise web.HTTPUnauthorized()

        claims = get_unverified_claims(token)

        # exp
        if time.time() > claims.get("exp", 0):
            raise web.HTTPUnauthorized()
        # aud (client id)
        client_id_expected = self.settings.USER_POOL_CLIENT_ID
        aud = claims.get("aud", client_id_expected)
        if client_id_expected and aud != client_id_expected:
            raise web.HTTPUnauthorized()
        # iss
        region = self.settings.REGION
        user_pool_id = self.settings.USER_POOL_ID
        issuer_expected = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        if claims.get("iss") != issuer_expected:
            raise web.HTTPUnauthorized()

        return claims

    async def verify_request(self, request: web.Request) -> Dict[str, Any]:
        auth_header = request.headers.get("Authorization") or request.query.get("Authorization")
        if not auth_header:
            raise web.HTTPUnauthorized()
        token = auth_header.replace("Bearer", "").strip()
        try:
            claims = self._verify_token(token)
            return {"claims": claims}
        except Exception as exc:
            logger.exception("Cognito verification failed: %s", exc)
            raise web.HTTPUnauthorized()


