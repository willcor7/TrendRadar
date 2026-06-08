# coding=utf-8
"""
Module de traitement des données

Fournit les fonctions de lecture et de détection des données :
- read_all_today_titles : lit tous les titres du jour depuis le backend de stockage
- detect_latest_new_titles : détecte les nouveaux titres du dernier lot

Author: TrendRadar Team
"""

from typing import Dict, List, Tuple, Optional


def read_all_today_titles_from_storage(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
) -> Tuple[Dict, Dict, Dict]:
    """
    Lit tous les titres du jour depuis le backend de stockage (données SQLite).

    Args:
        storage_manager: instance du gestionnaire de stockage
        current_platform_ids: liste des ID de plateformes actuellement surveillées (sert au filtrage)

    Returns:
        Tuple[Dict, Dict, Dict]: (all_results, id_to_name, title_info)
    """
    try:
        news_data = storage_manager.get_today_all_data()

        if not news_data or not news_data.items:
            return {}, {}, {}

        all_results = {}
        final_id_to_name = {}
        title_info = {}

        for source_id, news_list in news_data.items.items():
            # Filtrage par plateforme
            if current_platform_ids is not None and source_id not in current_platform_ids:
                continue

            # On récupère le nom de la source
            source_name = news_data.id_to_name.get(source_id, source_id)
            final_id_to_name[source_id] = source_name

            if source_id not in all_results:
                all_results[source_id] = {}
                title_info[source_id] = {}

            for item in news_list:
                title = item.title
                ranks = item.ranks or [item.rank]
                first_time = item.first_time or item.crawl_time
                last_time = item.last_time or item.crawl_time
                count = item.count
                rank_timeline = item.rank_timeline

                all_results[source_id][title] = {
                    "ranks": ranks,
                    "url": item.url or "",
                    "mobileUrl": item.mobile_url or "",
                }

                title_info[source_id][title] = {
                    "first_time": first_time,
                    "last_time": last_time,
                    "count": count,
                    "ranks": ranks,
                    "url": item.url or "",
                    "mobileUrl": item.mobile_url or "",
                    "rank_timeline": rank_timeline,
                }

        return all_results, final_id_to_name, title_info

    except Exception as e:
        print(f"[stockage] Échec de la lecture des données depuis le backend de stockage : {e}")
        return {}, {}, {}


def read_all_today_titles(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
    quiet: bool = False,
) -> Tuple[Dict, Dict, Dict]:
    """
    Lit tous les titres du jour (depuis le backend de stockage).

    Args:
        storage_manager: instance du gestionnaire de stockage
        current_platform_ids: liste des ID de plateformes actuellement surveillées (sert au filtrage)
        quiet: indique s'il faut activer le mode silencieux (ne pas afficher de journal)

    Returns:
        Tuple[Dict, Dict, Dict]: (all_results, id_to_name, title_info)
    """
    all_results, final_id_to_name, title_info = read_all_today_titles_from_storage(
        storage_manager, current_platform_ids
    )

    if not quiet:
        if all_results:
            total_count = sum(len(titles) for titles in all_results.values())
            print(f"[stockage] {total_count} titres lus depuis le backend de stockage")
        else:
            print("[stockage] Aucune donnée pour le moment aujourd'hui")

    return all_results, final_id_to_name, title_info


def detect_latest_new_titles_from_storage(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
) -> Dict:
    """
    Détecte les nouveaux titres du dernier lot depuis le backend de stockage.

    Args:
        storage_manager: instance du gestionnaire de stockage
        current_platform_ids: liste des ID de plateformes actuellement surveillées (sert au filtrage)

    Returns:
        Dict: nouveaux titres {source_id: {title: title_data}}
    """
    try:
        # On récupère les données de la dernière collecte
        latest_data = storage_manager.get_latest_crawl_data()
        if not latest_data or not latest_data.items:
            return {}

        # On récupère toutes les données historiques
        all_data = storage_manager.get_today_all_data()
        if not all_data or not all_data.items:
            # Aucune donnée historique (première collecte) : il ne doit pas y avoir de « nouveau » titre
            return {}

        # On récupère l'horodatage du dernier lot
        latest_time = latest_data.crawl_time

        # Étape 1 : on rassemble les titres du dernier lot (ceux dont last_crawl_time = latest_time)
        latest_titles = {}
        for source_id, news_list in latest_data.items.items():
            if current_platform_ids is not None and source_id not in current_platform_ids:
                continue
            latest_titles[source_id] = {}
            for item in news_list:
                latest_titles[source_id][item.title] = {
                    "ranks": [item.rank],
                    "url": item.url or "",
                    "mobileUrl": item.mobile_url or "",
                }

        # Étape 2 : on rassemble les titres historiques
        # Logique clé : un titre est considéré comme historique dès lors que son first_crawl_time < latest_time
        # Ainsi, même si un même titre possède plusieurs enregistrements (URL différentes), il suffit qu'un seul d'entre eux soit historique pour que le titre soit compté comme historique
        historical_titles = {}
        for source_id, news_list in all_data.items.items():
            if current_platform_ids is not None and source_id not in current_platform_ids:
                continue

            historical_titles[source_id] = set()
            for item in news_list:
                first_time = item.first_time or item.crawl_time
                # Si la première apparition de cet enregistrement est antérieure au dernier lot, alors ce titre est un titre historique
                if first_time < latest_time:
                    historical_titles[source_id].add(item.title)

        # On vérifie s'il s'agit de la première collecte de la journée (aucun titre historique)
        # Si l'ensemble des titres historiques de toutes les plateformes est vide, c'est qu'il n'y a qu'un seul lot de collecte
        # Dans ce cas, on considère tous les titres du dernier lot comme « nouveaux » (pour le premier envoi en mode incrémental)
        has_historical_data = any(len(titles) > 0 for titles in historical_titles.values())
        if not has_historical_data:
            # Première collecte : on retourne tous les titres les plus récents comme « nouveaux »
            return latest_titles

        # Étape 3 : on trouve les nouveaux titres = titres du dernier lot - titres historiques
        new_titles = {}
        for source_id, source_latest_titles in latest_titles.items():
            historical_set = historical_titles.get(source_id, set())
            source_new_titles = {}

            for title, title_data in source_latest_titles.items():
                if title not in historical_set:
                    source_new_titles[title] = title_data

            if source_new_titles:
                new_titles[source_id] = source_new_titles

        return new_titles

    except Exception as e:
        print(f"[stockage] Échec de la détection des nouveaux titres depuis le backend de stockage : {e}")
        return {}


def detect_latest_new_titles(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
    quiet: bool = False,
) -> Dict:
    """
    Détecte les nouveaux titres du dernier lot de la journée (depuis le backend de stockage).

    Args:
        storage_manager: instance du gestionnaire de stockage
        current_platform_ids: liste des ID de plateformes actuellement surveillées (sert au filtrage)
        quiet: indique s'il faut activer le mode silencieux (ne pas afficher de journal)

    Returns:
        Dict: nouveaux titres {source_id: {title: title_data}}
    """
    new_titles = detect_latest_new_titles_from_storage(storage_manager, current_platform_ids)
    if new_titles and not quiet:
        total_new = sum(len(titles) for titles in new_titles.values())
        print(f"[stockage] {total_new} nouveaux titres détectés depuis le backend de stockage")
    return new_titles
