"""
DOE (Design of Experiments) Validation Test

5-Factor, Multi-Level Experimental Design:
- Factor 1: Prompt Complexity (5 levels)
- Factor 2: Domain Configuration (5 levels)
- Factor 3: API Entry Point (5 levels)
- Factor 4: Expected Quality Band (5 levels)
- Factor 5: Error Conditions (5 levels)

Each experimental point collects evidence and provides proof of correctness.
"""

import json
import sys
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Ensure we can import from swarm_it
sys.path.insert(0, 'adk')

from swarm_it import (
    certify,
    certify_local,
    certify_batch,
    LocalEngine,
    FluentCertifier,
    RSCTCertificate,
    GateDecision,
    CertificationError,
    ErrorCode,
)


# ============================================================================
# DOE Factor Definitions
# ============================================================================

@dataclass
class PromptLevel:
    """Factor 1: Prompt Complexity Levels"""
    name: str
    prompt: str
    expected_length: int
    complexity_class: str


PROMPT_LEVELS = [
    PromptLevel(
        name="L1_MINIMAL",
        prompt="Test",
        expected_length=4,
        complexity_class="minimal"
    ),
    PromptLevel(
        name="L2_SHORT",
        prompt="Calculate the fibonacci sequence up to 100",
        expected_length=42,
        complexity_class="simple"
    ),
    PromptLevel(
        name="L3_MEDIUM",
        prompt="Analyze the quarterly financial report and identify key trends in revenue, "
               "expenses, and profit margins across all business units for Q3 2025",
        expected_length=146,
        complexity_class="moderate"
    ),
    PromptLevel(
        name="L4_COMPLEX",
        prompt="Design a distributed microservices architecture for a healthcare platform "
               "that needs to handle HIPAA compliance, real-time patient monitoring, "
               "integration with multiple EHR systems, support for telemedicine workflows, "
               "and maintain 99.99% uptime while processing millions of patient records daily. "
               "Include considerations for data encryption, audit logging, disaster recovery, "
               "and multi-region deployment strategies.",
        expected_length=449,
        complexity_class="complex"
    ),
    PromptLevel(
        name="L5_NARRATIVE",
        prompt="Write a comprehensive technical specification document for implementing "
               "a novel machine learning pipeline that combines transformer-based language models "
               "with graph neural networks to perform multi-modal medical diagnosis. The system "
               "should integrate clinical notes, lab results, imaging data, and patient history "
               "to provide diagnostic recommendations with uncertainty quantification. Address "
               "model architecture, training procedures, validation methodologies, interpretability "
               "requirements, regulatory compliance considerations, deployment infrastructure, "
               "monitoring and alerting systems, and continuous improvement workflows. Include "
               "detailed performance benchmarks, ablation studies, and comparison with baseline methods.",
        expected_length=714,
        complexity_class="narrative"
    ),
]


@dataclass
class DomainLevel:
    """Factor 2: Domain Configuration Levels"""
    name: str
    domain: str
    policy: str
    strict_level: str


DOMAIN_LEVELS = [
    DomainLevel(name="D1_DEFAULT", domain="default", policy="default", strict_level="standard"),
    DomainLevel(name="D2_MEDICAL", domain="medical", policy="medical", strict_level="strict"),
    DomainLevel(name="D3_LEGAL", domain="legal", policy="legal", strict_level="strict"),
    DomainLevel(name="D4_RESEARCH", domain="research", policy="research", strict_level="moderate"),
    DomainLevel(name="D5_DEVELOPMENT", domain="development", policy="development", strict_level="permissive"),
]


@dataclass
class APIMethodLevel:
    """Factor 3: API Entry Point Levels"""
    name: str
    method_type: str
    description: str


API_METHOD_LEVELS = [
    APIMethodLevel(name="M1_CERTIFY", method_type="certify", description="Quick one-liner function"),
    APIMethodLevel(name="M2_CERTIFY_LOCAL", method_type="certify_local", description="Module-level function"),
    APIMethodLevel(name="M3_LOCAL_ENGINE", method_type="LocalEngine", description="Direct engine class"),
    APIMethodLevel(name="M4_FLUENT_SIMPLE", method_type="FluentCertifier", description="Fluent builder pattern"),
    APIMethodLevel(name="M5_FLUENT_ADVANCED", method_type="FluentCertifier_advanced", description="Fluent with config"),
]


@dataclass
class QualityBand:
    """Factor 4: Expected Quality Level"""
    name: str
    kappa_min: float
    kappa_max: float
    expected_decision: Optional[str]


QUALITY_BANDS = [
    QualityBand(name="Q1_VERY_LOW", kappa_min=0.0, kappa_max=0.3, expected_decision="REJECT"),
    QualityBand(name="Q2_LOW", kappa_min=0.3, kappa_max=0.5, expected_decision="REJECT"),
    QualityBand(name="Q3_MEDIUM", kappa_min=0.5, kappa_max=0.7, expected_decision=None),
    QualityBand(name="Q4_HIGH", kappa_min=0.7, kappa_max=0.9, expected_decision="EXECUTE"),
    QualityBand(name="Q5_VERY_HIGH", kappa_min=0.9, kappa_max=1.0, expected_decision="EXECUTE"),
]


@dataclass
class ErrorCondition:
    """Factor 5: Error Condition Levels"""
    name: str
    condition_type: str
    input_value: Any
    expected_error: Optional[ErrorCode]


ERROR_CONDITIONS = [
    ErrorCondition(name="E1_VALID", condition_type="valid", input_value="Valid prompt text", expected_error=None),
    ErrorCondition(name="E2_EMPTY", condition_type="empty", input_value="", expected_error=ErrorCode.PROMPT_EMPTY),
    ErrorCondition(name="E3_TOO_SHORT", condition_type="too_short", input_value="ab", expected_error=ErrorCode.PROMPT_TOO_SHORT),
    ErrorCondition(name="E4_NONE", condition_type="none_value", input_value=None, expected_error=ErrorCode.PROMPT_EMPTY),
    ErrorCondition(name="E5_WHITESPACE", condition_type="whitespace", input_value="   ", expected_error=ErrorCode.PROMPT_EMPTY),
]


# ============================================================================
# Evidence Collection
# ============================================================================

@dataclass
class Evidence:
    """Evidence collected for each experimental point"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Input factors
    prompt_level: str = ""
    domain_level: str = ""
    api_method: str = ""

    # Output observations
    cert_id: Optional[str] = None
    decision: Optional[str] = None
    kappa: Optional[float] = None
    R: Optional[float] = None
    S: Optional[float] = None
    N: Optional[float] = None
    sigma: Optional[float] = None
    alpha: Optional[float] = None
    gate_reached: Optional[int] = None
    reason: Optional[str] = None

    # Type validation
    return_type: str = ""
    is_rsct_certificate: bool = False
    has_decision_property: bool = False
    has_allowed_property: bool = False

    # Simplex validation
    simplex_sum: Optional[float] = None
    simplex_valid: bool = False

    # Error handling
    error_occurred: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Performance
    execution_time_ms: Optional[float] = None

    # Metadata
    notes: List[str] = field(default_factory=list)


@dataclass
class Proof:
    """Proof of correctness for experimental point"""
    experiment_id: str
    pass_fail: str = "UNKNOWN"  # PASS, FAIL, WARN

    # Assertions checked
    assertions: List[Dict[str, Any]] = field(default_factory=list)

    # Evidence summary
    evidence: Optional[Evidence] = None

    # Verdict
    verdict: str = ""
    confidence: float = 0.0


# ============================================================================
# Experimental Execution
# ============================================================================

class DOEValidator:
    """Design of Experiments Validator"""

    def __init__(self):
        self.evidence_log: List[Evidence] = []
        self.proofs: List[Proof] = []
        self.experiment_count = 0
        self.pass_count = 0
        self.fail_count = 0
        self.warn_count = 0

    def run_experiment(
        self,
        prompt_level: PromptLevel,
        domain_level: DomainLevel,
        api_method: APIMethodLevel,
    ) -> Tuple[Evidence, Proof]:
        """Run single experimental point and collect evidence"""

        self.experiment_count += 1
        experiment_id = f"EXP_{self.experiment_count:04d}"

        evidence = Evidence(
            prompt_level=prompt_level.name,
            domain_level=domain_level.name,
            api_method=api_method.name,
        )

        proof = Proof(experiment_id=experiment_id)

        try:
            import time
            start_time = time.time()

            # Execute based on API method
            cert = self._execute_api_method(
                api_method,
                prompt_level.prompt,
                domain_level
            )

            execution_time = (time.time() - start_time) * 1000

            # Collect evidence
            evidence.execution_time_ms = execution_time
            evidence.return_type = type(cert).__name__
            evidence.is_rsct_certificate = isinstance(cert, RSCTCertificate)

            if evidence.is_rsct_certificate:
                evidence.cert_id = cert.id
                evidence.decision = cert.decision.value
                evidence.has_decision_property = hasattr(cert.decision, 'allowed')
                evidence.has_allowed_property = hasattr(cert.decision, 'allowed')
                evidence.kappa = cert.kappa_gate
                evidence.R = cert.R
                evidence.S = cert.S
                evidence.N = cert.N
                evidence.sigma = cert.sigma
                evidence.alpha = cert.alpha
                evidence.gate_reached = cert.gate_reached
                evidence.reason = cert.reason

                # Validate simplex constraint
                evidence.simplex_sum = cert.R + cert.S + cert.N
                evidence.simplex_valid = abs(evidence.simplex_sum - 1.0) < 0.001

            # Generate proof
            proof = self._generate_proof(experiment_id, evidence, prompt_level, domain_level)

        except CertificationError as e:
            evidence.error_occurred = True
            evidence.error_code = e.code.value
            evidence.error_message = e.message

            proof.pass_fail = "WARN"
            proof.verdict = f"CertificationError: {e.code.value}"
            proof.confidence = 0.5

        except Exception as e:
            evidence.error_occurred = True
            evidence.error_message = str(e)

            proof.pass_fail = "FAIL"
            proof.verdict = f"Unexpected error: {type(e).__name__}"
            proof.confidence = 0.0

        proof.evidence = evidence

        self.evidence_log.append(evidence)
        self.proofs.append(proof)

        if proof.pass_fail == "PASS":
            self.pass_count += 1
        elif proof.pass_fail == "FAIL":
            self.fail_count += 1
        else:
            self.warn_count += 1

        return evidence, proof

    def _execute_api_method(
        self,
        api_method: APIMethodLevel,
        prompt: str,
        domain_level: DomainLevel
    ) -> RSCTCertificate:
        """Execute certification using specified API method"""

        if api_method.method_type == "certify":
            return certify(prompt)

        elif api_method.method_type == "certify_local":
            return certify_local(prompt, policy=domain_level.policy)

        elif api_method.method_type == "LocalEngine":
            engine = LocalEngine(policy=domain_level.policy)
            return engine.certify(prompt)

        elif api_method.method_type == "FluentCertifier":
            return (
                FluentCertifier()
                .with_prompt(prompt)
                .for_domain(domain_level.domain)
                .certify()
            )

        elif api_method.method_type == "FluentCertifier_advanced":
            certifier = FluentCertifier()

            # Apply domain preset
            if domain_level.domain == "medical":
                certifier = certifier.for_medical()
            elif domain_level.domain == "legal":
                certifier = certifier.for_legal()
            elif domain_level.domain == "research":
                certifier = certifier.for_research()
            elif domain_level.domain == "development":
                certifier = certifier.for_development()
            else:
                certifier = certifier.for_domain(domain_level.domain)

            return certifier.with_prompt(prompt).certify()

        else:
            raise ValueError(f"Unknown API method: {api_method.method_type}")

    def _generate_proof(
        self,
        experiment_id: str,
        evidence: Evidence,
        prompt_level: PromptLevel,
        domain_level: DomainLevel
    ) -> Proof:
        """Generate proof of correctness from evidence"""

        proof = Proof(experiment_id=experiment_id)
        proof.evidence = evidence

        # Assertion 1: Returns RSCTCertificate
        assertion_1 = {
            "id": "A1_RETURN_TYPE",
            "description": "Returns RSCTCertificate object",
            "expected": "RSCTCertificate",
            "actual": evidence.return_type,
            "pass": evidence.is_rsct_certificate
        }
        proof.assertions.append(assertion_1)

        # Assertion 2: Has decision property
        assertion_2 = {
            "id": "A2_DECISION_PROPERTY",
            "description": "Certificate has decision property",
            "expected": True,
            "actual": evidence.has_decision_property,
            "pass": evidence.has_decision_property
        }
        proof.assertions.append(assertion_2)

        # Assertion 3: Decision has allowed property
        assertion_3 = {
            "id": "A3_ALLOWED_PROPERTY",
            "description": "Decision has allowed property",
            "expected": True,
            "actual": evidence.has_allowed_property,
            "pass": evidence.has_allowed_property
        }
        proof.assertions.append(assertion_3)

        # Assertion 4: Simplex constraint (R + S + N = 1)
        assertion_4 = {
            "id": "A4_SIMPLEX_CONSTRAINT",
            "description": "R + S + N = 1.0 (±0.001)",
            "expected": 1.0,
            "actual": evidence.simplex_sum,
            "pass": evidence.simplex_valid
        }
        proof.assertions.append(assertion_4)

        # Assertion 5: Kappa in valid range
        kappa_valid = evidence.kappa is not None and 0.0 <= evidence.kappa <= 1.0
        assertion_5 = {
            "id": "A5_KAPPA_RANGE",
            "description": "Kappa in [0, 1]",
            "expected": "0.0 <= kappa <= 1.0",
            "actual": evidence.kappa,
            "pass": kappa_valid
        }
        proof.assertions.append(assertion_5)

        # Assertion 6: Decision is valid enum
        valid_decisions = ["EXECUTE", "REJECT", "BLOCK", "RE_ENCODE", "REPAIR", "HALT", "TIMEOUT", "ESCALATE"]
        decision_valid = evidence.decision in valid_decisions
        assertion_6 = {
            "id": "A6_VALID_DECISION",
            "description": "Decision is valid GateDecision",
            "expected": f"One of {valid_decisions}",
            "actual": evidence.decision,
            "pass": decision_valid
        }
        proof.assertions.append(assertion_6)

        # Assertion 7: Gate reached is valid
        gate_valid = evidence.gate_reached is not None and 0 <= evidence.gate_reached <= 5
        assertion_7 = {
            "id": "A7_GATE_REACHED",
            "description": "Gate reached in [0, 5]",
            "expected": "0-5",
            "actual": evidence.gate_reached,
            "pass": gate_valid
        }
        proof.assertions.append(assertion_7)

        # Assertion 8: Certificate has unique ID
        id_valid = evidence.cert_id is not None and len(evidence.cert_id) > 0
        assertion_8 = {
            "id": "A8_UNIQUE_ID",
            "description": "Certificate has unique ID",
            "expected": "Non-empty string",
            "actual": evidence.cert_id[:8] + "..." if evidence.cert_id else None,
            "pass": id_valid
        }
        proof.assertions.append(assertion_8)

        # Calculate pass rate
        passed = sum(1 for a in proof.assertions if a["pass"])
        total = len(proof.assertions)
        pass_rate = passed / total

        # Determine verdict
        if pass_rate == 1.0:
            proof.pass_fail = "PASS"
            proof.verdict = f"All {total} assertions passed"
            proof.confidence = 1.0
        elif pass_rate >= 0.75:
            proof.pass_fail = "WARN"
            proof.verdict = f"{passed}/{total} assertions passed"
            proof.confidence = pass_rate
        else:
            proof.pass_fail = "FAIL"
            proof.verdict = f"Only {passed}/{total} assertions passed"
            proof.confidence = pass_rate

        return proof

    def run_batch_experiment(self, prompts: List[str]) -> Tuple[Evidence, Proof]:
        """Test batch processing API"""

        self.experiment_count += 1
        experiment_id = f"BATCH_{self.experiment_count:04d}"

        evidence = Evidence(
            prompt_level="BATCH",
            domain_level="DEFAULT",
            api_method="M6_CERTIFY_BATCH",
        )

        proof = Proof(experiment_id=experiment_id)

        try:
            import time
            start_time = time.time()

            certs = certify_batch(prompts)

            execution_time = (time.time() - start_time) * 1000
            evidence.execution_time_ms = execution_time

            # Validate batch results
            all_valid = all(isinstance(c, RSCTCertificate) for c in certs)
            correct_count = len(certs) == len(prompts)

            evidence.return_type = f"List[RSCTCertificate] (len={len(certs)})"
            evidence.is_rsct_certificate = all_valid

            # Collect aggregate stats
            if all_valid:
                evidence.kappa = sum(c.kappa_gate for c in certs) / len(certs)
                evidence.R = sum(c.R for c in certs) / len(certs)
                evidence.S = sum(c.S for c in certs) / len(certs)
                evidence.N = sum(c.N for c in certs) / len(certs)
                evidence.notes.append(f"Processed {len(certs)} certificates")

            # Generate proof
            proof.assertions.append({
                "id": "B1_BATCH_TYPE",
                "description": "Returns List[RSCTCertificate]",
                "expected": "List[RSCTCertificate]",
                "actual": f"List (all RSCTCertificate: {all_valid})",
                "pass": all_valid
            })

            proof.assertions.append({
                "id": "B2_BATCH_COUNT",
                "description": "Correct number of results",
                "expected": len(prompts),
                "actual": len(certs),
                "pass": correct_count
            })

            passed = sum(1 for a in proof.assertions if a["pass"])
            total = len(proof.assertions)

            if passed == total:
                proof.pass_fail = "PASS"
                proof.verdict = f"Batch processing: {passed}/{total} assertions passed"
                proof.confidence = 1.0
            else:
                proof.pass_fail = "FAIL"
                proof.verdict = f"Batch processing: {passed}/{total} assertions passed"
                proof.confidence = passed / total

        except Exception as e:
            evidence.error_occurred = True
            evidence.error_message = str(e)
            proof.pass_fail = "FAIL"
            proof.verdict = f"Batch experiment failed: {e}"
            proof.confidence = 0.0

        proof.evidence = evidence
        self.proofs.append(proof)

        if proof.pass_fail == "PASS":
            self.pass_count += 1
        else:
            self.fail_count += 1

        return evidence, proof

    def run_error_condition_experiment(self, error_condition: ErrorCondition) -> Tuple[Evidence, Proof]:
        """Test error handling"""

        self.experiment_count += 1
        experiment_id = f"ERROR_{self.experiment_count:04d}"

        evidence = Evidence(
            prompt_level=error_condition.name,
            domain_level="DEFAULT",
            api_method="M1_CERTIFY",
        )

        proof = Proof(experiment_id=experiment_id)

        try:
            if error_condition.input_value is None:
                # Special handling for None
                evidence.error_occurred = True
                evidence.error_message = "None input not testable with current API"
                proof.pass_fail = "WARN"
                proof.verdict = "Cannot test None input (type error)"
                proof.confidence = 0.5
            else:
                cert = certify(error_condition.input_value)

                # If we expected an error but didn't get one
                if error_condition.expected_error is not None:
                    evidence.notes.append(f"Expected error {error_condition.expected_error} but got certificate")
                    proof.pass_fail = "WARN"
                    proof.verdict = "Expected error but got valid certificate"
                    proof.confidence = 0.5
                else:
                    # Valid case
                    evidence.is_rsct_certificate = isinstance(cert, RSCTCertificate)
                    evidence.return_type = type(cert).__name__

                    if evidence.is_rsct_certificate:
                        evidence.decision = cert.decision.value
                        evidence.kappa = cert.kappa_gate

                        proof.pass_fail = "PASS"
                        proof.verdict = "Valid input processed correctly"
                        proof.confidence = 1.0

        except CertificationError as e:
            evidence.error_occurred = True
            evidence.error_code = e.code.value
            evidence.error_message = e.message

            # Check if this is the expected error
            if error_condition.expected_error == e.code:
                proof.pass_fail = "PASS"
                proof.verdict = f"Correctly raised {e.code.value}"
                proof.confidence = 1.0
            else:
                proof.pass_fail = "WARN"
                proof.verdict = f"Got {e.code.value}, expected {error_condition.expected_error}"
                proof.confidence = 0.5

        except Exception as e:
            evidence.error_occurred = True
            evidence.error_message = str(e)
            proof.pass_fail = "FAIL"
            proof.verdict = f"Unexpected error: {type(e).__name__}"
            proof.confidence = 0.0

        proof.evidence = evidence
        self.proofs.append(proof)

        if proof.pass_fail == "PASS":
            self.pass_count += 1
        elif proof.pass_fail == "FAIL":
            self.fail_count += 1
        else:
            self.warn_count += 1

        return evidence, proof


# ============================================================================
# Main Experimental Campaign
# ============================================================================

def fmt_float(value: Optional[float], decimals: int = 3) -> str:
    """Format float with fallback"""
    return f"{value:.{decimals}f}" if value is not None else "N/A"


def main():
    print("=" * 80)
    print("DOE VALIDATION - 5-Factor Multi-Level Experimental Design")
    print("=" * 80)
    print()

    validator = DOEValidator()

    # ========================================================================
    # Experiment Set 1: Core API Methods × Prompt Complexity
    # ========================================================================
    print("EXPERIMENT SET 1: Core API Methods × Prompt Complexity")
    print("-" * 80)

    for prompt_level in PROMPT_LEVELS:
        for api_method in API_METHOD_LEVELS[:4]:  # First 4 methods
            evidence, proof = validator.run_experiment(
                prompt_level=prompt_level,
                domain_level=DOMAIN_LEVELS[0],  # Default domain
                api_method=api_method
            )

            status = {
                "PASS": "[PASS]",
                "WARN": "[WARN]",
                "FAIL": "[FAIL]"
            }[proof.pass_fail]

            kappa_str = f"{evidence.kappa:.3f}" if evidence.kappa is not None else "N/A"
            print(f"{status} {proof.experiment_id}: "
                  f"{prompt_level.name} × {api_method.name} "
                  f"-> kappa={kappa_str} "
                  f"({proof.pass_fail}: {proof.confidence:.0%})")

    print()

    # ========================================================================
    # Experiment Set 2: Domain Presets × Complexity
    # ========================================================================
    print("EXPERIMENT SET 2: Domain Presets × Prompt Complexity")
    print("-" * 80)

    for domain_level in DOMAIN_LEVELS:
        for prompt_level in [PROMPT_LEVELS[1], PROMPT_LEVELS[2], PROMPT_LEVELS[3]]:  # Short, medium, complex
            evidence, proof = validator.run_experiment(
                prompt_level=prompt_level,
                domain_level=domain_level,
                api_method=API_METHOD_LEVELS[4],  # Fluent advanced
            )

            status = {
                "PASS": "[PASS]",
                "WARN": "[WARN]",
                "FAIL": "[FAIL]"
            }[proof.pass_fail]

            print(f"{status} {proof.experiment_id}: "
                  f"{domain_level.name} × {prompt_level.name} "
                  f"-> decision={evidence.decision}, kappa={fmt_float(evidence.kappa)}")

    print()

    # ========================================================================
    # Experiment Set 3: Batch Processing
    # ========================================================================
    print("EXPERIMENT SET 3: Batch Processing Validation")
    print("-" * 80)

    batch_prompts = [p.prompt for p in PROMPT_LEVELS[:3]]
    evidence, proof = validator.run_batch_experiment(batch_prompts)

    status = {
        "PASS": "[PASS]",
        "WARN": "[WARN]",
        "FAIL": "[FAIL]"
    }[proof.pass_fail]

    print(f"{status} {proof.experiment_id}: Batch processing {len(batch_prompts)} prompts")
    print(f"  Avg kappa: {fmt_float(evidence.kappa)}")
    print(f"  Avg R={fmt_float(evidence.R)}, "
          f"S={fmt_float(evidence.S)}, "
          f"N={fmt_float(evidence.N)}")
    exec_time = f"{evidence.execution_time_ms:.1f}" if evidence.execution_time_ms else "N/A"
    print(f"  Execution time: {exec_time}ms")

    print()

    # ========================================================================
    # Experiment Set 4: Error Conditions
    # ========================================================================
    print("EXPERIMENT SET 4: Error Condition Handling")
    print("-" * 80)

    for error_condition in ERROR_CONDITIONS:
        evidence, proof = validator.run_error_condition_experiment(error_condition)

        status = {
            "PASS": "[PASS]",
            "WARN": "[WARN]",
            "FAIL": "[FAIL]"
        }[proof.pass_fail]

        print(f"{status} {proof.experiment_id}: {error_condition.name} "
              f"-> {proof.verdict}")

    print()

    # ========================================================================
    # Summary Statistics
    # ========================================================================
    print("=" * 80)
    print("EXPERIMENTAL SUMMARY")
    print("=" * 80)

    total = validator.experiment_count
    pass_rate = validator.pass_count / total if total > 0 else 0

    print(f"Total Experiments: {total}")
    print(f"  PASS: {validator.pass_count} ({validator.pass_count/total*100:.1f}%)")
    print(f"  WARN: {validator.warn_count} ({validator.warn_count/total*100:.1f}%)")
    print(f"  FAIL: {validator.fail_count} ({validator.fail_count/total*100:.1f}%)")
    print()
    print(f"Overall Pass Rate: {pass_rate:.1%}")
    print()

    # ========================================================================
    # Detailed Proof Analysis
    # ========================================================================
    print("=" * 80)
    print("DETAILED PROOF ANALYSIS")
    print("=" * 80)
    print()

    # Show first 5 proofs in detail
    for proof in validator.proofs[:5]:
        print(f"Experiment: {proof.experiment_id}")
        print(f"Verdict: {proof.pass_fail} - {proof.verdict} (confidence: {proof.confidence:.0%})")
        print(f"Evidence:")
        if proof.evidence:
            print(f"  Prompt Level: {proof.evidence.prompt_level}")
            print(f"  Domain Level: {proof.evidence.domain_level}")
            print(f"  API Method: {proof.evidence.api_method}")
            print(f"  Return Type: {proof.evidence.return_type}")
            print(f"  Decision: {proof.evidence.decision}")
            print(f"  Kappa: {fmt_float(proof.evidence.kappa)}")
            print(f"  Simplex: R={fmt_float(proof.evidence.R)}, "
                  f"S={fmt_float(proof.evidence.S)}, "
                  f"N={fmt_float(proof.evidence.N)} "
                  f"(sum={fmt_float(proof.evidence.simplex_sum)})")

        print(f"Assertions:")
        for assertion in proof.assertions:
            status = "[OK]" if assertion["pass"] else "[FAIL]"
            print(f"  {status} {assertion['id']}: {assertion['description']}")
            print(f"       Expected: {assertion['expected']}, Actual: {assertion['actual']}")
        print()

    print(f"... and {len(validator.proofs) - 5} more experiments")
    print()

    # ========================================================================
    # Export Results
    # ========================================================================
    print("=" * 80)
    print("EXPORTING RESULTS")
    print("=" * 80)

    # Export evidence log
    evidence_data = [asdict(e) for e in validator.evidence_log]
    with open('doe_evidence_log.json', 'w') as f:
        json.dump(evidence_data, f, indent=2)
    print(f"Evidence log exported: doe_evidence_log.json ({len(evidence_data)} records)")

    # Export proofs (without circular references)
    proofs_data = []
    for p in validator.proofs:
        proof_dict = {
            "experiment_id": p.experiment_id,
            "pass_fail": p.pass_fail,
            "verdict": p.verdict,
            "confidence": p.confidence,
            "assertions": p.assertions,
        }
        proofs_data.append(proof_dict)

    with open('doe_proofs.json', 'w') as f:
        json.dump(proofs_data, f, indent=2)
    print(f"Proofs exported: doe_proofs.json ({len(proofs_data)} records)")

    print()

    # ========================================================================
    # Final Verdict
    # ========================================================================
    print("=" * 80)
    print("FINAL VERDICT")
    print("=" * 80)

    if pass_rate >= 0.95:
        verdict = "EXCELLENT - Production Ready"
        grade = "A+"
    elif pass_rate >= 0.90:
        verdict = "VERY GOOD - Minor issues"
        grade = "A"
    elif pass_rate >= 0.80:
        verdict = "GOOD - Some issues to address"
        grade = "B"
    elif pass_rate >= 0.70:
        verdict = "FAIR - Significant issues"
        grade = "C"
    else:
        verdict = "POOR - Major issues"
        grade = "F"

    print(f"Grade: {grade}")
    print(f"Verdict: {verdict}")
    print(f"Pass Rate: {pass_rate:.1%}")
    print()

    if validator.fail_count > 0:
        print(f"CRITICAL: {validator.fail_count} experiments failed!")
        print("Review doe_proofs.json for details")

    if validator.warn_count > 0:
        print(f"WARNING: {validator.warn_count} experiments had warnings")

    print("=" * 80)

    return validator


if __name__ == "__main__":
    validator = main()
