"""Shared pytest configuration.

Every test module except those listed in OFFLINE_MODULES talks to live upstream
APIs (HGNC, NCBI, UniProt, Ensembl, Open Targets, Europe PMC, ...). Those tests
are marked ``network`` automatically so the fast deterministic subset can be run
on its own:

    pytest -m "not network"   # offline only, seconds
    pytest -m network         # live upstream checks, minutes
"""

import pytest

OFFLINE_MODULES = {"test_offline_robustness"}


def pytest_collection_modifyitems(config, items):
    network = pytest.mark.network
    for item in items:
        if item.module.__name__.rsplit(".", 1)[-1] not in OFFLINE_MODULES:
            item.add_marker(network)
