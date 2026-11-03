"""Process-key integrity tokens for read-only replacement previews."""

import base64
import hashlib
import hmac
import json
import secrets

from src.model.scheduling import SchedulingError

_KEY = secrets.token_bytes(32)


def proposal_digest(proposal: bytes) -> str:
    """Return a stable digest of a supplied proposal."""
    return hashlib.sha256(proposal).hexdigest()


def issue_token(schedule_id: int, version: int, operation: str, digest: str) -> str:
    """Sign a preview binding with the current process key."""
    payload = json.dumps([schedule_id, version, operation, digest], separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(_KEY, encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_token(token: str, schedule_id: int, operation: str, digest: str) -> int:
    """Return the signed version or reject an altered preview."""
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(_KEY, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if (
            not isinstance(payload, list)
            or len(payload) != 4
            or payload[0] != schedule_id
            or payload[2:] != [operation, digest]
            or type(payload[1]) is not int
        ):
            raise ValueError("binding")
        return payload[1]
    except (ValueError, TypeError, UnicodeError) as error:
        raise SchedulingError("INVALID_PREVIEW", "preview token does not match proposal") from error
