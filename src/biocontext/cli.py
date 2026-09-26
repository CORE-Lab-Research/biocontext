"""Command-line interface (CLI) for direct terminal testing and execution."""

import argparse
import asyncio
import json
import sys

from biocontext.logging import setup_logging
from biocontext.resolver import EntityResolver
from biocontext.server import mcp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="biocontext",
        description="Authoritative Biological Entity Resolution & Contextual Intelligence Framework."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: server (Default MCP stdio server)
    subparsers.add_parser("server", help="Run the Model Context Protocol (MCP) stdio server")

    # Command: resolve (CLI query)
    resolve_parser = subparsers.add_parser("resolve", help="Resolve a single gene/protein query")
    resolve_parser.add_argument("query", help="Gene symbol, alias, or identifier (e.g. TP53, HER2, 7157)")
    resolve_parser.add_argument("--taxon", type=int, default=9606, help="NCBI Taxonomy ID (default: 9606 for human)")

    # Command: batch (CLI batch resolution)
    batch_parser = subparsers.add_parser("batch", help="Resolve multiple queries in batch")
    batch_parser.add_argument("queries", nargs="+", help="Space-separated list of symbols or IDs")
    batch_parser.add_argument("--taxon", type=int, default=9606, help="NCBI Taxonomy ID (default: 9606 for human)")

    # Command: protein (UniProt lookup)
    protein_parser = subparsers.add_parser("protein", help="Fetch UniProt protein metadata by accession")
    protein_parser.add_argument("accession", help="UniProt accession ID (e.g. P04637)")

    return parser


async def run_cli_async(args: argparse.Namespace) -> int:
    resolver = EntityResolver()

    if args.command == "resolve":
        res = await resolver.resolve(args.query, taxon_id=args.taxon)
        print(res.model_dump_json(indent=2))
        return 0

    elif args.command == "batch":
        tasks = [resolver.resolve(q, taxon_id=args.taxon) for q in args.queries]
        results = await asyncio.gather(*tasks)
        print("[" + ",\n".join(r.model_dump_json(indent=2) for r in results) + "]")
        return 0

    elif args.command == "protein":
        protein = await resolver.uniprot.fetch_by_accession(args.accession)
        if not protein:
            print(json.dumps({"status": "not_found", "accession": args.accession}, indent=2))
            return 1
        print(protein.model_dump_json(indent=2))
        return 0

    return 0


def main():
    setup_logging()
    parser = build_parser()

    # If no arguments provided or 'server' subcommand specified, launch MCP stdio server
    if len(sys.argv) == 1:
        mcp.run(transport="stdio")
        return

    args = parser.parse_args()

    if args.command == "server":
        mcp.run(transport="stdio")
    elif args.command in ("resolve", "batch", "protein"):
        sys.exit(asyncio.run(run_cli_async(args)))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
