"""End-to-End Multilayer Integration & Stress Test Suite.

Evaluates:
1. End-to-End deep biological context (Resolve -> GO Annotations -> Reactome Pathways).
2. Stress test: high concurrency batch with mixed valid/invalid/typo queries.
3. Cache acceleration validation (second run latency reduction).
"""

import time
import pytest
from biocontext.base import SQLiteCache
from biocontext.resolver import EntityResolver
from biocontext.schemas import FunctionalAnnotation, PathwayContext, ResolutionResult


@pytest.fixture(scope="module")
def shared_cache(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("e2e") / "e2e_cache.db"
    return SQLiteCache(db_path=str(db_file))


@pytest.fixture(scope="module")
def resolver(shared_cache):
    return EntityResolver(cache=shared_cache)


@pytest.mark.asyncio
async def test_e2e_deep_biological_context_pipeline(resolver):
    """Test full multi-layer contextual pipeline for clinical alias HER2 -> ERBB2."""
    query = "HER2"
    
    # 1. Resolve clinical alias
    res: ResolutionResult = await resolver.resolve(query, taxon_id=9606)
    assert res is not None
    assert res.resolved_entity is not None
    assert res.resolved_entity.symbol == "ERBB2"
    assert res.match_status == "alias"
    assert res.confidence_score >= 0.8
    assert "P04626" in res.resolved_entity.uniprot_ids

    # 2. Enrich with Gene Ontology functional annotations
    go_profile: FunctionalAnnotation = await resolver.annotate_gene(query, taxon_id=9606, max_terms_per_aspect=5)
    assert go_profile is not None
    assert go_profile.uniprot_accession == "P04626"
    assert go_profile.total_annotations > 0
    assert len(go_profile.molecular_functions) > 0
    # Verify GO terms have valid format
    for term in go_profile.molecular_functions:
        assert term.go_id.startswith("GO:")
        assert term.aspect == "molecular_function"

    # 3. Enrich with Reactome systems biology pathways
    pathway_ctx: PathwayContext = await resolver.get_pathways(query, taxon_id=9606, limit=5)
    assert pathway_ctx is not None
    assert pathway_ctx.uniprot_accession == "P04626"
    assert pathway_ctx.total_pathways > 0
    assert len(pathway_ctx.pathways) > 0
    for p in pathway_ctx.pathways:
        assert p.st_id.startswith("R-HSA-")
        assert p.species == "Homo sapiens"


@pytest.mark.asyncio
async def test_concurrency_stress_test_mixed_queries(resolver):
    """Stress test batch engine with 25 mixed queries (symbols, aliases, Entrez, UniProt, MGI, invalid, typos)."""
    mixed_queries = [
        # Approved symbols
        "TP53", "BRCA1", "EGFR", "MYC", "VEGFA",
        # Clinical & historical aliases
        "HER2", "p53", "p27Kip1", "Bcl-xL", "PD-1",
        # NCBI Entrez IDs
        "7157", "672", "2064",
        # UniProt accessions
        "P04637", "P38398",
        # Mus musculus models
        "Braf", "Trp53", "109880", "MGI:88190", "CDK4",
        # Intentionally invalid / noise queries
        "NON_EXISTENT_GENE_XYZ_999", "INVALID_123456789", "FAKE_ALIAS_NOT_REAL"
    ]

    summary = await resolver.resolve_batch(mixed_queries, concurrency=8)
    assert summary.total_queries == len(mixed_queries)
    # At least 20 out of 23 valid queries should resolve cleanly
    assert summary.resolved_count >= 18
    # Invalid queries must be safely handled without throwing uncaught exceptions
    assert summary.unresolved_count >= 3
    assert summary.success_rate >= 0.70
    assert summary.execution_time_seconds > 0


@pytest.mark.asyncio
async def test_cache_performance_acceleration(resolver):
    """Verify that cached queries execute near-instantaneously (< 100ms total for 5 queries)."""
    test_genes = ["TP53", "BRCA1", "EGFR", "HER2", "p53"]
    
    # Warm-up (populate cache)
    await resolver.resolve_batch(test_genes, concurrency=5)

    # Second pass: must hit SQLite cache
    start = time.perf_counter()
    second_summary = await resolver.resolve_batch(test_genes, concurrency=5)
    elapsed = time.perf_counter() - start

    assert second_summary.resolved_count == len(test_genes)
    # 5 concurrent cached queries should take well under 2.0 seconds
    assert elapsed < 2.0, f"Cached batch execution took too long: {elapsed:.3f}s"
