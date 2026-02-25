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
from api.metrics import (
    record_certification,
    record_validation,
    record_audit,
    update_store_gauge,
    update_thresholds,
    update_failure_rates,
    CERTIFICATION_LATENCY,
    VALIDATION_LATENCY,
)

router = APIRouter()

# Initialize engine and store
# Engine uses mock adapter by default (set USE_YRSN=1 for real yrsn)
import os
engine = RSCTEngine(
    use_mock=os.environ.get("USE_YRSN", "0") != "1",
    embed_model=os.environ.get("EMBED_MODEL", "text-embedding-3-small"),
    rotor_checkpoint=os.environ.get("ROTOR_CHECKPOINT"),
)
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
    embeddings: Optional[List[float]] = None  # User-provided embeddings (optional)
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
    gate_reached: int = Field(ge=0, le=5)  # 0 = pre-screen rejection
    reason: str
    allowed: bool

    # Multimodal hierarchy (optional)
    kappa_H: Optional[float] = None
    kappa_L: Optional[float] = None
    kappa_interface: Optional[float] = None

    # Diagnostics
    weak_modality: Optional[str] = None
    is_multimodal: bool = False

    # Sidecar annotations
    pattern_flags: List[str] = []
    pre_screen_rejection: bool = False


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
    import time
    start = time.perf_counter()

    cert = engine.certify(
        prompt=request.prompt,
        embeddings=request.embeddings,
        model_id=request.model_id,
        context=request.context,
        policy=request.policy,
    )

    # Store certificate
    store.store(cert)

    # Record metrics
    if CERTIFICATION_LATENCY:
        CERTIFICATION_LATENCY.observe(time.perf_counter() - start)
    record_certification(cert)
    update_store_gauge(store.count())

    return cert


@router.post("/validate", response_model=ValidateResponse)
async def validate(request: ValidateRequest) -> ValidateResponse:
    """
    SGCI Method 2: Validate (post-execution feedback)

    Records Type I-VI validation results for feedback loop.
    May trigger threshold adjustments.
    """
    import time
    start = time.perf_counter()

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

    # Record metrics
    if VALIDATION_LATENCY:
        VALIDATION_LATENCY.observe(time.perf_counter() - start)
    record_validation(request.validation_type.value, request.failed)
    update_failure_rates(engine.get_failure_rates())

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

    # Record metrics
    record_audit(request.format)

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
async def update_thresholds_endpoint(thresholds: Dict[str, float]) -> Dict[str, Any]:
    """Update certification thresholds."""
    for key, value in thresholds.items():
        engine.set_threshold(key, value)
    return {"updated": True, "thresholds": engine.get_thresholds()}


@router.get("/health")
async def health() -> Dict[str, Any]:
    """
    Health check endpoint.

    Shows sidecar status and yrsn adapter health.
    """
    return engine.health()
