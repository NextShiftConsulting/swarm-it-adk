#!/usr/bin/env python3
"""
SWARM-01 Timeline Integration (Standalone)

Generates ExperimentTimeline and HypothesisValidationMatrix visualizations
compatible with yrsn tracking infrastructure, but standalone.

Usage:
    python integrate_with_yrsn.py
"""

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from matplotlib.colors import ListedColormap
import numpy as np

# ============================================================================
# Data Classes (yrsn-compatible)
# ============================================================================

@dataclass
class ExperimentEvidence:
    """Evidence from a single experiment run (yrsn-compatible)."""
    exp_id: str
    file_path: str
    timestamp: datetime
    claims: List[str]
    status: str  # PASS/FAIL/PARTIAL/UNKNOWN
    schema_type: str
    metadata: Dict[str, Any]


@dataclass
class HypothesisResult:
    """Result of a hypothesis test (yrsn-compatible)."""
    hypothesis_id: str
    exp_id: str
    result: str  # PASS/FAIL/NOT_TESTED
    metric_value: Optional[float]
    p_value: Optional[float]


# ============================================================================
# YRSN Colors (standalone copy)
# ============================================================================

class YRSNColors:
    """YRSN color palette."""
    GREEN = '#2ECC71'
    RED = '#E74C3C'
    ORANGE = '#F39C12'
    PURPLE = '#9B59B6'
    GRAY = '#95A5A6'
    BLUE = '#3498DB'


# ============================================================================
# Paths
# ============================================================================

RESULTS_DIR = Path(__file__).parent / "results"
AGGREGATED_DIR = RESULTS_DIR / "aggregated"
PUBLICATION_DIR = RESULTS_DIR / "publication" / "tracking"
PUBLICATION_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# ExperimentTimeline (standalone implementation)
# ============================================================================

class ExperimentTimeline:
    """
    Creates Gantt-style timeline visualization of experiment runs.

    Features:
    - X-axis: Time (chronological)
    - Y-axis: Experiment ID
    - Color: Status (PASS=green, FAIL=red, PARTIAL=yellow, UNKNOWN=purple)
    """

    def __init__(self, evidence_list: List[ExperimentEvidence]):
        self.evidence_list = evidence_list
        self.status_colors = {
            'PASS': YRSNColors.GREEN,
            'FAIL': YRSNColors.RED,
            'PARTIAL': YRSNColors.ORANGE,
            'UNKNOWN': YRSNColors.PURPLE
        }

    def _group_by_experiment_and_date(self) -> Dict:
        """Group evidence by experiment ID and date."""
        grouped = defaultdict(lambda: defaultdict(lambda: {'status': 'UNKNOWN', 'count': 0}))

        for evidence in self.evidence_list:
            exp_id = evidence.exp_id
            date = evidence.timestamp.date()

            grouped[exp_id][date]['count'] += 1
            current_status = grouped[exp_id][date]['status']
            new_status = evidence.status

            if current_status == 'UNKNOWN' or new_status == 'PASS':
                grouped[exp_id][date]['status'] = new_status
            elif current_status != 'PASS' and new_status == 'PARTIAL':
                grouped[exp_id][date]['status'] = new_status

        result = {}
        for exp_id, dates in grouped.items():
            result[exp_id] = [
                (date, data['status'], data['count'])
                for date, data in sorted(dates.items())
            ]

        return result

    def create_figure(self, output_path: Path = None, figsize: tuple = (12, 8)) -> plt.Figure:
        """Create timeline figure."""
        if output_path is None:
            output_path = PUBLICATION_DIR / "fig_experiment_timeline.png"

        grouped = self._group_by_experiment_and_date()

        if not grouped:
            print("No evidence data to visualize")
            return None

        exp_ids = sorted(grouped.keys())
        n_experiments = len(exp_ids)

        fig, ax = plt.subplots(figsize=figsize)

        y_positions = {exp_id: i for i, exp_id in enumerate(exp_ids)}
        all_dates = []

        for exp_id, runs in grouped.items():
            y = y_positions[exp_id]

            for date, status, count in runs:
                all_dates.append(date)
                x = mdates.date2num(date)
                width = 1
                height = min(0.8, 0.2 + 0.1 * count)
                color = self.status_colors.get(status, YRSNColors.PURPLE)

                rect = Rectangle(
                    (x, y - height/2), width, height,
                    facecolor=color, edgecolor='black',
                    linewidth=0.5, alpha=0.8
                )
                ax.add_patch(rect)

        if all_dates:
            min_date = min(all_dates)
            max_date = max(all_dates)
            ax.set_xlim(mdates.date2num(min_date) - 1, mdates.date2num(max_date) + 2)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        ax.set_yticks(list(y_positions.values()))
        ax.set_yticklabels(list(y_positions.keys()), fontsize=9)
        ax.set_ylim(-0.5, n_experiments - 0.5)

        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Experiment ID', fontsize=12)
        ax.set_title('SWARM-01 Experiment Timeline', fontsize=14, fontweight='bold')

        ax.grid(True, axis='x', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

        legend_patches = [
            mpatches.Patch(color=self.status_colors['PASS'], label='Pass'),
            mpatches.Patch(color=self.status_colors['FAIL'], label='Fail'),
            mpatches.Patch(color=self.status_colors['PARTIAL'], label='Partial'),
            mpatches.Patch(color=self.status_colors['UNKNOWN'], label='Unknown')
        ]
        ax.legend(handles=legend_patches, loc='upper right', fontsize=9)

        plt.tight_layout()

        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.savefig(output_path.with_suffix('.pdf'), bbox_inches='tight')
        plt.close()

        print(f"✓ Timeline figure saved: {output_path}")
        print(f"  - {len(exp_ids)} experiments")
        print(f"  - {len(self.evidence_list)} evidence files")

        return fig


# ============================================================================
# HypothesisValidationMatrix (standalone implementation)
# ============================================================================

class HypothesisValidationMatrix:
    """
    Creates heatmap of hypothesis validation matrix.

    Features:
    - Rows: Hypotheses (H1, H2, H3, ...)
    - Columns: Experiments
    - Colors: Green (PASS), Red (FAIL), Gray (NOT_TESTED)
    """

    def __init__(self, hypothesis_matrix: Dict[str, Dict[str, HypothesisResult]]):
        self.hypothesis_matrix = hypothesis_matrix

    def _build_matrix_arrays(self):
        """Build numpy arrays for heatmap."""
        if not self.hypothesis_matrix:
            return None, [], [], []

        hypotheses = sorted(self.hypothesis_matrix.keys(),
                           key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)
        all_experiments = set()
        for experiments in self.hypothesis_matrix.values():
            all_experiments.update(experiments.keys())
        experiments = sorted(all_experiments)

        n_rows = len(hypotheses)
        n_cols = len(experiments)

        data = np.zeros((n_rows, n_cols))
        annotations = [['' for _ in range(n_cols)] for _ in range(n_rows)]

        result_values = {'PASS': 2, 'PARTIAL': 1, 'FAIL': 0, 'NOT_TESTED': -1}

        for i, hyp_id in enumerate(hypotheses):
            for j, exp_id in enumerate(experiments):
                if exp_id in self.hypothesis_matrix[hyp_id]:
                    result = self.hypothesis_matrix[hyp_id][exp_id]
                    data[i, j] = result_values.get(result.result, -1)

                    if result.p_value is not None:
                        if result.p_value < 0.001:
                            annotations[i][j] = '***'
                        elif result.p_value < 0.01:
                            annotations[i][j] = '**'
                        elif result.p_value < 0.05:
                            annotations[i][j] = '*'
                        else:
                            annotations[i][j] = 'ns'
                    elif result.result == 'PASS':
                        annotations[i][j] = '✓'
                    elif result.result == 'FAIL':
                        annotations[i][j] = '✗'
                else:
                    data[i, j] = -1

        return data, hypotheses, experiments, annotations

    def create_figure(self, output_path: Path = None, figsize: tuple = None) -> plt.Figure:
        """Create hypothesis matrix figure."""
        if output_path is None:
            output_path = PUBLICATION_DIR / "fig_hypothesis_matrix.png"

        data, hypotheses, experiments, annotations = self._build_matrix_arrays()

        if data is None or len(hypotheses) == 0:
            print("No hypothesis data to visualize")
            return None

        if figsize is None:
            width = max(8, len(experiments) * 1.5 + 2)
            height = max(6, len(hypotheses) * 0.6 + 2)
            figsize = (width, height)

        fig, ax = plt.subplots(figsize=figsize)

        colors = [YRSNColors.GRAY, YRSNColors.RED, YRSNColors.ORANGE, YRSNColors.GREEN]
        cmap = ListedColormap(colors)

        im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=-1, vmax=2)

        ax.set_xticks(np.arange(len(experiments)))
        ax.set_yticks(np.arange(len(hypotheses)))
        ax.set_xticklabels(experiments, rotation=45, ha='right', fontsize=10)
        ax.set_yticklabels(hypotheses, fontsize=11)

        for i in range(len(hypotheses)):
            for j in range(len(experiments)):
                if annotations[i][j]:
                    ax.text(j, i, annotations[i][j],
                           ha='center', va='center',
                           fontsize=14, fontweight='bold',
                           color='white' if data[i, j] >= 1 else 'black')

        ax.set_xlabel('Experiment ID', fontsize=12)
        ax.set_ylabel('Hypothesis ID', fontsize=12)
        ax.set_title('SWARM-01 Hypothesis Validation Matrix', fontsize=14, fontweight='bold')

        cbar = plt.colorbar(im, ax=ax, ticks=[-1, 0, 1, 2])
        cbar.ax.set_yticklabels(['Not Tested', 'Fail', 'Partial', 'Pass'], fontsize=10)

        ax.set_xticks(np.arange(len(experiments)) - 0.5, minor=True)
        ax.set_yticks(np.arange(len(hypotheses)) - 0.5, minor=True)
        ax.grid(which='minor', color='white', linestyle='-', linewidth=2)

        plt.tight_layout()

        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.savefig(output_path.with_suffix('.pdf'), bbox_inches='tight')
        plt.close()

        total_tests = np.sum(data >= 0)
        pass_count = np.sum(data == 2)

        print(f"✓ Hypothesis matrix saved: {output_path}")
        print(f"  - {len(hypotheses)} hypotheses")
        print(f"  - {len(experiments)} experiments")
        print(f"  - {int(total_tests)} tests ({int(pass_count)} pass)")

        return fig


# ============================================================================
# Load Data
# ============================================================================

def load_evidence_summary() -> List[ExperimentEvidence]:
    """Load evidence summary from aggregated directory."""
    with open(AGGREGATED_DIR / "evidence_summary.json") as f:
        data = json.load(f)

    evidence_list = []
    for item in data:
        ts = item["timestamp"]
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        try:
            timestamp = datetime.fromisoformat(ts)
        except ValueError:
            timestamp = datetime.now()

        evidence_list.append(ExperimentEvidence(
            exp_id=item["exp_id"],
            file_path=item["file_path"],
            timestamp=timestamp,
            claims=item["claims"],
            status=item["status"],
            schema_type=item["schema_type"],
            metadata=item["metadata"]
        ))

    return evidence_list


def load_hypothesis_db() -> Dict[str, Dict[str, HypothesisResult]]:
    """Load hypothesis database from aggregated directory."""
    with open(AGGREGATED_DIR / "hypothesis_db.json") as f:
        data = json.load(f)

    matrix = {}
    for h_id, experiments in data.items():
        matrix[h_id] = {}
        for exp_id, result in experiments.items():
            matrix[h_id][exp_id] = HypothesisResult(
                hypothesis_id=result["hypothesis_id"],
                exp_id=result["exp_id"],
                result=result["result"],
                metric_value=result.get("metric_value"),
                p_value=result.get("p_value")
            )

    return matrix


# ============================================================================
# Main
# ============================================================================

def main():
    print("\n" + "="*60)
    print("  SWARM-01 yrsn-Style Timeline Integration")
    print("="*60 + "\n")

    # Load data
    evidence_list = load_evidence_summary()
    hypothesis_matrix = load_hypothesis_db()

    print(f"  Loaded {len(evidence_list)} evidence entries")
    print(f"  Loaded {len(hypothesis_matrix)} hypotheses")

    # Create ExperimentTimeline
    print("\n  Creating ExperimentTimeline...")
    timeline = ExperimentTimeline(evidence_list)
    timeline.create_figure(output_path=PUBLICATION_DIR / "fig_experiment_timeline.png")

    # Create HypothesisValidationMatrix
    print("\n  Creating HypothesisValidationMatrix...")
    matrix_viz = HypothesisValidationMatrix(hypothesis_matrix)
    matrix_viz.create_figure(output_path=PUBLICATION_DIR / "fig_hypothesis_matrix.png")

    print("\n" + "="*60)
    print("  Integration complete!")
    print("="*60)
    print(f"\n  Output directory: {PUBLICATION_DIR}")
    print("\n  Files created:")
    for f in PUBLICATION_DIR.glob("*.png"):
        print(f"    - {f.name}")


if __name__ == "__main__":
    main()
