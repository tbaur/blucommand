# Contributing to Blucommand

Thank you for your interest in contributing to Blucommand! This document provides guidelines and instructions for contributing.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/tbaur/blucommand/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - macOS version and Python version
   - Relevant error messages or logs

### Suggesting Features

1. Check [Issues](https://github.com/tbaur/blucommand/issues) for existing proposals
2. Open a new issue with:
   - Clear description of the feature
   - Use case and motivation
   - Potential implementation approach (if you have ideas)

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes**:
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed
   - Ensure all tests pass
4. **Commit / PR title**: Use [Conventional Commits](https://www.conventionalcommits.org)
5. **Push to your fork**: `git push origin feature/your-feature-name`
6. **Open a Pull Request**: Provide a clear description of changes

#### Commit / PR titles

PR titles drive automated releases via release-please:

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `test:` — Test changes
- `refactor:` — Code refactoring
- `chore:` / `ci:` — Maintenance (no release)

Example: `feat: add group volume command`

> `CHANGELOG.md` is generated automatically by release-please from your
> Conventional Commit / PR titles — do not edit it by hand for routine
> releases. See [RELEASING.md](RELEASING.md).

#### PR checklist

- [ ] Tests added/updated
- [ ] Tests pass (`pytest`)
- [ ] Documentation updated if needed
- [ ] Descriptive PR title (Conventional Commits)

## Development Setup

### Prerequisites

- Python 3.10+
- macOS (for testing)
- Git

### Setup

```bash
# Clone your fork
git clone git@github.com:YOUR_USERNAME/blucommand.git
cd blucommand

# Run installation script
./install.sh

# Install test dependencies
pip install -r requirements-test.txt
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_validators.py -v
```

### Code Style

- Follow PEP 8 style guidelines
- Use type hints for all functions
- Add docstrings to all public functions
- Keep functions focused and small
- Use descriptive variable names

### Test Requirements

- New features must include tests
- Aim for high test coverage (currently 82%)
- Tests should be fast and isolated
- Use mocking for external dependencies

## Project Structure

```
blucommand/
├── main.py              # Entry point
├── constants.py         # Constants
├── models.py            # Data models
├── validators.py        # Input validation
├── config.py            # Configuration
├── network.py           # Network I/O
├── utils.py             # Utilities
├── controller.py        # Core logic
├── cli.py               # CLI interface
├── lsdp.py              # LSDP discovery
├── tests/               # Test suite
└── docs/                # Documentation
```

## Areas for Contribution

### High Priority

- **Cross-platform support**: Windows and Linux implementations
- **Additional discovery methods**: Alternative to mDNS/LSDP
- **Performance improvements**: Faster discovery, better caching
- **Documentation**: Examples, tutorials, video guides

### Medium Priority

- **New features**: Open an issue to discuss ideas
- **Test coverage**: Increase coverage in specific areas
- **Error handling**: Better error messages and recovery
- **Logging**: Enhanced structured logging features

### Low Priority

- **UI improvements**: Better CLI output formatting
- **Code refactoring**: Cleanup and optimization
- **Documentation**: Additional examples and use cases

## Code Review Process

1. All PRs require review before merging
2. Maintainers will review for:
   - Code quality and style
   - Test coverage
   - Documentation updates
   - Backward compatibility
3. Address feedback promptly
4. Squash commits if requested

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0, the same license as the project.

## Questions?

- Open an issue for discussion
- Check existing documentation in `docs/`
- Review [README.md](README.md) for project overview
- Review [SECURITY.md](SECURITY.md) for security policy

Thank you for contributing.

