"""
Swarm It Exceptions
"""


class SwarmItError(Exception):
    """Base exception for Swarm It SDK."""

    pass


class CertificationError(SwarmItError):
    """Raised when certification request fails."""

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


class AuthenticationError(SwarmItError):
    """Raised when API key is invalid or missing."""

    pass


class ConfigurationError(SwarmItError):
    """Raised when SDK is misconfigured."""

    pass
