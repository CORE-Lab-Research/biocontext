"""BioContext top-level SDK client and core exports (PRD-18)."""

from typing import List, Optional

from biocontext.graph.builder import KnowledgeGraphBuilder
from biocontext.graph.models import SubGraphContext, TraversalResult
from biocontext.graph.traversal import TraversalEngine
from biocontext.resolver import EntityResolver
from biocontext.schemas import (
    BatchResolutionSummary,
    DiseaseEntity,
    FunctionalAnnotation,
    GeneEntity,
    LiteratureContext,
    PathwayContext,
    ProteinEntity,
    PublicationEntity,
    ResolutionContext,
    ResolutionResult,
    TargetAssociationContext,
)


class BioContext:
    """High-level unified Python SDK client for biological entity intelligence and graph reasoning."""

    def __init__(
        self,
        ncbi_api_key: Optional[str] = None,
        email: Optional[str] = None,
        tool: Optional[str] = None,
    ):
        self.resolver = EntityResolver(
            ncbi_api_key=ncbi_api_key,
            email=email,
            tool=tool,
        )
        self.graph_builder = KnowledgeGraphBuilder(resolver=self.resolver)
        self.traversal_engine = TraversalEngine(resolver=self.resolver, builder=self.graph_builder)

    async def resolve_gene(
        self,
        query: str,
        taxon_id: int = 9606,
        chromosome: Optional[str] = None,
        locus_type: Optional[str] = None,
    ) -> ResolutionResult:
        """Resolve a gene symbol or alias to its canonical entity model."""
        ctx = None
        if chromosome or locus_type:
            ctx = ResolutionContext(chromosome=chromosome, locus_type=locus_type)
        return await self.resolver.resolve(query=query, taxon_id=taxon_id, context=ctx)

    async def get_gene(self, query: str, taxon_id: int = 9606) -> Optional[GeneEntity]:
        """Convenience helper to retrieve resolved canonical GeneEntity directly."""
        res = await self.resolve_gene(query, taxon_id=taxon_id)
        return res.resolved_entity

    async def get_protein(self, accession: str) -> Optional[ProteinEntity]:
        """Retrieve protein metadata from UniProt."""
        return await self.resolver.uniprot.fetch_by_accession(accession)

    async def get_functional_annotations(
        self,
        query: str,
        taxon_id: int = 9606,
        max_terms: int = 25,
    ) -> Optional[FunctionalAnnotation]:
        """Retrieve QuickGO functional annotations (molecular function, biological process, cellular component)."""
        return await self.resolver.annotate_gene(query, taxon_id=taxon_id, max_terms_per_aspect=max_terms)

    async def get_pathways(
        self,
        query: str,
        taxon_id: int = 9606,
        limit: int = 25,
    ) -> Optional[PathwayContext]:
        """Retrieve biological pathways from Reactome."""
        return await self.resolver.get_pathways(query, taxon_id=taxon_id, limit=limit)

    async def get_target_diseases(
        self,
        query: str,
        limit: int = 10,
    ) -> Optional[TargetAssociationContext]:
        """Retrieve Open Targets disease associations with evidence scores."""
        return await self.resolver.get_target_diseases(query, limit=limit)

    async def resolve_disease(
        self,
        query: str,
        limit: int = 5,
    ) -> List[DiseaseEntity]:
        """Search and resolve disease names against the MONDO Disease Ontology."""
        return await self.resolver.resolve_disease(query, limit=limit)

    async def get_literature(
        self,
        query: str,
        limit: int = 5,
    ) -> LiteratureContext:
        """Fetch supporting scientific publications from Europe PMC / PubMed."""
        return await self.resolver.get_supporting_publications(query, limit=limit)

    async def get_publication(
        self,
        identifier: str,
    ) -> Optional[PublicationEntity]:
        """Fetch detailed publication metadata by PMID, PMCID, or DOI."""
        return await self.resolver.get_publication_details(identifier)

    async def resolve_batch(
        self,
        queries: List[str],
        taxon_id: int = 9606,
        concurrency: int = 10,
    ) -> BatchResolutionSummary:
        """Resolve a large list of gene queries concurrently."""
        return await self.resolver.resolve_batch(queries, taxon_id=taxon_id, concurrency=concurrency)

    async def build_subgraph(
        self,
        query: str,
        taxon_id: int = 9606,
        include_pathways: bool = True,
        include_go: bool = True,
        include_diseases: bool = True,
        include_literature: bool = True,
    ) -> SubGraphContext:
        """Construct an interconnected biological Knowledge Subgraph (PRD-21)."""
        return await self.graph_builder.build_gene_subgraph(
            query=query,
            taxon_id=taxon_id,
            include_pathways=include_pathways,
            include_go=include_go,
            include_diseases=include_diseases,
            include_literature=include_literature,
        )

    async def traverse(
        self,
        source_query: str,
        target_query: str,
        max_hops: int = 3,
        min_score: float = 0.0,
    ) -> TraversalResult:
        """Perform deterministic multi-hop reasoning between entities (PRD-22)."""
        return await self.traversal_engine.traverse(
            source_query=source_query,
            target_query=target_query,
            max_hops=max_hops,
            min_score=min_score,
        )


__all__ = [
    "BioContext",
    "EntityResolver",
    "GeneEntity",
    "ProteinEntity",
    "ResolutionResult",
    "FunctionalAnnotation",
    "PathwayContext",
    "TargetAssociationContext",
    "DiseaseEntity",
    "LiteratureContext",
    "PublicationEntity",
    "SubGraphContext",
    "TraversalResult",
]
