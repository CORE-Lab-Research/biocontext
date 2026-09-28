# BioContext Architecture & API Reference

BioContext provides authoritative biological entity resolution, functional annotation, pathway intelligence, and batch processing through both a Python SDK, a CLI, and the Model Context Protocol (MCP).

---

## 1. Core Architecture

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

## 2. MCP Tools Reference

When running `biocontext serve`, the server exposes the following MCP tools:

### `resolve_gene(query, taxon_id=9606, chromosome=None, locus_type=None)`
Resolves any biological query (canonical symbol, historical alias, Entrez ID, UniProt accession, Ensembl ID, or MGI ID) into a standardized `GeneEntity`.
- **Arguments**:
  - `query` (str): Search term (e.g. `"TP53"`, `"HER2"`, `"7157"`, `"P04637"`, `"Trp53"`).
  - `taxon_id` (int): NCBI taxonomy ID (default `9606` for Human, `10090` for Mouse).
  - `chromosome` (str, optional): Chromosome clue for disambiguation.
  - `locus_type` (str, optional): Locus type clue (e.g. `"gene with protein product"`).
- **Returns**: JSON `ResolutionResult` with confidence score and match reasons.

### `batch_resolve_genes(queries, taxon_id=9606, concurrency=5)`
High-throughput concurrent resolution engine with rate-limiting and performance tracking.
- **Arguments**:
  - `queries` (list[str]): List of gene identifiers or symbols.
  - `taxon_id` (int): NCBI taxonomy ID.
  - `concurrency` (int): Number of concurrent tasks (default `5`).
- **Returns**: JSON `BatchResolutionSummary` (`total_queries`, `resolved_count`, `success_rate`, `execution_time_seconds`, and individual `results`).

### `get_protein(accession)`
Fetches protein structural metadata, description, and sequence length from UniProtKB.
- **Arguments**: `accession` (str, e.g. `"P04637"`).
- **Returns**: JSON `ProteinEntity`.

### `annotate_function(query, taxon_id=9606, aspect=None, limit=10)`
Fetches standardized Gene Ontology (GO) annotations (Molecular Function, Biological Process, Cellular Component) with evidence codes via EMBL-EBI QuickGO.
- **Arguments**:
  - `query` (str): Gene query.
  - `aspect` (str, optional): Filter by `"molecular_function"`, `"biological_process"`, or `"cellular_component"`.
  - `limit` (int): Max terms per aspect (default `10`).
- **Returns**: JSON `FunctionalAnnotation`.

### `get_go_term(go_id)`
Inspects a specific Gene Ontology term definition and aspect.
- **Arguments**: `go_id` (str, e.g. `"GO:0006915"`).
- **Returns**: JSON `GOAnnotation`.

### `get_pathways(query, taxon_id=9606, species="Homo sapiens", limit=10)`
Maps a gene/protein to biological pathways via the Reactome Content Service.
- **Arguments**:
  - `query` (str): Gene symbol or accession.
  - `limit` (int): Maximum pathways to return.
- **Returns**: JSON `PathwayContext`.

### `get_pathway_details(st_id)`
Retrieves full descriptive summary and metadata for a Reactome pathway.
- **Arguments**: `st_id` (str, e.g. `"R-HSA-5357801"`).
- **Returns**: JSON `PathwayEntity`.

### `get_mouse_gene(mgi_id)`
Performs direct lookup of mouse gene models from Mouse Genome Informatics (MGI).
- **Arguments**: `mgi_id` (str, e.g. `"MGI:98834"`).
- **Returns**: JSON `GeneEntity`.

---

## 3. Python SDK Usage

```python
import asyncio
from biocontext.resolver import EntityResolver

async def main():
    resolver = EntityResolver()

    # 1. Resolve a single gene query
    res = await resolver.resolve("HER2")
    print(f"Symbol: {res.resolved_entity.symbol} | Match: {res.match_status} | Conf: {res.confidence_score}")

    # 2. Batch resolution
    batch_res = await resolver.resolve_batch(["TP53", "BRCA1", "EGFR", "PTEN"], concurrency=4)
    print(f"Resolved {batch_res.resolved_count}/{batch_res.total_queries} in {batch_res.execution_time_seconds:.2f}s")

    # 3. Functional GO annotations
    func = await resolver.annotate_gene("TP53", max_terms_per_aspect=5)
    print("Biological Processes:", [bp.name for bp in func.biological_processes])

    # 4. Pathways
    pathways = await resolver.get_pathways("TP53", limit=5)
    print("Reactome Pathways:", [p.name for p in pathways.pathways])

asyncio.run(main())
```

---

## 4. CLI Commands Reference

| Command | Syntax | Description |
| :--- | :--- | :--- |
| `resolve` | `biocontext resolve <query> [--taxon INT]` | Resolve gene symbol, alias, or ID. |
| `batch` | `biocontext batch [<queries>...] [-f FILE] [-o OUT.csv]` | High-throughput batch resolution. |
| `annotate` | `biocontext annotate <query> [--aspect ASPECT] [-l INT]` | Fetch QuickGO annotations. |
| `go` | `biocontext go <GO_ID>` | Inspect GO term metadata. |
| `pathway` | `biocontext pathway <query> [-l INT]` | Retrieve Reactome pathways. |
| `pathway-info` | `biocontext pathway-info <ST_ID>` | Retrieve Reactome pathway summation. |
| `mouse` | `biocontext mouse <MGI_ID>` | Lookup mouse gene model via MGI. |
| `cache` | `biocontext cache [stats\|clear]` | Inspect or clear SQLite cache. |
| `serve` | `biocontext serve` | Start stdio MCP server for AI clients. |
