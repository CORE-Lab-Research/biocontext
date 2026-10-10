"""Knowledge Graph Builder pipeline integrating BioContext adapters into structured subgraphs."""

from typing import List, Optional
from biocontext.graph.models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    Provenance,
    SubGraphContext,
)
from biocontext.graph.store import InMemoryGraphStore
from biocontext.logging import get_logger
from biocontext.resolver import EntityResolver
from biocontext.schemas import ResolutionResult

logger = get_logger("graph.builder")


class KnowledgeGraphBuilder:
    """Orchestrates entity resolution and builds connected biological subgraphs."""

    def __init__(self, resolver: Optional[EntityResolver] = None):
        self.resolver = resolver or EntityResolver()

    async def build_gene_subgraph(
        self,
        query: str,
        taxon_id: int = 9606,
        include_pathways: bool = True,
        include_go: bool = True,
        include_diseases: bool = True,
        include_literature: bool = True,
        limit_diseases: int = 5,
        limit_pathways: int = 5,
        limit_literature: int = 5,
    ) -> SubGraphContext:
        """Resolve a gene and construct an interconnected biological subgraph across databases."""
        store = InMemoryGraphStore()

        # 1. Resolve Gene
        res: ResolutionResult = await self.resolver.resolve(query=query, taxon_id=taxon_id)
        if not res.resolved_entity:
            # Unresolved entity fallback node
            unresolved_node = GraphNode(
                id=f"unresolved:{query}",
                name=query,
                node_type=NodeType.GENE,
                properties={"status": "unresolved", "query": query},
            )
            store.add_node(unresolved_node)
            return store.get_subgraph(unresolved_node.id, max_depth=0)

        gene = res.resolved_entity
        gene_node_id = f"gene:{gene.symbol}"
        gene_node = GraphNode(
            id=gene_node_id,
            name=gene.symbol,
            node_type=NodeType.GENE,
            properties={
                "hgnc_id": gene.hgnc_id,
                "ncbi_gene_id": gene.ncbi_gene_id,
                "ensembl_gene_id": gene.ensembl_gene_id,
                "description": gene.name,
                "species": gene.species,
                "synonyms": gene.synonyms,
            },
            provenance=Provenance(
                source_database="HGNC",
                confidence=res.confidence_score,
                source_id=gene.hgnc_id,
            ),
        )
        store.add_node(gene_node)

        # 2. Proteins & Transcripts
        primary_accession = gene.uniprot_ids[0] if gene.uniprot_ids else None
        for acc in gene.uniprot_ids[:2]:  # Top 2 accessions
            protein_node_id = f"protein:{acc}"
            protein_node = GraphNode(
                id=protein_node_id,
                name=f"{gene.symbol} ({acc})",
                node_type=NodeType.PROTEIN,
                properties={"accession": acc, "gene_symbol": gene.symbol},
                provenance=Provenance(
                    source_database="UniProt",
                    confidence=1.0,
                    source_id=acc,
                ),
            )
            store.add_node(protein_node)
            store.add_edge(
                GraphEdge(
                    source_id=gene_node_id,
                    target_id=protein_node_id,
                    edge_type=EdgeType.ENCODES,
                    weight=1.0,
                    provenance=Provenance(source_database="UniProt", confidence=1.0, source_id=acc),
                )
            )

        # 3. Transcripts (from Ensembl if available)
        for transcript in gene.transcripts[:3]:  # Top 3 transcripts
            t_node_id = f"transcript:{transcript.transcript_id}"
            t_node = GraphNode(
                id=t_node_id,
                name=transcript.name or transcript.transcript_id,
                node_type=NodeType.TRANSCRIPT,
                properties={
                    "transcript_id": transcript.transcript_id,
                    "is_canonical": transcript.is_canonical,
                    "biotype": transcript.biotype,
                },
                provenance=Provenance(
                    source_database="Ensembl",
                    confidence=1.0,
                    source_id=transcript.transcript_id,
                ),
            )
            store.add_node(t_node)
            store.add_edge(
                GraphEdge(
                    source_id=gene_node_id,
                    target_id=t_node_id,
                    edge_type=EdgeType.TRANSCRIBES,
                    weight=1.0,
                    provenance=Provenance(source_database="Ensembl", confidence=1.0),
                )
            )

        # 4. Pathways (Reactome)
        if include_pathways and primary_accession:
            try:
                p_ctx = await self.resolver.get_pathways(primary_accession)
                for pathway in p_ctx.pathways[:limit_pathways]:
                    p_node_id = f"pathway:{pathway.st_id}"
                    p_node = GraphNode(
                        id=p_node_id,
                        name=pathway.name,
                        node_type=NodeType.PATHWAY,
                        properties={
                            "st_id": pathway.st_id,
                            "url": pathway.url,
                            "is_in_disease": pathway.is_in_disease,
                        },
                        provenance=Provenance(
                            source_database="Reactome",
                            confidence=1.0,
                            source_id=pathway.st_id,
                        ),
                    )
                    store.add_node(p_node)
                    # Link to protein
                    protein_node_id = f"protein:{primary_accession}"
                    if store.get_node(protein_node_id):
                        store.add_edge(
                            GraphEdge(
                                source_id=protein_node_id,
                                target_id=p_node_id,
                                edge_type=EdgeType.PARTICIPATES_IN,
                                weight=1.0,
                                provenance=Provenance(source_database="Reactome", confidence=1.0),
                            )
                        )
                    else:
                        # Fallback link to gene
                        store.add_edge(
                            GraphEdge(
                                source_id=gene_node_id,
                                target_id=p_node_id,
                                edge_type=EdgeType.PARTICIPATES_IN,
                                weight=1.0,
                                provenance=Provenance(source_database="Reactome", confidence=1.0),
                            )
                        )
            except Exception as e:
                logger.warning(f"Failed to fetch pathways for graph: {e}")

        # 5. Gene Ontology (GO Terms)
        if include_go and primary_accession:
            try:
                go_ctx = await self.resolver.annotate_gene(primary_accession, max_terms_per_aspect=2)
                if go_ctx:
                    sampled_go = (go_ctx.biological_processes[:2] + go_ctx.molecular_functions[:2])
                    for go in sampled_go:
                        go_node_id = f"go:{go.go_id}"
                        go_node = GraphNode(
                            id=go_node_id,
                            name=go.name or go.go_id,
                            node_type=NodeType.GO_TERM,
                            properties={"go_id": go.go_id, "aspect": go.aspect},
                            provenance=Provenance(
                                source_database="GeneOntology",
                                confidence=1.0,
                                source_id=go.go_id,
                                evidence_code=go.evidence_code,
                            ),
                        )
                        store.add_node(go_node)
                        protein_node_id = f"protein:{primary_accession}"
                        src_id = protein_node_id if store.get_node(protein_node_id) else gene_node_id
                        edge_type = (
                            EdgeType.INVOLVED_IN
                            if go.aspect == "biological_process"
                            else EdgeType.HAS_FUNCTION
                        )
                        store.add_edge(
                            GraphEdge(
                                source_id=src_id,
                                target_id=go_node_id,
                                edge_type=edge_type,
                                weight=1.0,
                                provenance=Provenance(source_database="GeneOntology", confidence=1.0),
                            )
                        )
            except Exception as e:
                logger.warning(f"Failed to fetch GO annotations for graph: {e}")

        # 6. Target-Disease Associations (Open Targets)
        if include_diseases and gene.ensembl_gene_id:
            try:
                target_diseases = await self.resolver.get_target_diseases(gene.ensembl_gene_id)
                for assoc in target_diseases.associations[:limit_diseases]:
                    disease_node_id = f"disease:{assoc.disease_id}"
                    disease_node = GraphNode(
                        id=disease_node_id,
                        name=assoc.disease_name,
                        node_type=NodeType.DISEASE,
                        properties={
                            "disease_id": assoc.disease_id,
                            "association_score": assoc.score,
                        },
                        provenance=Provenance(
                            source_database="OpenTargets",
                            confidence=assoc.score,
                            source_id=assoc.disease_id,
                        ),
                    )
                    store.add_node(disease_node)
                    store.add_edge(
                        GraphEdge(
                            source_id=gene_node_id,
                            target_id=disease_node_id,
                            edge_type=EdgeType.ASSOCIATED_WITH,
                            weight=assoc.score,
                            provenance=Provenance(
                                source_database="OpenTargets",
                                confidence=assoc.score,
                                source_id=assoc.disease_id,
                            ),
                            properties={"datatype_scores": assoc.datatype_scores or {}},
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch disease associations for graph: {e}")

        # 7. Supporting Literature (Europe PMC)
        if include_literature:
            try:
                lit_ctx = await self.resolver.get_supporting_publications(gene.symbol, limit=limit_literature)
                for pub in lit_ctx.publications[:limit_literature]:
                    pub_id_str = pub.pmid or pub.doi or pub.title[:30]
                    pub_node_id = f"pub:{pub_id_str}"
                    pub_node = GraphNode(
                        id=pub_node_id,
                        name=pub.title,
                        node_type=NodeType.PUBLICATION,
                        properties={
                            "pmid": pub.pmid,
                            "doi": pub.doi,
                            "year": pub.pub_year,
                            "journal": pub.journal,
                        },
                        provenance=Provenance(
                            source_database="EuropePMC",
                            confidence=1.0,
                            source_id=pub.pmid,
                        ),
                    )
                    store.add_node(pub_node)
                    store.add_edge(
                        GraphEdge(
                            source_id=gene_node_id,
                            target_id=pub_node_id,
                            edge_type=EdgeType.CITED_IN,
                            weight=1.0,
                            provenance=Provenance(source_database="EuropePMC", confidence=1.0),
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch literature for graph: {e}")

        return store.get_subgraph(gene_node_id, max_depth=2)
