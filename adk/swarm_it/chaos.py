"""
Chaos Engineering - Phase 6 Extensibility

Implements chaos engineering experiments for resilience testing:
- Fault injection (exceptions, errors)
- Latency injection (network delays, processing delays)
- Circuit breaker validation
- Error rate simulation
- Resource exhaustion testing

Based on ReliabilityEngineer recommendation:
"Need chaos engineering to validate circuit breakers and error handling
under failure conditions."

Implements:
- ChaosScenario definitions
- Fault injection decorators
- Latency injection
- Error rate control
- Experiment orchestration
- Metrics collection

Usage:
    from swarm_it_adk.chaos import ChaosManager, LatencyInjection

    # Inject latency
    manager = ChaosManager()
    manager.enable_scenario(LatencyInjection(mean_ms=100, std_ms=20))

    # Run experiment
    with manager.run_experiment("latency_test"):
        result = certifier.certify(prompt)
"""

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import random
import time
from abc import ABC, abstractmethod


class ChaosType(str, Enum):
    """Types of chaos scenarios."""
    LATENCY = "latency"
    FAULT = "fault"
    ERROR_RATE = "error_rate"
    RESOURCE = "resource"
    NETWORK = "network"


class InjectionStrategy(str, Enum):
    """Chaos injection strategies."""
    ALWAYS = "always"  # Always inject
    PROBABILITY = "probability"  # Inject with probability
    RATE_LIMIT = "rate_limit"  # Inject based on rate
    TIME_WINDOW = "time_window"  # Inject during time window


@dataclass
class ChaosMetrics:
    """Metrics collected during chaos experiment."""
    scenario_name: str
    chaos_type: ChaosType
    injections_attempted: int = 0
    injections_succeeded: int = 0
    errors_caused: int = 0
    latency_added_ms: float = 0.0
    requests_affected: int = 0
    circuit_breakers_triggered: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        """Calculate experiment duration."""
        end = self.end_time or datetime.utcnow()
        return (end - self.start_time).total_seconds()

    @property
    def injection_rate(self) -> float:
        """Calculate injection success rate."""
        if self.injections_attempted == 0:
            return 0.0
        return self.injections_succeeded / self.injections_attempted

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scenario_name": self.scenario_name,
            "chaos_type": self.chaos_type.value,
            "injections_attempted": self.injections_attempted,
            "injections_succeeded": self.injections_succeeded,
            "errors_caused": self.errors_caused,
            "latency_added_ms": self.latency_added_ms,
            "requests_affected": self.requests_affected,
            "circuit_breakers_triggered": self.circuit_breakers_triggered,
            "duration_seconds": self.duration_seconds,
            "injection_rate": self.injection_rate,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None
        }


class ChaosScenario(ABC):
    """
    Base class for chaos scenarios.

    Subclasses implement specific chaos injection behavior.
    """

    def __init__(
        self,
        name: str,
        chaos_type: ChaosType,
        strategy: InjectionStrategy = InjectionStrategy.PROBABILITY,
        probability: float = 0.1,
        enabled: bool = True
    ):
        """
        Initialize chaos scenario.

        Args:
            name: Scenario name
            chaos_type: Type of chaos
            strategy: Injection strategy
            probability: Injection probability (0.0-1.0)
            enabled: Whether scenario is enabled
        """
        self.name = name
        self.chaos_type = chaos_type
        self.strategy = strategy
        self.probability = probability
        self.enabled = enabled
        self.metrics = ChaosMetrics(name, chaos_type)

    def should_inject(self) -> bool:
        """Determine if chaos should be injected."""
        if not self.enabled:
            return False

        self.metrics.injections_attempted += 1

        if self.strategy == InjectionStrategy.ALWAYS:
            return True
        elif self.strategy == InjectionStrategy.PROBABILITY:
            return random.random() < self.probability

        return False

    @abstractmethod
    def inject(self, *args, **kwargs) -> Any:
        """
        Inject chaos.

        Subclasses must implement this method.
        """
        pass

    def record_injection(self, success: bool = True, error_caused: bool = False):
        """Record injection metrics."""
        if success:
            self.metrics.injections_succeeded += 1
            self.metrics.requests_affected += 1
        if error_caused:
            self.metrics.errors_caused += 1


class LatencyInjection(ChaosScenario):
    """
    Inject artificial latency.

    Simulates slow network, database, or API calls.
    """

    def __init__(
        self,
        mean_ms: float = 100.0,
        std_ms: float = 20.0,
        max_ms: float = 1000.0,
        probability: float = 0.1,
        enabled: bool = True
    ):
        """
        Initialize latency injection.

        Args:
            mean_ms: Mean latency in milliseconds
            std_ms: Standard deviation in milliseconds
            max_ms: Maximum latency in milliseconds
            probability: Injection probability
            enabled: Whether enabled
        """
        super().__init__(
            name=f"latency_{int(mean_ms)}ms",
            chaos_type=ChaosType.LATENCY,
            probability=probability,
            enabled=enabled
        )
        self.mean_ms = mean_ms
        self.std_ms = std_ms
        self.max_ms = max_ms

    def inject(self) -> float:
        """
        Inject latency by sleeping.

        Returns:
            Actual latency injected in milliseconds
        """
        if not self.should_inject():
            return 0.0

        # Generate latency from normal distribution
        latency_ms = random.gauss(self.mean_ms, self.std_ms)
        latency_ms = max(0, min(latency_ms, self.max_ms))

        # Sleep for latency duration
        time.sleep(latency_ms / 1000.0)

        # Record metrics
        self.record_injection(success=True)
        self.metrics.latency_added_ms += latency_ms

        return latency_ms


class FaultInjection(ChaosScenario):
    """
    Inject faults (exceptions).

    Simulates service failures, API errors, etc.
    """

    def __init__(
        self,
        exception_type: type = Exception,
        exception_message: str = "Chaos engineering fault injection",
        probability: float = 0.1,
        enabled: bool = True
    ):
        """
        Initialize fault injection.

        Args:
            exception_type: Type of exception to raise
            exception_message: Exception message
            probability: Injection probability
            enabled: Whether enabled
        """
        super().__init__(
            name=f"fault_{exception_type.__name__}",
            chaos_type=ChaosType.FAULT,
            probability=probability,
            enabled=enabled
        )
        self.exception_type = exception_type
        self.exception_message = exception_message

    def inject(self):
        """
        Inject fault by raising exception.

        Raises:
            Exception: If injection occurs
        """
        if not self.should_inject():
            return

        # Record metrics
        self.record_injection(success=True, error_caused=True)

        # Raise exception
        raise self.exception_type(self.exception_message)


class ErrorRateInjection(ChaosScenario):
    """
    Inject errors to simulate increased error rate.

    Returns error responses instead of raising exceptions.
    """

    def __init__(
        self,
        error_response: Any = None,
        target_error_rate: float = 0.1,
        enabled: bool = True
    ):
        """
        Initialize error rate injection.

        Args:
            error_response: Response to return on error
            target_error_rate: Target error rate (0.0-1.0)
            enabled: Whether enabled
        """
        super().__init__(
            name=f"error_rate_{int(target_error_rate*100)}pct",
            chaos_type=ChaosType.ERROR_RATE,
            probability=target_error_rate,
            enabled=enabled
        )
        self.error_response = error_response or {"error": "Chaos-induced error"}

    def inject(self) -> Optional[Any]:
        """
        Inject error response.

        Returns:
            Error response if injection occurs, None otherwise
        """
        if not self.should_inject():
            return None

        # Record metrics
        self.record_injection(success=True, error_caused=True)

        return self.error_response


class ResourceExhaustionInjection(ChaosScenario):
    """
    Simulate resource exhaustion.

    Allocates memory, CPU, or other resources.
    """

    def __init__(
        self,
        memory_mb: float = 100.0,
        duration_seconds: float = 1.0,
        probability: float = 0.05,
        enabled: bool = True
    ):
        """
        Initialize resource exhaustion.

        Args:
            memory_mb: Memory to allocate in MB
            duration_seconds: Duration to hold resources
            probability: Injection probability
            enabled: Whether enabled
        """
        super().__init__(
            name=f"resource_{int(memory_mb)}mb",
            chaos_type=ChaosType.RESOURCE,
            probability=probability,
            enabled=enabled
        )
        self.memory_mb = memory_mb
        self.duration_seconds = duration_seconds

    def inject(self):
        """
        Inject resource exhaustion.

        Allocates memory for specified duration.
        """
        if not self.should_inject():
            return

        # Record metrics
        self.record_injection(success=True)

        # Allocate memory (list of bytes)
        memory_bytes = int(self.memory_mb * 1024 * 1024)
        data = bytearray(memory_bytes)

        # Hold for duration
        time.sleep(self.duration_seconds)

        # Release memory
        del data


class ChaosManager:
    """
    Chaos engineering manager.

    Orchestrates chaos scenarios and collects metrics.

    Usage:
        manager = ChaosManager()

        # Add scenarios
        manager.add_scenario(LatencyInjection(mean_ms=100))
        manager.add_scenario(FaultInjection(exception_type=TimeoutError))

        # Run experiment
        with manager.run_experiment("resilience_test"):
            for i in range(100):
                try:
                    result = certifier.certify(prompts[i])
                except Exception as e:
                    # Circuit breaker should handle this
                    pass

        # Get metrics
        metrics = manager.get_experiment_metrics("resilience_test")
    """

    def __init__(self):
        """Initialize chaos manager."""
        self.scenarios: Dict[str, ChaosScenario] = {}
        self.experiment_metrics: Dict[str, List[ChaosMetrics]] = {}
        self._active_experiment: Optional[str] = None

    def add_scenario(self, scenario: ChaosScenario):
        """Add chaos scenario."""
        self.scenarios[scenario.name] = scenario

    def remove_scenario(self, name: str):
        """Remove chaos scenario."""
        self.scenarios.pop(name, None)

    def enable_scenario(self, name: str):
        """Enable scenario."""
        if name in self.scenarios:
            self.scenarios[name].enabled = True

    def disable_scenario(self, name: str):
        """Disable scenario."""
        if name in self.scenarios:
            self.scenarios[name].enabled = False

    def disable_all_scenarios(self):
        """Disable all scenarios."""
        for scenario in self.scenarios.values():
            scenario.enabled = False

    def enable_all_scenarios(self):
        """Enable all scenarios."""
        for scenario in self.scenarios.values():
            scenario.enabled = True

    def inject_latency(self) -> float:
        """
        Inject latency from all enabled latency scenarios.

        Returns:
            Total latency injected in milliseconds
        """
        total_latency = 0.0
        for scenario in self.scenarios.values():
            if isinstance(scenario, LatencyInjection) and scenario.enabled:
                total_latency += scenario.inject()
        return total_latency

    def inject_fault(self):
        """
        Inject faults from all enabled fault scenarios.

        May raise exceptions.
        """
        for scenario in self.scenarios.values():
            if isinstance(scenario, FaultInjection) and scenario.enabled:
                scenario.inject()

    def inject_error(self) -> Optional[Any]:
        """
        Inject errors from all enabled error scenarios.

        Returns:
            Error response if injection occurs
        """
        for scenario in self.scenarios.values():
            if isinstance(scenario, ErrorRateInjection) and scenario.enabled:
                error = scenario.inject()
                if error is not None:
                    return error
        return None

    def run_experiment(self, name: str):
        """
        Context manager for running chaos experiment.

        Usage:
            with manager.run_experiment("test"):
                # Run code under chaos
                pass
        """
        return ChaosExperiment(self, name)

    def start_experiment(self, name: str):
        """Start chaos experiment."""
        self._active_experiment = name
        # Reset scenario metrics
        for scenario in self.scenarios.values():
            scenario.metrics = ChaosMetrics(scenario.name, scenario.chaos_type)

    def end_experiment(self, name: str):
        """End chaos experiment and collect metrics."""
        if self._active_experiment != name:
            return

        # Collect metrics from all scenarios
        metrics = []
        for scenario in self.scenarios.values():
            scenario.metrics.end_time = datetime.utcnow()
            metrics.append(scenario.metrics)

        # Store metrics
        if name not in self.experiment_metrics:
            self.experiment_metrics[name] = []
        self.experiment_metrics[name].extend(metrics)

        self._active_experiment = None

    def get_experiment_metrics(self, name: str) -> List[ChaosMetrics]:
        """Get metrics for experiment."""
        return self.experiment_metrics.get(name, [])

    def get_all_metrics(self) -> Dict[str, List[ChaosMetrics]]:
        """Get all experiment metrics."""
        return self.experiment_metrics


class ChaosExperiment:
    """Context manager for chaos experiments."""

    def __init__(self, manager: ChaosManager, name: str):
        """Initialize experiment context."""
        self.manager = manager
        self.name = name

    def __enter__(self):
        """Start experiment."""
        self.manager.start_experiment(self.name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End experiment."""
        self.manager.end_experiment(self.name)
        return False


# Decorator for chaos injection

def with_chaos(manager: ChaosManager):
    """
    Decorator to inject chaos into function.

    Usage:
        @with_chaos(manager)
        def certify(prompt):
            return certifier.certify(prompt)
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # Inject latency
            manager.inject_latency()

            # Inject faults (may raise)
            manager.inject_fault()

            # Check for error injection
            error = manager.inject_error()
            if error is not None:
                return error

            # Execute function
            return func(*args, **kwargs)

        return wrapper
    return decorator


# Global chaos manager
_global_manager: Optional[ChaosManager] = None


def get_chaos_manager() -> ChaosManager:
    """Get or create global chaos manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = ChaosManager()
    return _global_manager


def configure_chaos(scenarios: List[ChaosScenario]):
    """Configure global chaos manager with scenarios."""
    manager = get_chaos_manager()
    for scenario in scenarios:
        manager.add_scenario(scenario)
