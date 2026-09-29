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


class ExonEntity(BaseModel):
    """Genomic coordinates for a single exon."""
    exon_id: str = Field(..., description="Ensembl exon identifier, e.g. 'ENSE00003505295'")
    start: int = Field(..., description="1-based start coordinate")
    end: int = Field(..., description="1-based end coordinate")
    strand: Optional[str] = Field(None, description="Strand: '+' or '-'")


class OrthologEntity(BaseModel):
    """Homology and ortholog relationship between genes across species."""
    source_gene_id: str = Field(..., description="Source Ensembl gene ID (e.g. ENSG00000141510)")
    source_species: str = Field(..., description="Source species (e.g. homo_sapiens)")
    target_gene_id: str = Field(..., description="Target orthologous gene ID (e.g. ENSMUSG00000059552)")
    target_species: str = Field(..., description="Target species (e.g. mus_musculus)")
    orthology_type: str = Field(..., description="Relationship type: ortholog_one2one, ortholog_one2many, etc.")
    percent_identity: Optional[float] = Field(None, description="Sequence identity percentage")
    target_protein_id: Optional[str] = Field(None, description="Target protein identifier")



class TranscriptEntity(BaseModel):
    """Transcript model associated with a gene."""
    transcript_id: str = Field(..., description="Ensembl transcript ID, e.g. 'ENST00000269305'")
    name: Optional[str] = Field(None, description="Transcript name, e.g. 'TP53-201'")
    is_canonical: bool = Field(False, description="Flag indicating if this is the Ensembl canonical transcript")
    biotype: Optional[str] = Field(None, description="Biotype, e.g. 'protein_coding'")
    length: Optional[int] = Field(None, description="Length in base pairs")
    protein_id: Optional[str] = Field(None, description="Ensembl translation/protein ID, e.g. 'ENSP00000269305'")
    start: Optional[int] = Field(None, description="Genomic start position")
    end: Optional[int] = Field(None, description="Genomic end position")
    exons: List[ExonEntity] = Field(default_factory=list, description="Exons making up this transcript")


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
    mgi_id: Optional[str] = Field(None, description="MGI identifier for mouse genes (e.g. MGI:98834)")
    uniprot_ids: List[str] = Field(default_factory=list, description="Associated UniProt accession IDs")
    
    synonyms: List[str] = Field(default_factory=list, description="Alternative symbols / aliases")
    locus_type: Optional[str] = Field(None, description="Locus group/type (e.g. protein-coding gene)")
    location: Optional[GenomicLocation] = Field(None, description="Genomic coordinates")
    transcripts: List[TranscriptEntity] = Field(default_factory=list, description="Associated transcript variants")



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


class GOAnnotation(BaseModel):
    """Single Gene Ontology annotation associating an entity with a GO term."""
    go_id: str = Field(..., description="Gene Ontology identifier (e.g. 'GO:0006915')")
    name: Optional[str] = Field(None, description="Human-readable term name (e.g. 'apoptotic process')")
    aspect: str = Field(..., description="Ontology aspect: 'molecular_function', 'biological_process', or 'cellular_component'")
    evidence_code: Optional[str] = Field(None, description="GO evidence code abbreviation (e.g. 'IDA', 'IMP', 'IEA')")
    eco_id: Optional[str] = Field(None, description="Evidence and Conclusion Ontology identifier (e.g. 'ECO:0000314')")
    assigned_by: Optional[str] = Field(None, description="Authoritative database attributing the annotation (e.g. 'UniProt', 'Ensembl')")
    definition: Optional[str] = Field(None, description="Detailed functional definition of the GO term")


class FunctionalAnnotation(BaseModel):
    """Aggregated functional ontology profile for a biological entity."""
    query: str = Field(..., description="Original input query or gene symbol")
    taxon_id: int = Field(9606, description="NCBI Taxonomy ID")
    uniprot_accession: Optional[str] = Field(None, description="Primary UniProt accession used for annotation lookup")
    molecular_functions: List[GOAnnotation] = Field(default_factory=list, description="Molecular Function (MF) annotations")
    biological_processes: List[GOAnnotation] = Field(default_factory=list, description="Biological Process (BP) annotations")
    cellular_components: List[GOAnnotation] = Field(default_factory=list, description="Cellular Component (CC) annotations")
    total_annotations: int = Field(0, description="Total count of annotations retrieved")


class PathwayEntity(BaseModel):
    """Standardized representation of a biological pathway from Reactome."""
    st_id: str = Field(..., description="Reactome stable identifier (e.g. 'R-HSA-5357801')")
    name: str = Field(..., description="Pathway name (e.g. 'Programmed Cell Death')")
    species: str = Field("Homo sapiens", description="Species scientific name")
    is_in_disease: bool = Field(False, description="Flag indicating if this pathway is associated with disease state")
    url: Optional[str] = Field(None, description="Web link to the Reactome pathway browser diagram")
    summary: Optional[str] = Field(None, description="Brief description or summation text of the pathway")


class PathwayContext(BaseModel):
    """Pathway systems biology context for a biological entity."""
    query: str = Field(..., description="Original input query or gene symbol")
    taxon_id: int = Field(9606, description="NCBI Taxonomy ID")
    uniprot_accession: Optional[str] = Field(None, description="UniProt accession used for pathway mapping")
    source: str = Field("Reactome", description="Authoritative pathway knowledge base")
    pathways: List[PathwayEntity] = Field(default_factory=list, description="List of associated biological pathways")
    total_pathways: int = Field(0, description="Total count of pathways retrieved")


class BatchResolutionSummary(BaseModel):
    """Aggregate summary statistics and results of a batch entity resolution run."""
    total_queries: int = Field(..., description="Total number of input queries submitted")
    resolved_count: int = Field(..., description="Number of queries successfully resolved (exact, alias, fuzzy)")
    unresolved_count: int = Field(..., description="Number of queries unmapped or unresolved")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Proportion of successfully resolved queries")
    execution_time_seconds: float = Field(..., description="Elapsed wall-clock processing time")
    results: List[ResolutionResult] = Field(default_factory=list, description="List of resolution results for each query")


class DiseaseEntity(BaseModel):
    """Standardized representation of a disease entity based on MONDO and cross-references."""
    mondo_id: str = Field(..., description="Canonical MONDO disease identifier (e.g. 'MONDO:0018875')")
    name: str = Field(..., description="Standard disease preferred label / name (e.g. 'Li-Fraumeni syndrome')")
    description: Optional[str] = Field(None, description="Clinical definition or description of the disease")
    synonyms: List[str] = Field(default_factory=list, description="Alternative names, acronyms, and synonyms")
    cross_references: List[str] = Field(default_factory=list, description="External cross-references (OMIM, DOID, Orphanet, UMLS, MeSH)")


class TargetDiseaseAssociation(BaseModel):
    """Evidence-backed association between a therapeutic target (gene) and a disease from Open Targets."""
    disease_id: str = Field(..., description="Disease identifier (e.g. MONDO or EFO ID)")
    disease_name: str = Field(..., description="Preferred name of the disease")
    score: float = Field(..., ge=0.0, le=1.0, description="Overall aggregate association evidence score (0.0 - 1.0)")
    datatype_scores: Optional[Dict[str, float]] = Field(default=None, description="Breakdown scores by evidence data type (genetic, somatic, literature, animal)")


class TargetAssociationContext(BaseModel):
    """Profile of diseases associated with a target gene."""
    query: str = Field(..., description="Input gene symbol or target identifier")
    ensembl_gene_id: Optional[str] = Field(None, description="Ensembl gene ID used for Open Targets association")
    symbol: Optional[str] = Field(None, description="Approved gene symbol")
    total_associations: int = Field(0, description="Total number of associated diseases found")
    associations: List[TargetDiseaseAssociation] = Field(default_factory=list, description="Top ranked disease associations")

