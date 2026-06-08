# coding=utf-8
"""
Module de rendu du rapport HTML RSS.

Fournit la génération de rapports HTML pour le contenu des abonnements RSS.
"""

import json as _json
from datetime import datetime
from typing import Dict, List, Optional, Callable

from trendradar.report.helpers import html_escape
from trendradar.i18n import t


def _json_str(value: str) -> str:
    """Sérialise une chaîne en littéral JSON sûr pour l'injection JS."""
    return _json.dumps(value, ensure_ascii=False)


def render_rss_html_content(
    rss_items: List[Dict],
    total_count: int,
    feeds_info: Optional[Dict[str, str]] = None,
    *,
    get_time_func: Optional[Callable[[], datetime]] = None,
    language: str = "fr",
) -> str:
    """Rend le contenu HTML RSS.

    Args:
        rss_items: liste des entrées RSS, chaque entrée contient :
            - title: titre
            - feed_id: ID de la source RSS
            - feed_name: nom de la source RSS
            - url: lien
            - published_at: date de publication
            - summary: résumé (optionnel)
            - author: auteur (optionnel)
        total_count: nombre total d'entrées
        feeds_info: correspondance ID de source RSS vers nom
        get_time_func: fonction renvoyant l'heure courante (optionnel, défaut datetime.now)
        language: langue du rapport ("fr" ou "en")

    Returns:
        chaîne HTML rendue
    """
    html = f"""
    <!DOCTYPE html>
    <html lang="{language}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{t("rss_page_title", language)}</title>
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
                max-width: 700px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 2px 16px rgba(0,0,0,0.06);
            }

            .header {
                background: linear-gradient(135deg, #059669 0%, #10b981 100%);
                color: white;
                padding: 32px 24px;
                text-align: center;
                position: relative;
            }

            .save-buttons {
                position: absolute;
                top: 16px;
                right: 16px;
                display: flex;
                gap: 8px;
            }

            .save-btn {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
                white-space: nowrap;
            }

            .save-btn:hover {
                background: rgba(255, 255, 255, 0.3);
                border-color: rgba(255, 255, 255, 0.5);
                transform: translateY(-1px);
            }

            .save-btn:active {
                transform: translateY(0);
            }

            .save-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }

            .header-title {
                font-size: 22px;
                font-weight: 700;
                margin: 0 0 20px 0;
            }

            .header-info {
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

            .feed-group {
                margin-bottom: 32px;
            }

            .feed-group:last-child {
                margin-bottom: 0;
            }

            .feed-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 16px;
                padding-bottom: 8px;
                border-bottom: 2px solid #10b981;
            }

            .feed-name {
                font-size: 16px;
                font-weight: 600;
                color: #059669;
            }

            .feed-count {
                color: #666;
                font-size: 13px;
                font-weight: 500;
            }

            .rss-item {
                margin-bottom: 16px;
                padding: 16px;
                background: #f9fafb;
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
                margin-bottom: 8px;
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
                font-size: 15px;
                line-height: 1.5;
                color: #1a1a1a;
                margin: 0 0 8px 0;
                font-weight: 500;
            }

            .rss-link {
                color: #2563eb;
                text-decoration: none;
            }

            .rss-link:hover {
                text-decoration: underline;
            }

            .rss-link:visited {
                color: #7c3aed;
            }

            .rss-summary {
                font-size: 13px;
                color: #6b7280;
                line-height: 1.6;
                margin: 0;
                display: -webkit-box;
                -webkit-line-clamp: 3;
                -webkit-box-orient: vertical;
                overflow: hidden;
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
                color: #059669;
                text-decoration: none;
                font-weight: 500;
                transition: color 0.2s ease;
            }

            .footer-link:hover {
                color: #10b981;
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
                .rss-meta { gap: 8px; }
                .rss-item { padding: 12px; }
                .save-buttons {
                    position: static;
                    margin-bottom: 16px;
                    display: flex;
                    gap: 8px;
                    justify-content: center;
                    flex-direction: column;
                    width: 100%;
                }
                .save-btn {
                    width: 100%;
                }
            }
        </style>
    </head>
    <body>"""

    html += f"""
        <div class="container">
            <div class="header">
                <div class="save-buttons">
                    <button class="save-btn" onclick="saveAsImage()">{t("save_as_image", language)}</button>
                </div>
                <div class="header-title">{t("rss_report_title", language)}</div>
                <div class="header-info">
                    <div class="info-item">
                        <span class="info-label">{t("info_subscription_items", language)}</span>
                        <span class="info-value">"""

    html += f"{total_count} {t('count_unit', language)}"

    html += f"""</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">{t("info_generated_at", language)}</span>
                        <span class="info-value">"""

    # Utilise la fonction de temps fournie ou datetime.now par défaut
    if get_time_func:
        now = get_time_func()
    else:
        now = datetime.now()
    html += now.strftime("%m-%d %H:%M")

    html += """</span>
                    </div>
                </div>
            </div>

            <div class="content">"""

    # Regroupe par feed_id
    feeds_map: Dict[str, List[Dict]] = {}
    for item in rss_items:
        feed_id = item.get("feed_id", "unknown")
        if feed_id not in feeds_map:
            feeds_map[feed_id] = []
        feeds_map[feed_id].append(item)

    # Rend le contenu de chaque source RSS
    for feed_id, items in feeds_map.items():
        feed_name = items[0].get("feed_name", feed_id) if items else feed_id
        if feeds_info and feed_id in feeds_info:
            feed_name = feeds_info[feed_id]

        escaped_feed_name = html_escape(feed_name)

        html += f"""
                <div class="feed-group">
                    <div class="feed-header">
                        <div class="feed-name">{escaped_feed_name}</div>
                        <div class="feed-count">{len(items)} {t("count_unit", language)}</div>
                    </div>"""

        for item in items:
            raw_title = item.get("title", "")
            if not raw_title or not raw_title.strip():
                raw_title = item.get("url", "") or item.get("feed_name", "")
            escaped_title = html_escape(raw_title)
            url = item.get("url", "")
            published_at = item.get("published_at", "")
            author = item.get("author", "")
            summary = item.get("summary", "")

            html += """
                    <div class="rss-item">
                        <div class="rss-meta">"""

            if published_at:
                html += f'<span class="rss-time">{html_escape(published_at)}</span>'

            if author:
                html += f'<span class="rss-author">by {html_escape(author)}</span>'

            html += """
                        </div>
                        <div class="rss-title">"""

            if url:
                escaped_url = html_escape(url)
                html += f'<a href="{escaped_url}" target="_blank" class="rss-link">{escaped_title}</a>'
            else:
                html += escaped_title

            html += """
                        </div>"""

            if summary:
                escaped_summary = html_escape(summary)
                html += f"""
                        <p class="rss-summary">{escaped_summary}</p>"""

            html += """
                    </div>"""

        html += """
                </div>"""

    html += f"""
            </div>

            <div class="footer">
                <div class="footer-content">
                    {t("footer_generated_by", language)} <span class="project-name">TrendRadar</span> ·
                    <a href="https://github.com/sansan0/TrendRadar" target="_blank" class="footer-link">
                        {t("footer_github_project", language)}
                    </a>
                </div>
            </div>
        </div>"""

    html += f"""
        <script>
            var I18N = {{
                "generating": {_json_str(t("js_generating", language))},
                "saveSuccess": {_json_str(t("js_save_success", language))},
                "saveFailed": {_json_str(t("js_save_failed", language))},
                "screenshotLabel": {_json_str(t("screenshot_rss_filename_label", language))}
            }};
        </script>"""

    html += """
        <script>
            async function saveAsImage() {
                const button = event.target;
                const originalText = button.textContent;

                try {
                    button.textContent = I18N.generating;
                    button.disabled = true;
                    window.scrollTo(0, 0);

                    await new Promise(resolve => setTimeout(resolve, 200));

                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'hidden';

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

                    const link = document.createElement('a');
                    const now = new Date();
                    const filename = `TrendRadar_${I18N.screenshotLabel}_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}.png`;

                    link.download = filename;
                    link.href = canvas.toDataURL('image/png', 1.0);

                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);

                    button.textContent = I18N.saveSuccess;
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);

                } catch (error) {
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'visible';
                    button.textContent = I18N.saveFailed;
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);
                }
            }

            document.addEventListener('DOMContentLoaded', function() {
                window.scrollTo(0, 0);
            });
        </script>
    </body>
    </html>
    """

    return html
