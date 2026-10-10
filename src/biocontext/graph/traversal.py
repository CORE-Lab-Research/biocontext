"""Ontological multi-hop traversal over the BioContext knowledge graph (PRD-22).

Paths are enumerated deterministically from graph edges. The narrative for each
path is generated from a fixed template, so every sentence maps to one edge and
its source database. Scores are products of source-provided edge weights and are
not probabilities; unscored edges are reported as such.
"""

import re
from typing import List, Optional, Tuple

from biocontext.graph.builder import KnowledgeGraphBuilder
from biocontext.graph.models import (
    GraphEdge,
    GraphNode,
    NodeType,
    PathStep,
    TraversalPath,
    TraversalResult,
)
from biocontext.graph.store import InMemoryGraphStore
from biocontext.logging import get_logger
from biocontext.resolver import EntityResolver

logger = get_logger("graph.traversal")


def _node_identifiers(node: GraphNode) -> List[str]:
    """Identifiers a user may supply for a node (graph ID and source accession fields)."""
    ids = [node.id]
    for key in ("disease_id", "st_id", "go_id", "accession", "pmid", "doi", "transcript_id"):
        value = node.properties.get(key)
        if value:
            ids.append(str(value))
    return ids


def match_target_nodes(
    nodes: List[GraphNode],
    target_query: str,
    target_type: Optional[NodeType] = None,
    exclude_id: Optional[str] = None,
) -> List[GraphNode]:
    """Select nodes matching a target query using identifiers or whole-phrase names.

    Matching rules:
    - Exact, case-insensitive match on the node ID or a source accession field.
    - Otherwise a whole-word, case-insensitive phrase match on the node name.
    - Free-text properties are never searched.
    - Publication nodes are only eligible when target_type is PUBLICATION, because
      a paper title containing a word does not establish a biological relation.
    """
    query = target_query.strip().lower()
    phrase = re.compile(rf"(?<!\w){re.escape(query)}(?!\w)")
    matched: List[GraphNode] = []

    for node in nodes:
        if node.id == exclude_id:
            continue
        if target_type is not None and node.node_type != target_type:
            continue
        if node.node_type == NodeType.PUBLICATION and target_type != NodeType.PUBLICATION:
            continue

        if any(query == ident.lower() for ident in _node_identifiers(node)):
            matched.append(node)
        elif phrase.search(node.name.lower()):
            matched.append(node)

    return matched


class TraversalEngine:
    """Finds and explains paths between a gene and other graph entities."""

    MAX_HOPS = InMemoryGraphStore.MAX_ALLOWED_HOPS

    def __init__(
        self,
        resolver: Optional[EntityResolver] = None,
        builder: Optional[KnowledgeGraphBuilder] = None,
    ):
        self.resolver = resolver or EntityResolver()
        self.builder = builder or KnowledgeGraphBuilder(resolver=self.resolver)

    @staticmethod
    def _score_path(edges: List[GraphEdge]) -> Tuple[Optional[float], int]:
        """Return (product of source-provided weights, number of scored hops)."""
        scored = [e.weight for e in edges if e.weight is not None]
        if not scored:
            return None, 0
        product = 1.0
        for w in scored:
            product *= w
        return product, len(scored)

    @staticmethod
    def _generate_explanation(steps: List[PathStep], score: Optional[float], scored_hops: int) -> str:
        """Template-based narrative; one line per edge, with source database and weight if any."""
        lines = []
        for i, step in enumerate(steps, 1):
            src = f"{step.source_node.name} ({step.source_node.node_type.value})"
            rel = step.edge.edge_type.value.replace("_", " ")
            tgt = f"{step.target_node.name} ({step.target_node.node_type.value})"
            prov = step.edge.provenance
            source_txt = prov.source_database if prov else "unknown source"
            if prov and prov.source_id:
                source_txt += f":{prov.source_id}"
            weight_txt = f"score={step.edge.weight:.2f}" if step.edge.weight is not None else "unscored"
            lines.append(f"Hop {i}: {src} {rel} {tgt} [source={source_txt}; {weight_txt}]")

        start = steps[0].source_node.name
        end = steps[-1].target_node.name
        score_txt = (
            f"product of {scored_hops} source-provided score(s) = {score:.2f}"
            if score is not None
            else "no source-provided score on this path"
        )
        header = f"Path from {start} to {end} in {len(steps)} hop(s); {score_txt}."
        return header + "\n" + "\n".join(f"- {line}" for line in lines)

    async def traverse(
        self,
        source_query: str,
        target_query: str,
        max_hops: int = 3,
        min_score: float = 0.0,
        target_type: Optional[NodeType] = None,
    ) -> TraversalResult:
        """Enumerate paths from a source gene to graph entities matching target_query."""
        if not source_query or not source_query.strip():
            raise ValueError("source_query must be a non-empty string")
        if not target_query or not target_query.strip():
            raise ValueError("target_query must be a non-empty string")
        if not 1 <= max_hops <= self.MAX_HOPS:
            raise ValueError(f"max_hops must be between 1 and {self.MAX_HOPS}, got {max_hops}")
        if not 0.0 <= min_score <= 1.0:
            raise ValueError(f"min_score must be between 0.0 and 1.0, got {min_score}")

        subgraph = await self.builder.build_gene_subgraph(
            query=source_query.strip(),
            include_literature=(target_type == NodeType.PUBLICATION),
        )
        warnings = list(subgraph.warnings)

        store = InMemoryGraphStore()
        for node in subgraph.nodes:
            store.add_node(node)
        for edge in subgraph.edges:
            store.add_edge(edge)

        start_id = subgraph.root_node_id
        targets = match_target_nodes(subgraph.nodes, target_query, target_type, exclude_id=start_id)
        if not targets:
            warnings.append(
                f"No node in the subgraph of '{source_query}' matches target '{target_query}'"
                + (f" with type '{target_type.value}'" if target_type else "")
                + "."
            )

        paths: List[TraversalPath] = []
        for target in targets:
            for edge_list in store.find_paths(start_id, target.id, max_hops=max_hops, min_cumulative_score=min_score):
                steps: List[PathStep] = []
                for edge in edge_list:
                    src_node = store.get_node(edge.source_id)
                    tgt_node = store.get_node(edge.target_id)
                    if src_node is None or tgt_node is None:
                        raise RuntimeError(f"Edge references a missing node: {edge.source_id} -> {edge.target_id}")
                    steps.append(PathStep(source_node=src_node, edge=edge, target_node=tgt_node))

                score, scored_hops = self._score_path(edge_list)
                paths.append(
                    TraversalPath(
                        start_node_id=start_id,
                        target_node_id=target.id,
                        steps=steps,
                        hop_count=len(steps),
                        cumulative_score=score,
                        scored_hops=scored_hops,
                        human_explanation=self._generate_explanation(steps, score, scored_hops),
                    )
                )

        paths.sort(key=lambda p: (p.cumulative_score is None, -(p.cumulative_score or 0.0), p.hop_count))

        return TraversalResult(
            source_query=source_query,
            target_query=target_query,
            target_type=target_type,
            paths_found=paths,
            total_paths=len(paths),
            matched_targets=[t.id for t in targets],
            warnings=warnings,
        )
