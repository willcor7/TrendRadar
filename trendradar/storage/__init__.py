# coding=utf-8
"""
Module de stockage - prend en charge plusieurs backends de stockage

Backends de stockage pris en charge :
- local : SQLite local + fichiers TXT/HTML
- remote : stockage cloud distant (protocole compatible S3 : R2/OSS/COS/S3, etc.)
- auto : sélection automatique selon l'environnement (GitHub Actions utilise remote, sinon local)
"""

from trendradar.storage.base import (
    StorageBackend,
    NewsItem,
    NewsData,
    RSSItem,
    RSSData,
    convert_crawl_results_to_news_data,
)
from trendradar.storage.sqlite_mixin import SQLiteStorageMixin
from trendradar.storage.local import LocalStorageBackend
from trendradar.storage.manager import StorageManager, get_storage_manager

# Import optionnel du backend distant (nécessite boto3)
try:
    from trendradar.storage.remote import RemoteStorageBackend
    HAS_REMOTE = True
except ImportError:
    RemoteStorageBackend = None
    HAS_REMOTE = False

__all__ = [
    # Classes de base
    "StorageBackend",
    "NewsItem",
    "NewsData",
    "RSSItem",
    "RSSData",
    # Mixin
    "SQLiteStorageMixin",
    # Fonction de conversion
    "convert_crawl_results_to_news_data",
    # Implémentations de backend
    "LocalStorageBackend",
    "RemoteStorageBackend",
    "HAS_REMOTE",
    # Gestionnaire
    "StorageManager",
    "get_storage_manager",
]
