"""Biological Knowledge Graph models and schemas for BioContext (PRD-21)."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Categorical types of biological entities in the Knowledge Graph."""
    GENE = "gene"
    PROTEIN = "protein"
    TRANSCRIPT = "transcript"
    PATHWAY = "pathway"
    DISEASE = "disease"
    PUBLICATION = "publication"
    GO_TERM = "go_term"


class EdgeType(str, Enum):
    """Authoritative semantic biological relationships between entities."""
    ENCODES = "encodes"
    ENCODED_BY = "encoded_by"
    TRANSCRIBES = "transcribes"
    TRANSCRIBED_FROM = "transcribed_from"
    INTERACTS_WITH = "interacts_with"
    PARTICIPATES_IN = "participates_in"
    HAS_FUNCTION = "has_function"
    INVOLVED_IN = "involved_in"
    ASSOCIATED_WITH = "associated_with"
    CITED_IN = "cited_in"
    ORTHOLOG_OF = "ortholog_of"


class Provenance(BaseModel):
    """Audit trail and confidence metadata for graph nodes and edges."""
    source_database: str = Field(..., description="Authoritative primary source (e.g. HGNC, UniProt, Reactome, OpenTargets)")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence or association score between 0.0 and 1.0")
    source_id: Optional[str] = Field(None, description="Identifier in source database (e.g. HGNC:11998, R-HSA-5357801)")
    evidence_code: Optional[str] = Field(None, description="Experimental evidence code if applicable (e.g. IDA, IEA)")


class GraphNode(BaseModel):
    """Single entity node in the Knowledge Graph."""
    id: str = Field(..., description="Unique canonical node ID (e.g. 'gene:TP53', 'protein:P04637', 'disease:MONDO:0018875')")
    name: str = Field(..., description="Human-readable primary display name or symbol")
    node_type: NodeType = Field(..., description="Biological entity category")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional structured properties")
    provenance: Optional[Provenance] = Field(None, description="Provenance metadata for the node")


class GraphEdge(BaseModel):
    """Directed semantic edge connecting two entities in the Knowledge Graph."""
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    edge_type: EdgeType = Field(..., description="Semantic relationship category")
    weight: float = Field(1.0, ge=0.0, le=1.0, description="Edge weight / association strength")
    provenance: Optional[Provenance] = Field(None, description="Source attribution and evidence")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Edge specific annotations (e.g. mechanism, datatype_scores)")


class SubGraphContext(BaseModel):
    """A connected subgraph centered around an entity query."""
    query: str = Field(..., description="Original input query or seed entity ID")
    root_node_id: str = Field(..., description="The focal entity node ID")
    nodes: List[GraphNode] = Field(default_factory=list, description="Unique nodes present in the subgraph")
    edges: List[GraphEdge] = Field(default_factory=list, description="Relationships connecting nodes in the subgraph")
    total_nodes: int = Field(0, description="Total node count")
    total_edges: int = Field(0, description="Total edge count")


class PathStep(BaseModel):
    """Single transition along an ontological traversal path."""
    source_node: GraphNode = Field(..., description="Origin node of this hop")
    edge: GraphEdge = Field(..., description="Connecting edge and relation")
    target_node: GraphNode = Field(..., description="Destination node of this hop")


class TraversalPath(BaseModel):
    """An explainable, multi-hop path connecting two biological entities (PRD-22)."""
    start_node_id: str = Field(..., description="Starting entity ID")
    target_node_id: str = Field(..., description="Destination entity ID")
    steps: List[PathStep] = Field(default_factory=list, description="Sequence of hops in the path")
    hop_count: int = Field(0, description="Number of edges traversed")
    cumulative_score: float = Field(1.0, ge=0.0, le=1.0, description="Product of confidence scores along path")
    human_explanation: str = Field(..., description="Deterministic, zero-hallucination natural language narrative of the biological path")


class TraversalResult(BaseModel):
    """Result of a multi-hop graph traversal query."""
    source_query: str = Field(..., description="Initial source query or symbol")
    target_query: str = Field(..., description="Initial target query or disease/pathway")
    paths_found: List[TraversalPath] = Field(default_factory=list, description="Discovered deterministic biological paths")
    total_paths: int = Field(0, description="Count of valid paths discovered")

