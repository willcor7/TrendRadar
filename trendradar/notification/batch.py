# coding=utf-8
"""
Module de traitement par lots

Fournit des fonctions auxiliaires pour l'envoi des messages par lots
"""

from typing import List


def get_batch_header(format_type: str, batch_num: int, total_batches: int) -> str:
    """Génère l'en-tête de lot au format correspondant selon format_type

    Args:
        format_type: type d'envoi (telegram, slack, wework_text, bark, feishu, dingtalk, ntfy, wework)
        batch_num: numéro du lot courant
        total_batches: nombre total de lots

    Returns:
        chaîne de l'en-tête de lot formatée
    """
    if format_type == "telegram":
        return f"<b>[n° {batch_num}/{total_batches} lot]</b>\n\n"
    elif format_type == "slack":
        return f"*[n° {batch_num}/{total_batches} lot]*\n\n"
    elif format_type in ("wework_text", "bark"):
        # le mode texte de WeCom et Bark utilisent le format texte brut
        return f"[n° {batch_num}/{total_batches} lot]\n\n"
    else:
        # Feishu, DingTalk, ntfy, mode markdown de WeCom
        return f"**[n° {batch_num}/{total_batches} lot]**\n\n"


def get_max_batch_header_size(format_type: str) -> int:
    """Estime le nombre d'octets maximal de l'en-tête de lot (en supposant au plus 99 lots)

    Sert à réserver de l'espace lors du découpage en lots, afin d'éviter qu'une troncature
    ultérieure ne compromette l'intégrité du contenu.

    Args:
        format_type: type d'envoi

    Returns:
        nombre d'octets maximal de l'en-tête
    """
    # génère l'en-tête du pire cas (lot 99/99)
    max_header = get_batch_header(format_type, 99, 99)
    return len(max_header.encode("utf-8"))


def truncate_to_bytes(text: str, max_bytes: int) -> str:
    """Tronque une chaîne en toute sécurité au nombre d'octets indiqué, sans couper un caractère multioctet

    Args:
        text: texte à tronquer
        max_bytes: nombre d'octets maximal

    Returns:
        texte tronqué
    """
    text_bytes = text.encode("utf-8")
    if len(text_bytes) <= max_bytes:
        return text

    truncated = text_bytes[:max_bytes]
    for i in range(min(4, len(truncated))):
        try:
            return truncated[: len(truncated) - i].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return ""


def truncate_at_line_boundary(text: str, max_bytes: int) -> str:
    """Tronque à la limite d'une ligne, en garantissant de ne pas couper au milieu d'un titre ou d'un contenu

    Tronque d'abord par octets, puis recule jusqu'à la position du saut de ligne le plus proche,
    afin que chaque ligne reste complète.

    Args:
        text: texte à tronquer
        max_bytes: nombre d'octets maximal

    Returns:
        texte tronqué se terminant à la dernière ligne complète
    """
    if len(text.encode("utf-8")) <= max_bytes:
        return text

    rough_cut = truncate_to_bytes(text, max_bytes)
    last_newline = rough_cut.rfind("\n")
    if last_newline > 0:
        return rough_cut[:last_newline]
    return rough_cut


def truncate_preserving_footer(content: str, max_bytes: int) -> str:
    """Tronque le contenu en préservant en priorité le pied de page (footer : date de mise à jour, etc.), le corps étant tronqué à la limite d'une ligne

    Identifie la zone de pied de page (footer) en fin de contenu (date de mise à jour, mention de
    version, etc.), tronque la partie du corps précédant le footer à la limite d'une ligne,
    puis réassemble le footer complet.

    Args:
        content: contenu complet (corps + footer)
        max_bytes: nombre d'octets maximal

    Returns:
        contenu tronqué, footer conservé intégralement, corps tronqué à la limite d'une ligne
    """
    if len(content.encode("utf-8")) <= max_bytes:
        return content

    # motifs de début courants du footer pour chaque plateforme
    footer_markers = ["\n\n\n> ", "\n\n> ", "\n\n<font", "\n\n_", "\n\nMis à jour le"]
    footer_start = -1
    for marker in footer_markers:
        pos = content.rfind(marker)
        if pos > 0:
            footer_start = pos
            break

    if footer_start <= 0:
        return truncate_at_line_boundary(content, max_bytes)

    footer = content[footer_start:]
    body = content[:footer_start]
    footer_size = len(footer.encode("utf-8"))

    if footer_size >= max_bytes:
        return truncate_at_line_boundary(content, max_bytes)

    truncated_body = truncate_at_line_boundary(body, max_bytes - footer_size)
    return truncated_body + footer


def _split_oversized_batch(content: str, max_content_bytes: int) -> List[str]:
    """Découpe un lot dépassant la limite en plusieurs sous-lots aux limites de ligne (conserve le footer)

    Args:
        content: contenu du lot dépassant la limite (footer inclus)
        max_content_bytes: nombre d'octets maximal de chaque sous-lot

    Returns:
        liste des sous-lots après découpage
    """
    # identifie le footer
    footer_markers = ["\n\n\n> ", "\n\n> ", "\n\n<font", "\n\n_", "\n\nMis à jour le"]
    footer = ""
    body = content
    for marker in footer_markers:
        pos = content.rfind(marker)
        if pos > 0:
            footer = content[pos:]
            body = content[:pos]
            break

    footer_size = len(footer.encode("utf-8"))
    available = max_content_bytes - footer_size
    if available <= 0:
        return [truncate_at_line_boundary(content, max_content_bytes)]

    # découpe le corps (body) ligne par ligne
    lines = body.split("\n")
    sub_batches = []
    current = ""

    for line in lines:
        candidate = current + line + "\n"
        if len(candidate.encode("utf-8")) > available and current.strip():
            sub_batches.append(current + footer)
            current = line + "\n"
        else:
            current = candidate

    if current.strip():
        sub_batches.append(current + footer)

    return sub_batches if sub_batches else [content]


def add_batch_headers(
    batches: List[str], format_type: str, max_bytes: int
) -> List[str]:
    """Ajoute un en-tête à chaque lot et découpe en plusieurs sous-lots en cas de dépassement de limite (sans perdre de contenu)

    Args:
        batches: liste des lots d'origine
        format_type: type d'envoi (bark, telegram, feishu, etc.)
        max_bytes: limite d'octets maximale pour ce type d'envoi

    Returns:
        liste des lots après ajout des en-têtes
    """
    if len(batches) <= 1:
        return batches

    # première passe : découpe les lots dépassant la limite
    expanded = []
    max_header_size = get_max_batch_header_size(format_type)
    for content in batches:
        if len(content.encode("utf-8")) + max_header_size > max_bytes:
            expanded.extend(_split_oversized_batch(content, max_bytes - max_header_size))
        else:
            expanded.append(content)

    # deuxième passe : ajoute les en-têtes
    if len(expanded) <= 1:
        return expanded

    total = len(expanded)
    result = []
    for i, content in enumerate(expanded, 1):
        header = get_batch_header(format_type, i, total)
        header_size = len(header.encode("utf-8"))
        max_content_size = max_bytes - header_size

        if len(content.encode("utf-8")) > max_content_size:
            # toujours en dépassement (cas extrême : une seule ligne trop longue), troncature à la limite d'une ligne
            content = truncate_preserving_footer(content, max_content_size)

        result.append(header + content)

    return result
