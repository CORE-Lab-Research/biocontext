# BioContext

Authoritative Biological Entity Resolution & Contextual Intelligence Framework.

BioContext standardizes, resolves, and cross-references biological entities (genes, proteins, transcripts, genomic loci, functional Gene Ontology annotations, and Reactome pathways) across fragmented reference authorities (HGNC, NCBI Entrez, UniProt, Ensembl, MGI, QuickGO, Reactome) with deterministic accuracy and explainable audit trails.

Designed natively for AI coding agents and biological research workflows via the Model Context Protocol (MCP).

---

## Key Capabilities (Phase 1)

- **Multi-Authority Resolution Hierarchy**:
  - **Human Genes (HGNC Primary)**: Direct symbol resolution and historical alias/previous symbol traversal with protein-coding prioritization (e.g. `HER2` $\rightarrow$ `ERBB2`, `p53` $\rightarrow$ `TP53`, `p16` $\rightarrow$ `CDKN2A`, `p21` $\rightarrow$ `CDKN1A`).
  - **NCBI Entrez Integration**: Entrez Gene ID lookup (`7157` $\rightarrow$ `TP53`) and cross-species identifier support.
  - **UniProtKB Cross-Mapping**: Direct accession resolution (`P04637` $\rightarrow$ `TP53`) and protein structural metadata enrichment.
  - **Ensembl Genome & Transcripts**: Ensembl Gene ID resolution, transcript mapping, canonical identification, exon coordinates, and cross-species orthology.
  - **Mouse Genome Informatics (MGI)**: Direct MGI ID resolution (`MGI:98834` $\rightarrow$ `Trp53`) and mouse gene models.
- **Functional & Systems Intelligence**:
  - **Gene Ontology (QuickGO)**: Automated functional annotation enrichment (Molecular Functions, Biological Processes, Cellular Components) with evidence codes and ECO mappings.
  - **Reactome Pathways**: Systems-level mechanism mapping, hierarchical pathway structures, and pathway summations.
- **High-Throughput Batch Engine**:
  - Concurrent batch resolution bounded by `asyncio.Semaphore` with automatic rate-limiting compliance.
  - Dual output modes: CLI stdout (JSON) or formatted CSV exports.
  - CSV/TSV file input with automated header detection.
- **Explainable Audit Trail**: Every resolution result includes exact matching rules, confidence scores ($0.0 - 1.0$), and authoritative source citations.
- **Strongly Typed Schemas**: Comprehensive Pydantic v2 models for `GeneEntity`, `ProteinEntity`, `GOAnnotation`, `PathwayEntity`, and `BatchResolutionSummary`.
- **Embedded Persistence**: Zero-configuration SQLite key-value cache with configurable TTL to minimize latency and respect external rate limits.
- **Model Context Protocol (MCP)**: Native stdio server compliant with MCP 2.x for integration with Claude Desktop, Cursor, Antigravity IDE, Goose, and custom LLM tool-calling clients.

---

## Architecture Overview

```
[ AI Agent / LLM Client ] (Claude, Cursor, Goose, Custom)
            │
      MCP Protocol (JSON-RPC over stdio / SSE)
            │
            ▼
┌────────────────────────────────────────────────────────┐
│                   FastMCP Server                       │
│    src/biocontext/server.py                            │
└────────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────┐
│                  Entity Resolver                       │
│    src/biocontext/resolver.py                          │
│    • Hierarchical disambiguation & scoring             │
│    • High-Throughput Batch Engine (asyncio.Semaphore)  │
└────────────────────────────────────────────────────────┘
     │            │           │            │           │
     ▼            ▼           ▼            ▼           ▼
┌─────────┐ ┌──────────┐ ┌─────────┐ ┌───────────┐ ┌───────────┐
│  HGNC   │ │ NCBI/Uni │ │ Ensembl │ │ QuickGO   │ │ Reactome  │
│ Adapter │ │ Adapters │ │ & MGI   │ │ (Function)│ │ (Pathway) │
└─────────┘ └──────────┘ └─────────┘ └───────────┘ └───────────┘
     │            │           │            │           │
     └────────────┴─────┬─────┴────────────┴───────────┘
                        ▼
         ┌──────────────────────────────┐
         │     SQLite Persistent Cache  │
         │     (~/.cache/biocontext/..) │
         └──────────────────────────────┘
```

---

## Installation & Setup

BioContext is distributed as a standalone CLI tool and MCP server via [`uv`](https://github.com/astral-sh/uv).

### Global Installation

Install `biocontext` globally into your system path using `uv tool`:

```bash
# Install directly from GitHub
uv tool install git+https://github.com/CORE-Lab-Research/biocontext.git
```

Once installed, the `biocontext` command is available everywhere across your terminal.

To update to the latest release:
```bash
uv tool upgrade biocontext
```

### Local Development Setup

```bash
git clone https://github.com/CORE-Lab-Research/biocontext.git
cd biocontext

# Synchronize virtualenv with dependencies
uv sync
```

---

## Using BioContext as an MCP Server

BioContext exposes its tools via standard input/output (`stdio`), making it compatible with any MCP-compliant client.

### Option A: Run directly via `uvx` (No local clone needed)

Add the following to your AI client's configuration (`claude_desktop_config.json`, Cursor, etc.):

```json
{
  "mcpServers": {
    "biocontext": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/CORE-Lab-Research/biocontext.git",
        "biocontext",
        "serve"
      ]
    }
  }
}
```

### Option B: Local Repository Setup

```json
{
  "mcpServers": {
    "biocontext": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/biocontext",
        "run",
        "biocontext",
        "serve"
      ]
    }
  }
}
```

### Option C: Containerized MCP Server (Docker)

```bash
docker run -i --rm -v biocontext_cache:/data biocontext:latest
```

---

## Available MCP Tools

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `resolve_gene` | `query: str`, `taxon_id: int = 9606`, `chromosome: str = None`, `locus_type: str = None` | Resolves symbols, aliases, Entrez IDs, UniProt accessions, or MGI IDs with contextual scoring adjustments. |
| `batch_resolve_genes` | `queries: list[str]`, `taxon_id: int = 9606`, `concurrency: int = 5` | High-throughput concurrent resolution engine with execution metrics. |
| `get_protein` | `accession: str` | Retrieves structured protein metadata from UniProtKB by primary accession (e.g. `P04637`). |
| `annotate_function` | `query: str`, `taxon_id: int = 9606`, `aspect: str = None`, `limit: int = 10` | Fetches Gene Ontology terms with evidence codes from EMBL-EBI QuickGO. |
| `get_go_term` | `go_id: str` | Inspects a specific Gene Ontology term definition and aspect. |
| `get_pathways` | `query: str`, `taxon_id: int = 9606`, `species: str = "Homo sapiens"`, `limit: int = 10` | Maps genes/proteins to biological pathways via Reactome. |
| `get_pathway_details`| `st_id: str` | Retrieves descriptive summary and metadata for a Reactome pathway. |
| `get_mouse_gene` | `mgi_id: str` | Direct lookup of mouse gene models from MGI. |

---

## Command-Line Interface (CLI)

BioContext provides a comprehensive CLI for interactive querying and pipeline integration:

```bash
# Resolve a gene symbol, alias, or ID
biocontext resolve TP53
biocontext resolve HER2
biocontext resolve 7157
biocontext resolve P04637

# Disambiguation with genomic clues
biocontext resolve TP53 --chrom 17 --locus-type protein-coding

# Query cross-species (e.g. Mus musculus - taxon 10090)
biocontext resolve Trp53 --taxon 10090
biocontext mouse MGI:98834

# High-throughput batch processing
biocontext batch TP53 EGFR BRCA1 KRAS BRAF
biocontext batch --file gene_list.csv --output results.csv --concurrency 8

# Functional annotations (Gene Ontology)
biocontext annotate TP53 --limit 5
biocontext go GO:0006915

# Systems biology (Reactome pathways)
biocontext pathway TP53
biocontext pathway-info R-HSA-5357801

# Manage local cache
biocontext cache stats
biocontext cache clear

# Run test suites and accuracy benchmark
biocontext bench
biocontext test
```

---

## Benchmark & Empirical Validation

BioContext is continuously evaluated against a 50-case curated biological benchmark covering canonical symbols, clinical and historical aliases, Entrez Gene IDs, UniProt accessions, and cross-species models:

```bash
uv run pytest tests/test_benchmark.py -v
```

- **Accuracy**: $100\%$ ($50/50$ benchmark cases passing).
- **Target KPI**: $\ge 95\%$ accuracy achieved.
- **Coverage**: Full test suite: **80 passed, 5 skipped** (external Ensembl REST degradation tracked in Issue #4).

---

## Documentation & Contributing

- **[Architecture & API Reference](docs/API.md)**: Detailed schema specifications and Python SDK examples.
- **[Contributing Guide](CONTRIBUTING.md)**: Developer setup, adapter creation tutorial, and coding standards.
- **[Code of Conduct](CODE_OF_CONDUCT.md)**: Community standards and participation guidelines.
- **[Security Policy](SECURITY.md)**: Vulnerability disclosure and security architecture.

---

## Citation

If you use BioContext in your scientific research or software workflows, please cite:

```bibtex
@software{nandatama2026biocontext,
  author = {Nandatama, Engki},
  title = {BioContext: Authoritative Biological Entity Resolution & Contextual Intelligence Framework},
  year = {2026},
  url = {https://github.com/CORE-Lab-Research/biocontext},
  version = {0.1.0}
}
```

Or reference [CITATION.cff](file:///home/nanda/projects/biocontext/CITATION.cff).

---

## License

Distributed under the [Apache License, Version 2.0](file:///home/nanda/projects/biocontext/LICENSE). See `LICENSE` for more information.
