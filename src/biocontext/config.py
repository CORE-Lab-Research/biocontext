"""Centralized configuration for BioContext scoring weights, rate limits, and CLI commands registry.
Allows easy inspection, auditing, and addition of new CLI commands and rules from a single source.
"""

from typing import Any, Dict, List


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
