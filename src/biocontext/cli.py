"""Command-line interface (CLI) driven dynamically by CLI_COMMANDS_REGISTRY.
Allows seamless addition and modification of subcommands from config.py without touching execution plumbing.
"""

import argparse
import asyncio
import json
import sys

from biocontext.config import CLI_COMMANDS_REGISTRY
from biocontext.logging import setup_logging
from biocontext.resolver import EntityResolver
from biocontext.schemas import ResolutionContext
from biocontext.server import mcp


def build_parser() -> argparse.ArgumentParser:
    """Dynamically construct argument parser from declarative registry in config.py."""
    parser = argparse.ArgumentParser(
        prog="biocontext",
        description="Authoritative Biological Entity Resolution & Contextual Intelligence Framework."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    for cmd in CLI_COMMANDS_REGISTRY:
        cmd_name = cmd["name"]
        cmd_help = cmd.get("help", "")

        if "subcommands" in cmd:
            sub = subparsers.add_parser(cmd_name, help=cmd_help)
            nested = sub.add_subparsers(dest=f"{cmd_name}_action", help=f"{cmd_name} action")
            for subcmd in cmd["subcommands"]:
                nested.add_parser(subcmd["name"], help=subcmd.get("help", ""))
        else:
            sub = subparsers.add_parser(cmd_name, help=cmd_help)
            for arg in cmd.get("arguments", []):
                flags = arg["flags"]
                kwargs = {k: v for k, v in arg.items() if k != "flags"}
                sub.add_argument(*flags, **kwargs)

    return parser


async def run_cli_async(args: argparse.Namespace) -> int:
    resolver = EntityResolver()

    if args.command == "resolve":
        context = None
        if getattr(args, "chrom", None) or getattr(args, "locus_type", None):
            context = ResolutionContext(
                chromosome=getattr(args, "chrom", None),
                locus_type=getattr(args, "locus_type", None)
            )

        res = await resolver.resolve(args.query, taxon_id=args.taxon, context=context)
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

    elif args.command == "cache":
        cache = resolver.cache
        if args.cache_action == "clear":
            count = cache.clear()
            print(f"Purged {count} cached entries from {cache.db_path}")
            return 0
        else:
            print(json.dumps(cache.stats(), indent=2))
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
    elif args.command == "bench":
        import pytest
        sys.exit(pytest.main(["tests/test_benchmark.py", "-v"]))
    elif args.command == "test":
        import pytest
        sys.exit(pytest.main(["tests/", "-v"]))
    elif args.command in ("resolve", "batch", "protein", "cache"):
        sys.exit(asyncio.run(run_cli_async(args)))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
