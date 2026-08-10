from src.core.default_exception import DefaultException


class MessagePublishingException(DefaultException):
    def __init__(self, error: str):
        super().__init__(status_code=503, message=error)


class MessageRejectedException(DefaultException):
    def __init__(self, error: str):
        super().__init__(status_code=422, message=error)
