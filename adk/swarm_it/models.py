"""
Runtime Model Selection - Copilot SDK Pattern
Dynamic certification model discovery and configuration.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional


@dataclass
class CertificationModel:
    """Available certification model configuration."""
    id: str
    name: str
    description: str
    rotor_checkpoint: Optional[str]
    thresholds: Dict[str, float]
    cost_per_cert: float  # USD
    tags: List[str]


# Registry of available certification models
CERTIFICATION_MODELS = [
    CertificationModel(
        id="universal64",
        name="Universal Rotor (64-dim)",
        description="Multi-architecture rotor for general use (default)",
        rotor_checkpoint="trained_rotor_universal64.pt",
        thresholds={"kappa": 0.7, "R": 0.3, "S": 0.4, "N": 0.5},
        cost_per_cert=0.001,
        tags=["default", "production", "balanced"]
    ),
    CertificationModel(
        id="strict",
        name="Strict Policy",
        description="Tighter thresholds for safety-critical applications",
        rotor_checkpoint="trained_rotor_universal64.pt",
        thresholds={"kappa": 0.85, "R": 0.5, "S": 0.6, "N": 0.3},
        cost_per_cert=0.001,
        tags=["safety-critical", "healthcare", "finance"]
    ),
    CertificationModel(
        id="permissive",
        name="Permissive Policy",
        description="Looser thresholds for experimentation and development",
        rotor_checkpoint="trained_rotor_universal64.pt",
        thresholds={"kappa": 0.5, "R": 0.2, "S": 0.3, "N": 0.7},
        cost_per_cert=0.001,
        tags=["development", "prototyping", "experimentation"]
    ),
    CertificationModel(
        id="research",
        name="Research Mode",
        description="Very permissive for research and exploration",
        rotor_checkpoint="trained_rotor_universal64.pt",
        thresholds={"kappa": 0.3, "R": 0.1, "S": 0.2, "N": 0.9},
        cost_per_cert=0.001,
        tags=["research", "academic", "exploration"]
    ),
    CertificationModel(
        id="multimodal",
        name="Multimodal (High-Low-Interface)",
        description="For vision-text hybrid systems with interface scoring",
        rotor_checkpoint="trained_rotor_universal64.pt",
        thresholds={
            "kappa": 0.7,
            "kappa_H": 0.65,  # High-level (text/symbolic)
            "kappa_L": 0.65,  # Low-level (vision/signal)
            "kappa_interface": 0.60,  # Cross-modal compatibility
            "R": 0.3,
            "S": 0.4,
            "N": 0.5
        },
        cost_per_cert=0.002,
        tags=["multimodal", "vision-language", "hybrid"]
    ),
]


def get_models() -> List[Dict[str, Any]]:
    """
    Return available certification models.

    Returns:
        List of model configurations as dictionaries

    Example:
        >>> models = get_models()
        >>> for model in models:
        ...     print(f"{model['id']}: {model['name']}")
        universal64: Universal Rotor (64-dim)
        strict: Strict Policy
        ...
    """
    return [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "thresholds": m.thresholds,
            "cost_per_cert": m.cost_per_cert,
            "tags": m.tags,
        }
        for m in CERTIFICATION_MODELS
    ]


def get_model(model_id: str) -> CertificationModel:
    """
    Get specific model configuration.

    Args:
        model_id: Model identifier (e.g., "universal64", "strict")

    Returns:
        CertificationModel instance

    Raises:
        ValueError: If model_id not found

    Example:
        >>> model = get_model("strict")
        >>> print(model.thresholds["kappa"])
        0.85
    """
    for model in CERTIFICATION_MODELS:
        if model.id == model_id:
            return model
    raise ValueError(f"Unknown model: {model_id}. Available models: {[m.id for m in CERTIFICATION_MODELS]}")


def get_models_by_tag(tag: str) -> List[CertificationModel]:
    """
    Get models filtered by tag.

    Args:
        tag: Tag to filter by (e.g., "production", "research")

    Returns:
        List of matching CertificationModel instances

    Example:
        >>> prod_models = get_models_by_tag("production")
        >>> print([m.id for m in prod_models])
        ['universal64']
    """
    return [m for m in CERTIFICATION_MODELS if tag in m.tags]


def register_custom_model(model: CertificationModel):
    """
    Register a custom certification model at runtime.

    Args:
        model: CertificationModel instance to register

    Example:
        >>> custom = CertificationModel(
        ...     id="my-model",
        ...     name="Custom Model",
        ...     description="Company-specific policy",
        ...     rotor_checkpoint="my_rotor.pt",
        ...     thresholds={"kappa": 0.75, "R": 0.4, "S": 0.5, "N": 0.4},
        ...     cost_per_cert=0.001,
        ...     tags=["custom", "company"]
        ... )
        >>> register_custom_model(custom)
    """
    # Check for duplicate IDs
    if any(m.id == model.id for m in CERTIFICATION_MODELS):
        raise ValueError(f"Model ID '{model.id}' already exists")

    CERTIFICATION_MODELS.append(model)


def get_recommended_model(use_case: str) -> Optional[CertificationModel]:
    """
    Get recommended model for specific use case.

    Args:
        use_case: One of "production", "development", "safety-critical",
                  "research", "multimodal"

    Returns:
        Recommended CertificationModel or None if no match

    Example:
        >>> model = get_recommended_model("safety-critical")
        >>> print(model.id)
        strict
    """
    recommendations = {
        "production": "universal64",
        "development": "permissive",
        "safety-critical": "strict",
        "research": "research",
        "multimodal": "multimodal",
        "healthcare": "strict",
        "finance": "strict",
        "prototyping": "permissive",
    }

    model_id = recommendations.get(use_case)
    if model_id:
        return get_model(model_id)
    return None
