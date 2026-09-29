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
async def batch_resolve_genes(
    queries: list[str],
    taxon_id: int = 9606,
    concurrency: int = 10
) -> str:
    """Resolve a list of gene identifiers/aliases in batch with concurrency control and performance metrics.

    Args:
        queries: List of gene symbols or aliases (e.g. ["TP53", "HER2", "EGFR", "7157", "P04637"]).
        taxon_id: NCBI Taxonomy ID (default: 9606 for human).
        concurrency: Maximum concurrent requests (default: 10).

    Returns:
        JSON string containing the batch resolution summary, success rate, and resolved entities.
    """
    summary = await resolver.resolve_batch(queries=queries, taxon_id=taxon_id, concurrency=concurrency)
    return summary.model_dump_json(indent=2)


@mcp.tool()
async def get_transcripts(query: str, species: str = "homo_sapiens") -> str:
    """Fetch transcripts, canonical isoform, and exon structures from Ensembl.

    Args:
        query: Ensembl Gene ID (e.g. ENSG00000141510) or gene symbol (e.g. TP53).
        species: Species name (default: 'homo_sapiens' or 'mus_musculus').

    Returns:
        JSON string containing gene coordinates and transcript variants with exon models.
    """
    query_clean = query.strip()
    if query_clean.upper().startswith("ENS"):
        gene = await resolver.ensembl.fetch_by_id(query_clean, expand=True)
    else:
        gene = await resolver.ensembl.fetch_by_symbol(species=species, symbol=query_clean, expand=True)

    if not gene:
        return '{"status": "not_found", "query": "%s", "species": "%s"}' % (query_clean, species)

    return gene.model_dump_json(indent=2)


@mcp.tool()
async def find_orthologs(
    query: str,
    target_species: str = "mus_musculus",
    source_species: str = "homo_sapiens"
) -> str:
    """Identify corresponding orthologous genes across species via Ensembl.

    Args:
        query: Gene symbol (e.g. TP53) or Ensembl Gene ID (e.g. ENSG00000141510).
        target_species: Target species (default: 'mus_musculus', 'danio_rerio', etc.).
        source_species: Source species (default: 'homo_sapiens').

    Returns:
        JSON string containing list of orthologous genes with identity and relation type.
    """
    orthologs = await resolver.ensembl.fetch_orthologs(
        gene_id_or_symbol=query,
        target_species=target_species,
        source_species=source_species
    )
    return "[" + ",\n".join(o.model_dump_json(indent=2) for o in orthologs) + "]"


@mcp.tool()
async def get_mouse_gene(query: str) -> str:
    """Resolve mouse gene details and MGI identifiers (Mus musculus).

    Args:
        query: Mouse gene symbol (e.g. 'Trp53') or MGI ID (e.g. 'MGI:98834') or Ensembl ID.

    Returns:
        JSON string containing the resolved mouse gene entity with MGI identifier.
    """
    clean_q = query.strip()
    if clean_q.upper().startswith("MGI:"):
        gene = await resolver.mgi.fetch_by_mgi_id(clean_q)
        if gene:
            return gene.model_dump_json(indent=2)

    res = await resolver.resolve(query=clean_q, taxon_id=10090)
    if res and res.resolved_entity:
        return res.resolved_entity.model_dump_json(indent=2)

    return '{"status": "not_found", "query": "%s", "taxon_id": 10090}' % clean_q


@mcp.tool()
async def annotate_function(
    query: str,
    taxon_id: int = 9606,
    aspect: str | None = None,
    limit: int = 25
) -> str:
    """Fetch Gene Ontology functional annotations (MF, BP, CC) for a gene or protein.

    Args:
        query: Gene symbol (e.g. 'TP53'), alias, or UniProt accession (e.g. 'P04637').
        taxon_id: NCBI Taxonomy ID (default: 9606 for human).
        aspect: Optional filter: 'molecular_function', 'biological_process', or 'cellular_component'.
        limit: Maximum number of annotations per aspect (default: 25).

    Returns:
        JSON string containing the functional profile structured into MF, BP, and CC with evidence codes.
    """
    profile = await resolver.annotate_gene(
        query=query,
        taxon_id=taxon_id,
        max_terms_per_aspect=limit,
        target_aspect=aspect
    )
    if not profile:
        return '{"status": "not_found", "query": "%s", "taxon_id": %d}' % (query, taxon_id)

    return profile.model_dump_json(indent=2)


@mcp.tool()
async def get_go_term(go_id: str) -> str:
    """Fetch metadata and functional definition for a Gene Ontology (GO) term ID.

    Args:
        go_id: Gene Ontology identifier (e.g. 'GO:0006915').

    Returns:
        JSON string containing term name, definition, aspect, and synonyms.
    """
    term = await resolver.go.fetch_term(go_id)
    if not term:
        return '{"status": "not_found", "go_id": "%s"}' % go_id

    import json
    return json.dumps(term, indent=2)


@mcp.tool()
async def get_pathways(
    query: str,
    taxon_id: int = 9606,
    species: str = "Homo sapiens",
    limit: int = 20
) -> str:
    """Fetch biological pathways involving a gene or protein from Reactome.

    Args:
        query: Gene symbol (e.g. 'TP53'), alias, or UniProt accession (e.g. 'P04637').
        taxon_id: NCBI Taxonomy ID (default: 9606 for human).
        species: Species name (default: 'Homo sapiens').
        limit: Maximum number of pathways to return (default: 20).

    Returns:
        JSON string containing the list of pathways with names, stable IDs, and Reactome links.
    """
    context = await resolver.get_pathways(
        query=query,
        taxon_id=taxon_id,
        species=species,
        limit=limit
    )
    if not context:
        return '{"status": "not_found", "query": "%s", "taxon_id": %d}' % (query, taxon_id)

    return context.model_dump_json(indent=2)


@mcp.tool()
async def get_pathway_details(st_id: str) -> str:
    """Fetch detailed information for a Reactome pathway by its stable identifier.

    Args:
        st_id: Reactome pathway stable ID (e.g. 'R-HSA-5357801' for Programmed Cell Death).

    Returns:
        JSON string containing pathway name, species, summary text, and diagram availability.
    """
    details = await resolver.reactome.fetch_pathway_details(st_id)
    if not details:
        return '{"status": "not_found", "st_id": "%s"}' % st_id

    import json
    return json.dumps(details, indent=2)


@mcp.tool()
async def resolve_disease(query: str, limit: int = 5) -> str:
    """Resolve a disease name, synonym, or MONDO identifier against the MONDO Disease Ontology.

    Args:
        query: Disease name (e.g. 'Li-Fraumeni syndrome', 'Breast cancer'), synonym, or ID ('MONDO:0018875').
        limit: Maximum number of matches to return (default: 5).

    Returns:
        JSON string containing the list of resolved disease entities with MONDO IDs, definitions, and cross-references.
    """
    diseases = await resolver.resolve_disease(query=query, limit=limit)
    import json
    return json.dumps([d.model_dump() for d in diseases], indent=2)


@mcp.tool()
async def get_target_diseases(gene: str, limit: int = 10) -> str:
    """Fetch evidence-backed therapeutic target-disease associations from Open Targets Platform.

    Args:
        gene: Gene symbol (e.g. 'TP53', 'BRAF', 'EGFR') or Ensembl Gene ID ('ENSG00000141510').
        limit: Maximum number of top disease associations to return (default: 10).

    Returns:
        JSON string containing associated diseases, evidence scores (0.0-1.0), and datatype evidence breakdowns.
    """
    context = await resolver.get_target_diseases(gene_query=gene, limit=limit)
    if not context:
        return '{"status": "not_found", "gene": "%s"}' % gene

    return context.model_dump_json(indent=2)


def main():
    """Run MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
