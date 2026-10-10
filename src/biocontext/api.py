"""Lightweight REST API v1 server for BioContext (PRD-18).

Runs standalone using Python's standard library http.server and asyncio,
ensuring zero extra heavy dependencies (FastAPI/Starlette not required).
"""

import asyncio
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
from typing import Any, Dict

from biocontext import BioContext
from biocontext.logging import get_logger

logger = get_logger("api")


class BioContextAPIHandler(BaseHTTPRequestHandler):
    """Handler for REST API v1 endpoints."""

    client: BioContext = None  # Injected during startup
    loop: asyncio.AbstractEventLoop = None

    def _send_json(self, data: Any, status: int = HTTPStatus.OK):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = HTTPStatus.BAD_REQUEST):
        self._send_json({"error": message, "status_code": status}, status=status)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # Healthcheck
        if path == "/health" or path == "":
            return self._send_json({"status": "ok", "version": "1.0.0", "service": "BioContext API v1"})

        # GET /v1/gene/{symbol}
        if path.startswith("/v1/gene/"):
            symbol = path.replace("/v1/gene/", "").strip()
            if not symbol:
                return self._send_error_json("Gene symbol is required")

            res = self.loop.run_until_complete(self.client.resolve_gene(symbol))
            return self._send_json(res.model_dump())

        # GET /v1/protein/{accession}
        if path.startswith("/v1/protein/"):
            accession = path.replace("/v1/protein/", "").strip()
            protein = self.loop.run_until_complete(self.client.get_protein(accession))
            if not protein:
                return self._send_error_json(f"Protein '{accession}' not found", status=HTTPStatus.NOT_FOUND)
            return self._send_json(protein.model_dump())

        # GET /v1/disease/{query}
        if path.startswith("/v1/disease/"):
            disease_q = path.replace("/v1/disease/", "").strip()
            diseases = self.loop.run_until_complete(self.client.resolve_disease(disease_q))
            return self._send_json([d.model_dump() for d in diseases])

        # GET /v1/graph/{symbol}
        if path.startswith("/v1/graph/"):
            symbol = path.replace("/v1/graph/", "").strip()
            subgraph = self.loop.run_until_complete(self.client.build_subgraph(symbol))
            return self._send_json(subgraph.model_dump())

        # GET /v1/traverse?source=TP53&target=cancer
        if path == "/v1/traverse":
            source = query_params.get("source", [""])[0].strip()
            target = query_params.get("target", [""])[0].strip()
            max_hops = int(query_params.get("max_hops", [3])[0])

            if not source or not target:
                return self._send_error_json("Both 'source' and 'target' query parameters are required")

            res = self.loop.run_until_complete(self.client.traverse(source, target, max_hops=max_hops))
            return self._send_json(res.model_dump())

        return self._send_error_json("Endpoint not found", status=HTTPStatus.NOT_FOUND)


def run_api_server(host: str = "127.0.0.1", port: int = 8000):
    """Launch the lightweight REST API v1 server."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = BioContext()

    BioContextAPIHandler.client = client
    BioContextAPIHandler.loop = loop

    server = HTTPServer((host, port), BioContextAPIHandler)
    logger.info(f"BioContext REST API v1 listening at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down REST API server...")
    finally:
        server.server_close()
