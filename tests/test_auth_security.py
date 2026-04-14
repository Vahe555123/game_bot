import unittest

from app.auth.security import (
    create_signed_oauth_state,
    generate_session_token,
    generate_verification_code,
    generate_verification_salt,
    hash_password,
    hash_session_token,
    hash_verification_code,
    verify_signed_oauth_state,
    verify_password,
    verify_verification_code,
)
from config.settings import settings


class AuthSecurityTests(unittest.TestCase):
    def test_password_hash_roundtrip(self):
        password_hash = hash_password("my-strong-password")

        self.assertNotEqual(password_hash, "my-strong-password")
        self.assertTrue(verify_password("my-strong-password", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))

    def test_verification_code_hash_roundtrip(self):
        code = generate_verification_code(settings.AUTH_EMAIL_CODE_LENGTH)
        salt = generate_verification_salt()
        code_hash = hash_verification_code(code, salt)
        wrong_code = "0" * settings.AUTH_EMAIL_CODE_LENGTH
        if wrong_code == code:
            wrong_code = "1" * settings.AUTH_EMAIL_CODE_LENGTH

        self.assertEqual(len(code), settings.AUTH_EMAIL_CODE_LENGTH)
        self.assertTrue(code.isdigit())
        self.assertTrue(verify_verification_code(code, salt, code_hash))
        self.assertFalse(verify_verification_code(wrong_code, salt, code_hash))

    def test_session_token_hash_is_stable(self):
        token = generate_session_token()

        self.assertEqual(hash_session_token(token), hash_session_token(token))
        self.assertNotEqual(hash_session_token(token), hash_session_token(token + "x"))

    def test_signed_oauth_state_roundtrip(self):
        payload = {"provider": "google", "next_path": "/profile", "iat": 123456}
        token = create_signed_oauth_state(payload, "secret-key")

        self.assertEqual(verify_signed_oauth_state(token, "secret-key"), payload)
        self.assertIsNone(verify_signed_oauth_state(token, "wrong-secret"))

    def test_signed_oauth_state_contains_only_vk_safe_characters(self):
        import re
        vk_safe_pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
        payload = {"p": "vk", "n": "/profile", "v": "code-verifier-value", "i": 1700000000}
        token = create_signed_oauth_state(payload, "secret-key")

        self.assertRegex(token, vk_safe_pattern)
        self.assertNotIn(".", token)

    def test_signed_oauth_state_backward_compatible_with_dot_separator(self):
        import json
        import base64
        import hashlib
        import hmac

        payload = {"provider": "google", "next_path": "/profile", "iat": 123456}
        serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload_part = base64.urlsafe_b64encode(serialized).decode("ascii").rstrip("=")
        signature = hmac.new("secret-key".encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).hexdigest()
        legacy_token = f"{payload_part}.{signature}"

        self.assertEqual(verify_signed_oauth_state(legacy_token, "secret-key"), payload)


if __name__ == "__main__":
    unittest.main()
