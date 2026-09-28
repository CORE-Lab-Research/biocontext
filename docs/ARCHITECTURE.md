# BioContext System Architecture

BioContext provides authoritative biological entity resolution and contextual intelligence for AI agents and genomic pipelines. This document describes the system architecture, component boundaries, data flow, and defensive resolution principles.

---

## 1. Architectural Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AI Agents & Clients                             │
│   (Cursor, Claude Desktop, Antigravity IDE, Claude Code, Python SDK)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │  MCP Protocol (JSON-RPC stdio) / CLI
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FastMCP Server Layer                            │
│                      src/biocontext/server.py                          │
│                                                                        │
│   • resolve_gene            • batch_resolve_genes    • get_protein     │
│   • annotate_function       • get_go_term            • get_pathways    │
│   • get_pathway_details     • get_mouse_gene                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       Entity Resolution Core                           │
│                     src/biocontext/resolver.py                         │
│                                                                        │
│   • Disambiguation Engine & Confidence Scoring (0.0 - 1.0)             │
│   • Genomic Clue Matching (Chromosome, Locus Type)                     │
│   • High-Throughput Batch Engine (asyncio.Semaphore rate-limiting)     │
└────────────┬─────────────┬────────────┬─────────────┬────────────┬─────┘
             │             │            │             │            │
             ▼             ▼            ▼             ▼            ▼
      ┌──────────┐   ┌──────────┐ ┌──────────┐  ┌──────────┐ ┌───────────┐
      │   HGNC   │   │   NCBI   │ │ UniProt  │  │ QuickGO  │ │ Reactome  │
      │ Adapter  │   │ Adapter  │ │ Adapter  │  │ Adapter  │ │  Adapter  │
      └────┬─────┘   └────┬─────┘ └────┬─────┘  └────┬─────┘ └─────┬─────┘
           │              │            │             │             │
           └──────────────┴────────────┼─────────────┴─────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │     SQLite Persistence Cache  │
                       │    (~/.cache/biocontext/..)   │
                       └───────────────────────────────┘
```

---

## 2. Core Components

### A. Server Layer (`server.py`)
Built on `FastMCP`, exposing strongly typed MCP tool definitions. Communicates via standard I/O (`stdio`), enabling zero-overhead execution without opening unauthenticated network ports.

### B. Resolution & Disambiguation Core (`resolver.py`)
Implements hierarchical lookup rules with protein-coding gene prioritization:
1. **Direct Identifier Inspection**: Detects Entrez Gene IDs (numeric digits), UniProtKB accessions (regex pattern `[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}`), or MGI identifiers (`MGI:\d+`).
2. **Authoritative Symbol Resolution**: Direct query against HGNC (for Human, taxon 9606) or NCBI Gene (for model organisms).
3. **Alias & Historical Symbol Traversal**: Disambiguates synonyms against official database alias registries.
4. **Contextual Pruning**: Applies supplied clues (e.g. chromosome, locus type) to filter candidate matches.
5. **Typo / Fuzzy Recovery**: Levenshtein-distance fallback for minor typos when strict matches fail.

### C. Persistent Caching Layer (`base.py`)
- SQLite key-value store with configurable Time-To-Live (TTL).
- Caches raw responses and parsed models to eliminate redundant network roundtrips and protect upstream public bioinformatics APIs from rate-limiting.

---

## 3. Scientific Integrity & Anti-Hallucination Design

BioContext enforces a strict **"Fail Safely over Guessing"** design pattern:

| Principle | Implementation |
| :--- | :--- |
| **Deterministic Provenance** | Every resolution result links directly to authoritative accession numbers (`hgnc_id`, `entrez_id`, `ensembl_gene_id`, `uniprot_ids`). No synthetic or randomized fallbacks are permitted. |
| **Explicit Confidence Scores** | Outputs include scores from `1.0` (exact approved symbol) to `0.85` (alias), `0.60` (fuzzy), or `0.0` (unresolved). |
| **Transparent Audit Trails** | Every result object includes `match_reasons` detailing the exact rule, source authority, and evaluation details. |
| **Safe Failure State** | Unresolvable queries return `match_status: "unresolved"` rather than making speculative guesses. |
