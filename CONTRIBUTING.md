# Contributing to BioContext

Thank you for your interest in contributing to BioContext! We welcome contributions from researchers, bioinformaticians, and software engineers.

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) and [Security Policy](SECURITY.md) before participating in our community.

---

## Getting Started

### Prerequisites
- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) (recommended package installer and resolver) or `pip`
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

3. Create a virtual environment and install dependencies with development tools:
   ```bash
   uv sync
   ```

---

## Architecture & Code Organization

```
src/biocontext/
├── base.py       # BaseBioAdapter abstract class, SQLiteCache, AsyncRateLimiter
├── config.py     # ClientConfig, RateLimitConfig, CLI_COMMANDS_REGISTRY
├── schemas.py    # Pydantic v2 domain models (GeneEntity, ProteinEntity, GOAnnotation, PathwayContext)
├── adapters.py   # Database adapters (HGNC, NCBI, UniProt, Ensembl, MGI, QuickGO, Reactome)
├── resolver.py   # EntityResolver multi-authority resolution engine & batch engine
├── server.py     # FastMCP tool-calling interface for AI agents
├── cli.py        # CLI subcommand parsers and argument handlers
└── logging.py    # Structured logging formatted to stderr
```

---

## How to Build a New Biological Adapter

BioContext follows an extensible adapter pattern. To connect a new biological database:

### Step 1: Subclass `BaseBioAdapter`
All adapters must inherit from `BaseBioAdapter` in [`base.py`](file:///home/nanda/projects/biocontext/src/biocontext/base.py):

```python
from typing import Optional, Dict, Any
import httpx
from biocontext.base import BaseBioAdapter, SQLiteCache
from biocontext.config import ClientConfig, RateLimitConfig

class MyNewBioAdapter(BaseBioAdapter):
    """Adapter for MyNewDatabase REST API."""
    BASE_URL = "https://api.mynewdatabase.org"

    def __init__(self, cache: Optional[SQLiteCache] = None, email: Optional[str] = None):
        super().__init__(name="MyNewDatabase", cache=cache)
        self.email = ClientConfig.get_email(email)
        self.headers = ClientConfig.get_headers(self.email)

    async def fetch_data(self, query_id: str) -> Optional[Dict[str, Any]]:
        # 1. Check SQLite cache
        cache_key = f"record:{query_id.upper()}"
        cached = self.cache.get("mynewdb", cache_key)
        if cached:
            return cached

        # 2. Query external API with rate limiting & error handling
        url = f"{self.BASE_URL}/records/{query_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self.headers)
            if resp.status_code != 200:
                return None
            data = resp.json()

        # 3. Store in cache & return
        self.cache.set("mynewdb", cache_key, data)
        return data
```

### Step 2: Define Strongly-Typed Schemas
Add domain models in [`schemas.py`](file:///home/nanda/projects/biocontext/src/biocontext/schemas.py) using Pydantic v2:
```python
class MyEntity(BaseModel):
    id: str
    name: str
    provenance: str = "MyNewDatabase"
```

### Step 3: Wire into `EntityResolver` and `server.py`
1. Instantiate the adapter in `EntityResolver.__init__()` ([`resolver.py`](file:///home/nanda/projects/biocontext/src/biocontext/resolver.py)).
2. Expose an MCP tool in `server.py` decorated with `@mcp.tool()` for AI clients.
3. Register the CLI subcommand in `config.py` and `cli.py`.

---

## Testing & Quality Assurance

All contributions must pass existing tests and include tests for new functionality.

1. **Run the full test suite**:
   ```bash
   uv run pytest tests/ -v
   ```

2. **Run specific test suites**:
   ```bash
   # Core resolver & schemas
   uv run pytest tests/test_resolver.py -v

   # Biological benchmark accuracy (50 curated test cases)
   uv run pytest tests/test_benchmark.py -v

   # High-throughput batch processing engine
   uv run pytest tests/test_batch_processing.py -v

   # Functional annotations & Pathways
   uv run pytest tests/test_go_adapter.py tests/test_reactome_adapter.py -v

   # MCP Server tool execution
   uv run pytest tests/test_server.py -v
   ```

3. **Verify CLI subcommands**:
   ```bash
   uv run biocontext --help
   uv run biocontext resolve TP53
   uv run biocontext batch TP53 EGFR BRCA1
   uv run biocontext annotate TP53
   uv run biocontext pathway TP53
   ```

---

## Commit Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) convention:

- `feat(scope): add new feature or adapter`
- `fix(scope): fix bug or error handling`
- `docs: update documentation or README`
- `test: add or update test suites`
- `refactor: code changes without altering external behavior`

**Git Hygiene Notice**: Do not add AI attribution trailers (e.g. `Co-Authored-By: <AI>`) in commit messages.

---

## Pull Request Process

1. Ensure all tests pass locally (`uv run pytest tests/`).
2. Push your topic branch to your fork:
   ```bash
   git push origin feat/your-feature-name
   ```
3. Open a Pull Request against the `main` branch of `CORE-Lab-Research/biocontext`.
4. Fill out the PR template describing the purpose of the change, test results, and any relevant issue references.
5. Maintainers will review your PR and coordinate merging.
