# Contributing to Swarm-It API

Thank you for your interest in contributing to the Swarm-It platform!

## License Agreement

By contributing to this repository, you agree that:

1. **Your contributions are licensed under Apache License 2.0**
   - Same license as the project (see [LICENSE](LICENSE))
   - Grants perpetual, worldwide, royalty-free copyright license

2. **Patent Grant**
   - You grant Next Shift Consulting LLC a patent license for any patents covering your contributions
   - This allows us to use your contributions in both open source and commercial offerings

3. **Right to Contribute**
   - You have the legal right to make these contributions
   - No conflicting obligations (employer IP agreements, etc.)
   - You have not knowingly included third-party patented technology without disclosure

4. **Commercial Use Rights**
   - You grant Next Shift Consulting LLC the right to use your contributions in commercial licenses
   - This allows us to offer commercial support and licensing while keeping the base project open source

## What This Means

- ✓ Your contributions remain open source (Apache 2.0)
- ✓ You retain copyright to your contributions
- ✓ Next Shift Consulting can use your contributions commercially
- ✓ You can use your own contributions however you like
- ✓ Everyone benefits from your improvements

## How to Contribute

### 1. Fork and Clone

```bash
git clone https://github.com/NextShiftConsulting/swarm-it-api.git
cd swarm-it-api
```

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 3. Make Your Changes

- Follow existing code style
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

### 4. Commit Your Changes

```bash
git add .
git commit -m "Add feature: brief description"
```

**Important**: Do not include Claude attribution per CLAUDE.md project instructions.

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Code Review Process

1. **Automated Checks**
   - CI/CD pipeline runs tests
   - Pre-commit hooks check for credentials
   - Code style validation

2. **Manual Review**
   - Maintainers review code quality
   - Check for security issues
   - Verify patent/IP compliance

3. **Merge**
   - Once approved, maintainers will merge
   - Your contribution is now part of the project!

## Contribution Guidelines

### Code Style

- **Python**: Follow PEP 8
- **Type hints**: Use for function signatures
- **Docstrings**: Required for public APIs
- **Comments**: Explain "why", not "what"

### Testing

- Write unit tests for new code
- Ensure integration tests pass
- Aim for >80% code coverage

### Documentation

- Update README if changing user-facing features
- Add inline comments for complex logic
- Update API documentation

### Security

- Never commit credentials or secrets
- Follow secure coding practices
- Report security issues privately to security@nextshiftconsulting.com

## Patent and IP Considerations

### What You Can Contribute

✓ Bug fixes and improvements
✓ New features and functionality
✓ Documentation and examples
✓ Tests and tooling

### What Requires Disclosure

If your contribution includes:
- Implementation of a third-party patent
- Algorithms from published papers (cite the paper)
- Code based on existing libraries (mention the source)

Please disclose this in your pull request description.

### RSCT Patent

The core RSCT (Representation-Space Compatibility Theory) algorithms are patent-pending by Next Shift Consulting LLC. You don't need to worry about this for contributions - we handle the patent licensing.

## Types of Contributions

### 🐛 Bug Reports

Create an issue with:
- Description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Python version, etc.)

### 💡 Feature Requests

Create an issue with:
- Problem you're trying to solve
- Proposed solution
- Alternative solutions considered
- Impact on existing functionality

### 📝 Documentation

- Fix typos
- Clarify confusing sections
- Add examples
- Improve API documentation

### 🧪 Tests

- Increase test coverage
- Add edge case tests
- Improve test performance

## Community Guidelines

- Be respectful and inclusive
- Provide constructive feedback
- Help others learn and grow
- Follow our [Code of Conduct](CODE_OF_CONDUCT.md)

## Questions?

- **General questions**: Open a GitHub Discussion
- **Bug reports**: Create an issue
- **Commercial licensing**: legal@nextshiftconsulting.com
- **Security issues**: security@nextshiftconsulting.com

## Contributor License Agreement (CLA)

For significant contributions (>100 lines), we may ask you to sign a formal CLA. This:

- Confirms you have the right to contribute
- Grants necessary patent and copyright licenses
- Protects both you and the project

We'll notify you if a CLA is required for your contribution.

---

Thank you for contributing to Swarm-It! 🚀

© 2026 Next Shift Consulting LLC
