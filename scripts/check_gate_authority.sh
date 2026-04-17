#!/usr/bin/env bash
# scripts/check_gate_authority.sh
#
# Gate authority guardrail (ADR-004).
# Catches NEW inline gate logic that reimplements what should be in
# yrsn-controlplane. Does NOT flag delegating methods or enum usage.
#
# Inline tag '# APPROVED_BRIDGE' suppresses a line.
#
# Usage: REPO_NAME=swarm-it-api bash scripts/check_gate_authority.sh

set -euo pipefail

REPO_NAME="${REPO_NAME:-$(basename "$(git rev-parse --show-toplevel)")}"

# Patterns indicating inline gate COMPUTATION (not delegation or enum usage).
# These catch reimplemented Oobleck formulas, hardcoded noise thresholds,
# and inline decision assignments from threshold comparisons.
GATE_PATTERNS=(
  # Oobleck formula reimplementation
  'kappa_base\s*\+\s*.*lambda.*sigma'
  'kappa_req\s*=\s*0\.[0-9].*\+.*0\.[0-9].*\*\s*sigma'
  # Hardcoded noise threshold producing a decision
  'if\s+N\s*>=?\s*0\.[45].*:.*return.*REJECT'
  'if\s+N\s*>=?\s*0\.[45].*:.*return.*BLOCK'
  # Hardcoded coherence producing a decision
  'if\s+coherence\s*<.*:.*return.*BLOCK'
  # Hardcoded kappa producing a decision
  'if\s+kappa\s*<\s*kappa_req.*:.*return.*RE_ENCODE'
  'if\s+kappa\s*<\s*0\.[0-9].*:.*return.*REPAIR'
)

# Directories that are ALLOWED
ALLOWED_DIRS=(
  "yrsn_controlplane"
  "src/yrsn/controlplane"
  "tests"
  "test"
  ".pytest_cache"
  "__pycache__"
  "experiments"
  "clients"
  "analysis"
  "docs"
  "dashboard"
  "examples"
  "agents"
  "archive"
)

# Build grep exclude args
EXCLUDES=()
for d in "${ALLOWED_DIRS[@]}"; do
  EXCLUDES+=("--exclude-dir=$d")
done
EXCLUDES+=(
  "--exclude=check_gate_authority.sh"
  "--exclude=*.md"
  "--exclude=*.txt"
  "--exclude=*.yml"
  "--exclude=*.yaml"
  "--exclude=*.json"
  "--exclude=*.toml"
)

echo "[$REPO_NAME] Checking gate authority (ADR-004)..."

VIOLATIONS=""
for pattern in "${GATE_PATTERNS[@]}"; do
  hits=$(grep -rEn "$pattern" \
    "${EXCLUDES[@]}" \
    --include="*.py" \
    . 2>/dev/null \
    | grep -v "# APPROVED_BRIDGE" \
    | grep -v "_controlplane_compat" \
    | grep -v "^Binary" \
    | grep -v "^\./test_" \
    | grep -Ev ":[[:space:]]*#" || true)
  if [ -n "$hits" ]; then
    VIOLATIONS+="$hits"$'\n'
  fi
done

if [ -n "$VIOLATIONS" ]; then
  echo ""
  echo "================================================================"
  echo "  GATE AUTHORITY VIOLATION in [$REPO_NAME]"
  echo "  Inline gate logic detected outside yrsn-controlplane."
  echo "  Delegate to SequentialGatekeeper.evaluate() instead."
  echo "  See ADR-004."
  echo "================================================================"
  echo "$VIOLATIONS"
  exit 1
fi

echo "[$REPO_NAME] Gate authority check passed."
exit 0
