"""Entity Resolution Engine resolving queries across biological authorities."""

from typing import List, Optional
from biocontext.adapters import HGNCAdapter, NCBIAdapter, UniProtAdapter
from biocontext.base import SQLiteCache
from biocontext.logging import get_logger
from biocontext.schemas import MatchReason, ResolutionResult

logger = get_logger("resolver")


class EntityResolver:
    """Multi-source biological entity resolution engine."""

    def __init__(self, cache: Optional[SQLiteCache] = None, ncbi_api_key: Optional[str] = None):
        self.cache = cache or SQLiteCache()
        self.hgnc = HGNCAdapter(cache=self.cache)
        self.ncbi = NCBIAdapter(cache=self.cache, api_key=ncbi_api_key)
        self.uniprot = UniProtAdapter(cache=self.cache)

    async def resolve(self, query: str, taxon_id: int = 9606) -> ResolutionResult:
        query_clean = query.strip()
        reasons: List[MatchReason] = []

        # 1. Primary Authority for Human: HGNC
        if taxon_id == 9606 and not query_clean.isdigit():
            hgnc_res = await self.hgnc.resolve_gene(query_clean, taxon_id=taxon_id)
            if hgnc_res:
                gene = hgnc_res["entity"]
                rule = hgnc_res["rule"]
                confidence = hgnc_res["confidence"]
                
                reasons.append(
                    MatchReason(
                        source="HGNC",
                        rule=rule,
                        confidence=confidence,
                        details=f"Matched {rule} via HGNC REST API for symbol '{gene.symbol}'"
                    )
                )

                # Cross-reference with UniProt if uniprot_ids missing or to enrich
                if not gene.uniprot_ids:
                    uniprot_res = await self.uniprot.resolve_gene(gene.symbol, taxon_id=taxon_id)
                    if uniprot_res and "accession" in uniprot_res:
                        gene.uniprot_ids.append(uniprot_res["accession"])

                match_status = "exact" if rule == "exact_symbol" else "alias"
                return ResolutionResult(
                    query=query_clean,
                    match_status=match_status,
                    confidence_score=confidence,
                    resolved_entity=gene,
                    match_reasons=reasons
                )

        # 2. Check Entrez Gene ID lookup or cross-species / fallback via NCBI
        ncbi_res = await self.ncbi.resolve_gene(query_clean, taxon_id=taxon_id)
        if ncbi_res:
            ncbi_gene = ncbi_res["entity"]
            rule = ncbi_res["rule"]
            confidence = ncbi_res["confidence"]
            reasons.append(
                MatchReason(
                    source="NCBI",
                    rule=rule,
                    confidence=confidence,
                    details=f"Resolved via NCBI Entrez Gene (ID: {ncbi_gene.ncbi_gene_id})"
                )
            )

            # If human, try to enrich with HGNC data (symbol, ensembl, location)
            if taxon_id == 9606 and ncbi_gene.symbol:
                hgnc_gene = await self.hgnc.fetch_by_symbol(ncbi_gene.symbol)
                if hgnc_gene:
                    if not hgnc_gene.ncbi_gene_id:
                        hgnc_gene.ncbi_gene_id = ncbi_gene.ncbi_gene_id
                    return ResolutionResult(
                        query=query_clean,
                        match_status="exact" if query_clean.isdigit() else "ncbi_matched",
                        confidence_score=confidence,
                        resolved_entity=hgnc_gene,
                        match_reasons=reasons
                    )

            return ResolutionResult(
                query=query_clean,
                match_status="exact" if query_clean.isdigit() else "ncbi_matched",
                confidence_score=confidence,
                resolved_entity=ncbi_gene,
                match_reasons=reasons
            )

        # 3. Check UniProt directly (accession lookup e.g. P04637)
        uniprot_protein = await self.uniprot.fetch_by_accession(query_clean)
        if uniprot_protein and uniprot_protein.gene_symbol:
            reasons.append(
                MatchReason(
                    source="UniProt",
                    rule="accession_lookup",
                    confidence=0.95,
                    details=f"UniProt accession {uniprot_protein.accession} maps to gene {uniprot_protein.gene_symbol}"
                )
            )
            # Resolve gene symbol back to HGNC
            gene = await self.hgnc.fetch_by_symbol(uniprot_protein.gene_symbol)
            if gene:
                if uniprot_protein.accession not in gene.uniprot_ids:
                    gene.uniprot_ids.append(uniprot_protein.accession)
                return ResolutionResult(
                    query=query_clean,
                    match_status="exact",
                    confidence_score=0.95,
                    resolved_entity=gene,
                    match_reasons=reasons
                )

        return ResolutionResult(
            query=query_clean,
            match_status="unresolved",
            confidence_score=0.0,
            resolved_entity=None,
            match_reasons=[
                MatchReason(
                    source="BioContext",
                    rule="no_match",
                    confidence=0.0,
                    details=f"No matching authoritative entity found for query '{query_clean}'"
                )
            ]
        )
