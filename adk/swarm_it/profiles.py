"""
Profile Configuration for Embedding Dimension Handling

Defines two explicit profiles to prevent confusion between current production
baseline and protected hardware compression path.

Reference: docs/ADR_HARDWARE_COMPRESSION_PROFILES.md
"""

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass


class SwarmProfile(Enum):
    """
    Explicit profile selection for embedding dimension handling.

    CRITICAL: These are two separate profiles, not a migration path.
    """

    # Profile A: Current production baseline
    TRACK2_NATIVE_1024 = "TRACK2_NATIVE_1024"

    # Profile B: Protected hardware compression path
    COMPACT_64_MULTIMODAL = "COMPACT_64_MULTIMODAL"

    @classmethod
    def from_string(cls, profile_str: str) -> "SwarmProfile":
        """
        Parse profile from string.

        Args:
            profile_str: Profile name as string

        Returns:
            SwarmProfile enum

        Raises:
            ValueError: If profile string is invalid
        """
        profile_str = profile_str.upper()

        try:
            return cls[profile_str]
        except KeyError:
            valid_profiles = [p.value for p in cls]
            raise ValueError(
                f"Invalid profile: {profile_str}. "
                f"Valid profiles: {valid_profiles}. "
                f"See docs/ADR_HARDWARE_COMPRESSION_PROFILES.md"
            )

    @property
    def input_dim(self) -> int:
        """Get input embedding dimension for this profile."""
        if self == SwarmProfile.TRACK2_NATIVE_1024:
            return 1024
        elif self == SwarmProfile.COMPACT_64_MULTIMODAL:
            return 1024  # Input is always 1024 from Bedrock
        else:
            raise ValueError(f"Unknown profile: {self}")

    @property
    def output_dim(self) -> int:
        """Get output embedding dimension (after projection) for this profile."""
        if self == SwarmProfile.TRACK2_NATIVE_1024:
            return 1024  # No projection, native dimension
        elif self == SwarmProfile.COMPACT_64_MULTIMODAL:
            return 64  # Compressed via projection layer
        else:
            raise ValueError(f"Unknown profile: {self}")

    @property
    def requires_projection(self) -> bool:
        """Check if this profile requires projection layer."""
        if self == SwarmProfile.TRACK2_NATIVE_1024:
            return False  # Native dimension, no projection
        elif self == SwarmProfile.COMPACT_64_MULTIMODAL:
            return True  # Hardware compression path
        else:
            raise ValueError(f"Unknown profile: {self}")

    @property
    def rotor_checkpoint(self) -> str:
        """Get rotor checkpoint filename for this profile."""
        if self == SwarmProfile.TRACK2_NATIVE_1024:
            return "trained_rotor_universal1024_titan.pt"
        elif self == SwarmProfile.COMPACT_64_MULTIMODAL:
            return "trained_rotor_universal64.pt"
        else:
            raise ValueError(f"Unknown profile: {self}")

    @property
    def projection_checkpoint(self) -> Optional[str]:
        """Get projection checkpoint filename for this profile (if needed)."""
        if self == SwarmProfile.TRACK2_NATIVE_1024:
            return None  # No projection needed
        elif self == SwarmProfile.COMPACT_64_MULTIMODAL:
            return "trained_rotor_universal64.pt"  # Same as rotor checkpoint for now
        else:
            raise ValueError(f"Unknown profile: {self}")

    @property
    def status(self) -> str:
        """Get maturity status of this profile."""
        if self == SwarmProfile.TRACK2_NATIVE_1024:
            return "PRODUCTION_VALIDATED"
        elif self == SwarmProfile.COMPACT_64_MULTIMODAL:
            return "EXPERIMENTAL"
        else:
            raise ValueError(f"Unknown profile: {self}")

    @property
    def description(self) -> str:
        """Get human-readable description of this profile."""
        if self == SwarmProfile.TRACK2_NATIVE_1024:
            return (
                "Profile A: Native 1024-dim Track 2 (current production baseline). "
                "No dimension compression. Direct R-S-N decomposition from Bedrock Titan embeddings."
            )
        elif self == SwarmProfile.COMPACT_64_MULTIMODAL:
            return (
                "Profile B: 1024→64 hardware compression (experimental/protected path). "
                "For future memristor/hardware deployment and multimodal text+vision alignment. "
                "NOT production-default."
            )
        else:
            raise ValueError(f"Unknown profile: {self}")

    @property
    def use_cases(self) -> list[str]:
        """Get typical use cases for this profile."""
        if self == SwarmProfile.TRACK2_NATIVE_1024:
            return [
                "Production API deployment",
                "AWS Bedrock integration",
                "Full semantic fidelity required",
                "Current operational baseline",
            ]
        elif self == SwarmProfile.COMPACT_64_MULTIMODAL:
            return [
                "Future memristor/neuromorphic hardware",
                "Multimodal text + vision systems",
                "Edge deployment with resource constraints",
                "Hardware efficiency research",
            ]
        else:
            raise ValueError(f"Unknown profile: {self}")


@dataclass
class ProfileConfig:
    """
    Configuration for a specific profile.

    This combines profile metadata with runtime configuration.
    """

    profile: SwarmProfile
    input_dim: int
    output_dim: int
    requires_projection: bool
    rotor_checkpoint: str
    projection_checkpoint: Optional[str]
    status: str

    @classmethod
    def from_profile(cls, profile: SwarmProfile) -> "ProfileConfig":
        """
        Create ProfileConfig from SwarmProfile enum.

        Args:
            profile: Profile enum value

        Returns:
            ProfileConfig instance with metadata populated
        """
        return cls(
            profile=profile,
            input_dim=profile.input_dim,
            output_dim=profile.output_dim,
            requires_projection=profile.requires_projection,
            rotor_checkpoint=profile.rotor_checkpoint,
            projection_checkpoint=profile.projection_checkpoint,
            status=profile.status,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "profile": self.profile.value,
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "requires_projection": self.requires_projection,
            "rotor_checkpoint": self.rotor_checkpoint,
            "projection_checkpoint": self.projection_checkpoint,
            "status": self.status,
            "description": self.profile.description,
            "use_cases": self.profile.use_cases,
        }


def get_default_profile() -> SwarmProfile:
    """
    Get default profile.

    Default is Profile A (native 1024-dim) for backward compatibility
    and production safety.

    Returns:
        SwarmProfile.TRACK2_NATIVE_1024
    """
    return SwarmProfile.TRACK2_NATIVE_1024


def validate_profile_selection(
    profile: SwarmProfile,
    require_explicit: bool = False,
) -> None:
    """
    Validate profile selection.

    Args:
        profile: Selected profile
        require_explicit: If True, raise error if default profile used implicitly

    Raises:
        ValueError: If profile selection is invalid or requires explicit choice
    """
    if require_explicit and profile == get_default_profile():
        raise ValueError(
            "Explicit profile selection required. "
            "Set SWARM_PROFILE environment variable to one of: "
            f"{[p.value for p in SwarmProfile]}"
        )

    # Warn if using experimental profile
    if profile.status == "EXPERIMENTAL":
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Using EXPERIMENTAL profile: {profile.value}. "
            f"This is NOT the production baseline. "
            f"See docs/ADR_HARDWARE_COMPRESSION_PROFILES.md"
        )


# Example usage and documentation
if __name__ == "__main__":
    print("Swarm-It Profile Configuration\n")
    print("=" * 60)

    for profile in SwarmProfile:
        print(f"\n{profile.value}:")
        print(f"  Status: {profile.status}")
        print(f"  Input dimension: {profile.input_dim}")
        print(f"  Output dimension: {profile.output_dim}")
        print(f"  Requires projection: {profile.requires_projection}")
        print(f"  Rotor checkpoint: {profile.rotor_checkpoint}")
        print(f"  Description: {profile.description}")
        print(f"  Use cases:")
        for use_case in profile.use_cases:
            print(f"    - {use_case}")

    print("\n" + "=" * 60)
    print(f"\nDefault profile: {get_default_profile().value}")
