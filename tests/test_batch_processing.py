"""Tests for High-Throughput Batch Processing Engine (PRD-03, PRD-18)."""

import json
import pytest
from biocontext.base import SQLiteCache
from biocontext.resolver import EntityResolver
from biocontext.schemas import BatchResolutionSummary
from biocontext.server import batch_resolve_genes


@pytest.fixture
def temp_cache(tmp_path):
    db_file = tmp_path / "test_batch_cache.db"
    return SQLiteCache(db_path=str(db_file))


@pytest.fixture
def resolver(temp_cache):
    return EntityResolver(cache=temp_cache)


@pytest.mark.asyncio
async def test_resolve_batch_direct_list(resolver):
    """Test concurrent batch resolution of heterogeneous queries."""
    queries = ["TP53", "HER2", "BRCA1", "7157", "P04637", "NONEXISTENT_XYZ_999"]
    summary = await resolver.resolve_batch(queries=queries, taxon_id=9606, concurrency=5)

    assert isinstance(summary, BatchResolutionSummary)
    assert summary.total_queries == 6
    assert summary.resolved_count >= 5
    assert summary.unresolved_count == 1
    assert summary.success_rate >= 0.8
    assert summary.execution_time_seconds > 0.0
    assert len(summary.results) == 6

    # Verify resolution accuracy
    results_map = {r.query: r for r in summary.results}
    assert results_map["TP53"].resolved_entity.symbol == "TP53"
    assert results_map["HER2"].resolved_entity.symbol == "ERBB2"
    assert results_map["BRCA1"].resolved_entity.symbol == "BRCA1"
    assert results_map["7157"].resolved_entity.symbol == "TP53"
    assert results_map["P04637"].resolved_entity.symbol == "TP53"
    assert results_map["NONEXISTENT_XYZ_999"].match_status == "unresolved"


@pytest.mark.asyncio
async def test_resolve_batch_empty_list(resolver):
    """Test batch resolution with empty query list."""
    summary = await resolver.resolve_batch(queries=[], taxon_id=9606)
    assert summary.total_queries == 0
    assert summary.resolved_count == 0
    assert summary.success_rate == 0.0
    assert len(summary.results) == 0


@pytest.mark.asyncio
async def test_mcp_batch_resolve_genes_tool():
    """Test MCP server batch_resolve_genes tool with concurrency."""
    queries = ["TP53", "EGFR", "KRAS"]
    raw_json = await batch_resolve_genes(queries=queries, concurrency=3)
    data = json.loads(raw_json)

    assert data["total_queries"] == 3
    assert data["resolved_count"] == 3
    assert data["success_rate"] == 1.0
    assert len(data["results"]) == 3
