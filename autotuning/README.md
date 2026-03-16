# AutoTuning Framework

This directory contains the **shared infrastructure** for autotuning experiments.

Each experiment gets its own autoloop configuration because **metrics are problem-specific**.

## Structure

```
swarm-it-adk/
├── autotuning/                    # Shared framework
│   ├── README.md                  # This file
│   ├── base_evaluate.py           # Base evaluator class
│   └── templates/                 # Starter templates
│       ├── thresholds.yaml
│       ├── evaluate.py
│       └── program.md
│
└── experiments/
    ├── SWARM-05/
    │   └── autoloop/              # SWARM-05 specific
    │       ├── thresholds.yaml    # MUTABLE
    │       ├── evaluate.py        # Experiment-specific metric
    │       ├── program.md         # Experiment-specific instructions
    │       └── results.tsv        # Experiment log
    │
    └── SWARM-06/
        └── autoloop/              # SWARM-06 specific (different metric)
            └── ...
```

## Why Per-Experiment?

| Experiment | Metric | Threshold Surface |
|------------|--------|-------------------|
| SWARM-05 H13 | FNR reduction | conflict_memory, propagation_decay |
| SWARM-05 H14 | F1 hallucination | token_importance_method, aggregation |
| SWARM-05 H16 | Accuracy | domain, calibration_method |

Different problems → different metrics → different mutable surfaces.

## Usage

1. Copy templates to your experiment's `autoloop/` directory
2. Customize `evaluate.py` for your metric
3. Customize `thresholds.yaml` for your mutable surface
4. Run the autoloop via `swarm-doe autoloop SWARM-XX`
