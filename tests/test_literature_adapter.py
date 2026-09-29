"""Tests for Europe PMC Literature Adapter, Literature Context, and Server Tools."""

import json
import pytest
from biocontext.adapters import LiteratureAdapter
from biocontext.base import SQLiteCache
from biocontext.resolver import EntityResolver
from biocontext.schemas import LiteratureContext, PublicationEntity
from biocontext.server import get_publication_details, get_supporting_publications


@pytest.fixture
def temp_cache(tmp_path):
    db_file = tmp_path / "test_literature_cache.db"
    return SQLiteCache(db_path=str(db_file))


@pytest.fixture
def literature_adapter(temp_cache):
    return LiteratureAdapter(cache=temp_cache)


@pytest.fixture
def resolver(temp_cache):
    return EntityResolver(cache=temp_cache)


@pytest.mark.asyncio
async def test_fetch_publication_by_pmid(literature_adapter):
    """Test fetching publication metadata by PubMed ID (PMID: 30514107)."""
    pub = await literature_adapter.fetch_by_id("30514107")
    assert pub is not None
    assert isinstance(pub, PublicationEntity)
    assert pub.pmid == "30514107"
    assert pub.title is not None
    assert len(pub.authors) > 0
    assert pub.pub_year is not None


@pytest.mark.asyncio
async def test_fetch_publication_by_pmcid(literature_adapter):
    """Test fetching publication metadata by PMC ID (PMC13589805)."""
    pub = await literature_adapter.fetch_by_id("PMC13589805")
    assert pub is not None
    assert isinstance(pub, PublicationEntity)
    assert pub.pmcid == "PMC13589805"


@pytest.mark.asyncio
async def test_fetch_publication_by_doi(literature_adapter):
    """Test fetching publication metadata by DOI."""
    pub = await literature_adapter.fetch_by_id("10.1096/fj.201801695r")
    assert pub is not None
    assert isinstance(pub, PublicationEntity)
    assert pub.doi == "10.1096/fj.201801695r"
    assert "CELF1" in pub.title or "p53" in pub.title



@pytest.mark.asyncio
async def test_search_publications_tp53(literature_adapter):
    """Test searching Europe PMC for TP53 citations."""
    context = await literature_adapter.search_publications("TP53", limit=3)
    assert context is not None
    assert isinstance(context, LiteratureContext)
    assert context.total_hits > 1000
    assert len(context.publications) == 3

    first = context.publications[0]
    assert first.title is not None
    assert first.cited_by_count is not None and first.cited_by_count >= 0


@pytest.mark.asyncio
async def test_resolver_get_supporting_publications(resolver):
    """Test EntityResolver.get_supporting_publications for gene symbol BRCA1."""
    context = await resolver.get_supporting_publications("BRCA1", limit=3)
    assert context is not None
    assert isinstance(context, LiteratureContext)
    assert len(context.publications) > 0


@pytest.mark.asyncio
async def test_resolver_get_publication_details(resolver):
    """Test EntityResolver.get_publication_details."""
    pub = await resolver.get_publication_details("30514107")
    assert pub is not None
    assert pub.pmid == "30514107"


@pytest.mark.asyncio
async def test_mcp_tool_get_supporting_publications():
    """Test MCP get_supporting_publications tool serialization."""
    res_str = await get_supporting_publications("TP53", limit=2)
    assert res_str is not None
    data = json.loads(res_str)
    assert "publications" in data
    assert len(data["publications"]) > 0


@pytest.mark.asyncio
async def test_mcp_tool_get_publication_details():
    """Test MCP get_publication_details tool serialization."""
    res_str = await get_publication_details("30514107")
    assert res_str is not None
    data = json.loads(res_str)
    assert data.get("pmid") == "30514107"
