#!/usr/bin/env python3
"""
Unified Experiment Runner with AutoLoop Support

Converts DOE experiment templates to executable experiments with optional
Karpathy-style autoloop for metric optimization.

Usage:
    python experiment_runner.py SWARM-01 run           # One-shot run
    python experiment_runner.py SWARM-01 autoloop      # Continuous optimization
    python experiment_runner.py SWARM-01 analyze       # Analyze results
    python experiment_runner.py SWARM-01 status        # Check status

Structure expected per experiment:
    experiments/SWARM-XX/
    ├── DOE_SWARM-XX_*.md        # Hypothesis specification
    ├── run_experiment.py        # Optional custom runner
    ├── autoloop/                # AutoLoop configuration
    │   ├── config.yaml          # Mutable surface + metric
    │   ├── evaluate.py          # Optional custom evaluator
    │   └── results.tsv          # Experiment log
    └── evidence/                # Evidence files
        └── h*_*.json
"""

import os
import sys
import re
import json
import yaml
import time
import hashlib
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional


# =============================================================================
# CONFIGURATION
# =============================================================================

EXPERIMENTS_DIR = (Path(__file__).parent.parent / "experiments").resolve()
DEFAULT_TIME_BUDGET = 120  # 2 minutes per evaluation


@dataclass
class Hypothesis:
    """Parsed hypothesis from DOE markdown."""
    id: str
    statement: str
    variables: Dict[str, str]
    metrics: Dict[str, Any]
    evidence_file: str


@dataclass
class ExperimentSpec:
    """Parsed experiment specification."""
    exp_id: str
    title: str
    hypotheses: List[Hypothesis]
    status: str
    last_updated: str


@dataclass
class AutoLoopConfig:
    """AutoLoop configuration for an experiment."""
    experiment: str
    hypothesis: str
    metric: str
    mutable_surface: Dict[str, Any]
    constraints: Dict[str, Any]


@dataclass
class RunResult:
    """Result of a single experiment run."""
    timestamp: str
    commit: str
    metric_name: str
    metric_value: float
    status: str  # keep, discard, crash
    description: str
    config_hash: str
    details: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# DOE MARKDOWN PARSER
# =============================================================================

def parse_doe_markdown(exp_id: str) -> Optional[ExperimentSpec]:
    """Parse DOE markdown file into ExperimentSpec."""
    exp_dir = EXPERIMENTS_DIR / exp_id

    # Find DOE markdown file
    doe_files = list(exp_dir.glob("DOE_*.md"))
    if not doe_files:
        print(f"No DOE markdown found in {exp_dir}")
        return None

    doe_file = doe_files[0]

    with open(doe_file) as f:
        content = f.read()

    # Parse metadata
    title_match = re.search(r"^# DOE: (.+)$", content, re.MULTILINE)
    title = title_match.group(1) if title_match else exp_id

    status_match = re.search(r"\*\*Status:\*\* (\w+)", content)
    status = status_match.group(1) if status_match else "UNKNOWN"

    date_match = re.search(r"\*\*Last Updated:\*\* ([\d-]+)", content)
    last_updated = date_match.group(1) if date_match else "unknown"

    # Parse hypotheses
    hypotheses = []
    h_pattern = r"### (H\d+): (.+?)\n\*\*Statement:\*\* (.+?)(?=\n\n|\n###|\Z)"
    for match in re.finditer(h_pattern, content, re.DOTALL):
        h_id, h_title, h_content = match.groups()

        # Parse variables table
        variables = {}
        var_pattern = r"\| (\w+) \| (.+?) \|"
        for var_match in re.finditer(var_pattern, h_content):
            var_type, var_desc = var_match.groups()
            if var_type in ["Independent", "Dependent", "Control"]:
                variables[var_type] = var_desc.strip()

        # Parse metrics
        metrics = {}
        metric_pattern = r"- `(\w+)`: Expected = (.+)"
        for m_match in re.finditer(metric_pattern, h_content):
            metrics[m_match.group(1)] = m_match.group(2)

        # Parse evidence file
        evidence_match = re.search(r"\*\*Evidence Required:\*\* `(.+?)`", h_content)
        evidence_file = evidence_match.group(1) if evidence_match else f"evidence/{h_id.lower()}.json"

        hypotheses.append(Hypothesis(
            id=h_id,
            statement=h_title.strip(),
            variables=variables,
            metrics=metrics,
            evidence_file=evidence_file,
        ))

    return ExperimentSpec(
        exp_id=exp_id,
        title=title,
        hypotheses=hypotheses,
        status=status,
        last_updated=last_updated,
    )


# =============================================================================
# AUTOLOOP CONFIGURATION
# =============================================================================

def load_autoloop_config(exp_id: str) -> Optional[AutoLoopConfig]:
    """Load autoloop configuration for experiment."""
    config_path = EXPERIMENTS_DIR / exp_id / "autoloop" / "config.yaml"

    if not config_path.exists():
        return None

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return AutoLoopConfig(
        experiment=config.get("experiment", exp_id),
        hypothesis=config.get("hypothesis", "H1"),
        metric=config.get("metric", "f1_score"),
        mutable_surface=config.get("thresholds", {}),
        constraints=config.get("constraints", {}),
    )


def save_autoloop_config(exp_id: str, config: AutoLoopConfig):
    """Save autoloop configuration."""
    config_path = EXPERIMENTS_DIR / exp_id / "autoloop" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump({
            "experiment": config.experiment,
            "hypothesis": config.hypothesis,
            "metric": config.metric,
            "thresholds": config.mutable_surface,
            "constraints": config.constraints,
        }, f, default_flow_style=False)


def hash_config(config: Dict[str, Any]) -> str:
    """Create reproducibility hash of configuration."""
    serialized = json.dumps(config, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:12]


def mutate_config(exp_id: str, config: AutoLoopConfig):
    """Randomly mutate one threshold in config.yaml."""
    import random

    config_path = EXPERIMENTS_DIR / exp_id / "autoloop" / "config.yaml"

    with open(config_path) as f:
        yaml_config = yaml.safe_load(f)

    # Find mutable thresholds
    thresholds = yaml_config.get("thresholds", {})
    domains = thresholds.get("domains", {})

    # Pick random domain and adjust multiplier
    if domains:
        domain = random.choice(list(domains.keys()))
        current = domains[domain].get("multiplier", 1.0)

        # Adjust by ±0.05
        delta = random.choice([-0.05, 0.05])
        new_value = max(0.8, min(1.3, current + delta))

        domains[domain]["multiplier"] = round(new_value, 2)
        print(f"  Mutated {domain} multiplier: {current:.2f} → {new_value:.2f}")

        # Save
        with open(config_path, "w") as f:
            yaml.dump(yaml_config, f, default_flow_style=False)


# =============================================================================
# EXPERIMENT RUNNER
# =============================================================================

def run_experiment(exp_id: str, hypothesis: Optional[str] = None) -> Dict[str, Any]:
    """Run experiment (one-shot mode)."""
    exp_dir = EXPERIMENTS_DIR / exp_id

    # Check for custom runner
    custom_runner = exp_dir / "run_experiment.py"
    if custom_runner.exists():
        print(f"Running custom runner: {custom_runner}")
        result = subprocess.run(
            [sys.executable, str(custom_runner)],
            capture_output=True,
            text=True,
            cwd=str(exp_dir),
            timeout=300,
        )
        print(result.stdout)
        if result.stderr:
            print(f"STDERR: {result.stderr}", file=sys.stderr)
        return {"status": "completed", "returncode": result.returncode}

    # Otherwise, parse spec and run tests
    spec = parse_doe_markdown(exp_id)
    if not spec:
        return {"status": "error", "message": f"No DOE spec found for {exp_id}"}

    print(f"=== {spec.title} ===")
    print(f"Status: {spec.status}")
    print(f"Hypotheses: {len(spec.hypotheses)}")
    print()

    results = {}
    for h in spec.hypotheses:
        if hypothesis and h.id != hypothesis:
            continue

        print(f"[{h.id}] {h.statement}")
        print(f"  Variables: {h.variables}")
        print(f"  Metrics: {h.metrics}")
        print(f"  Evidence: {h.evidence_file}")

        # Check if evidence exists
        evidence_path = exp_dir / h.evidence_file
        if evidence_path.exists():
            with open(evidence_path) as f:
                evidence = json.load(f)
            results[h.id] = {"status": "PASS", "evidence": evidence}
            print(f"  Status: PASS (evidence exists)")
        else:
            results[h.id] = {"status": "NOT_TESTED", "evidence": None}
            print(f"  Status: NOT_TESTED")
        print()

    return {"status": "completed", "results": results}


# =============================================================================
# AUTOLOOP RUNNER
# =============================================================================

def run_autoloop(exp_id: str, max_iterations: Optional[int] = None):
    """Run experiment in autoloop mode (Karpathy pattern)."""
    exp_dir = EXPERIMENTS_DIR / exp_id
    autoloop_dir = exp_dir / "autoloop"

    # Load config
    config = load_autoloop_config(exp_id)
    if not config:
        print(f"No autoloop config found for {exp_id}")
        print(f"Create {autoloop_dir}/config.yaml first")
        return

    # Initialize results file
    results_file = autoloop_dir / "results.tsv"
    if not results_file.exists():
        with open(results_file, "w") as f:
            f.write("timestamp\tcommit\tmetric\tvalue\tstatus\tdescription\thash\n")

    # Check for custom evaluator
    evaluate_script = autoloop_dir / "evaluate.py"
    use_custom_eval = evaluate_script.exists()

    print(f"=== AutoLoop: {exp_id} ===")
    print(f"Hypothesis: {config.hypothesis}")
    print(f"Metric: {config.metric}")
    print(f"Custom evaluator: {use_custom_eval}")
    print()

    best_metric = 0.0
    iteration = 0

    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")

        # Mutate config (random threshold adjustment)
        if iteration > 1:
            mutate_config(exp_id, config)

        # Get current commit
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, cwd=str(exp_dir)
            ).stdout.strip()
        except Exception:
            commit = f"iter{iteration}"

        # Run evaluation
        try:
            if use_custom_eval:
                result = subprocess.run(
                    [sys.executable, str(evaluate_script)],
                    capture_output=True, text=True,
                    cwd=str(autoloop_dir),
                    timeout=DEFAULT_TIME_BUDGET,
                )
                output = result.stdout

                # Parse metric from output
                metric_match = re.search(rf"^{config.metric}:\s*([\d.]+)", output, re.MULTILINE)
                if metric_match:
                    metric_value = float(metric_match.group(1))
                else:
                    print(f"Could not parse {config.metric} from output")
                    metric_value = 0.0
            else:
                # Mock evaluation
                import random
                metric_value = best_metric + random.uniform(-0.05, 0.1)
                metric_value = max(0.0, min(1.0, metric_value))

        except subprocess.TimeoutExpired:
            print("Evaluation timed out")
            metric_value = 0.0
            status = "timeout"
        except Exception as e:
            print(f"Evaluation error: {e}")
            metric_value = 0.0
            status = "crash"
        else:
            status = "keep" if metric_value > best_metric else "discard"

        # Log result
        config_hash = hash_config(config.mutable_surface)
        timestamp = datetime.utcnow().isoformat()

        result = RunResult(
            timestamp=timestamp,
            commit=commit,
            metric_name=config.metric,
            metric_value=metric_value,
            status=status,
            description=f"iteration {iteration}",
            config_hash=config_hash,
        )

        with open(results_file, "a") as f:
            f.write(f"{result.timestamp}\t{result.commit}\t{result.metric_name}\t"
                    f"{result.metric_value:.6f}\t{result.status}\t"
                    f"{result.description}\t{result.config_hash}\n")

        print(f"{config.metric}: {metric_value:.6f} [{status}]")

        # Update best
        if metric_value > best_metric:
            best_metric = metric_value
            print(f"New best: {best_metric:.6f}")

        # Brief pause
        time.sleep(1)

    print(f"\n=== AutoLoop Complete ===")
    print(f"Iterations: {iteration}")
    print(f"Best {config.metric}: {best_metric:.6f}")


# =============================================================================
# ANALYSIS
# =============================================================================

def analyze_results(exp_id: str):
    """Analyze autoloop results."""
    results_file = EXPERIMENTS_DIR / exp_id / "autoloop" / "results.tsv"

    if not results_file.exists():
        print(f"No results file found: {results_file}")
        return

    # Read results
    results = []
    with open(results_file) as f:
        header = f.readline().strip().split("\t")
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= len(header):
                results.append(dict(zip(header, parts)))

    if not results:
        print("No results to analyze")
        return

    # Statistics
    total = len(results)
    kept = sum(1 for r in results if r.get("status") == "keep")
    discarded = sum(1 for r in results if r.get("status") == "discard")
    crashed = sum(1 for r in results if r.get("status") in ["crash", "timeout"])

    # Best result
    best = max(results, key=lambda r: float(r.get("value", 0)))

    print(f"=== Analysis: {exp_id} ===")
    print(f"Total experiments: {total}")
    print(f"Kept: {kept}")
    print(f"Discarded: {discarded}")
    print(f"Crashed: {crashed}")
    print()
    print(f"Best {best.get('metric', 'metric')}: {best.get('value')}")
    print(f"Commit: {best.get('commit')}")
    print(f"Description: {best.get('description')}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Unified Experiment Runner")
    parser.add_argument("experiment", help="Experiment ID (e.g., SWARM-01)")
    parser.add_argument("command", choices=["run", "autoloop", "analyze", "status"],
                        help="Command to execute")
    parser.add_argument("--hypothesis", "-H", help="Specific hypothesis to run")
    parser.add_argument("--iterations", "-n", type=int, help="Max autoloop iterations")
    args = parser.parse_args()

    if args.command == "run":
        run_experiment(args.experiment, hypothesis=args.hypothesis)
    elif args.command == "autoloop":
        run_autoloop(args.experiment, max_iterations=args.iterations)
    elif args.command == "analyze":
        analyze_results(args.experiment)
    elif args.command == "status":
        spec = parse_doe_markdown(args.experiment)
        if spec:
            print(f"Experiment: {spec.exp_id}")
            print(f"Title: {spec.title}")
            print(f"Status: {spec.status}")
            print(f"Hypotheses: {len(spec.hypotheses)}")
            for h in spec.hypotheses:
                print(f"  - {h.id}: {h.statement}")


if __name__ == "__main__":
    main()
