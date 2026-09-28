"""Tests for Gene Ontology (GO) Adapter, Functional Annotations, and Server Tools."""

import json
import pytest
from biocontext.adapters import GeneOntologyAdapter
from biocontext.base import SQLiteCache
from biocontext.resolver import EntityResolver
from biocontext.schemas import FunctionalAnnotation, GOAnnotation
from biocontext.server import annotate_function, get_go_term


@pytest.fixture
def temp_cache(tmp_path):
    db_file = tmp_path / "test_go_cache.db"
    return SQLiteCache(db_path=str(db_file))


@pytest.fixture
def go_adapter(temp_cache):
    return GeneOntologyAdapter(cache=temp_cache)


@pytest.fixture
def resolver(temp_cache):
    return EntityResolver(cache=temp_cache)


@pytest.mark.asyncio
async def test_fetch_go_term(go_adapter):
    """Test fetching GO term metadata for apoptosis (GO:0006915)."""
    term = await go_adapter.fetch_term("GO:0006915")
    assert term is not None
    assert term["go_id"] == "GO:0006915"
    assert "apoptotic process" in term["name"].lower() or "apoptosis" in term["name"].lower()
    assert term["aspect"] == "biological_process"
    assert term["definition"] is not None
    assert isinstance(term["synonyms"], list)


@pytest.mark.asyncio
async def test_fetch_go_term_formatting(go_adapter):
    """Test that go_id prefix normalization works (e.g. '0006915' -> 'GO:0006915')."""
    term = await go_adapter.fetch_term("0006915")
    assert term is not None
    assert term["go_id"] == "GO:0006915"


@pytest.mark.asyncio
async def test_fetch_annotations_tp53(go_adapter):
    """Test fetching QuickGO annotations directly for TP53 (P04637)."""
    annots = await go_adapter.fetch_annotations(gene_product_id="P04637", taxon_id=9606, limit=10)
    assert len(annots) > 0
    first = annots[0]
    assert isinstance(first, GOAnnotation)
    assert first.go_id.startswith("GO:")
    assert first.aspect in ("molecular_function", "biological_process", "cellular_component")
    assert first.evidence_code is not None


@pytest.mark.asyncio
async def test_annotate_gene_tp53(resolver):
    """Test full functional annotation resolution for gene TP53."""
    profile = await resolver.annotate_gene("TP53", taxon_id=9606, max_terms_per_aspect=10)
    assert profile is not None
    assert isinstance(profile, FunctionalAnnotation)
    assert profile.query == "TP53"
    assert profile.uniprot_accession == "P04637"
    assert profile.total_annotations > 0

    # Verify that aspects are segregated
    assert len(profile.biological_processes) > 0
    for bp in profile.biological_processes:
        assert bp.aspect == "biological_process"

    if profile.molecular_functions:
        for mf in profile.molecular_functions:
            assert mf.aspect == "molecular_function"

    if profile.cellular_components:
        for cc in profile.cellular_components:
            assert cc.aspect == "cellular_component"


@pytest.mark.asyncio
async def test_annotate_gene_caching(resolver):
    """Test that repeated requests use SQLite cache."""
    # First call
    p1 = await resolver.annotate_gene("TP53", max_terms_per_aspect=5)
    assert p1 is not None

    # Verify cache key in 'go' namespace
    cache_stats = resolver.cache.stats()
    assert cache_stats["by_namespace"].get("go", 0) > 0

    # Second call should return identical annotations quickly from cache
    p2 = await resolver.annotate_gene("TP53", max_terms_per_aspect=5)
    assert p2 is not None
    assert p1.total_annotations == p2.total_annotations
    assert [a.go_id for a in p1.biological_processes] == [a.go_id for a in p2.biological_processes]


@pytest.mark.asyncio
async def test_mcp_annotate_function_tool():
    """Test MCP server annotate_function tool."""
    raw_json = await annotate_function("TP53", limit=5)
    data = json.loads(raw_json)
    assert "query" in data
    assert data["query"] == "TP53"
    assert "biological_processes" in data
    assert data["total_annotations"] > 0


@pytest.mark.asyncio
async def test_mcp_get_go_term_tool():
    """Test MCP server get_go_term tool."""
    raw_json = await get_go_term("GO:0006915")
    data = json.loads(raw_json)
    assert data.get("go_id") == "GO:0006915"
    assert "apoptotic process" in data.get("name", "").lower()
