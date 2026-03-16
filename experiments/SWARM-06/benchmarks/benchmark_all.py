#!/usr/bin/env python3
"""
SWARM-06: Jailbreak Detection Benchmark Suite

Benchmarks YRSN rotor against SOTA classifiers on jailbreak detection.

Usage:
    python benchmark_all.py --phase baseline    # H1, H2: Baseline evaluation
    python benchmark_all.py --phase finetune    # H3: Fine-tune rotor
    python benchmark_all.py --phase sota        # H4: SOTA comparison
    python benchmark_all.py --phase all         # Full benchmark

Reference: DOE_SWARM-06_Jailbreak_Detection_Benchmark.md
"""

import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional
from collections import Counter
import numpy as np

# Paths
EXPERIMENT_DIR = Path(__file__).parent.parent
DATA_DIR = EXPERIMENT_DIR / "data"
EVIDENCE_DIR = EXPERIMENT_DIR / "evidence"
RESULTS_DIR = EXPERIMENT_DIR / "results"
CHECKPOINTS_DIR = EXPERIMENT_DIR / "checkpoints"

# Ensure directories exist
EVIDENCE_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)
CHECKPOINTS_DIR.mkdir(exist_ok=True)


@dataclass
class BenchmarkResult:
    """Result from a single model benchmark."""
    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    fpr: float  # False positive rate
    fnr: float  # False negative rate
    samples: int
    latency_ms: float
    throughput: float  # samples/sec
    timestamp: str


@dataclass
class RSNStatistics:
    """RSN distribution statistics."""
    R_mean: float
    R_std: float
    S_mean: float
    S_std: float
    N_mean: float
    N_std: float
    samples: int


def load_dataset(split: str = "test") -> List[Dict]:
    """Load unified dataset split."""
    path = DATA_DIR / f"unified_{split}.jsonl"
    samples = []
    with open(path) as f:
        for line in f:
            samples.append(json.loads(line))
    return samples


def compute_metrics(predictions: List[bool], labels: List[bool]) -> Dict:
    """Compute classification metrics."""
    tp = sum(p and l for p, l in zip(predictions, labels))
    tn = sum(not p and not l for p, l in zip(predictions, labels))
    fp = sum(p and not l for p, l in zip(predictions, labels))
    fn = sum(not p and l for p, l in zip(predictions, labels))

    total = len(predictions)
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "fpr": fpr,
        "fnr": fnr,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def cohens_d(group1: List[float], group2: List[float]) -> float:
    """Compute Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_std = np.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))
    if pooled_std == 0:
        return 0
    return (np.mean(group1) - np.mean(group2)) / pooled_std


# =============================================================================
# MODEL EVALUATORS
# =============================================================================

class YRSNRotorEvaluator:
    """Evaluate YRSN rotor for jailbreak detection."""

    def __init__(self, checkpoint: str = "trained_rotor_text64.pt"):
        import sys
        import torch
        import torch.nn as nn

        # Add YRSN paths
        YRSN_SRC = Path("/Users/rudy/GitHub/yrsn/src")
        YRSN_CHECKPOINTS = Path("/Users/rudy/GitHub/yrsn/checkpoints")
        sys.path.insert(0, str(YRSN_SRC / "yrsn/adapters/models"))
        sys.path.insert(0, str(YRSN_SRC / "yrsn/core/decomposition"))

        # Load components
        from text_adapter import SentenceTransformerExtractor
        from hybrid_rotor import HybridSimplexRotor

        self.extractor = SentenceTransformerExtractor(model_name='all-MiniLM-L6-v2')

        # Projection model
        class TextMLP384to64(nn.Module):
            def __init__(self):
                super().__init__()
                self.alpha = nn.Parameter(torch.tensor(0.5))
                self.fc1 = nn.Linear(384, 192)
                self.ln1 = nn.LayerNorm(192)
                self.fc2 = nn.Linear(192, 128)
                self.ln2 = nn.LayerNorm(128)
                self.fc3 = nn.Linear(128, 64)
                self.skip = nn.Linear(384, 64)
            def forward(self, x):
                h = torch.relu(self.ln1(self.fc1(x)))
                h = torch.relu(self.ln2(self.fc2(h)))
                h = self.fc3(h)
                s = self.skip(x)
                return self.alpha * h + (1 - self.alpha) * s

        self.projection = TextMLP384to64()
        proj_ckpt = YRSN_CHECKPOINTS / "text_mlp_384to64_trained.pt"
        if proj_ckpt.exists():
            ckpt = torch.load(proj_ckpt, map_location='cpu', weights_only=False)
            self.projection.load_state_dict(ckpt.get('model_state_dict', ckpt))
        self.projection.eval()

        # Rotor
        self.rotor = HybridSimplexRotor(embed_dim=64, subspace_dim=64, hidden_dim=256)
        rotor_ckpt = YRSN_CHECKPOINTS / checkpoint
        if rotor_ckpt.exists():
            ckpt = torch.load(rotor_ckpt, map_location='cpu', weights_only=False)
            self.rotor.load_state_dict(ckpt.get('model_state_dict', ckpt))
        self.rotor.eval()

        # Thresholds
        self.N_max = 0.50
        self.R_min = 0.35
        self.S_max = 0.45

        self.torch = torch

    def compute_rsn(self, text: str) -> Dict:
        """Compute RSN for single text."""
        with self.torch.no_grad():
            emb = self.extractor.extract([text])
            emb_tensor = self.torch.tensor(emb, dtype=self.torch.float32)
            emb_64 = self.projection(emb_tensor)
            rsn = self.rotor(emb_64)
            return {
                "R": float(rsn['R'][0].item()),
                "S": float(rsn['S'][0].item()),
                "N": float(rsn['N'][0].item()),
            }

    def predict(self, text: str) -> bool:
        """Predict if text is jailbreak."""
        rsn = self.compute_rsn(text)
        # Multi-gate: N high OR noise collapsed OR manipulation
        noise_high = rsn["N"] >= self.N_max
        noise_collapsed = rsn["N"] > rsn["R"] * 0.8
        manipulation = rsn["R"] < self.R_min and rsn["S"] > self.S_max
        return noise_high or noise_collapsed or manipulation

    def evaluate(self, samples: List[Dict]) -> Tuple[BenchmarkResult, List[Dict]]:
        """Evaluate on dataset."""
        predictions = []
        labels = []
        rsn_data = []

        start = time.time()
        for sample in samples:
            rsn = self.compute_rsn(sample["text"])
            pred = self.predict(sample["text"])
            predictions.append(pred)
            labels.append(sample["is_jailbreak"])
            rsn_data.append({
                "text": sample["text"][:100],
                "label": sample["is_jailbreak"],
                "prediction": pred,
                **rsn
            })
        elapsed = time.time() - start

        metrics = compute_metrics(predictions, labels)

        result = BenchmarkResult(
            model_name="YRSN_Rotor",
            accuracy=metrics["accuracy"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1_score=metrics["f1_score"],
            fpr=metrics["fpr"],
            fnr=metrics["fnr"],
            samples=len(samples),
            latency_ms=(elapsed / len(samples)) * 1000,
            throughput=len(samples) / elapsed,
            timestamp=datetime.utcnow().isoformat(),
        )

        return result, rsn_data


class HuggingFaceEvaluator:
    """Evaluate HuggingFace jailbreak classifiers."""

    def __init__(self, model_name: str):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch

        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()
        self.torch = torch

    def predict(self, text: str) -> bool:
        """Predict if text is jailbreak."""
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with self.torch.no_grad():
            outputs = self.model(**inputs)
            pred = self.torch.argmax(outputs.logits, dim=-1).item()
        return pred == 1  # Assuming 1 = jailbreak

    def evaluate(self, samples: List[Dict]) -> BenchmarkResult:
        """Evaluate on dataset."""
        predictions = []
        labels = []

        start = time.time()
        for sample in samples:
            pred = self.predict(sample["text"])
            predictions.append(pred)
            labels.append(sample["is_jailbreak"])
        elapsed = time.time() - start

        metrics = compute_metrics(predictions, labels)

        return BenchmarkResult(
            model_name=self.model_name.split("/")[-1],
            accuracy=metrics["accuracy"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1_score=metrics["f1_score"],
            fpr=metrics["fpr"],
            fnr=metrics["fnr"],
            samples=len(samples),
            latency_ms=(elapsed / len(samples)) * 1000,
            throughput=len(samples) / elapsed,
            timestamp=datetime.utcnow().isoformat(),
        )


class KeywordBaselineEvaluator:
    """Keyword-based baseline for jailbreak detection."""

    KEYWORDS = [
        "dan", "jailbreak", "ignore", "pretend", "roleplay",
        "bypass", "unrestricted", "developer mode", "debug mode",
        "forget", "disregard", "override", "without restrictions",
        "no rules", "evil", "malicious", "unethical",
    ]

    def predict(self, text: str) -> bool:
        """Predict based on keyword presence."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.KEYWORDS)

    def evaluate(self, samples: List[Dict]) -> BenchmarkResult:
        """Evaluate on dataset."""
        predictions = []
        labels = []

        start = time.time()
        for sample in samples:
            pred = self.predict(sample["text"])
            predictions.append(pred)
            labels.append(sample["is_jailbreak"])
        elapsed = time.time() - start

        metrics = compute_metrics(predictions, labels)

        return BenchmarkResult(
            model_name="Keyword_Baseline",
            accuracy=metrics["accuracy"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1_score=metrics["f1_score"],
            fpr=metrics["fpr"],
            fnr=metrics["fnr"],
            samples=len(samples),
            latency_ms=(elapsed / len(samples)) * 1000,
            throughput=len(samples) / elapsed,
            timestamp=datetime.utcnow().isoformat(),
        )


# =============================================================================
# BENCHMARK PHASES
# =============================================================================

def run_baseline_evaluation():
    """Phase 1: H1, H2 - Baseline rotor evaluation and RSN signature analysis."""
    print("=" * 70)
    print("PHASE 1: BASELINE EVALUATION (H1, H2)")
    print("=" * 70)

    # Load test data
    test_data = load_dataset("test")
    print(f"Loaded {len(test_data)} test samples")

    # Evaluate YRSN rotor
    print("\n[H1] Evaluating YRSN rotor (baseline)...")
    rotor = YRSNRotorEvaluator()
    result, rsn_data = rotor.evaluate(test_data)

    print(f"\n--- H1 Results: Baseline YRSN Rotor ---")
    print(f"Accuracy:  {result.accuracy:.4f}")
    print(f"Precision: {result.precision:.4f}")
    print(f"Recall:    {result.recall:.4f}")
    print(f"F1 Score:  {result.f1_score:.4f}")
    print(f"FPR:       {result.fpr:.4f}")
    print(f"FNR:       {result.fnr:.4f}")
    print(f"Latency:   {result.latency_ms:.2f} ms/sample")

    # Save H1 evidence
    h1_evidence = {
        "hypothesis": "H1",
        "statement": "Pre-trained YRSN rotor achieves <60% accuracy without fine-tuning",
        "result": asdict(result),
        "passed": bool(result.accuracy < 0.60),
        "timestamp": datetime.utcnow().isoformat(),
    }
    with open(EVIDENCE_DIR / "h1_baseline_rotor.json", "w") as f:
        json.dump(h1_evidence, f, indent=2)
    print(f"\nSaved evidence to h1_baseline_rotor.json")

    # H2: RSN signature analysis
    print("\n[H2] Analyzing RSN signatures...")
    jailbreak_rsn = [r for r in rsn_data if r["label"]]
    benign_rsn = [r for r in rsn_data if not r["label"]]

    jb_R = [r["R"] for r in jailbreak_rsn]
    jb_S = [r["S"] for r in jailbreak_rsn]
    jb_N = [r["N"] for r in jailbreak_rsn]

    bn_R = [r["R"] for r in benign_rsn]
    bn_S = [r["S"] for r in benign_rsn]
    bn_N = [r["N"] for r in benign_rsn]

    print(f"\n--- H2 Results: RSN Signature Analysis ---")
    print(f"Jailbreak (n={len(jailbreak_rsn)}):")
    print(f"  R: {np.mean(jb_R):.3f} ± {np.std(jb_R):.3f}")
    print(f"  S: {np.mean(jb_S):.3f} ± {np.std(jb_S):.3f}")
    print(f"  N: {np.mean(jb_N):.3f} ± {np.std(jb_N):.3f}")

    print(f"\nBenign (n={len(benign_rsn)}):")
    print(f"  R: {np.mean(bn_R):.3f} ± {np.std(bn_R):.3f}")
    print(f"  S: {np.mean(bn_S):.3f} ± {np.std(bn_S):.3f}")
    print(f"  N: {np.mean(bn_N):.3f} ± {np.std(bn_N):.3f}")

    # Effect sizes
    d_R = cohens_d(jb_R, bn_R)
    d_S = cohens_d(jb_S, bn_S)
    d_N = cohens_d(jb_N, bn_N)

    print(f"\nEffect sizes (Cohen's d):")
    print(f"  R: {d_R:.3f}")
    print(f"  S: {d_S:.3f}")
    print(f"  N: {d_N:.3f}")

    # Save H2 evidence
    h2_evidence = {
        "hypothesis": "H2",
        "statement": "Jailbreaks exhibit distinct RSN signature: R < 0.4 AND S > 0.4",
        "jailbreak_stats": {
            "R_mean": float(np.mean(jb_R)), "R_std": float(np.std(jb_R)),
            "S_mean": float(np.mean(jb_S)), "S_std": float(np.std(jb_S)),
            "N_mean": float(np.mean(jb_N)), "N_std": float(np.std(jb_N)),
            "count": len(jailbreak_rsn),
        },
        "benign_stats": {
            "R_mean": float(np.mean(bn_R)), "R_std": float(np.std(bn_R)),
            "S_mean": float(np.mean(bn_S)), "S_std": float(np.std(bn_S)),
            "N_mean": float(np.mean(bn_N)), "N_std": float(np.std(bn_N)),
            "count": len(benign_rsn),
        },
        "effect_sizes": {"R": float(d_R), "S": float(d_S), "N": float(d_N)},
        "passed": bool(abs(d_R) > 0.8 or abs(d_S) > 0.8),
        "timestamp": datetime.utcnow().isoformat(),
    }
    with open(EVIDENCE_DIR / "h2_rsn_signature.json", "w") as f:
        json.dump(h2_evidence, f, indent=2)
    print(f"\nSaved evidence to h2_rsn_signature.json")

    # Save raw RSN data for visualization
    with open(RESULTS_DIR / "rsn_data.json", "w") as f:
        json.dump(rsn_data, f, indent=2)

    return result


def run_sota_comparison():
    """Phase 3: H4 - Compare against SOTA classifiers."""
    print("=" * 70)
    print("PHASE 3: SOTA COMPARISON (H4)")
    print("=" * 70)

    # Load test data
    test_data = load_dataset("test")
    print(f"Loaded {len(test_data)} test samples")

    results = []

    # YRSN Rotor
    print("\n[1/4] Evaluating YRSN Rotor...")
    try:
        rotor = YRSNRotorEvaluator()
        result, _ = rotor.evaluate(test_data)
        results.append(result)
        print(f"  Accuracy: {result.accuracy:.4f}")
    except Exception as e:
        print(f"  Error: {e}")

    # Keyword Baseline
    print("\n[2/4] Evaluating Keyword Baseline...")
    try:
        baseline = KeywordBaselineEvaluator()
        result = baseline.evaluate(test_data)
        results.append(result)
        print(f"  Accuracy: {result.accuracy:.4f}")
    except Exception as e:
        print(f"  Error: {e}")

    # HuggingFace models (optional - requires download)
    hf_models = [
        "jackhhao/jailbreak-classifier",
        # "madhurjindal/Jailbreak-Detector",  # Add more as needed
    ]

    for i, model_name in enumerate(hf_models, 3):
        print(f"\n[{i}/4] Evaluating {model_name}...")
        try:
            evaluator = HuggingFaceEvaluator(model_name)
            result = evaluator.evaluate(test_data)
            results.append(result)
            print(f"  Accuracy: {result.accuracy:.4f}")
        except Exception as e:
            print(f"  Error: {e}")

    # Summary table
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * 70)
    print(f"{'Model':<30} {'Acc':>8} {'F1':>8} {'Prec':>8} {'Rec':>8} {'ms':>8}")
    print("-" * 70)
    for r in results:
        print(f"{r.model_name:<30} {r.accuracy:>8.4f} {r.f1_score:>8.4f} "
              f"{r.precision:>8.4f} {r.recall:>8.4f} {r.latency_ms:>8.1f}")

    # Save H4 evidence
    h4_evidence = {
        "hypothesis": "H4",
        "statement": "Fine-tuned RSCT rotor achieves accuracy within 5% of SOTA classifiers",
        "results": [asdict(r) for r in results],
        "timestamp": datetime.utcnow().isoformat(),
    }
    with open(EVIDENCE_DIR / "h4_sota_comparison.json", "w") as f:
        json.dump(h4_evidence, f, indent=2)
    print(f"\nSaved evidence to h4_sota_comparison.json")

    # Save CSV
    import csv
    with open(RESULTS_DIR / "tables" / "benchmark_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))

    return results


def main():
    parser = argparse.ArgumentParser(description="SWARM-06 Benchmark Suite")
    parser.add_argument("--phase", choices=["baseline", "sota", "all"],
                        default="baseline", help="Benchmark phase to run")
    args = parser.parse_args()

    if args.phase == "baseline" or args.phase == "all":
        run_baseline_evaluation()

    if args.phase == "sota" or args.phase == "all":
        run_sota_comparison()

    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    print(f"Evidence saved to: {EVIDENCE_DIR}")
    print(f"Results saved to: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
