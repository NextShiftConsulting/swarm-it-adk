"""
Swarm It SDK - Execution Governance for AI Agent Swarms

Provides RSCT certification for AI/LLM calls with multi-agent swarm support.

Quick Start:
    from swarm_it import SwarmIt

    swarm = SwarmIt(api_key="your-key")
    cert = swarm.certify("What is the capital of France?")

    if cert.allowed:
        response = my_llm(prompt)
    else:
        print(f"Blocked: {cert.reason}")

Modules:
    - local: Local certification engine (RSCTCertificate, LocalEngine)
    - taxonomy: Classification and validation (RSCTMode, ValidationFeedbackLoop)
    - topology: Multi-agent swarm models (Agent, Swarm, SwarmCertifier)
    - persistence: Certificate storage (MemoryStore, SQLiteStore, AuditLog)
    - integrations: Framework integrations (LangChain, FastAPI)
"""

__version__ = "0.2.0"

# === Local Engine ===
from .local.engine import (
    RSCTCertificate,
    GateDecision,
    LocalEngine,
    certify_local,
)

# === Fluent API ===
from .fluent import (
    FluentCertifier,
    certify,
    certify_batch,
)

# === Legacy Client (backward compatibility) ===
from .client import SwarmIt, Certificate

# === Taxonomy Classification ===
from .taxonomy.classification import (
    RSCTMode,
    DegradationType,
    Severity,
    classify_certificate,
    add_error_codes,
    diagnose_multimodal,
)

from .taxonomy.feedback import (
    ValidationFeedbackLoop,
    ValidationType,
    FeedbackEvent,
)

from .taxonomy.bridge import (
    to_yrsn_dict,
    from_yrsn_dict,
    CertificateHierarchy,
)

# === Topology Models ===
from .topology.models import (
    SolverType,
    Modality,
    Agent,
    Channel,
    Swarm,
)

from .topology.certifier import (
    SwarmCertifier,
    SwarmCertificate,
    certify_swarm,
)

from .topology.patterns import (
    SwarmPattern,
    create_pipeline_swarm,
    create_hub_spoke_swarm,
    create_mesh_swarm,
    create_ring_swarm,
)

# === Persistence ===
from .persistence.store import (
    CertificateStore,
    MemoryStore,
    SQLiteStore,
)

from .persistence.audit import (
    AuditLog,
    AuditEntry,
    SR117AuditFormatter,
)

# === Decorators ===
from .decorators import gate, certified

# === Exceptions ===
from .exceptions import (
    SwarmItError,
    CertificationError,  # Re-exported from errors.py for structured error handling
    GateBlockedError,
    AuthenticationError,
)

# === Structured Errors ===
from .errors import (
    ErrorCode,
)

# === Circuit Breakers ===
from .circuit_breakers import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerError,
)

# === Chaos Engineering ===
from .chaos import (
    ChaosManager,
    ChaosScenario,
)

# === Swarm Factory ===
from .swarm_factory import (
    create_swarm,
    create_agent,
    create_preset_swarm,
    ProviderAgentWrapper,
    AgentConfig,
    SwarmConfig,
    PRESET_SWARMS,
)


__all__ = [
    # Version
    "__version__",

    # Local Engine
    "RSCTCertificate",
    "GateDecision",
    "LocalEngine",
    "certify_local",

    # Fluent API
    "FluentCertifier",
    "certify",
    "certify_batch",

    # Legacy Client
    "SwarmIt",
    "Certificate",

    # Taxonomy
    "RSCTMode",
    "DegradationType",
    "Severity",
    "classify_certificate",
    "add_error_codes",
    "diagnose_multimodal",
    "ValidationFeedbackLoop",
    "ValidationType",
    "FeedbackEvent",
    "to_yrsn_dict",
    "from_yrsn_dict",
    "CertificateHierarchy",

    # Topology
    "SolverType",
    "Modality",
    "Agent",
    "Channel",
    "Swarm",
    "SwarmCertifier",
    "SwarmCertificate",
    "certify_swarm",
    "SwarmPattern",
    "create_pipeline_swarm",
    "create_hub_spoke_swarm",
    "create_mesh_swarm",
    "create_ring_swarm",

    # Persistence
    "CertificateStore",
    "MemoryStore",
    "SQLiteStore",
    "AuditLog",
    "AuditEntry",
    "SR117AuditFormatter",

    # Decorators
    "gate",
    "certified",

    # Exceptions
    "SwarmItError",
    "GateBlockedError",
    "AuthenticationError",

    # Structured Errors
    "CertificationError",
    "ErrorCode",

    # Circuit Breakers
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "CircuitBreakerError",

    # Chaos Engineering
    "ChaosManager",
    "ChaosScenario",

    # Swarm Factory
    "create_swarm",
    "create_agent",
    "create_preset_swarm",
    "ProviderAgentWrapper",
    "AgentConfig",
    "SwarmConfig",
    "PRESET_SWARMS",
]
