"""Tests for BioContext Entity Resolution and Schemas."""

import pytest
from biocontext.resolver import EntityResolver
from biocontext.base import SQLiteCache


@pytest.fixture
def temp_cache(tmp_path):
    db_file = tmp_path / "test_cache.db"
    return SQLiteCache(db_path=str(db_file))


@pytest.fixture
def resolver(temp_cache):
    return EntityResolver(cache=temp_cache)


@pytest.mark.asyncio
async def test_resolve_exact_symbol(resolver):
    result = await resolver.resolve("TP53")
    assert result.match_status == "exact"
    assert result.confidence_score == 1.0
    assert result.resolved_entity is not None
    assert result.resolved_entity.symbol == "TP53"
    assert result.resolved_entity.hgnc_id == "HGNC:11998"
    assert result.resolved_entity.ncbi_gene_id == "7157"
    assert "P04637" in result.resolved_entity.uniprot_ids


@pytest.mark.asyncio
async def test_resolve_alias_symbol(resolver):
    # HER2 is an alias for ERBB2
    result = await resolver.resolve("HER2")
    assert result.match_status == "alias"
    assert result.confidence_score >= 0.8
    assert result.resolved_entity is not None
    assert result.resolved_entity.symbol == "ERBB2"
    assert result.resolved_entity.hgnc_id == "HGNC:3430"


@pytest.mark.asyncio
async def test_uniprot_accession_lookup(resolver):
    # P04637 is UniProt accession for TP53
    result = await resolver.resolve("P04637")
    assert result.match_status == "exact"
    assert result.resolved_entity is not None
    assert result.resolved_entity.symbol == "TP53"


@pytest.mark.asyncio
async def test_ncbi_entrez_id_lookup(resolver):
    # 7157 is Entrez Gene ID for TP53
    result = await resolver.resolve("7157")
    assert result.match_status == "exact"
    assert result.resolved_entity is not None
    assert result.resolved_entity.symbol == "TP53"
    assert result.resolved_entity.ncbi_gene_id == "7157"


@pytest.mark.asyncio
async def test_unresolved_query(resolver):
    result = await resolver.resolve("NONEXISTENT_GENE_123456")
    assert result.match_status == "unresolved"
    assert result.confidence_score == 0.0
    assert result.resolved_entity is None
