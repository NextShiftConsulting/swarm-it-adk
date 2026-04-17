#!/usr/bin/env bash
# scripts/pre_release_check.sh
#
# Coordinated release validation for gate authority (ADR-004).
# Run before cutting any coordinated release tag across repos.
#
# Usage: bash scripts/pre_release_check.sh

set -uo pipefail

PASS=0
FAIL=0
SKIP=0

pass() { echo "  [$1] ... PASS"; ((PASS++)); }
fail() { echo "  [$1] ... FAIL"; ((FAIL++)); }
skip() { echo "  [$1] ... SKIP ($2)"; ((SKIP++)); }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GITHUB_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo ""
echo "================================================================"
echo "  Pre-Release Gate Authority Audit (ADR-004)"
echo "================================================================"
echo ""

# 1. Gate authority clean in consumer repos
echo "Gate authority checks:"
for repo in swarm-it-api swarm-it-adk; do
  rp="$GITHUB_ROOT/$repo"
  if [ -d "$rp" ] && [ -f "$rp/scripts/check_gate_authority.sh" ]; then
    if (cd "$rp" && REPO_NAME=$repo bash scripts/check_gate_authority.sh > /dev/null 2>&1); then
      pass "gate-authority: $repo"
    else
      fail "gate-authority: $repo"
    fi
  else
    skip "gate-authority: $repo" "not found"
  fi
done
echo ""

# 2. yrsn bridge importable
echo "Bridge checks:"
if python -c 'from yrsn.controlplane import SequentialGatekeeper, EnforcementDecision' 2>/dev/null; then
  pass "yrsn.controlplane bridge"
else
  fail "yrsn.controlplane bridge"
fi
echo ""

# 3. No local EnforcementDecision in consumer repos
echo "No local EnforcementDecision definitions:"
for repo in swarm-it-api swarm-it-adk; do
  rp="$GITHUB_ROOT/$repo"
  if [ -d "$rp" ]; then
    if grep -rn 'class EnforcementDecision' "$rp" --include='*.py' 2>/dev/null | grep -qv __pycache__; then
      fail "$repo: local EnforcementDecision found"
    else
      pass "$repo: no local EnforcementDecision"
    fi
  else
    skip "$repo" "not found"
  fi
done
echo ""

# 4. Test suites
echo "Test suites:"
cp="$GITHUB_ROOT/yrsn-controlplane"
if [ -d "$cp" ]; then
  if (cd "$cp" && python -m pytest tests/ -q --tb=no > /dev/null 2>&1); then
    pass "yrsn-controlplane tests"
  else
    fail "yrsn-controlplane tests"
  fi
else
  skip "yrsn-controlplane tests" "not found"
fi

api="$GITHUB_ROOT/swarm-it-api"
if [ -d "$api" ]; then
  if (cd "$api" && python -m pytest tests/test_engine.py -q --tb=no > /dev/null 2>&1); then
    pass "swarm-it-api engine tests"
  else
    fail "swarm-it-api engine tests"
  fi
else
  skip "swarm-it-api engine tests" "not found"
fi
echo ""

# 5. ADR-004 present
echo "ADR-004 present:"
for repo in yrsn yrsn-controlplane swarm-it-api swarm-it-adk; do
  rp="$GITHUB_ROOT/$repo"
  if [ -d "$rp" ]; then
    if find "$rp/docs" -name "*ADR*004*" -o -name "*CONTROLPLANE*GATE*" 2>/dev/null | grep -q .; then
      pass "ADR-004: $repo"
    else
      fail "ADR-004: $repo"
    fi
  else
    skip "ADR-004: $repo" "not found"
  fi
done
echo ""

# Summary
echo "================================================================"
echo "  Results: $PASS passed, $FAIL failed, $SKIP skipped"
echo "================================================================"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "Release BLOCKED. Fix failures before tagging."
  exit 1
fi

echo "All checks passed. Release is clear."
exit 0
