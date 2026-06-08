# coding=utf-8
"""
Module de rendu du contenu des notifications

Fournit le rendu du contenu des notifications multi-plateformes et génère des messages formatés.
"""

from datetime import datetime
from typing import Dict, List, Optional, Callable

from trendradar.report.formatter import format_title_for_platform


# Ordre des zones par défaut
DEFAULT_REGION_ORDER = ["hotlist", "rss", "new_items", "standalone", "ai_analysis"]


def render_feishu_content(
    report_data: Dict,
    update_info: Optional[Dict] = None,
    mode: str = "daily",
    separator: str = "---",
    region_order: Optional[List[str]] = None,
    get_time_func: Optional[Callable[[], datetime]] = None,
    rss_items: Optional[list] = None,
    show_new_section: bool = True,
) -> str:
    """Rend le contenu de notification Feishu (fusion tendances + RSS).

    Args:
        report_data: dictionnaire des données du rapport (stats, new_titles, failed_ids, total_new_count)
        update_info: informations de mise à jour de version (optionnel)
        mode: mode du rapport ("daily", "incremental", "current")
        separator: séparateur de contenu
        region_order: liste de l'ordre d'affichage des zones
        get_time_func: fonction renvoyant l'heure courante (optionnel, défaut datetime.now())
        rss_items: liste des entrées RSS (optionnel, pour la fusion)
        show_new_section: afficher ou non la zone des nouvelles tendances

    Returns:
        contenu du message Feishu formaté
    """
    if region_order is None:
        region_order = DEFAULT_REGION_ORDER

    # Génère la section des statistiques de mots-clés
    stats_content = ""
    if report_data["stats"]:
        stats_content += "📊 **Statistiques des tendances**\n\n"

        total_count = len(report_data["stats"])

        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]

            sequence_display = f"<font color='grey'>[{i + 1}/{total_count}]</font>"

            if count >= 10:
                stats_content += f"🔥 {sequence_display} **{word}** : <font color='red'>{count}</font> entrées\n\n"
            elif count >= 5:
                stats_content += f"📈 {sequence_display} **{word}** : <font color='orange'>{count}</font> entrées\n\n"
            else:
                stats_content += f"📌 {sequence_display} **{word}** : {count} entrées\n\n"

            for j, title_data in enumerate(stat["titles"], 1):
                formatted_title = format_title_for_platform(
                    "feishu", title_data, show_source=True
                )
                stats_content += f"  {j}. {formatted_title}\n"

                if j < len(stat["titles"]):
                    stats_content += "\n"

            if i < len(report_data["stats"]) - 1:
                stats_content += f"\n{separator}\n\n"

    # Génère la section des nouvelles actualités
    new_titles_content = ""
    if show_new_section and report_data["new_titles"]:
        new_titles_content += (
            f"🆕 **Nouvelles tendances de cette exécution** (total : {report_data['total_new_count']} entrées)\n\n"
        )

        for source_data in report_data["new_titles"]:
            new_titles_content += (
                f"**{source_data['source_name']}** ({len(source_data['titles'])} entrées) :\n"
            )

            for j, title_data in enumerate(source_data["titles"], 1):
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False
                formatted_title = format_title_for_platform(
                    "feishu", title_data_copy, show_source=False
                )
                new_titles_content += f"  {j}. {formatted_title}\n"

            new_titles_content += "\n"

    # Contenu RSS
    rss_content = ""
    if rss_items:
        rss_content = _render_rss_section_feishu(rss_items, separator)

    # Prépare la correspondance des contenus de chaque zone
    region_contents = {
        "hotlist": stats_content,
        "new_items": new_titles_content,
        "rss": rss_content,
    }

    # Assemble les contenus dans l'ordre de region_order
    text_content = ""
    for region in region_order:
        content = region_contents.get(region, "")
        if content:
            if text_content:
                text_content += f"\n{separator}\n\n"
            text_content += content

    if not text_content:
        if mode == "incremental":
            mode_text = "Aucune nouvelle tendance correspondante en mode incrémental"
        elif mode == "current":
            mode_text = "Aucune tendance correspondante pour le classement actuel"
        else:
            mode_text = "Aucune tendance correspondante"
        text_content = f"📭 {mode_text}\n\n"

    if report_data["failed_ids"]:
        if text_content and "Aucune tendance correspondante" not in text_content:
            text_content += f"\n{separator}\n\n"

        text_content += "⚠️ **Plateformes en échec de collecte :**\n\n"
        for i, id_value in enumerate(report_data["failed_ids"], 1):
            text_content += f"  • <font color='red'>{id_value}</font>\n"

    # Récupère l'heure courante
    now = get_time_func() if get_time_func else datetime.now()
    text_content += (
        f"\n\n<font color='grey'>Mis à jour le : {now.strftime('%Y-%m-%d %H:%M:%S')}</font>"
    )

    if update_info:
        text_content += f"\n<font color='grey'>TrendRadar a détecté une nouvelle version {update_info['remote_version']}, version actuelle {update_info['current_version']}</font>"

    return text_content


def render_dingtalk_content(
    report_data: Dict,
    update_info: Optional[Dict] = None,
    mode: str = "daily",
    region_order: Optional[List[str]] = None,
    get_time_func: Optional[Callable[[], datetime]] = None,
    rss_items: Optional[list] = None,
    show_new_section: bool = True,
) -> str:
    """Rend le contenu de notification DingTalk (fusion tendances + RSS).

    Args:
        report_data: dictionnaire des données du rapport (stats, new_titles, failed_ids, total_new_count)
        update_info: informations de mise à jour de version (optionnel)
        mode: mode du rapport ("daily", "incremental", "current")
        region_order: liste de l'ordre d'affichage des zones
        get_time_func: fonction renvoyant l'heure courante (optionnel, défaut datetime.now())
        rss_items: liste des entrées RSS (optionnel, pour la fusion)
        show_new_section: afficher ou non la zone des nouvelles tendances

    Returns:
        contenu du message DingTalk formaté
    """
    if region_order is None:
        region_order = DEFAULT_REGION_ORDER

    total_titles = sum(
        len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
    )
    now = get_time_func() if get_time_func else datetime.now()

    # L'en-tête est construit par le splitter, on ne le répète pas ici
    header_content = ""

    # Génère la section des statistiques de mots-clés
    stats_content = ""
    if report_data["stats"]:
        stats_content += "📊 **Statistiques des tendances**\n\n"

        total_count = len(report_data["stats"])

        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]

            sequence_display = f"[{i + 1}/{total_count}]"

            if count >= 10:
                stats_content += f"🔥 {sequence_display} **{word}** : **{count}** entrées\n\n"
            elif count >= 5:
                stats_content += f"📈 {sequence_display} **{word}** : **{count}** entrées\n\n"
            else:
                stats_content += f"📌 {sequence_display} **{word}** : {count} entrées\n\n"

            for j, title_data in enumerate(stat["titles"], 1):
                formatted_title = format_title_for_platform(
                    "dingtalk", title_data, show_source=True
                )
                stats_content += f"  {j}. {formatted_title}\n"

                if j < len(stat["titles"]):
                    stats_content += "\n"

            if i < len(report_data["stats"]) - 1:
                stats_content += "\n---\n\n"

    # Génère la section des nouvelles actualités
    new_titles_content = ""
    if show_new_section and report_data["new_titles"]:
        new_titles_content += (
            f"🆕 **Nouvelles tendances de cette exécution** (total : {report_data['total_new_count']} entrées)\n\n"
        )

        for source_data in report_data["new_titles"]:
            new_titles_content += f"**{source_data['source_name']}** ({len(source_data['titles'])} entrées) :\n\n"

            for j, title_data in enumerate(source_data["titles"], 1):
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False
                formatted_title = format_title_for_platform(
                    "dingtalk", title_data_copy, show_source=False
                )
                new_titles_content += f"  {j}. {formatted_title}\n"

            new_titles_content += "\n"

    # Contenu RSS
    rss_content = ""
    if rss_items:
        rss_content = _render_rss_section_markdown(rss_items)

    # Prépare la correspondance des contenus de chaque zone
    region_contents = {
        "hotlist": stats_content,
        "new_items": new_titles_content,
        "rss": rss_content,
    }

    # Assemble les contenus dans l'ordre de region_order
    text_content = header_content
    has_content = False
    for region in region_order:
        content = region_contents.get(region, "")
        if content:
            if has_content:
                text_content += "\n---\n\n"
            text_content += content
            has_content = True

    if not has_content:
        if mode == "incremental":
            mode_text = "Aucune nouvelle tendance correspondante en mode incrémental"
        elif mode == "current":
            mode_text = "Aucune tendance correspondante pour le classement actuel"
        else:
            mode_text = "Aucune tendance correspondante"
        text_content += f"📭 {mode_text}\n\n"

    if report_data["failed_ids"]:
        if "Aucune tendance correspondante" not in text_content:
            text_content += "\n---\n\n"

        text_content += "⚠️ **Plateformes en échec de collecte :**\n\n"
        for i, id_value in enumerate(report_data["failed_ids"], 1):
            text_content += f"  • **{id_value}**\n"

    text_content += f"\n\n> Mis à jour le : {now.strftime('%Y-%m-%d %H:%M:%S')}"

    if update_info:
        text_content += f"\n> TrendRadar a détecté une nouvelle version **{update_info['remote_version']}**, version actuelle **{update_info['current_version']}**"

    return text_content



# === Fonctions auxiliaires de rendu du contenu RSS (pour la fusion) ===

def _render_rss_section_feishu(rss_items: list, separator: str = "---") -> str:
    """Rend le bloc de contenu RSS (format Feishu, pour la fusion)."""
    if not rss_items:
        return ""

    # Regroupe par feed_id
    feeds_map: Dict[str, list] = {}
    for item in rss_items:
        feed_id = item.get("feed_id", "unknown")
        if feed_id not in feeds_map:
            feeds_map[feed_id] = []
        feeds_map[feed_id].append(item)

    text_content = f"📰 **Mise à jour des abonnements RSS** (total : {len(rss_items)} entrées)\n\n"

    for feed_id, items in feeds_map.items():
        feed_name = items[0].get("feed_name", feed_id) if items else feed_id

        text_content += f"**{feed_name}** ({len(items)} entrées)\n\n"

        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            published_at = item.get("published_at", "")

            if url:
                text_content += f"  {i}. [{title}]({url})"
            else:
                text_content += f"  {i}. {title}"

            if published_at:
                text_content += f" <font color='grey'>- {published_at}</font>"

            text_content += "\n"

            if i < len(items):
                text_content += "\n"

        text_content += "\n"

    return text_content.rstrip("\n")


def _render_rss_section_markdown(rss_items: list) -> str:
    """Rend le bloc de contenu RSS (format Markdown générique, pour la fusion)."""
    if not rss_items:
        return ""

    # Regroupe par feed_id
    feeds_map: Dict[str, list] = {}
    for item in rss_items:
        feed_id = item.get("feed_id", "unknown")
        if feed_id not in feeds_map:
            feeds_map[feed_id] = []
        feeds_map[feed_id].append(item)

    text_content = f"📰 **Mise à jour des abonnements RSS** (total : {len(rss_items)} entrées)\n\n"

    for feed_id, items in feeds_map.items():
        feed_name = items[0].get("feed_name", feed_id) if items else feed_id

        text_content += f"**{feed_name}** ({len(items)} entrées)\n"

        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            published_at = item.get("published_at", "")

            if url:
                text_content += f"  {i}. [{title}]({url})"
            else:
                text_content += f"  {i}. {title}"

            if published_at:
                text_content += f" `{published_at}`"

            text_content += "\n"

        text_content += "\n"

    return text_content.rstrip("\n")
