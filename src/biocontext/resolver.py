"""Entity Resolution Engine resolving queries across biological authorities."""

from typing import List, Optional
from biocontext.adapters import EnsemblAdapter, HGNCAdapter, MGIAdapter, NCBIAdapter, UniProtAdapter
from biocontext.base import SQLiteCache
from biocontext.config import ScoringConfig
from biocontext.logging import get_logger
from biocontext.schemas import MatchReason, ResolutionContext, ResolutionResult

logger = get_logger("resolver")


class EntityResolver:
    """Multi-source biological entity resolution engine."""

    def __init__(
        self,
        cache: Optional[SQLiteCache] = None,
        ncbi_api_key: Optional[str] = None,
        email: Optional[str] = None,
        tool: Optional[str] = None
    ):
        self.cache = cache or SQLiteCache()
        self.hgnc = HGNCAdapter(cache=self.cache, email=email)
        self.ncbi = NCBIAdapter(cache=self.cache, api_key=ncbi_api_key, email=email, tool=tool)
        self.uniprot = UniProtAdapter(cache=self.cache, email=email)
        self.ensembl = EnsemblAdapter(cache=self.cache, email=email)
        self.mgi = MGIAdapter(cache=self.cache, email=email)



    def _apply_context_clues(
        self, gene, context: Optional[ResolutionContext], base_confidence: float, reasons: List[MatchReason]
    ) -> float:
        if not context or not gene:
            return base_confidence

        confidence = base_confidence

        # Chromosome disambiguation
        if context.chromosome and gene.location and gene.location.chromosome:
            hint_chr = context.chromosome.lower().replace("chr", "")
            gene_chr = gene.location.chromosome.lower().replace("chr", "")

            # Match prefix e.g. "17" matches "17p13.1" or "17q12"
            if gene_chr.startswith(hint_chr):
                confidence = min(1.0, confidence + ScoringConfig.CHROMOSOME_MATCH_BONUS)
                reasons.append(
                    MatchReason(
                        source="ContextClue",
                        rule="chromosome_match",
                        confidence=confidence,
                        details=f"Candidate chromosome '{gene.location.chromosome}' matches context hint '{context.chromosome}'"
                    )
                )
            else:
                confidence = max(0.1, confidence - ScoringConfig.CHROMOSOME_MISMATCH_PENALTY)
                reasons.append(
                    MatchReason(
                        source="ContextClue",
                        rule="chromosome_mismatch",
                        confidence=confidence,
                        details=f"Candidate chromosome '{gene.location.chromosome}' differs from context hint '{context.chromosome}'"
                    )
                )

        # Locus type / biotype disambiguation
        if context.locus_type and gene.locus_type:
            if context.locus_type.lower() not in gene.locus_type.lower():
                confidence = max(0.1, confidence - ScoringConfig.LOCUS_TYPE_MISMATCH_PENALTY)
                reasons.append(
                    MatchReason(
                        source="ContextClue",
                        rule="locus_type_mismatch",
                        confidence=confidence,
                        details=f"Locus type '{gene.locus_type}' does not match hint '{context.locus_type}'"
                    )
                )

        return round(confidence, 2)

    async def resolve(
        self, query: str, taxon_id: int = 9606, context: Optional[ResolutionContext] = None
    ) -> ResolutionResult:
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

                # Apply context clues scoring adjustments if hints provided
                final_confidence = self._apply_context_clues(gene, context, confidence, reasons)
                match_status = "exact" if rule == "exact_symbol" else "alias"
                if final_confidence < 0.60:
                    match_status = "ambiguous"

                return ResolutionResult(
                    query=query_clean,
                    match_status=match_status,
                    confidence_score=final_confidence,
                    resolved_entity=gene,
                    match_reasons=reasons
                )

        # 2. Check direct MGI ID (e.g. MGI:98834 or MGI:xxxx)
        if query_clean.upper().startswith("MGI:"):
            mgi_gene = await self.mgi.fetch_by_mgi_id(query_clean)
            if mgi_gene:
                reasons.append(
                    MatchReason(
                        source="MGI",
                        rule="mgi_id_lookup",
                        confidence=1.0,
                        details=f"Direct MGI ID lookup matched '{query_clean}' to mouse symbol '{mgi_gene.symbol}'"
                    )
                )
                final_confidence = self._apply_context_clues(mgi_gene, context, 1.0, reasons)
                return ResolutionResult(
                    query=query_clean,
                    match_status="exact",
                    confidence_score=final_confidence,
                    resolved_entity=mgi_gene,
                    match_reasons=reasons
                )

        # 3. Check Ensembl Gene ID (e.g. ENSG... or ENSMUSG...)
        if query_clean.upper().startswith("ENS"):
            ens_gene = await self.ensembl.fetch_by_id(query_clean)
            if ens_gene:
                reasons.append(
                    MatchReason(
                        source="Ensembl",
                        rule="ensembl_id_lookup",
                        confidence=1.0,
                        details=f"Direct Ensembl Gene ID lookup matched '{query_clean}' to symbol '{ens_gene.symbol}'"
                    )
                )
                # If mouse Ensembl gene, fetch MGI ID xref
                if ens_gene.taxon_id == 10090 and ens_gene.ensembl_gene_id:
                    mgi_id = await self.ensembl.fetch_mgi_id(ens_gene.ensembl_gene_id)
                    if mgi_id:
                        ens_gene.mgi_id = mgi_id

                final_confidence = self._apply_context_clues(ens_gene, context, 1.0, reasons)
                return ResolutionResult(
                    query=query_clean,
                    match_status="exact",
                    confidence_score=final_confidence,
                    resolved_entity=ens_gene,
                    match_reasons=reasons
                )

        # 4. If query is numeric (Entrez ID) and human (9606), check HGNC first (authoritative and no strict 3 req/s throttle)
        if query_clean.isdigit() and taxon_id == 9606:
            hgnc_entrez_gene = await self.hgnc.fetch_by_entrez_id(query_clean)
            if hgnc_entrez_gene:
                reasons.append(
                    MatchReason(
                        source="HGNC",
                        rule="entrez_id_lookup",
                        confidence=1.0,
                        details=f"Matched Entrez Gene ID {query_clean} via HGNC to symbol '{hgnc_entrez_gene.symbol}'"
                    )
                )
                final_confidence = self._apply_context_clues(hgnc_entrez_gene, context, 1.0, reasons)
                return ResolutionResult(
                    query=query_clean,
                    match_status="exact",
                    confidence_score=final_confidence,
                    resolved_entity=hgnc_entrez_gene,
                    match_reasons=reasons
                )

        # 5. Check Entrez Gene ID lookup or cross-species / fallback via NCBI
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

            # If mouse (10090), check Ensembl to enrich MGI ID and transcripts
            if taxon_id == 10090 and ncbi_gene.symbol:
                ens_mouse = await self.ensembl.fetch_by_symbol(species="mus_musculus", symbol=ncbi_gene.symbol)
                if ens_mouse:
                    if ens_mouse.ensembl_gene_id:
                        ncbi_gene.ensembl_gene_id = ens_mouse.ensembl_gene_id
                        mgi_id = await self.ensembl.fetch_mgi_id(ens_mouse.ensembl_gene_id)
                        if mgi_id:
                            ncbi_gene.mgi_id = mgi_id
                    if ens_mouse.transcripts:
                        ncbi_gene.transcripts = ens_mouse.transcripts

            return ResolutionResult(
                query=query_clean,
                match_status="exact" if query_clean.isdigit() else "ncbi_matched",
                confidence_score=confidence,
                resolved_entity=ncbi_gene,
                match_reasons=reasons
            )

        # 4. Check UniProt directly (accession lookup e.g. P04637)
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

        # 5. Fuzzy Match Engine: Check for common typos (e.g. TP54 -> TP53, BRCA -> BRCA1)
        if taxon_id == 9606 and len(query_clean) >= 3 and not query_clean.isdigit():
            fuzzy_matches = await self.hgnc.search_fuzzy(
                query_clean, max_distance=ScoringConfig.FUZZY_MAX_DISTANCE
            )
            if fuzzy_matches:
                best_match = fuzzy_matches[0]
                reasons.append(
                    MatchReason(
                        source="HGNC",
                        rule="fuzzy_levenshtein_match",
                        confidence=ScoringConfig.FUZZY_MATCH_CONFIDENCE,
                        details=f"Approximate typo match resolved query '{query_clean}' to candidate '{best_match.symbol}'"
                    )
                )
                final_confidence = self._apply_context_clues(
                    best_match, context, ScoringConfig.FUZZY_MATCH_CONFIDENCE, reasons
                )
                return ResolutionResult(
                    query=query_clean,
                    match_status="fuzzy",
                    confidence_score=final_confidence,
                    resolved_entity=best_match,
                    alternative_matches=fuzzy_matches[1:],
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

