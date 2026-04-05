class AuthServiceError(Exception):
    """Controlled error raised by the auth service."""

    def __init__(self, status_code: int, message: str, *, extra: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.extra = extra or {}
