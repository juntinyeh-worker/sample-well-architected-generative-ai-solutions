"""
Exceptions for the Support Interactions client.

Mirrors the pattern boto3 uses: all exceptions inherit from ClientError,
and are accessible via client.exceptions.<ExceptionName> — so when the
real SDK ships, callers catch the same exception class names.
"""


class SupportInteractionsError(Exception):
    """Base exception. Mirrors botocore.exceptions.BotoCoreError."""

    def __init__(self, error_response: dict, operation_name: str):
        msg = error_response.get("Error", {}).get("Message", str(error_response))
        super().__init__(
            f"An error occurred ({self._code(error_response)}) "
            f"when calling the {operation_name} operation: {msg}"
        )
        self.response = error_response
        self.operation_name = operation_name

    @staticmethod
    def _code(error_response: dict) -> str:
        return error_response.get("Error", {}).get("Code", "UnknownError")


# ── Typed exceptions — one per AWS error code ──────────────────────────────────
# Named to match what the real SDK will almost certainly ship.

class ClientError(SupportInteractionsError):
    """Catch-all for any error returned by the service."""


class AccessDeniedException(ClientError):
    """IAM permissions missing for this operation."""


class SubscriptionRequiredException(ClientError):
    """Account does not have a qualifying AWS Support plan."""


class InteractionNotFoundException(ClientError):
    """The specified interaction ID does not exist."""


class ValidationException(ClientError):
    """Request parameters failed validation."""


class ThrottlingException(ClientError):
    """Request rate exceeded. Caller should back off and retry."""


class InternalServerError(ClientError):
    """AWS-side error. Safe to retry with exponential backoff."""


# ── Factory: map AWS error codes → typed exceptions ───────────────────────────

_CODE_MAP: dict[str, type[ClientError]] = {
    "AccessDeniedException":        AccessDeniedException,
    "AccessDenied":                 AccessDeniedException,
    "SubscriptionRequiredException": SubscriptionRequiredException,
    "InteractionNotFoundException":  InteractionNotFoundException,
    "ResourceNotFoundException":     InteractionNotFoundException,
    "ValidationException":           ValidationException,
    "ThrottlingException":           ThrottlingException,
    "InternalServerError":           InternalServerError,
    "InternalFailure":               InternalServerError,
    "ServiceUnavailableException":   InternalServerError,
}


def from_response(error_response: dict, operation_name: str) -> ClientError:
    """Return the most specific typed exception for a given error response."""
    code = SupportInteractionsError._code(error_response)
    cls = _CODE_MAP.get(code, ClientError)
    return cls(error_response, operation_name)
