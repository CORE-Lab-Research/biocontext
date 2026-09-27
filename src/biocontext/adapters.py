"""Adapters for authoritative biological databases: HGNC, NCBI, and UniProt."""

import logging
from typing import Any, Dict, List, Optional
import httpx

import os

from biocontext.base import AsyncRateLimiter, BaseBioAdapter, SQLiteCache
from biocontext.config import ClientConfig
from biocontext.logging import get_logger
from biocontext.schemas import GeneEntity, GenomicLocation, ProteinEntity

logger = get_logger("adapters")


class HGNCAdapter(BaseBioAdapter):
    """Adapter for HGNC (HUGO Gene Nomenclature Committee) REST API.
    Primary authority for human gene nomenclature.
    """

    BASE_URL = "https://rest.genenames.org"

    def __init__(self, cache: Optional[SQLiteCache] = None, email: Optional[str] = None):
        super().__init__(name="HGNC", cache=cache)
        self.email = ClientConfig.get_email(email)
        self.headers = ClientConfig.get_headers(self.email)


    async def fetch_by_symbol(self, symbol: str) -> Optional[GeneEntity]:
        cache_key = f"symbol:{symbol.upper()}"
        cached = self.cache.get("hgnc", cache_key)
        if cached:
            return GeneEntity(**cached)

        url = f"{self.BASE_URL}/fetch/symbol/{symbol.upper()}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self.headers)
            if resp.status_code != 200:
                return None
            data = resp.json()

        docs = data.get("response", {}).get("docs", [])
        if not docs:
            return None

        doc = docs[0]
        uniprot_ids = doc.get("uniprot_ids", [])
        aliases = doc.get("alias_symbol", [])
        prev_symbols = doc.get("prev_symbol", [])
        all_synonyms = list(dict.fromkeys(aliases + prev_symbols))

        location = None
        if "location" in doc:
            location = GenomicLocation(
                chromosome=doc.get("location", ""),
                assembly="GRCh38"
            )

        gene = GeneEntity(
            symbol=doc.get("symbol"),
            name=doc.get("name"),
            taxon_id=9606,
            species="Homo sapiens",
            hgnc_id=doc.get("hgnc_id"),
            ncbi_gene_id=doc.get("entrez_id"),
            ensembl_gene_id=doc.get("ensembl_gene_id"),
            uniprot_ids=uniprot_ids,
            synonyms=all_synonyms,
            locus_type=doc.get("locus_type"),
            location=location,
        )

        self.cache.set("hgnc", cache_key, gene.model_dump())
        return gene

    async def fetch_by_entrez_id(self, entrez_id: str) -> Optional[GeneEntity]:
        cache_key = f"entrez:{entrez_id}"
        cached = self.cache.get("hgnc", cache_key)
        if cached:
            return GeneEntity(**cached)

        url = f"{self.BASE_URL}/fetch/entrez_id/{entrez_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code != 200:
                    return None
                data = resp.json()
            except Exception as e:
                logger.warning(f"HGNC fetch_by_entrez_id failed | error={e}")
                return None

        docs = data.get("response", {}).get("docs", [])
        if not docs:
            return None

        doc = docs[0]
        uniprot_ids = doc.get("uniprot_ids", [])
        aliases = doc.get("alias_symbol", [])
        prev_symbols = doc.get("prev_symbol", [])
        all_synonyms = list(dict.fromkeys(aliases + prev_symbols))

        location = None
        if "location" in doc:
            location = GenomicLocation(
                chromosome=doc.get("location", ""),
                assembly="GRCh38"
            )

        gene = GeneEntity(
            symbol=doc.get("symbol"),
            name=doc.get("name"),
            taxon_id=9606,
            species="Homo sapiens",
            hgnc_id=doc.get("hgnc_id"),
            ncbi_gene_id=str(doc.get("entrez_id")),
            ensembl_gene_id=doc.get("ensembl_gene_id"),
            uniprot_ids=uniprot_ids,
            synonyms=all_synonyms,
            locus_type=doc.get("locus_type"),
            location=location,
        )

        self.cache.set("hgnc", cache_key, gene.model_dump())
        return gene

    async def search_alias(self, alias: str) -> Optional[GeneEntity]:
        cache_key = f"alias:{alias.upper()}"
        cached = self.cache.get("hgnc", cache_key)
        if cached:
            return GeneEntity(**cached)

        # 1. First check prev_symbol (exact historical symbols have higher clinical specificity)
        url_prev = f"{self.BASE_URL}/search/prev_symbol/{alias.upper()}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp_prev = await client.get(url_prev, headers=self.headers)
                if resp_prev.status_code == 200:
                    docs = resp_prev.json().get("response", {}).get("docs", [])
                    if docs:
                        primary_symbol = docs[0].get("symbol")
                        if primary_symbol:
                            return await self.fetch_by_symbol(primary_symbol)
            except Exception as e:
                logger.warning(f"HGNC prev_symbol lookup failed | error={e}")

        # 2. Check alias_symbol
        url = f"{self.BASE_URL}/search/alias_symbol/{alias.upper()}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code != 200:
                    return None
                docs = resp.json().get("response", {}).get("docs", [])
            except Exception as e:
                logger.warning(f"HGNC alias_symbol lookup failed | error={e}")
                return None

        if not docs:
            return None

        primary_symbol = docs[0].get("symbol")
        if primary_symbol:
            return await self.fetch_by_symbol(primary_symbol)
        return None

    async def resolve_gene(self, query: str, taxon_id: int = 9606) -> Optional[Dict[str, Any]]:
        if taxon_id != 9606:
            return None
        gene = await self.fetch_by_symbol(query)
        if gene:
            return {"entity": gene, "rule": "exact_symbol", "confidence": 1.0}
        alias_gene = await self.search_alias(query)
        if alias_gene:
            return {"entity": alias_gene, "rule": "alias_match", "confidence": 0.85}
        return None


class UniProtAdapter(BaseBioAdapter):
    """Adapter for UniProt REST API."""

    BASE_URL = "https://rest.uniprot.org/uniprotkb"

    def __init__(self, cache: Optional[SQLiteCache] = None, email: Optional[str] = None):
        super().__init__(name="UniProt", cache=cache)
        self.email = ClientConfig.get_email(email)
        self.headers = ClientConfig.get_headers(self.email)

    async def fetch_by_accession(self, accession: str) -> Optional[ProteinEntity]:
        cache_key = f"acc:{accession.upper()}"
        cached = self.cache.get("uniprot", cache_key)
        if cached:
            return ProteinEntity(**cached)

        url = f"{self.BASE_URL}/{accession.upper()}.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self.headers)
            if resp.status_code != 200:
                return None
            data = resp.json()

        primary_acc = data.get("primaryAccession", accession)
        entry_name = data.get("uniProtkbId")
        taxon_id = data.get("organism", {}).get("taxonId", 9606)
        species = data.get("organism", {}).get("scientificName", "Homo sapiens")

        # Protein names
        protein_desc = data.get("proteinDescription", {})
        rec_name = protein_desc.get("recommendedName", {}).get("fullName", {}).get("value")

        # Gene symbol
        genes = data.get("genes", [])
        gene_symbol = None
        if genes:
            gene_symbol = genes[0].get("geneName", {}).get("value")

        # Sequence details
        seq = data.get("sequence", {})
        seq_len = seq.get("length")
        mol_weight = seq.get("molWeight")

        protein = ProteinEntity(
            accession=primary_acc,
            entry_name=entry_name,
            name=rec_name,
            taxon_id=taxon_id,
            species=species,
            gene_symbol=gene_symbol,
            sequence_length=seq_len,
            molecular_weight=mol_weight,
        )

        self.cache.set("uniprot", cache_key, protein.model_dump())
        return protein

    async def resolve_gene(self, query: str, taxon_id: int = 9606) -> Optional[Dict[str, Any]]:
        # UniProt query search for human reviewed entries
        cache_key = f"query:{query.upper()}:{taxon_id}"
        cached = self.cache.get("uniprot", cache_key)
        if cached:
            return cached

        search_url = f"{self.BASE_URL}/search"
        params = {
            "query": f"(gene:{query}) AND (taxonomy_id:{taxon_id}) AND (reviewed:true)",
            "format": "json",
            "size": 1
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(search_url, params=params, headers=self.headers)
            if resp.status_code != 200:
                return None
            results = resp.json().get("results", [])
            if not results:
                return None
            accession = results[0].get("primaryAccession")
            if accession:
                protein = await self.fetch_by_accession(accession)
                if protein:
                    res = {"protein": protein.model_dump(), "accession": accession}
                    self.cache.set("uniprot", cache_key, res)
                    return res
        return None


class NCBIAdapter(BaseBioAdapter):
    """Adapter for NCBI E-utilities (Entrez Gene).
    Authority for cross-species genes and Entrez Gene IDs.
    """

    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def __init__(
        self,
        cache: Optional[SQLiteCache] = None,
        api_key: Optional[str] = None,
        email: Optional[str] = None,
        tool: Optional[str] = None
    ):
        super().__init__(name="NCBI", cache=cache)
        # Dynamically read from parameter or environment variable
        self.api_key = api_key or os.environ.get("NCBI_API_KEY")
        self.email = ClientConfig.get_email(email)
        self.tool = ClientConfig.get_tool(tool)
        self.headers = ClientConfig.get_headers(self.email)

        # Rate limit: 10 req/s with API key, 3 req/s without key (with safety margin: 2.8 req/s)
        rate = 9.5 if self.api_key else 2.8
        self.rate_limiter = AsyncRateLimiter(requests_per_second=rate)
        if self.api_key:
            logger.info("NCBIAdapter initialized with API key | rate_limit=10_req_sec")
        else:
            logger.info("NCBIAdapter initialized without API key | rate_limit=3_req_sec")

    def _params(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        p = {"retmode": "json", "tool": self.tool}
        if self.email:
            p["email"] = self.email
        if self.api_key:
            p["api_key"] = self.api_key
        p.update(extra)
        return p


    async def fetch_by_id(self, gene_id: str) -> Optional[GeneEntity]:
        cache_key = f"gene_id:{gene_id}"
        cached = self.cache.get("ncbi", cache_key)
        if cached:
            return GeneEntity(**cached)

        params = self._params({"db": "gene", "id": gene_id})
        for attempt in range(3):
            try:
                await self.rate_limiter.acquire()
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(self.ESUMMARY_URL, params=params, headers=self.headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        break
                    elif resp.status_code == 429:
                        logger.warning("NCBI rate limit 429 encountered, cooling down...")
                        import asyncio
                        await asyncio.sleep(1.0)
            except Exception as e:
                logger.warning(f"NCBI summary attempt {attempt + 1} failed | error={e}")
                if attempt == 2:
                    return None
                import asyncio
                await asyncio.sleep(0.5 * (attempt + 1))
        else:
            return None

        result = data.get("result", {})
        uids = result.get("uids", [])
        if not uids or gene_id not in result:
            return None

        doc = result[gene_id]
        symbol = doc.get("name")
        description = doc.get("description")
        taxon_id = doc.get("taxid", 9606)
        organism = doc.get("organism", {}).get("scientificname", "Homo sapiens")
        aliases_str = doc.get("otheraliases", "")
        aliases = [a.strip() for a in aliases_str.split(",") if a.strip()] if aliases_str else []

        gene = GeneEntity(
            symbol=symbol,
            name=description,
            taxon_id=taxon_id,
            species=organism,
            ncbi_gene_id=str(gene_id),
            synonyms=aliases,
        )

        self.cache.set("ncbi", cache_key, gene.model_dump())
        return gene

    async def resolve_gene(self, query: str, taxon_id: int = 9606) -> Optional[Dict[str, Any]]:
        # If query is purely digits, treat directly as Entrez Gene ID
        if query.isdigit():
            gene = await self.fetch_by_id(query)
            if gene:
                return {"entity": gene, "rule": "ncbi_id_lookup", "confidence": 1.0}

        # Otherwise search by gene symbol & taxid
        cache_key = f"search:{query.upper()}:{taxon_id}"
        cached = self.cache.get("ncbi", cache_key)
        if cached:
            return {"entity": GeneEntity(**cached), "rule": "ncbi_search", "confidence": 0.9}

        term = f"({query}[Gene Name]) AND {taxon_id}[Taxonomy ID]"
        params = self._params({"db": "gene", "term": term, "retmax": 1})
        for attempt in range(3):
            try:
                await self.rate_limiter.acquire()
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(self.ESEARCH_URL, params=params, headers=self.headers)
                    if resp.status_code == 200:
                        id_list = resp.json().get("esearchresult", {}).get("idlist", [])
                        break
                    elif resp.status_code == 429:
                        logger.warning("NCBI rate limit 429 encountered, cooling down...")
                        import asyncio
                        await asyncio.sleep(1.0)
            except Exception as e:
                logger.warning(f"NCBI search attempt {attempt + 1} failed | error={e}")
                if attempt == 2:
                    return None
                import asyncio
                await asyncio.sleep(0.5 * (attempt + 1))
        else:
            return None

        if not id_list:
            return None

        gene = await self.fetch_by_id(id_list[0])
        if gene:
            self.cache.set("ncbi", cache_key, gene.model_dump())
            return {"entity": gene, "rule": "ncbi_search", "confidence": 0.9}
        return None
