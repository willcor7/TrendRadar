# coding=utf-8
"""
Module de rendu du rapport HTML.

Fournit la génération de rapports de tendances au format HTML.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from trendradar.report.helpers import html_escape, calculate_rank_trend
from trendradar.utils.time import convert_time_for_display
from trendradar.ai.formatter import render_ai_analysis_html_rich
from trendradar.i18n import t


def render_html_content(
    report_data: Dict,
    total_titles: int,
    mode: str = "daily",
    update_info: Optional[Dict] = None,
    *,
    region_order: Optional[List[str]] = None,
    get_time_func: Optional[Callable[[], datetime]] = None,
    rss_items: Optional[List[Dict]] = None,
    rss_new_items: Optional[List[Dict]] = None,
    display_mode: str = "keyword",
    standalone_data: Optional[Dict] = None,
    ai_analysis: Optional[Any] = None,
    show_new_section: bool = True,
    language: str = "fr",
) -> str:
    """Rend le contenu HTML.

    Args:
        report_data: dictionnaire des données du rapport, contenant stats,
            new_titles, failed_ids, total_new_count
        total_titles: nombre total d'actualités
        mode: mode du rapport ("daily", "current", "incremental")
        update_info: informations de mise à jour (optionnel)
        region_order: liste de l'ordre d'affichage des zones
        get_time_func: fonction renvoyant l'heure courante (optionnel, défaut datetime.now)
        rss_items: liste des entrées de statistiques RSS (optionnel)
        rss_new_items: liste des nouvelles entrées RSS (optionnel)
        display_mode: mode d'affichage ("keyword"=par mot-clé, "platform"=par plateforme)
        standalone_data: données de la zone d'affichage autonome (optionnel), contient platforms et rss_feeds
        ai_analysis: objet résultat de l'analyse IA (optionnel), instance AIAnalysisResult
        show_new_section: afficher ou non la zone des nouvelles tendances
        language: langue du rapport ("fr" ou "en")

    Returns:
        chaîne HTML rendue
    """
    # Ordre des zones par défaut
    default_region_order = ["hotlist", "rss", "new_items", "standalone", "ai_analysis"]
    if region_order is None:
        region_order = default_region_order

    # Objet i18n injecté côté JS pour les états de boutons et l'export Markdown
    import json as _json
    js_i18n = {
        "generating": t("js_generating", language),
        "analyzing": t("js_analyzing", language),
        "generatingProgress": t("js_generating_progress", language),
        "saveSuccess": t("js_save_success", language),
        "saveFailed": t("js_save_failed", language),
        "savedImages": t("js_saved_images", language),
        "copyTooltip": t("js_copy_tooltip", language),
        "screenshotLabel": t("screenshot_filename_label", language),
        "mdHotNews": t("md_hot_news", language),
        "mdNewHotspots": t("md_new_hotspots", language),
        "mdRssUpdate": t("md_rss_update", language),
        "mdAiAnalysis": t("md_ai_analysis", language),
        "mdAiHotAnalysis": t("md_ai_hot_analysis", language),
        "mdStandalone": t("md_standalone", language),
        "mdCrawlErrors": t("md_crawl_errors", language),
    }
    js_i18n_json = _json.dumps(js_i18n, ensure_ascii=False)

    html = f"""
    <!DOCTYPE html>
    <html lang="{language}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{t("report_title", language)}</title>
"""

    html += """
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js" integrity="sha512-BNaRQnYJYiPSqHHDb58B0yaPfCu+Wgds8Gp/gU33kqBtgNS4tSPHuGibyoeqMV/TJlSKda6FXzoEyYGjTe+vXA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
        <style>
            * { box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
                margin: 0;
                padding: 16px;
                background: #fafafa;
                color: #333;
                line-height: 1.5;
            }

            .container {
                max-width: 600px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 2px 16px rgba(0,0,0,0.06);
            }

            .header {
                background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
                color: white;
                padding: 32px 24px;
                text-align: center;
                position: relative;
                overflow: visible;
            }

            .header-watermark {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-size: clamp(40px, 8vw, 80px);
                font-weight: 900;
                letter-spacing: 0.05em;
                color: rgba(255, 255, 255, 0.15);
                pointer-events: none;
                z-index: 1;
                white-space: nowrap;
                -webkit-mask-image: radial-gradient(circle 0px at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 100%);
                mask-image: radial-gradient(circle 0px at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 100%);
                transition: -webkit-mask-image 0.3s ease, mask-image 0.3s ease;
                user-select: none;
            }

            .save-buttons {
                position: absolute;
                top: 16px;
                right: 16px;
                display: flex;
                gap: 8px;
                z-index: 10;
            }

            .save-btn-group {
                position: relative;
                display: flex;
            }

            .save-btn {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 10px 18px;
                border-radius: 6px 0 0 6px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
                white-space: nowrap;
                min-height: 38px;
                border-right: none;
            }

            .save-btn:hover {
                background: rgba(255, 255, 255, 0.3);
            }

            .save-btn:active {
                transform: translateY(0);
            }

            .save-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }

            .save-dropdown-trigger {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 10px 10px;
                border-radius: 0 6px 6px 0;
                cursor: pointer;
                font-size: 11px;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
                min-height: 38px;
                display: flex;
                align-items: center;
            }

            .save-dropdown-trigger:hover {
                background: rgba(255, 255, 255, 0.35);
            }

            .save-dropdown-menu {
                position: absolute;
                top: 100%;
                right: 0;
                margin-top: 4px;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 10px;
                padding: 4px;
                min-width: 140px;
                opacity: 0;
                visibility: hidden;
                transform: translateY(-4px);
                transition: all 0.2s ease;
                box-shadow: 0 8px 24px rgba(0,0,0,0.12);
            }

            .save-btn-group:hover .save-dropdown-menu,
            .save-dropdown-menu:hover {
                opacity: 1;
                visibility: visible;
                transform: translateY(0);
            }

            .save-dropdown-item {
                display: block;
                width: 100%;
                padding: 9px 14px;
                background: none;
                border: none;
                color: #374151;
                font-size: 13px;
                cursor: pointer;
                border-radius: 6px;
                text-align: left;
                transition: background 0.15s;
                white-space: nowrap;
            }

            .save-dropdown-item:hover {
                background: #f3f4f6;
                color: #4f46e5;
            }

            .dropdown-icon {
                width: 14px;
                height: 14px;
                margin-right: 8px;
                vertical-align: -2px;
                flex-shrink: 0;
            }

            .header-title {
                font-size: 22px;
                font-weight: 700;
                margin: 0 0 20px 0;
                position: relative;
                z-index: 2;
            }

            .header-info {
                position: relative;
                z-index: 2;
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
                font-size: 14px;
                opacity: 0.95;
            }

            .info-item {
                text-align: center;
            }

            .info-label {
                display: block;
                font-size: 12px;
                opacity: 0.8;
                margin-bottom: 4px;
            }

            .info-value {
                font-weight: 600;
                font-size: 16px;
            }

            .content {
                padding: 24px;
            }

            .word-group {
                margin-bottom: 40px;
            }

            .word-group:first-child {
                margin-top: 0;
            }

            .word-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
                padding-bottom: 8px;
                border-bottom: 1px solid #f0f0f0;
            }

            .word-info {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .word-name {
                font-size: 17px;
                font-weight: 600;
                color: #1a1a1a;
            }

            .word-count {
                color: #666;
                font-size: 13px;
                font-weight: 500;
            }

            .word-count.hot { color: #dc2626; font-weight: 600; }
            .word-count.warm { color: #ea580c; font-weight: 600; }

            .word-index {
                color: #999;
                font-size: 12px;
            }

            .news-item {
                margin-bottom: 20px;
                padding: 16px 0;
                border-bottom: 1px solid #f5f5f5;
                position: relative;
                display: flex;
                gap: 12px;
                align-items: center;
            }

            .news-item:last-child {
                border-bottom: none;
            }

            .news-item.new::after {
                content: "NEW";
                position: absolute;
                top: 12px;
                right: 0;
                background: #fbbf24;
                color: #92400e;
                font-size: 9px;
                font-weight: 700;
                padding: 3px 6px;
                border-radius: 4px;
                letter-spacing: 0.5px;
            }

            .news-number {
                color: #999;
                font-size: 13px;
                font-weight: 600;
                min-width: 20px;
                text-align: center;
                flex-shrink: 0;
                background: #f8f9fa;
                border-radius: 50%;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                align-self: flex-start;
                margin-top: 8px;
                position: relative;
                cursor: pointer;
                transition: background 0.15s, color 0.15s;
            }
            .news-number .num-text { transition: opacity 0.15s; }
            .news-number .copy-icon {
                position: absolute;
                opacity: 0;
                transition: opacity 0.15s;
            }
            .news-item:hover .news-number .num-text { opacity: 0; }
            .news-item:hover .news-number .copy-icon { opacity: 1; }
            .news-item:hover .news-number {
                background: #eef2ff;
                color: #4f46e5;
            }
            .news-number.copied {
                background: #dcfce7 !important;
            }
            .news-number.copied .num-text { opacity: 0 !important; }
            .news-number.copied .copy-icon { opacity: 1 !important; }
            body.dark-mode .news-item:hover .news-number {
                background: #4338ca;
                color: #e0e7ff;
            }
            body.dark-mode .news-number.copied {
                background: #166534 !important;
            }

            .news-content {
                flex: 1;
                min-width: 0;
                padding-right: 40px;
            }

            .news-item.new .news-content {
                padding-right: 50px;
            }

            .news-header {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
                flex-wrap: wrap;
            }

            .source-name {
                color: #666;
                font-size: 12px;
                font-weight: 500;
            }

            .keyword-tag {
                color: #2563eb;
                font-size: 12px;
                font-weight: 500;
                background: #eff6ff;
                padding: 2px 6px;
                border-radius: 4px;
            }

            .rank-num {
                color: #fff;
                background: #6b7280;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 10px;
                min-width: 18px;
                text-align: center;
            }

            .rank-num.top { background: #dc2626; }
            .rank-num.high { background: #ea580c; }

            .trend-up, .trend-down {
                font-size: 12px;
                margin-left: 2px;
                vertical-align: middle;
            }

            .time-info {
                color: #999;
                font-size: 11px;
            }

            .count-info {
                color: #059669;
                font-size: 11px;
                font-weight: 500;
            }

            .news-title {
                font-size: 15px;
                line-height: 1.4;
                color: #1a1a1a;
                margin: 0;
            }

            .news-link {
                color: #2563eb;
                text-decoration: none;
            }

            .news-link:hover {
                text-decoration: underline;
            }

            .news-link:visited {
                color: #7c3aed;
            }

            /* Style générique de séparateur de zone */
            .section-divider {
                margin-top: 32px;
                padding-top: 24px;
                border-top: 2px solid #e5e7eb;
            }

            /* Style de la zone de statistiques des tendances */
            .hotlist-section {
                /* Pas de bordure par défaut, ajoutée dynamiquement par section-divider */
            }

            .new-section {
                margin-top: 40px;
                padding-top: 24px;
            }

            .new-section-title {
                color: #1a1a1a;
                font-size: 16px;
                font-weight: 600;
                margin: 0 0 20px 0;
            }

            .new-source-group {
                margin-bottom: 24px;
            }

            .new-source-title {
                color: #666;
                font-size: 13px;
                font-weight: 500;
                margin: 0 0 12px 0;
                padding-bottom: 6px;
                border-bottom: 1px solid #f5f5f5;
            }

            .new-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 8px 0;
                border-bottom: 1px solid #f9f9f9;
            }

            .new-item:last-child {
                border-bottom: none;
            }

            .new-item-number {
                color: #999;
                font-size: 12px;
                font-weight: 600;
                min-width: 18px;
                text-align: center;
                flex-shrink: 0;
                background: #f8f9fa;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .new-item-rank {
                color: #fff;
                background: #6b7280;
                font-size: 10px;
                font-weight: 700;
                padding: 3px 6px;
                border-radius: 8px;
                min-width: 20px;
                text-align: center;
                flex-shrink: 0;
            }

            .new-item-rank.top { background: #dc2626; }
            .new-item-rank.high { background: #ea580c; }

            .new-item-content {
                flex: 1;
                min-width: 0;
            }

            .new-item-title {
                font-size: 14px;
                line-height: 1.4;
                color: #1a1a1a;
                margin: 0;
            }

            .error-section {
                background: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 24px;
            }

            .error-title {
                color: #dc2626;
                font-size: 14px;
                font-weight: 600;
                margin: 0 0 8px 0;
            }

            .error-list {
                list-style: none;
                padding: 0;
                margin: 0;
            }

            .error-item {
                color: #991b1b;
                font-size: 13px;
                padding: 2px 0;
                font-family: 'SF Mono', Consolas, monospace;
            }

            .footer {
                margin-top: 32px;
                padding: 20px 24px;
                background: #f8f9fa;
                border-top: 1px solid #e5e7eb;
                text-align: center;
            }

            .footer-content {
                font-size: 13px;
                color: #6b7280;
                line-height: 1.6;
            }

            .footer-link {
                color: #4f46e5;
                text-decoration: none;
                font-weight: 500;
                transition: color 0.2s ease;
            }

            .footer-link:hover {
                color: #7c3aed;
                text-decoration: underline;
            }

            .project-name {
                font-weight: 600;
                color: #374151;
            }

            @media (max-width: 480px) {
                body { padding: 12px; }
                .header { padding: 24px 20px; }
                .content { padding: 20px; }
                .footer { padding: 16px 20px; }
                .header-info { grid-template-columns: 1fr; gap: 12px; }
                .news-header { gap: 6px; }
                .news-content { padding-right: 45px; }
                .news-item { gap: 8px; }
                .new-item { gap: 8px; }
                .news-number { width: 20px; height: 20px; font-size: 12px; }
                .save-buttons {
                    position: static;
                    margin-bottom: 16px;
                    display: flex;
                    gap: 8px;
                    justify-content: center;
                    width: 100%;
                }
                .save-btn-group {
                    flex: 1;
                }
                .save-btn {
                    width: 100%;
                    border-radius: 6px 0 0 6px;
                }
            }

            /* Style du contenu des abonnements RSS */
            .rss-section {
                margin-top: 32px;
                padding-top: 24px;
            }

            .rss-section-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
            }

            .rss-section-title {
                font-size: 18px;
                font-weight: 600;
                color: #059669;
            }

            .rss-section-count {
                color: #6b7280;
                font-size: 14px;
            }

            .feed-group {
                margin-bottom: 24px;
            }

            .feed-group:last-child {
                margin-bottom: 0;
            }

            .feed-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
                padding-bottom: 8px;
                border-bottom: 2px solid #10b981;
            }

            .feed-name {
                font-size: 15px;
                font-weight: 600;
                color: #059669;
            }

            .feed-count {
                color: #666;
                font-size: 13px;
                font-weight: 500;
            }

            .rss-item {
                margin-bottom: 12px;
                padding: 14px;
                background: #f0fdf4;
                border-radius: 8px;
                border-left: 3px solid #10b981;
            }

            .rss-item:last-child {
                margin-bottom: 0;
            }

            .rss-meta {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 6px;
                flex-wrap: wrap;
            }

            .rss-time {
                color: #6b7280;
                font-size: 12px;
            }

            .rss-author {
                color: #059669;
                font-size: 12px;
                font-weight: 500;
            }

            .rss-title {
                font-size: 14px;
                line-height: 1.5;
                margin-bottom: 6px;
            }

            .rss-link {
                color: #1f2937;
                text-decoration: none;
                font-weight: 500;
            }

            .rss-link:hover {
                color: #059669;
                text-decoration: underline;
            }

            .rss-summary {
                font-size: 13px;
                color: #6b7280;
                line-height: 1.5;
                margin: 0;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }

            /* Style de la zone d'affichage autonome - réutilise le style de la zone de statistiques de mots-clés */
            .standalone-section {
                margin-top: 32px;
                padding-top: 24px;
            }

            .standalone-section-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
            }

            .standalone-section-title {
                font-size: 18px;
                font-weight: 600;
                color: #059669;
            }

            .standalone-section-count {
                color: #6b7280;
                font-size: 14px;
            }

            .standalone-group {
                margin-bottom: 40px;
            }

            .standalone-group:last-child {
                margin-bottom: 0;
            }

            .standalone-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
                padding-bottom: 8px;
                border-bottom: 1px solid #f0f0f0;
            }

            .standalone-name {
                font-size: 17px;
                font-weight: 600;
                color: #1a1a1a;
            }

            .standalone-count {
                color: #666;
                font-size: 13px;
                font-weight: 500;
            }

            /* Style des blocs d'analyse IA */
            .ai-section {
                margin-top: 32px;
                padding: 24px;
                background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                border-radius: 12px;
                border: 1px solid #bae6fd;
            }

            .ai-section-header {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 20px;
            }

            .ai-section-title {
                font-size: 18px;
                font-weight: 600;
                color: #0369a1;
            }

            .ai-section-badge {
                background: #0ea5e9;
                color: white;
                font-size: 11px;
                font-weight: 600;
                padding: 3px 8px;
                border-radius: 4px;
            }

            .ai-block {
                margin-bottom: 16px;
                padding: 16px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }

            .ai-block:last-child {
                margin-bottom: 0;
            }

            .ai-block-title {
                font-size: 14px;
                font-weight: 600;
                color: #0369a1;
                margin-bottom: 8px;
            }

            .ai-block-content {
                font-size: 14px;
                line-height: 1.6;
                color: #334155;
                white-space: pre-wrap;
            }

            .ai-error {
                padding: 16px;
                background: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 8px;
                color: #991b1b;
                font-size: 14px;
            }

            .ai-warning {
                padding: 16px;
                background: #fffbeb;
                border: 1px solid #fde68a;
                border-radius: 8px;
                color: #92400e;
                font-size: 14px;
            }

            .ai-info {
                padding: 16px;
                background: #f0f9ff;
                border: 1px solid #bae6fd;
                border-radius: 8px;
                color: #0369a1;
                font-size: 14px;
            }

            /* ===== Styles d'amélioration navigateur (progressifs, sans effet sur les clients e-mail) ===== */

            /* Mode plein écran - base */
            body.wide-mode .container { max-width: 1200px; }
            body.wide-mode .header-info { grid-template-columns: repeat(4, 1fr); }
            body.wide-mode .content { padding: 32px 40px; }

            /* Mode plein écran - feed-group RSS en deux colonnes */
            body.wide-mode .rss-feeds-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
            }
            body.wide-mode .feed-group { margin-bottom: 0; }

            /* Mode plein écran - grille deux colonnes pour la zone d'analyse IA */
            body.wide-mode .ai-section .ai-blocks-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
            }
            body.wide-mode .ai-block { margin-bottom: 0; }

            /* Mode plein écran - nouvelles tendances multi-colonnes */
            body.wide-mode .new-section .new-sources-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
            }
            body.wide-mode .new-source-group { margin-bottom: 0; }

            /* Mode plein écran - zone d'affichage autonome multi-colonnes */
            body.wide-mode .standalone-section .standalone-groups-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
            }
            body.wide-mode .standalone-group { margin-bottom: 0; }

            /* Barre d'onglets */
            .tab-bar-wrapper {
                position: sticky;
                top: 0;
                z-index: 10;
                background: white;
                display: none;
                margin-bottom: 20px;
                align-items: stretch;
                border-bottom: 2px solid #e5e7eb;
            }
            body.wide-mode .tab-bar-wrapper { display: flex; }
            body.wide-mode .tab-bar-wrapper.tab-hidden { display: none; }

            .tab-bar {
                flex: 1;
                min-width: 0;
                display: flex;
                overflow-x: auto;
                white-space: nowrap;
                padding: 8px 0 12px 0;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: none;
                -ms-overflow-style: none;
                gap: 4px;
                mask-image: linear-gradient(to right, transparent, black 24px, black calc(100% - 24px), transparent);
                -webkit-mask-image: linear-gradient(to right, transparent, black 24px, black calc(100% - 24px), transparent);
            }
            .tab-bar::-webkit-scrollbar { display: none; }
            .tab-bar.scroll-start {
                mask-image: linear-gradient(to right, black, black calc(100% - 24px), transparent);
                -webkit-mask-image: linear-gradient(to right, black, black calc(100% - 24px), transparent);
            }
            .tab-bar.scroll-end {
                mask-image: linear-gradient(to right, transparent, black 24px, black);
                -webkit-mask-image: linear-gradient(to right, transparent, black 24px, black);
            }
            .tab-bar.scroll-start.scroll-end,
            .tab-bar.no-overflow {
                mask-image: none;
                -webkit-mask-image: none;
            }

            .tab-arrow {
                flex-shrink: 0;
                width: 28px;
                display: none;
                align-items: center;
                justify-content: center;
                background: none;
                border: none;
                color: #9ca3af;
                font-size: 20px;
                font-weight: 300;
                cursor: pointer;
                padding: 0;
                transition: color 0.15s ease;
            }
            .tab-arrow:hover { color: #4f46e5; }
            .tab-arrow.visible { display: flex; }

            .tab-scroll-indicator {
                position: absolute;
                bottom: 0;
                left: 0;
                width: 0;
                height: 2px;
                background: #4f46e5;
                border-radius: 0 1px 1px 0;
                transition: width 0.1s linear;
            }

            .tab-btn {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 8px 16px;
                border: none;
                background: #f3f4f6;
                color: #6b7280;
                border-radius: 8px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                white-space: nowrap;
                transition: all 0.2s ease;
                flex-shrink: 0;
            }
            .tab-btn:hover { background: #e5e7eb; color: #374151; }
            .tab-btn.active { background: #4f46e5; color: white; }
            .tab-count {
                font-size: 11px;
                background: rgba(0,0,0,0.1);
                padding: 1px 6px;
                border-radius: 10px;
            }
            .tab-btn.active .tab-count { background: rgba(255,255,255,0.3); }

            /* Barre de recherche */
            .search-bar { display: none; padding: 0 0 16px 0; }
            .search-input {
                width: 100%;
                padding: 10px 16px;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                font-size: 14px;
                outline: none;
                transition: border-color 0.2s;
                box-sizing: border-box;
            }
            .search-input:focus { border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79,70,229,0.1); }
            .search-input::placeholder { color: #9ca3af; }

            /* Barre d'outils flottante en bas à droite */
            .fab-bar {
                position: fixed;
                bottom: 24px;
                right: 24px;
                display: flex;
                flex-direction: column;
                gap: 8px;
                z-index: 100;
                opacity: 0;
                transform: translateY(10px);
                transition: opacity 0.3s, transform 0.3s;
                pointer-events: none;
            }
            .fab-bar.visible {
                opacity: 1;
                transform: translateY(0);
                pointer-events: auto;
            }
            .fab-btn {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: #4f46e5;
                color: white;
                border: none;
                cursor: pointer;
                font-size: 16px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                transition: transform 0.2s, background 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
                position: relative;
            }
            .fab-btn:hover { transform: scale(1.1); background: #4338ca; }
            body.dark-mode .fab-btn { background: #533483; }
            body.dark-mode .fab-btn:hover { background: #6d28d9; }

            /* Infobulle de raccourcis clavier */
            .fab-tooltip {
                position: absolute;
                bottom: 0;
                right: 52px;
                background: rgba(30, 30, 50, 0.92);
                backdrop-filter: blur(12px);
                color: white;
                border-radius: 10px;
                padding: 12px 16px;
                white-space: nowrap;
                font-size: 12px;
                line-height: 1.8;
                box-shadow: 0 8px 24px rgba(0,0,0,0.25);
                border: 1px solid rgba(255,255,255,0.1);
                opacity: 0;
                visibility: hidden;
                transform: translateY(6px);
                transition: all 0.2s ease;
                pointer-events: none;
            }
            .fab-btn:hover .fab-tooltip,
            .fab-btn.show-tip .fab-tooltip {
                opacity: 1;
                visibility: visible;
                transform: translateY(0);
                pointer-events: auto;
            }
            .fab-tooltip .tip-row {
                display: flex;
                justify-content: space-between;
                gap: 16px;
                align-items: center;
            }
            .fab-tooltip .tip-key {
                background: rgba(255,255,255,0.15);
                border-radius: 3px;
                padding: 1px 6px;
                font-family: monospace;
                font-size: 11px;
                margin-left: 8px;
            }

            /* Repli / dépli */
            .collapse-icon {
                display: none;
                margin-right: 6px;
                font-size: 12px;
                color: #9ca3af;
                transition: transform 0.2s;
                user-select: none;
            }
            .word-header.collapsible { cursor: pointer; }
            .word-header.collapsible .collapse-icon { display: inline; }
            .word-header.collapsible:hover {
                background: #f9fafb;
                border-radius: 6px;
                margin: 0 -8px 20px -8px;
                padding: 8px;
            }
            .word-group.collapsed .news-item { display: none; }
            .word-group.collapsed .collapse-icon { transform: rotate(-90deg); }

            /* Animation de changement d'onglet */
            body.wide-mode .word-group[data-tab-index] { animation: tabFadeIn 0.2s ease; }
            @keyframes tabFadeIn {
                from { opacity: 0; transform: translateY(8px); }
                to { opacity: 1; transform: translateY(0); }
            }

            /* Bouton de bascule plein écran */
            .toggle-wide-btn {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 10px 14px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 15px;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
                line-height: 1;
                min-height: 38px;
            }
            .toggle-wide-btn:hover {
                background: rgba(255, 255, 255, 0.3);
                border-color: rgba(255, 255, 255, 0.5);
                transform: translateY(-1px);
            }

            /* ===== Mode sombre ===== */
            body.dark-mode {
                background: #0f172a;
                color: #e2e8f0;
            }
            body.dark-mode .container {
                background: #1e293b;
                box-shadow: 0 4px 24px rgba(0,0,0,0.4);
            }
            body.dark-mode .header {
                background: linear-gradient(135deg, #3730a3 0%, #7c3aed 100%);
            }
            body.dark-mode .content {
                background: #1e293b;
            }

            /* Couleur du texte */
            body.dark-mode .word-name,
            body.dark-mode .new-section-title,
            body.dark-mode .standalone-name,
            body.dark-mode .new-item-title,
            body.dark-mode .project-name { color: #f1f5f9; }
            body.dark-mode .word-count,
            body.dark-mode .word-index,
            body.dark-mode .source-name,
            body.dark-mode .time-info,
            body.dark-mode .feed-count,
            body.dark-mode .new-source-title,
            body.dark-mode .standalone-count,
            body.dark-mode .rss-section-count,
            body.dark-mode .standalone-section-count,
            body.dark-mode .news-meta,
            body.dark-mode .rss-time,
            body.dark-mode .rss-author,
            body.dark-mode .rss-summary { color: #94a3b8; }
            body.dark-mode .info-value { color: white; }

            /* Liens */
            body.dark-mode .news-title a,
            body.dark-mode .rss-title a,
            body.dark-mode .new-item a,
            body.dark-mode .standalone-item a,
            body.dark-mode .rss-link { color: #93c5fd; }
            body.dark-mode .news-title a:visited { color: #c4b5fd; }
            body.dark-mode .rss-link:hover { color: #6ee7b7; }

            /* Couleur d'accentuation */
            body.dark-mode .keyword-tag {
                background: rgba(99,102,241,0.15);
                color: #a5b4fc;
            }
            body.dark-mode .count-info { color: #6ee7b7; }
            body.dark-mode .rss-source,
            body.dark-mode .feed-name,
            body.dark-mode .rss-section-title,
            body.dark-mode .standalone-section-title { color: #6ee7b7; }

            /* Bordures et séparateurs */
            body.dark-mode .word-header,
            body.dark-mode .news-item,
            body.dark-mode .new-item,
            body.dark-mode .standalone-item,
            body.dark-mode .new-source-title,
            body.dark-mode .standalone-header { border-bottom-color: #334155; }
            body.dark-mode .section-divider { border-top-color: #334155; }
            body.dark-mode .feed-header { border-bottom-color: #166534; }
            body.dark-mode .tab-bar { border-bottom-color: #334155; }

            /* Cercle de numérotation */
            body.dark-mode .news-number,
            body.dark-mode .new-item-number {
                background: #334155;
                color: #94a3b8;
            }

            /* Repli au survol */
            body.dark-mode .word-header.collapsible:hover { background: #253347; }

            /* Barre d'onglets */
            body.dark-mode .tab-bar-wrapper {
                background: #1e293b;
                border-bottom-color: #334155;
            }
            body.dark-mode .tab-arrow { color: #64748b; }
            body.dark-mode .tab-arrow:hover { color: #c4b5fd; }
            body.dark-mode .tab-scroll-indicator { background: #818cf8; }
            body.dark-mode .tab-btn {
                background: #334155;
                color: #94a3b8;
            }
            body.dark-mode .tab-btn:hover {
                background: #475569;
                color: #e2e8f0;
            }
            body.dark-mode .tab-btn.active {
                background: #6d28d9;
                color: white;
            }
            body.dark-mode .tab-bar::-webkit-scrollbar-track { background: #1e293b; }
            body.dark-mode .tab-bar::-webkit-scrollbar-thumb { background: #475569; }

            /* Champ de recherche */
            body.dark-mode .search-input {
                background: #1e293b;
                border-color: #334155;
                color: #e2e8f0;
            }
            body.dark-mode .search-input:focus {
                border-color: #818cf8;
                box-shadow: 0 0 0 3px rgba(129,140,248,0.15);
            }
            body.dark-mode .search-input::placeholder { color: #64748b; }

            /* Carte RSS */
            body.dark-mode .rss-item {
                background: #1a2e25;
                border-left-color: #059669;
            }

            /* Zone d'analyse IA */
            body.dark-mode .ai-section {
                background: linear-gradient(135deg, #1e1b4b 0%, #1e293b 100%);
                border-color: #334155;
            }
            body.dark-mode .ai-section-title { color: #a5b4fc; }
            body.dark-mode .ai-section-badge { background: #4f46e5; }
            body.dark-mode .ai-block {
                background: #1e293b;
                border-color: #334155;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
            }
            body.dark-mode .ai-block-title { color: #a5b4fc; }
            body.dark-mode .ai-block-content { color: #cbd5e1; }
            body.dark-mode .ai-warning {
                background: #422006;
                border-color: #854d0e;
                color: #fbbf24;
            }
            body.dark-mode .ai-error {
                background: #450a0a;
                border-color: #991b1b;
                color: #fca5a5;
            }
            body.dark-mode .ai-info {
                background: #172554;
                border-color: #1e40af;
                color: #93c5fd;
            }

            /* Zone d'erreur */
            body.dark-mode .error-section {
                background: #1c1917;
                border-color: #78350f;
            }
            body.dark-mode .error-title { color: #fca5a5; }
            body.dark-mode .error-item { color: #f87171; }

            /* Footer */
            body.dark-mode .footer {
                background: #0f172a;
                border-top-color: #334155;
                color: #94a3b8;
            }
            body.dark-mode .footer-link { color: #93c5fd; }
            body.dark-mode .footer-link:hover { color: #c4b5fd; }

            /* Bouton flottant */
            body.dark-mode .fab-btn { background: #6d28d9; }
            body.dark-mode .fab-btn:hover { background: #7c3aed; }

            /* Menu déroulant */
            body.dark-mode .save-dropdown-menu {
                background: rgba(30,41,59,0.95);
                border-color: #475569;
                box-shadow: 0 8px 24px rgba(0,0,0,0.4);
            }
            body.dark-mode .save-dropdown-item {
                color: #e2e8f0;
            }
            body.dark-mode .save-dropdown-item:hover {
                background: #334155;
                color: #c4b5fd;
            }

            /* Bouton de bascule mode sombre */
            .toggle-dark-btn {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 10px 14px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 15px;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
                line-height: 1;
                min-height: 38px;
            }
            .toggle-dark-btn:hover {
                background: rgba(255, 255, 255, 0.3);
                border-color: rgba(255, 255, 255, 0.5);
                transform: translateY(-1px);
            }

            /* Le panneau de raccourcis est intégré dans fab-tooltip */

            /* Barre de progression de lecture */
            .reading-progress {
                position: fixed;
                top: 0; left: 0;
                width: 0;
                height: 3px;
                background: linear-gradient(90deg, #4f46e5, #7c3aed);
                z-index: 9999;
                transition: width 0.1s linear;
            }
            body.dark-mode .reading-progress {
                background: linear-gradient(90deg, #8ab4f8, #c58af9);
            }

            /* Le style du bouton de copie est intégré dans .news-number */



            /* Marqueur de nouvelle entrée */
            .badge-new {
                display: inline-block;
                background: linear-gradient(135deg, #f43f5e, #ec4899);
                color: white;
                font-size: 10px;
                font-weight: 600;
                padding: 1px 6px;
                border-radius: 3px;
                margin-left: 6px;
                vertical-align: middle;
                letter-spacing: 0.5px;
            }
            body.dark-mode .badge-new {
                background: linear-gradient(135deg, #be185d, #9333ea);
            }
        </style>
    </head>
    <body>"""

    html += f"""
        <div class="reading-progress"></div>
        <div class="container">
            <div class="header">
                <div class="header-watermark">TrendRadar</div>
                <div class="save-buttons">
                    <button class="toggle-wide-btn" onclick="toggleWideMode()" title="{t("toggle_wide", language)}">⛶</button>
                    <button class="toggle-dark-btn" onclick="toggleDarkMode()" title="{t("toggle_dark", language)}">☽</button>
                    <div class="save-btn-group">
                        <button class="save-btn" onclick="saveAsImage(event)">{t("export", language)}</button>
                        <button class="save-dropdown-trigger">▾</button>
                        <div class="save-dropdown-menu">
                            <button class="save-dropdown-item" onclick="saveAsImage(event)"><svg class="dropdown-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="12" height="12" rx="2"/><circle cx="8" cy="7.5" r="2.5"/><path d="M12 4h.01"/></svg>{t("export_full_screenshot", language)}</button>
                            <button class="save-dropdown-item" onclick="saveAsMultipleImages(event)"><svg class="dropdown-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1" y="4" width="10" height="10" rx="1.5"/><path d="M5 4V2.5A1.5 1.5 0 016.5 1h7A1.5 1.5 0 0115 2.5v7a1.5 1.5 0 01-1.5 1.5H12"/></svg>{t("export_segmented_screenshot", language)}</button>
                            <button class="save-dropdown-item" onclick="saveAsMarkdown()"><svg class="dropdown-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2.5 2h11A1.5 1.5 0 0115 3.5v9a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 011 12.5v-9A1.5 1.5 0 012.5 2z"/><path d="M4 11V5l2.5 3L9 5v6"/><path d="M11.5 8v3m0 0l-1.5-2m1.5 2l1.5-2"/></svg>{t("export_markdown", language)}</button>
                        </div>
                    </div>
                </div>
                <div class="header-title">{t("report_title", language)}</div>
                <div class="header-info">"""

    # Utilise la fonction de temps fournie ou datetime.now par défaut
    if get_time_func:
        now = get_time_func()
    else:
        now = datetime.now()

    # Affichage du type de rapport
    if mode == "current":
        mode_display = t("mode_current", language)
    elif mode == "incremental":
        mode_display = t("mode_incremental", language)
    else:
        mode_display = t("mode_daily", language)

    # Calcul des différentes données
    hot_news_count = sum(len(stat["titles"]) for stat in report_data["stats"])
    new_count = report_data.get("total_new_count", 0)

    # Récupère les informations RSS et plateforme depuis les métadonnées
    hotlist_total = report_data.get("hotlist_total", total_titles)
    platform_total = report_data.get("platform_total", 0)
    failed_count = len(report_data.get("failed_ids", []))
    platform_success = platform_total - failed_count if platform_total else 0
    rss_matched = report_data.get("rss_matched_count", 0)
    rss_total = report_data.get("rss_total_count", 0)
    rss_source_total = report_data.get("rss_source_total", 0)
    rss_source_failed = report_data.get("rss_source_failed", 0)
    rss_source_success = max(0, rss_source_total - rss_source_failed)

    # 1. Type de rapport
    html += f"""
                    <div class="info-item">
                        <span class="info-label">{t("info_report_type", language)}</span>
                        <span class="info-value">{mode_display}</span>
                    </div>"""

    # 2. Heure de génération
    html += f"""
                    <div class="info-item">
                        <span class="info-label">{t("info_generated_at", language)}</span>
                        <span class="info-value">{now.strftime("%m-%d %H:%M")}</span>
                    </div>"""

    # 3. Tendances retenues
    html += f"""
                    <div class="info-item">
                        <span class="info-label">{t("info_hotlist_hits", language)}</span>
                        <span class="info-value">{hot_news_count} / {hotlist_total}</span>
                    </div>"""

    # 4. RSS retenus
    if rss_source_total > 0:
        rss_value = f"{rss_matched} / {rss_total}"
    else:
        rss_value = t("not_enabled", language)
    html += f"""
                    <div class="info-item">
                        <span class="info-label">{t("info_rss_hits", language)}</span>
                        <span class="info-value">{rss_value}</span>
                    </div>"""

    # 5. Plateformes de tendances
    if platform_total > 0:
        platform_value = f"{platform_success}/{platform_total}"
    else:
        platform_value = "--"
    html += f"""
                    <div class="info-item">
                        <span class="info-label">{t("info_hotlist_platforms", language)}</span>
                        <span class="info-value">{platform_value}</span>
                    </div>"""

    # 6. Sources RSS
    if rss_source_total > 0:
        rss_source_value = f"{rss_source_success}/{rss_source_total}"
    else:
        rss_source_value = "--"
    html += f"""
                    <div class="info-item">
                        <span class="info-label">{t("info_rss_sources", language)}</span>
                        <span class="info-value">{rss_source_value}</span>
                    </div>"""

    # 7. Nouvelles tendances (nouveautés tendances + nouveautés RSS)
    rss_new_count = sum(len(stat.get("titles", [])) for stat in (rss_new_items or []))
    total_new = new_count + rss_new_count
    new_value = f"{new_count} + {rss_new_count}" if total_new > 0 else "0"
    html += f"""
                    <div class="info-item">
                        <span class="info-label">{t("info_new_hotspots", language)}</span>
                        <span class="info-value">{new_value}</span>
                    </div>"""

    # 8. Analyse IA
    if ai_analysis and getattr(ai_analysis, "success", False):
        hotlist_analyzed = getattr(ai_analysis, "hotlist_analyzed", 0)
        rss_analyzed = getattr(ai_analysis, "rss_analyzed", 0)
        standalone_analyzed = getattr(ai_analysis, "standalone_analyzed", 0)
        ai_include_rss = getattr(ai_analysis, "include_rss", True)
        ai_include_standalone = getattr(ai_analysis, "include_standalone", False)

        ai_parts = [str(hotlist_analyzed)]
        if ai_include_rss:
            ai_parts.append(str(rss_analyzed))
        if ai_include_standalone:
            ai_parts.append(str(standalone_analyzed))
        ai_value = " + ".join(ai_parts) if sum(int(p) for p in ai_parts) > 0 else "0"
    elif ai_analysis:
        if getattr(ai_analysis, "skipped", False):
            ai_value = t("skipped", language)
        else:
            ai_value = t("to_configure", language)
    else:
        ai_value = t("not_enabled", language)
    html += f"""
                    <div class="info-item">
                        <span class="info-label">{t("info_ai_analysis", language)}</span>
                        <span class="info-value">{ai_value}</span>
                    </div>"""

    html += f"""
                </div>
            </div>

            <div class="content">
                <div class="search-bar">
                    <input type="text" class="search-input" placeholder="{t("search_placeholder", language)}" oninput="handleSearch(this.value)">
                </div>"""

    # Traite les erreurs des IDs en échec
    if report_data["failed_ids"]:
        html += f"""
                <div class="error-section">
                    <div class="error-title">{t("failed_platforms", language)}</div>
                    <ul class="error-list">"""
        for id_value in report_data["failed_ids"]:
            html += f'<li class="error-item">{html_escape(id_value)}</li>'
        html += """
                    </ul>
                </div>"""

    # Génère le HTML de la section des statistiques de mots-clés
    stats_html = ""
    tab_bar_html = ""
    if report_data["stats"]:
        total_count = len(report_data["stats"])

        # Génère le HTML de la barre d'onglets
        total_news_count = sum(s["count"] for s in report_data["stats"])
        tab_bar_html = '<div class="tab-bar-wrapper"><div class="tab-bar">'
        tab_bar_html += f'<button class="tab-btn" data-tab-index="all">{t("tab_all", language)}<span class="tab-count">{total_news_count}</span></button>'
        for tab_i, tab_stat in enumerate(report_data["stats"]):
            escaped_tab_word = html_escape(tab_stat["word"])
            tab_count = tab_stat["count"]
            tab_bar_html += f'<button class="tab-btn" data-tab-index="{tab_i}">{escaped_tab_word}<span class="tab-count">{tab_count}</span></button>'
        tab_bar_html += '</div></div>'

        for i, stat in enumerate(report_data["stats"], 1):
            count = stat["count"]

            # Détermine le niveau de popularité
            if count >= 10:
                count_class = "hot"
            elif count >= 5:
                count_class = "warm"
            else:
                count_class = ""

            escaped_word = html_escape(stat["word"])

            stats_html += f"""
                <div class="word-group" data-tab-index="{i - 1}">
                    <div class="word-header">
                        <div class="word-info">
                            <div class="word-name">{escaped_word}</div>
                            <div class="word-count {count_class}">{count} {t("count_unit", language)}</div>
                        </div>
                        <div class="word-index"><span class="collapse-icon">▼</span>{i}/{total_count}</div>
                    </div>"""

            # Traite les titres d'actualités de chaque groupe et les numérote
            for j, title_data in enumerate(stat["titles"], 1):
                is_new = title_data.get("is_new", False)
                new_class = "new" if is_new else ""

                stats_html += f"""
                    <div class="news-item {new_class}">
                        <div class="news-number">{j}</div>
                        <div class="news-content">
                            <div class="news-header">"""

                # Selon display_mode, affiche la source ou le mot-clé
                if display_mode == "keyword":
                    # mode keyword : affiche la source
                    stats_html += f'<span class="source-name">{html_escape(title_data["source_name"])}</span>'
                else:
                    # mode platform : affiche le mot-clé
                    matched_keyword = title_data.get("matched_keyword", "")
                    if matched_keyword:
                        stats_html += f'<span class="keyword-tag">[{html_escape(matched_keyword)}]</span>'

                # Traite l'affichage du classement
                ranks = title_data.get("ranks", [])
                if ranks:
                    min_rank = min(ranks)
                    max_rank = max(ranks)
                    rank_threshold = title_data.get("rank_threshold", 10)

                    # Détermine le niveau de classement
                    if min_rank <= 3:
                        rank_class = "top"
                    elif min_rank <= rank_threshold:
                        rank_class = "high"
                    else:
                        rank_class = ""

                    if min_rank == max_rank:
                        rank_text = str(min_rank)
                    else:
                        rank_text = f"{min_rank}-{max_rank}"

                    # Calcule la flèche de tendance
                    rank_timeline = title_data.get("rank_timeline", [])
                    trend = calculate_rank_trend(rank_timeline, ranks)
                    trend_html = ""
                    if trend == "up":
                        trend_html = '<span class="trend-up">📈</span>'
                    elif trend == "down":
                        trend_html = '<span class="trend-down">📉</span>'

                    stats_html += f'<span class="rank-num {rank_class}">{rank_text}</span>{trend_html}'

                # Traite l'affichage du temps
                time_display = title_data.get("time_display", "")
                if time_display:
                    # Simplifie le format d'affichage du temps, remplace le tilde par ~
                    simplified_time = (
                        time_display.replace(" ~ ", "~")
                        .replace("[", "")
                        .replace("]", "")
                    )
                    stats_html += (
                        f'<span class="time-info">{html_escape(simplified_time)}</span>'
                    )

                # Traite le nombre d'occurrences
                count_info = title_data.get("count", 1)
                if count_info > 1:
                    stats_html += f'<span class="count-info">{count_info}{t("occurrence_unit", language)}</span>'

                stats_html += """
                            </div>
                            <div class="news-title">"""

                # Traite le titre et le lien
                escaped_title = html_escape(title_data["title"])
                link_url = title_data.get("mobile_url") or title_data.get("url", "")

                if link_url:
                    escaped_url = html_escape(link_url)
                    stats_html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    stats_html += escaped_title

                stats_html += """
                            </div>
                        </div>
                    </div>"""

            stats_html += """
                </div>"""

    # Ajoute l'enveloppe externe aux statistiques de tendances
    if stats_html:
        stats_html = f"""
                <div class="hotlist-section">{tab_bar_html}{stats_html}
                </div>"""

    # Génère le HTML de la zone des nouvelles actualités
    new_titles_html = ""
    if show_new_section and report_data["new_titles"]:
        new_titles_html += f"""
                <div class="new-section">
                    <div class="new-section-title">{t("new_hotspots_title", language).format(count=report_data['total_new_count'])}</div>
                    <div class="new-sources-grid">"""

        for source_data in report_data["new_titles"]:
            escaped_source = html_escape(source_data["source_name"])
            titles_count = len(source_data["titles"])

            new_titles_html += f"""
                    <div class="new-source-group">
                        <div class="new-source-title">{escaped_source} · {titles_count} {t("count_unit", language)}</div>"""

            # Numérote également les nouvelles actualités
            for idx, title_data in enumerate(source_data["titles"], 1):
                ranks = title_data.get("ranks", [])

                # Traite l'affichage du classement des nouvelles actualités
                rank_class = ""
                if ranks:
                    min_rank = min(ranks)
                    if min_rank <= 3:
                        rank_class = "top"
                    elif min_rank <= title_data.get("rank_threshold", 10):
                        rank_class = "high"

                    if len(ranks) == 1:
                        rank_text = str(ranks[0])
                    else:
                        rank_text = f"{min(ranks)}-{max(ranks)}"
                else:
                    rank_text = "?"

                new_titles_html += f"""
                        <div class="new-item">
                            <div class="new-item-number">{idx}</div>
                            <div class="new-item-rank {rank_class}">{rank_text}</div>
                            <div class="new-item-content">
                                <div class="new-item-title">"""

                # Traite le lien des nouvelles actualités
                escaped_title = html_escape(title_data["title"])
                link_url = title_data.get("mobile_url") or title_data.get("url", "")

                if link_url:
                    escaped_url = html_escape(link_url)
                    new_titles_html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    new_titles_html += escaped_title

                new_titles_html += """
                                </div>
                            </div>
                        </div>"""

            new_titles_html += """
                    </div>"""

        new_titles_html += """
                    </div>
                </div>"""

    # Génère le contenu des statistiques RSS
    def render_rss_stats_html(stats: List[Dict], title: Optional[str] = None) -> str:
        """Rend le bloc HTML des statistiques RSS.

        Args:
            stats: liste des statistiques RSS groupées, même format que les tendances :
                [
                    {
                        "word": "mot-clé",
                        "count": 5,
                        "titles": [
                            {
                                "title": "titre",
                                "source_name": "nom du flux",
                                "time_display": "12-29 08:20",
                                "url": "...",
                                "is_new": True/False
                            }
                        ]
                    }
                ]
            title: titre du bloc

        Returns:
            chaîne HTML rendue
        """
        if title is None:
            title = t("rss_subscription_update", language)
        if not stats:
            return ""

        # Calcule le nombre total d'entrées
        total_count = sum(stat.get("count", 0) for stat in stats)
        if total_count == 0:
            return ""

        rss_html = f"""
                <div class="rss-section">
                    <div class="rss-section-header">
                        <div class="rss-section-title">{title}</div>
                        <div class="rss-section-count">{total_count} {t("count_unit", language)}</div>
                    </div>
                    <div class="rss-feeds-grid">"""

        # Rend par groupe de mots-clés (même format que les tendances)
        for stat in stats:
            keyword = stat.get("word", "")
            titles = stat.get("titles", [])
            if not titles:
                continue

            keyword_count = len(titles)

            rss_html += f"""
                    <div class="feed-group">
                        <div class="feed-header">
                            <div class="feed-name">{html_escape(keyword)}</div>
                            <div class="feed-count">{keyword_count} {t("count_unit", language)}</div>
                        </div>"""

            for title_data in titles:
                item_title = title_data.get("title", "")
                url = title_data.get("url", "")
                time_display = title_data.get("time_display", "")
                source_name = title_data.get("source_name", "")
                is_new = title_data.get("is_new", False)

                rss_html += """
                        <div class="rss-item">
                            <div class="rss-meta">"""

                if time_display:
                    rss_html += f'<span class="rss-time">{html_escape(time_display)}</span>'

                if source_name:
                    rss_html += f'<span class="rss-author">{html_escape(source_name)}</span>'

                if is_new:
                    rss_html += '<span class="rss-author" style="color: #dc2626;">NEW</span>'

                rss_html += """
                            </div>
                            <div class="rss-title">"""

                escaped_title = html_escape(item_title)
                if url:
                    escaped_url = html_escape(url)
                    rss_html += f'<a href="{escaped_url}" target="_blank" class="rss-link">{escaped_title}</a>'
                else:
                    rss_html += escaped_title

                rss_html += """
                            </div>
                        </div>"""

            rss_html += """
                    </div>"""

        rss_html += """
                    </div>
                </div>"""
        return rss_html

    # Génère le contenu de la zone d'affichage autonome
    def render_standalone_html(data: Optional[Dict]) -> str:
        """Rend le HTML de la zone d'affichage autonome (réutilise le style de la zone de statistiques de mots-clés).

        Args:
            data: données d'affichage autonome, format :
                {
                    "platforms": [
                        {
                            "id": "zhihu",
                            "name": "Classement Zhihu",
                            "items": [
                                {
                                    "title": "titre",
                                    "url": "lien",
                                    "rank": 1,
                                    "ranks": [1, 2, 1],
                                    "first_time": "08:00",
                                    "last_time": "12:30",
                                    "count": 3,
                                }
                            ]
                        }
                    ],
                    "rss_feeds": [
                        {
                            "id": "hacker-news",
                            "name": "Hacker News",
                            "items": [
                                {
                                    "title": "titre",
                                    "url": "lien",
                                    "published_at": "2025-01-07T08:00:00",
                                    "author": "auteur",
                                }
                            ]
                        }
                    ]
                }

        Returns:
            chaîne HTML rendue
        """
        if not data:
            return ""

        platforms = data.get("platforms", [])
        rss_feeds = data.get("rss_feeds", [])

        if not platforms and not rss_feeds:
            return ""

        # Calcule le nombre total d'entrées
        total_platform_items = sum(len(p.get("items", [])) for p in platforms)
        total_rss_items = sum(len(f.get("items", [])) for f in rss_feeds)
        total_count = total_platform_items + total_rss_items

        if total_count == 0:
            return ""

        # Rassemble les informations de tous les groupes pour générer les onglets
        all_groups = []
        for p in platforms:
            items = p.get("items", [])
            if items:
                all_groups.append({"name": p.get("name", p.get("id", "")), "count": len(items)})
        for f in rss_feeds:
            items = f.get("items", [])
            if items:
                all_groups.append({"name": f.get("name", f.get("id", "")), "count": len(items)})

        standalone_html = f"""
                <div class="standalone-section">
                    <div class="standalone-section-header">
                        <div class="standalone-section-title">{t("standalone_section", language)}</div>
                        <div class="standalone-section-count">{total_count} {t("count_unit", language)}</div>
                    </div>"""

        # Génère la barre d'onglets (à partir de 2 groupes)
        if len(all_groups) >= 2:
            standalone_html += """
                    <div class="tab-bar standalone-tab-bar">"""
            for idx, g in enumerate(all_groups):
                active = ' active' if idx == 0 else ''
                standalone_html += f"""
                        <button class="tab-btn{active}" data-standalone-tab="{idx}">{html_escape(g["name"])}<span class="tab-count">{g["count"]}</span></button>"""
            standalone_html += f"""
                        <button class="tab-btn" data-standalone-tab="all">{t("tab_all", language)}<span class="tab-count">{total_count}</span></button>
                    </div>"""

        standalone_html += """
                    <div class="standalone-groups-grid">"""

        group_idx = 0
        # Rend les plateformes de tendances (réutilise la structure word-group)
        for platform in platforms:
            platform_name = platform.get("name", platform.get("id", ""))
            items = platform.get("items", [])
            if not items:
                continue

            standalone_html += f"""
                    <div class="standalone-group" data-standalone-tab="{group_idx}">
                        <div class="standalone-header">
                            <div class="standalone-name">{html_escape(platform_name)}</div>
                            <div class="standalone-count">{len(items)} {t("count_unit", language)}</div>
                        </div>"""

            # Rend chaque entrée (réutilise la structure news-item)
            for j, item in enumerate(items, 1):
                title = item.get("title", "")
                url = item.get("url", "") or item.get("mobileUrl", "")
                rank = item.get("rank", 0)
                ranks = item.get("ranks", [])
                first_time = item.get("first_time", "")
                last_time = item.get("last_time", "")
                count = item.get("count", 1)

                standalone_html += f"""
                        <div class="news-item">
                            <div class="news-number">{j}</div>
                            <div class="news-content">
                                <div class="news-header">"""

                # Affichage du classement (réutilise le style rank-num, sans préfixe #)
                if ranks:
                    min_rank = min(ranks)
                    max_rank = max(ranks)

                    # Détermine le niveau de classement
                    if min_rank <= 3:
                        rank_class = "top"
                    elif min_rank <= 10:
                        rank_class = "high"
                    else:
                        rank_class = ""

                    if min_rank == max_rank:
                        rank_text = str(min_rank)
                    else:
                        rank_text = f"{min_rank}-{max_rank}"

                    standalone_html += f'<span class="rank-num {rank_class}">{rank_text}</span>'
                elif rank > 0:
                    if rank <= 3:
                        rank_class = "top"
                    elif rank <= 10:
                        rank_class = "high"
                    else:
                        rank_class = ""
                    standalone_html += f'<span class="rank-num {rank_class}">{rank}</span>'

                # Affichage du temps (réutilise le style time-info, convertit HH-MM en HH:MM)
                if first_time and last_time and first_time != last_time:
                    first_time_display = convert_time_for_display(first_time)
                    last_time_display = convert_time_for_display(last_time)
                    standalone_html += f'<span class="time-info">{html_escape(first_time_display)}~{html_escape(last_time_display)}</span>'
                elif first_time:
                    first_time_display = convert_time_for_display(first_time)
                    standalone_html += f'<span class="time-info">{html_escape(first_time_display)}</span>'

                # Nombre d'occurrences (réutilise le style count-info)
                if count > 1:
                    standalone_html += f'<span class="count-info">{count}{t("occurrence_unit", language)}</span>'

                standalone_html += """
                                </div>
                                <div class="news-title">"""

                # Titre et lien (réutilise le style news-link)
                escaped_title = html_escape(title)
                if url:
                    escaped_url = html_escape(url)
                    standalone_html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    standalone_html += escaped_title

                standalone_html += """
                                </div>
                            </div>
                        </div>"""

            standalone_html += """
                    </div>"""
            group_idx += 1

        # Rend les sources RSS (réutilise la même structure)
        for feed in rss_feeds:
            feed_name = feed.get("name", feed.get("id", ""))
            items = feed.get("items", [])
            if not items:
                continue

            standalone_html += f"""
                    <div class="standalone-group" data-standalone-tab="{group_idx}">
                        <div class="standalone-header">
                            <div class="standalone-name">{html_escape(feed_name)}</div>
                            <div class="standalone-count">{len(items)} {t("count_unit", language)}</div>
                        </div>"""

            for j, item in enumerate(items, 1):
                title = item.get("title", "")
                url = item.get("url", "")
                published_at = item.get("published_at", "")
                author = item.get("author", "")

                standalone_html += f"""
                        <div class="news-item">
                            <div class="news-number">{j}</div>
                            <div class="news-content">
                                <div class="news-header">"""

                # Affichage du temps (formate le temps ISO)
                if published_at:
                    try:
                        from datetime import datetime as dt
                        if "T" in published_at:
                            dt_obj = dt.fromisoformat(published_at.replace("Z", "+00:00"))
                            time_display = dt_obj.strftime("%m-%d %H:%M")
                        else:
                            time_display = published_at
                    except:
                        time_display = published_at

                    standalone_html += f'<span class="time-info">{html_escape(time_display)}</span>'

                # Affichage de l'auteur
                if author:
                    standalone_html += f'<span class="source-name">{html_escape(author)}</span>'

                standalone_html += """
                                </div>
                                <div class="news-title">"""

                escaped_title = html_escape(title)
                if url:
                    escaped_url = html_escape(url)
                    standalone_html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    standalone_html += escaped_title

                standalone_html += """
                                </div>
                            </div>
                        </div>"""

            standalone_html += """
                    </div>"""
            group_idx += 1

        standalone_html += """
                    </div>
                </div>"""
        return standalone_html

    # Génère le HTML des statistiques et nouveautés RSS
    rss_stats_html = render_rss_stats_html(rss_items, t("rss_subscription_update", language)) if rss_items else ""
    rss_new_html = render_rss_stats_html(rss_new_items, t("rss_new_update", language)) if rss_new_items else ""

    # Génère le HTML de la zone d'affichage autonome
    standalone_html = render_standalone_html(standalone_data)

    # Génère le HTML de l'analyse IA
    ai_html = render_ai_analysis_html_rich(ai_analysis, language) if ai_analysis else ""

    # Prépare la correspondance des contenus de chaque zone
    region_contents = {
        "hotlist": stats_html,
        "rss": rss_stats_html,
        "new_items": (new_titles_html, rss_new_html),  # tuple, traités séparément
        "standalone": standalone_html,
        "ai_analysis": ai_html,
    }

    def add_section_divider(content: str) -> str:
        """Ajoute la classe section-divider au div externe du contenu."""
        if not content or 'class="' not in content:
            return content
        first_class_pos = content.find('class="')
        if first_class_pos != -1:
            insert_pos = first_class_pos + len('class="')
            return content[:insert_pos] + "section-divider " + content[insert_pos:]
        return content

    # Assemble les contenus dans l'ordre de region_order, ajoute dynamiquement les séparateurs
    has_previous_content = False
    for region in region_order:
        content = region_contents.get(region, "")
        if region == "new_items":
            # Traitement spécial de la zone new_items (contient nouveautés tendances et nouveautés RSS)
            new_html, rss_new = content
            if new_html:
                if has_previous_content:
                    new_html = add_section_divider(new_html)
                html += new_html
                has_previous_content = True
            if rss_new:
                if has_previous_content:
                    rss_new = add_section_divider(rss_new)
                html += rss_new
                has_previous_content = True
        elif content:
            if has_previous_content:
                content = add_section_divider(content)
            html += content
            has_previous_content = True

    html += f"""
            </div>

            <div class="footer">
                <div class="footer-content">
                    {t("footer_generated_by", language)} <span class="project-name">TrendRadar</span> ·
                    <a href="https://github.com/sansan0/TrendRadar" target="_blank" class="footer-link">
                        {t("footer_github_project", language)}
                    </a>"""

    if update_info:
        html += f"""
                    <br>
                    <span style="color: #ea580c; font-weight: 500;">
                        {t("footer_new_version", language).format(remote=update_info['remote_version'], current=update_info['current_version'])}
                    </span>"""

    html += f"""
                </div>
            </div>
        </div>

        <div class="fab-bar">
            <button class="fab-btn" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" title="{t("fab_back_to_top", language)}">↑</button>
            <button class="fab-btn fab-help">
                <span>?</span>
                <div class="fab-tooltip">
                    <div class="tip-row"><span>{t("tip_toggle_wide", language)}</span><span class="tip-key">W</span></div>
                    <div class="tip-row"><span>{t("tip_dark_mode", language)}</span><span class="tip-key">D</span></div>
                    <div class="tip-row"><span>{t("tip_search", language)}</span><span class="tip-key">/</span></div>
                    <div class="tip-row"><span>{t("tip_prev_tab", language)}</span><span class="tip-key">←</span></div>
                    <div class="tip-row"><span>{t("tip_next_tab", language)}</span><span class="tip-key">→</span></div>
                    <div class="tip-row"><span>{t("tip_copyable_number", language)}</span><span class="tip-key">{t("tip_key_click", language)}</span></div>
                </div>
            </button>
        </div>"""

    html += f"""
        <script>
            // ===== Objet i18n injecté côté serveur =====
            var I18N = {js_i18n_json};
        </script>"""

    html += """
        <script>
            // ===== Fonctions d'amélioration navigateur =====

            function toggleWideMode() {
                document.body.classList.toggle('wide-mode');
                var isWide = document.body.classList.contains('wide-mode');
                try { localStorage.setItem('trendradar-wide-mode', isWide ? '1' : '0'); } catch(e) {}
                var btn = document.querySelector('.toggle-wide-btn');
                if (btn) btn.textContent = isWide ? '⊡' : '⛶';
                initTabVisibility();
                initCollapseVisibility();
                initStandaloneTabVisibility();
            }

            function toggleDarkMode() {
                var isDark = document.body.classList.toggle('dark-mode');
                try { localStorage.setItem('trendradar-dark-mode', isDark ? '1' : '0'); } catch(e) {}
                var btn = document.querySelector('.toggle-dark-btn');
                if (btn) btn.textContent = isDark ? '☀' : '☽';
            }

            function initTabScroll(tabBar) {
                var wrapper = tabBar.closest('.tab-bar-wrapper') || tabBar.parentNode;
                var leftArrow = wrapper.querySelector('.tab-arrow-left');
                var rightArrow = wrapper.querySelector('.tab-arrow-right');
                var indicator = wrapper.querySelector('.tab-scroll-indicator');
                if (!leftArrow) {
                    leftArrow = document.createElement('button');
                    leftArrow.className = 'tab-arrow tab-arrow-left';
                    leftArrow.innerHTML = '‹';
                    rightArrow = document.createElement('button');
                    rightArrow.className = 'tab-arrow tab-arrow-right';
                    rightArrow.innerHTML = '›';
                    indicator = document.createElement('div');
                    indicator.className = 'tab-scroll-indicator';
                    wrapper.insertBefore(leftArrow, tabBar);
                    tabBar.after(rightArrow);
                    wrapper.appendChild(indicator);
                }
                var scrollStep = 200;
                leftArrow.addEventListener('click', function(e) {
                    e.stopPropagation();
                    tabBar.scrollBy({ left: -scrollStep, behavior: 'smooth' });
                });
                rightArrow.addEventListener('click', function(e) {
                    e.stopPropagation();
                    tabBar.scrollBy({ left: scrollStep, behavior: 'smooth' });
                });
                function updateArrows() {
                    var sl = tabBar.scrollLeft;
                    var sw = tabBar.scrollWidth;
                    var cw = tabBar.clientWidth;
                    var noOverflow = sw <= cw + 1;
                    var atStart = sl <= 1;
                    var atEnd = sl + cw >= sw - 1;
                    leftArrow.classList.toggle('visible', !noOverflow && !atStart);
                    rightArrow.classList.toggle('visible', !noOverflow && !atEnd);
                    tabBar.classList.toggle('scroll-start', atStart);
                    tabBar.classList.toggle('scroll-end', atEnd);
                    tabBar.classList.toggle('no-overflow', noOverflow);
                    var progress = noOverflow ? 0 : sl / (sw - cw);
                    indicator.style.width = (progress * 100) + '%';
                }
                tabBar.addEventListener('scroll', updateArrows, { passive: true });
                tabBar.addEventListener('wheel', function(e) {
                    if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
                        tabBar.scrollLeft += e.deltaY;
                        e.preventDefault();
                    }
                }, { passive: false });
                updateArrows();
                new ResizeObserver(updateArrows).observe(tabBar);
            }

            function initTabs() {
                var wrapper = document.querySelector('.tab-bar-wrapper');
                var tabBar = wrapper ? wrapper.querySelector('.tab-bar') : null;
                if (!tabBar) return;
                var tabs = tabBar.querySelectorAll('.tab-btn');
                var groups = document.querySelectorAll('.word-group[data-tab-index]');
                initTabVisibility();
                initTabScroll(tabBar);

                function activateTab(index, scroll) {
                    tabs.forEach(function(t) { t.classList.remove('active'); });
                    if (index === 'all') {
                        var allBtn = tabBar.querySelector('[data-tab-index="all"]');
                        if (allBtn) {
                            allBtn.classList.add('active');
                            if (scroll !== false) allBtn.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
                        }
                        groups.forEach(function(g) { g.style.display = ''; });
                        try { history.replaceState(null, '', '#all'); } catch(e) {}
                        return;
                    }
                    var idx = parseInt(index);
                    tabs.forEach(function(t) {
                        if (parseInt(t.dataset.tabIndex) === idx) t.classList.add('active');
                    });
                    if (document.body.classList.contains('wide-mode') && !wrapper.classList.contains('tab-hidden')) {
                        groups.forEach(function(g) {
                            g.style.display = (parseInt(g.dataset.tabIndex) === idx) ? '' : 'none';
                        });
                    }
                    var activeBtn = tabBar.querySelector('.tab-btn.active');
                    if (scroll !== false && activeBtn) activeBtn.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
                    try { history.replaceState(null, '', '#tab-' + idx); } catch(e) {}
                }

                tabs.forEach(function(tab) {
                    tab.addEventListener('click', function() {
                        var idx = tab.dataset.tabIndex;
                        activateTab(idx === 'all' ? 'all' : parseInt(idx));
                    });
                });

                tabBar.addEventListener('keydown', function(e) {
                    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                        var tabsArr = Array.from(tabs);
                        var ci = tabsArr.findIndex(function(t) { return t.classList.contains('active'); });
                        var dir = e.key === 'ArrowRight' ? 1 : -1;
                        var ni = Math.max(0, Math.min(tabsArr.length - 1, ci + dir));
                        var nt = tabsArr[ni];
                        activateTab(nt.dataset.tabIndex === 'all' ? 'all' : parseInt(nt.dataset.tabIndex));
                        nt.focus();
                        e.preventDefault();
                    }
                });

                var hash = window.location.hash;
                if (hash === '#all') { activateTab('all'); }
                else if (hash.indexOf('#tab-') === 0) { activateTab(parseInt(hash.replace('#tab-', ''))); }
                else { activateTab(0, false); }
            }

            function initTabVisibility() {
                var wrapper = document.querySelector('.tab-bar-wrapper');
                if (!wrapper) return;
                var tabBar = wrapper.querySelector('.tab-bar');
                var groups = document.querySelectorAll('.word-group[data-tab-index]');
                var isWide = document.body.classList.contains('wide-mode');
                if (!isWide || groups.length <= 2) {
                    wrapper.classList.add('tab-hidden');
                    groups.forEach(function(g) { g.style.display = ''; });
                } else {
                    wrapper.classList.remove('tab-hidden');
                    var activeTab = tabBar.querySelector('.tab-btn.active');
                    if (activeTab) { activeTab.click(); }
                    else {
                        var firstTab = tabBar.querySelector('.tab-btn[data-tab-index="0"]');
                        if (firstTab) firstTab.click();
                    }
                }
            }

            var handleSearch = (function() {
                var timer = null;
                return function(query) {
                    clearTimeout(timer);
                    timer = setTimeout(function() {
                        query = query.toLowerCase();
                        document.querySelectorAll('.news-item').forEach(function(item) {
                            var title = (item.querySelector('.news-title') || {}).textContent || '';
                            item.style.display = (!query || title.toLowerCase().indexOf(query) !== -1) ? '' : 'none';
                        });
                        document.querySelectorAll('.rss-item').forEach(function(item) {
                            var title = (item.querySelector('.rss-title') || {}).textContent || '';
                            item.style.display = (!query || title.toLowerCase().indexOf(query) !== -1) ? '' : 'none';
                        });
                    }, 200);
                };
            })();

            function initBackToTop() {
                var fabBar = document.querySelector('.fab-bar');
                if (!fabBar) return;
                var ticking = false;
                window.addEventListener('scroll', function() {
                    if (!ticking) {
                        requestAnimationFrame(function() {
                            fabBar.classList.toggle('visible', window.scrollY > 300);
                            ticking = false;
                        });
                        ticking = true;
                    }
                });
            }

            function initCollapse() {
                document.querySelectorAll('.word-header').forEach(function(header) {
                    header.addEventListener('click', function() {
                        var wrapper = document.querySelector('.tab-bar-wrapper');
                        if (document.body.classList.contains('wide-mode') && wrapper && !wrapper.classList.contains('tab-hidden')) return;
                        var group = header.closest('.word-group');
                        if (group) group.classList.toggle('collapsed');
                    });
                });
                initCollapseVisibility();
            }

            function initCollapseVisibility() {
                var headers = document.querySelectorAll('.word-header');
                var wrapper = document.querySelector('.tab-bar-wrapper');
                var isTabMode = document.body.classList.contains('wide-mode') && wrapper && !wrapper.classList.contains('tab-hidden');
                headers.forEach(function(h) {
                    if (isTabMode) { h.classList.remove('collapsible'); }
                    else { h.classList.add('collapsible'); }
                });
                if (isTabMode) {
                    document.querySelectorAll('.word-group.collapsed').forEach(function(g) {
                        g.classList.remove('collapsed');
                    });
                }
            }

            // Changement d'onglet de la zone d'affichage autonome
            function initStandaloneTabs() {
                var tabBar = document.querySelector('.standalone-tab-bar');
                if (!tabBar) return;
                var groups = document.querySelectorAll('.standalone-group[data-standalone-tab]');
                var btns = tabBar.querySelectorAll('.tab-btn[data-standalone-tab]');
                initTabScroll(tabBar);

                function activateStandaloneTab(val) {
                    btns.forEach(function(b) {
                        var bVal = b.getAttribute('data-standalone-tab');
                        b.classList.toggle('active', bVal === String(val));
                    });
                    groups.forEach(function(g) {
                        var gVal = g.getAttribute('data-standalone-tab');
                        g.style.display = (val === 'all' || gVal === String(val)) ? '' : 'none';
                    });
                }

                btns.forEach(function(btn) {
                    btn.addEventListener('click', function() {
                        activateStandaloneTab(btn.getAttribute('data-standalone-tab'));
                    });
                });

                // État initial
                initStandaloneTabVisibility();
            }

            function initStandaloneTabVisibility() {
                var tabBar = document.querySelector('.standalone-tab-bar');
                if (!tabBar) return;
                var groups = document.querySelectorAll('.standalone-group[data-standalone-tab]');
                var isWide = document.body.classList.contains('wide-mode');
                if (!isWide || groups.length <= 1) {
                    tabBar.classList.add('tab-hidden');
                    groups.forEach(function(g) { g.style.display = ''; });
                } else {
                    tabBar.classList.remove('tab-hidden');
                    var activeBtn = tabBar.querySelector('.tab-btn.active');
                    if (activeBtn) activeBtn.click();
                    else { var first = tabBar.querySelector('.tab-btn'); if (first) first.click(); }
                }
            }

            function prepareForScreenshot() {
                var state = {
                    wasWide: document.body.classList.contains('wide-mode'),
                    hiddenGroups: []
                };
                document.body.classList.remove('wide-mode');
                state.wasDark = document.body.classList.contains('dark-mode');
                document.body.classList.remove('dark-mode');
                document.querySelectorAll('.word-group[data-tab-index]').forEach(function(g, i) {
                    if (g.style.display === 'none') {
                        state.hiddenGroups.push(i);
                        g.style.display = '';
                    }
                });
                state.hiddenStandaloneGroups = [];
                document.querySelectorAll('.standalone-group[data-standalone-tab]').forEach(function(g, i) {
                    if (g.style.display === 'none') {
                        state.hiddenStandaloneGroups.push(i);
                        g.style.display = '';
                    }
                });
                document.querySelectorAll('.tab-bar-wrapper, .standalone-tab-bar, .search-bar, .fab-bar, .toggle-wide-btn').forEach(function(el) {
                    el.dataset.prevDisplay = el.style.display || '';
                    el.style.display = 'none';
                });
                document.querySelectorAll('.toggle-dark-btn').forEach(function(el) {
                    el.dataset.prevDisplay = el.style.display || ''; el.style.display = 'none';
                });
                document.querySelectorAll('.reading-progress').forEach(function(el) { el.style.display = 'none'; });
                document.querySelectorAll('.header-watermark').forEach(function(el) { el.style.display = 'none'; });
                return state;
            }

            function restoreAfterScreenshot(state) {
                if (state.wasWide) document.body.classList.add('wide-mode');
                if (state.wasDark) document.body.classList.add('dark-mode');
                var groups = document.querySelectorAll('.word-group[data-tab-index]');
                state.hiddenGroups.forEach(function(i) {
                    if (groups[i]) groups[i].style.display = 'none';
                });
                var standaloneGroups = document.querySelectorAll('.standalone-group[data-standalone-tab]');
                if (state.hiddenStandaloneGroups) {
                    state.hiddenStandaloneGroups.forEach(function(i) {
                        if (standaloneGroups[i]) standaloneGroups[i].style.display = 'none';
                    });
                }
                document.querySelectorAll('.tab-bar-wrapper, .standalone-tab-bar, .search-bar, .fab-bar, .toggle-wide-btn').forEach(function(el) {
                    el.style.display = el.dataset.prevDisplay || '';
                    delete el.dataset.prevDisplay;
                });
                document.querySelectorAll('.toggle-dark-btn').forEach(function(el) {
                    el.style.display = el.dataset.prevDisplay || ''; delete el.dataset.prevDisplay;
                });
                document.querySelectorAll('.reading-progress').forEach(function(el) { el.style.display = ''; });
                document.querySelectorAll('.header-watermark').forEach(function(el) { el.style.display = ''; });
                initTabVisibility();
                initCollapseVisibility();
                initStandaloneTabVisibility();
                var fabBar = document.querySelector('.fab-bar');
                if (fabBar && window.scrollY > 300) fabBar.classList.add('visible');
            }

            // ===== Fonctions de capture d'écran =====

            async function saveAsImage(e) {
                const button = e.target.closest('.save-dropdown-item') || e.target;
                const originalHTML = button.innerHTML;
                var screenshotState = null;

                try {
                    button.textContent = I18N.generating;
                    button.disabled = true;
                    window.scrollTo(0, 0);

                    // Attend la stabilisation de la page
                    await new Promise(resolve => setTimeout(resolve, 200));

                    // Préparation avant capture : repasse en disposition étroite
                    screenshotState = prepareForScreenshot();

                    // Masque les boutons avant la capture
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'hidden';

                    // Attend à nouveau pour garantir que les boutons sont bien masqués
                    await new Promise(resolve => setTimeout(resolve, 100));

                    const container = document.querySelector('.container');

                    const canvas = await html2canvas(container, {
                        backgroundColor: '#ffffff',
                        scale: 1.5,
                        useCORS: true,
                        allowTaint: false,
                        imageTimeout: 10000,
                        removeContainer: false,
                        foreignObjectRendering: false,
                        logging: false,
                        width: container.offsetWidth,
                        height: container.offsetHeight,
                        x: 0,
                        y: 0,
                        scrollX: 0,
                        scrollY: 0,
                        windowWidth: window.innerWidth,
                        windowHeight: window.innerHeight
                    });

                    buttons.style.visibility = 'visible';
                    restoreAfterScreenshot(screenshotState);

                    const link = document.createElement('a');
                    const now = new Date();
                    const filename = `TrendRadar_${I18N.screenshotLabel}_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}.png`;

                    link.download = filename;
                    link.href = canvas.toDataURL('image/png', 1.0);

                    // Déclenche le téléchargement
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);

                    button.textContent = I18N.saveSuccess;
                    setTimeout(() => {
                        button.innerHTML = originalHTML;
                        button.disabled = false;
                    }, 2000);

                } catch (error) {
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'visible';
                    if (screenshotState) { restoreAfterScreenshot(screenshotState); }
                    button.textContent = I18N.saveFailed;
                    setTimeout(() => {
                        button.innerHTML = originalHTML;
                        button.disabled = false;
                    }, 2000);
                }
            }

            async function saveAsMultipleImages(e) {
                const button = e.target.closest('.save-dropdown-item') || e.target;
                const originalHTML = button.innerHTML;
                const container = document.querySelector('.container');
                const scale = 1.5;
                const maxHeight = 5000 / scale;
                var screenshotState2 = null;

                try {
                    screenshotState2 = prepareForScreenshot();
                    button.textContent = I18N.analyzing;
                    button.disabled = true;

                    // Récupère tous les éléments de découpe possibles
                    const newsItems = Array.from(container.querySelectorAll('.news-item'));
                    const wordGroups = Array.from(container.querySelectorAll('.word-group'));
                    const newSection = container.querySelector('.new-section');
                    const errorSection = container.querySelector('.error-section');
                    const header = container.querySelector('.header');
                    const footer = container.querySelector('.footer');

                    // Calcule la position et la hauteur des éléments
                    const containerRect = container.getBoundingClientRect();
                    const elements = [];

                    // Ajoute le header comme élément obligatoire
                    elements.push({
                        type: 'header',
                        element: header,
                        top: 0,
                        bottom: header.offsetHeight,
                        height: header.offsetHeight
                    });

                    // Ajoute les informations d'erreur (si présentes)
                    if (errorSection) {
                        const rect = errorSection.getBoundingClientRect();
                        elements.push({
                            type: 'error',
                            element: errorSection,
                            top: rect.top - containerRect.top,
                            bottom: rect.bottom - containerRect.top,
                            height: rect.height
                        });
                    }

                    // Traite les news-item groupés par word-group
                    wordGroups.forEach(group => {
                        const groupRect = group.getBoundingClientRect();
                        const groupNewsItems = group.querySelectorAll('.news-item');

                        // Ajoute la partie header du word-group
                        const wordHeader = group.querySelector('.word-header');
                        if (wordHeader) {
                            const headerRect = wordHeader.getBoundingClientRect();
                            elements.push({
                                type: 'word-header',
                                element: wordHeader,
                                parent: group,
                                top: groupRect.top - containerRect.top,
                                bottom: headerRect.bottom - containerRect.top,
                                height: headerRect.height
                            });
                        }

                        // Ajoute chaque news-item
                        groupNewsItems.forEach(item => {
                            const rect = item.getBoundingClientRect();
                            elements.push({
                                type: 'news-item',
                                element: item,
                                parent: group,
                                top: rect.top - containerRect.top,
                                bottom: rect.bottom - containerRect.top,
                                height: rect.height
                            });
                        });
                    });

                    // Ajoute la partie des nouvelles actualités
                    if (newSection) {
                        const rect = newSection.getBoundingClientRect();
                        elements.push({
                            type: 'new-section',
                            element: newSection,
                            top: rect.top - containerRect.top,
                            bottom: rect.bottom - containerRect.top,
                            height: rect.height
                        });
                    }

                    // Ajoute le footer
                    const footerRect = footer.getBoundingClientRect();
                    elements.push({
                        type: 'footer',
                        element: footer,
                        top: footerRect.top - containerRect.top,
                        bottom: footerRect.bottom - containerRect.top,
                        height: footer.offsetHeight
                    });

                    // Calcule les points de découpe
                    const segments = [];
                    let currentSegment = { start: 0, end: 0, height: 0, includeHeader: true };
                    let headerHeight = header.offsetHeight;
                    currentSegment.height = headerHeight;

                    for (let i = 1; i < elements.length; i++) {
                        const element = elements[i];
                        const potentialHeight = element.bottom - currentSegment.start;

                        // Vérifie s'il faut créer un nouveau segment
                        if (potentialHeight > maxHeight && currentSegment.height > headerHeight) {
                            // Découpe à la fin de l'élément précédent
                            currentSegment.end = elements[i - 1].bottom;
                            segments.push(currentSegment);

                            // Commence un nouveau segment
                            currentSegment = {
                                start: currentSegment.end,
                                end: 0,
                                height: element.bottom - currentSegment.end,
                                includeHeader: false
                            };
                        } else {
                            currentSegment.height = potentialHeight;
                            currentSegment.end = element.bottom;
                        }
                    }

                    // Ajoute le dernier segment
                    if (currentSegment.height > 0) {
                        currentSegment.end = container.offsetHeight;
                        segments.push(currentSegment);
                    }

                    button.textContent = I18N.generatingProgress.replace('{current}', 0).replace('{total}', segments.length);

                    // Masque les boutons d'enregistrement
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'hidden';

                    // Génère une image pour chaque segment
                    const images = [];
                    for (let i = 0; i < segments.length; i++) {
                        const segment = segments[i];
                        button.textContent = I18N.generatingProgress.replace('{current}', i + 1).replace('{total}', segments.length);

                        // Crée un conteneur temporaire pour la capture
                        const tempContainer = document.createElement('div');
                        tempContainer.style.cssText = `
                            position: absolute;
                            left: -9999px;
                            top: 0;
                            width: ${container.offsetWidth}px;
                            background: white;
                        `;
                        tempContainer.className = 'container';

                        // Clone le contenu du conteneur
                        const clonedContainer = container.cloneNode(true);

                        // Retire les boutons d'enregistrement du clone
                        const clonedButtons = clonedContainer.querySelector('.save-buttons');
                        if (clonedButtons) {
                            clonedButtons.style.display = 'none';
                        }

                        tempContainer.appendChild(clonedContainer);
                        document.body.appendChild(tempContainer);

                        // Attend la mise à jour du DOM
                        await new Promise(resolve => setTimeout(resolve, 100));

                        // Utilise html2canvas pour capturer la zone ciblée
                        const canvas = await html2canvas(clonedContainer, {
                            backgroundColor: '#ffffff',
                            scale: scale,
                            useCORS: true,
                            allowTaint: false,
                            imageTimeout: 10000,
                            logging: false,
                            width: container.offsetWidth,
                            height: segment.end - segment.start,
                            x: 0,
                            y: segment.start,
                            windowWidth: window.innerWidth,
                            windowHeight: window.innerHeight
                        });

                        images.push(canvas.toDataURL('image/png', 1.0));

                        // Nettoie le conteneur temporaire
                        document.body.removeChild(tempContainer);
                    }

                    // Restaure l'affichage des boutons
                    buttons.style.visibility = 'visible';

                    // Télécharge toutes les images
                    const now = new Date();
                    const baseFilename = `TrendRadar_${I18N.screenshotLabel}_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;

                    for (let i = 0; i < images.length; i++) {
                        const link = document.createElement('a');
                        link.download = `${baseFilename}_part${i + 1}.png`;
                        link.href = images[i];
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);

                        // Petit délai pour éviter que le navigateur bloque les téléchargements multiples
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }

                    button.textContent = I18N.savedImages.replace('{count}', segments.length);
                    restoreAfterScreenshot(screenshotState2);
                    setTimeout(() => {
                        button.innerHTML = originalHTML;
                        button.disabled = false;
                    }, 2000);

                } catch (error) {
                    console.error('Echec de la sauvegarde segmentee:', error);
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'visible';
                    if (screenshotState2) { restoreAfterScreenshot(screenshotState2); }
                    button.textContent = I18N.saveFailed;
                    setTimeout(() => {
                        button.innerHTML = originalHTML;
                        button.disabled = false;
                    }, 2000);
                }
            }

            function saveAsMarkdown() {
                var lines = [];
                var now = new Date();
                var dateStr = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
                var timeStr = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');

                // Titre
                var headerTitle = document.querySelector('.header-title');
                lines.push('# ' + (headerTitle ? headerTitle.textContent.trim() : 'TrendRadar'));
                lines.push('');

                // Métadonnées du rapport
                var infoItems = document.querySelectorAll('.header-info .info-item');
                if (infoItems.length) {
                    infoItems.forEach(function(item) {
                        var label = item.querySelector('.info-label');
                        var value = item.querySelector('.info-value');
                        if (label && value) {
                            lines.push('- **' + label.textContent.trim() + '**: ' + value.textContent.trim());
                        }
                    });
                    lines.push('');
                }

                // Fonction générique d'extraction d'un news-item
                function extractItem(item, idx) {
                    var titleEl = item.querySelector('.news-title a');
                    var titleText = '';
                    var url = '';
                    if (titleEl) {
                        titleText = titleEl.textContent.trim();
                        url = titleEl.href || '';
                    } else {
                        var titleDiv = item.querySelector('.news-title') || item.querySelector('.new-item-title');
                        if (titleDiv) titleText = titleDiv.textContent.trim();
                    }
                    if (!titleText) return '';

                    var meta = [];
                    var rank = item.querySelector('.rank-num, .new-item-rank');
                    if (rank && rank.textContent.trim() && rank.textContent.trim() !== '?') meta.push('#' + rank.textContent.trim());
                    var source = item.querySelector('.source-name');
                    if (source) meta.push(source.textContent.trim());
                    var keyword = item.querySelector('.keyword-tag');
                    if (keyword) meta.push(keyword.textContent.trim());
                    var time = item.querySelector('.time-info');
                    if (time) meta.push(time.textContent.trim());
                    var count = item.querySelector('.count-info');
                    if (count) meta.push(count.textContent.trim());

                    var line = idx + '. ';
                    if (url) {
                        line += '[' + titleText.replace(/[[\\]]/g, '') + '](' + url + ')';
                    } else {
                        line += titleText;
                    }
                    if (meta.length) line += '  `' + meta.join(' | ') + '`';
                    return line;
                }

                // Zone des mots-clés tendances
                var wordGroups = document.querySelectorAll('.hotlist-section > .word-group');
                if (wordGroups.length) {
                    lines.push('## ' + I18N.mdHotNews);
                    lines.push('');
                    wordGroups.forEach(function(group) {
                        var wordName = group.querySelector('.word-name');
                        var wordCount = group.querySelector('.word-count');
                        if (wordName) {
                            lines.push('### ' + wordName.textContent.trim() + (wordCount ? ' (' + wordCount.textContent.trim() + ')' : ''));
                            lines.push('');
                        }
                        var items = group.querySelectorAll('.news-item');
                        items.forEach(function(item, i) {
                            var line = extractItem(item, i + 1);
                            if (line) lines.push(line);
                        });
                        lines.push('');
                    });
                }

                // Zone des nouvelles tendances
                var newSection = document.querySelector('.new-section');
                if (newSection) {
                    var newTitle = newSection.querySelector('.new-section-title');
                    lines.push('## ' + (newTitle ? newTitle.textContent.trim() : I18N.mdNewHotspots));
                    lines.push('');
                    var sourceGroups = newSection.querySelectorAll('.new-source-group');
                    sourceGroups.forEach(function(sg) {
                        var srcTitle = sg.querySelector('.new-source-title');
                        if (srcTitle) {
                            lines.push('### ' + srcTitle.textContent.trim());
                            lines.push('');
                        }
                        var items = sg.querySelectorAll('.new-item');
                        items.forEach(function(item, i) {
                            var line = extractItem(item, i + 1);
                            if (line) lines.push(line);
                        });
                        lines.push('');
                    });
                }

                // Zone de mise à jour des abonnements RSS
                var rssSection = document.querySelector('.rss-section');
                if (rssSection) {
                    var rssSectionTitle = rssSection.querySelector('.rss-section-title');
                    lines.push('## ' + (rssSectionTitle ? rssSectionTitle.textContent.trim() : I18N.mdRssUpdate));
                    lines.push('');
                    var feedGroups = rssSection.querySelectorAll('.feed-group');
                    feedGroups.forEach(function(group) {
                        var feedName = group.querySelector('.feed-name');
                        var feedCount = group.querySelector('.feed-count');
                        if (feedName) {
                            lines.push('### ' + feedName.textContent.trim() + (feedCount ? ' (' + feedCount.textContent.trim() + ')' : ''));
                            lines.push('');
                        }
                        var items = group.querySelectorAll('.rss-item');
                        items.forEach(function(item, i) {
                            var titleEl = item.querySelector('.rss-title a');
                            var titleText = titleEl ? titleEl.textContent.trim() : '';
                            var url = titleEl ? (titleEl.href || '') : '';
                            if (!titleText) return;
                            var meta = [];
                            var time = item.querySelector('.rss-time');
                            if (time) meta.push(time.textContent.trim());
                            var author = item.querySelector('.rss-author');
                            if (author) meta.push(author.textContent.trim());
                            var line = (i + 1) + '. ';
                            if (url) { line += '[' + titleText.replace(/[\\[\\]]/g, '') + '](' + url + ')'; }
                            else { line += titleText; }
                            if (meta.length) line += '  `' + meta.join(' | ') + '`';
                            lines.push(line);
                        });
                        lines.push('');
                    });
                }

                // Zone d'analyse IA des tendances
                var aiSection = document.querySelector('.ai-section');
                if (aiSection) {
                    var aiError = aiSection.querySelector('.ai-error') || aiSection.querySelector('.ai-warning');
                    var aiInfo = aiSection.querySelector('.ai-info');
                    if (aiError) {
                        lines.push('## ' + I18N.mdAiAnalysis);
                        lines.push('');
                        lines.push('> ' + aiError.textContent.trim());
                        lines.push('');
                    } else if (aiInfo) {
                        // Ignore les messages d'information (ex. « ignoré »)
                    } else {
                        var aiTitle = aiSection.querySelector('.ai-section-title');
                        lines.push('## ' + (aiTitle ? aiTitle.textContent.trim() : I18N.mdAiHotAnalysis));
                        lines.push('');
                        var aiBlocks = aiSection.querySelectorAll('.ai-block');
                        aiBlocks.forEach(function(block) {
                            var blockTitle = block.querySelector('.ai-block-title');
                            var blockContent = block.querySelector('.ai-block-content');
                            if (blockTitle) {
                                lines.push('### ' + blockTitle.textContent.trim());
                                lines.push('');
                            }
                            if (blockContent) {
                                lines.push(blockContent.textContent.trim());
                                lines.push('');
                            }
                        });
                    }
                }

                // Zone d'affichage autonome (plateformes de tendances + RSS)
                var standaloneSection = document.querySelector('.standalone-section');
                if (standaloneSection) {
                    var standaloneTitle = standaloneSection.querySelector('.standalone-section-title');
                    lines.push('## ' + (standaloneTitle ? standaloneTitle.textContent.trim() : I18N.mdStandalone));
                    lines.push('');
                    var groups = standaloneSection.querySelectorAll('.standalone-group');
                    groups.forEach(function(group) {
                        var name = group.querySelector('.standalone-name');
                        var cnt = group.querySelector('.standalone-count');
                        if (name) {
                            lines.push('### ' + name.textContent.trim() + (cnt ? ' (' + cnt.textContent.trim() + ')' : ''));
                            lines.push('');
                        }
                        var items = group.querySelectorAll('.news-item');
                        items.forEach(function(item, i) {
                            var line = extractItem(item, i + 1);
                            if (line) lines.push(line);
                        });
                        lines.push('');
                    });
                }

                // Zone d'erreur
                var errorSection = document.querySelector('.error-section');
                if (errorSection) {
                    var errorItems = errorSection.querySelectorAll('.error-item');
                    if (errorItems.length) {
                        lines.push('## ' + I18N.mdCrawlErrors);
                        lines.push('');
                        errorItems.forEach(function(item) {
                            lines.push('- ' + item.textContent.trim());
                        });
                        lines.push('');
                    }
                }

                // Pied de page
                lines.push('---');
                lines.push('*Generated by TrendRadar*');

                // Téléchargement
                var md = lines.join('\\n');
                var blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
                var link = document.createElement('a');
                var filename = 'TrendRadar_' + dateStr + '_' + timeStr.replace(':', '') + '.md';
                link.download = filename;
                link.href = URL.createObjectURL(blob);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(link.href);
            }

            document.addEventListener('DOMContentLoaded', function() {
                window.scrollTo(0, 0);

                // Détection automatique du mode plein écran
                var savedMode = null;
                try { savedMode = localStorage.getItem('trendradar-wide-mode'); } catch(e) {}
                if (savedMode === '1' || (savedMode === null && window.innerWidth > 768)) {
                    document.body.classList.add('wide-mode');
                    var btn = document.querySelector('.toggle-wide-btn');
                    if (btn) btn.textContent = '⊡';
                }

                // Restauration du mode sombre
                var savedDark = null;
                try { savedDark = localStorage.getItem('trendradar-dark-mode'); } catch(e) {}
                if (savedDark === '1') {
                    document.body.classList.add('dark-mode');
                    var darkBtn = document.querySelector('.toggle-dark-btn');
                    if (darkBtn) darkBtn.textContent = '☀';
                }

                // Active la barre de recherche
                var searchBar = document.querySelector('.search-bar');
                if (searchBar) searchBar.style.display = 'block';

                // Initialise les fonctions d'amélioration
                initTabs();
                initBackToTop();
                initCollapse();
                initStandaloneTabs();

                // Raccourcis clavier
                document.addEventListener('keydown', function(e) {
                    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                    var helpBtn = document.querySelector('.fab-help');
                    switch(e.key) {
                        case '?':
                            if (helpBtn) {
                                helpBtn.classList.toggle('show-tip');
                                var fabBar = document.querySelector('.fab-bar');
                                if (fabBar) fabBar.classList.add('visible');
                            }
                            break;
                        case 'Escape':
                            if (helpBtn) helpBtn.classList.remove('show-tip');
                            break;
                        case 'w': case 'W': toggleWideMode(); break;
                        case 'd': case 'D': toggleDarkMode(); break;
                        case '/': e.preventDefault(); var si = document.querySelector('.search-input'); if (si) si.focus(); break;
                    }
                });

                // Barre de progression de lecture
                var progressBar = document.querySelector('.reading-progress');
                if (progressBar) {
                    var progressTicking = false;
                    window.addEventListener('scroll', function() {
                        if (!progressTicking) {
                            requestAnimationFrame(function() {
                                var h = document.documentElement.scrollHeight - window.innerHeight;
                                progressBar.style.width = (h > 0 ? (window.scrollY / h * 100) : 0) + '%';
                                progressTicking = false;
                            });
                            progressTicking = true;
                        }
                    });
                }

                // Copie en un clic : au survol, le numéro devient une icône de copie
                var copySvg = '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="5" width="9" height="9" rx="1.5"/><path d="M5 11H3.5A1.5 1.5 0 012 9.5v-7A1.5 1.5 0 013.5 1h7A1.5 1.5 0 0112 2.5V5"/></svg>';
                var checkSvg = '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="#22c55e" stroke-width="2"><path d="M3 8.5l3.5 3.5 7-7"/></svg>';
                document.querySelectorAll('.news-item .news-number').forEach(function(numEl) {
                    var item = numEl.closest('.news-item');
                    var titleEl = item ? item.querySelector('.news-title a') : null;
                    if (!titleEl) return;
                    var numText = numEl.textContent.trim();
                    numEl.innerHTML = '<span class="num-text">' + numText + '</span><span class="copy-icon">' + copySvg + '</span>';
                    numEl.title = I18N.copyTooltip;
                    numEl.addEventListener('click', function(e) {
                        e.stopPropagation();
                        var text = titleEl.textContent.trim() + ' ' + titleEl.href;
                        function onCopySuccess() {
                            numEl.classList.add('copied');
                            numEl.querySelector('.copy-icon').innerHTML = checkSvg;
                            setTimeout(function() {
                                numEl.classList.remove('copied');
                                numEl.querySelector('.copy-icon').innerHTML = copySvg;
                            }, 1500);
                        }
                        function fallbackCopy(str, cb) {
                            var ta = document.createElement('textarea');
                            ta.value = str; ta.style.position = 'fixed'; ta.style.opacity = '0';
                            document.body.appendChild(ta); ta.select();
                            try { document.execCommand('copy'); cb(); } catch(ex) {}
                            document.body.removeChild(ta);
                        }
                        if (navigator.clipboard && navigator.clipboard.writeText) {
                            navigator.clipboard.writeText(text).then(onCopySuccess).catch(function() {
                                fallbackCopy(text, onCopySuccess);
                            });
                        } else {
                            fallbackCopy(text, onCopySuccess);
                        }
                    });
                });



                // Filigrane du header révélé au suivi de la souris
                (function() {
                    var header = document.querySelector('.header');
                    var watermark = document.querySelector('.header-watermark');
                    if (!header || !watermark) return;

                    var radius = 100;

                    header.addEventListener('mousemove', function(e) {
                        var rect = watermark.getBoundingClientRect();
                        var x = e.clientX - rect.left;
                        var y = e.clientY - rect.top;
                        var maskVal = 'radial-gradient(circle ' + radius + 'px at ' + x + 'px ' + y + 'px, rgba(0,0,0,1) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0) 100%)';
                        watermark.style.webkitMaskImage = maskVal;
                        watermark.style.maskImage = maskVal;
                        watermark.style.color = 'rgba(255, 255, 255, 0.25)';
                    });

                    header.addEventListener('mouseleave', function() {
                        watermark.style.webkitMaskImage = 'radial-gradient(circle 0px at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 100%)';
                        watermark.style.maskImage = 'radial-gradient(circle 0px at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 100%)';
                        watermark.style.color = 'rgba(255, 255, 255, 0.15)';
                    });
                })();
            });
        </script>
    </body>
    </html>
    """

    return html
