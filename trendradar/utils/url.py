# coding=utf-8
"""
Module d'utilitaires de traitement des URL

Fournit une fonction de normalisation des URL, destinée à éliminer l'effet des paramètres dynamiques
lors de la déduplication :
- normalize_url : normalise une URL en retirant les paramètres dynamiques
"""

from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Dict, Set


# Paramètres spécifiques à retirer pour chaque plateforme
#   - weibo : possède les paramètres dynamiques band_rank (classement) et Refer (source)
#   - autres plateformes : l'URL est au format chemin ou correspond à une simple recherche par mot-clé, aucun traitement nécessaire
PLATFORM_PARAMS_TO_REMOVE: Dict[str, Set[str]] = {
    # Weibo : band_rank est un paramètre de classement dynamique, Refer est un paramètre de source, t est un paramètre de plage horaire
    # Exemple : https://s.weibo.com/weibo?q=xxx&t=31&band_rank=1&Refer=top
    # Conservé : q (mot-clé)
    # Retiré : band_rank, Refer, t
    "weibo": {"band_rank", "Refer", "t"},
}

# Paramètres de suivi génériques (applicables à toutes les plateformes)
# Ces paramètres sont généralement ajoutés par des liens de partage ou du suivi publicitaire et n'affectent pas l'identification du contenu
COMMON_TRACKING_PARAMS: Set[str] = {
    # Paramètres de suivi UTM
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    # Paramètres de suivi courants
    "ref", "referrer", "source", "channel",
    # Horodatages et paramètres aléatoires
    "_t", "timestamp", "_", "random",
    # Liés au partage
    "share_token", "share_id", "share_from",
}


def normalize_url(url: str, platform_id: str = "") -> str:
    """
    Normalise une URL en retirant les paramètres dynamiques

    Sert à la déduplication en base de données : garantit que les différentes variantes d'URL d'une même
    actualité soient correctement identifiées comme une seule et même entrée.

    Règles de traitement :
    1. Retirer les paramètres dynamiques spécifiques à la plateforme (comme band_rank pour Weibo)
    2. Retirer les paramètres de suivi génériques (comme utm_*)
    3. Conserver les paramètres de requête essentiels (comme les mots-clés de recherche q=, wd=, keyword=)
    4. Trier les paramètres de requête par ordre alphabétique (pour garantir la cohérence)

    Args:
        url: URL d'origine
        platform_id: ID de la plateforme, sert à appliquer les règles spécifiques à la plateforme

    Returns:
        l'URL normalisée

    Examples:
        >>> normalize_url("https://s.weibo.com/weibo?q=test&band_rank=6&Refer=top", "weibo")
        'https://s.weibo.com/weibo?q=test'

        >>> normalize_url("https://example.com/page?id=1&utm_source=twitter", "")
        'https://example.com/page?id=1'
    """
    if not url:
        return url

    try:
        # Analyse l'URL
        parsed = urlparse(url)

        # S'il n'y a aucun paramètre de requête, retourne directement
        if not parsed.query:
            return url

        # Analyse les paramètres de requête
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Rassemble les paramètres à retirer (la comparaison se fait en minuscules)
        params_to_remove: Set[str] = set()

        # Ajoute les paramètres de suivi génériques
        params_to_remove.update(COMMON_TRACKING_PARAMS)

        # Ajoute les paramètres spécifiques à la plateforme
        if platform_id and platform_id in PLATFORM_PARAMS_TO_REMOVE:
            params_to_remove.update(PLATFORM_PARAMS_TO_REMOVE[platform_id])

        # Filtre les paramètres (le nom des paramètres est mis en minuscules pour la comparaison)
        filtered_params = {
            key: values
            for key, values in params.items()
            if key.lower() not in {p.lower() for p in params_to_remove}
        }

        # S'il ne reste aucun paramètre après filtrage, retourne l'URL sans chaîne de requête
        if not filtered_params:
            return urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                "",  # chaîne de requête vide
                ""   # retire le fragment
            ))

        # Reconstruit la chaîne de requête (triée par ordre alphabétique pour garantir la cohérence)
        sorted_params = []
        for key in sorted(filtered_params.keys()):
            for value in filtered_params[key]:
                sorted_params.append((key, value))

        new_query = urlencode(sorted_params)

        # Reconstruit l'URL (en retirant le fragment)
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            ""  # retire le fragment
        ))

        return normalized

    except Exception:
        # En cas d'échec de l'analyse, retourne l'URL d'origine
        return url
