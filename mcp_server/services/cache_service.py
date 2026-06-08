"""
Service de cache

Implémente un mécanisme de cache TTL pour améliorer les performances d'accès aux données.
"""

import hashlib
import json
import time
from typing import Any, Optional
from threading import Lock


def make_cache_key(namespace: str, **params) -> str:
    """
    Génère une clé de cache structurée

    En triant et en hachant les paramètres, garantit qu'une même combinaison de paramètres génère toujours la même clé.

    Args:
        namespace: espace de noms du cache, par ex. "latest_news", "trending_topics"
        **params: paramètres du cache

    Returns:
        clé de cache formatée, par ex. "latest_news:a1b2c3d4"

    Examples:
        >>> make_cache_key("latest_news", platforms=["zhihu"], limit=50)
        'latest_news:8f14e45f'
        >>> make_cache_key("search", query="AI", mode="keyword")
        'search:3c6e0b8a'
    """
    if not params:
        return namespace

    # Normalisation des paramètres
    normalized_params = {}
    for k, v in params.items():
        if v is None:
            continue  # Ignore les valeurs None
        elif isinstance(v, (list, tuple)):
            # Liste triée puis convertie en chaîne
            normalized_params[k] = json.dumps(sorted(v) if all(isinstance(i, str) for i in v) else list(v), ensure_ascii=False)
        elif isinstance(v, dict):
            # Dictionnaire trié par clé puis converti en chaîne
            normalized_params[k] = json.dumps(v, sort_keys=True, ensure_ascii=False)
        else:
            normalized_params[k] = str(v)

    # Trie les paramètres et génère le hachage
    sorted_params = sorted(normalized_params.items())
    param_str = "&".join(f"{k}={v}" for k, v in sorted_params)

    # Utilise MD5 pour générer un hachage court (8 premiers caractères)
    hash_value = hashlib.md5(param_str.encode('utf-8')).hexdigest()[:8]

    return f"{namespace}:{hash_value}"


class CacheService:
    """Classe du service de cache"""

    def __init__(self):
        """Initialise le service de cache"""
        self._cache = {}
        self._timestamps = {}
        self._lock = Lock()

    def get(self, key: str, ttl: int = 900) -> Optional[Any]:
        """
        Récupère des données du cache

        Args:
            key: clé du cache
            ttl: durée de vie (secondes), 15 minutes par défaut

        Returns:
            la valeur en cache, ou None si elle n'existe pas ou a expiré
        """
        with self._lock:
            if key in self._cache:
                # Vérifie si l'entrée a expiré
                if time.time() - self._timestamps[key] < ttl:
                    return self._cache[key]
                else:
                    # Expirée, suppression du cache
                    del self._cache[key]
                    del self._timestamps[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """
        Définit des données dans le cache

        Args:
            key: clé du cache
            value: valeur à mettre en cache
        """
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = time.time()

    def delete(self, key: str) -> bool:
        """
        Supprime une entrée du cache

        Args:
            key: clé du cache

        Returns:
            indique si la suppression a réussi
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]
                return True
        return False

    def clear(self) -> None:
        """Vide tout le cache"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()

    def cleanup_expired(self, ttl: int = 900) -> int:
        """
        Nettoie les entrées de cache expirées

        Args:
            ttl: durée de vie (secondes)

        Returns:
            le nombre d'entrées nettoyées
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, timestamp in self._timestamps.items()
                if current_time - timestamp >= ttl
            ]

            for key in expired_keys:
                del self._cache[key]
                del self._timestamps[key]

            return len(expired_keys)

    def get_stats(self) -> dict:
        """
        Récupère les statistiques du cache

        Returns:
            dictionnaire des statistiques
        """
        with self._lock:
            return {
                "total_entries": len(self._cache),
                "oldest_entry_age": (
                    time.time() - min(self._timestamps.values())
                    if self._timestamps else 0
                ),
                "newest_entry_age": (
                    time.time() - max(self._timestamps.values())
                    if self._timestamps else 0
                )
            }


# Instance de cache globale
_global_cache = None


def get_cache() -> CacheService:
    """
    Récupère l'instance de cache globale

    Returns:
        l'instance du service de cache globale
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheService()
    return _global_cache
