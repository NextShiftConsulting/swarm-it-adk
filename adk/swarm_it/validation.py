"""
Input Validation - Phase 1 Quick Win

Provides secure input validation using Pydantic to:
- Prevent injection attacks
- Validate data types and formats
- Provide clear validation errors
- Sanitize user input
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum


class CertificationDomain(str, Enum):
    """Supported certification domains."""
    RESEARCH = "research"
    MEDICAL = "medical"
    LEGAL = "legal"
    FINANCIAL = "financial"
    DEV = "dev"


class CertifyRequest(BaseModel):
    """
    Certification request with validation.

    Validates:
    - Prompt length (10-100,000 chars)
    - Model name format
    - Threshold ranges (0.0-1.0)
    - Domain values
    """

    prompt: str = Field(
        ...,
        min_length=10,
        max_length=100000,
        description="Text to certify (10-100k chars)"
    )

    model: Optional[str] = Field(
        None,
        regex=r"^[a-zA-Z0-9_-]+$",
        max_length=50,
        description="Model name (alphanumeric, hyphens, underscores only)"
    )

    domain: CertificationDomain = Field(
        CertificationDomain.RESEARCH,
        description="Certification domain for threshold selection"
    )

    # Quality thresholds (optional overrides)
    kappa: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Compatibility threshold (0.0-1.0)"
    )

    R: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Relevance threshold (0.0-1.0)"
    )

    S: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Stability threshold (0.0-1.0)"
    )

    N: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Noise threshold (0.0-1.0)"
    )

    # User context (for audit trail)
    user_id: Optional[str] = Field(
        None,
        max_length=100,
        description="User ID for audit trail"
    )

    org_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Organization ID for audit trail"
    )

    request_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Request ID for correlation"
    )

    # Advanced options
    max_retries: int = Field(
        2,
        ge=0,
        le=10,
        description="Maximum retry attempts (0-10)"
    )

    enable_autofix: bool = Field(
        True,
        description="Enable automatic prompt repair on REPAIR decision"
    )

    auto_export_evidence: bool = Field(
        True,
        description="Automatically export evidence file"
    )

    @validator('prompt')
    def validate_prompt_content(cls, v):
        """Validate prompt has meaningful content."""
        # Strip whitespace
        v = v.strip()

        if not v:
            raise ValueError("Prompt cannot be empty or whitespace only")

        # Check for minimum alphabetic content (prevent purely numeric/punctuation)
        alpha_chars = sum(1 for c in v if c.isalpha())
        if alpha_chars < 5:
            raise ValueError("Prompt must contain at least 5 alphabetic characters")

        return v

    @root_validator
    def validate_thresholds(cls, values):
        """Validate threshold combinations if provided."""
        R = values.get('R')
        S = values.get('S')
        N = values.get('N')

        # If all three provided, they should sum to ~1.0 (simplex constraint)
        if R is not None and S is not None and N is not None:
            total = R + S + N
            if not (0.95 <= total <= 1.05):
                raise ValueError(
                    f"R + S + N must sum to ~1.0 (got {total:.3f}). "
                    "Thresholds should satisfy simplex constraint."
                )

        return values

    class Config:
        """Pydantic config."""
        use_enum_values = True


class BatchCertifyRequest(BaseModel):
    """
    Batch certification request.

    Validates:
    - Batch size (1-100 requests)
    - Individual request validation
    """

    requests: List[CertifyRequest] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="Batch of certification requests (1-100)"
    )

    @validator('requests')
    def validate_batch_size(cls, v):
        """Validate batch doesn't exceed memory limits."""
        if len(v) > 100:
            raise ValueError("Batch size exceeds maximum of 100 requests")
        return v


class QualityThresholds(BaseModel):
    """
    Quality gate thresholds with validation.

    Ensures thresholds are valid and don't conflict.
    """

    kappa: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Compatibility threshold (min of R and S)"
    )

    R: float = Field(
        0.3,
        ge=0.0,
        le=1.0,
        description="Relevance threshold"
    )

    S: float = Field(
        0.4,
        ge=0.0,
        le=1.0,
        description="Stability threshold"
    )

    N: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Noise threshold (upper bound)"
    )

    @root_validator
    def validate_threshold_logic(cls, values):
        """Validate threshold logic is sensible."""
        kappa = values.get('kappa')
        R = values.get('R')
        S = values.get('S')

        # kappa should be <= min(R, S) since kappa = min(R, S) by definition
        if kappa is not None and R is not None and S is not None:
            expected_kappa = min(R, S)
            if kappa > expected_kappa:
                raise ValueError(
                    f"kappa threshold ({kappa}) cannot exceed min(R, S) = {expected_kappa:.3f}"
                )

        return values


class RotorConfig(BaseModel):
    """
    Rotor configuration with validation.

    Validates rotor model parameters.
    """

    model_path: str = Field(
        ...,
        max_length=500,
        description="Path to rotor model file"
    )

    embed_dim: int = Field(
        64,
        ge=8,
        le=2048,
        description="Embedding dimension (8-2048)"
    )

    device: str = Field(
        "cpu",
        regex=r"^(cpu|cuda|cuda:\d+)$",
        description="Device (cpu, cuda, cuda:0, etc.)"
    )

    timeout_seconds: float = Field(
        5.0,
        ge=0.1,
        le=60.0,
        description="Inference timeout in seconds (0.1-60)"
    )

    @validator('model_path')
    def validate_model_path(cls, v):
        """Validate model path format (security check)."""
        # Prevent path traversal attacks
        if '..' in v or v.startswith('/'):
            raise ValueError("Invalid model path (path traversal detected)")

        # Only allow .pt files
        if not v.endswith('.pt'):
            raise ValueError("Model path must end with .pt")

        return v


# Convenience validation functions

def validate_certify_request(data: Dict[str, Any]) -> CertifyRequest:
    """
    Validate certification request from raw dictionary.

    Raises:
        ValidationError: If validation fails
    """
    return CertifyRequest(**data)


def validate_batch_request(data: Dict[str, Any]) -> BatchCertifyRequest:
    """
    Validate batch certification request from raw dictionary.

    Raises:
        ValidationError: If validation fails
    """
    return BatchCertifyRequest(**data)


def validate_thresholds(data: Dict[str, float]) -> QualityThresholds:
    """
    Validate quality thresholds from raw dictionary.

    Raises:
        ValidationError: If validation fails
    """
    return QualityThresholds(**data)
