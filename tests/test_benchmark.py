"""Rigorous benchmark test suite evaluating Entity Resolution Accuracy across 25 diverse test cases.
Target KPI: >= 95% resolution accuracy.
"""

import pytest
from biocontext.base import SQLiteCache
from biocontext.resolver import EntityResolver

# 25 Curated Benchmark Cases (Exact symbols, historical aliases, Entrez IDs, UniProt accessions, cross-species)
BENCHMARK_DATA = [
    # 1-15: Well-known human cancer & cell cycle genes (exact symbols)
    {"query": "TP53", "taxon": 9606, "expected_symbol": "TP53", "expected_status": "exact"},
    {"query": "BRCA1", "taxon": 9606, "expected_symbol": "BRCA1", "expected_status": "exact"},
    {"query": "BRCA2", "taxon": 9606, "expected_symbol": "BRCA2", "expected_status": "exact"},
    {"query": "EGFR", "taxon": 9606, "expected_symbol": "EGFR", "expected_status": "exact"},
    {"query": "KRAS", "taxon": 9606, "expected_symbol": "KRAS", "expected_status": "exact"},
    {"query": "BRAF", "taxon": 9606, "expected_symbol": "BRAF", "expected_status": "exact"},
    {"query": "PTEN", "taxon": 9606, "expected_symbol": "PTEN", "expected_status": "exact"},
    {"query": "MYC", "taxon": 9606, "expected_symbol": "MYC", "expected_status": "exact"},
    {"query": "VEGFA", "taxon": 9606, "expected_symbol": "VEGFA", "expected_status": "exact"},
    {"query": "IL6", "taxon": 9606, "expected_symbol": "IL6", "expected_status": "exact"},
    {"query": "CDK4", "taxon": 9606, "expected_symbol": "CDK4", "expected_status": "exact"},
    {"query": "RB1", "taxon": 9606, "expected_symbol": "RB1", "expected_status": "exact"},
    {"query": "CDKN2A", "taxon": 9606, "expected_symbol": "CDKN2A", "expected_status": "exact"},
    {"query": "AKT1", "taxon": 9606, "expected_symbol": "AKT1", "expected_status": "exact"},
    {"query": "PIK3CA", "taxon": 9606, "expected_symbol": "PIK3CA", "expected_status": "exact"},

    # 16-25: Important historical and clinical aliases
    {"query": "HER2", "taxon": 9606, "expected_symbol": "ERBB2", "expected_status": "alias"},
    {"query": "p53", "taxon": 9606, "expected_symbol": "TP53", "expected_status": "alias"},
    {"query": "MLL", "taxon": 9606, "expected_symbol": "KMT2A", "expected_status": "alias"},
    {"query": "OCT4", "taxon": 9606, "expected_symbol": "POU5F1", "expected_status": "alias"},
    {"query": "WNT1", "taxon": 9606, "expected_symbol": "WNT1", "expected_status": "exact"},
    {"query": "INT1", "taxon": 9606, "expected_symbol": "WNT1", "expected_status": "alias"},
    {"query": "CD340", "taxon": 9606, "expected_symbol": "ERBB2", "expected_status": "alias"},
    {"query": "p16", "taxon": 9606, "expected_symbol": "CDKN2A", "expected_status": "alias"},
    {"query": "p16INK4a", "taxon": 9606, "expected_symbol": "CDKN2A", "expected_status": "alias"},
    {"query": "p21", "taxon": 9606, "expected_symbol": "CDKN1A", "expected_status": "alias"},

    # 26-33: Entrez Gene ID lookups
    {"query": "7157", "taxon": 9606, "expected_symbol": "TP53", "expected_status": "exact"},
    {"query": "672", "taxon": 9606, "expected_symbol": "BRCA1", "expected_status": "exact"},
    {"query": "2064", "taxon": 9606, "expected_symbol": "ERBB2", "expected_status": "exact"},
    {"query": "1019", "taxon": 9606, "expected_symbol": "CDK4", "expected_status": "exact"},
    {"query": "5925", "taxon": 9606, "expected_symbol": "RB1", "expected_status": "exact"},
    {"query": "1029", "taxon": 9606, "expected_symbol": "CDKN2A", "expected_status": "exact"},
    {"query": "207", "taxon": 9606, "expected_symbol": "AKT1", "expected_status": "exact"},
    {"query": "5290", "taxon": 9606, "expected_symbol": "PIK3CA", "expected_status": "exact"},

    # 34-41: UniProtKB accession lookups
    {"query": "P04637", "taxon": 9606, "expected_symbol": "TP53", "expected_status": "exact"},
    {"query": "P38398", "taxon": 9606, "expected_symbol": "BRCA1", "expected_status": "exact"},
    {"query": "P00533", "taxon": 9606, "expected_symbol": "EGFR", "expected_status": "exact"},
    {"query": "P11802", "taxon": 9606, "expected_symbol": "CDK4", "expected_status": "exact"},
    {"query": "P06400", "taxon": 9606, "expected_symbol": "RB1", "expected_status": "exact"},
    {"query": "P01116", "taxon": 9606, "expected_symbol": "KRAS", "expected_status": "exact"},
    {"query": "P42224", "taxon": 9606, "expected_symbol": "STAT1", "expected_status": "exact"},
    {"query": "P31749", "taxon": 9606, "expected_symbol": "AKT1", "expected_status": "exact"},

    # 42-50: Cross-species (Mus musculus - taxon 10090)
    {"query": "Trp53", "taxon": 10090, "expected_symbol": "Trp53", "expected_status": "ncbi_matched"},
    {"query": "22059", "taxon": 10090, "expected_symbol": "Trp53", "expected_status": "exact"},
    {"query": "MGI:98834", "taxon": 10090, "expected_symbol": "Trp53", "expected_status": "exact"},
    {"query": "Egfr", "taxon": 10090, "expected_symbol": "Egfr", "expected_status": "ncbi_matched"},
    {"query": "13649", "taxon": 10090, "expected_symbol": "Egfr", "expected_status": "exact"},
    {"query": "MGI:95294", "taxon": 10090, "expected_symbol": "Egfr", "expected_status": "exact"},
    {"query": "Kras", "taxon": 10090, "expected_symbol": "Kras", "expected_status": "ncbi_matched"},
    {"query": "16653", "taxon": 10090, "expected_symbol": "Kras", "expected_status": "exact"},
    {"query": "MGI:96680", "taxon": 10090, "expected_symbol": "Kras", "expected_status": "exact"},
]


@pytest.fixture(scope="module")
def shared_cache(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("benchmark") / "bench_cache.db"
    return SQLiteCache(db_path=str(db_file))


@pytest.fixture(scope="module")
def bench_resolver(shared_cache):
    return EntityResolver(cache=shared_cache)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", BENCHMARK_DATA)
async def test_benchmark_entity_resolution(bench_resolver, case):
    result = await bench_resolver.resolve(query=case["query"], taxon_id=case["taxon"])
    
    assert result is not None, f"Failed to return result for query {case['query']}"
    assert result.resolved_entity is not None, f"Entity not resolved for {case['query']}"
    assert result.resolved_entity.symbol == case["expected_symbol"], (
        f"Query '{case['query']}' resolved to '{result.resolved_entity.symbol}', "
        f"expected '{case['expected_symbol']}'"
    )
    assert result.confidence_score >= 0.8, (
        f"Confidence score {result.confidence_score} below 0.8 for '{case['query']}'"
    )
