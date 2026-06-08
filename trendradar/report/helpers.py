# coding=utf-8
"""
Module des fonctions auxiliaires du rapport.

Fournit les fonctions auxiliaires génériques liées à la génération des rapports.
"""

import re
from typing import Dict, List, Optional


def clean_title(title: str) -> str:
    """Nettoie les caractères spéciaux d'un titre.

    Règles de nettoyage :
    - remplace les retours à la ligne (\n, \r) par des espaces
    - fusionne les suites de caractères blancs consécutifs en un seul espace
    - supprime les espaces en début et en fin de chaîne

    Args:
        title: chaîne du titre d'origine

    Returns:
        chaîne du titre nettoyée
    """
    if not isinstance(title, str):
        title = str(title)
    cleaned_title = title.replace("\n", " ").replace("\r", " ")
    cleaned_title = re.sub(r"\s+", " ", cleaned_title)
    cleaned_title = cleaned_title.strip()
    return cleaned_title


def html_escape(text: str) -> str:
    """Échappe les caractères spéciaux HTML.

    Règles d'échappement (dans l'ordre) :
    - & → &amp;
    - < → &lt;
    - > → &gt;
    - " → &quot;
    - ' → &#x27;

    Args:
        text: texte d'origine

    Returns:
        texte échappé
    """
    if not isinstance(text, str):
        text = str(text)

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def calculate_rank_trend(rank_timeline=None, ranks=None):
    """Calcule le sens de la tendance à partir de la chronologie ou de la liste des classements.

    Args:
        rank_timeline: liste des classements enregistrés dans l'ordre chronologique, par exemple [{"time": "10:00", "rank": 5}, ...]
        ranks: liste des classements

    Returns:
        "up" (le classement monte, la valeur diminue), "down" (le classement baisse, la valeur augmente), ou None
    """
    prev_rank = None
    curr_rank = None

    if rank_timeline:
        valid_ranks = [r["rank"] for r in rank_timeline if r.get("rank") is not None]
        if len(valid_ranks) >= 2:
            prev_rank = valid_ranks[-2]
            curr_rank = valid_ranks[-1]
    elif ranks and len(ranks) >= 2:
        prev_rank = ranks[-2]
        curr_rank = ranks[-1]

    if prev_rank is not None and curr_rank is not None:
        if curr_rank < prev_rank:
            return "up"
        elif curr_rank > prev_rank:
            return "down"
    return None


def format_rank_display(
    ranks: List[int],
    rank_threshold: int,
    format_type: str,
    rank_timeline: Optional[List[Dict]] = None,
) -> str:
    """Formate l'affichage du classement.

    Génère une chaîne de classement au format adapté à chaque plateforme.
    Lorsque le classement minimal est inférieur ou égal au seuil, un format de mise en évidence est utilisé.

    Args:
        ranks: liste des classements (valeurs uniques après déduplication, sert à l'affichage d'une plage)
        rank_threshold: seuil de mise en évidence ; les classements inférieurs ou égaux à cette valeur sont mis en évidence
        format_type: type de plateforme, valeurs supportées :
            - "html" : format HTML
            - "feishu" : format Feishu
            - "dingtalk" : format DingTalk
            - "wework" : format WeCom
            - "telegram" : format Telegram
            - "slack" : format Slack
            - autre : format markdown par défaut
        rank_timeline: liste des classements enregistrés dans l'ordre chronologique (optionnel, sert à calculer la tendance)

    Returns:
        chaîne du classement formatée, par exemple "[1]" ou "[1 - 5]"
        si la liste des classements est vide, renvoie une chaîne vide
    """
    if not ranks:
        return ""

    unique_ranks = sorted(set(ranks))
    min_rank = unique_ranks[0]
    max_rank = unique_ranks[-1]

    # Choisit le format de mise en évidence selon le type de plateforme
    if format_type == "html":
        highlight_start = "<font color='red'><strong>"
        highlight_end = "</strong></font>"
    elif format_type == "feishu":
        highlight_start = "<font color='red'>**"
        highlight_end = "**</font>"
    elif format_type == "dingtalk":
        highlight_start = "**"
        highlight_end = "**"
    elif format_type == "wework":
        highlight_start = "**"
        highlight_end = "**"
    elif format_type == "telegram":
        highlight_start = "<b>"
        highlight_end = "</b>"
    elif format_type == "slack":
        highlight_start = "*"
        highlight_end = "*"
    else:
        # format markdown par défaut
        highlight_start = "**"
        highlight_end = "**"

    # Génère l'affichage du classement
    rank_str = ""
    if min_rank <= rank_threshold:
        if min_rank == max_rank:
            rank_str = f"{highlight_start}[{min_rank}]{highlight_end}"
        else:
            rank_str = f"{highlight_start}[{min_rank} - {max_rank}]{highlight_end}"
    else:
        if min_rank == max_rank:
            rank_str = f"[{min_rank}]"
        else:
            rank_str = f"[{min_rank} - {max_rank}]"

    trend = calculate_rank_trend(rank_timeline, ranks)
    trend_arrow = {"up": "📈", "down": "📉"}.get(trend, "")

    return f"{rank_str} {trend_arrow}" if trend_arrow else rank_str
