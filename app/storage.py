"""Redis-backed storage for short links.

Kept separate from the web layer so tests can hand it a fake Redis client.
"""

import secrets
import string

import redis

ALPHABET = string.ascii_letters + string.digits  # 62 characters
CODE_LENGTH = 6  # 62^6 ≈ 56 billion possible codes
KEY_PREFIX = "link:"  # namespacing keys is a Redis convention: "link:ab12xY"


class LinkStore:
    def __init__(self, client: redis.Redis):
        self.client = client

    def create(self, url: str) -> str:
        """Save the URL under a new random code and return the code."""
        while True:
            # `secrets` (not `random`) gives unpredictable codes, so nobody can guess other people's links
            code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
            # nx=True means "only set if the key doesn't exist", so a rare collision never overwrites a link
            if self.client.set(KEY_PREFIX + code, url, nx=True):
                return code

    def get(self, code: str) -> str | None:
        """Return the URL for a code, or None if it doesn't exist."""
        return self.client.get(KEY_PREFIX + code)

    def ping(self) -> bool:
        """True if Redis answers. Used by the readiness check."""
        try:
            return bool(self.client.ping())
        except redis.RedisError:
            return False
