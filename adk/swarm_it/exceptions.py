"""
Swarm It Exceptions
"""

# Re-export CertificationError from errors module (canonical location)
from swarm_it.errors import CertificationError  # noqa: F401


class SwarmItError(Exception):
    """Base exception for Swarm It SDK."""

    pass


class GateBlockedError(SwarmItError):
    """Raised when execution is blocked by gate decision."""

    def __init__(self, certificate):
        self.certificate = certificate
        super().__init__(
            f"Execution blocked: {certificate.reason} "
            f"(decision={certificate.decision.value}, "
            f"R={certificate.R:.3f}, N={certificate.N:.3f}, "
            f"kappa={certificate.kappa:.3f})"
        )


class MissingContextError(SwarmItError):
    """Raised when certification context cannot be extracted from arguments.

    Fail-closed guard: if no context can be found, the function must not
    execute uncertified.  HTTP-layer callers should map this to 422.
    """

    def __init__(self, func_name: str):
        self.func_name = func_name
        super().__init__(
            f"Certification context required but not found in arguments to "
            f"'{func_name}'. Ensure the call includes a certifiable string "
            f"argument (prompt, context, query, message, or input)."
        )


class AuthenticationError(SwarmItError):
    """Raised when API key is invalid or missing."""

    pass


class ConfigurationError(SwarmItError):
    """Raised when SDK is misconfigured."""

    pass
