"""
Config bridge — converts ADK threshold dicts to controlplane GatekeeperConfig.

ADK models.py defines thresholds as flat dicts like:
    {"kappa": 0.7, "R": 0.3, "S": 0.4, "N": 0.5}

This bridge maps them to GatekeeperConfig which uses the canonical
gate parameters (N_thr, alpha_min, kappa_base, etc.).
"""

from __future__ import annotations

from typing import Any

from yrsn_controlplane import GatekeeperConfig, get_preset


def thresholds_to_config(thresholds: dict[str, Any]) -> GatekeeperConfig:
    """Convert ADK-style threshold dict to GatekeeperConfig.

    Args:
        thresholds: Dict with keys like 'kappa', 'R', 'S', 'N',
                    optionally 'kappa_H', 'kappa_L', 'kappa_interface'.

    Returns:
        GatekeeperConfig with mapped thresholds.
    """
    return GatekeeperConfig(
        N_thr=thresholds.get("N", 0.5),
        alpha_min=thresholds.get("R", 0.3),
        c_min=thresholds.get("S", 0.4),
        kappa_base=thresholds.get("kappa", 0.5),
        kappa_L_min=thresholds.get("kappa_L", 0.3),
    )


def model_id_to_config(model_id: str) -> GatekeeperConfig:
    """Map ADK model ID to controlplane preset.

    Args:
        model_id: One of 'universal64', 'strict', 'permissive',
                  'research', 'multimodal'.

    Returns:
        GatekeeperConfig from controlplane preset.
    """
    # ADK model IDs map directly to controlplane preset names
    preset_map = {
        "universal64": "universal",
        "strict": "strict",
        "permissive": "permissive",
        "research": "research",
        "multimodal": "multimodal",
    }
    preset_name = preset_map.get(model_id, "universal")
    return get_preset(preset_name)
