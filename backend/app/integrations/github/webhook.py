import hmac
from hashlib import sha256


def verify_github_signature(secret: str, payload: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload, sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

