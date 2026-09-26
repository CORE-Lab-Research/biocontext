# BioContext

Authoritative Biological Entity Resolution & Contextual Intelligence Framework.

BioContext standardizes, resolves, and cross-references biological entities (genes, proteins, transcripts, genomic loci) across fragmented reference authorities (HGNC, NCBI Entrez, UniProt, Ensembl) with deterministic accuracy and explainable audit trails.

Designed natively for AI coding agents and biological research workflows via the Model Context Protocol (MCP).

---

## Key Capabilities (Phase 0 - MVP v0.1.0)

- **Authoritative Resolution Hierarchy**:
  - **Human Genes (HGNC Primary)**: Direct symbol resolution and historical alias/previous symbol traversal (e.g. `HER2` $\rightarrow$ `ERBB2`, `p53` $\rightarrow$ `TP53`).
  - **NCBI Entrez Integration**: Entrez Gene ID lookup (`7157` $\rightarrow$ `TP53`) and cross-species identifier support.
  - **UniProtKB Cross-Mapping**: Direct accession resolution (`P04637` $\rightarrow$ `TP53`) and protein structural metadata enrichment.
- **Explainable Audit Trail**: Every resolution result includes exact matching rules, confidence scores ($0.0 - 1.0$), and authoritative source citations.
- **Strongly Typed Schemas**: Comprehensive Pydantic models for `GeneEntity`, `ProteinEntity`, `GenomicLocation`, and `ResolutionResult`.
- **Embedded Persistence**: Zero-configuration SQLite key-value cache with configurable TTL to reduce latency and comply with NCBI rate limits.
- **Model Context Protocol (MCP)**: Native stdio server compliant with MCP 2.x for integration with Claude Desktop, Antigravity IDE, Cursor, and custom LLM tool-calling clients.

---

## Architecture Overview

```
[ LLM / AI Client / Agent ]
           |
       (MCP stdio)
           v
   [ FastMCP Server ]
           |
   [ Entity Resolver ]
      /    |     \
     v     v      v
  [HGNC] [NCBI] [UniProt]
     \     |     /
    [ SQLite Cache ]
```

---

## Installation & Setup

BioContext uses [`uv`](https://github.com/astral-sh/uv) for deterministic package and virtual environment management.

### Prerequisites
- Python $\ge 3.11$
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Clone and Install

```bash
git clone https://github.com/engkinandatama/biocontext.git
cd biocontext

# Install dependencies including dev tools
uv sync --extra dev
```

---

## Running Tests

Execute the complete asynchronous test suite:

```bash
uv run --extra dev pytest -v
```

All 8 integration tests verify HGNC exact matching, alias traversal, UniProt accession lookup, NCBI Entrez ID lookup, and MCP tool endpoints.

---

## Using BioContext as an MCP Server

BioContext exposes its tools via standard input/output (`stdio`), making it compatible with any MCP-compliant client.

### Option A: Run directly from GitHub via `uvx` (No local clone needed)

If `uv` is installed on your system, you or any user can run BioContext directly without cloning the repository:

```json
{
  "mcpServers": {
    "biocontext": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/engkinandatama/biocontext.git",
        "biocontext"
      ]
    }
  }
}
```

### Option B: Local Repository Setup

When working with a locally cloned repository:

```bash
uv run biocontext
```

Add the server to your client's MCP configuration (`claude_desktop_config.json`, Cursor, Antigravity IDE, etc.):

```json
{
  "mcpServers": {
    "biocontext": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/biocontext",
        "run",
        "biocontext"
      ]
    }
  }
}
```

> **Note**: Replace `/path/to/biocontext` with the absolute path to your cloned directory (e.g. `/home/user/projects/biocontext` on Linux/macOS or `C:/Users/Username/projects/biocontext` on Windows).

---

## Command-Line Interface (CLI)

BioContext includes a built-in CLI for direct terminal testing without needing an active LLM client:

```bash
# Resolve a gene symbol or alias
uv run biocontext resolve TP53
uv run biocontext resolve HER2

# Query cross-species (e.g. Mus musculus - taxon 10090)
uv run biocontext resolve Trp53 --taxon 10090

# Batch resolve multiple entities
uv run biocontext batch TP53 HER2 EGFR MYC

# Fetch protein metadata from UniProt
uv run biocontext protein P04637

# Manage local cache
uv run biocontext cache stats
uv run biocontext cache clear

# Run built-in accuracy benchmark & test suite
uv run biocontext bench
uv run biocontext test
```

---

## Available MCP Tools

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `resolve_gene` | `query: str`, `taxon_id: int = 9606` | Resolves official symbols (`TP53`), aliases (`HER2`), or Entrez IDs (`7157`) to a canonical `GeneEntity` with audit reasons. |
| `batch_resolve_genes` | `queries: list[str]`, `taxon_id: int = 9606` | Concurrently resolves multiple gene identifiers or aliases. |
| `get_protein_info` | `accession: str` | Retrieves structured protein metadata from UniProtKB by primary accession (e.g. `P04637`). |

---

## Benchmark & Empirical Validation

To validate Phase 0 accuracy KPIs, a 25-case benchmark suite evaluates standard symbols, historical aliases (`MLL`, `OCT4`, `INT1`, `HER2`), Entrez IDs (`7157`, `672`, `2064`), UniProt accessions, and cross-species lookups:

```bash
uv run --extra dev pytest tests/test_benchmark.py -v
```

- **Accuracy**: $100\%$ ($25/25$ benchmark cases passing).
- **Target KPI**: $\ge 95\%$ accuracy achieved.

---

## Example Resolution Output

```json
{
  "query": "HER2",
  "match_status": "alias",
  "confidence_score": 0.85,
  "resolved_entity": {
    "symbol": "ERBB2",
    "name": "erb-b2 receptor tyrosine kinase 2",
    "taxon_id": 9606,
    "species": "Homo sapiens",
    "hgnc_id": "HGNC:3430",
    "ncbi_gene_id": "2064",
    "ensembl_gene_id": "ENSG00000141736",
    "uniprot_ids": ["P04626"],
    "synonyms": ["HER2", "NEU", "NGL", "TKR1", "CD340", "HER-2", "MLN 19", "HER-2/neu"],
    "locus_type": "gene with protein product",
    "location": {
      "chromosome": "17q12",
      "start": null,
      "end": null,
      "strand": null,
      "assembly": "GRCh38"
    }
  },
  "match_reasons": [
    {
      "source": "HGNC",
      "rule": "alias_match",
      "confidence": 0.85,
      "details": "Matched alias_match via HGNC REST API for symbol 'ERBB2'"
    }
  ]
}
```

---

## Roadmap

- **Phase 0 (MVP v0.1.0) [CURRENT]**: Core schemas, HGNC, NCBI Entrez, UniProt adapters, SQLite cache, FastMCP server.
- **Phase 1 (v0.5.0)**: Ensembl & MGI adapters, batch processing engine, PyPI package publication, REST API bridge.
- **Phase 2 (v1.0.0)**: Knowledge Graph integration, Biological Evidence & Provenance layer, AI Reasoning (Bio-RAG).
- **Phase 3 (v2.0.0)**: Variant interpretation, Drug discovery cross-referencing, multi-omics integration.

---

## Citation

If you use BioContext in your scientific research or software workflows, please cite:

```bibtex
@software{nandatama2026biocontext,
  author = {Nandatama, Engki},
  title = {BioContext: Authoritative Biological Entity Resolution & Contextual Intelligence Framework},
  year = {2026},
  url = {https://github.com/engkinandatama/biocontext},
  version = {0.1.0}
}
```

Or reference [CITATION.cff](file:///home/nanda/projects/biocontext/CITATION.cff).

---

## License

Distributed under the [Apache License, Version 2.0](file:///home/nanda/projects/biocontext/LICENSE). See `LICENSE` for more information.
