# coding=utf-8
"""
Module de formatage des titres par plateforme.

Fournit les fonctions de formatage des titres pour plusieurs plateformes.
"""

from typing import Dict

from trendradar.report.helpers import clean_title, html_escape, format_rank_display


def format_title_for_platform(
    platform: str, title_data: Dict, show_source: bool = True, show_keyword: bool = False
) -> str:
    """Méthode unifiée de formatage des titres.

    Génère une chaîne de titre au format adapté à chaque plateforme.

    Args:
        platform: plateforme cible, valeurs supportées :
            - "feishu" : Feishu
            - "dingtalk" : DingTalk
            - "wework" : WeCom
            - "bark" : Bark
            - "telegram" : Telegram
            - "ntfy" : ntfy
            - "slack" : Slack
            - "html" : rapport HTML
        title_data: dictionnaire des données du titre, contenant les champs suivants :
            - title : texte du titre
            - source_name : nom de la source
            - time_display : affichage de l'heure
            - count : nombre d'occurrences
            - ranks : liste des classements
            - rank_threshold : seuil de mise en évidence
            - url : lien pour ordinateur de bureau
            - mobile_url : lien pour mobile (utilisé en priorité)
            - is_new : indique s'il s'agit d'un nouveau titre (optionnel)
            - matched_keyword : mot-clé correspondant (optionnel, utilisé en mode platform)
        show_source: indique s'il faut afficher le nom de la source (utilisé en mode keyword)
        show_keyword: indique s'il faut afficher l'étiquette du mot-clé (utilisé en mode platform)

    Returns:
        chaîne du titre formatée
    """
    rank_display = format_rank_display(
        title_data["ranks"], title_data["rank_threshold"], platform,
        rank_timeline=title_data.get("rank_timeline"),
    )

    link_url = title_data["mobile_url"] or title_data["url"]
    cleaned_title = clean_title(title_data["title"])
    if not cleaned_title:
        cleaned_title = link_url or title_data["url"] or ""

    # Récupère l'étiquette du mot-clé (utilisée en mode platform)
    keyword = title_data.get("matched_keyword", "") if show_keyword else ""

    if platform == "feishu":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"<font color='grey'>[{title_data['source_name']}]</font> {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"<font color='blue'>[{keyword}]</font> {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <font color='grey'>- {title_data['time_display']}</font>"
        if title_data["count"] > 1:
            result += f" <font color='green'>({title_data['count']} fois)</font>"

        return result

    elif platform == "dingtalk":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"[{keyword}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']} fois)"

        return result

    elif platform in ("wework", "bark"):
        # WeCom et Bark utilisent le format markdown
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"[{keyword}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']} fois)"

        return result

    elif platform == "telegram":
        if link_url:
            formatted_title = f'<a href="{link_url}">{html_escape(cleaned_title)}</a>'
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"<b>[{html_escape(keyword)}]</b> {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <code>- {title_data['time_display']}</code>"
        if title_data["count"] > 1:
            result += f" <code>({title_data['count']} fois)</code>"

        return result

    elif platform == "ntfy":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"[{keyword}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" `- {title_data['time_display']}`"
        if title_data["count"] > 1:
            result += f" `({title_data['count']} fois)`"

        return result

    elif platform == "slack":
        # Slack utilise le format mrkdwn
        if link_url:
            # Format de lien Slack : <url|text>
            formatted_title = f"<{link_url}|{cleaned_title}>"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        elif show_keyword and keyword:
            result = f"*[{keyword}]* {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        # Classement (mis en gras avec *)
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "slack",
            rank_timeline=title_data.get("rank_timeline"),
        )
        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" `- {title_data['time_display']}`"
        if title_data["count"] > 1:
            result += f" `({title_data['count']} fois)`"

        return result

    elif platform == "html":
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "html",
            rank_timeline=title_data.get("rank_timeline"),
        )

        link_url = title_data["mobile_url"] or title_data["url"]

        escaped_title = html_escape(cleaned_title)
        escaped_source_name = html_escape(title_data["source_name"])

        # Construit le préfixe (source ou mot-clé)
        if show_source:
            prefix = f'<span class="source-tag">[{escaped_source_name}]</span> '
        elif show_keyword and keyword:
            escaped_keyword = html_escape(keyword)
            prefix = f'<span class="keyword-tag">[{escaped_keyword}]</span> '
        else:
            prefix = ""

        if link_url:
            escaped_url = html_escape(link_url)
            formatted_title = f'{prefix}<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
        else:
            formatted_title = f'{prefix}<span class="no-link">{escaped_title}</span>'

        if rank_display:
            formatted_title += f" {rank_display}"
        if title_data["time_display"]:
            escaped_time = html_escape(title_data["time_display"])
            formatted_title += f" <font color='grey'>- {escaped_time}</font>"
        if title_data["count"] > 1:
            formatted_title += f" <font color='green'>({title_data['count']} fois)</font>"

        if title_data.get("is_new"):
            formatted_title = f"<div class='new-title'>🆕 {formatted_title}</div>"

        return formatted_title

    else:
        return cleaned_title
