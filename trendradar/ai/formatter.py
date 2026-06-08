# coding=utf-8
"""
Module de formatage des résultats d'analyse IA.

Met en forme les résultats de l'analyse IA selon le style de chaque canal de notification.
"""

import html as html_lib
import re
from .analyzer import AIAnalysisResult
from trendradar.i18n import t, ui_lang


def _escape_html(text: str) -> str:
    """Échappe les caractères spéciaux HTML pour prévenir les attaques XSS."""
    return html_lib.escape(text) if text else ""


def _format_list_content(text: str) -> str:
    """
    Formate le contenu d'une liste en garantissant un saut de ligne avant chaque numéro.
    Par exemple, convertit "1. xxx 2. yyy" en :
    1. xxx
    2. yyy
    """
    if not text:
        return ""

    # Retire les espaces de début/fin pour éviter une ligne vide si l'IA commence par un saut de ligne
    text = text.strip()

    # 0. Fusionne le numéro avec le libellé entre crochets CJK qui suit (traitement défensif)
    text = re.sub(r'(\d+\.)\s*【([^】]+)】([: : ]?)', r'\1 \2 : ', text)

    # 1. Normalisation : garantit un espace après "1."
    result = re.sub(r'(\d+)\.([^ \d])', r'\1. \2', text)

    # 2. Saut de ligne forcé : repère "chiffre." non précédé d'un saut de ligne
    #    (?!\d) exclut les numéros de version/décimaux (ex. 2.0, 3.5) pour ne pas les confondre avec des numéros de liste
    result = re.sub(r'(?<=[^\n])\s+(\d+\.)(?!\d)', r'\n\1', result)

    # 3. Traite le cas "1.**gras**" (le prompt interdit le Markdown, traitement défensif)
    result = re.sub(r'(?<=[^\n])(\d+\.\*\*)', r'\n\1', result)

    # 4. Saut de ligne après la ponctuation CJK ou occidentale (exclut versions/décimaux)
    result = re.sub(r'([ : :;,.  ; , ])\s*(\d+\.)(?!\d)', r'\1\n\2', result)

    # 5. Saut de ligne pour les sous-titres CJK historiques terminés par un deux-points
    result = re.sub(r'([.  !  ?  ; , , ])\s*([a-zA-Z0-9\u4e00-\u9fa5]+(\u65b9\u9762|\u9886\u57df)[: : ])', r'\1\n\2', result)

    # 6. Traite le format de libellé entre crochets CJK 【...】
    # 6a. Garantit une ligne vide avant le libellé (sauf en début de texte)
    result = re.sub(r'(?<=\S)\n*(【[^】]+】)', r'\n\n\1', result)
    # 6b. Recolle le libellé et le deux-points séparé par un saut de ligne
    result = re.sub(r'(【[^】]+】)\n+([: : ])', r'\1\2', result)
    # 6c. Après le libellé (deux-points optionnel), passe à la ligne si du contenu non vide suit
    result = re.sub(r'(【[^】]+】[: : ]?)[ \t]*(?=[^\s: : ])', r'\1\n', result)

    # 7. Ajoute une ligne vide visuelle entre les éléments de liste (exclut versions/décimaux)
    result = re.sub(r'(?<![: : 】])\n(\d+\.)(?!\d)', r'\n\n\1', result)

    return result


def _format_standalone_summaries(summaries: dict) -> str:
    """Formate les résumés de la zone d'affichage autonome en lignes de texte brut, un nom de source par ligne."""
    if not summaries:
        return ""
    lines = []
    for source_name, summary in summaries.items():
        if summary:
            lines.append(f"[{source_name}]:\n{summary}")
    return "\n\n".join(lines)


def _ai_blocks(result: AIAnalysisResult, lang: str):
    """Renvoie la liste des (clé i18n, contenu) à afficher, dans l'ordre."""
    blocks = []
    if result.core_trends:
        blocks.append(("ai_core_trends", result.core_trends))
    if result.sentiment_controversy:
        blocks.append(("ai_sentiment_controversy", result.sentiment_controversy))
    if result.signals:
        blocks.append(("ai_signals", result.signals))
    if result.rss_insights:
        blocks.append(("ai_rss_insights", result.rss_insights))
    if result.outlook_strategy:
        blocks.append(("ai_outlook_strategy", result.outlook_strategy))
    return blocks


def render_ai_analysis_markdown(result: AIAnalysisResult, lang: str = None) -> str:
    """Rend au format Markdown générique (Telegram, WeCom, ntfy, Bark, Slack)."""
    lang = lang or ui_lang()
    if not result.success:
        if result.skipped:
            return f"ℹ️ {result.error}"
        return f"⚠️ {t('ai_failed', lang)}: {result.error}"

    lines = [f"**{t('ai_title', lang)}**", ""]

    for key, content in _ai_blocks(result, lang):
        lines.extend([f"**{t(key, lang)}**", _format_list_content(content), ""])

    if result.standalone_summaries:
        summaries_text = _format_standalone_summaries(result.standalone_summaries)
        if summaries_text:
            lines.extend([f"**{t('ai_standalone_summaries', lang)}**", summaries_text])

    return "\n".join(lines)


def render_ai_analysis_feishu(result: AIAnalysisResult, lang: str = None) -> str:
    """Rend au format Markdown de carte Feishu."""
    lang = lang or ui_lang()
    if not result.success:
        if result.skipped:
            return f"ℹ️ {result.error}"
        return f"⚠️ {t('ai_failed', lang)}: {result.error}"

    lines = [f"**{t('ai_title', lang)}**", ""]

    for key, content in _ai_blocks(result, lang):
        lines.extend([f"**{t(key, lang)}**", _format_list_content(content), ""])

    if result.standalone_summaries:
        summaries_text = _format_standalone_summaries(result.standalone_summaries)
        if summaries_text:
            lines.extend([f"**{t('ai_standalone_summaries', lang)}**", summaries_text])

    return "\n".join(lines)


def render_ai_analysis_dingtalk(result: AIAnalysisResult, lang: str = None) -> str:
    """Rend au format Markdown DingTalk."""
    lang = lang or ui_lang()
    if not result.success:
        if result.skipped:
            return f"ℹ️ {result.error}"
        return f"⚠️ {t('ai_failed', lang)}: {result.error}"

    lines = [f"### {t('ai_title', lang)}", ""]

    for key, content in _ai_blocks(result, lang):
        lines.extend([f"#### {t(key, lang)}", _format_list_content(content), ""])

    if result.standalone_summaries:
        summaries_text = _format_standalone_summaries(result.standalone_summaries)
        if summaries_text:
            lines.extend([f"#### {t('ai_standalone_summaries', lang)}", summaries_text])

    return "\n".join(lines)


def render_ai_analysis_plain(result: AIAnalysisResult, lang: str = None) -> str:
    """Rend au format texte brut."""
    lang = lang or ui_lang()
    if not result.success:
        if result.skipped:
            return result.error
        return f"{t('ai_failed', lang)}: {result.error}"

    lines = [f"[{t('ai_title', lang)}]", ""]

    for key, content in _ai_blocks(result, lang):
        lines.extend([f"[{t(key, lang)}]", _format_list_content(content), ""])

    if result.standalone_summaries:
        summaries_text = _format_standalone_summaries(result.standalone_summaries)
        if summaries_text:
            lines.extend([f"[{t('ai_standalone_summaries', lang)}]", summaries_text])

    return "\n".join(lines)


def render_ai_analysis_telegram(result: AIAnalysisResult, lang: str = None) -> str:
    """Rend au format HTML Telegram (avec parse_mode: HTML).

    Le mode HTML de l'API Telegram Bot ne supporte que des balises limitées :
    <b>, <i>, <u>, <s>, <code>, <pre>, <a href="">, <blockquote>.
    Les sauts de ligne utilisent directement \\n ; <br>, <div>, <h1>-<h6>, etc. ne sont pas supportés.
    """
    lang = lang or ui_lang()
    if not result.success:
        if result.skipped:
            return f"ℹ️ {_escape_html(result.error)}"
        return f"⚠️ {t('ai_failed', lang)}: {_escape_html(result.error)}"

    lines = [f"<b>{t('ai_title', lang)}</b>", ""]

    for key, content in _ai_blocks(result, lang):
        lines.extend([f"<b>{t(key, lang)}</b>", _escape_html(_format_list_content(content)), ""])

    if result.standalone_summaries:
        summaries_text = _format_standalone_summaries(result.standalone_summaries)
        if summaries_text:
            lines.extend([f"<b>{t('ai_standalone_summaries', lang)}</b>", _escape_html(summaries_text)])

    return "\n".join(lines)


def get_ai_analysis_renderer(channel: str):
    """Renvoie la fonction de rendu correspondant au canal."""
    renderers = {
        "feishu": render_ai_analysis_feishu,
        "dingtalk": render_ai_analysis_dingtalk,
        "wework": render_ai_analysis_markdown,
        "telegram": render_ai_analysis_telegram,
        "email": render_ai_analysis_html_rich,  # l'e-mail utilise le style riche, avec le CSS du rapport HTML
        "ntfy": render_ai_analysis_markdown,
        "bark": render_ai_analysis_plain,
        "slack": render_ai_analysis_markdown,
    }
    return renderers.get(channel, render_ai_analysis_markdown)


def render_ai_analysis_html_rich(result: AIAnalysisResult, language: str = "fr") -> str:
    """Rend au format HTML riche (pour le rapport HTML)."""
    if not result:
        return ""

    # Vérifie le succès
    if not result.success:
        if result.skipped:
            return f"""
                <div class="ai-section">
                    <div class="ai-info">ℹ️ {_escape_html(str(result.error))}</div>
                </div>"""
        error_msg = result.error or t("ai_unknown_error", language)
        return f"""
                <div class="ai-section">
                    <div class="ai-warning">{t("ai_failed", language)}: {_escape_html(str(error_msg))}</div>
                </div>"""

    ai_html = f"""
                <div class="ai-section">
                    <div class="ai-section-header">
                        <div class="ai-section-title">{t("ai_title", language)}</div>
                        <span class="ai-section-badge">{t("ai_badge", language)}</span>
                    </div>
                    <div class="ai-blocks-grid">"""

    for key, content in _ai_blocks(result, language):
        formatted = _format_list_content(content)
        content_html = _escape_html(formatted).replace("\n", "<br>")
        ai_html += f"""
                    <div class="ai-block">
                        <div class="ai-block-title">{t(key, language)}</div>
                        <div class="ai-block-content">{content_html}</div>
                    </div>"""

    if result.standalone_summaries:
        summaries_text = _format_standalone_summaries(result.standalone_summaries)
        if summaries_text:
            summaries_html = _escape_html(summaries_text).replace("\n", "<br>")
            ai_html += f"""
                    <div class="ai-block">
                        <div class="ai-block-title">{t("ai_standalone_summaries", language)}</div>
                        <div class="ai-block-content">{summaries_html}</div>
                    </div>"""

    ai_html += """
                    </div>
                </div>"""
    return ai_html
