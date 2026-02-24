"""
SGCI REST API - Swarm Gate Certification Interface

Three core methods (Tendermint ABCI-inspired):
1. Certify - pre-execution gate check
2. Validate - post-execution feedback
3. Audit - compliance export
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from engine.rsct import RSCTEngine
from store.certificates import CertificateStore

router = APIRouter()

# Initialize engine and store
engine = RSCTEngine()
store = CertificateStore()


# === Request/Response Models ===

class GateDecision(str, Enum):
    EXECUTE = "EXECUTE"
    REPAIR = "REPAIR"
    DELEGATE = "DELEGATE"
    BLOCK = "BLOCK"
    REJECT = "REJECT"


class CertifyRequest(BaseModel):
    """Pre-execution certification request."""
    prompt: str
    model_id: Optional[str] = None
    context: Optional[str] = None
    swarm_id: Optional[str] = None
    policy: Optional[str] = "default"


class Certificate(BaseModel):
    """RSCT Certificate."""
    id: str
    timestamp: str
    R: float = Field(ge=0, le=1)
    S: float = Field(ge=0, le=1)
    N: float = Field(ge=0, le=1)
    kappa_gate: float = Field(ge=0, le=1)
    sigma: float = Field(ge=0, le=1)
    decision: GateDecision
    gate_reached: int = Field(ge=1, le=5)
    reason: str
    allowed: bool

    # Multimodal hierarchy (optional)
    kappa_H: Optional[float] = None
    kappa_L: Optional[float] = None
    kappa_interface: Optional[float] = None

    # Diagnostics
    weak_modality: Optional[str] = None
    is_multimodal: bool = False


class ValidationType(str, Enum):
    TYPE_I = "TYPE_I"      # Groundedness
    TYPE_II = "TYPE_II"    # Contradiction
    TYPE_III = "TYPE_III"  # Inversion
    TYPE_IV = "TYPE_IV"    # Drift
    TYPE_V = "TYPE_V"      # Reasoning
    TYPE_VI = "TYPE_VI"    # Domain


class ValidateRequest(BaseModel):
    """Post-execution validation feedback."""
    certificate_id: str
    validation_type: ValidationType
    score: float = Field(ge=0, le=1)
    failed: bool


class ValidateResponse(BaseModel):
    """Validation response."""
    recorded: bool
    adjustment: Optional[Dict[str, Any]] = None


class AuditRequest(BaseModel):
    """Audit export request."""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    format: str = "JSON"  # JSON, SR11-7, CSV
    limit: int = 100


class AuditResponse(BaseModel):
    """Audit response."""
    certificate_count: int
    format: str
    records: List[Dict[str, Any]]


# === SGCI Endpoints ===

@router.post("/certify", response_model=Certificate)
async def certify(request: CertifyRequest) -> Certificate:
    """
    SGCI Method 1: Certify (pre-execution)

    Evaluates prompt/context and returns RSCT certificate
    with gate decision (EXECUTE, REPAIR, DELEGATE, BLOCK, REJECT).
    """
    cert = engine.certify(
        prompt=request.prompt,
        model_id=request.model_id,
        context=request.context,
        policy=request.policy,
    )

    # Store certificate
    store.store(cert)

    return cert


@router.post("/validate", response_model=ValidateResponse)
async def validate(request: ValidateRequest) -> ValidateResponse:
    """
    SGCI Method 2: Validate (post-execution feedback)

    Records Type I-VI validation results for feedback loop.
    May trigger threshold adjustments.
    """
    # Verify certificate exists
    cert = store.get(request.certificate_id)
    if cert is None:
        raise HTTPException(status_code=404, detail="Certificate not found")

    # Record validation
    adjustment = engine.record_validation(
        certificate_id=request.certificate_id,
        validation_type=request.validation_type.value,
        score=request.score,
        failed=request.failed,
    )

    return ValidateResponse(
        recorded=True,
        adjustment=adjustment,
    )


@router.post("/audit", response_model=AuditResponse)
async def audit(request: AuditRequest) -> AuditResponse:
    """
    SGCI Method 3: Audit (compliance export)

    Exports certificates for compliance review.
    Supports SR 11-7, JSON, CSV formats.
    """
    certs = store.list(limit=request.limit)

    if request.format == "SR11-7":
        records = [engine.format_sr117(c) for c in certs]
    else:
        records = [c.dict() if hasattr(c, 'dict') else c for c in certs]

    return AuditResponse(
        certificate_count=len(records),
        format=request.format,
        records=records,
    )


# === Convenience Endpoints ===

@router.get("/certificates/{certificate_id}", response_model=Certificate)
async def get_certificate(certificate_id: str) -> Certificate:
    """Get a specific certificate by ID."""
    cert = store.get(certificate_id)
    if cert is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return cert


@router.get("/statistics")
async def get_statistics() -> Dict[str, Any]:
    """Get sidecar statistics."""
    return {
        "total_certificates": store.count(),
        "thresholds": engine.get_thresholds(),
        "failure_rates": engine.get_failure_rates(),
    }


@router.post("/thresholds")
async def update_thresholds(thresholds: Dict[str, float]) -> Dict[str, Any]:
    """Update certification thresholds."""
    for key, value in thresholds.items():
        engine.set_threshold(key, value)
    return {"updated": True, "thresholds": engine.get_thresholds()}
