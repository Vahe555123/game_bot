import base64
import hashlib
import hmac
import json
import secrets
from typing import Any, Final

SCRYPT_N: Final[int] = 2**14
SCRYPT_R: Final[int] = 8
SCRYPT_P: Final[int] = 1
SCRYPT_DKLEN: Final[int] = 64


def _b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N,
        SCRYPT_R,
        SCRYPT_P,
        _b64encode(salt),
        _b64encode(derived_key),
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt_b64, hash_b64 = encoded_hash.split("$", 5)
        if algorithm != "scrypt":
            return False
    except ValueError:
        return False

    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=_b64decode(salt_b64),
        n=int(n),
        r=int(r),
        p=int(p),
        dklen=len(_b64decode(hash_b64)),
    )

    return secrets.compare_digest(derived_key, _b64decode(hash_b64))


def generate_verification_code(length: int = 6) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def generate_verification_salt() -> str:
    return secrets.token_hex(16)


def hash_verification_code(code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()


def verify_verification_code(code: str, salt: str, expected_hash: str) -> bool:
    actual_hash = hash_verification_code(code, salt)
    return secrets.compare_digest(actual_hash, expected_hash)


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


_SHA256_HEX_LENGTH: Final[int] = 64


def create_signed_oauth_state(payload: dict[str, Any], secret: str) -> str:
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _urlsafe_b64encode(serialized)
    signature = hmac.new(secret.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload_part}{signature}"


def verify_signed_oauth_state(state: str, secret: str) -> dict[str, Any] | None:
    if len(state) <= _SHA256_HEX_LENGTH:
        return None

    if "." in state:
        payload_part, signature = state.split(".", 1)
    else:
        payload_part = state[:-_SHA256_HEX_LENGTH]
        signature = state[-_SHA256_HEX_LENGTH:]

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not secrets.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(_urlsafe_b64decode(payload_part).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    return payload
