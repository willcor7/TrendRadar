# coding=utf-8
"""
Module de découpage des messages en lots

Découpe le contenu des messages en lots pour ne pas dépasser les limites de chaque plateforme.
"""

from datetime import datetime
from typing import Dict, List, Optional, Callable

from trendradar.report.formatter import format_title_for_platform
from trendradar.report.helpers import format_rank_display
from trendradar.utils.time import DEFAULT_TIMEZONE, format_iso_time_friendly, convert_time_for_display
from trendradar.notification.batch import truncate_at_line_boundary


# === Fonctions auxiliaires de découpage sécurisé en lots ===

def _split_content_by_lines(
    content: str, footer: str, max_bytes: int, base_header: str
) -> List[str]:
    """Découpe un contenu trop long en plusieurs lots complets aux limites de ligne (chaque lot avec son footer)

    Aucun contenu n'est perdu : la partie en débordement est automatiquement répartie sur les lots suivants.

    Args:
        content: contenu du corps (sans footer, peut contenir base_header)
        footer: contenu de pied de page (date de mise à jour, etc.)
        max_bytes: nombre d'octets maximal par lot
        base_header: en-tête des lots suivants

    Returns:
        liste des lots complets (chaque élément = corps + footer, taille ≤ max_bytes)
    """
    footer_size = len(footer.encode("utf-8"))
    result_batches = []
    lines = content.split("\n")

    current = ""
    for line in lines:
        candidate = current + line + "\n"
        if len(candidate.encode("utf-8")) + footer_size > max_bytes and current.strip():
            result_batches.append(current + footer)
            current = base_header + line + "\n"
        else:
            current = candidate

    if current.strip():
        result_batches.append(current + footer)

    return result_batches


def _safe_append_batch(
    batches: List[str], content: str, footer: str, max_bytes: int,
    base_header: str = ""
) -> None:
    """Ajoute un lot en toute sécurité, en le découpant en plusieurs lots aux limites de ligne en cas de dépassement (sans perdre de contenu)

    Args:
        batches: liste des lots (modifiée sur place)
        content: contenu du corps (sans footer)
        footer: contenu de pied de page (date de mise à jour, etc.)
        max_bytes: nombre d'octets maximal
        base_header: en-tête des lots suivants en cas de débordement
    """
    full = content + footer
    if len(full.encode("utf-8")) <= max_bytes:
        batches.append(full)
        return

    split_batches = _split_content_by_lines(content, footer, max_bytes, base_header)
    if split_batches:
        batches.extend(split_batches)
    else:
        # cas extrême : une seule ligne dépasse déjà la limite, troncature forcée
        batches.append(truncate_at_line_boundary(full, max_bytes))


def _safe_new_batch(
    new_content: str, footer: str, max_bytes: int, base_header: str,
    batches: List[str] = None
) -> str:
    """Crée un nouveau lot en toute sécurité ; en cas de dépassement, répartit le contenu en débordement dans batches et renvoie le dernier segment comme current_batch

    Args:
        new_content: contenu complet du nouveau lot (contient base_header + section_header + ...)
        footer: contenu de pied de page
        max_bytes: nombre d'octets maximal
        base_header: en-tête de base
        batches: liste des lots, à laquelle la partie en débordement est ajoutée (optionnel)

    Returns:
        le current_batch auquel on peut continuer à ajouter du contenu en toute sécurité (taille + footer ≤ max_bytes)
    """
    if len((new_content + footer).encode("utf-8")) <= max_bytes:
        return new_content

    if batches is None:
        # impossible de répartir dans batches, on revient à la troncature à la limite d'une ligne
        footer_size = len(footer.encode("utf-8"))
        available = max_bytes - footer_size
        header_size = len(base_header.encode("utf-8"))
        if available <= header_size:
            return base_header
        return truncate_at_line_boundary(new_content, available)

    # découpage : les parties précédentes sont stockées dans batches, le dernier segment est renvoyé comme current_batch
    split_batches = _split_content_by_lines(new_content, footer, max_bytes, base_header)
    if len(split_batches) <= 1:
        # impossible de découper davantage, on renvoie tel quel (la suite est gérée par _safe_append_batch)
        return new_content

    # les N-1 premiers lots sont stockés dans batches
    batches.extend(split_batches[:-1])
    # on retire le footer du dernier lot pour en faire le current_batch (du contenu y sera encore ajouté ensuite)
    last = split_batches[-1]
    if last.endswith(footer):
        return last[: -len(footer)]
    return last


# configuration par défaut de la taille des lots
DEFAULT_BATCH_SIZES = {
    "dingtalk": 20000,
    "feishu": 29000,
    "ntfy": 3800,
    "default": 4000,
}

# ordre des zones par défaut
DEFAULT_REGION_ORDER = ["hotlist", "rss", "new_items", "standalone", "ai_analysis"]


def split_content_into_batches(
    report_data: Dict,
    format_type: str,
    update_info: Optional[Dict] = None,
    max_bytes: Optional[int] = None,
    mode: str = "daily",
    batch_sizes: Optional[Dict[str, int]] = None,
    feishu_separator: str = "---",
    region_order: Optional[List[str]] = None,
    get_time_func: Optional[Callable[[], datetime]] = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    timezone: str = DEFAULT_TIMEZONE,
    display_mode: str = "keyword",
    ai_content: Optional[str] = None,
    standalone_data: Optional[Dict] = None,
    rank_threshold: int = 10,
    ai_stats: Optional[Dict] = None,
    report_type: str = "rapport d'analyse des tendances",
    show_new_section: bool = True,
) -> List[str]:
    """Découpe le contenu du message en lots, en préservant l'intégrité du titre de groupe + au moins la première actualité (prend en charge Tendances + RSS fusionnés + Analyse IA + Zone d'affichage autonome)

    Les statistiques des tendances et les statistiques RSS sont affichées côte à côte, de même que les nouveautés des tendances et les nouveautés RSS.
    region_order contrôle l'ordre d'affichage de chaque zone.
    Le contenu de l'Analyse IA est affiché selon sa position dans region_order.
    La Zone d'affichage autonome est affichée selon sa position dans region_order.

    Args:
        report_data: dictionnaire des données du rapport, contient stats, new_titles, failed_ids, total_new_count
        format_type: type de format (feishu, dingtalk, wework, telegram, ntfy, bark, slack)
        update_info: informations de mise à jour de version (optionnel)
        max_bytes: nombre d'octets maximal (optionnel, à défaut la configuration par défaut est utilisée)
        mode: mode du rapport (daily, incremental, current)
        batch_sizes: dictionnaire de configuration de la taille des lots (optionnel)
        feishu_separator: séparateur des messages Feishu
        region_order: liste de l'ordre d'affichage des zones
        get_time_func: fonction renvoyant l'heure courante (optionnel)
        rss_items: liste des entrées RSS pour les statistiques (regroupées par source, pour l'envoi fusionné)
        rss_new_items: liste des nouvelles entrées RSS (optionnel, pour le bloc des nouveautés)
        timezone: nom du fuseau horaire (pour le formatage de l'heure des entrées RSS)
        display_mode: mode d'affichage (keyword = regroupement par mot-clé, platform = regroupement par plateforme)
        ai_content: contenu de l'Analyse IA (chaîne déjà rendue, optionnel)
        standalone_data: données de la Zone d'affichage autonome (optionnel), contient les listes platforms et rss_feeds
        ai_stats: données statistiques de l'Analyse IA (optionnel), contient total_news, analyzed_news, max_news_limit, etc.

    Returns:
        liste du contenu des messages après découpage en lots
    """
    if region_order is None:
        region_order = DEFAULT_REGION_ORDER
    # fusionne la configuration de la taille des lots
    sizes = {**DEFAULT_BATCH_SIZES, **(batch_sizes or {})}

    if max_bytes is None:
        if format_type == "dingtalk":
            max_bytes = sizes.get("dingtalk", 20000)
        elif format_type == "feishu":
            max_bytes = sizes.get("feishu", 29000)
        elif format_type == "ntfy":
            max_bytes = sizes.get("ntfy", 3800)
        else:
            max_bytes = sizes.get("default", 4000)

    batches = []

    total_hotlist_count = sum(
        len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
    )
    total_titles = total_hotlist_count
    
    # ajoute le nombre d'entrées RSS au total
    if rss_items:
        total_titles += sum(stat.get("count", 0) for stat in rss_items)

    now = get_time_func() if get_time_func else datetime.now()

    # construit les informations d'en-tête
    base_header = ""

    # marqueurs de mise en gras selon le format
    if format_type == "slack":
        b_s, b_e = "*", "*"
    elif format_type == "telegram":
        b_s, b_e = "", ""
    else:
        b_s, b_e = "**", "**"

    # extrait les données statistiques
    hotlist_total = report_data.get("hotlist_total", total_hotlist_count)
    new_count = report_data.get("total_new_count", 0)
    platform_total = report_data.get("platform_total", 0)
    failed_count = len(report_data.get("failed_ids", []))
    platform_success = platform_total - failed_count if platform_total else 0
    rss_matched = report_data.get("rss_matched_count", 0)
    rss_total_items = report_data.get("rss_total_count", 0)
    rss_source_total = report_data.get("rss_source_total", 0)
    rss_source_failed = report_data.get("rss_source_failed", 0)
    rss_source_success = max(0, rss_source_total - rss_source_failed)

    # === Partie supérieure : statistiques des données ===

    # 1. Total actualités
    rss_new_count = sum(len(stat.get("titles", [])) for stat in (rss_new_items or []))
    total_new = new_count + rss_new_count
    total_news_line = f"{b_s}Total actualités : {b_e} {total_titles} entrées"
    if total_new > 0:
        total_news_line += f" (nouv. {new_count} + {rss_new_count}) "
    base_header += f"{total_news_line}\n"

    # 2. Tendances
    hotlist_info = f"{b_s}Tendances : {b_e} {total_hotlist_count}/{hotlist_total}"
    if platform_total > 0:
        hotlist_info += f" (plateformes {platform_success}/{platform_total}) "
    base_header += f"{hotlist_info}\n"

    # 3. RSS
    if rss_source_total > 0:
        rss_info = f"{b_s}RSS : {b_e} {rss_matched}/{rss_total_items} (sources {rss_source_success}/{rss_source_total}) "
        base_header += f"{rss_info}\n"

    # 4. Zone d'affichage autonome (affichée uniquement si des données sont présentes)
    if standalone_data:
        sa_platform_count = sum(len(p.get("items", [])) for p in standalone_data.get("platforms", []))
        sa_rss_count = sum(len(f.get("items", [])) for f in standalone_data.get("rss_feeds", []))
        sa_total = sa_platform_count + sa_rss_count
        if sa_total > 0:
            sa_parts = []
            if sa_platform_count > 0:
                sa_parts.append(f"Tendances {sa_platform_count}")
            if sa_rss_count > 0:
                sa_parts.append(f"RSS {sa_rss_count}")
            base_header += f"{b_s}Affichage autonome : {b_e} {sa_total} entrées ({' + '.join(sa_parts)}) \n"

    # 5. Analyse IA (affichée uniquement si des données d'analyse sont présentes)
    standalone_analyzed = ai_stats.get("standalone_analyzed", 0) if ai_stats else 0
    ai_has_data = ai_stats and (ai_stats.get("analyzed_news", 0) > 0 or standalone_analyzed > 0)
    if ai_has_data:
        hotlist_analyzed = ai_stats.get("hotlist_analyzed", 0)
        rss_analyzed = ai_stats.get("rss_analyzed", 0)
        ai_mode_val = ai_stats.get("ai_mode", "")

        ai_parts = [str(hotlist_analyzed)]
        if ai_stats.get("include_rss", True):
            ai_parts.append(str(rss_analyzed))
        if ai_stats.get("include_standalone", False):
            ai_parts.append(str(standalone_analyzed))
        ai_display = " + ".join(ai_parts) if sum(int(p) for p in ai_parts) > 0 else "0"

        mode_suffix = ""
        if ai_mode_val and ai_mode_val != mode:
            mode_map = {"daily": "Synthèse de la journée", "current": "Classement actuel", "incremental": "Analyse incrémentale"}
            mode_suffix = f" [{mode_map.get(ai_mode_val, ai_mode_val)}]"

        base_header += f"{b_s}Analyse IA : {b_e} {ai_display}{mode_suffix}\n"

    # === Ligne vide de séparation ===
    base_header += "\n"

    # === Partie inférieure : métadonnées ===
    base_header += f"{b_s}Type : {b_e} {report_type}\n"
    base_header += f"{b_s}Heure : {b_e} {now.strftime('%Y-%m-%d %H:%M:%S')}\n"

    top_words = report_data.get("stats", [])[:3]
    if top_words:
        topics = " | ".join(f"{s['word']}({s['count']})" for s in top_words)
        base_header += f"{b_s}Sujet le plus populaire : {b_e} {topics}\n"

    if format_type in ("feishu", "dingtalk"):
        base_header += "\n---\n\n"
    else:
        base_header += "\n"

    base_footer = ""
    if format_type in ("wework", "bark"):
        base_footer = f"\n\n\n> Mis à jour le : {now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            base_footer += f"\n> TrendRadar nouvelle version détectée **{update_info['remote_version']}**, version actuelle **{update_info['current_version']}**"
    elif format_type == "telegram":
        base_footer = f"\n\nMis à jour le : {now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            base_footer += f"\nTrendRadar nouvelle version détectée {update_info['remote_version']}, version actuelle {update_info['current_version']}"
    elif format_type == "ntfy":
        base_footer = f"\n\n> Mis à jour le : {now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            base_footer += f"\n> TrendRadar nouvelle version détectée **{update_info['remote_version']}**, version actuelle **{update_info['current_version']}**"
    elif format_type == "feishu":
        base_footer = f"\n\n<font color='grey'>Mis à jour le : {now.strftime('%Y-%m-%d %H:%M:%S')}</font>"
        if update_info:
            base_footer += f"\n<font color='grey'>TrendRadar nouvelle version détectée {update_info['remote_version']}, version actuelle {update_info['current_version']}</font>"
    elif format_type == "dingtalk":
        base_footer = f"\n\n> Mis à jour le : {now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            base_footer += f"\n> TrendRadar nouvelle version détectée **{update_info['remote_version']}**, version actuelle **{update_info['current_version']}**"
    elif format_type == "slack":
        base_footer = f"\n\n_Mis à jour le : {now.strftime('%Y-%m-%d %H:%M:%S')}_"
        if update_info:
            base_footer += f"\n_TrendRadar nouvelle version détectée *{update_info['remote_version']}*, version actuelle *{update_info['current_version']}_"

    # choisit le titre des statistiques selon display_mode
    stats_title = "Statistiques des tendances" if display_mode == "keyword" else "Statistiques des actualités"
    stats_header = ""
    if report_data["stats"]:
        if format_type in ("wework", "bark"):
            stats_header = f"📊 **{stats_title}** (total : {total_hotlist_count} entrées)\n\n"
        elif format_type == "telegram":
            stats_header = f"📊 {stats_title} (total : {total_hotlist_count} entrées)\n\n"
        elif format_type == "ntfy":
            stats_header = f"📊 **{stats_title}** (total : {total_hotlist_count} entrées)\n\n"
        elif format_type == "feishu":
            stats_header = f"📊 **{stats_title}** (total : {total_hotlist_count} entrées)\n\n"
        elif format_type == "dingtalk":
            stats_header = f"📊 **{stats_title}** (total : {total_hotlist_count} entrées)\n\n"
        elif format_type == "slack":
            stats_header = f"📊 *{stats_title}* (total : {total_hotlist_count} entrées)\n\n"

    current_batch = base_header
    current_batch_has_content = False

    # traitement du cas où il n'y a aucune donnée de tendances
    # remarque : si ai_content est présent, ne pas renvoyer le message "aucune correspondance" ici, mais continuer pour traiter le contenu IA
    if (
        not report_data["stats"]
        and not report_data["new_titles"]
        and not report_data["failed_ids"]
        and not ai_content  # si du contenu IA est présent, ne pas renvoyer "aucune correspondance"
        and not rss_items  # si du contenu RSS est présent, ne pas renvoyer non plus
        and not standalone_data  # si des données de Zone d'affichage autonome sont présentes, ne pas renvoyer non plus
    ):
        if mode == "incremental":
            mode_text = "Aucune nouvelle tendance correspondante en mode incrémental"
        elif mode == "current":
            mode_text = "Aucune tendance correspondante pour le classement actuel"
        else:
            mode_text = "Aucune tendance correspondante"
        simple_content = f"📭 {mode_text}\n\n"
        final_content = base_header + simple_content + base_footer
        batches.append(final_content)
        return batches

    # définit la fonction de traitement des Statistiques des tendances
    def process_stats_section(current_batch, current_batch_has_content, batches, add_separator=True):
        """traite les Statistiques des tendances"""
        if not report_data["stats"]:
            return current_batch, current_batch_has_content, batches

        total_count = len(report_data["stats"])

        # décide d'ajouter ou non un séparateur en tête selon add_separator
        actual_stats_header = ""
        if add_separator and current_batch_has_content:
            # un séparateur est nécessaire
            if format_type == "feishu":
                actual_stats_header = f"\n{feishu_separator}\n\n{stats_header}"
            elif format_type == "dingtalk":
                actual_stats_header = f"\n---\n\n{stats_header}"
            elif format_type in ("wework", "bark"):
                actual_stats_header = f"\n\n\n\n{stats_header}"
            else:
                actual_stats_header = f"\n\n{stats_header}"
        else:
            # pas de séparateur nécessaire (première zone)
            actual_stats_header = stats_header

        # ajoute le titre des statistiques
        test_content = current_batch + actual_stats_header
        if (
            len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
            < max_bytes
        ):
            current_batch = test_content
            current_batch_has_content = True
        else:
            if current_batch_has_content:
                _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
            current_batch = _safe_new_batch(
                base_header + stats_header, base_footer, max_bytes, base_header, batches
            )
            current_batch_has_content = True

        # traite les groupes de mots un par un (garantit l'atomicité titre du groupe + première actualité)
        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]
            sequence_display = f"[{i + 1}/{total_count}]"

            # construit le titre du groupe de mots
            word_header = ""
            if format_type in ("wework", "bark"):
                if count >= 10:
                    word_header = (
                        f"🔥 {sequence_display} **{word}** : **{count}** entrées\n\n"
                    )
                elif count >= 5:
                    word_header = (
                        f"📈 {sequence_display} **{word}** : **{count}** entrées\n\n"
                    )
                else:
                    word_header = f"📌 {sequence_display} **{word}** : {count} entrées\n\n"
            elif format_type == "telegram":
                if count >= 10:
                    word_header = f"🔥 {sequence_display} {word} : {count} entrées\n\n"
                elif count >= 5:
                    word_header = f"📈 {sequence_display} {word} : {count} entrées\n\n"
                else:
                    word_header = f"📌 {sequence_display} {word} : {count} entrées\n\n"
            elif format_type == "ntfy":
                if count >= 10:
                    word_header = (
                        f"🔥 {sequence_display} **{word}** : **{count}** entrées\n\n"
                    )
                elif count >= 5:
                    word_header = (
                        f"📈 {sequence_display} **{word}** : **{count}** entrées\n\n"
                    )
                else:
                    word_header = f"📌 {sequence_display} **{word}** : {count} entrées\n\n"
            elif format_type == "feishu":
                if count >= 10:
                    word_header = f"🔥 <font color='grey'>{sequence_display}</font> **{word}** : <font color='red'>{count}</font> entrées\n\n"
                elif count >= 5:
                    word_header = f"📈 <font color='grey'>{sequence_display}</font> **{word}** : <font color='orange'>{count}</font> entrées\n\n"
                else:
                    word_header = f"📌 <font color='grey'>{sequence_display}</font> **{word}** : {count} entrées\n\n"
            elif format_type == "dingtalk":
                if count >= 10:
                    word_header = (
                        f"🔥 {sequence_display} **{word}** : **{count}** entrées\n\n"
                    )
                elif count >= 5:
                    word_header = (
                        f"📈 {sequence_display} **{word}** : **{count}** entrées\n\n"
                    )
                else:
                    word_header = f"📌 {sequence_display} **{word}** : {count} entrées\n\n"
            elif format_type == "slack":
                if count >= 10:
                    word_header = (
                        f"🔥 {sequence_display} *{word}* : *{count}* entrées\n\n"
                    )
                elif count >= 5:
                    word_header = (
                        f"📈 {sequence_display} *{word}* : *{count}* entrées\n\n"
                    )
                else:
                    word_header = f"📌 {sequence_display} *{word}* : {count} entrées\n\n"

            # construit la première actualité
            # display_mode : keyword = affiche la source, platform = affiche le mot-clé
            show_source = display_mode == "keyword"
            show_keyword = display_mode == "platform"
            first_news_line = ""
            if stat["titles"]:
                first_title_data = stat["titles"][0]
                if format_type in ("wework", "bark"):
                    formatted_title = format_title_for_platform(
                        "wework", first_title_data, show_source=show_source, show_keyword=show_keyword
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", first_title_data, show_source=show_source, show_keyword=show_keyword
                    )
                elif format_type == "ntfy":
                    formatted_title = format_title_for_platform(
                        "ntfy", first_title_data, show_source=show_source, show_keyword=show_keyword
                    )
                elif format_type == "feishu":
                    formatted_title = format_title_for_platform(
                        "feishu", first_title_data, show_source=show_source, show_keyword=show_keyword
                    )
                elif format_type == "dingtalk":
                    formatted_title = format_title_for_platform(
                        "dingtalk", first_title_data, show_source=show_source, show_keyword=show_keyword
                    )
                elif format_type == "slack":
                    formatted_title = format_title_for_platform(
                        "slack", first_title_data, show_source=show_source, show_keyword=show_keyword
                    )
                else:
                    formatted_title = f"{first_title_data['title']}"

                first_news_line = f"  1. {formatted_title}\n"
                if len(stat["titles"]) > 1:
                    first_news_line += "\n"

            # vérification d'atomicité : le titre du groupe de mots et la première actualité doivent être traités ensemble
            word_with_first_news = word_header + first_news_line
            test_content = current_batch + word_with_first_news

            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                >= max_bytes
            ):
                if current_batch_has_content:
                    _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
                current_batch = _safe_new_batch(
                    base_header + stats_header + word_with_first_news,
                    base_footer, max_bytes, base_header, batches
                )
                current_batch_has_content = True
                start_index = 1
            else:
                current_batch = test_content
                current_batch_has_content = True
                start_index = 1

            # traite les actualités restantes
            for j in range(start_index, len(stat["titles"])):
                title_data = stat["titles"][j]
                if format_type in ("wework", "bark"):
                    formatted_title = format_title_for_platform(
                        "wework", title_data, show_source=show_source, show_keyword=show_keyword
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", title_data, show_source=show_source, show_keyword=show_keyword
                    )
                elif format_type == "ntfy":
                    formatted_title = format_title_for_platform(
                        "ntfy", title_data, show_source=show_source, show_keyword=show_keyword
                    )
                elif format_type == "feishu":
                    formatted_title = format_title_for_platform(
                        "feishu", title_data, show_source=show_source, show_keyword=show_keyword
                    )
                elif format_type == "dingtalk":
                    formatted_title = format_title_for_platform(
                        "dingtalk", title_data, show_source=show_source, show_keyword=show_keyword
                    )
                elif format_type == "slack":
                    formatted_title = format_title_for_platform(
                        "slack", title_data, show_source=show_source, show_keyword=show_keyword
                    )
                else:
                    formatted_title = f"{title_data['title']}"

                news_line = f"  {j + 1}. {formatted_title}\n"
                if j < len(stat["titles"]) - 1:
                    news_line += "\n"

                test_content = current_batch + news_line
                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    >= max_bytes
                ):
                    if current_batch_has_content:
                        _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
                    current_batch = _safe_new_batch(
                        base_header + stats_header + word_header + news_line,
                        base_footer, max_bytes, base_header, batches
                    )
                    current_batch_has_content = True
                else:
                    current_batch = test_content
                    current_batch_has_content = True

            # séparateur entre les groupes de mots
            if i < len(report_data["stats"]) - 1:
                separator = ""
                if format_type in ("wework", "bark"):
                    separator = f"\n\n\n\n"
                elif format_type == "telegram":
                    separator = f"\n\n"
                elif format_type == "ntfy":
                    separator = f"\n\n"
                elif format_type == "feishu":
                    separator = f"\n{feishu_separator}\n\n"
                elif format_type == "dingtalk":
                    separator = f"\n---\n\n"
                elif format_type == "slack":
                    separator = f"\n\n"

                test_content = current_batch + separator
                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    < max_bytes
                ):
                    current_batch = test_content

        return current_batch, current_batch_has_content, batches

    # définit la fonction de traitement des nouvelles actualités
    def process_new_titles_section(current_batch, current_batch_has_content, batches, add_separator=True):
        """traite les nouvelles actualités"""
        if not show_new_section or not report_data["new_titles"]:
            return current_batch, current_batch_has_content, batches

        # décide d'ajouter ou non un séparateur en tête selon add_separator
        new_header = ""
        if add_separator and current_batch_has_content:
            # un séparateur est nécessaire
            if format_type in ("wework", "bark"):
                new_header = f"\n\n\n\n🆕 **Nouvelles tendances de cette exécution** (total : {report_data['total_new_count']} entrées)\n\n"
            elif format_type == "telegram":
                new_header = (
                    f"\n\n🆕 Nouvelles tendances de cette exécution (total : {report_data['total_new_count']} entrées)\n\n"
                )
            elif format_type == "ntfy":
                new_header = f"\n\n🆕 **Nouvelles tendances de cette exécution** (total : {report_data['total_new_count']} entrées)\n\n"
            elif format_type == "feishu":
                new_header = f"\n{feishu_separator}\n\n🆕 **Nouvelles tendances de cette exécution** (total : {report_data['total_new_count']} entrées)\n\n"
            elif format_type == "dingtalk":
                new_header = f"\n---\n\n🆕 **Nouvelles tendances de cette exécution** (total : {report_data['total_new_count']} entrées)\n\n"
            elif format_type == "slack":
                new_header = f"\n\n🆕 *Nouvelles tendances de cette exécution* (total : {report_data['total_new_count']} entrées)\n\n"
        else:
            # pas de séparateur nécessaire (première zone)
            if format_type in ("wework", "bark"):
                new_header = f"🆕 **Nouvelles tendances de cette exécution** (total : {report_data['total_new_count']} entrées)\n\n"
            elif format_type == "telegram":
                new_header = f"🆕 Nouvelles tendances de cette exécution (total : {report_data['total_new_count']} entrées)\n\n"
            elif format_type == "ntfy":
                new_header = f"🆕 **Nouvelles tendances de cette exécution** (total : {report_data['total_new_count']} entrées)\n\n"
            elif format_type == "feishu":
                new_header = f"🆕 **Nouvelles tendances de cette exécution** (total : {report_data['total_new_count']} entrées)\n\n"
            elif format_type == "dingtalk":
                new_header = f"🆕 **Nouvelles tendances de cette exécution** (total : {report_data['total_new_count']} entrées)\n\n"
            elif format_type == "slack":
                new_header = f"🆕 *Nouvelles tendances de cette exécution* (total : {report_data['total_new_count']} entrées)\n\n"

        test_content = current_batch + new_header
        if (
            len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
            >= max_bytes
        ):
            if current_batch_has_content:
                _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
            current_batch = _safe_new_batch(
                base_header + new_header, base_footer, max_bytes, base_header, batches
            )
            current_batch_has_content = True
        else:
            current_batch = test_content
            current_batch_has_content = True

        # traite les sources de nouvelles actualités une par une
        for source_data in report_data["new_titles"]:
            source_header = ""
            if format_type in ("wework", "bark"):
                source_header = f"**{source_data['source_name']}** ({len(source_data['titles'])} entrées):\n\n"
            elif format_type == "telegram":
                source_header = f"{source_data['source_name']} ({len(source_data['titles'])} entrées):\n\n"
            elif format_type == "ntfy":
                source_header = f"**{source_data['source_name']}** ({len(source_data['titles'])} entrées):\n\n"
            elif format_type == "feishu":
                source_header = f"**{source_data['source_name']}** ({len(source_data['titles'])} entrées):\n\n"
            elif format_type == "dingtalk":
                source_header = f"**{source_data['source_name']}** ({len(source_data['titles'])} entrées):\n\n"
            elif format_type == "slack":
                source_header = f"*{source_data['source_name']}* ({len(source_data['titles'])} entrées):\n\n"

            # construit la première nouvelle actualité
            first_news_line = ""
            if source_data["titles"]:
                first_title_data = source_data["titles"][0]
                title_data_copy = first_title_data.copy()
                title_data_copy["is_new"] = False

                if format_type in ("wework", "bark"):
                    formatted_title = format_title_for_platform(
                        "wework", title_data_copy, show_source=False
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", title_data_copy, show_source=False
                    )
                elif format_type == "feishu":
                    formatted_title = format_title_for_platform(
                        "feishu", title_data_copy, show_source=False
                    )
                elif format_type == "dingtalk":
                    formatted_title = format_title_for_platform(
                        "dingtalk", title_data_copy, show_source=False
                    )
                elif format_type == "slack":
                    formatted_title = format_title_for_platform(
                        "slack", title_data_copy, show_source=False
                    )
                else:
                    formatted_title = f"{title_data_copy['title']}"

                first_news_line = f"  1. {formatted_title}\n"

            # vérification d'atomicité : titre de la source + première actualité
            source_with_first_news = source_header + first_news_line
            test_content = current_batch + source_with_first_news

            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                >= max_bytes
            ):
                if current_batch_has_content:
                    _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
                current_batch = _safe_new_batch(
                    base_header + new_header + source_with_first_news,
                    base_footer, max_bytes, base_header, batches
                )
                current_batch_has_content = True
                start_index = 1
            else:
                current_batch = test_content
                current_batch_has_content = True
                start_index = 1

            # traite les nouvelles actualités restantes
            for j in range(start_index, len(source_data["titles"])):
                title_data = source_data["titles"][j]
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False

                if format_type == "wework":
                    formatted_title = format_title_for_platform(
                        "wework", title_data_copy, show_source=False
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", title_data_copy, show_source=False
                    )
                elif format_type == "feishu":
                    formatted_title = format_title_for_platform(
                        "feishu", title_data_copy, show_source=False
                    )
                elif format_type == "dingtalk":
                    formatted_title = format_title_for_platform(
                        "dingtalk", title_data_copy, show_source=False
                    )
                elif format_type == "slack":
                    formatted_title = format_title_for_platform(
                        "slack", title_data_copy, show_source=False
                    )
                else:
                    formatted_title = f"{title_data_copy['title']}"

                news_line = f"  {j + 1}. {formatted_title}\n"

                test_content = current_batch + news_line
                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    >= max_bytes
                ):
                    if current_batch_has_content:
                        _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
                    current_batch = _safe_new_batch(
                        base_header + new_header + source_header + news_line,
                        base_footer, max_bytes, base_header, batches
                    )
                    current_batch_has_content = True
                else:
                    current_batch = test_content
                    current_batch_has_content = True

            current_batch += "\n"

        return current_batch, current_batch_has_content, batches

    # définit la fonction de traitement de l'Analyse IA
    def process_ai_section(current_batch, current_batch_has_content, batches, add_separator=True):
        """traite le contenu de l'Analyse IA"""
        nonlocal ai_content
        if not ai_content:
            return current_batch, current_batch_has_content, batches

        # décide d'ajouter ou non un séparateur en tête selon add_separator
        ai_separator = ""
        if add_separator and current_batch_has_content:
            # un séparateur est nécessaire
            if format_type == "feishu":
                ai_separator = f"\n{feishu_separator}\n\n"
            elif format_type == "dingtalk":
                ai_separator = "\n---\n\n"
            elif format_type in ("wework", "bark"):
                ai_separator = "\n\n\n\n"
            elif format_type in ("telegram", "ntfy", "slack"):
                ai_separator = "\n\n"
        # si aucun séparateur n'est nécessaire, ai_separator reste une chaîne vide

        # tente d'ajouter le contenu IA au lot courant
        test_content = current_batch + ai_separator + ai_content
        if (
            len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
            < max_bytes
        ):
            current_batch = test_content
            current_batch_has_content = True
        else:
            if current_batch_has_content:
                _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)

            # le contenu IA peut être très long, on le découpe en plusieurs lots ligne par ligne
            footer_size = len(base_footer.encode("utf-8"))
            header_size = len(base_header.encode("utf-8"))
            available = max_bytes - footer_size - header_size

            ai_lines = ai_content.split("\n")
            current_batch = base_header
            current_batch_has_content = False

            for line in ai_lines:
                test_line = line + "\n" if not line.endswith("\n") else line
                test_content = current_batch + test_line
                if len(test_content.encode("utf-8")) + footer_size >= max_bytes and current_batch_has_content:
                    _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
                    current_batch = base_header + test_line
                else:
                    current_batch = test_content
                current_batch_has_content = True

        return current_batch, current_batch_has_content, batches

    # définit la fonction de traitement de la Zone d'affichage autonome
    def process_standalone_section_wrapper(current_batch, current_batch_has_content, batches, add_separator=True):
        """traite la Zone d'affichage autonome"""
        if not standalone_data:
            return current_batch, current_batch_has_content, batches
        return _process_standalone_section(
            standalone_data, format_type, feishu_separator, base_header, base_footer,
            max_bytes, current_batch, current_batch_has_content, batches, timezone,
            rank_threshold, add_separator
        )

    # définit la fonction de traitement des statistiques RSS
    def process_rss_stats_wrapper(current_batch, current_batch_has_content, batches, add_separator=True):
        """traite les statistiques RSS"""
        if not rss_items:
            return current_batch, current_batch_has_content, batches
        return _process_rss_stats_section(
            rss_items, format_type, feishu_separator, base_header, base_footer,
            max_bytes, current_batch, current_batch_has_content, batches, timezone,
            add_separator
        )

    # définit la fonction de traitement des nouveautés RSS
    def process_rss_new_wrapper(current_batch, current_batch_has_content, batches, add_separator=True):
        """traite les nouveautés RSS"""
        if not rss_new_items:
            return current_batch, current_batch_has_content, batches
        return _process_rss_new_titles_section(
            rss_new_items, format_type, feishu_separator, base_header, base_footer,
            max_bytes, current_batch, current_batch_has_content, batches, timezone,
            add_separator
        )

    # traite chaque zone dans l'ordre de region_order
    # mémorise si une zone a déjà produit du contenu (sert à décider d'ajouter un séparateur)
    has_region_content = False

    for region in region_order:
        # mémorise l'état avant traitement, pour déterminer si cette zone produit du contenu
        batch_before = current_batch
        has_content_before = current_batch_has_content
        batches_len_before = len(batches)

        # décide s'il faut ajouter un séparateur (la première zone avec du contenu n'en a pas besoin)
        add_separator = has_region_content

        if region == "hotlist":
            # traite les statistiques des tendances
            current_batch, current_batch_has_content, batches = process_stats_section(
                current_batch, current_batch_has_content, batches, add_separator
            )
        elif region == "rss":
            # traite les statistiques RSS
            current_batch, current_batch_has_content, batches = process_rss_stats_wrapper(
                current_batch, current_batch_has_content, batches, add_separator
            )
        elif region == "new_items":
            # traite les nouveautés des tendances
            current_batch, current_batch_has_content, batches = process_new_titles_section(
                current_batch, current_batch_has_content, batches, add_separator
            )
            # traite les nouveautés RSS (à la suite de new_items, hérite de la logique add_separator)
            # si les nouveautés des tendances ont produit du contenu, les nouveautés RSS ont besoin d'un séparateur
            new_batch_changed = (
                current_batch != batch_before or
                current_batch_has_content != has_content_before or
                len(batches) != batches_len_before
            )
            rss_new_separator = new_batch_changed or has_region_content
            current_batch, current_batch_has_content, batches = process_rss_new_wrapper(
                current_batch, current_batch_has_content, batches, rss_new_separator
            )
        elif region == "standalone":
            # traite la Zone d'affichage autonome
            current_batch, current_batch_has_content, batches = process_standalone_section_wrapper(
                current_batch, current_batch_has_content, batches, add_separator
            )
        elif region == "ai_analysis":
            # traite l'Analyse IA
            current_batch, current_batch_has_content, batches = process_ai_section(
                current_batch, current_batch_has_content, batches, add_separator
            )

        # vérifie si cette zone a produit du contenu
        region_produced_content = (
            current_batch != batch_before or
            current_batch_has_content != has_content_before or
            len(batches) != batches_len_before
        )
        if region_produced_content:
            has_region_content = True

    if report_data["failed_ids"]:
        failed_header = ""
        if format_type == "wework":
            failed_header = f"\n\n\n\n⚠️ **Plateformes en échec de collecte :**\n\n"
        elif format_type == "telegram":
            failed_header = f"\n\n⚠️ Plateformes en échec de collecte :\n\n"
        elif format_type == "ntfy":
            failed_header = f"\n\n⚠️ **Plateformes en échec de collecte :**\n\n"
        elif format_type == "feishu":
            failed_header = f"\n{feishu_separator}\n\n⚠️ **Plateformes en échec de collecte :**\n\n"
        elif format_type == "dingtalk":
            failed_header = f"\n---\n\n⚠️ **Plateformes en échec de collecte :**\n\n"

        test_content = current_batch + failed_header
        if (
            len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
            >= max_bytes
        ):
            if current_batch_has_content:
                _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
            current_batch = _safe_new_batch(
                base_header + failed_header, base_footer, max_bytes, base_header, batches
            )
            current_batch_has_content = True
        else:
            current_batch = test_content
            current_batch_has_content = True

        for i, id_value in enumerate(report_data["failed_ids"], 1):
            if format_type == "feishu":
                failed_line = f"  • <font color='red'>{id_value}</font>\n"
            elif format_type == "dingtalk":
                failed_line = f"  • **{id_value}**\n"
            else:
                failed_line = f"  • {id_value}\n"

            test_content = current_batch + failed_line
            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                >= max_bytes
            ):
                if current_batch_has_content:
                    _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
                current_batch = _safe_new_batch(
                    base_header + failed_header + failed_line,
                    base_footer, max_bytes, base_header, batches
                )
                current_batch_has_content = True
            else:
                current_batch = test_content
                current_batch_has_content = True

    # finalise le dernier lot
    if current_batch_has_content:
        _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)

    return batches


def _process_rss_stats_section(
    rss_stats: list,
    format_type: str,
    feishu_separator: str,
    base_header: str,
    base_footer: str,
    max_bytes: int,
    current_batch: str,
    current_batch_has_content: bool,
    batches: List[str],
    timezone: str = DEFAULT_TIMEZONE,
    add_separator: bool = True,
) -> tuple:
    """Traite le bloc des statistiques RSS (regroupées par mot-clé, format cohérent avec les statistiques des tendances)

    Args:
        rss_stats: liste des statistiques RSS par mot-clé, format cohérent avec les stats des tendances :
            [{"word": "AI", "count": 5, "titles": [...]}]
        format_type: type de format
        feishu_separator: séparateur Feishu
        base_header: en-tête de base
        base_footer: pied de page de base
        max_bytes: nombre d'octets maximal
        current_batch: contenu du lot courant
        current_batch_has_content: indique si le lot courant contient du contenu
        batches: liste des lots déjà finalisés
        timezone: nom du fuseau horaire
        add_separator: indique s'il faut ajouter un séparateur avant le bloc (False pour la première zone)

    Returns:
        tuple (current_batch, current_batch_has_content, batches)
    """
    if not rss_stats:
        return current_batch, current_batch_has_content, batches

    # calcule le nombre total d'entrées
    total_items = sum(stat["count"] for stat in rss_stats)
    total_keywords = len(rss_stats)

    # titre du bloc des statistiques RSS (décide d'ajouter un séparateur en tête selon add_separator)
    rss_header = ""
    if add_separator and current_batch_has_content:
        # un séparateur est nécessaire
        if format_type == "feishu":
            rss_header = f"\n{feishu_separator}\n\n📰 **Statistiques des abonnements RSS** (total : {total_items} entrées)\n\n"
        elif format_type == "dingtalk":
            rss_header = f"\n---\n\n📰 **Statistiques des abonnements RSS** (total : {total_items} entrées)\n\n"
        elif format_type in ("wework", "bark"):
            rss_header = f"\n\n\n\n📰 **Statistiques des abonnements RSS** (total : {total_items} entrées)\n\n"
        elif format_type == "telegram":
            rss_header = f"\n\n📰 Statistiques des abonnements RSS (total : {total_items} entrées)\n\n"
        elif format_type == "slack":
            rss_header = f"\n\n📰 *Statistiques des abonnements RSS* (total : {total_items} entrées)\n\n"
        else:
            rss_header = f"\n\n📰 **Statistiques des abonnements RSS** (total : {total_items} entrées)\n\n"
    else:
        # pas de séparateur nécessaire (première zone)
        if format_type == "feishu":
            rss_header = f"📰 **Statistiques des abonnements RSS** (total : {total_items} entrées)\n\n"
        elif format_type == "dingtalk":
            rss_header = f"📰 **Statistiques des abonnements RSS** (total : {total_items} entrées)\n\n"
        elif format_type == "telegram":
            rss_header = f"📰 Statistiques des abonnements RSS (total : {total_items} entrées)\n\n"
        elif format_type == "slack":
            rss_header = f"📰 *Statistiques des abonnements RSS* (total : {total_items} entrées)\n\n"
        else:
            rss_header = f"📰 **Statistiques des abonnements RSS** (total : {total_items} entrées)\n\n"

    # ajoute le titre RSS
    test_content = current_batch + rss_header
    if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) < max_bytes:
        current_batch = test_content
        current_batch_has_content = True
    else:
        if current_batch_has_content:
            _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
        current_batch = _safe_new_batch(
            base_header + rss_header, base_footer, max_bytes, base_header, batches
        )
        current_batch_has_content = True

    # traite les groupes de mots-clés un par un (cohérent avec les tendances)
    for i, stat in enumerate(rss_stats):
        word = stat["word"]
        count = stat["count"]
        sequence_display = f"[{i + 1}/{total_keywords}]"

        # construit le titre du mot-clé (format cohérent avec les tendances)
        word_header = ""
        if format_type in ("wework", "bark"):
            if count >= 10:
                word_header = f"🔥 {sequence_display} **{word}** : **{count}** entrées\n\n"
            elif count >= 5:
                word_header = f"📈 {sequence_display} **{word}** : **{count}** entrées\n\n"
            else:
                word_header = f"📌 {sequence_display} **{word}** : {count} entrées\n\n"
        elif format_type == "telegram":
            if count >= 10:
                word_header = f"🔥 {sequence_display} {word} : {count} entrées\n\n"
            elif count >= 5:
                word_header = f"📈 {sequence_display} {word} : {count} entrées\n\n"
            else:
                word_header = f"📌 {sequence_display} {word} : {count} entrées\n\n"
        elif format_type == "ntfy":
            if count >= 10:
                word_header = f"🔥 {sequence_display} **{word}** : **{count}** entrées\n\n"
            elif count >= 5:
                word_header = f"📈 {sequence_display} **{word}** : **{count}** entrées\n\n"
            else:
                word_header = f"📌 {sequence_display} **{word}** : {count} entrées\n\n"
        elif format_type == "feishu":
            if count >= 10:
                word_header = f"🔥 <font color='grey'>{sequence_display}</font> **{word}** : <font color='red'>{count}</font> entrées\n\n"
            elif count >= 5:
                word_header = f"📈 <font color='grey'>{sequence_display}</font> **{word}** : <font color='orange'>{count}</font> entrées\n\n"
            else:
                word_header = f"📌 <font color='grey'>{sequence_display}</font> **{word}** : {count} entrées\n\n"
        elif format_type == "dingtalk":
            if count >= 10:
                word_header = f"🔥 {sequence_display} **{word}** : **{count}** entrées\n\n"
            elif count >= 5:
                word_header = f"📈 {sequence_display} **{word}** : **{count}** entrées\n\n"
            else:
                word_header = f"📌 {sequence_display} **{word}** : {count} entrées\n\n"
        elif format_type == "slack":
            if count >= 10:
                word_header = f"🔥 {sequence_display} *{word}* : *{count}* entrées\n\n"
            elif count >= 5:
                word_header = f"📈 {sequence_display} *{word}* : *{count}* entrées\n\n"
            else:
                word_header = f"📌 {sequence_display} *{word}* : {count} entrées\n\n"

        # construit la première actualité (utilise format_title_for_platform)
        first_news_line = ""
        if stat["titles"]:
            first_title_data = stat["titles"][0]
            if format_type in ("wework", "bark"):
                formatted_title = format_title_for_platform("wework", first_title_data, show_source=True)
            elif format_type == "telegram":
                formatted_title = format_title_for_platform("telegram", first_title_data, show_source=True)
            elif format_type == "ntfy":
                formatted_title = format_title_for_platform("ntfy", first_title_data, show_source=True)
            elif format_type == "feishu":
                formatted_title = format_title_for_platform("feishu", first_title_data, show_source=True)
            elif format_type == "dingtalk":
                formatted_title = format_title_for_platform("dingtalk", first_title_data, show_source=True)
            elif format_type == "slack":
                formatted_title = format_title_for_platform("slack", first_title_data, show_source=True)
            else:
                formatted_title = f"{first_title_data['title']}"

            first_news_line = f"  1. {formatted_title}\n"
            if len(stat["titles"]) > 1:
                first_news_line += "\n"

        # vérification d'atomicité : le titre du mot-clé et la première actualité doivent être traités ensemble
        word_with_first_news = word_header + first_news_line
        test_content = current_batch + word_with_first_news

        if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) >= max_bytes:
            if current_batch_has_content:
                _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
            current_batch = _safe_new_batch(
                base_header + rss_header + word_with_first_news,
                base_footer, max_bytes, base_header, batches
            )
            current_batch_has_content = True
            start_index = 1
        else:
            current_batch = test_content
            current_batch_has_content = True
            start_index = 1

        # traite les actualités restantes
        for j in range(start_index, len(stat["titles"])):
            title_data = stat["titles"][j]
            if format_type in ("wework", "bark"):
                formatted_title = format_title_for_platform("wework", title_data, show_source=True)
            elif format_type == "telegram":
                formatted_title = format_title_for_platform("telegram", title_data, show_source=True)
            elif format_type == "ntfy":
                formatted_title = format_title_for_platform("ntfy", title_data, show_source=True)
            elif format_type == "feishu":
                formatted_title = format_title_for_platform("feishu", title_data, show_source=True)
            elif format_type == "dingtalk":
                formatted_title = format_title_for_platform("dingtalk", title_data, show_source=True)
            elif format_type == "slack":
                formatted_title = format_title_for_platform("slack", title_data, show_source=True)
            else:
                formatted_title = f"{title_data['title']}"

            news_line = f"  {j + 1}. {formatted_title}\n"
            if j < len(stat["titles"]) - 1:
                news_line += "\n"

            test_content = current_batch + news_line
            if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) >= max_bytes:
                if current_batch_has_content:
                    _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
                current_batch = _safe_new_batch(
                    base_header + rss_header + word_header + news_line,
                    base_footer, max_bytes, base_header, batches
                )
                current_batch_has_content = True
            else:
                current_batch = test_content
                current_batch_has_content = True

        # séparateur entre les mots-clés
        if i < len(rss_stats) - 1:
            separator = ""
            if format_type in ("wework", "bark"):
                separator = "\n\n\n\n"
            elif format_type == "telegram":
                separator = "\n\n"
            elif format_type == "ntfy":
                separator = "\n\n"
            elif format_type == "feishu":
                separator = f"\n{feishu_separator}\n\n"
            elif format_type == "dingtalk":
                separator = "\n---\n\n"
            elif format_type == "slack":
                separator = "\n\n"

            test_content = current_batch + separator
            if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) < max_bytes:
                current_batch = test_content

    return current_batch, current_batch_has_content, batches


def _process_rss_new_titles_section(
    rss_new_stats: list,
    format_type: str,
    feishu_separator: str,
    base_header: str,
    base_footer: str,
    max_bytes: int,
    current_batch: str,
    current_batch_has_content: bool,
    batches: List[str],
    timezone: str = DEFAULT_TIMEZONE,
    add_separator: bool = True,
) -> tuple:
    """Traite le bloc des nouveautés RSS (regroupées par source, format cohérent avec les nouveautés des tendances)

    Args:
        rss_new_stats: liste des statistiques des nouveautés RSS par mot-clé, format cohérent avec les stats des tendances :
            [{"word": "AI", "count": 5, "titles": [...]}]
        format_type: type de format
        feishu_separator: séparateur Feishu
        base_header: en-tête de base
        base_footer: pied de page de base
        max_bytes: nombre d'octets maximal
        current_batch: contenu du lot courant
        current_batch_has_content: indique si le lot courant contient du contenu
        batches: liste des lots déjà finalisés
        timezone: nom du fuseau horaire
        add_separator: indique s'il faut ajouter un séparateur avant le bloc (False pour la première zone)

    Returns:
        tuple (current_batch, current_batch_has_content, batches)
    """
    if not rss_new_stats:
        return current_batch, current_batch_has_content, batches

    # extrait toutes les entrées depuis le regroupement par mot-clé, puis les regroupe par source
    source_map = {}
    for stat in rss_new_stats:
        for title_data in stat.get("titles", []):
            source_name = title_data.get("source_name", "Source inconnue")
            if source_name not in source_map:
                source_map[source_name] = []
            source_map[source_name].append(title_data)

    if not source_map:
        return current_batch, current_batch_has_content, batches

    # calcule le nombre total d'entrées
    total_items = sum(len(titles) for titles in source_map.values())

    # titre du bloc des nouveautés RSS (décide d'ajouter un séparateur en tête selon add_separator)
    new_header = ""
    if add_separator and current_batch_has_content:
        # un séparateur est nécessaire
        if format_type in ("wework", "bark"):
            new_header = f"\n\n\n\n🆕 **Nouveautés RSS de cette exécution** (total : {total_items} entrées)\n\n"
        elif format_type == "telegram":
            new_header = f"\n\n🆕 Nouveautés RSS de cette exécution (total : {total_items} entrées)\n\n"
        elif format_type == "ntfy":
            new_header = f"\n\n🆕 **Nouveautés RSS de cette exécution** (total : {total_items} entrées)\n\n"
        elif format_type == "feishu":
            new_header = f"\n{feishu_separator}\n\n🆕 **Nouveautés RSS de cette exécution** (total : {total_items} entrées)\n\n"
        elif format_type == "dingtalk":
            new_header = f"\n---\n\n🆕 **Nouveautés RSS de cette exécution** (total : {total_items} entrées)\n\n"
        elif format_type == "slack":
            new_header = f"\n\n🆕 *Nouveautés RSS de cette exécution* (total : {total_items} entrées)\n\n"
    else:
        # pas de séparateur nécessaire (première zone)
        if format_type in ("wework", "bark"):
            new_header = f"🆕 **Nouveautés RSS de cette exécution** (total : {total_items} entrées)\n\n"
        elif format_type == "telegram":
            new_header = f"🆕 Nouveautés RSS de cette exécution (total : {total_items} entrées)\n\n"
        elif format_type == "ntfy":
            new_header = f"🆕 **Nouveautés RSS de cette exécution** (total : {total_items} entrées)\n\n"
        elif format_type == "feishu":
            new_header = f"🆕 **Nouveautés RSS de cette exécution** (total : {total_items} entrées)\n\n"
        elif format_type == "dingtalk":
            new_header = f"🆕 **Nouveautés RSS de cette exécution** (total : {total_items} entrées)\n\n"
        elif format_type == "slack":
            new_header = f"🆕 *Nouveautés RSS de cette exécution* (total : {total_items} entrées)\n\n"

    # ajoute le titre des nouveautés RSS
    test_content = current_batch + new_header
    if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) >= max_bytes:
        if current_batch_has_content:
            _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
        current_batch = _safe_new_batch(
            base_header + new_header, base_footer, max_bytes, base_header, batches
        )
        current_batch_has_content = True
    else:
        current_batch = test_content
        current_batch_has_content = True

    # affichage regroupé par source (format cohérent avec les nouveautés des tendances)
    source_list = list(source_map.items())
    for i, (source_name, titles) in enumerate(source_list):
        count = len(titles)

        # construit le titre de la source (format cohérent avec les nouveautés des tendances)
        source_header = ""
        if format_type in ("wework", "bark"):
            source_header = f"**{source_name}** ({count} entrées):\n\n"
        elif format_type == "telegram":
            source_header = f"{source_name} ({count} entrées):\n\n"
        elif format_type == "ntfy":
            source_header = f"**{source_name}** ({count} entrées):\n\n"
        elif format_type == "feishu":
            source_header = f"**{source_name}** ({count} entrées):\n\n"
        elif format_type == "dingtalk":
            source_header = f"**{source_name}** ({count} entrées):\n\n"
        elif format_type == "slack":
            source_header = f"*{source_name}* ({count} entrées):\n\n"

        # construit la première actualité (sans afficher la source, sans l'emoji new)
        first_news_line = ""
        if titles:
            first_title_data = titles[0].copy()
            first_title_data["is_new"] = False
            if format_type in ("wework", "bark"):
                formatted_title = format_title_for_platform("wework", first_title_data, show_source=False)
            elif format_type == "telegram":
                formatted_title = format_title_for_platform("telegram", first_title_data, show_source=False)
            elif format_type == "ntfy":
                formatted_title = format_title_for_platform("ntfy", first_title_data, show_source=False)
            elif format_type == "feishu":
                formatted_title = format_title_for_platform("feishu", first_title_data, show_source=False)
            elif format_type == "dingtalk":
                formatted_title = format_title_for_platform("dingtalk", first_title_data, show_source=False)
            elif format_type == "slack":
                formatted_title = format_title_for_platform("slack", first_title_data, show_source=False)
            else:
                formatted_title = f"{first_title_data['title']}"

            first_news_line = f"  1. {formatted_title}\n"

        # vérification d'atomicité : le titre de la source et la première actualité doivent être traités ensemble
        source_with_first_news = source_header + first_news_line
        test_content = current_batch + source_with_first_news

        if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) >= max_bytes:
            if current_batch_has_content:
                _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
            current_batch = _safe_new_batch(
                base_header + new_header + source_with_first_news,
                base_footer, max_bytes, base_header, batches
            )
            current_batch_has_content = True
            start_index = 1
        else:
            current_batch = test_content
            current_batch_has_content = True
            start_index = 1

        # traite les actualités restantes (sans l'emoji new)
        for j in range(start_index, len(titles)):
            title_data = titles[j].copy()
            title_data["is_new"] = False
            if format_type in ("wework", "bark"):
                formatted_title = format_title_for_platform("wework", title_data, show_source=False)
            elif format_type == "telegram":
                formatted_title = format_title_for_platform("telegram", title_data, show_source=False)
            elif format_type == "ntfy":
                formatted_title = format_title_for_platform("ntfy", title_data, show_source=False)
            elif format_type == "feishu":
                formatted_title = format_title_for_platform("feishu", title_data, show_source=False)
            elif format_type == "dingtalk":
                formatted_title = format_title_for_platform("dingtalk", title_data, show_source=False)
            elif format_type == "slack":
                formatted_title = format_title_for_platform("slack", title_data, show_source=False)
            else:
                formatted_title = f"{title_data['title']}"

            news_line = f"  {j + 1}. {formatted_title}\n"

            test_content = current_batch + news_line
            if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) >= max_bytes:
                if current_batch_has_content:
                    _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
                current_batch = _safe_new_batch(
                    base_header + new_header + source_header + news_line,
                    base_footer, max_bytes, base_header, batches
                )
                current_batch_has_content = True
            else:
                current_batch = test_content
                current_batch_has_content = True

        # ajoute une ligne vide entre les sources (format cohérent avec les nouveautés des tendances)
        current_batch += "\n"

    return current_batch, current_batch_has_content, batches


def _format_rss_item_line(
    item: Dict,
    index: int,
    format_type: str,
    timezone: str = DEFAULT_TIMEZONE,
) -> str:
    """Formate une seule entrée RSS

    Args:
        item: dictionnaire de l'entrée RSS
        index: numéro d'ordre
        format_type: type de format
        timezone: nom du fuseau horaire

    Returns:
        chaîne de la ligne d'entrée formatée
    """
    title = item.get("title", "")
    url = item.get("url", "")
    published_at = item.get("published_at", "")

    # utilise un format d'heure lisible
    if published_at:
        friendly_time = format_iso_time_friendly(published_at, timezone, include_date=True)
    else:
        friendly_time = ""

    # construit la ligne d'entrée
    if format_type == "feishu":
        if url:
            item_line = f"  {index}. [{title}]({url})"
        else:
            item_line = f"  {index}. {title}"
        if friendly_time:
            item_line += f" <font color='grey'>- {friendly_time}</font>"
    elif format_type == "telegram":
        if url:
            item_line = f"  {index}. {title} ({url})"
        else:
            item_line = f"  {index}. {title}"
        if friendly_time:
            item_line += f" - {friendly_time}"
    else:
        if url:
            item_line = f"  {index}. [{title}]({url})"
        else:
            item_line = f"  {index}. {title}"
        if friendly_time:
            item_line += f" `{friendly_time}`"

    item_line += "\n"
    return item_line


def _process_standalone_section(
    standalone_data: Dict,
    format_type: str,
    feishu_separator: str,
    base_header: str,
    base_footer: str,
    max_bytes: int,
    current_batch: str,
    current_batch_has_content: bool,
    batches: List[str],
    timezone: str = DEFAULT_TIMEZONE,
    rank_threshold: int = 10,
    add_separator: bool = True,
) -> tuple:
    """Traite le bloc de la Zone d'affichage autonome

    La Zone d'affichage autonome affiche le contenu complet des tendances d'une plateforme donnée ou d'une source RSS, sans être affectée par le filtrage par mots-clés.
    Les tendances sont triées par classement d'origine, les entrées RSS par date de publication.

    Args:
        standalone_data: données d'affichage autonome, format :
            {
                "platforms": [{"id": "zhihu", "name": "Tendances Zhihu", "items": [...]}],
                "rss_feeds": [{"id": "hacker-news", "name": "Hacker News", "items": [...]}]
            }
        format_type: type de format
        feishu_separator: séparateur Feishu
        base_header: en-tête de base
        base_footer: pied de page de base
        max_bytes: nombre d'octets maximal
        current_batch: contenu du lot courant
        current_batch_has_content: indique si le lot courant contient du contenu
        batches: liste des lots déjà finalisés
        timezone: nom du fuseau horaire
        rank_threshold: seuil de mise en évidence du classement
        add_separator: indique s'il faut ajouter un séparateur avant le bloc (False pour la première zone)

    Returns:
        tuple (current_batch, current_batch_has_content, batches)
    """
    if not standalone_data:
        return current_batch, current_batch_has_content, batches

    platforms = standalone_data.get("platforms", [])
    rss_feeds = standalone_data.get("rss_feeds", [])

    if not platforms and not rss_feeds:
        return current_batch, current_batch_has_content, batches

    # calcule le nombre total d'entrées
    total_platform_items = sum(len(p.get("items", [])) for p in platforms)
    total_rss_items = sum(len(f.get("items", [])) for f in rss_feeds)
    total_items = total_platform_items + total_rss_items

    # titre de la Zone d'affichage autonome (décide d'ajouter un séparateur en tête selon add_separator)
    section_header = ""
    if add_separator and current_batch_has_content:
        # un séparateur est nécessaire
        if format_type == "feishu":
            section_header = f"\n{feishu_separator}\n\n📋 **Zone d'affichage autonome** (total : {total_items} entrées)\n\n"
        elif format_type == "dingtalk":
            section_header = f"\n---\n\n📋 **Zone d'affichage autonome** (total : {total_items} entrées)\n\n"
        elif format_type in ("wework", "bark"):
            section_header = f"\n\n\n\n📋 **Zone d'affichage autonome** (total : {total_items} entrées)\n\n"
        elif format_type == "telegram":
            section_header = f"\n\n📋 Zone d'affichage autonome (total : {total_items} entrées)\n\n"
        elif format_type == "slack":
            section_header = f"\n\n📋 *Zone d'affichage autonome* (total : {total_items} entrées)\n\n"
        else:
            section_header = f"\n\n📋 **Zone d'affichage autonome** (total : {total_items} entrées)\n\n"
    else:
        # pas de séparateur nécessaire (première zone)
        if format_type == "feishu":
            section_header = f"📋 **Zone d'affichage autonome** (total : {total_items} entrées)\n\n"
        elif format_type == "dingtalk":
            section_header = f"📋 **Zone d'affichage autonome** (total : {total_items} entrées)\n\n"
        elif format_type == "telegram":
            section_header = f"📋 Zone d'affichage autonome (total : {total_items} entrées)\n\n"
        elif format_type == "slack":
            section_header = f"📋 *Zone d'affichage autonome* (total : {total_items} entrées)\n\n"
        else:
            section_header = f"📋 **Zone d'affichage autonome** (total : {total_items} entrées)\n\n"

    # ajoute le titre du bloc
    test_content = current_batch + section_header
    if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) < max_bytes:
        current_batch = test_content
        current_batch_has_content = True
    else:
        if current_batch_has_content:
            _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
        current_batch = _safe_new_batch(
            base_header + section_header, base_footer, max_bytes, base_header, batches
        )
        current_batch_has_content = True

    # traite les plateformes de tendances
    for platform in platforms:
        platform_name = platform.get("name", platform.get("id", ""))
        items = platform.get("items", [])
        if not items:
            continue

        # titre de la plateforme
        platform_header = ""
        if format_type in ("wework", "bark"):
            platform_header = f"**{platform_name}** ({len(items)} entrées):\n\n"
        elif format_type == "telegram":
            platform_header = f"{platform_name} ({len(items)} entrées):\n\n"
        elif format_type == "ntfy":
            platform_header = f"**{platform_name}** ({len(items)} entrées):\n\n"
        elif format_type == "feishu":
            platform_header = f"**{platform_name}** ({len(items)} entrées):\n\n"
        elif format_type == "dingtalk":
            platform_header = f"**{platform_name}** ({len(items)} entrées):\n\n"
        elif format_type == "slack":
            platform_header = f"*{platform_name}* ({len(items)} entrées):\n\n"

        # construit la première actualité
        first_item_line = ""
        if items:
            first_item_line = _format_standalone_platform_item(items[0], 1, format_type, rank_threshold)

        # vérification d'atomicité
        platform_with_first = platform_header + first_item_line
        test_content = current_batch + platform_with_first

        if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) >= max_bytes:
            if current_batch_has_content:
                _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
            current_batch = _safe_new_batch(
                base_header + section_header + platform_with_first,
                base_footer, max_bytes, base_header, batches
            )
            current_batch_has_content = True
            start_index = 1
        else:
            current_batch = test_content
            current_batch_has_content = True
            start_index = 1

        # traite les entrées restantes
        for j in range(start_index, len(items)):
            item_line = _format_standalone_platform_item(items[j], j + 1, format_type, rank_threshold)

            test_content = current_batch + item_line
            if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) >= max_bytes:
                if current_batch_has_content:
                    _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
                current_batch = _safe_new_batch(
                    base_header + section_header + platform_header + item_line,
                    base_footer, max_bytes, base_header, batches
                )
                current_batch_has_content = True
            else:
                current_batch = test_content
                current_batch_has_content = True

        current_batch += "\n"

    # traite les sources RSS
    for feed in rss_feeds:
        feed_name = feed.get("name", feed.get("id", ""))
        items = feed.get("items", [])
        if not items:
            continue

        # titre de la source RSS
        feed_header = ""
        if format_type in ("wework", "bark"):
            feed_header = f"**{feed_name}** ({len(items)} entrées):\n\n"
        elif format_type == "telegram":
            feed_header = f"{feed_name} ({len(items)} entrées):\n\n"
        elif format_type == "ntfy":
            feed_header = f"**{feed_name}** ({len(items)} entrées):\n\n"
        elif format_type == "feishu":
            feed_header = f"**{feed_name}** ({len(items)} entrées):\n\n"
        elif format_type == "dingtalk":
            feed_header = f"**{feed_name}** ({len(items)} entrées):\n\n"
        elif format_type == "slack":
            feed_header = f"*{feed_name}* ({len(items)} entrées):\n\n"

        # construit la première entrée RSS
        first_item_line = ""
        if items:
            first_item_line = _format_standalone_rss_item(items[0], 1, format_type, timezone)

        # vérification d'atomicité
        feed_with_first = feed_header + first_item_line
        test_content = current_batch + feed_with_first

        if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) >= max_bytes:
            if current_batch_has_content:
                _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
            current_batch = _safe_new_batch(
                base_header + section_header + feed_with_first,
                base_footer, max_bytes, base_header, batches
            )
            current_batch_has_content = True
            start_index = 1
        else:
            current_batch = test_content
            current_batch_has_content = True
            start_index = 1

        # traite les entrées restantes
        for j in range(start_index, len(items)):
            item_line = _format_standalone_rss_item(items[j], j + 1, format_type, timezone)

            test_content = current_batch + item_line
            if len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8")) >= max_bytes:
                if current_batch_has_content:
                    _safe_append_batch(batches, current_batch, base_footer, max_bytes, base_header)
                current_batch = _safe_new_batch(
                    base_header + section_header + feed_header + item_line,
                    base_footer, max_bytes, base_header, batches
                )
                current_batch_has_content = True
            else:
                current_batch = test_content
                current_batch_has_content = True

        current_batch += "\n"

    return current_batch, current_batch_has_content, batches


def _format_standalone_platform_item(item: Dict, index: int, format_type: str, rank_threshold: int = 10) -> str:
    """Formate une entrée de tendances de la Zone d'affichage autonome (réutilise le style de la zone des statistiques des tendances)

    Args:
        item: entrée de tendances, contient title, url, rank, ranks, first_time, last_time, count
        index: numéro d'ordre
        format_type: type de format
        rank_threshold: seuil de mise en évidence du classement

    Returns:
        chaîne de la ligne d'entrée formatée
    """
    title = item.get("title", "")
    url = item.get("url", "") or item.get("mobileUrl", "")
    ranks = item.get("ranks", [])
    rank = item.get("rank", 0)
    first_time = item.get("first_time", "")
    last_time = item.get("last_time", "")
    count = item.get("count", 1)

    # utilise format_rank_display pour formater le classement (réutilise la logique de la zone des statistiques des tendances)
    # s'il n'y a pas de liste ranks, on la construit à partir du rang unique
    if not ranks and rank > 0:
        ranks = [rank]
    rank_timeline = item.get("rank_timeline")
    rank_display = format_rank_display(ranks, rank_threshold, format_type, rank_timeline=rank_timeline) if ranks else ""

    # construit l'affichage de l'heure (relie la plage par ~, cohérent avec la zone des statistiques des tendances)
    # convertit le format HH-MM en format HH:MM
    time_display = ""
    if first_time and last_time and first_time != last_time:
        first_time_display = convert_time_for_display(first_time)
        last_time_display = convert_time_for_display(last_time)
        time_display = f"{first_time_display}~{last_time_display}"
    elif first_time:
        time_display = convert_time_for_display(first_time)

    # construit l'affichage du nombre d'occurrences (format (N fois), cohérent avec la zone des statistiques des tendances)
    count_display = f"({count} fois)" if count > 1 else ""

    # construit la ligne d'entrée selon le type de format (réutilise le style de la zone des statistiques des tendances)
    if format_type == "feishu":
        if url:
            item_line = f"  {index}. [{title}]({url})"
        else:
            item_line = f"  {index}. {title}"
        if rank_display:
            item_line += f" {rank_display}"
        if time_display:
            item_line += f" <font color='grey'>- {time_display}</font>"
        if count_display:
            item_line += f" <font color='green'>{count_display}</font>"

    elif format_type == "dingtalk":
        if url:
            item_line = f"  {index}. [{title}]({url})"
        else:
            item_line = f"  {index}. {title}"
        if rank_display:
            item_line += f" {rank_display}"
        if time_display:
            item_line += f" - {time_display}"
        if count_display:
            item_line += f" {count_display}"

    elif format_type == "telegram":
        if url:
            item_line = f"  {index}. {title} ({url})"
        else:
            item_line = f"  {index}. {title}"
        if rank_display:
            item_line += f" {rank_display}"
        if time_display:
            item_line += f" - {time_display}"
        if count_display:
            item_line += f" {count_display}"

    elif format_type == "slack":
        if url:
            item_line = f"  {index}. <{url}|{title}>"
        else:
            item_line = f"  {index}. {title}"
        if rank_display:
            item_line += f" {rank_display}"
        if time_display:
            item_line += f" _{time_display}_"
        if count_display:
            item_line += f" {count_display}"

    else:
        # wework, bark, ntfy
        if url:
            item_line = f"  {index}. [{title}]({url})"
        else:
            item_line = f"  {index}. {title}"
        if rank_display:
            item_line += f" {rank_display}"
        if time_display:
            item_line += f" - {time_display}"
        if count_display:
            item_line += f" {count_display}"

    item_line += "\n"
    return item_line


def _format_standalone_rss_item(
    item: Dict, index: int, format_type: str, timezone: str = "Asia/Shanghai"
) -> str:
    """Formate une entrée RSS de la Zone d'affichage autonome

    Args:
        item: entrée RSS, contient title, url, published_at, author
        index: numéro d'ordre
        format_type: type de format
        timezone: nom du fuseau horaire

    Returns:
        chaîne de la ligne d'entrée formatée
    """
    title = item.get("title", "")
    url = item.get("url", "")
    published_at = item.get("published_at", "")
    author = item.get("author", "")

    # utilise un format d'heure lisible
    friendly_time = ""
    if published_at:
        friendly_time = format_iso_time_friendly(published_at, timezone, include_date=True)

    # construit les métadonnées
    meta_parts = []
    if friendly_time:
        meta_parts.append(friendly_time)
    if author:
        meta_parts.append(author)
    meta_str = ", ".join(meta_parts)

    # construit la ligne d'entrée selon le type de format
    if format_type == "feishu":
        if url:
            item_line = f"  {index}. [{title}]({url})"
        else:
            item_line = f"  {index}. {title}"
        if meta_str:
            item_line += f" <font color='grey'>- {meta_str}</font>"
    elif format_type == "telegram":
        if url:
            item_line = f"  {index}. {title} ({url})"
        else:
            item_line = f"  {index}. {title}"
        if meta_str:
            item_line += f" - {meta_str}"
    elif format_type == "slack":
        if url:
            item_line = f"  {index}. <{url}|{title}>"
        else:
            item_line = f"  {index}. {title}"
        if meta_str:
            item_line += f" _{meta_str}_"
    else:
        # wework, bark, ntfy, dingtalk
        if url:
            item_line = f"  {index}. [{title}]({url})"
        else:
            item_line = f"  {index}. {title}"
        if meta_str:
            item_line += f" `{meta_str}`"

    item_line += "\n"
    return item_line
