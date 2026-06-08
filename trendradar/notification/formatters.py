# coding=utf-8
"""
Module de conversion de format du contenu des notifications

Fournit la conversion de format entre les différentes plateformes d'envoi
"""

import re


def strip_markdown(text: str) -> str:
    """Supprime la syntaxe markdown d'un texte, pour l'envoi via WeChat personnel

    Args:
        text: texte contenant du format markdown

    Returns:
        contenu en texte brut
    """
    # convertit les liens [text](url) -> text url (conserve l'URL)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 \2', text)

    # protège d'abord les URL pour éviter que le nettoyage markdown suivant n'altère
    # les caractères comme les tirets bas à l'intérieur des liens
    protected_urls: list[str] = []

    def _protect_url(match: re.Match) -> str:
        protected_urls.append(match.group(0))
        return f"@@URLTOKEN{len(protected_urls) - 1}@@"

    text = re.sub(r'https?://[^\s<>\]]+', _protect_url, text)

    # supprime le gras **text** ou __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'(?<!\w)__(?!\s)(.+?)(?<!\s)__(?!\w)', r'\1', text)

    # supprime l'italique *text* ou _text_
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)', r'\1', text)

    # supprime le barré ~~text~~
    text = re.sub(r'~~(.+?)~~', r'\1', text)

    # supprime les images ![alt](url) -> alt
    text = re.sub(r'!\[(.+?)\]\(.+?\)', r'\1', text)

    # supprime le code en ligne `code`
    text = re.sub(r'`(.+?)`', r'\1', text)

    # supprime le symbole de citation >
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)

    # supprime les symboles de titre # ## ### etc.
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)

    # supprime les séparateurs horizontaux --- ou ***
    text = re.sub(r'^[\-\*]{3,}\s*$', '', text, flags=re.MULTILINE)

    # supprime les balises HTML <font color='xxx'>text</font> -> text
    text = re.sub(r'<font[^>]*>(.+?)</font>', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)

    # nettoie les lignes vides superflues (conserve au plus deux lignes vides consécutives)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # restaure les URL protégées précédemment
    for idx, url in enumerate(protected_urls):
        text = text.replace(f"@@URLTOKEN{idx}@@", url)

    return text.strip()


def convert_markdown_to_mrkdwn(content: str) -> str:
    """
    Convertit du Markdown standard au format mrkdwn de Slack

    Règles de conversion :
    - **gras** → *gras*
    - [texte](url) → <url|texte>
    - conserve les autres formats (blocs de code, listes, etc.)

    Args:
        content: contenu au format Markdown

    Returns:
        contenu au format mrkdwn de Slack
    """
    # 1. convertit le format des liens : [texte](url) → <url|texte>
    content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', content)

    # 2. convertit le gras : **texte** → *texte*
    content = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', content)

    return content
