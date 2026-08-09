class DefaultException(Exception):
    def __init__(self, status_code: int, message: str, detail: dict | None = None):
        self.status_code = status_code
        self.message = message
        self.detail = detail or {}
