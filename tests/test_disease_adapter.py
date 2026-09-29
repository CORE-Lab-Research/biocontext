"""Tests for MONDO Disease Ontology and Open Targets Platform Adapters."""

import json
import pytest
from biocontext.adapters import MondoAdapter, OpenTargetsAdapter
from biocontext.base import SQLiteCache
from biocontext.resolver import EntityResolver
from biocontext.schemas import DiseaseEntity, TargetAssociationContext
from biocontext.server import get_target_diseases, resolve_disease


@pytest.fixture
def temp_cache(tmp_path):
    db_file = tmp_path / "test_disease_cache.db"
    return SQLiteCache(db_path=str(db_file))


@pytest.fixture
def mondo_adapter(temp_cache):
    return MondoAdapter(cache=temp_cache)


@pytest.fixture
def opentargets_adapter(temp_cache):
    return OpenTargetsAdapter(cache=temp_cache)


@pytest.fixture
def resolver(temp_cache):
    return EntityResolver(cache=temp_cache)


@pytest.mark.asyncio
async def test_fetch_mondo_by_id(mondo_adapter):
    """Test fetching Li-Fraumeni syndrome by MONDO ID (MONDO:0018875)."""
    disease = await mondo_adapter.fetch_by_id("MONDO:0018875")
    assert disease is not None
    assert isinstance(disease, DiseaseEntity)
    assert disease.mondo_id == "MONDO:0018875"
    assert "li-fraumeni" in disease.name.lower()
    assert len(disease.cross_references) > 0


@pytest.mark.asyncio
async def test_search_mondo_disease(mondo_adapter):
    """Test searching MONDO disease ontology by keyword."""
    results = await mondo_adapter.search_disease("Li-Fraumeni", limit=3)
    assert len(results) > 0
    first = results[0]
    assert isinstance(first, DiseaseEntity)
    assert first.mondo_id.startswith("MONDO:")
    assert "li-fraumeni" in first.name.lower()


@pytest.mark.asyncio
async def test_opentargets_fetch_target_diseases_tp53(opentargets_adapter):
    """Test fetching Open Targets associations for TP53 (ENSG00000141510)."""
    context = await opentargets_adapter.fetch_target_diseases(
        ensembl_gene_id="ENSG00000141510",
        symbol="TP53",
        limit=5
    )
    assert context is not None
    assert isinstance(context, TargetAssociationContext)
    assert context.ensembl_gene_id == "ENSG00000141510"
    assert context.total_associations > 100
    assert len(context.associations) > 0

    top_assoc = context.associations[0]
    assert top_assoc.score > 0.0
    assert top_assoc.disease_id is not None
    assert top_assoc.disease_name is not None


@pytest.mark.asyncio
async def test_resolver_resolve_disease(resolver):
    """Test EntityResolver.resolve_disease method."""
    diseases = await resolver.resolve_disease("Li-Fraumeni", limit=2)
    assert len(diseases) > 0
    assert diseases[0].mondo_id.startswith("MONDO:")


@pytest.mark.asyncio
async def test_resolver_get_target_diseases(resolver):
    """Test EntityResolver.get_target_diseases for gene symbol TP53."""
    context = await resolver.get_target_diseases("TP53", limit=3)
    assert context is not None
    assert isinstance(context, TargetAssociationContext)
    assert context.symbol == "TP53"
    assert len(context.associations) > 0


@pytest.mark.asyncio
async def test_mcp_tool_resolve_disease():
    """Test MCP resolve_disease tool serialization."""
    res_str = await resolve_disease("Li-Fraumeni", limit=2)
    assert res_str is not None
    data = json.loads(res_str)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "mondo_id" in data[0]


@pytest.mark.asyncio
async def test_mcp_tool_get_target_diseases():
    """Test MCP get_target_diseases tool serialization."""
    res_str = await get_target_diseases("TP53", limit=3)
    assert res_str is not None
    data = json.loads(res_str)
    assert "associations" in data
    assert len(data["associations"]) > 0
