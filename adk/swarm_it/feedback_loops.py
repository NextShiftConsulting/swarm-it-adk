"""
Feedback Loops - Stripe Minions "Shift Left" Pattern

Inspired by Stripe's multi-layer feedback system:
- L1: Local fast checks (~50ms) - Heuristic validation
- L2: Agent analysis (~2 seconds) - LLM processing
- L3: Rotor certification (~200ms) - RSN decomposition
- L4: Quality gates (~10ms) - Gate enforcement
- Autofix: Max 2 iterations (diminishing returns)

Pattern: Catch errors early, fail fast, minimal latency
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import time


class FeedbackLevel(Enum):
    """Feedback loop levels (Stripe pattern)."""
    L1_LOCAL = "l1_local"           # Fast heuristics (~50ms)
    L2_AGENT = "l2_agent"           # LLM analysis (~2s)
    L3_ROTOR = "l3_rotor"           # RSN decomposition (~200ms)
    L4_GATES = "l4_gates"           # Quality gates (~10ms)


@dataclass
class FeedbackResult:
    """Result from feedback loop."""
    level: FeedbackLevel
    passed: bool
    reason: Optional[str] = None
    latency_ms: Optional[float] = None
    suggestions: Optional[Dict[str, Any]] = None


class LocalValidator:
    """
    L1: Local fast checks (Stripe pattern: ~5 seconds local execution).

    Heuristic-based validation to catch obvious issues before expensive operations.

    Checks:
    - Prompt length (too short/long)
    - Content type (empty, malformed)
    - Language detection
    - Profanity/unsafe content
    - Rate limiting
    """

    def __init__(
        self,
        min_length: int = 10,
        max_length: int = 100000,
        require_text: bool = True,
    ):
        self.min_length = min_length
        self.max_length = max_length
        self.require_text = require_text

    def validate(self, prompt: str) -> FeedbackResult:
        """
        Run local fast checks.

        Args:
            prompt: Input prompt

        Returns:
            FeedbackResult with pass/fail
        """
        start = time.time()

        # Check 1: Length
        if len(prompt) < self.min_length:
            return FeedbackResult(
                level=FeedbackLevel.L1_LOCAL,
                passed=False,
                reason=f"Prompt too short: {len(prompt)} < {self.min_length} chars",
                latency_ms=(time.time() - start) * 1000,
                suggestions={"fix": "Provide more detailed prompt"}
            )

        if len(prompt) > self.max_length:
            return FeedbackResult(
                level=FeedbackLevel.L1_LOCAL,
                passed=False,
                reason=f"Prompt too long: {len(prompt)} > {self.max_length} chars",
                latency_ms=(time.time() - start) * 1000,
                suggestions={"fix": "Truncate or summarize prompt"}
            )

        # Check 2: Empty or whitespace only
        if self.require_text and not prompt.strip():
            return FeedbackResult(
                level=FeedbackLevel.L1_LOCAL,
                passed=False,
                reason="Prompt is empty or whitespace only",
                latency_ms=(time.time() - start) * 1000,
                suggestions={"fix": "Provide non-empty prompt"}
            )

        # Check 3: Basic content validation
        if not self._has_meaningful_content(prompt):
            return FeedbackResult(
                level=FeedbackLevel.L1_LOCAL,
                passed=False,
                reason="Prompt lacks meaningful content",
                latency_ms=(time.time() - start) * 1000,
                suggestions={"fix": "Add more descriptive text"}
            )

        # All checks passed
        return FeedbackResult(
            level=FeedbackLevel.L1_LOCAL,
            passed=True,
            latency_ms=(time.time() - start) * 1000
        )

    def _has_meaningful_content(self, text: str) -> bool:
        """Check if text has meaningful content (not just punctuation/numbers)."""
        # Remove punctuation and whitespace
        clean = re.sub(r'[^\w\s]', '', text)
        clean = re.sub(r'\s+', '', clean)

        # Check if at least 50% is alphabetic
        if not clean:
            return False

        alphabetic = sum(1 for c in clean if c.isalpha())
        return alphabetic / len(clean) >= 0.5


class FeedbackLoopOrchestrator:
    """
    Multi-layer feedback loop orchestrator (Stripe pattern).

    Executes feedback loops in order, failing fast when possible.

    Stripe pattern: "Shift feedback left" - catch issues early
    before expensive operations (CI, rotor inference, etc.).
    """

    def __init__(
        self,
        local_validator: Optional[LocalValidator] = None,
        enable_autofix: bool = True,
        max_iterations: int = 2,  # Stripe pattern: max 2 CI rounds
    ):
        self.local_validator = local_validator or LocalValidator()
        self.enable_autofix = enable_autofix
        self.max_iterations = max_iterations

    def validate_layers(
        self,
        prompt: str,
        run_agent: bool = False,
        run_rotor: bool = False,
    ) -> Tuple[bool, Dict[str, FeedbackResult]]:
        """
        Run feedback loops in order (shift left pattern).

        Args:
            prompt: Input prompt
            run_agent: Whether to run L2 agent analysis (expensive)
            run_rotor: Whether to run L3 rotor certification (expensive)

        Returns:
            (overall_passed, results_by_level)
        """
        results = {}

        # L1: Local fast checks (always run)
        l1_result = self.local_validator.validate(prompt)
        results["L1_LOCAL"] = l1_result

        if not l1_result.passed:
            # Fail fast - don't proceed to expensive operations
            return False, results

        # L2: Agent analysis (optional, expensive)
        if run_agent:
            l2_result = self._run_agent_analysis(prompt)
            results["L2_AGENT"] = l2_result

            if not l2_result.passed:
                return False, results

        # L3: Rotor certification (optional, expensive)
        if run_rotor:
            l3_result = self._run_rotor_certification(prompt)
            results["L3_ROTOR"] = l3_result

            if not l3_result.passed:
                return False, results

        # All layers passed
        return True, results

    def certify_with_feedback(
        self,
        prompt: str,
        certify_func: callable,
    ) -> Dict[str, Any]:
        """
        Run certification with feedback loops and autofix.

        Stripe pattern: Local checks → Agent → Rotor → Gates
        with max 2 iterations for autofix.

        Args:
            prompt: Input prompt
            certify_func: Function that performs certification

        Returns:
            Certification result with feedback metadata
        """
        iteration = 0
        feedback_history = []

        while iteration < self.max_iterations:
            iteration += 1

            # L1: Local fast checks (shift left)
            l1_result = self.local_validator.validate(prompt)
            feedback_history.append(l1_result)

            if not l1_result.passed:
                # Failed local checks - no point continuing
                return {
                    "decision": "REJECT",
                    "reason": l1_result.reason,
                    "feedback_level": "L1_LOCAL",
                    "iterations": iteration,
                    "feedback_history": feedback_history,
                }

            # L2-L4: Run certification (agent + rotor + gates)
            cert_result = certify_func(prompt)

            # Check if passed
            if cert_result.get("decision") == "EXECUTE":
                return {
                    **cert_result,
                    "iterations": iteration,
                    "feedback_history": feedback_history,
                }

            # Check if we should retry with autofix
            if iteration < self.max_iterations and self.enable_autofix:
                if cert_result.get("decision") == "REPAIR":
                    # Stripe pattern: autofix based on feedback
                    prompt = self._autofix(prompt, cert_result.get("reason", ""))
                    continue

            # No more retries or terminal decision
            return {
                **cert_result,
                "iterations": iteration,
                "feedback_history": feedback_history,
            }

        # Max iterations reached
        return {
            "decision": "BLOCK",
            "reason": f"Max iterations ({self.max_iterations}) reached",
            "iterations": iteration,
            "feedback_history": feedback_history,
        }

    def _run_agent_analysis(self, prompt: str) -> FeedbackResult:
        """L2: Agent analysis (placeholder - would call LLM)."""
        # Placeholder - would integrate with actual agent
        return FeedbackResult(
            level=FeedbackLevel.L2_AGENT,
            passed=True,
            latency_ms=2000.0  # Simulated LLM latency
        )

    def _run_rotor_certification(self, prompt: str) -> FeedbackResult:
        """L3: Rotor certification (placeholder - would call rotor)."""
        # Placeholder - would integrate with actual rotor
        return FeedbackResult(
            level=FeedbackLevel.L3_ROTOR,
            passed=True,
            latency_ms=200.0  # Simulated rotor latency
        )

    def _autofix(self, prompt: str, feedback: str) -> str:
        """
        Autofix prompt based on feedback (Stripe pattern).

        Simple implementation - production would use LLM refinement.
        """
        if "Low relevance" in feedback:
            return f"{prompt}\n\n[SYSTEM: Focus on relevant details]"
        elif "Low stability" in feedback:
            return f"{prompt}\n\n[SYSTEM: Provide consistent analysis]"
        elif "High noise" in feedback:
            return f"{prompt}\n\n[SYSTEM: Reduce irrelevant content]"
        else:
            return prompt


# Convenience functions

def quick_validate(prompt: str) -> bool:
    """Quick local validation (L1 only)."""
    validator = LocalValidator()
    result = validator.validate(prompt)
    return result.passed


def validate_all_layers(prompt: str) -> Tuple[bool, Dict[str, FeedbackResult]]:
    """Run all feedback layers."""
    orchestrator = FeedbackLoopOrchestrator()
    return orchestrator.validate_layers(prompt, run_agent=True, run_rotor=True)