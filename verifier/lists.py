import os
from functools import lru_cache

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load_set(filename: str) -> frozenset:
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return frozenset(line.strip().lower() for line in f if line.strip() and not line.startswith("#"))


def _load_list(filename: str) -> list:
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]


@lru_cache(maxsize=1)
def disposable_domains() -> frozenset:
    return _load_set("disposable_domains.txt")


@lru_cache(maxsize=1)
def free_providers() -> frozenset:
    return _load_set("free_providers.txt")


@lru_cache(maxsize=1)
def role_prefixes() -> frozenset:
    return _load_set("role_prefixes.txt")


@lru_cache(maxsize=1)
def common_domains() -> list:
    return _load_list("common_domains.txt")
