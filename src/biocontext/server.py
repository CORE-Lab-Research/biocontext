"""MCPServer stdio server exposing BioContext tools to AI/LLM clients."""

import asyncio
from mcp.server.mcpserver import MCPServer
from biocontext.resolver import EntityResolver
from biocontext.schemas import ResolutionResult

# Initialize MCP Server (mcp >= 2.x)
mcp = MCPServer("BioContext")
resolver = EntityResolver()


@mcp.tool()
async def resolve_gene(
    query: str,
    taxon_id: int = 9606,
    chromosome: str | None = None,
    locus_type: str | None = None
) -> str:
    """Resolve an ambiguous gene symbol, alias, or accession to an authoritative entity.

    Args:
        query: Gene symbol (e.g. TP53), alias (e.g. HER2, p53), or accession.
        taxon_id: NCBI Taxonomy ID (default: 9606 for human).
        chromosome: Optional chromosome hint for disambiguation (e.g. '17' or 'chr17').
        locus_type: Optional biotype hint (e.g. 'protein-coding', 'pseudogene').

    Returns:
        JSON string containing the resolved canonical gene entity, cross-references, and match audit trail.
    """
    from biocontext.schemas import ResolutionContext
    context = None
    if chromosome or locus_type:
        context = ResolutionContext(chromosome=chromosome, locus_type=locus_type)

    result: ResolutionResult = await resolver.resolve(query=query, taxon_id=taxon_id, context=context)
    return result.model_dump_json(indent=2)


@mcp.tool()
async def get_protein_info(accession: str) -> str:
    """Fetch structured protein details from UniProt by primary accession.

    Args:
        accession: UniProt accession ID (e.g. P04637).

    Returns:
        JSON string containing protein name, gene, length, mass, and organism.
    """
    protein = await resolver.uniprot.fetch_by_accession(accession)
    if not protein:
        return '{"status": "not_found", "accession": "%s"}' % accession
    return protein.model_dump_json(indent=2)


@mcp.tool()
async def batch_resolve_genes(queries: list[str], taxon_id: int = 9606) -> str:
    """Resolve a list of gene identifiers/aliases in batch.

    Args:
        queries: List of gene symbols or aliases (e.g. ["TP53", "HER2", "EGFR"]).
        taxon_id: NCBI Taxonomy ID (default: 9606 for human).

    Returns:
        JSON string containing list of resolved entity results.
    """
    tasks = [resolver.resolve(q, taxon_id=taxon_id) for q in queries]
    results = await asyncio.gather(*tasks)
    return "[" + ",\n".join(r.model_dump_json(indent=2) for r in results) + "]"


def main():
    """Run MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
