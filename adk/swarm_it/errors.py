"""
Structured Error Handling - Phase 1 Quick Win

Provides clear, actionable error messages with:
- Error codes for programmatic handling
- Detailed messages for debugging
- Actionable guidance for resolution
- Context preservation for observability
"""

from typing import Dict, Any, Optional
from enum import Enum


class ErrorCode(Enum):
    """Error codes for certification failures."""

    # Input validation errors (1xx)
    PROMPT_TOO_SHORT = "E101"
    PROMPT_TOO_LONG = "E102"
    PROMPT_EMPTY = "E103"
    INVALID_MODEL = "E104"
    INVALID_THRESHOLD = "E105"

    # Rotor errors (2xx)
    ROTOR_TIMEOUT = "E201"
    ROTOR_UNAVAILABLE = "E202"
    ROTOR_INFERENCE_FAILED = "E203"
    EMBEDDING_INVALID = "E204"

    # API errors (3xx)
    API_RATE_LIMIT = "E301"
    API_KEY_INVALID = "E302"
    API_TIMEOUT = "E303"
    API_UNAVAILABLE = "E304"

    # Network errors (4xx)
    NETWORK_PARTITION = "E401"
    NETWORK_TIMEOUT = "E402"
    CONNECTION_FAILED = "E403"

    # Quality gate errors (5xx)
    GATE_INTEGRITY_FAILED = "E501"
    GATE_NOISE_FAILED = "E502"
    GATE_RELEVANCE_FAILED = "E503"
    GATE_STABILITY_FAILED = "E504"
    GATE_COMPATIBILITY_FAILED = "E505"

    # System errors (6xx)
    OUT_OF_MEMORY = "E601"
    SIDECAR_CRASHED = "E602"
    DOWNSTREAM_REJECTED = "E603"
    INTERNAL_ERROR = "E699"


class CertificationError(Exception):
    """
    Structured certification error with code, message, and guidance.

    Attributes:
        code: Error code for programmatic handling
        message: Detailed error message for debugging
        guidance: Actionable guidance for resolution
        context: Additional context (request ID, correlation IDs, etc.)
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        guidance: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.guidance = guidance or "See documentation for error code details"
        self.context = context or {}

        super().__init__(self.format_message())

    def format_message(self) -> str:
        """Format error for display."""
        lines = [
            f"[{self.code.value}] {self.message}",
            f"",
            f"Guidance: {self.guidance}",
        ]

        if self.context:
            lines.append("")
            lines.append("Context:")
            for key, value in self.context.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_code": self.code.value,
            "error_name": self.code.name,
            "message": self.message,
            "guidance": self.guidance,
            "context": self.context,
        }


# Convenience functions for common errors

def prompt_too_short(length: int, min_length: int, request_id: Optional[str] = None) -> CertificationError:
    """Create error for prompt that's too short."""
    return CertificationError(
        code=ErrorCode.PROMPT_TOO_SHORT,
        message=f"Prompt too short: {length} characters (minimum: {min_length})",
        guidance="Provide a more detailed prompt with at least {min_length} characters",
        context={"prompt_length": length, "min_length": min_length, "request_id": request_id}
    )


def prompt_too_long(length: int, max_length: int, request_id: Optional[str] = None) -> CertificationError:
    """Create error for prompt that's too long."""
    return CertificationError(
        code=ErrorCode.PROMPT_TOO_LONG,
        message=f"Prompt too long: {length} characters (maximum: {max_length})",
        guidance=f"Truncate or summarize prompt to under {max_length} characters",
        context={"prompt_length": length, "max_length": max_length, "request_id": request_id}
    )


def rotor_timeout(timeout_seconds: float, request_id: Optional[str] = None) -> CertificationError:
    """Create error for rotor inference timeout."""
    return CertificationError(
        code=ErrorCode.ROTOR_TIMEOUT,
        message=f"Rotor inference exceeded {timeout_seconds} second timeout",
        guidance="Try reducing input size, using async mode, or increasing timeout threshold",
        context={"timeout_seconds": timeout_seconds, "request_id": request_id}
    )


def api_rate_limit(retry_after: Optional[int] = None, request_id: Optional[str] = None) -> CertificationError:
    """Create error for API rate limiting."""
    guidance = "Wait and retry with exponential backoff"
    if retry_after:
        guidance = f"Wait {retry_after} seconds before retrying"

    return CertificationError(
        code=ErrorCode.API_RATE_LIMIT,
        message="API rate limit exceeded",
        guidance=guidance,
        context={"retry_after": retry_after, "request_id": request_id}
    )


def gate_failed(
    gate_name: str,
    gate_number: int,
    value: float,
    threshold: float,
    request_id: Optional[str] = None
) -> CertificationError:
    """Create error for quality gate failure."""
    error_codes = {
        1: ErrorCode.GATE_INTEGRITY_FAILED,
        2: ErrorCode.GATE_NOISE_FAILED,
        3: ErrorCode.GATE_RELEVANCE_FAILED,
        4: ErrorCode.GATE_STABILITY_FAILED,
        5: ErrorCode.GATE_COMPATIBILITY_FAILED,
    }

    code = error_codes.get(gate_number, ErrorCode.INTERNAL_ERROR)

    return CertificationError(
        code=code,
        message=f"Quality gate {gate_number} ({gate_name}) failed: {value:.3f} (threshold: {threshold:.3f})",
        guidance=f"Improve {gate_name.lower()} by refining input or adjusting thresholds",
        context={
            "gate_number": gate_number,
            "gate_name": gate_name,
            "value": value,
            "threshold": threshold,
            "request_id": request_id
        }
    )


def network_partition(service: str, request_id: Optional[str] = None) -> CertificationError:
    """Create error for network partition."""
    return CertificationError(
        code=ErrorCode.NETWORK_PARTITION,
        message=f"Network partition detected to {service}",
        guidance="Check network connectivity and service health, then retry",
        context={"service": service, "request_id": request_id}
    )


def out_of_memory(batch_size: int, request_id: Optional[str] = None) -> CertificationError:
    """Create error for out of memory."""
    return CertificationError(
        code=ErrorCode.OUT_OF_MEMORY,
        message=f"Out of memory during batch processing (batch size: {batch_size})",
        guidance=f"Reduce batch size below {batch_size} or increase available memory",
        context={"batch_size": batch_size, "request_id": request_id}
    )
