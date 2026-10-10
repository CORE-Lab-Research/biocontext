"""Lightweight REST API v1 server for BioContext (PRD-18).

Uses the standard library only. Requests are served by a threaded HTTP server and
all coroutines run on one dedicated asyncio event loop, so a slow upstream call
does not block other requests. The API is read-only and unauthenticated: bind it
to localhost (the default) or place it behind an authenticating reverse proxy.
"""

import asyncio
import json
import threading
import urllib.parse
from concurrent.futures import TimeoutError as FutureTimeoutError
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from biocontext import BioContext
from biocontext.graph.models import NodeType
from biocontext.logging import get_logger

logger = get_logger("api")

API_VERSION = "1.0.1"
REQUEST_TIMEOUT_SEC = 120.0
MAX_PATH_PARAM_LEN = 200


class ApiError(Exception):
    """Error with an HTTP status that is reported to the client as JSON."""

    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = int(status)


def _match_path_param(raw_path: str, base_route: str, name: str) -> Optional[str]:
    """Extract a path parameter after base_route, raising 400 if empty."""
    stripped = raw_path.rstrip("/")
    if stripped == base_route:
        raise ApiError(f"{name} is required")
    prefix = base_route + "/"
    if raw_path.startswith(prefix):
        raw = urllib.parse.unquote(raw_path[len(prefix):]).strip().strip("/")
        if not raw:
            raise ApiError(f"{name} is required")
        if len(raw) > MAX_PATH_PARAM_LEN:
            raise ApiError(f"{name} exceeds {MAX_PATH_PARAM_LEN} characters")
        return raw
    return None


def _int_param(params: Dict[str, list], key: str, default: int, low: int, high: int) -> int:
    values = params.get(key)
    if not values:
        return default
    try:
        value = int(values[0])
    except ValueError:
        raise ApiError(f"Query parameter '{key}' must be an integer")
    if not low <= value <= high:
        raise ApiError(f"Query parameter '{key}' must be between {low} and {high}")
    return value


def _float_param(params: Dict[str, list], key: str, default: float, low: float, high: float) -> float:
    values = params.get(key)
    if not values:
        return default
    try:
        value = float(values[0])
    except ValueError:
        raise ApiError(f"Query parameter '{key}' must be a number")
    if not low <= value <= high:
        raise ApiError(f"Query parameter '{key}' must be between {low} and {high}")
    return value


class BioContextAPIHandler(BaseHTTPRequestHandler):
    """Handler for REST API v1 endpoints."""

    client: Optional[BioContext] = None
    loop: Optional[asyncio.AbstractEventLoop] = None
    cors_origin: Optional[str] = None

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if self.cors_origin:
            self.send_header("Access-Control-Allow-Origin", self.cors_origin)
        self.end_headers()
        self.wfile.write(body)

    def _run(self, coro: Any) -> Any:
        if self.loop is None or self.client is None:
            raise ApiError("Server is not initialised", HTTPStatus.SERVICE_UNAVAILABLE)
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        try:
            return future.result(timeout=REQUEST_TIMEOUT_SEC)
        except FutureTimeoutError:
            future.cancel()
            raise ApiError("Upstream request timed out", HTTPStatus.GATEWAY_TIMEOUT)

    def do_GET(self) -> None:
        try:
            self._route()
        except ApiError as e:
            self._send_json({"error": str(e), "status_code": e.status}, status=e.status)
        except Exception as e:
            logger.error("Unhandled API error | path=%s error=%s", self.path, e, exc_info=True)
            self._send_json(
                {"error": "Internal server error", "status_code": HTTPStatus.INTERNAL_SERVER_ERROR},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _route(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        raw_path = parsed.path
        norm_path = raw_path.rstrip("/")
        params = urllib.parse.parse_qs(parsed.query)

        if norm_path in ("", "/health"):
            self._send_json({"status": "ok", "version": API_VERSION, "service": "BioContext API v1"})
            return

        symbol = _match_path_param(raw_path, "/v1/gene", "Gene symbol")
        if symbol is not None:
            result = self._run(self.client.resolve_gene(symbol))
            self._send_json(result.model_dump())
            return

        accession = _match_path_param(raw_path, "/v1/protein", "Protein accession")
        if accession is not None:
            protein = self._run(self.client.get_protein(accession))
            if not protein:
                raise ApiError(f"Protein '{accession}' not found", HTTPStatus.NOT_FOUND)
            self._send_json(protein.model_dump())
            return

        query = _match_path_param(raw_path, "/v1/disease", "Disease query")
        if query is not None:
            limit = _int_param(params, "limit", 5, 1, 25)
            diseases = self._run(self.client.resolve_disease(query, limit=limit))
            self._send_json([d.model_dump() for d in diseases])
            return

        graph_symbol = _match_path_param(raw_path, "/v1/graph", "Gene symbol")
        if graph_symbol is not None:
            subgraph = self._run(self.client.build_subgraph(graph_symbol))
            self._send_json(subgraph.model_dump())
            return

        if norm_path == "/v1/traverse":
            source = params.get("source", [""])[0].strip()
            target = params.get("target", [""])[0].strip()
            if not source or not target:
                raise ApiError("Both 'source' and 'target' query parameters are required")
            max_hops = _int_param(params, "max_hops", 3, 1, 6)
            min_score = _float_param(params, "min_score", 0.0, 0.0, 1.0)
            raw_type = params.get("target_type", [""])[0].strip().lower()
            node_type = None
            if raw_type:
                try:
                    node_type = NodeType(raw_type)
                except ValueError:
                    valid = ", ".join(t.value for t in NodeType)
                    raise ApiError(f"Invalid target_type '{raw_type}'. Valid values: {valid}")
            result = self._run(
                self.client.traverse(source, target, max_hops=max_hops, min_score=min_score, target_type=node_type)
            )
            self._send_json(result.model_dump())
            return

        raise ApiError("Endpoint not found", HTTPStatus.NOT_FOUND)


def start_event_loop_thread() -> asyncio.AbstractEventLoop:
    """Start a dedicated asyncio loop in a daemon thread and return it."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, name="biocontext-api-loop", daemon=True)
    thread.start()
    return loop


def run_api_server(host: str = "127.0.0.1", port: int = 8000, cors_origin: Optional[str] = None) -> None:
    """Launch the REST API v1 server until interrupted."""
    loop = start_event_loop_thread()
    BioContextAPIHandler.client = BioContext()
    BioContextAPIHandler.loop = loop
    BioContextAPIHandler.cors_origin = cors_origin

    server = ThreadingHTTPServer((host, port), BioContextAPIHandler)
    server.daemon_threads = True
    logger.info("BioContext REST API v%s listening | url=http://%s:%d cors_origin=%s", API_VERSION, host, port, cors_origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down REST API server")
    finally:
        server.server_close()
        loop.call_soon_threadsafe(loop.stop)
