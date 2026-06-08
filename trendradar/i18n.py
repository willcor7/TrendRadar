# coding=utf-8
"""
Module d'internationalisation (i18n) léger, sans dépendance.

Centralise tous les libellés d'interface utilisateur des rapports HTML
(html.py + rss_html.py) ainsi que les libellés « chrome » des notifications
(titres de blocs de ai/formatter.py, en-têtes de renderer.py).

Les clés sont stables, en anglais snake_case. La langue par défaut est le
français ("fr"). Une langue manquante retombe sur le français, puis sur la clé
elle-même.

API :
- LABELS : dictionnaire {langue: {clé: libellé}}
- t(key, lang="fr") : traduit une clé
- ui_lang() : langue d'UI par défaut (variable d'environnement UI_LANG)
- REPORT_LANGS : langues de rapport à générer (["fr", "en"])
"""

import os
from typing import List


# Langues de rapport à générer (un fichier HTML par langue).
REPORT_LANGS: List[str] = ["fr", "en"]


LABELS = {
    "fr": {
        # ---- En-têtes / titres de page ----
        "report_title": "Analyse des tendances",
        "rss_page_title": "Contenu des abonnements RSS",
        "rss_report_title": "Contenu des abonnements RSS",
        # ---- Boutons d'en-tête (HTML report) ----
        "toggle_wide": "Basculer plein écran / colonne étroite",
        "toggle_dark": "Basculer mode sombre / clair",
        "export": "Exporter",
        "export_full_screenshot": "Capture pleine page",
        "export_segmented_screenshot": "Capture segmentée",
        "export_markdown": "Markdown",
        "save_as_image": "Enregistrer en image",
        # ---- Bloc d'informations de l'en-tête ----
        "info_report_type": "Type de rapport",
        "info_generated_at": "Heure de génération",
        "info_hotlist_hits": "Tendances retenues",
        "info_rss_hits": "RSS retenus",
        "info_hotlist_platforms": "Plateformes de tendances",
        "info_rss_sources": "Sources RSS",
        "info_new_hotspots": "Nouvelles tendances",
        "info_ai_analysis": "Analyse IA",
        "info_subscription_items": "Entrées d'abonnement",
        # ---- Modes de rapport (affichage) ----
        "mode_current": "Classement actuel",
        "mode_incremental": "Analyse incrémentale",
        "mode_daily": "Synthèse de la journée",
        # ---- Valeurs spéciales ----
        "not_enabled": "Désactivé",
        "skipped": "Ignoré",
        "to_configure": "À configurer",
        # ---- Sections / contenu ----
        "search_placeholder": "Rechercher un titre...",
        "failed_platforms": "⚠️ Plateformes en échec",
        "new_hotspots_title": "Nouvelles tendances de cette exécution (total : {count})",
        "items_unit": "entrées",
        "count_unit": "entrées",
        "occurrence_unit": "fois",
        "rss_subscription_update": "Mise à jour des abonnements RSS",
        "rss_new_update": "Nouveautés RSS",
        "standalone_section": "Zone d'affichage autonome",
        "tab_all": "Tout",
        # ---- Pied de page ----
        "footer_generated_by": "Généré par",
        "footer_github_project": "Projet open source GitHub",
        "footer_new_version": "Nouvelle version {remote} disponible, version actuelle {current}",
        "footer_generated_by_plain": "Généré par TrendRadar",
        # ---- Infobulle de raccourcis (FAB) ----
        "fab_back_to_top": "Retour en haut",
        "tip_toggle_wide": "Basculer plein écran",
        "tip_dark_mode": "Mode sombre",
        "tip_search": "Rechercher",
        "tip_prev_tab": "Onglet précédent",
        "tip_next_tab": "Onglet suivant",
        "tip_copyable_number": "Numéro copiable",
        "tip_key_click": "clic",
        # ---- États de boutons JS ----
        "js_generating": "Génération...",
        "js_analyzing": "Analyse...",
        "js_generating_progress": "Génération ({current}/{total})...",
        "js_save_success": "Enregistré !",
        "js_save_failed": "Échec de l'enregistrement",
        "js_saved_images": "{count} images enregistrées !",
        "js_copy_tooltip": "Cliquer pour copier le titre et le lien",
        # ---- Libellés export Markdown (JS) ----
        "md_hot_news": "Tendances",
        "md_new_hotspots": "Nouvelles tendances de cette exécution",
        "md_rss_update": "Mise à jour des abonnements RSS",
        "md_ai_analysis": "Analyse IA",
        "md_ai_hot_analysis": "Analyse IA des tendances",
        "md_standalone": "Zone d'affichage autonome",
        "md_crawl_errors": "Anomalies de collecte",
        # ---- Captures de fichiers (noms) ----
        "screenshot_filename_label": "Analyse_des_tendances",
        "screenshot_rss_filename_label": "Abonnement_RSS",
        # ---- Blocs d'analyse IA (titres) ----
        "ai_title": "✨ Analyse IA des tendances",
        "ai_badge": "IA",
        "ai_core_trends": "Panorama des tendances clés",
        "ai_sentiment_controversy": "Climat d'opinion et controverses",
        "ai_signals": "Mouvements et signaux faibles",
        "ai_rss_insights": "Analyses approfondies RSS",
        "ai_outlook_strategy": "Recommandations stratégiques",
        "ai_standalone_summaries": "Aperçu des sources autonomes",
        "ai_failed": "Échec de l'analyse IA",
        "ai_unknown_error": "Erreur inconnue",
        # ---- Notifications (renderer / formatter chrome) ----
        "no_matched_hotspots_current": "Aucune tendance correspondante pour le classement actuel",
    },
    "en": {
        # ---- Headers / page titles ----
        "report_title": "Trend Analysis",
        "rss_page_title": "RSS Subscription Content",
        "rss_report_title": "RSS Subscription Content",
        # ---- Header buttons (HTML report) ----
        "toggle_wide": "Toggle wide / narrow layout",
        "toggle_dark": "Toggle dark / light mode",
        "export": "Export",
        "export_full_screenshot": "Full-page screenshot",
        "export_segmented_screenshot": "Segmented screenshot",
        "export_markdown": "Markdown",
        "save_as_image": "Save as image",
        # ---- Header info block ----
        "info_report_type": "Report type",
        "info_generated_at": "Generated at",
        "info_hotlist_hits": "Trends matched",
        "info_rss_hits": "RSS matched",
        "info_hotlist_platforms": "Trend platforms",
        "info_rss_sources": "RSS sources",
        "info_new_hotspots": "New trends",
        "info_ai_analysis": "AI analysis",
        "info_subscription_items": "Subscription items",
        # ---- Report modes (display) ----
        "mode_current": "Current Ranking",
        "mode_incremental": "Incremental Analysis",
        "mode_daily": "Daily Summary",
        # ---- Special values ----
        "not_enabled": "Disabled",
        "skipped": "Skipped",
        "to_configure": "To configure",
        # ---- Sections / content ----
        "search_placeholder": "Search a title...",
        "failed_platforms": "⚠️ Failed platforms",
        "new_hotspots_title": "New trends in this run (total: {count})",
        "items_unit": "items",
        "count_unit": "items",
        "occurrence_unit": "times",
        "rss_subscription_update": "RSS subscription update",
        "rss_new_update": "New RSS items",
        "standalone_section": "Standalone display area",
        "tab_all": "All",
        # ---- Footer ----
        "footer_generated_by": "Generated by",
        "footer_github_project": "GitHub open source project",
        "footer_new_version": "New version {remote} available, current version {current}",
        "footer_generated_by_plain": "Generated by TrendRadar",
        # ---- Shortcut tooltip (FAB) ----
        "fab_back_to_top": "Back to top",
        "tip_toggle_wide": "Toggle wide",
        "tip_dark_mode": "Dark mode",
        "tip_search": "Search",
        "tip_prev_tab": "Previous tab",
        "tip_next_tab": "Next tab",
        "tip_copyable_number": "Number is copyable",
        "tip_key_click": "click",
        # ---- JS button states ----
        "js_generating": "Generating...",
        "js_analyzing": "Analyzing...",
        "js_generating_progress": "Generating ({current}/{total})...",
        "js_save_success": "Saved!",
        "js_save_failed": "Save failed",
        "js_saved_images": "{count} images saved!",
        "js_copy_tooltip": "Click to copy title and link",
        # ---- Markdown export labels (JS) ----
        "md_hot_news": "Trends",
        "md_new_hotspots": "New trends in this run",
        "md_rss_update": "RSS subscription update",
        "md_ai_analysis": "AI analysis",
        "md_ai_hot_analysis": "AI trend analysis",
        "md_standalone": "Standalone display area",
        "md_crawl_errors": "Crawl anomalies",
        # ---- Screenshot filenames ----
        "screenshot_filename_label": "Trend_Analysis",
        "screenshot_rss_filename_label": "RSS_Subscription",
        # ---- AI analysis blocks (titles) ----
        "ai_title": "✨ AI Trend Analysis",
        "ai_badge": "AI",
        "ai_core_trends": "Core trend overview",
        "ai_sentiment_controversy": "Public sentiment & controversy",
        "ai_signals": "Movements & weak signals",
        "ai_rss_insights": "RSS deep insights",
        "ai_outlook_strategy": "Strategic recommendations",
        "ai_standalone_summaries": "Standalone sources overview",
        "ai_failed": "AI analysis failed",
        "ai_unknown_error": "Unknown error",
        # ---- Notifications (renderer / formatter chrome) ----
        "no_matched_hotspots_current": "No matching trends for the current ranking",
    },
}


def t(key: str, lang: str = "fr") -> str:
    """Traduit une clé dans la langue demandée.

    Retombe sur le français si la clé est absente de la langue demandée,
    puis sur la clé elle-même si elle est absente du français.
    """
    return LABELS.get(lang, {}).get(key, LABELS["fr"].get(key, key))


def ui_lang() -> str:
    """Langue d'interface par défaut, lue depuis la variable d'environnement UI_LANG.

    Retourne "fr" par défaut.
    """
    lang = os.environ.get("UI_LANG", "fr").strip().lower()
    return lang if lang in LABELS else "fr"
