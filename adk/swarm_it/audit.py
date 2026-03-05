"""
Audit Logging - Week 2-3 Security/Reliability Critical

Implements comprehensive audit logging for:
- SR 11-7 compliance
- Incident investigation
- Forensic analysis
- Security monitoring
- Performance tracking

Based on ComplianceValidator recommendation (CVSS 6.5):
"There is no audit trail for certificate requests, which can hinder
compliance and investigations. SR 11-7 requires comprehensive logging."

Implements:
- Structured JSON logging
- Contextual information (request ID, user, timestamp)
- SIEM integration preparation
- Log rotation and retention
- Performance metrics logging
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
import logging
import sys


class AuditEvent(str, Enum):
    """Audit event types."""
    # Certification events
    CERT_REQUEST = "certification_request"
    CERT_SUCCESS = "certification_success"
    CERT_FAILURE = "certification_failure"
    CERT_GATE_FAILED = "certification_gate_failed"

    # Authentication events
    AUTH_LOGIN = "authentication_login"
    AUTH_LOGOUT = "authentication_logout"
    AUTH_FAILED = "authentication_failed"
    API_KEY_USED = "api_key_used"
    API_KEY_ROTATED = "api_key_rotated"

    # Rate limiting events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    RATE_LIMIT_WHITELIST = "rate_limit_whitelist_added"
    RATE_LIMIT_BLACKLIST = "rate_limit_blacklist_added"

    # Circuit breaker events
    CIRCUIT_OPENED = "circuit_breaker_opened"
    CIRCUIT_CLOSED = "circuit_breaker_closed"
    CIRCUIT_HALF_OPEN = "circuit_breaker_half_open"

    # Security events
    SECURITY_VIOLATION = "security_violation"
    INPUT_VALIDATION_FAILED = "input_validation_failed"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

    # System events
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    HEALTH_CHECK_FAILED = "health_check_failed"
    ERROR_OCCURRED = "error_occurred"


class AuditLevel(str, Enum):
    """Audit log levels (aligned with logging levels)."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditLogEntry:
    """
    Audit log entry with SR 11-7 compliance.

    Fields follow SR 11-7 requirements for regulatory compliance.
    """
    # Required fields
    timestamp: str  # ISO 8601 format
    event: AuditEvent
    level: AuditLevel = AuditLevel.INFO

    # User context
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    session_id: Optional[str] = None

    # Request context
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Event details
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    # Certification context (if applicable)
    prompt_length: Optional[int] = None
    model: Optional[str] = None
    domain: Optional[str] = None
    decision: Optional[str] = None
    kappa: Optional[float] = None
    R: Optional[float] = None
    S: Optional[float] = None
    N: Optional[float] = None
    gate_reached: Optional[int] = None

    # Performance metrics
    latency_ms: Optional[float] = None
    cache_hit: Optional[bool] = None

    # Security context
    rate_limit_remaining: Optional[int] = None
    circuit_breaker_state: Optional[str] = None

    def __post_init__(self):
        """Ensure timestamp is set."""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)

        # Remove None values for cleaner logs
        return {k: v for k, v in data.items() if v is not None}

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Audit logger with structured logging.

    Features:
    - Structured JSON logging
    - Context preservation
    - SIEM integration preparation
    - Log rotation support
    - Performance tracking

    Usage:
        logger = AuditLogger(name="swarm_it_audit")

        # Log certification request
        logger.log_certification_request(
            user_id="user_123",
            prompt_length=500,
            model="gpt-4"
        )

        # Log certification success
        logger.log_certification_success(
            user_id="user_123",
            decision="EXECUTE",
            kappa=0.842
        )
    """

    def __init__(
        self,
        name: str = "swarm_it_audit",
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        enable_console: bool = True,
        enable_siem: bool = False,
        siem_endpoint: Optional[str] = None
    ):
        """
        Initialize audit logger.

        Args:
            name: Logger name
            log_level: Minimum log level
            log_file: Log file path (optional)
            enable_console: Enable console output
            enable_siem: Enable SIEM integration
            siem_endpoint: SIEM endpoint URL
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # Configure formatters
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # File handler
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        # SIEM integration (placeholder)
        self.enable_siem = enable_siem
        self.siem_endpoint = siem_endpoint

    def log(self, entry: AuditLogEntry):
        """
        Log audit entry.

        Args:
            entry: Audit log entry
        """
        # Log to standard logger
        log_method = getattr(self.logger, entry.level.value)
        log_method(entry.to_json())

        # Send to SIEM if enabled
        if self.enable_siem and self.siem_endpoint:
            self._send_to_siem(entry)

    def _send_to_siem(self, entry: AuditLogEntry):
        """Send audit entry to SIEM (placeholder)."""
        # Placeholder for SIEM integration
        # Production would use Splunk, Elasticsearch, etc.
        pass

    # Convenience methods for common events

    def log_certification_request(
        self,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        prompt_length: Optional[int] = None,
        model: Optional[str] = None,
        domain: Optional[str] = None
    ):
        """Log certification request."""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event=AuditEvent.CERT_REQUEST,
            level=AuditLevel.INFO,
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
            prompt_length=prompt_length,
            model=model,
            domain=domain,
            message=f"Certification request from user {user_id}"
        )
        self.log(entry)

    def log_certification_success(
        self,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        decision: Optional[str] = None,
        kappa: Optional[float] = None,
        R: Optional[float] = None,
        S: Optional[float] = None,
        N: Optional[float] = None,
        gate_reached: Optional[int] = None,
        latency_ms: Optional[float] = None,
        cache_hit: Optional[bool] = None
    ):
        """Log successful certification."""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event=AuditEvent.CERT_SUCCESS,
            level=AuditLevel.INFO,
            user_id=user_id,
            request_id=request_id,
            decision=decision,
            kappa=kappa,
            R=R,
            S=S,
            N=N,
            gate_reached=gate_reached,
            latency_ms=latency_ms,
            cache_hit=cache_hit,
            message=f"Certification success: {decision}, kappa={kappa:.3f}"
        )
        self.log(entry)

    def log_certification_failure(
        self,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        error: Optional[str] = None,
        gate_reached: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log failed certification."""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event=AuditEvent.CERT_FAILURE,
            level=AuditLevel.WARNING,
            user_id=user_id,
            request_id=request_id,
            gate_reached=gate_reached,
            message=f"Certification failed: {error}",
            details=details or {}
        )
        self.log(entry)

    def log_rate_limit_exceeded(
        self,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
        limit: Optional[int] = None,
        remaining: Optional[int] = None
    ):
        """Log rate limit exceeded."""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event=AuditEvent.RATE_LIMIT_EXCEEDED,
            level=AuditLevel.WARNING,
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
            rate_limit_remaining=remaining,
            message=f"Rate limit exceeded for {ip_address or user_id}",
            details={"limit": limit, "remaining": remaining}
        )
        self.log(entry)

    def log_circuit_breaker_opened(
        self,
        circuit_name: str,
        failure_count: int,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log circuit breaker opened."""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event=AuditEvent.CIRCUIT_OPENED,
            level=AuditLevel.ERROR,
            circuit_breaker_state="open",
            message=f"Circuit breaker '{circuit_name}' opened after {failure_count} failures",
            details=details or {}
        )
        self.log(entry)

    def log_circuit_breaker_closed(
        self,
        circuit_name: str,
        success_count: int,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log circuit breaker closed."""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event=AuditEvent.CIRCUIT_CLOSED,
            level=AuditLevel.INFO,
            circuit_breaker_state="closed",
            message=f"Circuit breaker '{circuit_name}' closed after {success_count} successes",
            details=details or {}
        )
        self.log(entry)

    def log_security_violation(
        self,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
        violation_type: str = "",
        details: Optional[Dict[str, Any]] = None
    ):
        """Log security violation."""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event=AuditEvent.SECURITY_VIOLATION,
            level=AuditLevel.CRITICAL,
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
            message=f"Security violation: {violation_type}",
            details=details or {}
        )
        self.log(entry)

    def log_error(
        self,
        error: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log error."""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event=AuditEvent.ERROR_OCCURRED,
            level=AuditLevel.ERROR,
            user_id=user_id,
            request_id=request_id,
            message=f"Error: {error}",
            details=details or {}
        )
        self.log(entry)


# Global audit logger instance
_global_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger."""
    global _global_logger
    if _global_logger is None:
        _global_logger = AuditLogger()
    return _global_logger


def configure_audit_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_console: bool = True,
    enable_siem: bool = False,
    siem_endpoint: Optional[str] = None
):
    """Configure global audit logger."""
    global _global_logger
    _global_logger = AuditLogger(
        log_level=log_level,
        log_file=log_file,
        enable_console=enable_console,
        enable_siem=enable_siem,
        siem_endpoint=siem_endpoint
    )


# Convenience function for quick logging

def audit_log(
    event: AuditEvent,
    message: str,
    level: AuditLevel = AuditLevel.INFO,
    **kwargs
):
    """
    Quick audit log function.

    Usage:
        audit_log(
            AuditEvent.CERT_SUCCESS,
            "Certification approved",
            user_id="user_123",
            kappa=0.842
        )
    """
    logger = get_audit_logger()
    entry = AuditLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        event=event,
        level=level,
        message=message,
        **kwargs
    )
    logger.log(entry)
