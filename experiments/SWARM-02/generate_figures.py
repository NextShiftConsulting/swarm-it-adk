#!/usr/bin/env python3
"""
SWARM-02: Easy-to-understand visualizations for capacity expansion findings.

Generates four key graphs:
1. κ scales linearly with expansion factor k
2. Threshold crossing: choked → viable
3. Accuracy improvement when κ crosses 50
4. Sweet spot visualization (k comparison)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

# Create output directory
output_dir = Path(__file__).parent / "results" / "figures"
output_dir.mkdir(parents=True, exist_ok=True)

# Set style for clean, readable graphs
try:
    plt.style.use('seaborn-whitegrid')
except OSError:
    plt.style.use('ggplot')
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['font.size'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12


def fig1_kappa_scales_linearly():
    """Graph 1: κ scales linearly with expansion factor k"""

    fig, ax = plt.subplots(figsize=(10, 6))

    # Data from H1 evidence
    data = {
        'rank=3 (κ₀=23)': {'k': [1, 2, 3, 4], 'kappa': [23.16, 46.32, 69.47, 92.63]},
        'rank=5 (κ₀=16)': {'k': [1, 2, 3, 4], 'kappa': [15.53, 31.06, 46.59, 62.12]},
        'rank=8 (κ₀=12)': {'k': [1, 2, 3, 4], 'kappa': [11.76, 23.53, 35.29, 47.05]},
        'rank=12 (κ₀=10)': {'k': [1, 2, 3, 4], 'kappa': [9.66, 19.31, 28.97, 38.63]},
    }

    colors = ['#2ecc71', '#3498db', '#9b59b6', '#e74c3c']
    markers = ['o', 's', '^', 'D']

    for (label, vals), color, marker in zip(data.items(), colors, markers):
        ax.plot(vals['k'], vals['kappa'], marker=marker, markersize=10,
                linewidth=2.5, label=label, color=color)

    # Add threshold line
    ax.axhline(y=50, color='#e74c3c', linestyle='--', linewidth=2, alpha=0.7, label='κ ≥ 50 threshold')

    # Fill sweet spot region
    ax.axhspan(50, 80, alpha=0.15, color='green', label='Sweet spot (50-80)')

    ax.set_xlabel('Expansion Factor (k)', fontweight='bold')
    ax.set_ylabel('Over-parameterization Ratio (κ)', fontweight='bold')
    ax.set_title('κ Scales Linearly with Expansion Factor k', fontweight='bold', fontsize=16)
    ax.set_xticks([1, 2, 3, 4])
    ax.legend(loc='upper left', framealpha=0.95)
    ax.set_ylim(0, 100)

    plt.tight_layout()
    plt.savefig(output_dir / 'fig1_kappa_scales_linearly.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved fig1_kappa_scales_linearly.png")


def fig2_threshold_crossing():
    """Graph 2: Before/After expansion - threshold crossing"""

    fig, ax = plt.subplots(figsize=(10, 6))

    # Data from H2 evidence
    scenarios = ['Scenario 1', 'Scenario 2', 'Scenario 3', 'Scenario 4', 'Scenario 5', 'Scenario 6']
    kappa_before = [26.25, 33.5, 33.11, 35.63, 35.44, 33.71]
    kappa_after = [52.5, 67.01, 66.22, 71.25, 70.89, 67.42]

    x = np.arange(len(scenarios))
    width = 0.35

    bars1 = ax.bar(x - width/2, kappa_before, width, label='Before (k=1)', color='#e74c3c', alpha=0.8)
    bars2 = ax.bar(x + width/2, kappa_after, width, label='After (k=2)', color='#2ecc71', alpha=0.8)

    # Threshold line
    ax.axhline(y=50, color='#2c3e50', linestyle='--', linewidth=2.5, label='κ ≥ 50 threshold')

    # Add "CHOKED" and "VIABLE" labels
    for i, (before, after) in enumerate(zip(kappa_before, kappa_after)):
        ax.annotate('CHOKED', (i - width/2, before + 1), ha='center', fontsize=8, color='#c0392b', fontweight='bold')
        ax.annotate('VIABLE', (i + width/2, after + 1), ha='center', fontsize=8, color='#27ae60', fontweight='bold')

    ax.set_xlabel('Test Scenario', fontweight='bold')
    ax.set_ylabel('Over-parameterization Ratio (κ)', fontweight='bold')
    ax.set_title('Expansion Enables Threshold Crossing (κ < 50 → κ ≥ 50)', fontweight='bold', fontsize=16)
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios)
    ax.legend(loc='upper right', framealpha=0.95)
    ax.set_ylim(0, 85)

    plt.tight_layout()
    plt.savefig(output_dir / 'fig2_threshold_crossing.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved fig2_threshold_crossing.png")


def fig3_accuracy_improvement():
    """Graph 3: Accuracy improves when κ crosses threshold"""

    fig, ax = plt.subplots(figsize=(10, 6))

    # Data from H3 evidence
    cases = ['rank=3\n(k=3)', 'rank=5\n(k=3)', 'rank=8\n(k=5)', 'rank=12\n(k=5)']
    acc_before = [79.8, 84.0, 80.8, 79.4]
    acc_after = [90.0, 91.4, 93.4, 93.2]
    improvement = [12.8, 8.8, 15.6, 17.4]

    x = np.arange(len(cases))
    width = 0.35

    bars1 = ax.bar(x - width/2, acc_before, width, label='Before expansion', color='#e74c3c', alpha=0.8)
    bars2 = ax.bar(x + width/2, acc_after, width, label='After expansion', color='#2ecc71', alpha=0.8)

    # Add improvement annotations
    for i, (before, after, imp) in enumerate(zip(acc_before, acc_after, improvement)):
        # Arrow showing improvement
        ax.annotate('', xy=(i + width/2, after - 1), xytext=(i - width/2, before + 1),
                   arrowprops=dict(arrowstyle='->', color='#2c3e50', lw=1.5))
        ax.annotate(f'+{imp}%', (i, (before + after) / 2), ha='center', fontsize=11,
                   fontweight='bold', color='#27ae60')

    ax.set_xlabel('Intrinsic Data Rank (expansion factor used)', fontweight='bold')
    ax.set_ylabel('Classification Accuracy (%)', fontweight='bold')
    ax.set_title('Accuracy Improves 8-17% When κ Crosses Threshold', fontweight='bold', fontsize=16)
    ax.set_xticks(x)
    ax.set_xticklabels(cases)
    ax.legend(loc='lower right', framealpha=0.95)
    ax.set_ylim(70, 100)

    plt.tight_layout()
    plt.savefig(output_dir / 'fig3_accuracy_improvement.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved fig3_accuracy_improvement.png")


def fig4_sweet_spot():
    """Graph 4: Sweet spot visualization - diminishing returns beyond κ≈80"""

    fig, ax = plt.subplots(figsize=(10, 6))

    # Data from H3b evidence (intrinsic_rank=5 case)
    k_values = [1, 2, 3, 4, 5]
    kappa_values = [16.36, 32.71, 49.07, 65.43, 81.78]
    accuracy_values = [86.2, 91.8, 91.0, 90.6, 90.6]

    # Create dual axis
    ax2 = ax.twinx()

    # Plot κ vs k (left axis)
    line1 = ax.plot(k_values, kappa_values, 'o-', color='#3498db', linewidth=2.5,
                    markersize=10, label='κ value')

    # Plot accuracy vs k (right axis)
    line2 = ax2.plot(k_values, accuracy_values, 's-', color='#e74c3c', linewidth=2.5,
                     markersize=10, label='Accuracy')

    # Highlight sweet spot
    ax.axhspan(50, 80, alpha=0.2, color='green')
    ax.axhline(y=50, color='#27ae60', linestyle='--', linewidth=2, alpha=0.7)
    ax.axhline(y=80, color='#27ae60', linestyle='--', linewidth=2, alpha=0.7)

    # Annotate best k
    ax2.annotate('BEST\n(k=2)', xy=(2, 91.8), xytext=(2.5, 93.5),
                arrowprops=dict(arrowstyle='->', color='#c0392b', lw=2),
                fontsize=11, fontweight='bold', color='#c0392b')

    # Sweet spot label
    ax.text(4.5, 65, 'SWEET\nSPOT\n(50-80)', ha='center', va='center',
            fontsize=11, fontweight='bold', color='#27ae60',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    ax.set_xlabel('Expansion Factor (k)', fontweight='bold')
    ax.set_ylabel('Over-parameterization Ratio (κ)', color='#3498db', fontweight='bold')
    ax2.set_ylabel('Accuracy (%)', color='#e74c3c', fontweight='bold')
    ax.set_title('Sweet Spot: κ ≈ 50-80 (Diminishing Returns Beyond)', fontweight='bold', fontsize=16)
    ax.set_xticks(k_values)

    # Combined legend
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax.legend(lines, labels, loc='center right', framealpha=0.95)

    ax.set_ylim(0, 100)
    ax2.set_ylim(80, 95)
    ax.tick_params(axis='y', labelcolor='#3498db')
    ax2.tick_params(axis='y', labelcolor='#e74c3c')

    plt.tight_layout()
    plt.savefig(output_dir / 'fig4_sweet_spot.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved fig4_sweet_spot.png")


def fig5_summary_formula():
    """Graph 5: Visual summary of the practical formula"""

    fig, ax = plt.subplots(figsize=(10, 6))

    # Create a flowchart-style summary
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(5, 7.5, 'Practical Formula for Optimal Expansion',
            ha='center', va='center', fontsize=18, fontweight='bold')

    # Main formula box
    formula_box = mpatches.FancyBboxPatch((1.5, 4.5), 7, 2, boxstyle='round,pad=0.1',
                                          facecolor='#ecf0f1', edgecolor='#2c3e50', linewidth=2)
    ax.add_patch(formula_box)
    ax.text(5, 5.5, r'$k = \min\left(\lceil \frac{65}{\kappa_{current}} \rceil, 5\right)$',
            ha='center', va='center', fontsize=24, fontweight='bold')

    # Explanation boxes
    boxes = [
        (1, 2.5, 2.5, 1.5, 'If κ < 50:\nExpand!', '#e74c3c'),
        (4, 2.5, 2.5, 1.5, 'Target:\nκ ≈ 65', '#27ae60'),
        (7, 2.5, 2.5, 1.5, 'Cap:\nk ≤ 5', '#3498db'),
    ]

    for x, y, w, h, text, color in boxes:
        box = mpatches.FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.05',
                                      facecolor=color, edgecolor='#2c3e50',
                                      linewidth=1.5, alpha=0.8)
        ax.add_patch(box)
        ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                fontsize=12, fontweight='bold', color='white')

    # Example calculation
    ax.text(5, 1, 'Example: κ=17 → k = min(ceil(65/17), 5) = min(4, 5) = 4',
            ha='center', va='center', fontsize=12,
            bbox=dict(boxstyle='round', facecolor='#fff9c4', edgecolor='#f9a825', linewidth=1.5))

    plt.tight_layout()
    plt.savefig(output_dir / 'fig5_summary_formula.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Saved fig5_summary_formula.png")


if __name__ == '__main__':
    print("\n=== Generating SWARM-02 Figures ===\n")

    fig1_kappa_scales_linearly()
    fig2_threshold_crossing()
    fig3_accuracy_improvement()
    fig4_sweet_spot()
    fig5_summary_formula()

    print(f"\n✅ All figures saved to: {output_dir.absolute()}\n")
