# Contributing to MemoryMesh

Thank you for your interest in contributing to MemoryMesh. This is an open project built to serve humanity by making AI memory accessible, free, and simple. Every contribution -- whether it is a bug fix, a feature, documentation, or a thoughtful issue report -- helps move that mission forward.

---

## Getting Started

### Prerequisites

- Python 3.9 or later
- Git

### Setting Up the Development Environment

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/YOUR_USERNAME/memorymesh.git
   cd memorymesh
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in development mode with all dependencies:**

   ```bash
   pip install -e ".[dev,all]"
   ```

   Or use the Makefile shortcut:

   ```bash
   make install
   ```

4. **Verify everything works:**

   ```bash
   make all   # Runs lint + tests + type checking
   ```

---

## Code Style

We use **ruff** for both linting and formatting. The configuration is in `pyproject.toml`.

### Requirements

- **Type hints** are required on all public functions and methods.
- **Docstrings** are required on all public classes, methods, and functions. Use Google-style docstrings.
- **No wildcard imports.** Always import specific names.
- **Prefer dataclasses** over plain dictionaries for structured data.

### Running the Linter and Formatter

```bash
make lint      # Check for issues
make format    # Auto-fix formatting
make typecheck # Run mypy
```

Please ensure `make lint` and `make typecheck` pass before submitting a pull request.

---

## Testing

We use **pytest** for all testing.

```bash
make test              # Run the full test suite
pytest tests/ -x       # Stop on first failure
pytest tests/ -v       # Verbose output
pytest tests/ -k name  # Run tests matching a pattern
```

### Testing Guidelines

- All new features must include tests.
- All bug fixes must include a regression test.
- Tests should be fast. Avoid network calls in unit tests; mock external services.
- Place tests in the `tests/` directory, mirroring the source structure.

---

## Pull Request Process

1. **Fork** the repository and create a new branch from `main`:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes.** Keep commits focused and atomic.

3. **Run the full check suite:**

   ```bash
   make all
   ```

4. **Push your branch** and open a pull request against `main`.

5. **Fill out the PR template.** Describe what changed, why, and how to test it.

6. **Respond to review feedback.** We aim to review all PRs within a few days.

### PR Checklist

- [ ] Code follows the project style guidelines
- [ ] Type hints are included for all public APIs
- [ ] Docstrings are included for all public APIs
- [ ] Tests are added or updated
- [ ] `make lint` passes
- [ ] `make typecheck` passes
- [ ] `make test` passes
- [ ] Documentation is updated if needed

---

## Reporting Issues

We use GitHub Issues for tracking bugs and feature requests.

### Bug Reports

Use the **Bug Report** issue template. Include:

- A clear description of the problem
- Steps to reproduce
- Expected vs. actual behavior
- Your environment (OS, Python version, MemoryMesh version, embedding provider)

### Feature Requests

Use the **Feature Request** issue template. Include:

- A description of the feature
- The use case it addresses
- A proposed solution (if you have one)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you agree to uphold a welcoming, inclusive, and respectful environment for everyone.

We have zero tolerance for harassment, discrimination, or disrespectful behavior. If you experience or witness unacceptable behavior, please report it by opening an issue or contacting the maintainers directly.

---

## Questions?

If you have questions about contributing, feel free to open a discussion on GitHub or reach out by filing an issue. We are happy to help you get started.

Thank you for helping build the future of open AI memory.
