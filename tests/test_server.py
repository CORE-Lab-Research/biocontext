"""Tests for FastMCP server tools."""

import json
import pytest
from biocontext.server import batch_resolve_genes, find_orthologs, get_protein_info, get_transcripts, resolve_gene


@pytest.mark.asyncio
async def test_mcp_tool_resolve_gene():
    res_str = await resolve_gene("TP53")
    res = json.loads(res_str)
    assert res["match_status"] == "exact"
    assert res["resolved_entity"]["symbol"] == "TP53"


@pytest.mark.asyncio
async def test_mcp_tool_get_protein():
    res_str = await get_protein_info("P04637")
    res = json.loads(res_str)
    assert res["accession"] == "P04637"
    assert "Cellular tumor antigen p53" in res["name"]


@pytest.mark.asyncio
async def test_mcp_tool_batch_resolve():
    res_str = await batch_resolve_genes(["TP53", "HER2"])
    res = json.loads(res_str)
    assert len(res) == 2
    symbols = [item["resolved_entity"]["symbol"] for item in res if item["resolved_entity"]]
    assert "TP53" in symbols
    assert "ERBB2" in symbols


@pytest.mark.asyncio
async def test_mcp_tool_get_transcripts():
    res_str = await get_transcripts("TP53")
    res = json.loads(res_str)
    assert res["symbol"] == "TP53"
    assert res["ensembl_gene_id"] == "ENSG00000141510"
    assert len(res["transcripts"]) > 0


@pytest.mark.asyncio
async def test_mcp_tool_find_orthologs():
    res_str = await find_orthologs("TP53", target_species="mus_musculus")
    res = json.loads(res_str)
    assert len(res) > 0
    assert res[0]["target_gene_id"] == "ENSMUSG00000059552"
    assert res[0]["target_species"] == "mus_musculus"


