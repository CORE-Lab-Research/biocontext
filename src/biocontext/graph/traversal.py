"""Ontological Multi-hop Traversal and Reasoning Engine (PRD-22)."""

from typing import List, Optional
from biocontext.graph.builder import KnowledgeGraphBuilder
from biocontext.graph.models import (
    GraphEdge,
    GraphNode,
    PathStep,
    TraversalPath,
    TraversalResult,
)
from biocontext.graph.store import InMemoryGraphStore
from biocontext.logging import get_logger
from biocontext.resolver import EntityResolver

logger = get_logger("graph.traversal")


class TraversalEngine:
    """Performs deterministic, evidence-based multi-hop graph traversal and explanation."""

    def __init__(
        self,
        resolver: Optional[EntityResolver] = None,
        builder: Optional[KnowledgeGraphBuilder] = None,
    ):
        self.resolver = resolver or EntityResolver()
        self.builder = builder or KnowledgeGraphBuilder(resolver=self.resolver)

    def _generate_explanation(self, steps: List[PathStep], cumulative_score: float) -> str:
        """Construct a deterministic natural language explanation from traversal steps."""
        if not steps:
            return "No connecting path found."

        narrative_parts = []
        for i, step in enumerate(steps, 1):
            src = f"{step.source_node.name} ({step.source_node.node_type.value})"
            rel = step.edge.edge_type.value.replace("_", " ")
            tgt = f"{step.target_node.name} ({step.target_node.node_type.value})"
            prov_str = ""
            if step.edge.provenance:
                prov_str = f" [via {step.edge.provenance.source_database}"
                if step.edge.provenance.source_id:
                    prov_str += f":{step.edge.provenance.source_id}"
                prov_str += f", weight={step.edge.weight:.2f}]"

            narrative_parts.append(f"Hop {i}: {src} {rel} {tgt}{prov_str}")

        start_name = steps[0].source_node.name
        end_name = steps[-1].target_node.name
        overall_summary = (
            f"Evidence path connects {start_name} to {end_name} in {len(steps)} hops "
            f"(cumulative confidence score: {cumulative_score:.2f})."
        )
        return f"{overall_summary}\n" + "\n".join(f"- {part}" for part in narrative_parts)

    async def traverse(
        self,
        source_query: str,
        target_query: str,
        max_hops: int = 3,
        min_score: float = 0.0,
    ) -> TraversalResult:
        """Find deterministic multi-hop reasoning paths connecting two biological entities."""
        # 1. Build subgraph around source entity
        subgraph = await self.builder.build_gene_subgraph(
            query=source_query,
            include_pathways=True,
            include_go=True,
            include_diseases=True,
            include_literature=True,
        )

        store = InMemoryGraphStore()
        for node in subgraph.nodes:
            store.add_node(node)
        for edge in subgraph.edges:
            store.add_edge(edge)

        start_id = subgraph.root_node_id

        # 2. Identify target node(s) matching target_query
        target_q_clean = target_query.strip().lower()
        candidate_target_ids = []
        for node in subgraph.nodes:
            if (
                target_q_clean in node.id.lower()
                or target_q_clean in node.name.lower()
                or target_q_clean in str(node.properties).lower()
            ):
                candidate_target_ids.append(node.id)

        traversal_paths: List[TraversalPath] = []

        for target_id in candidate_target_ids:
            if target_id == start_id:
                continue

            raw_paths: List[List[GraphEdge]] = store.find_paths(
                start_id=start_id,
                target_id=target_id,
                max_hops=max_hops,
                min_cumulative_score=min_score,
            )

            for edge_list in raw_paths:
                steps: List[PathStep] = []
                cumulative_score = 1.0
                for edge in edge_list:
                    src_node = store.get_node(edge.source_id)
                    tgt_node = store.get_node(edge.target_id)
                    if src_node and tgt_node:
                        steps.append(PathStep(source_node=src_node, edge=edge, target_node=tgt_node))
                        cumulative_score *= edge.weight

                if steps:
                    explanation = self._generate_explanation(steps, cumulative_score)
                    traversal_paths.append(
                        TraversalPath(
                            start_node_id=start_id,
                            target_node_id=target_id,
                            steps=steps,
                            hop_count=len(steps),
                            cumulative_score=cumulative_score,
                            human_explanation=explanation,
                        )
                    )

        # Sort paths by highest cumulative score and lowest hop count
        traversal_paths.sort(key=lambda p: (-p.cumulative_score, p.hop_count))

        return TraversalResult(
            source_query=source_query,
            target_query=target_query,
            paths_found=traversal_paths,
            total_paths=len(traversal_paths),
        )
