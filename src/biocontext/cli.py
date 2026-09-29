"""Command-line interface (CLI) driven dynamically by CLI_COMMANDS_REGISTRY.
Allows seamless addition and modification of subcommands from config.py without touching execution plumbing.
"""

import argparse
import asyncio
import json
import sys
from typing import List

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
        queries: List[str] = list(args.queries) if args.queries else []

        # Load from file if specified
        if getattr(args, "file", None):
            import csv
            from pathlib import Path
            input_path = Path(args.file)
            if not input_path.exists():
                print(json.dumps({"error": f"Input file not found: {args.file}"}, indent=2), file=sys.stderr)
                return 1

            text = input_path.read_text(encoding="utf-8").strip()
            # Check if CSV/TSV or newline delimited
            if "\n" in text or "," in text or "\t" in text:
                delimiter = "," if "," in text else ("\t" if "\t" in text else None)
                if delimiter:
                    reader = csv.reader(text.splitlines(), delimiter=delimiter)
                    for row in reader:
                        for cell in row:
                            cell_clean = cell.strip()
                            if cell_clean and not cell_clean.lower().startswith("gene") and not cell_clean.lower().startswith("symbol"):
                                queries.append(cell_clean)
                else:
                    for line in text.splitlines():
                        line_clean = line.strip()
                        if line_clean and not line_clean.lower().startswith("gene") and not line_clean.lower().startswith("symbol"):
                            queries.append(line_clean)

        if not queries:
            print(json.dumps({"error": "No queries provided. Specify queries as arguments or via --file"}, indent=2), file=sys.stderr)
            return 1

        concurrency = getattr(args, "concurrency", 10)
        summary = await resolver.resolve_batch(queries=queries, taxon_id=args.taxon, concurrency=concurrency)

        # Output formatting
        output_file = getattr(args, "output", None)
        if output_file:
            from pathlib import Path
            out_p = Path(output_file)
            if out_p.suffix.lower() == ".csv":
                import csv
                with open(out_p, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["query", "match_status", "confidence_score", "symbol", "name", "hgnc_id", "ncbi_gene_id", "ensembl_gene_id", "uniprot_ids"])
                    for r in summary.results:
                        ent = r.resolved_entity
                        writer.writerow([
                            r.query,
                            r.match_status,
                            r.confidence_score,
                            ent.symbol if ent else "",
                            ent.name if ent else "",
                            ent.hgnc_id if ent else "",
                            ent.ncbi_gene_id if ent else "",
                            ent.ensembl_gene_id if ent else "",
                            ";".join(ent.uniprot_ids) if ent else ""
                        ])
            else:
                out_p.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
            print(f"Batch resolution completed: {summary.resolved_count}/{summary.total_queries} resolved ({summary.success_rate * 100:.1f}%) in {summary.execution_time_seconds}s. Output written to {output_file}")
            return 0

        print(summary.model_dump_json(indent=2))
        return 0

    elif args.command == "protein":
        protein = await resolver.uniprot.fetch_by_accession(args.accession)
        if not protein:
            print(json.dumps({"status": "not_found", "accession": args.accession}, indent=2))
            return 1
        print(protein.model_dump_json(indent=2))
        return 0

    elif args.command == "transcripts":
        query_clean = args.query.strip()
        if query_clean.upper().startswith("ENS"):
            gene = await resolver.ensembl.fetch_by_id(query_clean, expand=True)
        else:
            gene = await resolver.ensembl.fetch_by_symbol(species=args.species, symbol=query_clean, expand=True)

        if not gene:
            print(json.dumps({"status": "not_found", "query": args.query, "species": args.species}, indent=2))
            return 1
        print(gene.model_dump_json(indent=2))
        return 0

    elif args.command == "ortholog":
        orthologs = await resolver.ensembl.fetch_orthologs(
            gene_id_or_symbol=args.query,
            target_species=args.target,
            source_species=args.source
        )
        print("[" + ",\n".join(o.model_dump_json(indent=2) for o in orthologs) + "]")
        return 0

    elif args.command == "mouse":
        clean_q = args.query.strip()
        if clean_q.upper().startswith("MGI:"):
            gene = await resolver.mgi.fetch_by_mgi_id(clean_q)
            if gene:
                print(gene.model_dump_json(indent=2))
                return 0
        res = await resolver.resolve(query=clean_q, taxon_id=10090)
        if res and res.resolved_entity:
            print(res.resolved_entity.model_dump_json(indent=2))
            return 0
        print(json.dumps({"status": "not_found", "query": clean_q, "taxon_id": 10090}, indent=2))
        return 1

    elif args.command == "annotate":
        profile = await resolver.annotate_gene(
            query=args.query,
            taxon_id=args.taxon,
            max_terms_per_aspect=args.limit,
            target_aspect=args.aspect
        )
        if not profile:
            print(json.dumps({"status": "not_found", "query": args.query, "taxon_id": args.taxon}, indent=2))
            return 1
        print(profile.model_dump_json(indent=2))
        return 0

    elif args.command == "go":
        term = await resolver.go.fetch_term(args.go_id)
        if not term:
            print(json.dumps({"status": "not_found", "go_id": args.go_id}, indent=2))
            return 1
        print(json.dumps(term, indent=2))
        return 0

    elif args.command == "pathway":
        context = await resolver.get_pathways(
            query=args.query,
            taxon_id=args.taxon,
            limit=args.limit
        )
        if not context:
            print(json.dumps({"status": "not_found", "query": args.query, "taxon_id": args.taxon}, indent=2))
            return 1
        print(context.model_dump_json(indent=2))
        return 0

    elif args.command == "pathway-info":
        details = await resolver.reactome.fetch_pathway_details(args.st_id)
        if not details:
            print(json.dumps({"status": "not_found", "st_id": args.st_id}, indent=2))
            return 1
        print(json.dumps(details, indent=2))
        return 0

    elif args.command == "disease":
        diseases = await resolver.resolve_disease(query=args.query, limit=args.limit)
        print(json.dumps([d.model_dump() for d in diseases], indent=2))
        return 0

    elif args.command == "targets":
        context = await resolver.get_target_diseases(gene_query=args.gene, limit=args.limit)
        if not context:
            print(json.dumps({"status": "not_found", "gene": args.gene}, indent=2))
            return 1
        print(context.model_dump_json(indent=2))
        return 0

    elif args.command == "literature":
        context = await resolver.get_supporting_publications(query=args.query, limit=args.limit)
        print(context.model_dump_json(indent=2))
        return 0

    elif args.command == "paper":
        pub = await resolver.get_publication_details(identifier=args.identifier)
        if not pub:
            print(json.dumps({"status": "not_found", "identifier": args.identifier}, indent=2))
            return 1
        print(pub.model_dump_json(indent=2))
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
    elif args.command in (
        "resolve", "batch", "protein", "transcripts", "ortholog", "mouse",
        "annotate", "go", "pathway", "pathway-info", "disease", "targets",
        "literature", "paper", "cache"
    ):
        sys.exit(asyncio.run(run_cli_async(args)))
    else:
        parser.print_help()




if __name__ == "__main__":
    main()
