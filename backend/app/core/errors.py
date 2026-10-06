class ApiError(Exception):
    def __init__(self, status_code: int, message: str, errors: list | None = None):
        self.status_code = status_code
        self.message = message
        self.errors = errors or []
        super().__init__(message)

    @classmethod
    def bad_request(cls, message: str = "Bad Request", errors: list | None = None):
        return cls(400, message, errors)

    @classmethod
    def unauthorized(cls, message: str = "Unauthorized"):
        return cls(401, message)

    @classmethod
    def forbidden(cls, message: str = "Forbidden"):
        return cls(403, message)

    @classmethod
    def not_found(cls, message: str = "Resource not found"):
        return cls(404, message)

    @classmethod
    def conflict(cls, message: str = "Conflict"):
        return cls(409, message)

    @classmethod
    def internal(cls, message: str = "Internal Server Error"):
        return cls(500, message)

    @classmethod
    def service_unavailable(cls, message: str = "Service Unavailable"):
        return cls(503, message)
