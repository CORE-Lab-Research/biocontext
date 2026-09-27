"""Centralized configuration for BioContext scoring weights, rate limits, and CLI commands registry.
Allows easy inspection, auditing, and addition of new CLI commands and rules from a single source.
"""

import os
from typing import Any, Dict, List, Optional


class ScoringConfig:
    """Confidence scoring weights and penalties for entity resolution."""
    EXACT_SYMBOL_CONFIDENCE: float = 1.0
    ACCESSION_LOOKUP_CONFIDENCE: float = 0.95
    ENTREZ_ID_CONFIDENCE: float = 1.0
    PREV_SYMBOL_CONFIDENCE: float = 0.90
    ALIAS_MATCH_CONFIDENCE: float = 0.85
    NCBI_SEARCH_CONFIDENCE: float = 0.90

    # Contextual disambiguation adjustments
    CHROMOSOME_MATCH_BONUS: float = 0.05
    CHROMOSOME_MISMATCH_PENALTY: float = 0.40
    LOCUS_TYPE_MISMATCH_PENALTY: float = 0.30


class RateLimitConfig:
    """Outbound API request rate limits (requests per second)."""
    NCBI_WITHOUT_KEY_RPS: float = 2.8
    NCBI_WITH_KEY_RPS: float = 9.5
    HGNC_TIMEOUT_SEC: float = 10.0
    UNIPROT_TIMEOUT_SEC: float = 10.0
    ENSEMBL_RPS: float = 14.0  # Ensembl allows up to 15 req/sec
    ENSEMBL_TIMEOUT_SEC: float = 15.0



class ClientConfig:
    """Outbound client identity and contact information for external APIs."""
    DEFAULT_TOOL: str = "biocontext"
    DEFAULT_USER_AGENT: str = "BioContext/0.1.0 (https://github.com/CORE-Lab-Research/biocontext)"

    @classmethod
    def get_email(cls, email: Optional[str] = None) -> Optional[str]:
        return email or os.environ.get("NCBI_EMAIL") or os.environ.get("BIOCONTEXT_EMAIL")

    @classmethod
    def get_tool(cls, tool: Optional[str] = None) -> str:
        return tool or os.environ.get("NCBI_TOOL") or cls.DEFAULT_TOOL

    @classmethod
    def get_headers(cls, email: Optional[str] = None) -> Dict[str, str]:
        contact = cls.get_email(email)
        ua = f"{cls.DEFAULT_USER_AGENT}; contact: {contact}" if contact else cls.DEFAULT_USER_AGENT
        return {
            "User-Agent": ua,
            "Accept": "application/json",
        }



# Single Source of Truth for Exclusive CLI Commands
# Allows auditing and extending CLI commands without modifying parsing loops
CLI_COMMANDS_REGISTRY: List[Dict[str, Any]] = [
    {
        "name": "server",
        "help": "Run the Model Context Protocol (MCP) stdio server for AI agents",
        "arguments": []
    },
    {
        "name": "resolve",
        "help": "Resolve a single gene/protein query to canonical entity",
        "arguments": [
            {"flags": ["query"], "help": "Gene symbol, alias, or identifier (e.g. TP53, HER2, 7157)"},
            {"flags": ["--taxon"], "type": int, "default": 9606, "help": "NCBI Taxonomy ID (default: 9606 for human)"},
            {"flags": ["--chrom", "--chromosome"], "type": str, "default": None, "help": "Chromosome hint for disambiguation (e.g. 17 or chr17)"},
            {"flags": ["--locus-type"], "type": str, "default": None, "help": "Expected biotype (e.g. protein-coding, pseudogene)"},
        ]
    },
    {
        "name": "batch",
        "help": "Resolve multiple gene queries concurrently in batch",
        "arguments": [
            {"flags": ["queries"], "nargs": "+", "help": "Space-separated list of symbols or IDs"},
            {"flags": ["--taxon"], "type": int, "default": 9606, "help": "NCBI Taxonomy ID (default: 9606 for human)"},
        ]
    },
    {
        "name": "protein",
        "help": "Fetch UniProt protein metadata by accession",
        "arguments": [
            {"flags": ["accession"], "help": "UniProt accession ID (e.g. P04637)"}
        ]
    },
    {
        "name": "transcripts",
        "help": "Fetch gene coordinates and transcript variants from Ensembl",
        "arguments": [
            {"flags": ["query"], "help": "Ensembl Gene ID (e.g. ENSG00000141510) or gene symbol (e.g. TP53)"},
            {"flags": ["--species"], "type": str, "default": "homo_sapiens", "help": "Species name (default: homo_sapiens)"}
        ]
    },
    {
        "name": "ortholog",
        "help": "Identify orthologous genes across species via Ensembl",
        "arguments": [
            {"flags": ["query"], "help": "Gene symbol (e.g. TP53) or Ensembl Gene ID"},
            {"flags": ["--target"], "type": str, "default": "mus_musculus", "help": "Target species (default: mus_musculus)"},
            {"flags": ["--source"], "type": str, "default": "homo_sapiens", "help": "Source species (default: homo_sapiens)"}
        ]
    },


    {
        "name": "cache",
        "help": "Inspect or clear persistent local SQLite cache",
        "subcommands": [
            {"name": "stats", "help": "Show cache item counts and namespace distribution"},
            {"name": "clear", "help": "Purge all cached responses"}
        ]
    },
    {
        "name": "bench",
        "help": "Run empirical 25-case resolution accuracy benchmark (KPI validation)",
        "arguments": []
    },
    {
        "name": "test",
        "help": "Run complete automated test suite",
        "arguments": []
    }
]
