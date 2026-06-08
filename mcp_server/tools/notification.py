# coding=utf-8
"""
Outil de notification (push)

Permet d'envoyer des messages vers les canaux de notification configurés, en détectant automatiquement la configuration des canaux dans config.yaml et .env.
Accepte du contenu au format markdown, converti automatiquement en interne au format requis par chaque canal avant l'envoi.
"""

import json
import os
import re
import smtplib
import time
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
import yaml

from trendradar.core.loader import _load_webhook_config, _load_notification_config
from trendradar.notification.batch import (
    truncate_to_bytes,
    get_batch_header,
    get_max_batch_header_size,
    add_batch_headers,
)
from trendradar.notification.formatters import strip_markdown
from trendradar.notification.senders import SMTP_CONFIGS

from ..utils.errors import MCPError, InvalidParameterError


# ==================== Règles de détermination de l'activation des canaux ====================

# Pour chaque canal, quels éléments de configuration doivent être non vides pour être considéré comme "configuré"
# Remarque : NTFY_SERVER_URL a une valeur par défaut "https://ntfy.sh" dans le loader, donc il ne sert pas de critère
_CHANNEL_REQUIREMENTS = {
    "feishu": ["FEISHU_WEBHOOK_URL"],
    "dingtalk": ["DINGTALK_WEBHOOK_URL"],
    "wework": ["WEWORK_WEBHOOK_URL"],
    "telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
    "email": ["EMAIL_FROM", "EMAIL_PASSWORD", "EMAIL_TO"],
    "ntfy": ["NTFY_TOPIC"],
    "bark": ["BARK_URL"],
    "slack": ["SLACK_WEBHOOK_URL"],
    "generic_webhook": ["GENERIC_WEBHOOK_URL"],
}

# Noms d'affichage des canaux
_CHANNEL_NAMES = {
    "feishu": "Feishu",
    "dingtalk": "DingTalk",
    "wework": "WeCom",
    "telegram": "Telegram",
    "email": "E-mail",
    "ntfy": "ntfy",
    "bark": "Bark",
    "slack": "Slack",
    "generic_webhook": "Webhook générique",
}


# ==================== Configuration du traitement par lots ====================

# Valeurs par défaut du nombre maximal d'octets par lot pour chaque canal
# Au moment de l'exécution, lues et écrasées depuis config.yaml → advanced.batch_size
_CHANNEL_BATCH_SIZES_DEFAULT = {
    "feishu": 30000,    # config.yaml: advanced.batch_size.feishu
    "dingtalk": 20000,  # config.yaml: advanced.batch_size.dingtalk
    "wework": 4000,     # config.yaml: advanced.batch_size.default
    "telegram": 4000,   # config.yaml: advanced.batch_size.default
    "email": 0,         # L'e-mail n'a pas de limite d'octets, pas de découpage en lots
    "ntfy": 3800,       # Limite stricte de 4 Ko (valeur par défaut du code ntfy)
    "bark": 4000,       # config.yaml: advanced.batch_size.bark
    "slack": 4000,      # config.yaml: advanced.batch_size.slack
    "generic_webhook": 4000,
}

# Canaux affichant les messages les plus récents en premier : les lots doivent être envoyés en ordre inverse
_REVERSE_BATCH_CHANNELS = {"ntfy", "bark"}

# Valeur par défaut de l'intervalle d'envoi entre lots (secondes), lue au moment de l'exécution depuis config.yaml → advanced.batch_send_interval
_BATCH_INTERVAL_DEFAULT = 3.0


# ==================== Traitement par lots ====================
# truncate_to_bytes, get_batch_header, get_max_batch_header_size,
# add_batch_headers réutilisés depuis trendradar.notification.batch


def _split_text_into_batches(text: str, max_bytes: int) -> List[str]:
    """Découpe le texte en lots selon une limite d'octets, en coupant en priorité aux frontières de paragraphes (double saut de ligne)

    Stratégie de découpage (s'inspire de la garantie d'atomicité de trendradar splitter.py) :
    1. Découpe d'abord par paragraphe (double saut de ligne \\n\\n)
    2. Si un paragraphe dépasse encore la limite, découpe par ligne (\\n)
    3. Si une ligne dépasse encore la limite, troncature sûre avec _truncate_to_bytes

    Args:
        text: texte déjà converti au format du canal cible
        max_bytes: nombre maximal d'octets par lot (réserve d'en-tête de lot déjà déduite)

    Returns:
        liste des textes découpés en lots
    """
    if max_bytes <= 0 or len(text.encode("utf-8")) <= max_bytes:
        return [text]

    # Découpe par paragraphe
    paragraphs = text.split("\n\n")
    batches = []
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate.encode("utf-8")) <= max_bytes:
            current = candidate
        else:
            # Le paragraphe courant ne tient pas, on enregistre d'abord le contenu existant
            if current:
                batches.append(current)
                current = ""

            # Vérifie si un seul paragraphe dépasse la limite
            if len(para.encode("utf-8")) <= max_bytes:
                current = para
            else:
                # Le paragraphe lui-même dépasse la limite, on découpe par ligne
                lines = para.split("\n")
                for line in lines:
                    candidate = f"{current}\n{line}" if current else line
                    if len(candidate.encode("utf-8")) <= max_bytes:
                        current = candidate
                    else:
                        if current:
                            batches.append(current)
                            current = ""
                        # Une ligne dépasse la limite, on tronque en boucle jusqu'à épuisement
                        if len(line.encode("utf-8")) > max_bytes:
                            remaining = line
                            while remaining:
                                chunk = truncate_to_bytes(remaining, max_bytes)
                                if not chunk:
                                    break
                                batches.append(chunk)
                                # Retire la partie déjà tronquée
                                remaining = remaining[len(chunk):]
                        else:
                            current = line

    if current:
        batches.append(current)

    return batches if batches else [text]


def _format_for_channel(message: str, channel_id: str) -> str:
    """Adapte et convertit du Markdown générique au format du canal cible

    Point d'entrée unifié : adapte d'abord (retire la syntaxe non prise en charge), puis convertit (Markdown→HTML/mrkdwn, etc.).
    Le texte retourné peut être directement utilisé pour le découpage en octets et l'envoi.

    Args:
        message: texte d'origine au format Markdown
        channel_id: ID du canal cible

    Returns:
        texte au format du canal cible
    """
    if channel_id == "feishu":
        return _adapt_markdown_for_feishu(message)
    elif channel_id == "dingtalk":
        return _adapt_markdown_for_dingtalk(message)
    elif channel_id == "wework":
        return _adapt_markdown_for_wework(message)
    elif channel_id == "telegram":
        return _markdown_to_telegram_html(message)
    elif channel_id == "ntfy":
        return _adapt_markdown_for_ntfy(message)
    elif channel_id == "bark":
        return _adapt_markdown_for_bark(message)
    elif channel_id == "slack":
        return _convert_markdown_to_slack(message)
    else:
        # email, generic_webhook : conserve le Markdown d'origine
        return message


def _prepare_batches(message: str, channel_id: str, batch_sizes: Dict = None) -> List[str]:
    """Pipeline complet de découpage en lots : adaptation du format → découpage en octets → ajout des en-têtes de lot

    Args:
        message: texte d'origine au format Markdown
        channel_id: ID du canal cible
        batch_sizes: dictionnaire des tailles de lot par canal (issu de config.yaml), None utilise les valeurs par défaut

    Returns:
        liste des lots prêts (en-têtes ajoutés, ordre inverse traité)
    """
    sizes = batch_sizes or _CHANNEL_BATCH_SIZES_DEFAULT
    max_bytes = sizes.get(channel_id, sizes.get("default", 4000))
    if max_bytes <= 0:
        # Pas de limite d'octets (comme email), retourne le texte d'origine
        return [message]

    formatted = _format_for_channel(message, channel_id)

    # Découpe après avoir réservé l'espace pour l'en-tête de lot
    header_reserve = get_max_batch_header_size(channel_id)
    batches = _split_text_into_batches(formatted, max_bytes - header_reserve)

    # Ajoute les en-têtes de lot (non ajoutés s'il n'y a qu'un seul lot)
    batches = add_batch_headers(batches, channel_id, max_bytes)

    # Envoi en ordre inverse pour ntfy/Bark (le client affiche les plus récents en premier)
    if channel_id in _REVERSE_BATCH_CHANNELS and len(batches) > 1:
        batches = list(reversed(batches))

    return batches

CHANNEL_FORMAT_GUIDES = {
    "feishu": {
        "name": "Feishu",
        "format": "Markdown (message carte)",
        "max_length": "environ 29000 octets",
        "supported": [
            "**gras**",
            "[texte du lien](URL)",
            "<font color='red/green/grey/orange/blue'>texte coloré</font>",
            "--- (ligne de séparation)",
            "saut de ligne pour séparer les paragraphes",
        ],
        "unsupported": [
            "syntaxe de titre # (non rendue comme un titre)",
            "> bloc de citation",
            "tableaux / images intégrées",
        ],
        "prompt": (
            "Stratégie de formatage Markdown pour les cartes Feishu :\n"
            "1. Utiliser **gras** pour les sous-titres et les mots importants\n"
            "2. Utiliser <font color='red'>rouge</font> pour le contenu urgent/important\n"
            "3. Utiliser <font color='grey'>gris</font> pour les informations secondaires (heure, source)\n"
            "4. Utiliser <font color='orange'>orange</font> pour les avertissements\n"
            "5. Utiliser <font color='green'>vert</font> pour les informations positives/de succès\n"
            "6. Utiliser [texte](URL) pour ajouter des liens cliquables\n"
            "7. Utiliser --- pour séparer les différentes zones thématiques\n"
            "8. Ne pas utiliser la syntaxe de titre # (non rendue dans la carte)\n"
            "9. Ne pas utiliser la syntaxe de citation >\n"
            "10. Utiliser saut de ligne + gras pour simuler une structure hiérarchique"
        ),
    },
    "dingtalk": {
        "name": "DingTalk",
        "format": "Markdown",
        "max_length": "environ 20000 octets",
        "supported": [
            "### titre de niveau 3 / #### titre de niveau 4",
            "**gras**",
            "[texte du lien](URL)",
            "> bloc de citation",
            "--- (ligne de séparation)",
            "- liste non ordonnée / 1. liste ordonnée",
        ],
        "unsupported": [
            "# titre de niveau 1 / ## titre de niveau 2 (peuvent ne pas être rendus)",
            "<font> texte coloré",
            "~~barré~~",
            "tableaux / images intégrées",
        ],
        "prompt": (
            "Stratégie de formatage Markdown pour DingTalk :\n"
            "1. Utiliser ### ou #### pour les titres de section (pas # ni ##)\n"
            "2. Utiliser **gras** pour mettre en valeur les mots-clés et les données\n"
            "3. Utiliser les blocs de citation > pour les remarques ou compléments\n"
            "4. Utiliser --- pour séparer les différentes zones thématiques\n"
            "5. Utiliser [texte](URL) pour ajouter des liens cliquables\n"
            "6. Utiliser des listes ordonnées (1. 2. 3.) pour organiser les points clés\n"
            "7. Ne pas utiliser les balises de couleur <font> (non prises en charge par DingTalk)\n"
            "8. Ne pas utiliser la syntaxe barré\n"
            "9. Ajouter une ligne vide entre titre et corps pour améliorer la lisibilité"
        ),
    },
    "wework": {
        "name": "WeCom",
        "format": "Markdown (robot de groupe) / texte brut (WeChat personnel)",
        "max_length": "environ 4000 octets",
        "supported": [
            "**gras**",
            "[texte du lien](URL)",
            "> bloc de citation (seule la première ligne est prise en compte)",
        ],
        "unsupported": [
            "syntaxe de titre #",
            "--- (ligne horizontale de séparation)",
            "<font> texte coloré",
            "~~barré~~",
            "tableaux / images intégrées / listes ordonnées",
        ],
        "prompt": (
            "Stratégie de formatage Markdown pour WeCom :\n"
            "1. Utiliser **gras** pour les sous-titres et les mots importants\n"
            "2. Utiliser [texte](URL) pour ajouter des liens cliquables\n"
            "3. Utiliser les blocs de citation > pour les remarques (seule la première ligne compte)\n"
            "4. Le contenu doit être concis, limité à 4 Ko\n"
            "5. Ne pas utiliser la syntaxe de titre # (non rendue)\n"
            "6. Ne pas utiliser --- (non rendu), utiliser plusieurs sauts de ligne pour séparer les zones\n"
            "7. Ne pas utiliser les balises de couleur <font>\n"
            "8. Ne pas utiliser le barré ni les listes ordonnées\n"
            "9. Utiliser saut de ligne + gras pour simuler une structure hiérarchique\n"
            "10. En mode WeChat personnel, tout le formatage est réduit en texte brut"
        ),
    },
    "telegram": {
        "name": "Telegram",
        "format": "HTML (converti automatiquement depuis le Markdown)",
        "max_length": "environ 4096 caractères",
        "supported": [
            "<b>gras</b> (converti depuis **gras**)",
            "<i>italique</i> (converti depuis *italique*)",
            "<s>barré</s> (converti depuis ~~barré~~)",
            "<code>code en ligne</code> (converti depuis `code`)",
            "<a href='URL'>lien</a> (converti depuis [texte](URL))",
            "<blockquote>bloc de citation</blockquote> (converti depuis > citation)",
        ],
        "unsupported": [
            "syntaxe de titre # (préfixe # retiré automatiquement)",
            "--- (ligne de séparation, retirée automatiquement)",
            "<font> texte coloré (retiré automatiquement)",
            "tableaux / images intégrées",
        ],
        "prompt": (
            "Stratégie de formatage HTML pour Telegram (l'entrée reste en Markdown, convertie automatiquement en HTML) :\n"
            "1. Utiliser **gras** pour mettre en valeur les mots-clés (converti en <b>)\n"
            "2. Utiliser *italique* pour les informations secondaires (converti en <i>)\n"
            "3. Utiliser `code` pour marquer les valeurs/heures (converti en <code>)\n"
            "4. Utiliser [texte](URL) pour ajouter des liens (converti en <a>)\n"
            "5. Utiliser des lignes commençant par > comme blocs de citation (convertis en <blockquote>)\n"
            "6. Ne pas utiliser de titres # (Telegram n'a pas de style de titre, seul # est retiré)\n"
            "7. Ne pas utiliser de lignes de séparation --- (retirées), utiliser des lignes vides pour séparer\n"
            "8. Ne pas utiliser les balises de couleur <font> (retirées)\n"
            "9. Le contenu est limité à 4096 caractères, rester concis\n"
            "10. L'aperçu des liens est désactivé par défaut, adapté aux messages denses en informations"
        ),
    },
    "email": {
        "name": "E-mail",
        "format": "HTML (page web complète, convertie depuis le Markdown)",
        "max_length": "pas de limite stricte",
        "supported": [
            "titres # / ## / ### (convertis en <h1>/<h2>/<h3>)",
            "**gras** / *italique* / ~~barré~~",
            "[texte du lien](URL)",
            "`code en ligne`",
            "--- (ligne horizontale de séparation)",
        ],
        "unsupported": [
            "<font> texte coloré (affiché échappé)",
            "tableaux complexes",
        ],
        "prompt": (
            "Stratégie de formatage HTML pour l'e-mail (l'entrée est en Markdown, convertie automatiquement en HTML stylé) :\n"
            "1. Utiliser # / ## / ### pour créer une hiérarchie de titres claire\n"
            "2. Utiliser **gras** et *italique* pour améliorer la lisibilité\n"
            "3. Utiliser [texte](URL) pour ajouter des liens (bleus et cliquables)\n"
            "4. Utiliser --- pour séparer les différentes sections\n"
            "5. Utiliser `code` pour marquer les termes techniques ou les données\n"
            "6. Vous pouvez écrire un contenu plus long, l'e-mail n'a pas de limite stricte de longueur\n"
            "7. La date et l'heure sont automatiquement ajoutées à l'objet de l'e-mail\n"
            "8. Une version texte brut de secours est jointe automatiquement"
        ),
    },
    "ntfy": {
        "name": "ntfy",
        "format": "Markdown (pris en charge nativement)",
        "max_length": "environ 3800 octets (limite de 4 Ko par message)",
        "supported": [
            "**gras** / *italique*",
            "[texte du lien](URL)",
            "> bloc de citation",
            "`code en ligne`",
            "- liste",
        ],
        "unsupported": [
            "syntaxe de titre # (le rendu dépend du client)",
            "<font> texte coloré",
            "--- (le rendu dépend du client)",
            "tableaux",
        ],
        "prompt": (
            "Stratégie de formatage Markdown pour ntfy :\n"
            "1. Utiliser **gras** pour mettre en valeur les mots-clés\n"
            "2. Utiliser [texte](URL) pour ajouter des liens cliquables\n"
            "3. Utiliser les blocs de citation > pour les remarques\n"
            "4. Utiliser `code` pour marquer les valeurs\n"
            "5. Le contenu doit être concis, limité à 4 Ko\n"
            "6. Ne pas utiliser les balises de couleur <font> (sans effet)\n"
            "7. Ne pas dépendre des titres # ni des lignes de séparation ---\n"
            "8. Utiliser lignes vides et gras pour organiser la hiérarchie des informations"
        ),
    },
    "bark": {
        "name": "Bark",
        "format": "Markdown (notification push iOS)",
        "max_length": "environ 3600 octets (limite APNs de 4 Ko)",
        "supported": [
            "**gras**",
            "[texte du lien](URL)",
            "formatage de texte de base",
        ],
        "unsupported": [
            "syntaxe de titre #",
            "<font> texte coloré",
            "--- (ligne de séparation)",
            "> bloc de citation",
            "formats imbriqués complexes",
        ],
        "prompt": (
            "Stratégie de formatage Bark (notification push iOS) :\n"
            "1. Le contenu doit être extrêmement concis, contexte de lecture mobile\n"
            "2. Utiliser **gras** pour marquer les informations essentielles\n"
            "3. Utiliser [texte](URL) pour ajouter des liens\n"
            "4. Ne pas utiliser de formats complexes comme titres/couleurs/citations\n"
            "5. Soumis à la limite APNs de 4 Ko, contrôler la longueur du contenu\n"
            "6. La structure hiérarchique se fait par indentation et sauts de ligne\n"
            "7. Adapté aux notifications et résumés courts, pas aux textes longs"
        ),
    },
    "slack": {
        "name": "Slack",
        "format": "mrkdwn (format propriétaire de Slack, converti automatiquement depuis le Markdown)",
        "max_length": "environ 4000 octets",
        "supported": [
            "*gras* (converti depuis **gras**)",
            "_italique_",
            "~barré~ (converti depuis ~~barré~~)",
            "<URL|texte du lien> (converti depuis [texte](URL))",
            "`code en ligne`",
            "```bloc de code```",
            "> bloc de citation",
        ],
        "unsupported": [
            "syntaxe de titre # (réduite en gras)",
            "<font> texte coloré",
            "--- ligne de séparation (rendu instable)",
            "tableaux",
        ],
        "prompt": (
            "Stratégie de formatage mrkdwn pour Slack (l'entrée est en Markdown, convertie automatiquement en mrkdwn) :\n"
            "1. Utiliser **gras** pour mettre en valeur les mots-clés (converti en *gras*)\n"
            "2. Utiliser ~~barré~~ pour marquer les informations obsolètes (converti en ~barré~)\n"
            "3. Utiliser [texte](URL) pour ajouter des liens (converti en <URL|texte>)\n"
            "4. Utiliser les blocs de citation > pour les remarques\n"
            "5. Utiliser `code` pour marquer les valeurs\n"
            "6. Ne pas utiliser de titres # (Slack n'a pas de style de titre)\n"
            "7. Ne pas utiliser les balises de couleur <font>\n"
            "8. Utiliser lignes vides et gras pour organiser la hiérarchie des informations"
        ),
    },
    "generic_webhook": {
        "name": "Webhook générique",
        "format": "Markdown (ou modèle personnalisé)",
        "max_length": "environ 4000 octets",
        "supported": ["syntaxe Markdown standard"],
        "unsupported": ["dépend du destinataire"],
        "prompt": (
            "Stratégie de formatage pour le Webhook générique :\n"
            "1. Utiliser le format Markdown standard\n"
            "2. Éviter la syntaxe propriétaire spécifique à une plateforme\n"
            "3. Si un modèle personnalisé est configuré, le contenu remplit le placeholder {content}"
        ),
    },
}


# ==================== Adaptation Markdown par canal ====================

def _adapt_markdown_for_feishu(text: str) -> str:
    """Adapte du Markdown générique au format Markdown des cartes Feishu

    Les cartes Feishu prennent en charge : **gras**, [lien](url), <font color='...'>, ---
    Non prises en charge : titre #, > bloc de citation
    """
    # Convertit les titres # en gras (les cartes Feishu ne rendent pas la syntaxe de titre)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'**\1**', text, flags=re.MULTILINE)
    # Retire le préfixe de syntaxe de citation (non pris en charge par Feishu)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    # Nettoie les lignes vides superflues
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _adapt_markdown_for_dingtalk(text: str) -> str:
    """Adapte du Markdown générique au format Markdown de DingTalk

    DingTalk prend en charge : titres ### ####, **gras**, [lien](url), > citation, ---
    Non pris en charge : titres # ##, <font> texte coloré, ~~barré~~
    """
    # Retire les balises <font> (non prises en charge par DingTalk, conserve le contenu)
    text = re.sub(r'<font[^>]*>(.+?)</font>', r'\1', text)
    # Rétrograde les titres # et ## en ### (DingTalk ne prend en charge que ### et ####)
    text = re.sub(r'^##\s+(.+)$', r'### \1', text, flags=re.MULTILINE)
    text = re.sub(r'^#\s+(.+)$', r'### \1', text, flags=re.MULTILINE)
    # Retire la syntaxe barré (non prise en charge par DingTalk)
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    # Nettoie les lignes vides superflues
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _adapt_markdown_for_wework(text: str) -> str:
    """Adapte du Markdown générique au format Markdown de WeCom

    WeCom prend en charge : **gras**, [lien](url), > citation (limitée)
    Non pris en charge : titre #, ---, <font>, ~~barré~~, listes ordonnées
    """
    # Retire les balises <font> (conserve le contenu)
    text = re.sub(r'<font[^>]*>(.+?)</font>', r'\1', text)
    # Convertit les titres # en gras (WeCom ne rend pas la syntaxe de titre)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'**\1**', text, flags=re.MULTILINE)
    # Remplace les lignes de séparation --- par plusieurs sauts de ligne (WeCom ne rend pas les lignes horizontales)
    text = re.sub(r'^[\-\*]{3,}\s*$', '\n\n', text, flags=re.MULTILINE)
    # Retire la syntaxe barré (non prise en charge par WeCom)
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    # Nettoie les lignes vides superflues (en conserve au maximum deux)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()


def _adapt_markdown_for_ntfy(text: str) -> str:
    """Adapte du Markdown générique au format ntfy

    ntfy prend en charge : **gras**, *italique*, [lien](url), > citation, `code`
    Peu fiable : titre #, ---, <font>
    """
    # Retire les balises <font> (non prises en charge par ntfy)
    text = re.sub(r'<font[^>]*>(.+?)</font>', r'\1', text)
    # Nettoie les lignes vides superflues
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _adapt_markdown_for_bark(text: str) -> str:
    """Adapte du Markdown générique au format Bark (notification push iOS)

    Bark prend en charge : **gras**, [lien](url), texte de base
    Non pris en charge : titre #, <font>, ---, > citation, imbrication complexe
    """
    # Retire les balises <font> (conserve le contenu)
    text = re.sub(r'<font[^>]*>(.+?)</font>', r'\1', text)
    # Convertit les titres # en gras
    text = re.sub(r'^#{1,6}\s+(.+)$', r'**\1**', text, flags=re.MULTILINE)
    # Remplace --- par un saut de ligne
    text = re.sub(r'^[\-\*]{3,}\s*$', '\n', text, flags=re.MULTILINE)
    # Retire la syntaxe de citation
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    # Retire la syntaxe barré
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    # Nettoie les lignes vides superflues
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ==================== Conversion de format ====================

def _markdown_to_telegram_html(text: str) -> str:
    """
    Convertit du markdown au format HTML pris en charge par Telegram

    Balises prises en charge par Telegram : <b>, <i>, <s>, <code>, <a href="url">text</a>, <blockquote>
    """
    # Prétraitement : retire les balises <font> (non prises en charge par Telegram, conserve le contenu)
    text = re.sub(r'<font[^>]*>(.+?)</font>', r'\1', text)

    lines = text.split('\n')
    result_lines = []
    in_blockquote = False

    for line in lines:
        # Convertit les symboles de titre # ## ### en gras
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if header_match:
            line = f'**{header_match.group(2)}**'

        # Retire les lignes horizontales de séparation
        if re.match(r'^[\-\*]{3,}\s*$', line):
            if in_blockquote:
                result_lines.append('</blockquote>')
                in_blockquote = False
            line = ''

        # Traite les blocs de citation > text → <blockquote>text</blockquote>
        quote_match = re.match(r'^>\s*(.*)$', line)
        if quote_match:
            if not in_blockquote:
                result_lines.append('<blockquote>')
                in_blockquote = True
            result_lines.append(quote_match.group(1))
            continue
        elif in_blockquote:
            result_lines.append('</blockquote>')
            in_blockquote = False

        result_lines.append(line)

    if in_blockquote:
        result_lines.append('</blockquote>')

    text = '\n'.join(result_lines)

    # Échappe les entités HTML (avant le remplacement des marques, mais après les balises blockquote)
    # Traitement par segments : conserve les balises HTML déjà générées
    parts = re.split(r'(</?blockquote>)', text)
    escaped_parts = []
    for part in parts:
        if part in ('<blockquote>', '</blockquote>'):
            escaped_parts.append(part)
        else:
            part = part.replace('&', '&amp;')
            part = part.replace('<', '&lt;')
            part = part.replace('>', '&gt;')
            escaped_parts.append(part)
    text = ''.join(escaped_parts)

    # Convertit les liens [text](url) → <a href="url">text</a>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    # Convertit le gras **text** → <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # Convertit l'italique *text* → <i>text</i>
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)

    # Convertit le barré ~~text~~ → <s>text</s>
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)

    # Convertit le code en ligne `code` → <code>code</code>
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)

    # Nettoie les lignes vides superflues
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _convert_markdown_to_slack(text: str) -> str:
    """Convertit du Markdown au format mrkdwn de Slack (version améliorée)

    Différences entre mrkdwn de Slack et le Markdown standard :
    - gras : *text* (et non **text**)
    - barré : ~text~ (et non ~~text~~)
    - lien : <url|text> (et non [text](url))
    - syntaxe de titre non prise en charge
    """
    # Retire les balises <font> (conserve le contenu)
    text = re.sub(r'<font[^>]*>(.+?)</font>', r'\1', text)
    # Convertit les titres # en gras (Slack n'a pas de style de titre)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'**\1**', text, flags=re.MULTILINE)
    # Retire les lignes de séparation --- (rendu instable dans Slack)
    text = re.sub(r'^[\-\*]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Convertit le format des liens : [texte](url) → <url|texte>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', text)
    # Convertit le barré : ~~texte~~ → ~texte~
    text = re.sub(r'~~(.+?)~~', r'~\1~', text)
    # Convertit le gras : **texte** → *texte* (doit venir après le barré)
    text = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', text)
    # Nettoie les lignes vides superflues
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _markdown_to_simple_html(text: str) -> str:
    """
    Convertit du markdown en HTML simple (utilisé pour l'e-mail)
    """
    html = text

    # Échappement
    html = html.replace('&', '&amp;')
    html = html.replace('<', '&lt;')
    html = html.replace('>', '&gt;')

    # Liens
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)

    # Titres ### → <h3>
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Gras
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

    # Italique
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # Barré
    html = re.sub(r'~~(.+?)~~', r'<del>\1</del>', html)

    # Code en ligne
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)

    # Ligne de séparation
    html = re.sub(r'^[\-\*]{3,}\s*$', '<hr>', html, flags=re.MULTILINE)

    # Saut de ligne
    html = html.replace('\n', '<br>\n')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Notification TrendRadar</title>
<style>body{{font-family:sans-serif;padding:20px;max-width:800px;margin:0 auto}}
a{{color:#1a73e8}}h1,h2,h3{{color:#333}}hr{{border:none;border-top:1px solid #ddd;margin:16px 0}}
code{{background:#f5f5f5;padding:2px 6px;border-radius:3px}}</style>
</head><body>{html}</body></html>"""


# ==================== Émetteurs par canal ====================

def _send_feishu(webhook_url: str, content: str, title: str) -> Dict:
    """Envoi Feishu (message texte brut, cohérent avec trendradar send_to_feishu)

    Le webhook Feishu utilise msg_type: "text", toutes les informations sont regroupées dans content.text.
    """
    payload = {
        "msg_type": "text",
        "content": {
            "text": content,
        },
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=30)
        data = resp.json()
        ok = resp.status_code == 200 and (data.get("code") == 0 or data.get("StatusCode") == 0)
        detail = ""
        if not ok:
            detail = data.get("msg") or data.get("StatusMessage", "")
        return {"success": ok, "detail": detail}
    except Exception as e:
        return {"success": False, "detail": str(e)}


def _send_dingtalk(webhook_url: str, content: str, title: str) -> Dict:
    """Envoi DingTalk (reçoit du Markdown déjà adapté)"""
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": content}
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=30)
        data = resp.json()
        ok = resp.status_code == 200 and data.get("errcode") == 0
        return {"success": ok, "detail": data.get("errmsg", "") if not ok else ""}
    except Exception as e:
        return {"success": False, "detail": str(e)}


def _send_wework(webhook_url: str, content: str, title: str, msg_type: str = "markdown") -> Dict:
    """Envoi WeCom (reçoit du Markdown déjà adapté, le mode text retire automatiquement le formatage)"""
    if msg_type == "text":
        payload = {"msgtype": "text", "text": {"content": strip_markdown(content)}}
    else:
        payload = {"msgtype": "markdown", "markdown": {"content": content}}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=30)
        data = resp.json()
        ok = resp.status_code == 200 and data.get("errcode") == 0
        return {"success": ok, "detail": data.get("errmsg", "") if not ok else ""}
    except Exception as e:
        return {"success": False, "detail": str(e)}


def _send_telegram(bot_token: str, chat_id: str, content: str, title: str) -> Dict:
    """Envoi Telegram (reçoit du HTML déjà converti)"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": content,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        data = resp.json()
        ok = resp.status_code == 200 and data.get("ok")
        return {"success": ok, "detail": data.get("description", "") if not ok else ""}
    except Exception as e:
        return {"success": False, "detail": str(e)}


def _send_email(
    from_email: str, password: str, to_email: str,
    message: str, title: str,
    smtp_server: str = "", smtp_port: str = ""
) -> Dict:
    """Envoi par e-mail (format HTML)"""
    try:
        domain = from_email.split("@")[-1].lower()
        html_content = _markdown_to_simple_html(message)

        # Configuration SMTP
        if smtp_server and smtp_port:
            server_host = smtp_server
            port = int(smtp_port)
            use_tls = port != 465
        elif domain in SMTP_CONFIGS:
            cfg = SMTP_CONFIGS[domain]
            server_host = cfg["server"]
            port = cfg["port"]
            use_tls = cfg["encryption"] == "TLS"
        else:
            server_host = f"smtp.{domain}"
            port = 587
            use_tls = True

        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr(("TrendRadar", from_email))

        recipients = [addr.strip() for addr in to_email.split(",")]
        msg["To"] = ", ".join(recipients)

        now = datetime.now()
        msg["Subject"] = Header(f"{title} - {now.strftime('%d/%m %H:%M')}", "utf-8")
        msg["MIME-Version"] = "1.0"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        # Version texte brut de secours
        msg.attach(MIMEText(strip_markdown(message), "plain", "utf-8"))
        # Corps HTML
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        if use_tls:
            server = smtplib.SMTP(server_host, port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(server_host, port, timeout=30)
            server.ehlo()

        server.login(from_email, password)
        server.send_message(msg)
        server.quit()

        return {"success": True, "detail": ""}
    except Exception as e:
        return {"success": False, "detail": str(e)}


def _send_ntfy(server_url: str, topic: str, content: str, title: str, token: str = "") -> Dict:
    """Envoi ntfy (reçoit du Markdown déjà adapté, cohérent avec trendradar send_to_ntfy)

    Remarque : Title utilise des caractères ASCII pour éviter les problèmes d'encodage des en-têtes HTTP.
    Prend en charge la nouvelle tentative en cas de limite de débit 429.
    """
    base_url = server_url.rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    url = f"{base_url}/{topic}"

    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Markdown": "yes",
        "Title": "TrendRadar Notification",  # ASCII, pour éviter les problèmes d'encodage des en-têtes HTTP
        "Priority": "default",
        "Tags": "news",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.post(url, data=content.encode("utf-8"), headers=headers, timeout=30)
        if resp.status_code == 200:
            return {"success": True, "detail": ""}
        elif resp.status_code == 429:
            # Limite de débit, on attend puis on réessaie une fois (cohérent avec trendradar)
            time.sleep(10)
            retry_resp = requests.post(url, data=content.encode("utf-8"), headers=headers, timeout=30)
            ok = retry_resp.status_code == 200
            return {"success": ok, "detail": "" if ok else f"retry status={retry_resp.status_code}"}
        elif resp.status_code == 413:
            return {"success": False, "detail": f"Message trop volumineux, rejeté ({len(content.encode('utf-8'))} octets)"}
        else:
            return {"success": False, "detail": f"status={resp.status_code}"}
    except Exception as e:
        return {"success": False, "detail": str(e)}


def _send_bark(bark_url: str, content: str, title: str) -> Dict:
    """Envoi Bark (reçoit du Markdown déjà adapté, notification push iOS)"""
    parsed = urlparse(bark_url)
    device_key = parsed.path.strip('/').split('/')[0] if parsed.path else None
    if not device_key:
        return {"success": False, "detail": f"Impossible d'extraire device_key depuis l'URL : {bark_url}"}

    api_endpoint = f"{parsed.scheme}://{parsed.netloc}/push"
    payload = {
        "title": title,
        "markdown": content,
        "device_key": device_key,
        "sound": "default",
        "group": "TrendRadar",
        "action": "none",
    }

    try:
        resp = requests.post(api_endpoint, json=payload, timeout=30)
        data = resp.json()
        ok = resp.status_code == 200 and data.get("code") == 200
        return {"success": ok, "detail": data.get("message", "") if not ok else ""}
    except Exception as e:
        return {"success": False, "detail": str(e)}


def _send_slack(webhook_url: str, content: str, title: str) -> Dict:
    """Envoi Slack (reçoit du mrkdwn déjà converti)"""
    payload = {"text": content}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=30)
        ok = resp.status_code == 200 and resp.text == "ok"
        return {"success": ok, "detail": "" if ok else resp.text}
    except Exception as e:
        return {"success": False, "detail": str(e)}


def _send_generic_webhook(
    webhook_url: str, message: str, title: str, payload_template: str = ""
) -> Dict:
    """Envoi Webhook générique (format Markdown, prend en charge un modèle personnalisé)"""
    try:
        if payload_template:
            json_content = json.dumps(message)[1:-1]
            json_title = json.dumps(title)[1:-1]
            payload_str = payload_template.replace("{content}", json_content).replace("{title}", json_title)
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                payload = {"title": title, "content": message}
        else:
            payload = {"title": title, "content": message}

        resp = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        ok = 200 <= resp.status_code < 300
        return {"success": ok, "detail": "" if ok else f"status={resp.status_code}"}
    except Exception as e:
        return {"success": False, "detail": str(e)}


# ==================== Classe d'outils ====================

class NotificationTools:
    """Classe des outils de notification (push)"""

    def __init__(self, project_root: str = None):
        if project_root:
            self.project_root = Path(project_root)
        else:
            current_file = Path(__file__)
            self.project_root = current_file.parent.parent.parent

    def _load_merged_config(self) -> Dict[str, Any]:
        """
        Charge la configuration de notification fusionnée (config.yaml + .env)

        Returns:
            dictionnaire fusionné contenant la configuration webhook et les paramètres de notification
        """
        config_path = self.project_root / "config" / "config.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
        else:
            config_data = {}

        webhook_config = _load_webhook_config(config_data)
        notification_config = _load_notification_config(config_data)
        return {**webhook_config, **notification_config}

    def _detect_config_source(self, env_key: str, yaml_value: str) -> str:
        """Détecte la source d'un élément de configuration : env / yaml / non configuré"""
        env_val = os.environ.get(env_key, "").strip()
        if env_val:
            return "env"
        elif yaml_value:
            return "yaml"
        return ""

    def get_channel_format_guide(self, channel: Optional[str] = None) -> Dict:
        """
        Récupère le guide des stratégies de formatage des canaux

        Retourne pour chaque canal les fonctionnalités Markdown prises en charge, les limites et les meilleures
        consignes de formatage, à titre de référence pour le LLM lors de la génération du contenu push,
        afin que le style du contenu soit adapté au canal cible.

        Args:
            channel: ID de canal indiqué, None retourne les stratégies de tous les canaux

        Returns:
            dictionnaire des stratégies de formatage
        """
        if channel:
            if channel not in CHANNEL_FORMAT_GUIDES:
                valid = list(CHANNEL_FORMAT_GUIDES.keys())
                return {
                    "success": False,
                    "error": {
                        "code": "INVALID_CHANNEL",
                        "message": f"Canal invalide : {channel}",
                        "suggestion": f"Canaux pris en charge : {valid}",
                    },
                }
            guide = CHANNEL_FORMAT_GUIDES[channel]
            return {
                "success": True,
                "channel": channel,
                "guide": guide,
            }
        else:
            return {
                "success": True,
                "summary": f"Stratégies de formatage pour {len(CHANNEL_FORMAT_GUIDES)} canaux au total",
                "guides": CHANNEL_FORMAT_GUIDES,
            }

    def get_notification_channels(self) -> Dict:
        """
        Récupère l'état de configuration de tous les canaux de notification

        Détecte config.yaml et les variables d'environnement .env, retourne si chaque canal est configuré.

        Returns:
            dictionnaire de l'état des canaux
        """
        try:
            config = self._load_merged_config()
            enabled = config.get("ENABLE_NOTIFICATION", True)

            # Lecture directe depuis le yaml (pour déterminer la source)
            config_path = self.project_root / "config" / "config.yaml"
            yaml_channels = {}
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                    yaml_channels = raw.get("notification", {}).get("channels", {})

            channels = []
            env_key_map = {
                "FEISHU_WEBHOOK_URL": ("feishu", "webhook_url"),
                "DINGTALK_WEBHOOK_URL": ("dingtalk", "webhook_url"),
                "WEWORK_WEBHOOK_URL": ("wework", "webhook_url"),
                "TELEGRAM_BOT_TOKEN": ("telegram", "bot_token"),
                "TELEGRAM_CHAT_ID": ("telegram", "chat_id"),
                "EMAIL_FROM": ("email", "from"),
                "EMAIL_PASSWORD": ("email", "password"),
                "EMAIL_TO": ("email", "to"),
                "NTFY_SERVER_URL": ("ntfy", "server_url"),
                "NTFY_TOPIC": ("ntfy", "topic"),
                "BARK_URL": ("bark", "url"),
                "SLACK_WEBHOOK_URL": ("slack", "webhook_url"),
                "GENERIC_WEBHOOK_URL": ("generic_webhook", "webhook_url"),
            }

            for channel_id, required_keys in _CHANNEL_REQUIREMENTS.items():
                is_configured = all(config.get(k) for k in required_keys)

                # Détermine la source
                sources = set()
                for key in required_keys:
                    ch_name, field = env_key_map.get(key, ("", ""))
                    yaml_val = yaml_channels.get(ch_name, {}).get(field, "")
                    src = self._detect_config_source(key, yaml_val)
                    if src:
                        sources.add(src)

                channels.append({
                    "id": channel_id,
                    "name": _CHANNEL_NAMES.get(channel_id, channel_id),
                    "configured": is_configured,
                    "source": list(sources) if sources else [],
                })

            configured_count = sum(1 for ch in channels if ch["configured"])

            return {
                "success": True,
                "notification_enabled": enabled,
                "summary": f"{configured_count}/{len(channels)} canaux configurés",
                "channels": channels,
            }
        except Exception as e:
            return {
                "success": False,
                "error": {"code": "INTERNAL_ERROR", "message": str(e)},
            }

    def send_notification(
        self,
        message: str,
        title: str = "Notification TrendRadar",
        channels: Optional[List[str]] = None,
    ) -> Dict:
        """
        Envoie un message vers les canaux de notification configurés

        Accepte du contenu au format markdown, converti automatiquement en interne au format requis par chaque canal.

        Args:
            message: contenu du message au format markdown
            title: titre du message
            channels: liste des canaux d'envoi indiqués, None signifie envoyer vers tous les canaux configurés
                      valeurs possibles : feishu, dingtalk, wework, telegram, email, ntfy, bark, slack, generic_webhook

        Returns:
            dictionnaire du résultat d'envoi
        """
        if not message or not message.strip():
            return {
                "success": False,
                "error": {"code": "EMPTY_MESSAGE", "message": "Le contenu du message ne peut pas être vide"},
            }

        try:
            config = self._load_merged_config()

            if not config.get("ENABLE_NOTIFICATION", True):
                return {
                    "success": False,
                    "error": {"code": "NOTIFICATION_DISABLED", "message": "La fonction de notification est désactivée (notification.enabled = false)"},
                }

            # Détermine les canaux cibles
            all_channel_ids = list(_CHANNEL_REQUIREMENTS.keys())
            if channels:
                # Valide les noms de canaux
                invalid = [ch for ch in channels if ch not in all_channel_ids]
                if invalid:
                    raise InvalidParameterError(
                        f"Canaux invalides : {invalid}",
                        suggestion=f"Canaux pris en charge : {all_channel_ids}"
                    )
                target_channels = channels
            else:
                # Envoie vers tous les canaux configurés
                target_channels = [
                    ch_id for ch_id, keys in _CHANNEL_REQUIREMENTS.items()
                    if all(config.get(k) for k in keys)
                ]

            if not target_channels:
                return {
                    "success": False,
                    "error": {
                        "code": "NO_CHANNELS",
                        "message": "Aucun canal cible configuré",
                        "suggestion": "Veuillez configurer au moins un canal de notification dans config.yaml ou .env",
                    },
                }

            # Envoi canal par canal
            results = {}
            for ch_id in target_channels:
                required_keys = _CHANNEL_REQUIREMENTS[ch_id]
                if not all(config.get(k) for k in required_keys):
                    results[ch_id] = {"success": False, "detail": "Canal non configuré"}
                    continue

                result = self._dispatch_to_channel(ch_id, config, message, title)
                results[ch_id] = result

            success_count = sum(1 for r in results.values() if r["success"])
            total = len(results)

            return {
                "success": success_count > 0,
                "summary": f"{success_count}/{total} canaux ont reçu le message avec succès",
                "results": {
                    ch_id: {
                        "name": _CHANNEL_NAMES.get(ch_id, ch_id),
                        **r,
                    }
                    for ch_id, r in results.items()
                },
            }

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {
                "success": False,
                "error": {"code": "INTERNAL_ERROR", "message": str(e)},
            }

    def _dispatch_to_channel(
        self, channel_id: str, config: Dict, message: str, title: str
    ) -> Dict:
        """Distribue le message vers le canal indiqué (adaptation du format → découpage en octets → multi-comptes × envoi lot par lot)

        Lit la configuration depuis config.yaml → advanced.batch_size / batch_send_interval.
        """
        # Lit la configuration des lots depuis config (cohérent avec trendradar)
        batch_sizes = self._get_batch_sizes()
        batch_interval = self._get_batch_interval()

        # L'e-mail n'a pas de limite d'octets, ne passe pas par le pipeline de découpage en lots
        if channel_id == "email":
            return _send_email(
                config["EMAIL_FROM"],
                config["EMAIL_PASSWORD"],
                config["EMAIL_TO"],
                message, title,
                config.get("EMAIL_SMTP_SERVER", ""),
                config.get("EMAIL_SMTP_PORT", ""),
            )

        # Pipeline de découpage en lots unifié : adaptation du format → découpage en octets → ajout des en-têtes de lot → (facultatif) ordre inverse
        batches = _prepare_batches(message, channel_id, batch_sizes)

        # Achemine l'envoi selon le canal
        if channel_id == "feishu":
            return self._send_batched_multi_account(
                config["FEISHU_WEBHOOK_URL"], batches, channel_id,
                lambda url, content: _send_feishu(url, content, title),
                batch_interval,
            )
        elif channel_id == "dingtalk":
            return self._send_batched_multi_account(
                config["DINGTALK_WEBHOOK_URL"], batches, channel_id,
                lambda url, content: _send_dingtalk(url, content, title),
                batch_interval,
            )
        elif channel_id == "wework":
            msg_type = config.get("WEWORK_MSG_TYPE", "markdown")
            return self._send_batched_multi_account(
                config["WEWORK_WEBHOOK_URL"], batches, channel_id,
                lambda url, content: _send_wework(url, content, title, msg_type),
                batch_interval,
            )
        elif channel_id == "telegram":
            return self._send_batched_telegram(
                config, batches, title, batch_interval,
            )
        elif channel_id == "ntfy":
            return self._send_batched_ntfy(
                config, batches, title, batch_interval,
            )
        elif channel_id == "bark":
            return self._send_batched_multi_account(
                config["BARK_URL"], batches, channel_id,
                lambda url, content: _send_bark(url, content, title),
                batch_interval,
            )
        elif channel_id == "slack":
            return self._send_batched_multi_account(
                config["SLACK_WEBHOOK_URL"], batches, channel_id,
                lambda url, content: _send_slack(url, content, title),
                batch_interval,
            )
        elif channel_id == "generic_webhook":
            template = config.get("GENERIC_WEBHOOK_TEMPLATE", "")
            return self._send_batched_multi_account(
                config["GENERIC_WEBHOOK_URL"], batches, channel_id,
                lambda url, content: _send_generic_webhook(url, content, title, template),
                batch_interval,
            )
        else:
            return {"success": False, "detail": f"Canal inconnu : {channel_id}"}

    def _get_batch_sizes(self) -> Dict:
        """Lit advanced.batch_size depuis config.yaml et le fusionne avec les valeurs par défaut"""
        try:
            config_path = self.project_root / "config" / "config.yaml"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                advanced = raw.get("advanced", {})
                cfg_sizes = advanced.get("batch_size", {})
                # Construit la correspondance des canaux depuis config
                sizes = dict(_CHANNEL_BATCH_SIZES_DEFAULT)
                default_size = cfg_sizes.get("default", 4000)
                for ch_id in sizes:
                    if ch_id in cfg_sizes:
                        sizes[ch_id] = cfg_sizes[ch_id]
                    elif ch_id not in ("email", "ntfy") and sizes[ch_id] == 4000:
                        # Utilise la valeur default de config
                        sizes[ch_id] = default_size
                return sizes
        except Exception:
            pass
        return dict(_CHANNEL_BATCH_SIZES_DEFAULT)

    def _get_batch_interval(self) -> float:
        """Lit advanced.batch_send_interval depuis config.yaml"""
        try:
            config_path = self.project_root / "config" / "config.yaml"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                return float(raw.get("advanced", {}).get("batch_send_interval", _BATCH_INTERVAL_DEFAULT))
        except Exception:
            pass
        return _BATCH_INTERVAL_DEFAULT

    def _send_batched_multi_account(
        self, urls_str: str, batches: List[str], channel_id: str, send_func,
        batch_interval: float = _BATCH_INTERVAL_DEFAULT,
    ) -> Dict:
        """Envoi multi-comptes × lot par lot (URL séparées par ;)"""
        urls = [u.strip() for u in urls_str.split(";") if u.strip()]
        if not urls:
            return {"success": False, "detail": "URL vide"}

        any_ok = False
        details = []
        for url in urls:
            for i, batch in enumerate(batches):
                r = send_func(url, batch)
                if r["success"]:
                    any_ok = True
                elif r["detail"]:
                    details.append(r["detail"])
                # Intervalle entre les lots
                if i < len(batches) - 1:
                    time.sleep(batch_interval)

        return {
            "success": any_ok,
            "detail": "; ".join(details) if details else "",
            "batches": len(batches),
        }

    def _send_batched_telegram(
        self, config: Dict, batches: List[str], title: str,
        batch_interval: float = _BATCH_INTERVAL_DEFAULT,
    ) -> Dict:
        """Envoi Telegram multi-comptes × lot par lot (appariement token/chat_id)"""
        tokens = config["TELEGRAM_BOT_TOKEN"].split(";")
        chat_ids = config["TELEGRAM_CHAT_ID"].split(";")
        if len(tokens) != len(chat_ids):
            return {"success": False, "detail": "Le nombre de bot_token et de chat_id ne correspond pas"}

        any_ok = False
        details = []
        for token, cid in zip(tokens, chat_ids):
            token, cid = token.strip(), cid.strip()
            if not (token and cid):
                continue
            for i, batch in enumerate(batches):
                r = _send_telegram(token, cid, batch, title)
                if r["success"]:
                    any_ok = True
                elif r["detail"]:
                    details.append(r["detail"])
                if i < len(batches) - 1:
                    time.sleep(batch_interval)

        return {
            "success": any_ok,
            "detail": "; ".join(details) if details else "",
            "batches": len(batches),
        }

    def _send_batched_ntfy(
        self, config: Dict, batches: List[str], title: str,
        batch_interval: float = _BATCH_INTERVAL_DEFAULT,
    ) -> Dict:
        """Envoi ntfy multi-comptes × lot par lot (appariement server/topic/token, avec gestion de la limite de débit)"""
        servers = config["NTFY_SERVER_URL"].split(";")
        topics = config["NTFY_TOPIC"].split(";")
        tokens_str = config.get("NTFY_TOKEN", "")
        tokens = tokens_str.split(";") if tokens_str else [""]
        if len(servers) != len(topics):
            return {"success": False, "detail": "Le nombre de server_url et de topic ne correspond pas"}

        any_ok = False
        details = []
        for i, (srv, topic) in enumerate(zip(servers, topics)):
            srv, topic = srv.strip(), topic.strip()
            tk = tokens[i].strip() if i < len(tokens) else ""
            if not (srv and topic):
                continue
            # Le serveur public ntfy.sh utilise un intervalle de 2 s (cohérent avec trendradar)
            interval = 2.0 if "ntfy.sh" in srv else batch_interval
            for j, batch in enumerate(batches):
                r = _send_ntfy(srv, topic, batch, title, tk)
                if r["success"]:
                    any_ok = True
                elif r["detail"]:
                    details.append(r["detail"])
                if j < len(batches) - 1:
                    time.sleep(interval)

        return {
            "success": any_ok,
            "detail": "; ".join(details) if details else "",
            "batches": len(batches),
        }
