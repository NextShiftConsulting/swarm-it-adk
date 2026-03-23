# Pull Request Description

## Summary

<!-- Briefly describe what this PR does and why -->

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Test coverage improvement

## Related Issues

<!-- Link to related issues: Fixes #123, Relates to #456 -->

---

## Testing Checklist

- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Manual testing completed
- [ ] Edge cases considered and tested

---

## P18 Checklist: Hardware Compression Path Protection

<!-- Only required if this PR modifies dimension-related code, projection layer, or Profile B -->

**Does this PR affect any of the following?**

- [ ] Dimension contract (`config/dimension_contract.yaml`)
- [ ] Projection layer (`swarm_it/projection.py`)
- [ ] Profile B (hardware compression) code path
- [ ] Rotor checkpoints or loading logic
- [ ] Embedding dimension handling (1024-dim, 64-dim)
- [ ] Multimodal dimension alignment

**If YES to any above, complete P18 compliance checklist:**

### Architecture Review

- [ ] Architecture team reviewed hardware impact
- [ ] Hardware team confirmed feasibility (if Profile B affected)
- [ ] Clear justification for dimension-related changes provided

### Checkpoint and Contract

- [ ] Dimension contract updated if dimensions changed
- [ ] New projection checkpoint trained if dimension changed
- [ ] Checkpoint metadata includes training date, validation metrics
- [ ] Change control section in contract updated

### Validation

- [ ] Certificate quality validated with new checkpoint (if applicable)
- [ ] All P18 tests pass:
  - [ ] `test_projection_dimensions_match_contract`
  - [ ] `test_projection_checkpoint_exists`
  - [ ] `test_certificate_quality_at_64d`
  - [ ] `test_multimodal_dimension_alignment`
- [ ] Startup validation tested for Profile B
- [ ] Drift monitoring configured for new dimension (if applicable)

### Documentation

- [ ] `WHY_64_DIM.md` updated if rationale changed
- [ ] `ADR_HARDWARE_COMPRESSION_PROFILES.md` updated if profiles changed
- [ ] PRINCIPLE 18 in First Principles reviewed for accuracy
- [ ] Comments explain why dimension choices were made

### Prohibited Changes Check

**STOP: Do NOT proceed if this PR:**

- [ ] ❌ Removes projection layer without architecture + hardware + exec approval
- [ ] ❌ Changes dimension contract without required approvals
- [ ] ❌ Adds identity or random fallback in production
- [ ] ❌ Bypasses dimension contract in runtime path
- [ ] ❌ Removes Profile B without executive sign-off

**If any ❌ checked above, this PR requires elevated approval process.**

---

## Documentation

- [ ] README updated (if needed)
- [ ] Docstrings added/updated for public APIs
- [ ] Architecture docs updated (if applicable)
- [ ] Migration guide included (for breaking changes)

---

## Code Quality

- [ ] Code follows project style guidelines
- [ ] No unnecessary code duplication
- [ ] Complex logic is commented and explained
- [ ] Security considerations addressed
- [ ] Error handling is appropriate

---

## Deployment Considerations

- [ ] Backward compatible (or migration plan provided)
- [ ] No hardcoded values or credentials
- [ ] Environment variables documented
- [ ] Database migrations included (if needed)
- [ ] Performance impact assessed

---

## Additional Notes

<!-- Any additional context, screenshots, benchmarks, or considerations -->

---

## Reviewer Guidance

**For reviewers, please verify:**

1. **If P18-related**: All P18 checklist items completed
2. **Tests**: New functionality has test coverage
3. **Documentation**: Changes are documented appropriately
4. **Security**: No credentials or sensitive data exposed
5. **Performance**: No obvious performance regressions
6. **Backward compatibility**: Existing systems won't break

**Special attention for dimension-related PRs:**

- Verify dimension contract changes have proper approvals
- Check that projection checkpoint exists and is validated
- Ensure P18 tests pass in CI
- Confirm hardware team signed off (if Profile B affected)

---

## Post-Merge Actions

<!-- Check if any of these apply after merge -->

- [ ] Announce breaking changes to team
- [ ] Update deployment runbook
- [ ] Schedule production deployment
- [ ] Monitor metrics after deployment
- [ ] Update related repositories (if applicable)
