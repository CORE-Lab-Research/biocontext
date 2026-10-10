import pytest
from biocontext import BioContext, NodeType
from biocontext.api import BioContextAPIHandler
from http import HTTPStatus


@pytest.mark.asyncio
async def test_sdk_client_get_gene_and_protein():
    bc = BioContext()
    gene = await bc.get_gene("TP53")
    assert gene is not None
    assert gene.symbol == "TP53"
    assert gene.hgnc_id == "HGNC:11998"

    protein = await bc.get_protein("P04637")
    assert protein is not None
    assert protein.accession == "P04637"
    assert "tumor protein p53" in protein.name.lower() or "cellular tumor antigen p53" in protein.name.lower()


@pytest.mark.asyncio
async def test_sdk_client_subgraph_and_traverse():
    bc = BioContext()
    subgraph = await bc.build_subgraph("TP53", include_literature=False)
    assert subgraph.root_node_id == "gene:TP53"
    assert subgraph.total_nodes > 1

    traversal = await bc.traverse("TP53", "cancer", target_type=NodeType.DISEASE, max_hops=3)
    assert traversal.source_query == "TP53"
    assert traversal.total_paths >= 1
    assert "TP53" in traversal.paths_found[0].human_explanation


def test_api_handler_health():
    import urllib.request
    import threading
    from http.server import HTTPServer
    from biocontext.api import API_VERSION, start_event_loop_thread
    import json

    loop = start_event_loop_thread()
    client = BioContext()
    BioContextAPIHandler.client = client
    BioContextAPIHandler.loop = loop

    # Bind to ephemeral port
    server = HTTPServer(("127.0.0.1", 0), BioContextAPIHandler)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        url = f"http://127.0.0.1:{port}/health"
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.status == 200
            data = json.loads(response.read().decode())
            assert data["status"] == "ok"
            assert data["version"] == API_VERSION
    finally:
        server.shutdown()
        server.server_close()
