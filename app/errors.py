from typing import Any


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, **details: Any) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        super().__init__(code)

    def payload(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}
