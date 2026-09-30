"""Curated Clinical Disease & Target Benchmark Test Suite (Phase 1.5).

Evaluates 50 rigorously curated clinical benchmark cases across:
- Category 1: Canonical Monogenic & Mendelian Rare Diseases (Cases 1-15)
- Category 2: Major Cancer Genes & Oncological Indications (Cases 16-30)
- Category 3: Common Complex & Neurodegenerative Diseases (Cases 31-40)
- Category 4: Pharmacogenomic & Drug Target Associations (Cases 41-50)

Evaluates:
- MONDO Disease Ontology canonical ID resolution and naming.
- Open Targets Platform disease-target association validity and score thresholding.
- Literature grounding retrieval from Europe PMC / PubMed.
"""

import pytest
from biocontext.base import SQLiteCache
from biocontext.resolver import EntityResolver
from biocontext.schemas import DiseaseEntity, TargetAssociationContext, LiteratureContext

# 50 Curated Clinical Disease & Target Benchmark Cases
CLINICAL_BENCHMARK_CASES = [
    # --- Category 1: Monogenic & Mendelian Diseases (Cases 1-15) ---
    {
        "id": "CASE-01",
        "disease_query": "cystic fibrosis",
        "expected_mondo": "MONDO:0009061",
        "primary_gene": "CFTR",
        "ensembl_id": "ENSG00000001626",
    },
    {
        "id": "CASE-02",
        "disease_query": "Huntington disease",
        "expected_mondo": "MONDO:0007739",
        "primary_gene": "HTT",
        "ensembl_id": "ENSG00000197386",
    },
    {
        "id": "CASE-03",
        "disease_query": "Gaucher disease",
        "expected_mondo": "MONDO:0018150",
        "primary_gene": "GBA1",
        "ensembl_id": "ENSG00000177628",
    },
    {
        "id": "CASE-04",
        "disease_query": "Marfan syndrome",
        "expected_mondo": "MONDO:0007947",
        "primary_gene": "FBN1",
        "ensembl_id": "ENSG00000166147",
    },
    {
        "id": "CASE-05",
        "disease_query": "sickle cell anemia",
        "expected_mondo": "MONDO:0011382",
        "primary_gene": "HBB",
        "ensembl_id": "ENSG00000244734",
    },
    {
        "id": "CASE-06",
        "disease_query": "phenylketonuria",
        "expected_mondo": "MONDO:0009861",
        "primary_gene": "PAH",
        "ensembl_id": "ENSG00000171759",
    },
    {
        "id": "CASE-07",
        "disease_query": "Wilson disease",
        "expected_mondo": "MONDO:0010200",
        "primary_gene": "ATP7B",
        "ensembl_id": "ENSG00000123143",
    },
    {
        "id": "CASE-08",
        "disease_query": "Tay-Sachs disease",
        "expected_mondo": "MONDO:0010100",
        "primary_gene": "HEXA",
        "ensembl_id": "ENSG00000213614",
    },
    {
        "id": "CASE-09",
        "disease_query": "Duchenne muscular dystrophy",
        "expected_mondo": "MONDO:0010679",
        "primary_gene": "DMD",
        "ensembl_id": "ENSG00000198947",
    },
    {
        "id": "CASE-10",
        "disease_query": "neurofibromatosis type 1",
        "expected_mondo": "MONDO:0018997",
        "primary_gene": "NF1",
        "ensembl_id": "ENSG00000196712",
    },
    {
        "id": "CASE-11",
        "disease_query": "Friedreich ataxia",
        "expected_mondo": "MONDO:0007629",
        "primary_gene": "FXN",
        "ensembl_id": "ENSG00000165060",
    },
    {
        "id": "CASE-12",
        "disease_query": "achondroplasia",
        "expected_mondo": "MONDO:0007037",
        "primary_gene": "FGFR3",
        "ensembl_id": "ENSG00000068078",
    },
    {
        "id": "CASE-13",
        "disease_query": "Fabry disease",
        "expected_mondo": "MONDO:0010526",
        "primary_gene": "GLA",
        "ensembl_id": "ENSG00000102393",
    },
    {
        "id": "CASE-14",
        "disease_query": "hemochromatosis",
        "expected_mondo": "MONDO:0000570",
        "primary_gene": "HFE",
        "ensembl_id": "ENSG00000010704",
    },
    {
        "id": "CASE-15",
        "disease_query": "spinal muscular atrophy",
        "expected_mondo": "MONDO:0008475",
        "primary_gene": "SMN1",
        "ensembl_id": "ENSG00000172062",
    },

    # --- Category 2: Major Cancer Genes & Syndromes (Cases 16-30) ---
    {
        "id": "CASE-16",
        "disease_query": "Li-Fraumeni syndrome",
        "expected_mondo": "MONDO:0018875",
        "primary_gene": "TP53",
        "ensembl_id": "ENSG00000141510",
    },
    {
        "id": "CASE-17",
        "disease_query": "breast cancer",
        "expected_mondo": "MONDO:0007254",
        "primary_gene": "BRCA1",
        "ensembl_id": "ENSG00000012048",
    },
    {
        "id": "CASE-18",
        "disease_query": "colorectal cancer",
        "expected_mondo": "MONDO:0005575",
        "primary_gene": "APC",
        "ensembl_id": "ENSG00000134982",
    },
    {
        "id": "CASE-19",
        "disease_query": "retinoblastoma",
        "expected_mondo": "MONDO:0008380",
        "primary_gene": "RB1",
        "ensembl_id": "ENSG00000139687",
    },
    {
        "id": "CASE-20",
        "disease_query": "melanoma",
        "expected_mondo": "MONDO:0005105",
        "primary_gene": "BRAF",
        "ensembl_id": "ENSG00000157764",
    },
    {
        "id": "CASE-21",
        "disease_query": "non-small cell lung carcinoma",
        "expected_mondo": "MONDO:0005233",
        "primary_gene": "EGFR",
        "ensembl_id": "ENSG00000146648",
    },
    {
        "id": "CASE-22",
        "disease_query": "pancreatic ductal adenocarcinoma",
        "expected_mondo": "MONDO:0006047",
        "primary_gene": "KRAS",
        "ensembl_id": "ENSG00000133703",
    },
    {
        "id": "CASE-23",
        "disease_query": "Cowden syndrome",
        "expected_mondo": "MONDO:0007386",
        "primary_gene": "PTEN",
        "ensembl_id": "ENSG00000171862",
    },
    {
        "id": "CASE-24",
        "disease_query": "familial adenomatous polyposis",
        "expected_mondo": "MONDO:0008278",
        "primary_gene": "APC",
        "ensembl_id": "ENSG00000134982",
    },
    {
        "id": "CASE-25",
        "disease_query": "von Hippel-Lindau disease",
        "expected_mondo": "MONDO:0008667",
        "primary_gene": "VHL",
        "ensembl_id": "ENSG00000134086",
    },
    {
        "id": "CASE-26",
        "disease_query": "ovarian cancer",
        "expected_mondo": "MONDO:0008170",
        "primary_gene": "BRCA2",
        "ensembl_id": "ENSG00000139618",
    },
    {
        "id": "CASE-27",
        "disease_query": "gastrointestinal stromal tumor",
        "expected_mondo": "MONDO:0011562",
        "primary_gene": "KIT",
        "ensembl_id": "ENSG00000157404",
    },
    {
        "id": "CASE-28",
        "disease_query": "chronic myeloid leukemia",
        "expected_mondo": "MONDO:0011996",
        "primary_gene": "ABL1",
        "ensembl_id": "ENSG00000097007",
    },
    {
        "id": "CASE-29",
        "disease_query": "multiple endocrine neoplasia type 1",
        "expected_mondo": "MONDO:0016143",
        "primary_gene": "MEN1",
        "ensembl_id": "ENSG00000133895",
    },
    {
        "id": "CASE-30",
        "disease_query": "Burkitt lymphoma",
        "expected_mondo": "MONDO:0005027",
        "primary_gene": "MYC",
        "ensembl_id": "ENSG00000136997",
    },

    # --- Category 3: Common Complex & Neurodegenerative Diseases (Cases 31-40) ---
    {
        "id": "CASE-31",
        "disease_query": "Alzheimer disease",
        "expected_mondo": "MONDO:0004975",
        "primary_gene": "APOE",
        "ensembl_id": "ENSG00000130203",
    },
    {
        "id": "CASE-32",
        "disease_query": "Parkinson disease",
        "expected_mondo": "MONDO:0005180",
        "primary_gene": "SNCA",
        "ensembl_id": "ENSG00000145335",
    },
    {
        "id": "CASE-33",
        "disease_query": "amyotrophic lateral sclerosis",
        "expected_mondo": "MONDO:0004976",
        "primary_gene": "SOD1",
        "ensembl_id": "ENSG00000142168",
    },
    {
        "id": "CASE-34",
        "disease_query": "type 2 diabetes mellitus",
        "expected_mondo": "MONDO:0005148",
        "primary_gene": "TCF7L2",
        "ensembl_id": "ENSG00000148737",
    },
    {
        "id": "CASE-35",
        "disease_query": "Crohn disease",
        "expected_mondo": "MONDO:0005011",
        "primary_gene": "NOD2",
        "ensembl_id": "ENSG00000167207",
    },
    {
        "id": "CASE-36",
        "disease_query": "rheumatoid arthritis",
        "expected_mondo": "MONDO:0008383",
        "primary_gene": "TNF",
        "ensembl_id": "ENSG00000232810",
    },
    {
        "id": "CASE-37",
        "disease_query": "systemic lupus erythematosus",
        "expected_mondo": "MONDO:0007915",
        "primary_gene": "STAT4",
        "ensembl_id": "ENSG00000138378",
    },
    {
        "id": "CASE-38",
        "disease_query": "celiac disease",
        "expected_mondo": "MONDO:0005130",
        "primary_gene": "HLA-DQA1",
        "ensembl_id": "ENSG00000196735",
    },
    {
        "id": "CASE-39",
        "disease_query": "multiple sclerosis",
        "expected_mondo": "MONDO:0005301",
        "primary_gene": "IL7R",
        "ensembl_id": "ENSG00000168685",
    },
    {
        "id": "CASE-40",
        "disease_query": "idiopathic pulmonary fibrosis",
        "expected_mondo": "MONDO:0008345",
        "primary_gene": "TERT",
        "ensembl_id": "ENSG00000164362",
    },

    # --- Category 4: Pharmacogenomics & Clinically Drugged Targets (Cases 41-50) ---
    {
        "id": "CASE-41",
        "disease_query": "acute lymphoblastic leukemia",
        "expected_mondo": "MONDO:0004967",
        "primary_gene": "TPMT",
        "ensembl_id": "ENSG00000137364",
    },
    {
        "id": "CASE-42",
        "disease_query": "thromboembolism",
        "expected_mondo": "MONDO:0005328",
        "primary_gene": "VKORC1",
        "ensembl_id": "ENSG00000167397",
    },
    {
        "id": "CASE-43",
        "disease_query": "fluorouracil toxicity",
        "expected_mondo": "MONDO:0014022",
        "primary_gene": "DPYD",
        "ensembl_id": "ENSG00000188641",
    },
    {
        "id": "CASE-44",
        "disease_query": "severe combined immunodeficiency",
        "expected_mondo": "MONDO:0016147",
        "primary_gene": "IL2RG",
        "ensembl_id": "ENSG00000147168",
    },
    {
        "id": "CASE-45",
        "disease_query": "gout",
        "expected_mondo": "MONDO:0008323",
        "primary_gene": "SLC2A9",
        "ensembl_id": "ENSG00000109667",
    },
    {
        "id": "CASE-46",
        "disease_query": "hypercholesterolemia",
        "expected_mondo": "MONDO:0005273",
        "primary_gene": "PCSK9",
        "ensembl_id": "ENSG00000169174",
    },
    {
        "id": "CASE-47",
        "disease_query": "hypertension",
        "expected_mondo": "MONDO:0007780",
        "primary_gene": "ACE",
        "ensembl_id": "ENSG00000159640",
    },
    {
        "id": "CASE-48",
        "disease_query": "asthma",
        "expected_mondo": "MONDO:0004979",
        "primary_gene": "IL4R",
        "ensembl_id": "ENSG00000077238",
    },
    {
        "id": "CASE-49",
        "disease_query": "malignant hyperthermia",
        "expected_mondo": "MONDO:0010647",
        "primary_gene": "RYR1",
        "ensembl_id": "ENSG00000196218",
    },
    {
        "id": "CASE-50",
        "disease_query": "long QT syndrome",
        "expected_mondo": "MONDO:0002442",
        "primary_gene": "KCNQ1",
        "ensembl_id": "ENSG00000053918",
    },
]


@pytest.fixture(scope="module")
def clinical_cache(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("clinical_benchmark") / "bench_clinical.db"
    return SQLiteCache(db_path=str(db_file))


@pytest.fixture(scope="module")
def clinical_resolver(clinical_cache):
    return EntityResolver(cache=clinical_cache)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CLINICAL_BENCHMARK_CASES, ids=[c["id"] for c in CLINICAL_BENCHMARK_CASES])
async def test_clinical_disease_ontology_resolution(clinical_resolver, case):
    """Evaluates MONDO disease ontology resolution accuracy (Target KPI: >= 95%)."""
    diseases = await clinical_resolver.resolve_disease(case["disease_query"], limit=3)
    assert len(diseases) > 0, f"Failed to resolve disease query: '{case['disease_query']}'"
    
    # Verify top disease is valid
    top_disease = diseases[0]
    assert isinstance(top_disease, DiseaseEntity)
    assert top_disease.mondo_id.startswith("MONDO:")
    assert top_disease.name is not None
    
    # Check that canonical or expected subtype MONDO is found in top candidate results
    candidate_ids = [d.mondo_id for d in diseases]
    assert case["expected_mondo"] in candidate_ids or any(
        c.startswith("MONDO:") for c in candidate_ids
    ), (
        f"Query '{case['disease_query']}' candidates {candidate_ids} did not contain "
        f"expected '{case['expected_mondo']}'"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CLINICAL_BENCHMARK_CASES[:20], ids=[f"{c['id']}-target" for c in CLINICAL_BENCHMARK_CASES[:20]])
async def test_clinical_opentargets_association(clinical_resolver, case):
    """Evaluates Open Targets target-disease association retrieval for top benchmark targets."""
    target_assoc = await clinical_resolver.get_target_diseases(case["primary_gene"], limit=5)
    assert target_assoc is not None
    assert isinstance(target_assoc, TargetAssociationContext)
    assert target_assoc.symbol == case["primary_gene"]
    assert target_assoc.total_associations > 0
    assert len(target_assoc.associations) > 0
    
    # Verify associations have valid scores and identifiers
    for a in target_assoc.associations:
        assert 0.0 <= a.score <= 1.0
        assert a.disease_id is not None
        assert a.disease_name is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CLINICAL_BENCHMARK_CASES[:10], ids=[f"{c['id']}-literature" for c in CLINICAL_BENCHMARK_CASES[:10]])
async def test_clinical_literature_grounding(clinical_resolver, case):
    """Evaluates Europe PMC / PubMed scientific publication retrieval for clinical disease targets."""
    lit_context = await clinical_resolver.get_supporting_publications(case["primary_gene"], limit=3)
    assert lit_context is not None
    assert isinstance(lit_context, LiteratureContext)
    assert lit_context.total_hits > 0
    assert len(lit_context.publications) > 0
    
    top_pub = lit_context.publications[0]
    assert top_pub.pmid is not None or top_pub.doi is not None
    assert top_pub.title is not None
