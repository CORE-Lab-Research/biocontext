"""Knowledge Graph Builder pipeline integrating BioContext adapters into structured subgraphs.

Every optional layer reports a status in SubGraphContext.layer_status so that a
failed or empty layer is visible to the caller instead of silently producing a
smaller graph.
"""

from typing import Dict, List, Optional

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

LAYER_PATHWAYS = "pathways"
LAYER_GO = "go"
LAYER_DISEASES = "diseases"
LAYER_LITERATURE = "literature"


class KnowledgeGraphBuilder:
    """Orchestrates entity resolution and builds connected biological subgraphs."""

    def __init__(self, resolver: Optional[EntityResolver] = None):
        self.resolver = resolver or EntityResolver()

    def _finish(
        self,
        store: InMemoryGraphStore,
        root_id: str,
        layer_status: Dict[str, str],
        warnings: List[str],
        max_depth: int,
    ) -> SubGraphContext:
        subgraph = store.get_subgraph(root_id, max_depth=max_depth)
        subgraph.layer_status = layer_status
        subgraph.warnings = warnings
        logger.info(
            "Subgraph built | root=%s nodes=%d edges=%d layers=%s",
            root_id, subgraph.total_nodes, subgraph.total_edges, layer_status,
        )
        return subgraph

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
        layer_status: Dict[str, str] = {}
        warnings: List[str] = []

        res: ResolutionResult = await self.resolver.resolve(query=query, taxon_id=taxon_id)
        if not res.resolved_entity:
            unresolved_node = GraphNode(
                id=f"unresolved:{query}",
                name=query,
                node_type=NodeType.GENE,
                properties={"status": "unresolved", "query": query},
            )
            store.add_node(unresolved_node)
            warnings.append(f"Seed query '{query}' could not be resolved to a gene; no layers were built.")
            return self._finish(store, unresolved_node.id, layer_status, warnings, max_depth=0)

        gene = res.resolved_entity
        gene_node_id = f"gene:{gene.symbol}"
        store.add_node(
            GraphNode(
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
                    "match_status": res.match_status,
                },
                provenance=Provenance(
                    source_database="HGNC",
                    confidence=res.confidence_score,
                    source_id=gene.hgnc_id,
                ),
            )
        )

        # Proteins (UniProt accessions attached to the resolved gene)
        primary_accession = gene.uniprot_ids[0] if gene.uniprot_ids else None
        for acc in gene.uniprot_ids[:2]:
            protein_node_id = f"protein:{acc}"
            store.add_node(
                GraphNode(
                    id=protein_node_id,
                    name=f"{gene.symbol} ({acc})",
                    node_type=NodeType.PROTEIN,
                    properties={"accession": acc, "gene_symbol": gene.symbol},
                    provenance=Provenance(source_database="UniProt", source_id=acc),
                )
            )
            store.add_edge(
                GraphEdge(
                    source_id=gene_node_id,
                    target_id=protein_node_id,
                    edge_type=EdgeType.ENCODES,
                    provenance=Provenance(source_database="UniProt", source_id=acc),
                )
            )

        # Transcripts (only present when the resolver populated them from Ensembl)
        for transcript in gene.transcripts[:3]:
            t_node_id = f"transcript:{transcript.transcript_id}"
            store.add_node(
                GraphNode(
                    id=t_node_id,
                    name=transcript.name or transcript.transcript_id,
                    node_type=NodeType.TRANSCRIPT,
                    properties={
                        "transcript_id": transcript.transcript_id,
                        "is_canonical": transcript.is_canonical,
                        "biotype": transcript.biotype,
                    },
                    provenance=Provenance(source_database="Ensembl", source_id=transcript.transcript_id),
                )
            )
            store.add_edge(
                GraphEdge(
                    source_id=gene_node_id,
                    target_id=t_node_id,
                    edge_type=EdgeType.TRANSCRIBES,
                    provenance=Provenance(source_database="Ensembl", source_id=transcript.transcript_id),
                )
            )

        protein_anchor_id = f"protein:{primary_accession}" if primary_accession else None
        anchor_id = protein_anchor_id if protein_anchor_id and store.get_node(protein_anchor_id) else gene_node_id

        # Pathways (Reactome)
        if not include_pathways:
            layer_status[LAYER_PATHWAYS] = "skipped"
        elif not primary_accession:
            layer_status[LAYER_PATHWAYS] = "skipped: no UniProt accession for gene"
        else:
            try:
                p_ctx = await self.resolver.get_pathways(primary_accession)
                pathways = p_ctx.pathways[:limit_pathways] if p_ctx else []
                for pathway in pathways:
                    p_node_id = f"pathway:{pathway.st_id}"
                    store.add_node(
                        GraphNode(
                            id=p_node_id,
                            name=pathway.name,
                            node_type=NodeType.PATHWAY,
                            properties={
                                "st_id": pathway.st_id,
                                "url": pathway.url,
                                "is_in_disease": pathway.is_in_disease,
                            },
                            provenance=Provenance(source_database="Reactome", source_id=pathway.st_id),
                        )
                    )
                    store.add_edge(
                        GraphEdge(
                            source_id=anchor_id,
                            target_id=p_node_id,
                            edge_type=EdgeType.PARTICIPATES_IN,
                            provenance=Provenance(source_database="Reactome", source_id=pathway.st_id),
                        )
                    )
                layer_status[LAYER_PATHWAYS] = "ok" if pathways else "empty"
            except Exception as e:
                logger.warning("Pathway layer failed | gene=%s error=%s", gene.symbol, e)
                layer_status[LAYER_PATHWAYS] = f"failed: {e}"
                warnings.append(f"Pathway layer failed: {e}")

        # Gene Ontology (QuickGO)
        if not include_go:
            layer_status[LAYER_GO] = "skipped"
        elif not primary_accession:
            layer_status[LAYER_GO] = "skipped: no UniProt accession for gene"
        else:
            try:
                go_ctx = await self.resolver.annotate_gene(primary_accession, max_terms_per_aspect=2)
                sampled_go = (
                    go_ctx.biological_processes[:2] + go_ctx.molecular_functions[:2] if go_ctx else []
                )
                for go in sampled_go:
                    go_node_id = f"go:{go.go_id}"
                    store.add_node(
                        GraphNode(
                            id=go_node_id,
                            name=go.name or go.go_id,
                            node_type=NodeType.GO_TERM,
                            properties={"go_id": go.go_id, "aspect": go.aspect},
                            provenance=Provenance(
                                source_database="GeneOntology",
                                source_id=go.go_id,
                                evidence_code=go.evidence_code,
                            ),
                        )
                    )
                    edge_type = (
                        EdgeType.INVOLVED_IN if go.aspect == "biological_process" else EdgeType.HAS_FUNCTION
                    )
                    store.add_edge(
                        GraphEdge(
                            source_id=anchor_id,
                            target_id=go_node_id,
                            edge_type=edge_type,
                            provenance=Provenance(
                                source_database="GeneOntology",
                                source_id=go.go_id,
                                evidence_code=go.evidence_code,
                            ),
                        )
                    )
                layer_status[LAYER_GO] = "ok" if sampled_go else "empty"
            except Exception as e:
                logger.warning("GO layer failed | gene=%s error=%s", gene.symbol, e)
                layer_status[LAYER_GO] = f"failed: {e}"
                warnings.append(f"GO layer failed: {e}")

        # Target-disease associations (Open Targets). These carry real scores.
        if not include_diseases:
            layer_status[LAYER_DISEASES] = "skipped"
        elif not gene.ensembl_gene_id:
            layer_status[LAYER_DISEASES] = "skipped: no Ensembl gene ID for gene"
        else:
            try:
                target_diseases = await self.resolver.get_target_diseases(gene.ensembl_gene_id)
                associations = target_diseases.associations[:limit_diseases] if target_diseases else []
                for assoc in associations:
                    disease_node_id = f"disease:{assoc.disease_id}"
                    store.add_node(
                        GraphNode(
                            id=disease_node_id,
                            name=assoc.disease_name,
                            node_type=NodeType.DISEASE,
                            properties={"disease_id": assoc.disease_id},
                            provenance=Provenance(source_database="OpenTargets", source_id=assoc.disease_id),
                        )
                    )
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
                layer_status[LAYER_DISEASES] = "ok" if associations else "empty"
            except Exception as e:
                logger.warning("Disease layer failed | gene=%s error=%s", gene.symbol, e)
                layer_status[LAYER_DISEASES] = f"failed: {e}"
                warnings.append(f"Disease layer failed: {e}")

        # Literature (Europe PMC keyword search). Unscored: ranking is not evidence strength.
        if not include_literature:
            layer_status[LAYER_LITERATURE] = "skipped"
        else:
            try:
                lit_ctx = await self.resolver.get_supporting_publications(gene.symbol, limit=limit_literature)
                publications = lit_ctx.publications[:limit_literature] if lit_ctx else []
                for pub in publications:
                    pub_key = pub.pmid or pub.doi
                    if not pub_key:
                        logger.warning("Skipping publication without PMID/DOI | title=%s", pub.title[:60])
                        continue
                    pub_node_id = f"pub:{pub_key}"
                    store.add_node(
                        GraphNode(
                            id=pub_node_id,
                            name=pub.title,
                            node_type=NodeType.PUBLICATION,
                            properties={
                                "pmid": pub.pmid,
                                "doi": pub.doi,
                                "year": pub.pub_year,
                                "journal": pub.journal,
                            },
                            provenance=Provenance(source_database="EuropePMC", source_id=pub.pmid),
                        )
                    )
                    store.add_edge(
                        GraphEdge(
                            source_id=gene_node_id,
                            target_id=pub_node_id,
                            edge_type=EdgeType.CITED_IN,
                            provenance=Provenance(source_database="EuropePMC", source_id=pub.pmid),
                            properties={
                                "relation_basis": "keyword_search_hit",
                                "search_term": gene.symbol,
                                "note": "Hit for the gene symbol; topical relevance is not verified.",
                            },
                        )
                    )
                layer_status[LAYER_LITERATURE] = "ok" if publications else "empty"
            except Exception as e:
                logger.warning("Literature layer failed | gene=%s error=%s", gene.symbol, e)
                layer_status[LAYER_LITERATURE] = f"failed: {e}"
                warnings.append(f"Literature layer failed: {e}")

        return self._finish(store, gene_node_id, layer_status, warnings, max_depth=2)
