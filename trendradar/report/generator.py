# coding=utf-8
"""
Module de génération de rapports.

Fournit la préparation des données et la génération HTML :
- prepare_report_data : prépare les données du rapport
- generate_html_report : génère le rapport HTML
"""

from pathlib import Path
from typing import Dict, List, Optional, Callable

from trendradar.i18n import REPORT_LANGS


def prepare_report_data(
    stats: List[Dict],
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
    rank_threshold: int = 3,
    show_new_section: bool = True,
) -> Dict:
    """
    Prépare les données du rapport.

    Args:
        stats: liste des résultats de statistiques
        failed_ids: liste des IDs en échec
        new_titles: nouveaux titres
        id_to_name: correspondance ID vers nom
        mode: mode du rapport (daily/incremental/current)
        rank_threshold: seuil de classement
        show_new_section: afficher ou non la zone des nouvelles tendances

    Returns:
        Dict: données du rapport préparées
    """
    processed_new_titles = []

    stats_title_set = {
        t["title"]
        for stat in stats
        for t in stat.get("titles", [])
    }

    # Filtre les nouveaux titres : ne garde que ceux présents dans stats (donc passés par le filtre IA/mots-clés)
    filtered_new_titles = {}
    if new_titles and id_to_name:
        for source_id, titles_data in new_titles.items():
            filtered_titles = {}
            for title, title_data in titles_data.items():
                if title in stats_title_set:
                    filtered_titles[title] = title_data
            if filtered_titles:
                filtered_new_titles[source_id] = filtered_titles

        original_new_count = sum(len(titles) for titles in new_titles.values()) if new_titles else 0
        filtered_new_count = sum(len(titles) for titles in filtered_new_titles.values()) if filtered_new_titles else 0
        if original_new_count > 0:
            print(f"Après filtrage des nouvelles tendances : {filtered_new_count} conservées (sur {original_new_count} initiales)")

    # En mode incrémental ou si la configuration le désactive, masque la zone des nouvelles actualités (le décompte reste fait)
    # Si toutes les entrées de tendances sont nouvelles (première exécution), on masque aussi pour éviter une duplication complète avec la zone principale
    all_new_titles = {title for titles in filtered_new_titles.values() for title in titles}
    all_are_new = bool(all_new_titles) and all_new_titles == stats_title_set
    hide_new_section = mode == "incremental" or not show_new_section or all_are_new

    if not hide_new_section and filtered_new_titles and id_to_name:
        for source_id, titles_data in filtered_new_titles.items():
            source_name = id_to_name.get(source_id, source_id)
            source_titles = []

            for title, title_data in titles_data.items():
                url = title_data.get("url", "")
                mobile_url = title_data.get("mobileUrl", "")
                ranks = title_data.get("ranks", [])

                processed_title = {
                    "title": title,
                    "source_name": source_name,
                    "time_display": "",
                    "count": 1,
                    "ranks": ranks,
                    "rank_threshold": rank_threshold,
                    "url": url,
                    "mobile_url": mobile_url,
                    "is_new": True,
                    "rank_timeline": title_data.get("rank_timeline", []),
                }
                source_titles.append(processed_title)

            if source_titles:
                processed_new_titles.append(
                    {
                        "source_id": source_id,
                        "source_name": source_name,
                        "titles": source_titles,
                    }
                )

    processed_stats = []
    for stat in stats:
        if stat["count"] <= 0:
            continue

        processed_titles = []
        for title_data in stat["titles"]:
            processed_title = {
                "title": title_data["title"],
                "source_name": title_data["source_name"],
                "time_display": title_data["time_display"],
                "count": title_data["count"],
                "ranks": title_data["ranks"],
                "rank_threshold": title_data["rank_threshold"],
                "url": title_data.get("url", ""),
                "mobile_url": title_data.get("mobileUrl", ""),
                "is_new": title_data.get("is_new", False),
                "rank_timeline": title_data.get("rank_timeline", []),
            }
            processed_titles.append(processed_title)

        processed_stats.append(
            {
                "word": stat["word"],
                "count": stat["count"],
                "percentage": stat.get("percentage", 0),
                "titles": processed_titles,
            }
        )

    # total_new_count est toujours calculé sur le résultat filtré (pour les statistiques d'en-tête), indépendamment de hide_new_section
    total_new_count = sum(len(titles) for titles in filtered_new_titles.values())

    return {
        "stats": processed_stats,
        "new_titles": processed_new_titles,
        "failed_ids": failed_ids or [],
        "total_new_count": total_new_count,
    }


def generate_html_report(
    stats: List[Dict],
    total_titles: int,
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
    update_info: Optional[Dict] = None,
    rank_threshold: int = 3,
    output_dir: str = "output",
    date_folder: str = "",
    time_filename: str = "",
    render_html_func: Optional[Callable] = None,
    report_metadata: Optional[Dict] = None,
) -> str:
    """
    Génère le rapport HTML, en deux langues (FR + EN).

    Pour chaque langue de REPORT_LANGS, la fonction produit :
    1. un instantané horodaté output/html/<date>/<heure>_<lang>.html (historique)
    2. une copie dans output/html/latest/<mode>_<lang>.html (dernier rapport)

    Pour la langue par défaut ("fr"), elle écrit en plus, pour ne rien casser des
    appelants existants :
    - l'instantané non suffixé output/html/<date>/<heure>.html
    - output/html/latest/<mode>.html
    - output/index.html (montage Docker Volume)
    - index.html à la racine (GitHub Pages)

    Args:
        stats: liste des résultats de statistiques
        total_titles: nombre total de titres
        failed_ids: liste des IDs en échec
        new_titles: nouveaux titres
        id_to_name: correspondance ID vers nom
        mode: mode du rapport (daily/incremental/current)
        update_info: informations de mise à jour
        rank_threshold: seuil de classement
        output_dir: répertoire de sortie
        date_folder: nom du dossier de date
        time_filename: nom de fichier basé sur l'heure
        render_html_func: fonction de rendu HTML

    Returns:
        str: chemin du fichier HTML par défaut (instantané FR non suffixé)
    """
    # Prépare les données du rapport
    report_data = prepare_report_data(
        stats,
        failed_ids,
        new_titles,
        id_to_name,
        mode,
        rank_threshold,
    )

    if report_metadata:
        _METADATA_KEYS = {
            "hotlist_total", "platform_total", "rss_matched_count",
            "rss_total_count", "rss_source_total", "rss_source_failed",
        }
        for key in _METADATA_KEYS:
            if key in report_metadata:
                report_data[key] = report_metadata[key]

    # Construit les chemins de sortie (structure aplatie : output/html/<date>/)
    snapshot_path = Path(output_dir) / "html" / date_folder
    snapshot_path.mkdir(parents=True, exist_ok=True)
    latest_dir = Path(output_dir) / "html" / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    default_lang = REPORT_LANGS[0] if REPORT_LANGS else "fr"

    def _render(language: str) -> str:
        """Rend le HTML pour une langue ; tolère un render_html_func sans paramètre language."""
        if render_html_func:
            try:
                return render_html_func(
                    report_data, total_titles, mode, update_info, language=language
                )
            except TypeError:
                # Compat : ancien render_html_func sans paramètre language
                return render_html_func(report_data, total_titles, mode, update_info)
        # HTML simple par défaut
        return f"<html lang=\"{language}\"><body><h1>Report</h1><pre>{report_data}</pre></body></html>"

    default_snapshot_file = str(snapshot_path / f"{time_filename}.html")

    for language in REPORT_LANGS:
        html_content = _render(language)

        # 1. Instantané horodaté suffixé par la langue (historique)
        with open(snapshot_path / f"{time_filename}_{language}.html", "w", encoding="utf-8") as f:
            f.write(html_content)

        # 2. Dernier rapport suffixé par la langue
        with open(latest_dir / f"{mode}_{language}.html", "w", encoding="utf-8") as f:
            f.write(html_content)

        # Pour la langue par défaut, écrit aussi les chemins historiques non suffixés
        if language == default_lang:
            with open(default_snapshot_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            with open(latest_dir / f"{mode}.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            # output/index.html (montage Docker Volume)
            with open(Path(output_dir) / "index.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            # index.html à la racine (GitHub Pages)
            with open(Path("index.html"), "w", encoding="utf-8") as f:
                f.write(html_content)

    return default_snapshot_file
