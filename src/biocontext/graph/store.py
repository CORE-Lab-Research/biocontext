"""In-memory Knowledge Graph storage engine for BioContext."""

from typing import Dict, List, Optional, Set
from biocontext.graph.models import EdgeType, GraphEdge, GraphNode, NodeType, SubGraphContext


class InMemoryGraphStore:
    """Lightweight, deterministic in-memory graph structure for biological entity relationships."""

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._out_edges: Dict[str, List[GraphEdge]] = {}
        self._in_edges: Dict[str, List[GraphEdge]] = {}

    def add_node(self, node: GraphNode) -> None:
        """Add or update a node in the graph."""
        self._nodes[node.id] = node
        if node.id not in self._out_edges:
            self._out_edges[node.id] = []
        if node.id not in self._in_edges:
            self._in_edges[node.id] = []

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Retrieve a node by its unique ID."""
        return self._nodes.get(node_id)

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a directed edge between two existing nodes."""
        if edge.source_id not in self._nodes:
            raise ValueError(f"Source node '{edge.source_id}' does not exist in graph.")
        if edge.target_id not in self._nodes:
            raise ValueError(f"Target node '{edge.target_id}' does not exist in graph.")

        # Avoid exact duplicate edges
        existing = [
            e for e in self._out_edges[edge.source_id]
            if e.target_id == edge.target_id and e.edge_type == edge.edge_type
        ]
        if not existing:
            self._out_edges[edge.source_id].append(edge)
            self._in_edges[edge.target_id].append(edge)

    def get_outgoing_edges(self, node_id: str, edge_type: Optional[EdgeType] = None) -> List[GraphEdge]:
        """Return all outgoing edges from node_id, optionally filtered by edge_type."""
        edges = self._out_edges.get(node_id, [])
        if edge_type:
            return [e for e in edges if e.edge_type == edge_type]
        return list(edges)

    def get_incoming_edges(self, node_id: str, edge_type: Optional[EdgeType] = None) -> List[GraphEdge]:
        """Return all incoming edges to node_id, optionally filtered by edge_type."""
        edges = self._in_edges.get(node_id, [])
        if edge_type:
            return [e for e in edges if e.edge_type == edge_type]
        return list(edges)

    def get_neighbors(
        self,
        node_id: str,
        direction: str = "both",
        edge_type: Optional[EdgeType] = None,
        node_type: Optional[NodeType] = None,
    ) -> List[GraphNode]:
        """Retrieve connected neighboring nodes according to direction and filters."""
        neighbor_ids: Set[str] = set()

        if direction in ("out", "both"):
            for e in self.get_outgoing_edges(node_id, edge_type=edge_type):
                neighbor_ids.add(e.target_id)

        if direction in ("in", "both"):
            for e in self.get_incoming_edges(node_id, edge_type=edge_type):
                neighbor_ids.add(e.source_id)

        neighbors = [self._nodes[nid] for nid in neighbor_ids if nid in self._nodes]
        if node_type:
            neighbors = [n for n in neighbors if n.node_type == node_type]
        return neighbors

    def get_subgraph(self, root_id: str, max_depth: int = 1) -> SubGraphContext:
        """Extract a connected subgraph up to max_depth hops around root_id."""
        if root_id not in self._nodes:
            raise KeyError(f"Root node '{root_id}' not found in graph.")

        visited_nodes: Set[str] = {root_id}
        frontier: Set[str] = {root_id}
        collected_edges: List[GraphEdge] = []
        seen_edges: Set[tuple] = set()

        for _ in range(max_depth):
            next_frontier: Set[str] = set()
            for current_id in frontier:
                # Outgoing edges
                for edge in self.get_outgoing_edges(current_id):
                    edge_key = (edge.source_id, edge.target_id, edge.edge_type)
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        collected_edges.append(edge)
                    if edge.target_id not in visited_nodes:
                        visited_nodes.add(edge.target_id)
                        next_frontier.add(edge.target_id)

                # Incoming edges
                for edge in self.get_incoming_edges(current_id):
                    edge_key = (edge.source_id, edge.target_id, edge.edge_type)
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        collected_edges.append(edge)
                    if edge.source_id not in visited_nodes:
                        visited_nodes.add(edge.source_id)
                        next_frontier.add(edge.source_id)

            frontier = next_frontier
            if not frontier:
                break

        nodes_list = [self._nodes[nid] for nid in visited_nodes]
        root_node = self._nodes[root_id]
        return SubGraphContext(
            query=root_node.name,
            root_node_id=root_id,
            nodes=nodes_list,
            edges=collected_edges,
            total_nodes=len(nodes_list),
            total_edges=len(collected_edges),
        )

    def find_paths(
        self,
        start_id: str,
        target_id: str,
        max_hops: int = 3,
        min_cumulative_score: float = 0.0,
    ) -> List[List[GraphEdge]]:
        """Find deterministic directed paths between start_id and target_id using DFS."""
        if start_id not in self._nodes or target_id not in self._nodes:
            return []

        results: List[List[GraphEdge]] = []

        def dfs(current_id: str, current_path: List[GraphEdge], visited: Set[str], current_score: float):
            if current_id == target_id and current_path:
                results.append(list(current_path))
                return

            if len(current_path) >= max_hops:
                return

            for edge in self.get_outgoing_edges(current_id):
                next_id = edge.target_id
                if next_id not in visited:
                    next_score = current_score * edge.weight
                    if next_score >= min_cumulative_score:
                        visited.add(next_id)
                        current_path.append(edge)
                        dfs(next_id, current_path, visited, next_score)
                        current_path.pop()
                        visited.remove(next_id)

        dfs(start_id, [], {start_id}, 1.0)
        return results

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(edges) for edges in self._out_edges.values())

