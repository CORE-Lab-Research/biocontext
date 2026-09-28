"""Tests for Reactome Pathway Adapter, Pathway Context, and Server Tools."""

import json
import pytest
from biocontext.adapters import ReactomeAdapter
from biocontext.base import SQLiteCache
from biocontext.resolver import EntityResolver
from biocontext.schemas import PathwayContext, PathwayEntity
from biocontext.server import get_pathway_details, get_pathways


@pytest.fixture
def temp_cache(tmp_path):
    db_file = tmp_path / "test_reactome_cache.db"
    return SQLiteCache(db_path=str(db_file))


@pytest.fixture
def reactome_adapter(temp_cache):
    return ReactomeAdapter(cache=temp_cache)


@pytest.fixture
def resolver(temp_cache):
    return EntityResolver(cache=temp_cache)


@pytest.mark.asyncio
async def test_fetch_pathways_by_uniprot_tp53(reactome_adapter):
    """Test fetching Reactome pathways for TP53 (P04637)."""
    pathways = await reactome_adapter.fetch_pathways_by_uniprot(
        uniprot_accession="P04637",
        species="Homo sapiens",
        limit=5
    )
    assert len(pathways) > 0
    first = pathways[0]
    assert isinstance(first, PathwayEntity)
    assert first.st_id.startswith("R-HSA-")
    assert first.species == "Homo sapiens"
    assert first.url.startswith("https://reactome.org/PathwayBrowser/#/")


@pytest.mark.asyncio
async def test_fetch_pathway_details(reactome_adapter):
    """Test fetching pathway metadata by stable ID (R-HSA-5357801: Programmed Cell Death)."""
    details = await reactome_adapter.fetch_pathway_details("R-HSA-5357801")
    assert details is not None
    assert details["st_id"] == "R-HSA-5357801"
    assert "cell death" in details["name"].lower() or "programmed" in details["name"].lower()
    assert details["species"] == "Homo sapiens"
    assert details["url"] == "https://reactome.org/PathwayBrowser/#/R-HSA-5357801"


@pytest.mark.asyncio
async def test_resolver_get_pathways_tp53(resolver):
    """Test EntityResolver.get_pathways for gene symbol TP53."""
    context = await resolver.get_pathways("TP53", limit=5)
    assert context is not None
    assert isinstance(context, PathwayContext)
    assert context.query == "TP53"
    assert context.uniprot_accession == "P04637"
    assert context.source == "Reactome"
    assert context.total_pathways > 0
    assert len(context.pathways) <= 5
    for p in context.pathways:
        assert p.st_id.startswith("R-HSA-")


@pytest.mark.asyncio
async def test_resolver_get_pathways_caching(resolver):
    """Test SQLite caching for Reactome pathways."""
    # First call
    c1 = await resolver.get_pathways("TP53", limit=3)
    assert c1 is not None

    stats = resolver.cache.stats()
    assert stats["by_namespace"].get("reactome", 0) > 0

    # Second call uses cache
    c2 = await resolver.get_pathways("TP53", limit=3)
    assert c2 is not None
    assert c1.total_pathways == c2.total_pathways
    assert [p.st_id for p in c1.pathways] == [p.st_id for p in c2.pathways]


@pytest.mark.asyncio
async def test_mcp_get_pathways_tool():
    """Test MCP server get_pathways tool."""
    raw_json = await get_pathways("TP53", limit=3)
    data = json.loads(raw_json)
    assert data["query"] == "TP53"
    assert data["source"] == "Reactome"
    assert "pathways" in data
    assert len(data["pathways"]) > 0


@pytest.mark.asyncio
async def test_mcp_get_pathway_details_tool():
    """Test MCP server get_pathway_details tool."""
    raw_json = await get_pathway_details("R-HSA-5357801")
    data = json.loads(raw_json)
    assert data["st_id"] == "R-HSA-5357801"
    assert "name" in data
