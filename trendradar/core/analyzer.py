# coding=utf-8
"""
Module d'analyse statistique

Fournit les fonctions de statistiques et d'analyse des actualités :
- calculate_news_weight : calcule le poids d'une actualité
- format_time_display : met en forme l'affichage de l'heure
- count_word_frequency : calcule la fréquence des mots
"""

from typing import Dict, List, Tuple, Optional, Callable

from trendradar.core.frequency import matches_word_groups, _word_matches
from trendradar.utils.time import DEFAULT_TIMEZONE


def calculate_news_weight(
    title_data: Dict,
    rank_threshold: int,
    weight_config: Dict,
) -> float:
    """
    Calcule le poids d'une actualité, utilisé pour le tri.

    Args:
        title_data: données du titre, contenant ranks et count
        rank_threshold: seuil de classement
        weight_config: configuration des poids {RANK_WEIGHT, FREQUENCY_WEIGHT, HOTNESS_WEIGHT}

    Returns:
        float: le poids calculé
    """
    ranks = title_data.get("ranks", [])
    if not ranks:
        return 0.0

    count = title_data.get("count", len(ranks))

    # En un seul parcours, on calcule la somme des scores de classement et le nombre de classements élevés
    rank_score_sum = 0
    high_rank_count = 0
    for rank in ranks:
        rank_score_sum += 11 - min(rank, 10)
        if rank <= rank_threshold:
            high_rank_count += 1

    # Normalisation entre 0 et 100 (pour s'aligner sur l'échelle de frequency_weight et hotness_weight)
    rank_weight = (rank_score_sum / len(ranks)) * 10

    # Poids de fréquence : min(nombre d'apparitions, 10) × 10
    frequency_weight = min(count, 10) * 10

    # Bonus de popularité : nombre de classements élevés / nombre total d'apparitions × 100
    hotness_ratio = high_rank_count / len(ranks)
    hotness_weight = hotness_ratio * 100

    total_weight = (
        rank_weight * weight_config["RANK_WEIGHT"]
        + frequency_weight * weight_config["FREQUENCY_WEIGHT"]
        + hotness_weight * weight_config["HOTNESS_WEIGHT"]
    )

    return total_weight


def format_time_display(
    first_time: str,
    last_time: str,
    convert_time_func: Callable[[str], str],
) -> str:
    """
    Met en forme l'affichage de l'heure (convertit HH-MM en HH:MM).

    Args:
        first_time: heure de première apparition
        last_time: heure de dernière apparition
        convert_time_func: fonction de conversion du format d'heure

    Returns:
        str: chaîne d'affichage de l'heure mise en forme
    """
    if not first_time:
        return ""
    # On convertit au format d'affichage
    first_display = convert_time_func(first_time)
    last_display = convert_time_func(last_time)
    if first_display == last_display or not last_display:
        return first_display
    else:
        return f"[{first_display} ~ {last_display}]"


def count_word_frequency(
    results: Dict,
    word_groups: List[Dict],
    filter_words: List[str],
    id_to_name: Dict,
    title_info: Optional[Dict] = None,
    rank_threshold: int = 3,
    new_titles: Optional[Dict] = None,
    mode: str = "daily",
    global_filters: Optional[List[str]] = None,
    weight_config: Optional[Dict] = None,
    max_news_per_keyword: int = 0,
    sort_by_position_first: bool = False,
    is_first_crawl_func: Optional[Callable[[], bool]] = None,
    convert_time_func: Optional[Callable[[str], str]] = None,
    quiet: bool = False,
) -> Tuple[List[Dict], int]:
    """
    Calcule la fréquence des mots ; prend en charge les mots obligatoires, les mots-clés de fréquence, les mots de filtrage et les mots de filtrage global, et marque les nouveaux titres.

    Args:
        results: résultat de la collecte {source_id: {title: title_data}}
        word_groups: liste de configuration des groupes de mots
        filter_words: liste des mots de filtrage
        id_to_name: correspondance ID vers nom
        title_info: informations statistiques sur les titres (optionnel)
        rank_threshold: seuil de classement
        new_titles: nouveaux titres (optionnel)
        mode: mode de rapport (daily/incremental/current)
        global_filters: mots de filtrage global (optionnel)
        weight_config: configuration des poids
        max_news_per_keyword: nombre maximal d'affichages par mot-clé
        sort_by_position_first: indique s'il faut trier en priorité par position de configuration
        is_first_crawl_func: fonction détectant s'il s'agit de la première collecte de la journée
        convert_time_func: fonction de conversion du format d'heure
        quiet: indique s'il faut activer le mode silencieux (ne pas afficher de journal)

    Returns:
        Tuple[List[Dict], int]: (liste des résultats statistiques, nombre total de titres)
    """
    # Configuration des poids par défaut
    if weight_config is None:
        weight_config = {
            "RANK_WEIGHT": 0.6,
            "FREQUENCY_WEIGHT": 0.3,
            "HOTNESS_WEIGHT": 0.1,
        }

    # Fonction de conversion d'heure par défaut
    if convert_time_func is None:
        convert_time_func = lambda x: x

    # Fonction de détection de première collecte par défaut
    if is_first_crawl_func is None:
        is_first_crawl_func = lambda: True

    # Si aucun groupe de mots n'est configuré, on crée un groupe de mots virtuel englobant toutes les actualités
    if not word_groups:
        print("La configuration des mots-clés est vide : toutes les actualités seront affichées")
        word_groups = [{"required": [], "normal": [], "group_key": "Toutes les actualités"}]
        filter_words = []  # On vide les mots de filtrage pour afficher toutes les actualités

    is_first_today = is_first_crawl_func()

    # On détermine la source de données à traiter et la logique de marquage des nouveautés
    if mode == "incremental":
        if is_first_today:
            # Mode incrémental + première collecte du jour : on traite toutes les actualités et on les marque toutes comme nouvelles
            results_to_process = results
            all_news_are_new = True
        else:
            # Mode incrémental + collecte non initiale du jour : on ne traite que les nouvelles actualités
            results_to_process = new_titles if new_titles else {}
            all_news_are_new = True
    elif mode == "current":
        # Mode current : on ne traite que les actualités du lot horaire actuel, mais les informations statistiques proviennent de tout l'historique
        if title_info:
            latest_time = None
            for source_titles in title_info.values():
                for title_data in source_titles.values():
                    last_time = title_data.get("last_time", "")
                    if last_time:
                        if latest_time is None or last_time > latest_time:
                            latest_time = last_time

            # On ne traite que les actualités dont last_time est égal à l'heure la plus récente
            if latest_time:
                results_to_process = {}
                for source_id, source_titles in results.items():
                    if source_id in title_info:
                        filtered_titles = {}
                        for title, title_data in source_titles.items():
                            if title in title_info[source_id]:
                                info = title_info[source_id][title]
                                if info.get("last_time") == latest_time:
                                    filtered_titles[title] = title_data
                        if filtered_titles:
                            results_to_process[source_id] = filtered_titles

                if not quiet:
                    print(
                        f"Mode classement actuel : heure la plus récente {latest_time}, {sum(len(titles) for titles in results_to_process.values())} actualités du classement actuel retenues"
                    )
            else:
                results_to_process = results
        else:
            results_to_process = results
        all_news_are_new = False
    else:
        # Mode synthèse du jour : on traite toutes les actualités
        results_to_process = results
        all_news_are_new = False
        total_input_news = sum(len(titles) for titles in results.values())
        filter_status = (
            "affichage complet"
            if len(word_groups) == 1 and word_groups[0]["group_key"] == "Toutes les actualités"
            else "filtrage par mots-clés"
        )
        print(f"Mode synthèse du jour : {total_input_news} actualités traitées, mode : {filter_status}")

    word_stats = {}
    total_titles = 0
    processed_titles = {}
    matched_new_count = 0

    if title_info is None:
        title_info = {}
    if new_titles is None:
        new_titles = {}

    for group in word_groups:
        group_key = group["group_key"]
        word_stats[group_key] = {"count": 0, "titles": {}}

    for source_id, titles_data in results_to_process.items():
        total_titles += len(titles_data)

        if source_id not in processed_titles:
            processed_titles[source_id] = {}

        for title, title_data in titles_data.items():
            if title in processed_titles.get(source_id, {}):
                continue

            # On utilise la logique de correspondance unifiée
            matches_frequency_words = matches_word_groups(
                title, word_groups, filter_words, global_filters
            )

            if not matches_frequency_words:
                continue

            # En mode incrémental ou lors de la première passe du mode current, on compte le nombre de nouvelles actualités correspondantes
            if (mode == "incremental" and all_news_are_new) or (
                mode == "current" and is_first_today
            ):
                matched_new_count += 1

            source_ranks = title_data.get("ranks", [])
            source_url = title_data.get("url", "")
            source_mobile_url = title_data.get("mobileUrl", "")

            # On trouve le groupe de mots correspondant (conversion défensive pour garantir la sûreté du type)
            title_lower = str(title).lower() if not isinstance(title, str) else title.lower()
            for group in word_groups:
                required_words = group["required"]
                normal_words = group["normal"]

                # En mode « Toutes les actualités », tous les titres correspondent au premier (et unique) groupe de mots
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "Toutes les actualités":
                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []
                else:
                    # Logique de correspondance d'origine (prend en charge la syntaxe des expressions régulières)
                    if required_words:
                        all_required_present = all(
                            _word_matches(req_item, title_lower)
                            for req_item in required_words
                        )
                        if not all_required_present:
                            continue

                    if normal_words:
                        any_normal_present = any(
                            _word_matches(normal_item, title_lower)
                            for normal_item in normal_words
                        )
                        if not any_normal_present:
                            continue

                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []

                first_time = ""
                last_time = ""
                count_info = 1
                ranks = source_ranks if source_ranks else []
                url = source_url
                mobile_url = source_mobile_url
                rank_timeline = []

                # En mode current, on récupère les données complètes depuis les informations statistiques historiques
                if (
                    mode == "current"
                    and title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)
                    rank_timeline = info.get("rank_timeline", [])
                elif (
                    title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)
                    rank_timeline = info.get("rank_timeline", [])

                if not ranks:
                    ranks = [99]

                time_display = format_time_display(first_time, last_time, convert_time_func)

                source_name = id_to_name.get(source_id, source_id)

                # On détermine s'il s'agit d'une nouveauté
                is_new = False
                if all_news_are_new:
                    # En mode incrémental, toutes les actualités traitées sont nouvelles ; de même pour toutes les actualités de la première collecte du jour
                    is_new = True
                elif new_titles and source_id in new_titles:
                    # On vérifie si le titre figure dans la liste des nouveautés
                    new_titles_for_source = new_titles[source_id]
                    is_new = title in new_titles_for_source

                word_stats[group_key]["titles"][source_id].append(
                    {
                        "title": title,
                        "source_name": source_name,
                        "first_time": first_time,
                        "last_time": last_time,
                        "time_display": time_display,
                        "count": count_info,
                        "ranks": ranks,
                        "rank_threshold": rank_threshold,
                        "url": url,
                        "mobileUrl": mobile_url,
                        "is_new": is_new,
                        "rank_timeline": rank_timeline,
                    }
                )

                if source_id not in processed_titles:
                    processed_titles[source_id] = {}
                processed_titles[source_id][title] = True

                break

    # Enfin, on affiche de manière uniforme les informations de synthèse
    if mode == "incremental":
        if is_first_today:
            total_input_news = sum(len(titles) for titles in results.values())
            filter_status = (
                "affichage complet"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "Toutes les actualités"
                else "correspondance par mots-clés"
            )
            if not quiet:
                print(
                    f"Mode incrémental : première collecte du jour, {matched_new_count} actualités sur {total_input_news} en {filter_status}"
                )
        else:
            if new_titles:
                total_new_count = sum(len(titles) for titles in new_titles.values())
                filter_status = (
                    "affichage complet"
                    if len(word_groups) == 1
                    and word_groups[0]["group_key"] == "Toutes les actualités"
                    else "correspondance par mots-clés"
                )
                if not quiet:
                    print(
                        f"Mode incrémental : {matched_new_count} actualités sur {total_new_count} nouvelles en {filter_status}"
                    )
                    if matched_new_count == 0 and len(word_groups) > 1:
                        print("Mode incrémental : aucune nouvelle actualité ne correspond aux mots-clés, aucune notification ne sera envoyée")
            else:
                if not quiet:
                    print("Mode incrémental : aucune nouvelle actualité détectée")
    elif mode == "current":
        total_input_news = sum(len(titles) for titles in results_to_process.values())
        if is_first_today:
            filter_status = (
                "affichage complet"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "Toutes les actualités"
                else "correspondance par mots-clés"
            )
            if not quiet:
                print(
                    f"Mode classement actuel : première collecte du jour, {matched_new_count} actualités sur {total_input_news} du classement actuel en {filter_status}"
                )
        else:
            matched_count = sum(stat["count"] for stat in word_stats.values())
            filter_status = (
                "affichage complet"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "Toutes les actualités"
                else "correspondance par mots-clés"
            )
            if not quiet:
                print(
                    f"Mode classement actuel : {matched_count} actualités sur {total_input_news} du classement actuel en {filter_status}"
                )

    stats = []
    # On crée la correspondance entre group_key et position, nombre maximal, nom d'affichage
    group_key_to_position = {
        group["group_key"]: idx for idx, group in enumerate(word_groups)
    }
    group_key_to_max_count = {
        group["group_key"]: group.get("max_count", 0) for group in word_groups
    }
    group_key_to_display_name = {
        group["group_key"]: group.get("display_name") for group in word_groups
    }

    for group_key, data in word_stats.items():
        all_titles = []
        for source_id, title_list in data["titles"].items():
            all_titles.extend(title_list)

        # Tri par poids
        sorted_titles = sorted(
            all_titles,
            key=lambda x: (
                -calculate_news_weight(x, rank_threshold, weight_config),
                min(x["ranks"]) if x["ranks"] else 999,
                -x["count"],
            ),
        )

        # On applique la limite du nombre maximal d'affichages (priorité : configuration propre au groupe > configuration globale)
        group_max_count = group_key_to_max_count.get(group_key, 0)
        if group_max_count == 0:
            # On utilise la configuration globale
            group_max_count = max_news_per_keyword

        if group_max_count > 0:
            sorted_titles = sorted_titles[:group_max_count]

        # On privilégie display_name, sinon on utilise group_key
        display_word = group_key_to_display_name.get(group_key) or group_key

        stats.append(
            {
                "word": display_word,
                "count": data["count"],
                "position": group_key_to_position.get(group_key, 999),
                "titles": sorted_titles,
                "percentage": (
                    round(data["count"] / total_titles * 100, 2)
                    if total_titles > 0
                    else 0
                ),
            }
        )

    # On choisit la priorité de tri selon la configuration
    if sort_by_position_first:
        # D'abord par position de configuration, puis par nombre d'occurrences
        stats.sort(key=lambda x: (x["position"], -x["count"]))
    else:
        # D'abord par nombre d'occurrences, puis par position de configuration (logique d'origine)
        stats.sort(key=lambda x: (-x["count"], x["position"]))

    # On affiche le nombre d'actualités correspondantes après filtrage
    matched_news_count = sum(len(stat["titles"]) for stat in stats if stat["count"] > 0)
    if not quiet and mode == "daily":
        print(f"Mode synthèse du jour : {total_titles} actualités traitées, mode : filtrage par mots-clés")
        print(f"Après filtrage par mots-clés : {matched_news_count} actualités correspondantes")

    return stats, total_titles


def count_rss_frequency(
    rss_items: List[Dict],
    word_groups: List[Dict],
    filter_words: List[str],
    global_filters: Optional[List[str]] = None,
    new_items: Optional[List[Dict]] = None,
    max_news_per_keyword: int = 0,
    sort_by_position_first: bool = False,
    timezone: str = DEFAULT_TIMEZONE,
    rank_threshold: int = 5,
    quiet: bool = False,
) -> Tuple[List[Dict], int]:
    """
    Regroupe et compte les entrées RSS par mot-clé (format cohérent avec les statistiques des classements de tendances).

    Args:
        rss_items: liste des entrées RSS, chaque entrée contenant :
            - title : titre
            - feed_id : ID de la source RSS
            - feed_name : nom de la source RSS
            - url : lien de l'article
            - published_at : date de publication (format ISO)
        word_groups: liste de configuration des groupes de mots
        filter_words: liste des mots de filtrage
        global_filters: mots de filtrage global (optionnel)
        new_items: liste des nouvelles entrées (optionnel, sert à marquer is_new)
        max_news_per_keyword: nombre maximal d'affichages par mot-clé
        sort_by_position_first: indique s'il faut trier en priorité par position de configuration
        timezone: nom du fuseau horaire (sert à la mise en forme de l'heure)
        quiet: indique s'il faut activer le mode silencieux

    Returns:
        Tuple[List[Dict], int]: (liste des résultats statistiques, nombre total d'entrées)
        Le format des résultats est cohérent avec celui des classements de tendances :
        [
            {
                "word": "mot-clé",
                "count": 5,
                "position": 0,
                "titles": [
                    {
                        "title": "titre",
                        "source_name": "Hacker News",
                        "time_display": "12-29 08:20",
                        "count": 1,
                        "ranks": [1],  # le RSS utilise l'ordre de publication comme classement
                        "rank_threshold": 50,
                        "url": "...",
                        "mobile_url": "",
                        "is_new": True/False
                    }
                ],
                "percentage": 10.0
            }
        ]
    """
    from trendradar.utils.time import format_iso_time_friendly

    if not rss_items:
        return [], 0

    # Si aucun groupe de mots n'est configuré, on crée un groupe de mots virtuel englobant toutes les entrées
    if not word_groups:
        if not quiet:
            print("[RSS] La configuration des mots-clés est vide : toutes les entrées RSS seront affichées")
        word_groups = [{"required": [], "normal": [], "group_key": "Tous les RSS"}]
        filter_words = []

    # On crée l'ensemble des URL des nouvelles entrées, pour une recherche rapide
    new_urls = set()
    if new_items:
        for item in new_items:
            if item.get("url"):
                new_urls.add(item["url"])

    # On initialise les statistiques des groupes de mots
    word_stats = {}
    for group in word_groups:
        group_key = group["group_key"]
        word_stats[group_key] = {"count": 0, "titles": []}

    total_items = len(rss_items)
    processed_urls = set()  # sert à la déduplication

    # On attribue à chaque entrée un « classement » fondé sur la date de publication
    # On trie par date de publication, les plus récentes en tête
    sorted_items = sorted(
        rss_items,
        key=lambda x: x.get("published_at", ""),
        reverse=True
    )
    url_to_rank = {item.get("url", ""): idx + 1 for idx, item in enumerate(sorted_items)}

    for item in rss_items:
        title = item.get("title", "")
        url = item.get("url", "")

        # Déduplication
        if url and url in processed_urls:
            continue
        if url:
            processed_urls.add(url)

        # On utilise la logique de correspondance unifiée
        if not matches_word_groups(title, word_groups, filter_words, global_filters):
            continue

        # On trouve le groupe de mots correspondant
        title_lower = title.lower()
        for group in word_groups:
            required_words = group["required"]
            normal_words = group["normal"]
            group_key = group["group_key"]

            # Mode « Tous les RSS » : toutes les entrées correspondent
            if len(word_groups) == 1 and word_groups[0]["group_key"] == "Tous les RSS":
                matched = True
            else:
                # On vérifie les mots obligatoires (prend en charge la syntaxe des expressions régulières)
                if required_words:
                    all_required_present = all(
                        _word_matches(req_item, title_lower)
                        for req_item in required_words
                    )
                    if not all_required_present:
                        continue

                # On vérifie les mots ordinaires (prend en charge la syntaxe des expressions régulières)
                if normal_words:
                    any_normal_present = any(
                        _word_matches(normal_item, title_lower)
                        for normal_item in normal_words
                    )
                    if not any_normal_present:
                        continue

                matched = True

            if matched:
                word_stats[group_key]["count"] += 1

                # On met en forme l'affichage de l'heure
                published_at = item.get("published_at", "")
                time_display = format_iso_time_friendly(published_at, timezone, include_date=True) if published_at else ""

                # On détermine s'il s'agit d'une nouveauté
                is_new = url in new_urls if url else False

                # On récupère le classement (fondé sur l'ordre de publication)
                rank = url_to_rank.get(url, 99) if url else 99

                title_data = {
                    "title": title,
                    "source_name": item.get("feed_name", item.get("feed_id", "RSS")),
                    "time_display": time_display,
                    "count": 1,  # une entrée RSS n'apparaît généralement qu'une seule fois
                    "ranks": [rank],
                    "rank_threshold": rank_threshold,
                    "url": url,
                    "mobile_url": "",
                    "is_new": is_new,
                }
                word_stats[group_key]["titles"].append(title_data)
                break  # une entrée ne correspond qu'au premier groupe de mots

    # On construit les résultats statistiques
    stats = []
    group_key_to_position = {
        group["group_key"]: idx for idx, group in enumerate(word_groups)
    }
    group_key_to_max_count = {
        group["group_key"]: group.get("max_count", 0) for group in word_groups
    }
    group_key_to_display_name = {
        group["group_key"]: group.get("display_name") for group in word_groups
    }

    for group_key, data in word_stats.items():
        if data["count"] == 0:
            continue

        # Tri par date de publication (les plus récentes en tête)
        sorted_titles = sorted(
            data["titles"],
            key=lambda x: x["ranks"][0] if x["ranks"] else 999
        )

        # On applique la limite du nombre maximal d'affichages
        group_max_count = group_key_to_max_count.get(group_key, 0)
        if group_max_count == 0:
            group_max_count = max_news_per_keyword
        if group_max_count > 0:
            sorted_titles = sorted_titles[:group_max_count]

        # On privilégie display_name, sinon on utilise group_key
        display_word = group_key_to_display_name.get(group_key) or group_key

        stats.append({
            "word": display_word,
            "count": data["count"],
            "position": group_key_to_position.get(group_key, 999),
            "titles": sorted_titles,
            "percentage": round(data["count"] / total_items * 100, 2) if total_items > 0 else 0,
        })

    # Tri
    if sort_by_position_first:
        stats.sort(key=lambda x: (x["position"], -x["count"]))
    else:
        stats.sort(key=lambda x: (-x["count"], x["position"]))

    matched_count = sum(stat["count"] for stat in stats)
    if not quiet:
        print(f"[RSS] Statistiques groupées par mot-clé : {matched_count}/{total_items} entrées correspondantes")

    return stats, total_items


def convert_keyword_stats_to_platform_stats(
    keyword_stats: List[Dict],
    weight_config: Dict,
    rank_threshold: int = 5,
) -> List[Dict]:
    """
    Convertit les statistiques regroupées par mot-clé en statistiques regroupées par plateforme.

    Args:
        keyword_stats: statistiques d'origine regroupées par mot-clé
        weight_config: configuration des poids
        rank_threshold: seuil de classement

    Returns:
        statistiques regroupées par plateforme, au format cohérent avec les stats d'origine
    """
    # 1. On rassemble toutes les actualités et on les regroupe par plateforme
    platform_map: Dict[str, List[Dict]] = {}

    for stat in keyword_stats:
        keyword = stat["word"]
        for title_data in stat["titles"]:
            source_name = title_data["source_name"]

            if source_name not in platform_map:
                platform_map[source_name] = []

            # On copie title_data et on y ajoute le mot-clé correspondant
            title_with_keyword = title_data.copy()
            title_with_keyword["matched_keyword"] = keyword
            platform_map[source_name].append(title_with_keyword)

    # 2. Déduplication (sur une même plateforme, un titre identique n'est conservé qu'une fois, en gardant le premier mot-clé correspondant)
    for source_name, titles in platform_map.items():
        seen_titles: Dict[str, bool] = {}
        unique_titles = []
        for title_data in titles:
            title_text = title_data["title"]
            if title_text not in seen_titles:
                seen_titles[title_text] = True
                unique_titles.append(title_data)
        platform_map[source_name] = unique_titles

    # 3. On trie par poids les actualités au sein de chaque plateforme
    for source_name, titles in platform_map.items():
        platform_map[source_name] = sorted(
            titles,
            key=lambda x: (
                -calculate_news_weight(x, rank_threshold, weight_config),
                min(x["ranks"]) if x["ranks"] else 999,
                -x["count"],
            ),
        )

    # 4. On construit les résultats statistiques par plateforme
    platform_stats = []
    for source_name, titles in platform_map.items():
        platform_stats.append({
            "word": source_name,  # le nom de la plateforme sert d'identifiant de regroupement
            "count": len(titles),
            "titles": titles,
            "percentage": 0,  # pourra être calculé ultérieurement
        })

    # 5. On trie les plateformes par nombre d'actualités
    platform_stats.sort(key=lambda x: -x["count"])

    return platform_stats
