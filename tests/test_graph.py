"""Unit and integration tests for BioContext Knowledge Graph (PRD-21)."""

import pytest
from biocontext.graph.builder import KnowledgeGraphBuilder
from biocontext.graph.models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    Provenance,
    SubGraphContext,
)
from biocontext.graph.store import InMemoryGraphStore
from biocontext.resolver import EntityResolver


def test_graph_store_add_and_query():
    store = InMemoryGraphStore()

    gene_node = GraphNode(
        id="gene:TP53",
        name="TP53",
        node_type=NodeType.GENE,
        properties={"hgnc_id": "HGNC:11998"},
        provenance=Provenance(source_database="HGNC", confidence=1.0),
    )
    protein_node = GraphNode(
        id="protein:P04637",
        name="TP53 (P04637)",
        node_type=NodeType.PROTEIN,
        properties={"accession": "P04637"},
        provenance=Provenance(source_database="UniProt", confidence=1.0),
    )
    disease_node = GraphNode(
        id="disease:MONDO:0018875",
        name="Li-Fraumeni syndrome",
        node_type=NodeType.DISEASE,
        properties={"mondo_id": "MONDO:0018875"},
        provenance=Provenance(source_database="MONDO", confidence=1.0),
    )

    store.add_node(gene_node)
    store.add_node(protein_node)
    store.add_node(disease_node)

    assert store.node_count == 3
    assert store.get_node("gene:TP53") is not None

    # Add edges
    edge_encodes = GraphEdge(
        source_id="gene:TP53",
        target_id="protein:P04637",
        edge_type=EdgeType.ENCODES,
        weight=1.0,
    )
    edge_assoc = GraphEdge(
        source_id="gene:TP53",
        target_id="disease:MONDO:0018875",
        edge_type=EdgeType.ASSOCIATED_WITH,
        weight=0.95,
    )

    store.add_edge(edge_encodes)
    store.add_edge(edge_assoc)

    assert store.edge_count == 2

    # Query outgoing
    outgoing = store.get_outgoing_edges("gene:TP53")
    assert len(outgoing) == 2

    # Filtered by edge_type
    encodes_edges = store.get_outgoing_edges("gene:TP53", edge_type=EdgeType.ENCODES)
    assert len(encodes_edges) == 1
    assert encodes_edges[0].target_id == "protein:P04637"

    # Query neighbors
    neighbors = store.get_neighbors("gene:TP53", direction="out")
    assert len(neighbors) == 2

    # Subgraph extraction
    subgraph: SubGraphContext = store.get_subgraph("gene:TP53", max_depth=1)
    assert subgraph.total_nodes == 3
    assert subgraph.total_edges == 2
    assert subgraph.root_node_id == "gene:TP53"


@pytest.mark.asyncio
async def test_knowledge_graph_builder_tp53():
    resolver = EntityResolver()
    builder = KnowledgeGraphBuilder(resolver=resolver)

    subgraph = await builder.build_gene_subgraph(
        query="TP53",
        include_pathways=True,
        include_go=True,
        include_diseases=True,
        include_literature=True,
        limit_diseases=3,
        limit_pathways=3,
        limit_literature=3,
    )

    assert subgraph.root_node_id == "gene:TP53"
    assert subgraph.total_nodes > 1
    assert subgraph.total_edges > 1

    node_types = {n.node_type for n in subgraph.nodes}
    assert NodeType.GENE in node_types
    assert NodeType.PROTEIN in node_types

    edge_types = {e.edge_type for e in subgraph.edges}
    assert EdgeType.ENCODES in edge_types

    # Provenance verification
    for n in subgraph.nodes:
        if n.provenance:
            assert n.provenance.source_database is not None
            assert 0.0 <= n.provenance.confidence <= 1.0


@pytest.mark.asyncio
async def test_mcp_tool_build_entity_subgraph():
    from biocontext.server import build_entity_subgraph
    import json

    res_json = await build_entity_subgraph(
        query="BRCA1",
        include_pathways=True,
        include_go=False,
        include_diseases=True,
        include_literature=False,
    )
    data = json.loads(res_json)
    assert data["root_node_id"] == "gene:BRCA1"
    assert len(data["nodes"]) >= 2
    assert len(data["edges"]) >= 1


@pytest.mark.asyncio
async def test_traversal_engine_find_paths():
    from biocontext.graph.traversal import TraversalEngine
    resolver = EntityResolver()
    engine = TraversalEngine(resolver=resolver)

    result = await engine.traverse(
        source_query="TP53",
        target_query="cancer",
        max_hops=3,
    )

    assert result.source_query == "TP53"
    assert result.target_query == "cancer"
    assert result.total_paths >= 1
    top_path = result.paths_found[0]
    assert top_path.start_node_id == "gene:TP53"
    assert top_path.hop_count >= 1
    assert "TP53" in top_path.human_explanation
    assert len(top_path.steps) == top_path.hop_count


@pytest.mark.asyncio
async def test_mcp_tool_traverse_biological_graph():
    from biocontext.server import traverse_biological_graph
    import json

    res_json = await traverse_biological_graph(
        source_query="TP53",
        target_query="PUMA",
        max_hops=3,
    )
    data = json.loads(res_json)
    assert data["source_query"] == "TP53"
    assert "paths_found" in data

