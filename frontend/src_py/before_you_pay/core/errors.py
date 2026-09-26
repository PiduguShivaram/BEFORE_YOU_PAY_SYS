"""Core exception definitions for the application."""

from typing import Any
from uuid import UUID, uuid4


class BeforeYouPayException(Exception):
    """Base application exception for Before You Pay."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.correlation_id = correlation_id or uuid4()


class NotImplementedServiceException(BeforeYouPayException):
    """Raised when an endpoint or interface method is a stub and not yet implemented."""

    def __init__(
        self,
        service_name: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message or f"Service or endpoint '{service_name}' is not yet implemented.",
            code="NOT_IMPLEMENTED",
            status_code=501,
            details=details or {"service": service_name, "stage": "Phase 0/1 Contract Stub"},
        )


class EntityNotFoundException(BeforeYouPayException):
    """Raised when a requested entity (document, page, field) is not found."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity_type} with ID '{entity_id}' not found.",
            code="ENTITY_NOT_FOUND",
            status_code=404,
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


class ContractViolationException(BeforeYouPayException):
    """Raised when a contract invariant (e.g. orphan claim or invalid coordinates) is violated."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="CONTRACT_VIOLATION",
            status_code=422,
            details=details,
        )
