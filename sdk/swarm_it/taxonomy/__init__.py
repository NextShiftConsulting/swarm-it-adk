"""
RSCT Taxonomy Classification

Provides error code classification, degradation typing, and feedback loops.
"""

from .classification import (
    RSCTMode,
    DegradationType,
    Severity,
    classify_certificate,
    add_error_codes,
    diagnose_multimodal,
)

from .feedback import (
    ValidationFeedbackLoop,
    FeedbackEvent,
)

from .bridge import (
    to_yrsn_dict,
    from_yrsn_dict,
    CertificateHierarchy,
)

__all__ = [
    # Classification
    "RSCTMode",
    "DegradationType",
    "Severity",
    "classify_certificate",
    "add_error_codes",
    "diagnose_multimodal",
    # Feedback
    "ValidationFeedbackLoop",
    "FeedbackEvent",
    # Bridge
    "to_yrsn_dict",
    "from_yrsn_dict",
    "CertificateHierarchy",
]
