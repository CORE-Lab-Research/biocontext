# Security Policy

## Supported Versions

We actively support and provide security fixes for the following versions of BioContext:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

---

## Reporting a Vulnerability

The BioContext project takes security vulnerabilities seriously. We appreciate your efforts to responsibly disclose findings.

If you discover a security vulnerability or potential exploit in BioContext (such as input validation flaws, arbitrary file write via cache, dependency vulnerabilities, or unauthorized information leakage through MCP stdio/SSE channels):

1. **DO NOT** create a public GitHub issue.
2. Email your report directly to the security maintainers:
   - **Primary Contact**: `engkinandatama@outlook.com`
3. Please include:
   - A clear description of the vulnerability.
   - Minimal reproducible steps or proof-of-concept (PoC).
   - Potential impact on users, LLM host environments, or genomic data workflows.
   - Any suggested mitigations or patches if available.

### Response Timeline
- **Initial Acknowledgment**: Within 48 hours of report receipt.
- **Triage & Status Assessment**: Within 5 business days with details on replication status.
- **Remediation & Patch**: A fix will be developed in a private security advisory branch and published alongside an advisory release.

---

## Security Architecture & Best Practices

BioContext is designed with strict security considerations, especially when operating as an autonomous agent tool:

### 1. Isolated MCP Execution
- BioContext runs locally as an MCP stdio server. It does **not** execute arbitrary shell commands or write executable scripts on the host system.
- Standard output (`stdout`) is strictly reserved for JSON-RPC MCP messages; all diagnostic, debug, and error logs are directed to `stderr` or local cache to prevent stream pollution or prompt injection.

### 2. Local Cache Sanitization
- Local caches are stored in a designated SQLite database (`~/.cache/biocontext/cache.db` or configured path).
- Cache keys and SQL queries are parameterized using standard parameterized statements to eliminate SQL injection risks.

### 3. Outbound Network Requests
- Outbound API calls are made only to verified, authoritative scientific institutions:
  - HGNC (`https://rest.genenames.org`)
  - NCBI E-utilities (`https://eutils.ncbi.nlm.nih.gov`)
  - UniProt (`https://rest.uniprot.org`)
  - EMBL-EBI / Ensembl (`https://rest.ensembl.org`)
  - EMBL-EBI / QuickGO (`https://www.ebi.ac.uk/QuickGO`)
  - Reactome (`https://reactome.org`)
  - Mouse Genome Informatics (`https://www.informatics.jax.org`)
- All HTTPS requests use strict certificate verification via `httpx`.
