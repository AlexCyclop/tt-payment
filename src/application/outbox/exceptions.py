from src.core.default_exception import DefaultException


class MessagePublishingException(DefaultException):
    def __init__(self, attempts: int, error: str):
        self.attempts = attempts
        super().__init__(status_code=503, message=f"{error}")
