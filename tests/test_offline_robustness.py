"""Offline robustness tests for the graph builder, traversal engine, store, CLI and REST API.

[SYNTHETIC MOCK / SIMULATION]
Everything below uses test doubles with fictional identifiers (gene FAKEG1, accession
Q00000, disease IDs FAKE:*). They verify software behaviour (error visibility, matching
rules, scoring arithmetic, input validation) and make no biological claim. They do not
touch the network, so they are deterministic and independent of upstream API outages.
"""

import asyncio
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from biocontext.api import BioContextAPIHandler, start_event_loop_thread
from biocontext.cli import build_parser
from biocontext.graph.builder import KnowledgeGraphBuilder
from biocontext.graph.models import EdgeType, GraphEdge, GraphNode, NodeType, Provenance
from biocontext.graph.store import InMemoryGraphStore
from biocontext.graph.traversal import TraversalEngine, match_target_nodes
from biocontext.schemas import (
    FunctionalAnnotation,
    GeneEntity,
    GOAnnotation,
    LiteratureContext,
    PathwayContext,
    PathwayEntity,
    PublicationEntity,
    ResolutionResult,
    TargetAssociationContext,
    TargetDiseaseAssociation,
)


class StubResolver:
    """[SYNTHETIC MOCK] Resolver double returning fixed fictional data."""

    def __init__(self, fail_pathways=False, resolvable=True):
        self.fail_pathways = fail_pathways
        self.resolvable = resolvable

    async def resolve(self, query, taxon_id=9606, context=None):
        if not self.resolvable:
            return ResolutionResult(query=query, match_status="unresolved", confidence_score=0.0)
        gene = GeneEntity(
            symbol="FAKEG1",
            hgnc_id="HGNC:0",
            ensembl_gene_id="ENSG00000000000",
            uniprot_ids=["Q00000"],
        )
        return ResolutionResult(query=query, match_status="exact", confidence_score=0.99, resolved_entity=gene)

    async def get_pathways(self, query, **kwargs):
        if self.fail_pathways:
            raise RuntimeError("simulated pathway outage")
        return PathwayContext(
            query=query,
            pathways=[PathwayEntity(st_id="R-FAKE-1", name="Fake apoptosis signalling")],
            total_pathways=1,
        )

    async def annotate_gene(self, query, **kwargs):
        return FunctionalAnnotation(
            query=query,
            biological_processes=[GOAnnotation(go_id="GO:0000001", name="fake process", aspect="biological_process")],
            molecular_functions=[GOAnnotation(go_id="GO:0000002", name="fake function", aspect="molecular_function")],
        )

    async def get_target_diseases(self, query, **kwargs):
        return TargetAssociationContext(
            query=query,
            associations=[
                TargetDiseaseAssociation(disease_id="FAKE:0001", disease_name="fake colorectal cancer", score=0.8),
                TargetDiseaseAssociation(disease_id="FAKE:0002", disease_name="fake cancerous lesion", score=0.5),
            ],
        )

    async def get_supporting_publications(self, query, **kwargs):
        return LiteratureContext(
            query=query,
            publications=[PublicationEntity(pmid="1", title="Guidelines for cancer care in general")],
        )


class StubResolverWithoutGO(StubResolver):
    """[SYNTHETIC MOCK] Same as StubResolver but the GO method is missing, reproducing the v0.8.0 bug class."""

    annotate_gene = None


@pytest.mark.asyncio
async def test_builder_reports_layer_failure_instead_of_hiding_it():
    builder = KnowledgeGraphBuilder(resolver=StubResolver(fail_pathways=True))
    sub = await builder.build_gene_subgraph("FAKEG1")

    assert sub.layer_status["pathways"].startswith("failed:")
    assert any("Pathway layer failed" in w for w in sub.warnings)
    assert sub.layer_status["go"] == "ok"
    assert sub.layer_status["diseases"] == "ok"
    assert not any(n.node_type == NodeType.PATHWAY for n in sub.nodes)


@pytest.mark.asyncio
async def test_builder_go_layer_failure_is_visible_when_method_missing():
    builder = KnowledgeGraphBuilder(resolver=StubResolverWithoutGO())
    sub = await builder.build_gene_subgraph("FAKEG1")
    assert sub.layer_status["go"].startswith("failed:")


@pytest.mark.asyncio
async def test_builder_go_layer_adds_nodes_when_available():
    builder = KnowledgeGraphBuilder(resolver=StubResolver())
    sub = await builder.build_gene_subgraph("FAKEG1")
    go_nodes = [n for n in sub.nodes if n.node_type == NodeType.GO_TERM]
    assert len(go_nodes) == 2
    assert sub.layer_status["go"] == "ok"


@pytest.mark.asyncio
async def test_builder_does_not_invent_scores():
    builder = KnowledgeGraphBuilder(resolver=StubResolver())
    sub = await builder.build_gene_subgraph("FAKEG1")

    by_type = {}
    for e in sub.edges:
        by_type.setdefault(e.edge_type, []).append(e)

    assert all(e.weight is None for e in by_type[EdgeType.ENCODES])
    assert all(e.weight is None for e in by_type[EdgeType.PARTICIPATES_IN])
    assert all(e.weight is None for e in by_type[EdgeType.CITED_IN])
    assert all(e.properties["relation_basis"] == "keyword_search_hit" for e in by_type[EdgeType.CITED_IN])
    assert sorted(e.weight for e in by_type[EdgeType.ASSOCIATED_WITH]) == [0.5, 0.8]


@pytest.mark.asyncio
async def test_builder_unresolved_seed_warns_and_builds_no_layers():
    builder = KnowledgeGraphBuilder(resolver=StubResolver(resolvable=False))
    sub = await builder.build_gene_subgraph("NOTAGENE")
    assert sub.root_node_id == "unresolved:NOTAGENE"
    assert sub.total_nodes == 1
    assert sub.layer_status == {}
    assert any("could not be resolved" in w for w in sub.warnings)


def _nodes():
    return [
        GraphNode(id="gene:FAKEG1", name="FAKEG1", node_type=NodeType.GENE),
        GraphNode(id="disease:FAKE:0001", name="fake colorectal cancer", node_type=NodeType.DISEASE,
                  properties={"disease_id": "FAKE:0001"}),
        GraphNode(id="disease:FAKE:0002", name="fake cancerous lesion", node_type=NodeType.DISEASE,
                  properties={"disease_id": "FAKE:0002"}),
        GraphNode(id="pub:1", name="Guidelines for cancer care in general", node_type=NodeType.PUBLICATION,
                  properties={"pmid": "1"}),
        GraphNode(id="pathway:R-FAKE-1", name="Fake apoptosis signalling", node_type=NodeType.PATHWAY,
                  properties={"st_id": "R-FAKE-1"}),
    ]


def test_target_matching_uses_whole_words_and_excludes_publications():
    matched = {n.id for n in match_target_nodes(_nodes(), "cancer")}
    assert matched == {"disease:FAKE:0001"}  # not 'cancerous', not the publication title


def test_target_matching_by_identifier_and_type():
    assert [n.id for n in match_target_nodes(_nodes(), "FAKE:0002")] == ["disease:FAKE:0002"]
    assert [n.id for n in match_target_nodes(_nodes(), "r-fake-1")] == ["pathway:R-FAKE-1"]
    assert match_target_nodes(_nodes(), "cancer", target_type=NodeType.PATHWAY) == []
    pubs = match_target_nodes(_nodes(), "cancer", target_type=NodeType.PUBLICATION)
    assert [n.id for n in pubs] == ["pub:1"]


def test_target_matching_ignores_free_text_properties():
    nodes = [GraphNode(id="x:1", name="alpha", node_type=NodeType.PATHWAY, properties={"note": "cancer"})]
    assert match_target_nodes(nodes, "cancer") == []


@pytest.mark.asyncio
async def test_traversal_scores_and_explanations():
    engine = TraversalEngine(resolver=StubResolver())
    result = await engine.traverse("FAKEG1", "cancer", max_hops=3, target_type=NodeType.DISEASE)

    assert result.matched_targets == ["disease:FAKE:0001"]
    assert result.total_paths == 1
    path = result.paths_found[0]
    assert path.cumulative_score == pytest.approx(0.8)
    assert path.scored_hops == 1
    assert "score=0.80" in path.human_explanation
    assert "source=OpenTargets" in path.human_explanation


@pytest.mark.asyncio
async def test_traversal_unscored_path_has_no_score():
    engine = TraversalEngine(resolver=StubResolver())
    result = await engine.traverse("FAKEG1", "R-FAKE-1", max_hops=3)
    assert result.total_paths == 1
    path = result.paths_found[0]
    assert path.cumulative_score is None
    assert path.scored_hops == 0
    assert "unscored" in path.human_explanation
    assert path.hop_count == 2  # gene -> protein -> pathway


@pytest.mark.asyncio
async def test_traversal_no_match_produces_warning():
    engine = TraversalEngine(resolver=StubResolver())
    result = await engine.traverse("FAKEG1", "nonexistent phrase")
    assert result.total_paths == 0
    assert any("No node in the subgraph" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_traversal_propagates_layer_warnings():
    engine = TraversalEngine(resolver=StubResolver(fail_pathways=True))
    result = await engine.traverse("FAKEG1", "cancer", target_type=NodeType.DISEASE)
    assert any("Pathway layer failed" in w for w in result.warnings)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"source_query": "", "target_query": "x"},
        {"source_query": "FAKEG1", "target_query": "  "},
        {"source_query": "FAKEG1", "target_query": "x", "max_hops": 0},
        {"source_query": "FAKEG1", "target_query": "x", "max_hops": 99},
        {"source_query": "FAKEG1", "target_query": "x", "min_score": 1.5},
    ],
)
async def test_traversal_rejects_invalid_input(kwargs):
    engine = TraversalEngine(resolver=StubResolver())
    with pytest.raises(ValueError):
        await engine.traverse(**kwargs)


def test_store_find_paths_treats_unscored_edges_as_neutral_and_avoids_cycles():
    store = InMemoryGraphStore()
    for nid in ("a", "b", "c"):
        store.add_node(GraphNode(id=nid, name=nid, node_type=NodeType.GENE))
    store.add_edge(GraphEdge(source_id="a", target_id="b", edge_type=EdgeType.INTERACTS_WITH))
    store.add_edge(GraphEdge(source_id="b", target_id="c", edge_type=EdgeType.INTERACTS_WITH, weight=0.6))
    store.add_edge(GraphEdge(source_id="c", target_id="a", edge_type=EdgeType.INTERACTS_WITH, weight=0.9))

    assert len(store.find_paths("a", "c", max_hops=2, min_cumulative_score=0.5)) == 1
    assert store.find_paths("a", "c", max_hops=2, min_cumulative_score=0.7) == []
    assert store.find_paths("a", "a", max_hops=3) == []  # no trivial or cyclic self path


def test_store_find_paths_validates_arguments():
    store = InMemoryGraphStore()
    with pytest.raises(ValueError):
        store.find_paths("a", "b", max_hops=0)
    with pytest.raises(ValueError):
        store.find_paths("a", "b", max_hops=InMemoryGraphStore.MAX_ALLOWED_HOPS + 1)
    with pytest.raises(ValueError):
        store.find_paths("a", "b", min_cumulative_score=-0.1)


def test_provenance_confidence_may_be_absent():
    assert Provenance(source_database="X").confidence is None
    assert GraphEdge(source_id="a", target_id="b", edge_type=EdgeType.ENCODES).weight is None


def test_cli_accepts_documented_serve_command_and_legacy_alias():
    parser = build_parser()
    assert parser.parse_args(["serve"]).command == "serve"
    assert parser.parse_args(["server"]).command == "server"


@pytest.mark.asyncio
async def test_mcp_traverse_tool_returns_error_json_for_invalid_input():
    from biocontext.server import traverse_biological_graph

    bad_type = json.loads(await traverse_biological_graph("FAKEG1", "x", target_type="banana"))
    assert "Invalid target_type" in bad_type["error"]

    bad_hops = json.loads(await traverse_biological_graph("FAKEG1", "x", max_hops=0))
    assert "max_hops" in bad_hops["error"]


class _Dumpable:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return self._payload


class StubClient:
    """[SYNTHETIC MOCK] BioContext client double for exercising the HTTP layer only."""

    async def resolve_gene(self, symbol):
        await asyncio.sleep(0.5)
        return _Dumpable({"query": symbol})

    async def get_protein(self, accession):
        return None

    async def traverse(self, source, target, max_hops=3, min_score=0.0, target_type=None):
        return _Dumpable({"source": source, "target": target, "max_hops": max_hops,
                          "min_score": min_score, "target_type": target_type.value if target_type else None})


@pytest.fixture
def api_base():
    loop = start_event_loop_thread()
    handler = type("TestHandler", (BioContextAPIHandler,), {"client": StubClient(), "loop": loop, "cors_origin": None})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    loop.call_soon_threadsafe(loop.stop)


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read().decode())


@pytest.mark.parametrize(
    "path,status",
    [
        ("/v1/traverse", 400),
        ("/v1/traverse?source=A", 400),
        ("/v1/traverse?source=A&target=B&max_hops=abc", 400),
        ("/v1/traverse?source=A&target=B&max_hops=0", 400),
        ("/v1/traverse?source=A&target=B&max_hops=7", 400),
        ("/v1/traverse?source=A&target=B&min_score=2", 400),
        ("/v1/traverse?source=A&target=B&target_type=banana", 400),
        ("/v1/gene/", 400),
        ("/v1/protein/Q99999", 404),
        ("/v1/unknown", 404),
    ],
)
def test_api_rejects_bad_requests_with_json_errors(api_base, path, status):
    code, _, body = _get(api_base + path)
    assert code == status
    assert "error" in body


def test_api_valid_traverse_passes_validated_parameters(api_base):
    code, _, body = _get(api_base + "/v1/traverse?source=A&target=B&max_hops=2&min_score=0.5&target_type=Disease")
    assert code == 200
    assert body == {"source": "A", "target": "B", "max_hops": 2, "min_score": 0.5, "target_type": "disease"}


def test_api_has_no_cors_header_by_default(api_base):
    _, headers, _ = _get(api_base + "/health")
    assert "Access-Control-Allow-Origin" not in headers


def test_api_serves_concurrent_requests_in_parallel(api_base):
    results = []

    def call():
        results.append(_get(api_base + "/v1/gene/FAKEG1")[0])

    start = time.perf_counter()
    threads = [threading.Thread(target=call) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start

    assert results == [200, 200, 200, 200]
    assert elapsed < 1.5, f"requests were serialised (elapsed={elapsed:.2f}s, serial would be ~2.0s)"
