# BioContext Quickstart Guide

This guide walks you through setting up and using **BioContext** across different environments:
1. **PyPI Package & Python SDK**
2. **AI Code Editors & Assistants (Cursor, Antigravity IDE, Claude Desktop, Claude Code, Goose)**
3. **CLI & High-Throughput Batch Workflows**
4. **Docker Container Microservice**

---

## 1. Installation via PyPI

BioContext is distributed on PyPI and can be installed with any standard Python package manager.

### Standard `pip` Installation
```bash
pip install biocontext
```

### Modern `uv` Tool / Virtualenv (Recommended)
```bash
# Install globally into your PATH as a CLI tool:
uv tool install biocontext

# Or add to your active project environment:
uv add biocontext
```

---

## 2. Integrating with AI Assistants & IDEs (MCP)

BioContext natively implements the **Model Context Protocol (MCP)** over `stdio`. Once configured, your AI assistant automatically gains access to real-time biological entity resolution, functional Gene Ontology enrichment, and Reactome pathway lookups.

### A. Cursor IDE
1. Open Cursor **Settings** (`Cmd + ,` or `Ctrl + ,`).
2. Navigate to **Features** $\rightarrow$ **MCP Servers** $\rightarrow$ Click **Add New MCP Server**.
3. Fill in:
   - **Name**: `biocontext`
   - **Type**: `command`
   - **Command**: `uvx biocontext serve`
4. Or configure directly in `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "biocontext": {
      "command": "uvx",
      "args": ["biocontext", "serve"]
    }
  }
}
```

### B. Google Antigravity IDE
In Antigravity IDE, configure MCP servers in your workspace config (`.agents/mcp_config.json` or `~/.gemini/config/mcp_config.json`):
```json
{
  "mcpServers": {
    "biocontext": {
      "command": "uvx",
      "args": ["biocontext", "serve"]
    }
  }
}
```

### C. Claude Desktop
Add BioContext to your `claude_desktop_config.json`:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "biocontext": {
      "command": "uvx",
      "args": ["biocontext", "serve"]
    }
  }
}
```

### D. Claude Code (CLI)
When running Anthropic's `claude` CLI in your terminal:
```bash
claude mcp add biocontext uvx biocontext serve
```

### E. Codex / Goose / Custom Agentic Frameworks
For any MCP client supporting JSON-RPC over `stdio`, execute:
```bash
# When installed in active python env:
biocontext serve

# Or zero-install via uvx:
uvx biocontext serve
```

---

## 3. Python SDK Usage

You can embed BioContext directly into data science scripts, pandas workflows, or Jupyter Notebooks:

```python
import asyncio
from biocontext.resolver import EntityResolver

async def main():
    resolver = EntityResolver()

    # 1. Resolve an ambiguous clinical alias
    result = await resolver.resolve("HER2", taxon_id=9606)
    print(f"Query: {result.query}")
    print(f"Approved Symbol: {result.resolved_entity.symbol}")      # ERBB2
    print(f"HGNC ID: {result.resolved_entity.hgnc_id}")              # HGNC:3430
    print(f"Confidence: {result.confidence_score}")                  # 0.85
    print(f"Match Status: {result.match_status}")                    # alias

    # 2. Query Gene Ontology annotations
    annotations = await resolver.annotate_gene("TP53", limit=5)
    for ann in annotations:
        print(f"[{ann.aspect}] {ann.term_id}: {ann.term_name} (Evidence: {ann.evidence_code})")

    # 3. Query Reactome pathways
    pathways = await resolver.get_pathways("TP53", limit=3)
    for p in pathways:
        print(f"Pathway: {p.st_id} - {p.name}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. High-Throughput Batch Processing via CLI

BioContext includes a concurrent batch engine bounded by `asyncio.Semaphore` with automatic rate-limiting compliance.

### Direct Command Line Arguments:
```bash
biocontext batch TP53 EGFR BRCA1 KRAS BRAF
```

### Processing Large CSV / TSV Gene Lists:
Given `input_genes.csv`:
```csv
gene_query,patient_id
HER2,PAT-001
p53,PAT-002
CD20,PAT-003
```

Execute:
```bash
biocontext batch --file input_genes.csv --output resolved_genes.csv --concurrency 8
```

---

## 5. Docker Microservice Execution

Run BioContext as an isolated container with persistent SQLite caching:

```bash
# Pull and run container with mounted persistent volume
docker run -i --rm -v biocontext_cache:/data ghcr.io/core-lab-research/biocontext:latest
```
