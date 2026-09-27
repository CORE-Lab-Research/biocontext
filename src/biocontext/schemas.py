"""Core entity schemas for BioContext using Pydantic."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class GenomicLocation(BaseModel):
    """Genomic coordinates for a biological feature."""
    chromosome: str = Field(..., description="Chromosome identifier, e.g. '17' or 'chr17'")
    start: Optional[int] = Field(None, description="1-based start coordinate")
    end: Optional[int] = Field(None, description="1-based end coordinate")
    strand: Optional[str] = Field(None, description="Genomic strand: '+' or '-'")
    assembly: str = Field("GRCh38", description="Genome build/assembly version")


class GeneEntity(BaseModel):
    """Standardized representation of a gene entity."""
    symbol: str = Field(..., description="Approved standard gene symbol (e.g. TP53)")
    name: Optional[str] = Field(None, description="Full gene name / description")
    taxon_id: int = Field(9606, description="NCBI Taxonomy ID (default: 9606 for Homo sapiens)")
    species: str = Field("Homo sapiens", description="Species scientific name")
    
    # Primary identifiers across authoritative databases
    hgnc_id: Optional[str] = Field(None, description="HGNC ID (e.g. HGNC:11998)")
    ncbi_gene_id: Optional[str] = Field(None, description="NCBI Entrez Gene ID (e.g. 7157)")
    ensembl_gene_id: Optional[str] = Field(None, description="Ensembl Gene ID (e.g. ENSG00000141510)")
    uniprot_ids: List[str] = Field(default_factory=list, description="Associated UniProt accession IDs")
    
    synonyms: List[str] = Field(default_factory=list, description="Alternative symbols / aliases")
    locus_type: Optional[str] = Field(None, description="Locus group/type (e.g. protein-coding gene)")
    location: Optional[GenomicLocation] = Field(None, description="Genomic coordinates")


class ProteinEntity(BaseModel):
    """Standardized representation of a protein entity."""
    accession: str = Field(..., description="Primary UniProt accession (e.g. P04637)")
    entry_name: Optional[str] = Field(None, description="UniProt entry identifier (e.g. P53_HUMAN)")
    name: Optional[str] = Field(None, description="Full recommended protein name")
    taxon_id: int = Field(9606, description="NCBI Taxonomy ID")
    species: str = Field("Homo sapiens", description="Species scientific name")
    
    gene_symbol: Optional[str] = Field(None, description="Primary associated gene symbol")
    sequence_length: Optional[int] = Field(None, description="Amino acid length")
    molecular_weight: Optional[float] = Field(None, description="Mass in Daltons")
    function_summary: Optional[str] = Field(None, description="Brief functional description")


class MatchReason(BaseModel):
    """Explainable rationale for entity resolution matching."""
    source: str = Field(..., description="Data source providing the match (e.g. HGNC, NCBI, UniProt)")
    rule: str = Field(..., description="Resolution rule applied (e.g. exact_symbol, alias_match, id_lookup)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    details: Optional[str] = Field(None, description="Human-readable explanation of the match")


class ResolutionContext(BaseModel):
    """Contextual hints provided by the user or upstream pipelines for disambiguation."""
    chromosome: Optional[str] = Field(None, description="Chromosome identifier hint (e.g. '17', 'chr17')")
    start: Optional[int] = Field(None, description="Approximate start coordinate")
    end: Optional[int] = Field(None, description="Approximate end coordinate")
    locus_type: Optional[str] = Field(None, description="Expected gene biotype (e.g. 'protein-coding', 'lncRNA')")
    assembly: str = Field("GRCh38", description="Target genome assembly version")


class ResolutionResult(BaseModel):
    """Output of the Entity Resolution Engine."""
    query: str = Field(..., description="Raw input query")
    match_status: str = Field(..., description="'exact', 'alias', 'fuzzy', 'ambiguous', or 'unresolved'")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall match confidence score")
    
    resolved_entity: Optional[GeneEntity] = Field(None, description="Resolved gene entity if found")
    alternative_matches: List[GeneEntity] = Field(default_factory=list, description="Other plausible candidate matches")
    match_reasons: List[MatchReason] = Field(default_factory=list, description="Audit trail of resolution logic")
