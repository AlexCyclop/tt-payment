from src.core.default_exception import DefaultException


class IdempotencyKeyAlreadyUsedException(DefaultException):
    def __init__(self):
        super().__init__(
            status_code=409, message="Such idempotency key is already used."
        )


class PaymentNotFound(DefaultException):
    def __init__(self):
        super().__init__(status_code=404, message="Payment with such id not found.")
