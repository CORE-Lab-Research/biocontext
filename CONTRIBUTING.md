# Contributing to BioContext

Thank you for your interest in contributing to BioContext! We welcome contributions from researchers, bioinformaticians, and software engineers.

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating in our community.

---

## Getting Started

### Prerequisites
- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) (recommended fast package installer and resolver) or `pip`
- Git

### Development Setup

1. Fork the repository on GitHub and clone your fork:
   ```bash
   git clone https://github.com/<your-username>/biocontext.git
   cd biocontext
   ```

2. Add the upstream repository remote:
   ```bash
   git remote add upstream https://github.com/CORE-Lab-Research/biocontext.git
   ```

3. Create a virtual environment and install dependencies:
   ```bash
   uv venv
   source .venv/bin/activate
   uv sync
   ```

---

## Development Workflow

### Branching Strategy
- Always create a descriptive topic branch from `main`:
  ```bash
  git checkout -b feat/add-worm-adapter
  # or
  git checkout -b fix/timeout-handling
  ```
- Keep branches focused on a single logical change or deliverable.

### Coding Standards
- **Python**: Follow PEP 8 style guidelines.
- **Type Annotations**: BioContext relies heavily on Pydantic v2 schemas; provide explicit type annotations for function signatures.
- **Language**: All code, docstrings, variable names, log messages, and commit messages must be in clear, professional English.
- **Scientific Integrity**:
  - Never fabricate numbers, sample distributions, or biological facts.
  - Never substitute missing real-world data with synthetic mock distributions without prominent explicit labeling.

---

## Testing & Quality Assurance

All contributions must pass existing tests and include tests for new functionality.

1. **Run the full test suite**:
   ```bash
   uv run pytest
   ```

2. **Run specific test suites**:
   ```bash
   # Resolver unit tests
   uv run pytest tests/test_resolver.py -v

   # FastMCP server integration tests
   uv run pytest tests/test_server.py -v

   # Accuracy benchmark suite (26 curated cases)
   uv run pytest tests/test_benchmark.py -v
   ```

3. **Verify CLI**:
   ```bash
   uv run biocontext --help
   uv run biocontext resolve TP53
   uv run biocontext mouse Trp53
   ```

---

## Commit Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) convention:

- `feat(scope): add new feature or adapter`
- `fix(scope): fix bug or error handling`
- `docs: update documentation or README`
- `test: add or update test suites`
- `refactor: code changes without altering external behavior`

**Example**:
```text
feat(adapters): add RatAdapter for Rattus norvegicus resolution

- Implement RGD/Alliance API client for taxon 10116
- Map rgd_id into GeneEntity schema
- Add unit and benchmark tests
```

---

## Pull Request Process

1. Ensure all tests pass locally (`uv run pytest`).
2. Push your topic branch to your fork:
   ```bash
   git push origin feat/your-feature-name
   ```
3. Open a Pull Request against the `main` branch of `CORE-Lab-Research/biocontext`.
4. Fill out the PR template describing the purpose of the change, test results, and any relevant issue references (e.g., `Closes #4`).
5. A project maintainer will review your PR and provide constructive feedback.

---

## Reporting Issues & Security

- **Bug Reports & Feature Requests**: Use the [GitHub Issues](https://github.com/CORE-Lab-Research/biocontext/issues) tracker.
- **Security Vulnerabilities**: Report privately to `research@engkinandatama.my.id`.
