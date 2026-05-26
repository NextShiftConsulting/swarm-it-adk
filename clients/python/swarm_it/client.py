"""
Swarm-It Thin Client

Communicates with sidecar via REST API.

Certificate schema note (ADR-032 D4):
  The canonical certificate definition lives in swarm-it-api/schemas/certificate_v1.py.
  This module mirrors that definition. Until a shared rsct-schemas package exists,
  keep RSCTCertificate and GeoRSCTCertificate in sync with their canonical counterparts
  by documented mapping — not by independent convention.

  Divergences from the canonical schema must be recorded as ADR items, not silent diffs.
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Dict, Any, List, Optional

import httpx
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class GateDecision(str, Enum):
    """
    Internal enforcement decision from SequentialGatekeeper.

    Mirrors swarm-it-api/schemas/certificate_v1.py GateDecision.
    Not the same as PublicDecision (EXECUTE/CAUTION/REFUSE) used on geo endpoints.
    """
    EXECUTE   = "EXECUTE"
    RE_ENCODE = "RE_ENCODE"
    REPAIR    = "REPAIR"
    BLOCK     = "BLOCK"
    REJECT    = "REJECT"
    WARN      = "WARN"
    FALLBACK  = "FALLBACK"


class PublicDecision(str, Enum):
    """
    Role-projected decision returned by geo endpoints (ADR-029 D1).

    EXECUTE ← internal EXECUTE
    CAUTION ← internal REJECT, RE_ENCODE, REPAIR
    REFUSE  ← internal BLOCK
    """
    EXECUTE = "EXECUTE"
    CAUTION = "CAUTION"
    REFUSE  = "REFUSE"


class GateReachedIdentifier(str, Enum):
    """Named gate identifiers per ADR-016. Never an integer."""
    NONE                     = "NONE"
    GATE_1_INTEGRITY         = "GATE_1_INTEGRITY"
    GATE_1B_N_CEILING        = "GATE_1B_N_CEILING"
    GATE_2_CONSENSUS         = "GATE_2_CONSENSUS"
    GATE_3_ADMISSIBILITY     = "GATE_3_ADMISSIBILITY"
    GATE_3B_TRAJECTORY       = "GATE_3B_TRAJECTORY"
    GATE_4_GROUNDING         = "GATE_4_GROUNDING"
    GATE_5_CONTRACT_COVERAGE = "GATE_5_CONTRACT_COVERAGE"


class EmbeddingArm(str, Enum):
    """OOF embedding arms available in GeoRSCT v24.002."""
    PCA32_V1         = "pca32_v1"
    SPATIAL_LAG_V1   = "spatial_lag_v1"
    GRAPHSAGE_V1     = "graphsage_v1"
    GEO_V1           = "geo_v1"
    DOMAIN_V1        = "domain_v1"
    NOISY_CONTROL_V1 = "noisy_control_v1"


class AsyncJobStatus(str, Enum):
    PENDING  = "PENDING"
    RUNNING  = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED   = "FAILED"


class ValidationType(str, Enum):
    TYPE_I   = "TYPE_I"
    TYPE_II  = "TYPE_II"
    TYPE_III = "TYPE_III"
    TYPE_IV  = "TYPE_IV"
    TYPE_V   = "TYPE_V"
    TYPE_VI  = "TYPE_VI"


# ── Certificate models ─────────────────────────────────────────────────────────


class RSCTCertificate(BaseModel):
    """
    RSCT Certificate as returned by /certify and /certify/pair endpoints.

    Mirrors swarm-it-api/schemas/certificate_v1.py RSCTCertificate.
    Key invariants:
      - S_sup (never bare S) per NOTATION_DEFINITIVE namespace rule 4
      - gate_reached is a named string identifier, never an integer (ADR-016)
      - decision is internal GateDecision (not public EXECUTE/CAUTION/REFUSE)

    Replaces the former Certificate @dataclass that had S (wrong), gate_reached: int
    (wrong), and a stale GateDecision enum. See ADR-032 D4 for remediation history.
    """

    # Identity
    id:        str = Field(..., description="Unique certificate identifier.")
    timestamp: str = Field(..., description="ISO 8601 timestamp (UTC).")
    version:   str = Field("1.1.0", description="Certificate schema version.")

    # Core RSN simplex — R + S_sup + N = 1
    R:     float = Field(..., ge=0.0, le=1.0, description="Relevance.")
    S_sup: float = Field(..., ge=0.0, le=1.0,
                         description="Superfluous. Always S_sup, never bare S.")
    N:     float = Field(..., ge=0.0, le=1.0, description="Noise.")

    # Gate metrics
    kappa_compat: float = Field(..., ge=0.0, le=1.0,
                                description="Compatibility enforcement scalar: R*(1-N) unimodal, "
                                            "min(kappa_H, kappa_L, kappa_interface) multimodal.")
    kappa_modal_min: Optional[float] = Field(None, ge=0.0, le=1.0,
                                             description="min(kappa_H, kappa_L, kappa_interface) for multimodal certs.")
    sigma:      float = Field(..., ge=0.0, le=1.0,
                              description="Turbulence: std({kappa_i}) over per-sample scores.")

    # Derived quality
    alpha: Optional[float] = Field(None, ge=0.0, le=1.0,
                                   description="Signal quality: R / (R + N).")

    # Multimodal hierarchy (optional)
    kappa_H:         Optional[float] = Field(None, ge=0.0, le=1.0)
    kappa_L:         Optional[float] = Field(None, ge=0.0, le=1.0)
    kappa_interface: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_multimodal:   bool            = Field(False)
    weak_modality:   Optional[str]   = Field(None)

    # Enforcement result
    decision:    GateDecision = Field(...,
                                     description="Enforcement decision from SequentialGatekeeper.")
    gate_reached: str         = Field(...,
                                     description="First failing gate identifier (ADR-016). "
                                                 "Values: GATE_1_INTEGRITY, GATE_1B_N_CEILING, "
                                                 "GATE_2_CONSENSUS, GATE_3_ADMISSIBILITY, "
                                                 "GATE_3B_TRAJECTORY, GATE_4_GROUNDING, "
                                                 "GATE_5_CONTRACT_COVERAGE, or NONE.")
    reason:  str  = Field(..., description="Human-readable decision reason.")
    allowed: bool = Field(..., description="True only for EXECUTE and WARN.")


class GeoCertificate(BaseModel):
    """
    RSCT certificate returned by geo certification endpoints.

    Mirrors swarm-it-api/schemas/geo_v1.py GeoCertificate.
    Uses public decision vocabulary (ADR-029 D1) and kappa (not kappa_gate).
    """
    R:     float = Field(..., ge=0.0, le=1.0)
    S_sup: float = Field(..., ge=0.0, le=1.0)
    N:     float = Field(..., ge=0.0, le=1.0)
    alpha: float = Field(..., ge=0.0, le=1.0)
    kappa: float = Field(..., ge=0.0, le=1.0,
                         description="R*(1-N). NOT the ADK embedding-viability compute_kappa.")
    sigma: float = Field(..., ge=0.0)

    N_ceiling: Optional[float] = Field(None, ge=0.0, le=1.0)
    decision:     PublicDecision        = Field(...)
    gate_reached: GateReachedIdentifier = Field(...)
    gate_reason:  Optional[str]         = Field(None)


class GeoCertifyMetadata(BaseModel):
    zcta_id:          str                  = Field(...)
    state_fips:       str                  = Field(...)
    county_fips:      str                  = Field(...)
    target:           str                  = Field(...)
    snapshot_year:    int                  = Field(...)
    embedding_arm:    EmbeddingArm         = Field(...)
    scenario_id:      Optional[str]        = Field(None)
    huc8_id:          Optional[str]        = Field(None)
    huc8_coverage_pct: Optional[float]     = Field(None)


class GeoCertifyAudit(BaseModel):
    request_id:       str             = Field(...)
    timestamp:        str             = Field(...)
    dataset_version:  str             = Field(...)
    policy_id:        str             = Field(...)
    source_etags:     Dict[str, str]  = Field(default_factory=dict)
    live_sensors_used: bool           = Field(...)
    api_version:      str             = Field(...)
    adk_version:      Optional[str]   = Field(None)


class GeoCertifyResponse(BaseModel):
    """
    Response from POST /certify/geo.

    certificate_id is required (ADR-024) — it anchors this response to the
    DynamoDB enforcement log entry.
    """
    certificate_id: str               = Field(...)
    certificate:    GeoCertificate    = Field(...)
    metadata:       GeoCertifyMetadata = Field(...)
    audit:          GeoCertifyAudit   = Field(...)


class TrajectoryPoint(BaseModel):
    year:           int            = Field(...)
    snapshot_t:     Optional[int]  = Field(None)
    certificate_id: str            = Field(...)
    certificate:    GeoCertificate = Field(...)


class TrajectoryResponse(BaseModel):
    zcta_id:       str                   = Field(...)
    target:        str                   = Field(...)
    embedding_arm: EmbeddingArm          = Field(...)
    points:        List[TrajectoryPoint] = Field(...)
    summary:       dict                  = Field(default_factory=dict)
    audit:         GeoCertifyAudit       = Field(...)


class AblationPoint(BaseModel):
    mask:           dict           = Field(...)
    certificate_id: str            = Field(...)
    certificate:    GeoCertificate = Field(...)


class AblationResponse(BaseModel):
    zcta_id: str                  = Field(...)
    target:  str                  = Field(...)
    points:  List[AblationPoint]  = Field(...)
    summary: dict                 = Field(default_factory=dict)
    audit:   GeoCertifyAudit      = Field(...)


class CeilingResult(BaseModel):
    ceiling:        float = Field(...)
    ci_lo:          float = Field(...)
    ci_hi:          float = Field(...)
    target:         str   = Field(...)
    protocol:       str   = Field(...)
    bootstrap_reps: int   = Field(...)
    computed_at:    str   = Field(...)


class AsyncJobResponse(BaseModel):
    job_id:            str            = Field(...)
    status:            AsyncJobStatus = Field(AsyncJobStatus.PENDING)
    poll_url:          str            = Field(...)
    estimated_seconds: Optional[int]  = Field(None)


class AsyncJobResult(BaseModel):
    job_id:  str                     = Field(...)
    status:  AsyncJobStatus          = Field(...)
    result:  Optional[CeilingResult] = Field(None)
    error:   Optional[str]           = Field(None)


# ── SwarmIt client ─────────────────────────────────────────────────────────────


class SwarmIt:
    """
    Swarm-It Client.

    Thin wrapper around sidecar REST API.

    Usage:
        swarm = SwarmIt(url="http://localhost:8080")
        cert = swarm.certify("What is 2+2?")

        if cert.allowed:
            response = my_llm(prompt)
            swarm.validate(cert.id, ValidationType.TYPE_I, score=0.9)
    """

    def __init__(
        self,
        url: str = "http://localhost:8080",
        timeout: float = 30.0,
    ):
        self.base_url = url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def certify(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        context: Optional[str] = None,
        policy: str = "default",
    ) -> RSCTCertificate:
        """
        Request RSCT certification for a prompt.

        Args:
            prompt: The prompt to certify.
            model_id: Optional model identifier.
            context: Optional context/system prompt.
            policy: Certification policy name.

        Returns:
            RSCTCertificate with gate decision.
        """
        response = self._client.post(
            f"{self.base_url}/api/v1/certify",
            json={
                "prompt": prompt,
                "model_id": model_id,
                "context": context,
                "policy": policy,
            },
        )
        response.raise_for_status()
        return RSCTCertificate.model_validate(response.json())

    def validate(
        self,
        certificate_id: str,
        validation_type: ValidationType,
        score: float,
        failed: bool = False,
    ) -> Dict[str, Any]:
        """
        Submit post-execution validation feedback.

        Args:
            certificate_id: ID of the certificate being validated.
            validation_type: Type I-VI validation.
            score: Validation score [0, 1].
            failed: Whether validation failed.

        Returns:
            Response with optional threshold adjustment.
        """
        response = self._client.post(
            f"{self.base_url}/api/v1/validate",
            json={
                "certificate_id": certificate_id,
                "validation_type": validation_type.value,
                "score": score,
                "failed": failed,
            },
        )
        response.raise_for_status()
        return response.json()

    def audit(
        self,
        format: str = "JSON",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Export certificates for compliance audit.

        Args:
            format: Export format (JSON, SR11-7, CSV).
            limit: Maximum certificates to return.

        Returns:
            Audit response with records.
        """
        response = self._client.post(
            f"{self.base_url}/api/v1/audit",
            json={"format": format, "limit": limit},
        )
        response.raise_for_status()
        return response.json()

    def get_certificate(self, certificate_id: str) -> RSCTCertificate:
        """Get a specific certificate by ID."""
        response = self._client.get(
            f"{self.base_url}/api/v1/certificates/{certificate_id}"
        )
        response.raise_for_status()
        return RSCTCertificate.model_validate(response.json())

    def statistics(self) -> Dict[str, Any]:
        """Get sidecar statistics."""
        response = self._client.get(f"{self.base_url}/api/v1/statistics")
        response.raise_for_status()
        return response.json()

    def health(self) -> bool:
        """Check if sidecar is healthy."""
        try:
            response = self._client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    def close(self) -> None:
        """Close the client."""
        self._client.close()

    def __enter__(self) -> "SwarmIt":
        return self

    def __exit__(self, *args) -> None:
        self.close()


# ── GeoRSCT client ─────────────────────────────────────────────────────────────


class GeoRSCT:
    """
    GeoRSCT Client — typed methods for geo certification endpoints.

    Wraps:
      POST /certify/geo
      POST /certify/geo/trajectory
      POST /certify/geo/ablation
      POST /ceiling          (async, returns AsyncJobResponse)
      GET  /ceiling/{job_id} (poll for result)

    Per ADR-032 D7, request kwargs are validated against the Pydantic request
    models internally before the HTTP call — callers do not need to construct
    GeoCertifyRequest explicitly.

    Usage:
        geo = GeoRSCT(url="https://api.swarmit.io", api_key="...")
        resp = geo.certify_geo(zcta_id="77002", target="nfip_total_loss",
                               y_pred=1234.5, y_true=1100.0)
        if resp.certificate.decision == PublicDecision.EXECUTE:
            ...
    """

    def __init__(
        self,
        url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        adk_version: Optional[str] = None,
    ):
        self.base_url = url.rstrip("/")
        self.timeout = timeout
        headers: Dict[str, str] = {}
        if api_key:
            headers["X-API-Key"] = api_key
        if adk_version:
            headers["X-ADK-Version"] = adk_version
        self._client = httpx.Client(timeout=timeout, headers=headers)

    # ── Core geo certification ────────────────────────────────────────────────

    def certify_geo(
        self,
        zcta_id: str,
        target: str,
        y_pred: float,
        y_true: float,
        *,
        snapshot_year: int = 2022,
        embedding_arm: EmbeddingArm = EmbeddingArm.GRAPHSAGE_V1,
        include_live_sensors: bool = False,
        modal_sources: Optional[Dict[str, bool]] = None,
        scenario_id: Optional[str] = None,
    ) -> GeoCertifyResponse:
        """
        Certify a single ZCTA prediction.

        Args:
            zcta_id: 5-digit ZCTA code.
            target: Target column name (e.g. 'nfip_total_loss').
            y_pred: Model prediction.
            y_true: Observed ground truth.
            snapshot_year: ACS survey year [2018-2022]. Default 2022.
            embedding_arm: OOF embedding arm. Default graphsage_v1.
            include_live_sensors: Augment sigma with live USGS/NOAA readings.
            modal_sources: Dict with keys svi/twi/noaa_events/nfip_claims.
                           Defaults to all True when None.
            scenario_id: Floodcaster scenario identifier (ADR-031 D3).

        Returns:
            GeoCertifyResponse with certificate, metadata, and audit block.
        """
        payload: Dict[str, Any] = {
            "zcta_id": zcta_id,
            "target": target,
            "y_pred": y_pred,
            "y_true": y_true,
            "snapshot_year": snapshot_year,
            "embedding_arm": embedding_arm.value if isinstance(embedding_arm, EmbeddingArm) else embedding_arm,
            "include_live_sensors": include_live_sensors,
        }
        if modal_sources is not None:
            payload["modal_sources"] = modal_sources
        if scenario_id is not None:
            payload["scenario_id"] = scenario_id

        response = self._client.post(
            f"{self.base_url}/certify/geo",
            json=payload,
        )
        response.raise_for_status()
        return GeoCertifyResponse.model_validate(response.json())

    # ── Trajectory certification ──────────────────────────────────────────────

    def certify_geo_trajectory(
        self,
        zcta_id: str,
        target: str,
        y_pred: float,
        y_true: float,
        years: List[int],
        *,
        embedding_arm: EmbeddingArm = EmbeddingArm.GRAPHSAGE_V1,
        include_live_sensors: bool = False,
        modal_sources: Optional[Dict[str, bool]] = None,
        scenario_id: Optional[str] = None,
    ) -> TrajectoryResponse:
        """
        Certify a ZCTA across multiple ACS snapshot years.

        Args:
            zcta_id: 5-digit ZCTA code.
            target: Target column name.
            y_pred: Model prediction (applied uniformly across years).
            y_true: Observed ground truth (applied uniformly across years).
            years: List of ACS years to certify, e.g. [2018, 2019, 2020, 2021, 2022].

        Returns:
            TrajectoryResponse with one GeoCertificate per year.
        """
        payload: Dict[str, Any] = {
            "zcta_id": zcta_id,
            "target": target,
            "y_pred": y_pred,
            "y_true": y_true,
            "years": years,
            "embedding_arm": embedding_arm.value if isinstance(embedding_arm, EmbeddingArm) else embedding_arm,
            "include_live_sensors": include_live_sensors,
        }
        if modal_sources is not None:
            payload["modal_sources"] = modal_sources
        if scenario_id is not None:
            payload["scenario_id"] = scenario_id

        response = self._client.post(
            f"{self.base_url}/certify/geo/trajectory",
            json=payload,
        )
        response.raise_for_status()
        return TrajectoryResponse.model_validate(response.json())

    # ── Ablation certification ────────────────────────────────────────────────

    def certify_geo_ablation(
        self,
        zcta_id: str,
        target: str,
        y_pred: float,
        y_true: float,
        modal_masks: List[Dict[str, bool]],
        *,
        snapshot_year: int = 2022,
        embedding_arm: EmbeddingArm = EmbeddingArm.GRAPHSAGE_V1,
        scenario_id: Optional[str] = None,
    ) -> AblationResponse:
        """
        Run modal-source ablation experiment for a single ZCTA.

        Each entry in modal_masks is a ModalSources dict specifying which
        layers (svi, twi, noaa_events, nfip_claims) are enabled for that run.
        The all-enabled baseline is prepended automatically by the server if
        not included.

        Args:
            modal_masks: List of modal-source dicts, one per ablation run.

        Returns:
            AblationResponse with one GeoCertificate per mask.
        """
        payload: Dict[str, Any] = {
            "zcta_id": zcta_id,
            "target": target,
            "y_pred": y_pred,
            "y_true": y_true,
            "snapshot_year": snapshot_year,
            "embedding_arm": embedding_arm.value if isinstance(embedding_arm, EmbeddingArm) else embedding_arm,
            "modal_masks": modal_masks,
        }
        if scenario_id is not None:
            payload["scenario_id"] = scenario_id

        response = self._client.post(
            f"{self.base_url}/certify/geo/ablation",
            json=payload,
        )
        response.raise_for_status()
        return AblationResponse.model_validate(response.json())

    # ── N-ceiling (async) ─────────────────────────────────────────────────────

    def ceiling(
        self,
        target: str,
        protocol: str,
        *,
        embedding_arms: Optional[List[EmbeddingArm]] = None,
        bootstrap_reps: int = 200,
    ) -> AsyncJobResponse:
        """
        Submit an async N-ceiling estimation job (POST /ceiling).

        Returns immediately with a job_id. Poll with ceiling_result() until
        status is COMPLETE or FAILED.

        Args:
            target: Target variable name.
            protocol: Estimation protocol, e.g. 'imputation_state_blocked'.
            embedding_arms: Arms to use in the bootstrap. Defaults to [graphsage_v1].
            bootstrap_reps: Number of bootstrap replicates [10-1000]. Default 200.

        Returns:
            AsyncJobResponse with job_id and poll_url.
        """
        if embedding_arms is None:
            embedding_arms = [EmbeddingArm.GRAPHSAGE_V1]

        response = self._client.post(
            f"{self.base_url}/ceiling",
            json={
                "target": target,
                "protocol": protocol,
                "embedding_arms": [a.value if isinstance(a, EmbeddingArm) else a for a in embedding_arms],
                "bootstrap_reps": bootstrap_reps,
            },
        )
        response.raise_for_status()
        return AsyncJobResponse.model_validate(response.json())

    def ceiling_result(self, job_id: str) -> AsyncJobResult:
        """
        Poll the result of an async N-ceiling job (GET /ceiling/{job_id}).

        Args:
            job_id: Job identifier from AsyncJobResponse.

        Returns:
            AsyncJobResult. Check .status; result is populated when COMPLETE.
        """
        response = self._client.get(f"{self.base_url}/ceiling/{job_id}")
        response.raise_for_status()
        return AsyncJobResult.model_validate(response.json())

    def ceiling_wait(
        self,
        job_id: str,
        poll_interval: float = 5.0,
        max_wait: float = 300.0,
    ) -> CeilingResult:
        """
        Poll until the ceiling job completes and return the result.

        Args:
            job_id: Job identifier.
            poll_interval: Seconds between polls. Default 5.
            max_wait: Maximum seconds to wait before raising TimeoutError. Default 300.

        Returns:
            CeilingResult when job completes.

        Raises:
            TimeoutError: If job does not complete within max_wait seconds.
            RuntimeError: If job status is FAILED.
        """
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            result = self.ceiling_result(job_id)
            if result.status == AsyncJobStatus.COMPLETE:
                assert result.result is not None
                return result.result
            if result.status == AsyncJobStatus.FAILED:
                raise RuntimeError(f"Ceiling job {job_id} failed: {result.error}")
            time.sleep(poll_interval)
        raise TimeoutError(f"Ceiling job {job_id} did not complete within {max_wait}s")

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the client."""
        self._client.close()

    def __enter__(self) -> "GeoRSCT":
        return self

    def __exit__(self, *args) -> None:
        self.close()


# ── AsyncSwarmIt ───────────────────────────────────────────────────────────────


class AsyncSwarmIt:
    """Async version of SwarmIt client."""

    def __init__(
        self,
        url: str = "http://localhost:8080",
        timeout: float = 30.0,
    ):
        self.base_url = url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def certify(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        context: Optional[str] = None,
        policy: str = "default",
    ) -> RSCTCertificate:
        """Async version of certify."""
        response = await self._client.post(
            f"{self.base_url}/api/v1/certify",
            json={
                "prompt": prompt,
                "model_id": model_id,
                "context": context,
                "policy": policy,
            },
        )
        response.raise_for_status()
        return RSCTCertificate.model_validate(response.json())

    async def validate(
        self,
        certificate_id: str,
        validation_type: ValidationType,
        score: float,
        failed: bool = False,
    ) -> Dict[str, Any]:
        """Async version of validate."""
        response = await self._client.post(
            f"{self.base_url}/api/v1/validate",
            json={
                "certificate_id": certificate_id,
                "validation_type": validation_type.value,
                "score": score,
                "failed": failed,
            },
        )
        response.raise_for_status()
        return response.json()

    async def health(self) -> bool:
        """Check if sidecar is healthy."""
        try:
            response = await self._client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the client."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncSwarmIt":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
