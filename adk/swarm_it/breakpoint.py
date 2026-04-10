"""
swarm_it/breakpoint.py — ADK client for the V1 Comparative Breakpoint Law

Thin HTTP wrapper. All computation lives in swarm-it-api.

Usage:
    from swarm_it import SwarmIt

    client = SwarmIt.from_env()

    # Option A: Profile-first (managed, no math required from client)
    result = client.breakpoint.route(
        profile_id="prof_jina_v4_prod_001",
        sigma=0.12,
    )

    # Option B: Direct metrics
    result = client.breakpoint.route_direct(
        T6_arm2=0.61,
        T6_arm3=0.67,
        T8_probe_64d=0.74,
        T8_sep_ratio=0.71,
        d_native=1024,
        sigma=0.12,
    )

    # Option C: From validate_embeddings.py JSON output
    import json
    with open("val_output.json") as f:
        val_json = json.load(f)

    result = client.breakpoint.route_from_validation(
        validation_json=val_json,
        d_native=1024,
        sigma=0.12,
    )

    print(result.predicted_route)   # "edge_mlp_v1"
    print(result.kappa_edge_pre)    # 0.81
    print(result.admissibility_status)  # "PASS_PROXY_THRESHOLD"
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional, Any

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response dataclass (mirrors BreakpointResponse from the API)
# ---------------------------------------------------------------------------

@dataclass
class BreakpointRouteResult:
    predicted_route: str
    decision_basis: str
    epsilon: float
    winning_proxy: str

    # Proxy scores (Stage A routing law outputs)
    kappa_tree_pre: float
    kappa_edge_pre: float
    delta: float
    arm3_lift: float
    compression_penalty_bits: float

    # sigma passed through for audit — kappa_req lives in enforcement pipeline
    sigma: float

    # Advisory metadata
    law_version: str
    advisory_only: bool
    canonical_certificate_material: bool
    warnings: list[str]

    # Raw response for advanced use
    raw: dict

    @classmethod
    def from_api_response(cls, data: dict) -> "BreakpointRouteResult":
        derived = data["derived"]
        routing = data["routing"]
        return cls(
            predicted_route=routing["predicted_route"],
            decision_basis=routing["decision_basis"],
            epsilon=routing["epsilon"],
            winning_proxy=routing["winning_proxy"],
            kappa_tree_pre=derived["kappa_tree_pre"],
            kappa_edge_pre=derived["kappa_edge_pre"],
            delta=derived["delta"],
            arm3_lift=derived["arm3_lift"],
            compression_penalty_bits=derived["compression_penalty_bits"],
            sigma=data["inputs"]["metrics"].get("sigma", 0.0),
            law_version=data["law_version"],
            advisory_only=data["advisory_only"],
            canonical_certificate_material=data["canonical_certificate_material"],
            warnings=data.get("warnings", []),
            raw=data,
        )

    def __repr__(self) -> str:
        return (
            f"BreakpointRouteResult("
            f"route={self.predicted_route!r}, "
            f"κ_edge={self.kappa_edge_pre:.3f}, "
            f"κ_tree={self.kappa_tree_pre:.3f}, "
            f"δ={self.delta:+.3f})"
        )


@dataclass
class SubstrateProfile:
    profile_id: str
    status: str
    substrate_name: Optional[str]
    d_native: int
    modality: Optional[str]
    metrics_available: bool
    raw: dict

    @classmethod
    def from_api_response(cls, data: dict) -> "SubstrateProfile":
        return cls(
            profile_id=data["profile_id"],
            status=data["status"],
            substrate_name=data.get("substrate_name"),
            d_native=data.get("d_native", 0),
            modality=data.get("modality"),
            metrics_available=data.get("derived_metrics_available", False),
            raw=data,
        )


# ---------------------------------------------------------------------------
# Breakpoint namespace
# ---------------------------------------------------------------------------

class BreakpointNamespace:
    """
    client.breakpoint.route(...)            — route via profile (Option A)
    client.breakpoint.route_direct(...)     — route via raw metrics (Option B)
    client.breakpoint.route_from_validation(...) — route via validate_embeddings JSON (Option C)
    """

    def __init__(self, http: httpx.Client, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    def route(
        self,
        profile_id: str,
        sigma: float = 0.0,
        coefficients: Optional[dict] = None,
        options: Optional[dict] = None,
    ) -> BreakpointRouteResult:
        """
        Route by profile ID (Option A — managed, recommended).
        The backend resolves the profile's stored metrics automatically.
        """
        payload: dict[str, Any] = {"profile_id": profile_id, "sigma": sigma}
        if coefficients:
            payload["coefficients"] = coefficients
        if options:
            payload["options"] = options

        resp = self._http.post(
            f"{self._base}/api/v1/route/breakpoint/v1/by-profile",
            json=payload,
        )
        resp.raise_for_status()
        return BreakpointRouteResult.from_api_response(resp.json())

    def route_direct(
        self,
        T6_arm2: float,
        T6_arm3: float,
        T8_probe_64d: float,
        T8_sep_ratio: float,
        d_native: int,
        sigma: float = 0.0,
        substrate_id: Optional[str] = None,
        substrate_name: Optional[str] = None,
        coefficients: Optional[dict] = None,
        options: Optional[dict] = None,
    ) -> BreakpointRouteResult:
        """
        Route by providing diagnostic metrics directly (Option B).
        For advanced clients who have computed their own T6/T8 values.
        """
        payload: dict[str, Any] = {
            "metrics": {
                "T6_arm2": T6_arm2,
                "T6_arm3": T6_arm3,
                "T8_probe_64d": T8_probe_64d,
                "T8_sep_ratio": T8_sep_ratio,
                "d_native": d_native,
                "sigma": sigma,
            }
        }
        if substrate_id or substrate_name:
            payload["substrate"] = {}
            if substrate_id:
                payload["substrate"]["substrate_id"] = substrate_id
            if substrate_name:
                payload["substrate"]["substrate_name"] = substrate_name
        if coefficients:
            payload["coefficients"] = coefficients
        if options:
            payload["options"] = options

        resp = self._http.post(
            f"{self._base}/api/v1/route/breakpoint/v1",
            json=payload,
        )
        resp.raise_for_status()
        return BreakpointRouteResult.from_api_response(resp.json())

    def route_from_validation(
        self,
        validation_json: dict,
        d_native: int,
        sigma: float = 0.0,
        substrate_id: Optional[str] = None,
        substrate_name: Optional[str] = None,
        coefficients: Optional[dict] = None,
        options: Optional[dict] = None,
    ) -> BreakpointRouteResult:
        """
        Route from a validate_embeddings.py JSON output (Option C).
        The backend extracts T6/T8 metrics automatically.
        """
        payload: dict[str, Any] = {
            "validation_json": validation_json,
            "d_native": d_native,
            "sigma": sigma,
        }
        if substrate_id or substrate_name:
            payload["substrate"] = {}
            if substrate_id:
                payload["substrate"]["substrate_id"] = substrate_id
            if substrate_name:
                payload["substrate"]["substrate_name"] = substrate_name
        if coefficients:
            payload["coefficients"] = coefficients
        if options:
            payload["options"] = options

        resp = self._http.post(
            f"{self._base}/api/v1/route/breakpoint/from-validation",
            json=payload,
        )
        resp.raise_for_status()
        return BreakpointRouteResult.from_api_response(resp.json())

    def default_coefficients(self) -> dict:
        """Return current default V1 law coefficients from the server."""
        resp = self._http.get(f"{self._base}/api/v1/route/breakpoint/v1/coefficients")
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Profiles namespace
# ---------------------------------------------------------------------------

class ProfilesNamespace:
    """
    client.profiles.create(...)             — register a new substrate profile
    client.profiles.get(profile_id)         — retrieve profile
    client.profiles.upload_eval_bundle(...) — attach validation JSON to profile
    """

    def __init__(self, http: httpx.Client, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    def create(
        self,
        model_name: str,
        d_native: int,
        modality: str = "text",
        family: str = "text",
        notes: Optional[str] = None,
    ) -> SubstrateProfile:
        """
        Register a new substrate profile. Returns a profile_id for use
        in client.breakpoint.route(profile_id=...).

        Metrics are not yet available until upload_eval_bundle() is called.
        """
        payload: dict[str, Any] = {
            "model_name": model_name,
            "d_native": d_native,
            "modality": modality,
            "family": family,
        }
        if notes:
            payload["notes"] = notes

        resp = self._http.post(
            f"{self._base}/api/v1/route/breakpoint/v1/profiles",
            json=payload,
        )
        resp.raise_for_status()
        return SubstrateProfile.from_api_response(resp.json())

    def get(self, profile_id: str) -> SubstrateProfile:
        """Retrieve a substrate profile by ID."""
        resp = self._http.get(
            f"{self._base}/api/v1/route/breakpoint/v1/profiles/{profile_id}",
        )
        resp.raise_for_status()
        return SubstrateProfile.from_api_response(resp.json())

    def upload_eval_bundle(
        self,
        profile_id: str,
        validation_json: dict,
        sigma: float = 0.0,
    ) -> SubstrateProfile:
        """
        Attach a validate_embeddings.py JSON output to an existing profile.
        The backend extracts T6/T8 metrics and marks the profile READY.

        Args:
            profile_id: Profile to attach to.
            validation_json: Full dict from validate_embeddings.py output.
            sigma: Optional turbulence value for Oobleck gate; use 0.0 until
                   production monitoring is available.
        """
        payload = {
            "validation_json": validation_json,
            "sigma": sigma,
        }
        resp = self._http.post(
            f"{self._base}/api/v1/route/breakpoint/v1/profiles/{profile_id}/eval-bundle",
            json=payload,
        )
        resp.raise_for_status()
        return SubstrateProfile.from_api_response(resp.json())
