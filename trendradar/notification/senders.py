# coding=utf-8
"""
Module d'envoi de messages

Envoie les données du rapport vers les différents canaux de notification : 
- Feishu (Feishu/Lark)
- DingTalk (DingTalk)
- WeCom (WeCom/WeWork)
- Telegram
- e-mail (Email)
- ntfy
- Bark
- Slack

Chaque fonction d'envoi supporte l'envoi par lots et se découple de CONFIG via une configuration paramétrée.
"""

import smtplib
import time
import json
from datetime import datetime
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from .batch import add_batch_headers, get_max_batch_header_size
from .formatters import convert_markdown_to_mrkdwn, strip_markdown


def _extract_ai_stats(ai_analysis) -> Optional[Dict]:
    """Extrait les données statistiques depuis le résultat de l'Analyse IA"""
    if not ai_analysis or not getattr(ai_analysis, "success", False):
        return None
    return {
        "total_news": getattr(ai_analysis, "total_news", 0),
        "analyzed_news": getattr(ai_analysis, "analyzed_news", 0),
        "max_news_limit": getattr(ai_analysis, "max_news_limit", 0),
        "hotlist_count": getattr(ai_analysis, "hotlist_count", 0),
        "rss_count": getattr(ai_analysis, "rss_count", 0),
        "hotlist_analyzed": getattr(ai_analysis, "hotlist_analyzed", 0),
        "rss_analyzed": getattr(ai_analysis, "rss_analyzed", 0),
        "standalone_analyzed": getattr(ai_analysis, "standalone_analyzed", 0),
        "ai_mode": getattr(ai_analysis, "ai_mode", ""),
        "include_rss": getattr(ai_analysis, "include_rss", True),
        "include_standalone": getattr(ai_analysis, "include_standalone", False),
    }


def _render_ai_analysis(ai_analysis: Any, channel: str) -> str:
    """Rend le contenu de l'Analyse IA au format du canal indiqué"""
    if not ai_analysis:
        return ""

    try:
        from trendradar.ai.formatter import get_ai_analysis_renderer
        renderer = get_ai_analysis_renderer(channel)
        return renderer(ai_analysis)
    except ImportError:
        return ""


# === Configuration SMTP des messageries ===
SMTP_CONFIGS = {
    # Gmail (utilise STARTTLS)
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "encryption": "TLS"},
    # Messagerie QQ (utilise SSL, plus stable)
    "qq.com": {"server": "smtp.qq.com", "port": 465, "encryption": "SSL"},
    # Outlook (utilise STARTTLS)
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "encryption": "TLS"},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "encryption": "TLS"},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "encryption": "TLS"},
    # Messagerie NetEase (utilise SSL, plus stable)
    "163.com": {"server": "smtp.163.com", "port": 465, "encryption": "SSL"},
    "126.com": {"server": "smtp.126.com", "port": 465, "encryption": "SSL"},
    # Messagerie Sina (utilise SSL)
    "sina.com": {"server": "smtp.sina.com", "port": 465, "encryption": "SSL"},
    # Messagerie Sohu (utilise SSL)
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "encryption": "SSL"},
    # Messagerie 189 (China Telecom) (utilise SSL)
    "189.cn": {"server": "smtp.189.cn", "port": 465, "encryption": "SSL"},
    # Messagerie Alibaba Cloud (utilise TLS)
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "encryption": "TLS"},
    # Messagerie Yandex (utilise TLS)
    "yandex.com": {"server": "smtp.yandex.com", "port": 465, "encryption": "TLS"},
    # Messagerie iCloud (utilise SSL)
    "icloud.com": {"server": "smtp.mail.me.com", "port": 587, "encryption": "SSL"},
}


def send_to_feishu(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 29000,
    batch_interval: float = 1.0,
    split_content_func: Callable = None,
    get_time_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    Envoie vers Feishu (envoi par lots, prend en charge Tendances + RSS fusionnés + Zone d'affichage autonome)

    Args:
        webhook_url: Feishu Webhook URL
        report_data: données du rapport
        report_type: type de rapport
        update_info: informations de mise à jour (optionnel)
        proxy_url: URL du proxy (optionnel)
        mode: mode du rapport (daily/current)
        account_label: libellé du compte (affiché en mode multi-comptes)
        batch_size: taille des lots (octets)
        batch_interval: intervalle entre les envois de lots (secondes)
        split_content_func: fonction de découpage du contenu en lots
        get_time_func: fonction renvoyant l'heure courante
        rss_items: liste des entrées RSS pour les statistiques (optionnel, pour l'envoi fusionné)
        rss_new_items: liste des nouvelles entrées RSS (optionnel, pour le bloc des nouveautés)

    Returns:
        bool : succès de l'envoi
    """
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # préfixe des journaux
    log_prefix = f"Feishu{account_label}" if account_label else "Feishu"

    # rend le contenu de l'Analyse IA et extrait les données statistiques
    ai_content = _render_ai_analysis(ai_analysis, "feishu") if ai_analysis else None
    ai_stats = _extract_ai_stats(ai_analysis)

    # réserve de l'espace pour l'en-tête de lot, afin d'éviter un dépassement après ajout de l'en-tête
    header_reserve = get_max_batch_header_size("feishu")
    batches = split_content_func(
        report_data,
        "feishu",
        update_info,
        max_bytes=batch_size - header_reserve,
        mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    # ajoute uniformément les en-têtes de lot (l'espace est déjà réservé, pas de dépassement)
    batches = add_batch_headers(batches, "feishu", batch_size)

    print(f"{log_prefix} : message divisé en {len(batches)} lots à envoyer [{report_type}]")

    # envoi lot par lot
    for i, batch_content in enumerate(batches, 1):
        content_size = len(batch_content.encode("utf-8"))
        print(
            f"{log_prefix} : envoi du lot n° {i}/{len(batches)}, taille : {content_size} octets [{report_type}]"
        )

        # choisit le format du payload selon le domaine du webhook
        # www.feishu.cn utilise le format texte brut, les autres domaines (open.feishu.cn/open.larksuite.com) utilisent la carte 2.0
        if "www.feishu.cn" in webhook_url:
            payload = {
                "msg_type": "text",
                "content": {
                    "text": batch_content,
                },
            }
        else:
            payload = {
                "msg_type": "interactive",
                "card": {
                    "schema": "2.0",
                    "body": {
                        "elements": [
                            {"tag": "markdown", "content": batch_content}
                        ]
                    },
                },
            }

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                # vérifie le statut de la réponse Feishu
                if result.get("StatusCode") == 0 or result.get("code") == 0:
                    print(f"{log_prefix} : lot n° {i}/{len(batches)} envoyé avec succès [{report_type}]")
                    # intervalle entre les lots
                    if i < len(batches):
                        time.sleep(batch_interval)
                else:
                    error_msg = result.get("msg") or result.get("StatusMessage", "erreur inconnue")
                    print(
                        f"{log_prefix} : échec de l'envoi du lot n° {i}/{len(batches)} [{report_type}], erreur : {error_msg}"
                    )
                    return False
            else:
                print(
                    f"{log_prefix} : échec de l'envoi du lot n° {i}/{len(batches)} [{report_type}], code d'état : {response.status_code}"
                )
                return False
        except Exception as e:
            print(f"{log_prefix} : erreur lors de l'envoi du lot n° {i}/{len(batches)} [{report_type}] : {e}")
            return False

    print(f"{log_prefix} : les {len(batches)} lots ont été envoyés [{report_type}]")

    return True


def send_to_dingtalk(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 20000,
    batch_interval: float = 1.0,
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    Envoie vers DingTalk (envoi par lots, prend en charge Tendances + RSS fusionnés + Zone d'affichage autonome)

    Args:
        webhook_url: DingTalk Webhook URL
        report_data: données du rapport
        report_type: type de rapport
        update_info: informations de mise à jour (optionnel)
        proxy_url: URL du proxy (optionnel)
        mode: mode du rapport (daily/current)
        account_label: libellé du compte (affiché en mode multi-comptes)
        batch_size: taille des lots (octets)
        batch_interval: intervalle entre les envois de lots (secondes)
        split_content_func: fonction de découpage du contenu en lots
        rss_items: liste des entrées RSS pour les statistiques (optionnel, pour l'envoi fusionné)
        rss_new_items: liste des nouvelles entrées RSS (optionnel, pour le bloc des nouveautés)

    Returns:
        bool : succès de l'envoi
    """
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # préfixe des journaux
    log_prefix = f"DingTalk{account_label}" if account_label else "DingTalk"

    # rend le contenu de l'Analyse IA et extrait les données statistiques
    ai_content = _render_ai_analysis(ai_analysis, "dingtalk") if ai_analysis else None
    ai_stats = _extract_ai_stats(ai_analysis)

    # réserve de l'espace pour l'en-tête de lot, afin d'éviter un dépassement après ajout de l'en-tête
    header_reserve = get_max_batch_header_size("dingtalk")
    batches = split_content_func(
        report_data,
        "dingtalk",
        update_info,
        max_bytes=batch_size - header_reserve,
        mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    # ajoute uniformément les en-têtes de lot (l'espace est déjà réservé, pas de dépassement)
    batches = add_batch_headers(batches, "dingtalk", batch_size)

    print(f"{log_prefix} : message divisé en {len(batches)} lots à envoyer [{report_type}]")

    # envoi lot par lot
    for i, batch_content in enumerate(batches, 1):
        content_size = len(batch_content.encode("utf-8"))
        print(
            f"{log_prefix} : envoi du lot n° {i}/{len(batches)}, taille : {content_size} octets [{report_type}]"
        )

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"TrendRadar rapport d'analyse des tendances - {report_type}",
                "text": batch_content,
            },
        }

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"{log_prefix} : lot n° {i}/{len(batches)} envoyé avec succès [{report_type}]")
                    # intervalle entre les lots
                    if i < len(batches):
                        time.sleep(batch_interval)
                else:
                    print(
                        f"{log_prefix} : échec de l'envoi du lot n° {i}/{len(batches)} [{report_type}], erreur : {result.get('errmsg')}"
                    )
                    return False
            else:
                print(
                    f"{log_prefix} : échec de l'envoi du lot n° {i}/{len(batches)} [{report_type}], code d'état : {response.status_code}"
                )
                return False
        except Exception as e:
            print(f"{log_prefix} : erreur lors de l'envoi du lot n° {i}/{len(batches)} [{report_type}] : {e}")
            return False

    print(f"{log_prefix} : les {len(batches)} lots ont été envoyés [{report_type}]")

    return True


def send_to_wework(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 4000,
    batch_interval: float = 1.0,
    msg_type: str = "markdown",
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    Envoie vers WeCom (envoi par lots, prend en charge les formats markdown et text, ainsi que Tendances + RSS fusionnés + Zone d'affichage autonome)

    Args:
        webhook_url: WeCom Webhook URL
        report_data: données du rapport
        report_type: type de rapport
        update_info: informations de mise à jour (optionnel)
        proxy_url: URL du proxy (optionnel)
        mode: mode du rapport (daily/current)
        account_label: libellé du compte (affiché en mode multi-comptes)
        batch_size: taille des lots (octets)
        batch_interval: intervalle entre les envois de lots (secondes)
        msg_type: type de message (markdown/text)
        split_content_func: fonction de découpage du contenu en lots
        rss_items: liste des entrées RSS pour les statistiques (optionnel, pour l'envoi fusionné)
        rss_new_items: liste des nouvelles entrées RSS (optionnel, pour le bloc des nouveautés)

    Returns:
        bool : succès de l'envoi
    """
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # préfixe des journaux
    log_prefix = f"WeCom{account_label}" if account_label else "WeCom"

    # récupère la configuration du type de message (markdown ou text)
    is_text_mode = msg_type.lower() == "text"

    if is_text_mode:
        print(f"{log_prefix} : utilise le format text (mode WeChat personnel) [{report_type}]")
    else:
        print(f"{log_prefix} : utilise le format markdown (mode bot de groupe) [{report_type}]")

    # le mode text utilise wework_text, le mode markdown utilise wework
    header_format_type = "wework_text" if is_text_mode else "wework"

    # rend le contenu de l'Analyse IA et extrait les données statistiques
    ai_content = _render_ai_analysis(ai_analysis, "wework") if ai_analysis else None
    ai_stats = _extract_ai_stats(ai_analysis)

    # récupère le contenu découpé en lots, en réservant de l'espace pour l'en-tête de lot
    header_reserve = get_max_batch_header_size(header_format_type)
    batches = split_content_func(
        report_data, "wework", update_info, max_bytes=batch_size - header_reserve, mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    # ajoute uniformément les en-têtes de lot (l'espace est déjà réservé, pas de dépassement)
    batches = add_batch_headers(batches, header_format_type, batch_size)

    print(f"{log_prefix} : message divisé en {len(batches)} lots à envoyer [{report_type}]")

    # envoi lot par lot
    for i, batch_content in enumerate(batches, 1):
        # construit le payload selon le type de message
        if is_text_mode:
            # format text : supprime la syntaxe markdown
            plain_content = strip_markdown(batch_content)
            payload = {"msgtype": "text", "text": {"content": plain_content}}
            content_size = len(plain_content.encode("utf-8"))
        else:
            # format markdown : conserve le contenu tel quel
            payload = {"msgtype": "markdown", "markdown": {"content": batch_content}}
            content_size = len(batch_content.encode("utf-8"))

        print(
            f"{log_prefix} : envoi du lot n° {i}/{len(batches)}, taille : {content_size} octets [{report_type}]"
        )

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"{log_prefix} : lot n° {i}/{len(batches)} envoyé avec succès [{report_type}]")
                    # intervalle entre les lots
                    if i < len(batches):
                        time.sleep(batch_interval)
                else:
                    print(
                        f"{log_prefix} : échec de l'envoi du lot n° {i}/{len(batches)} [{report_type}], erreur : {result.get('errmsg')}"
                    )
                    return False
            else:
                print(
                    f"{log_prefix} : échec de l'envoi du lot n° {i}/{len(batches)} [{report_type}], code d'état : {response.status_code}"
                )
                return False
        except Exception as e:
            print(f"{log_prefix} : erreur lors de l'envoi du lot n° {i}/{len(batches)} [{report_type}] : {e}")
            return False

    print(f"{log_prefix} : les {len(batches)} lots ont été envoyés [{report_type}]")

    return True


def send_to_telegram(
    bot_token: str,
    chat_id: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 4000,
    batch_interval: float = 1.0,
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    Envoie vers Telegram (envoi par lots, prend en charge Tendances + RSS fusionnés + Zone d'affichage autonome)

    Args:
        bot_token: Telegram Bot Token
        chat_id: Telegram Chat ID
        report_data: données du rapport
        report_type: type de rapport
        update_info: informations de mise à jour (optionnel)
        proxy_url: URL du proxy (optionnel)
        mode: mode du rapport (daily/current)
        account_label: libellé du compte (affiché en mode multi-comptes)
        batch_size: taille des lots (octets)
        batch_interval: intervalle entre les envois de lots (secondes)
        split_content_func: fonction de découpage du contenu en lots
        rss_items: liste des entrées RSS pour les statistiques (optionnel, pour l'envoi fusionné)
        rss_new_items: liste des nouvelles entrées RSS (optionnel, pour le bloc des nouveautés)

    Returns:
        bool : succès de l'envoi
    """
    headers = {"Content-Type": "application/json"}
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # préfixe des journaux
    log_prefix = f"Telegram{account_label}" if account_label else "Telegram"

    # rend le contenu de l'Analyse IA et extrait les données statistiques
    ai_content = _render_ai_analysis(ai_analysis, "telegram") if ai_analysis else None
    ai_stats = _extract_ai_stats(ai_analysis)

    # récupère le contenu découpé en lots, en réservant de l'espace pour l'en-tête de lot
    header_reserve = get_max_batch_header_size("telegram")
    batches = split_content_func(
        report_data, "telegram", update_info, max_bytes=batch_size - header_reserve, mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    # ajoute uniformément les en-têtes de lot (l'espace est déjà réservé, pas de dépassement)
    batches = add_batch_headers(batches, "telegram", batch_size)

    print(f"{log_prefix} : message divisé en {len(batches)} lots à envoyer [{report_type}]")

    # envoi lot par lot
    for i, batch_content in enumerate(batches, 1):
        content_size = len(batch_content.encode("utf-8"))
        print(
            f"{log_prefix} : envoi du lot n° {i}/{len(batches)}, taille : {content_size} octets [{report_type}]"
        )

        payload = {
            "chat_id": chat_id,
            "text": batch_content,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(
                url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print(f"{log_prefix} : lot n° {i}/{len(batches)} envoyé avec succès [{report_type}]")
                    # intervalle entre les lots
                    if i < len(batches):
                        time.sleep(batch_interval)
                else:
                    print(
                        f"{log_prefix} : échec de l'envoi du lot n° {i}/{len(batches)} [{report_type}], erreur : {result.get('description')}"
                    )
                    return False
            else:
                print(
                    f"{log_prefix} : échec de l'envoi du lot n° {i}/{len(batches)} [{report_type}], code d'état : {response.status_code}"
                )
                return False
        except Exception as e:
            print(f"{log_prefix} : erreur lors de l'envoi du lot n° {i}/{len(batches)} [{report_type}] : {e}")
            return False

    print(f"{log_prefix} : les {len(batches)} lots ont été envoyés [{report_type}]")

    return True


def _resolve_language_html_files(html_file_path: str) -> List[Tuple[str, Path]]:
    """Déduit les fichiers HTML par langue (FR + EN) à partir du chemin reçu.

    Le chemin reçu peut être soit suffixé par la langue (``<base>_fr.html`` /
    ``<base>_en.html``), soit non suffixé (``<base>.html``). On cherche dans tous
    les cas les variantes ``<base>_fr.html`` et ``<base>_en.html``.

    Returns:
        Liste de tuples (langue, chemin) pour les fichiers existants, dans l'ordre
        FR puis EN. Si aucune variante de langue n'existe, retombe sur le fichier
        reçu lui-même (compat).
    """
    from trendradar.i18n import REPORT_LANGS

    p = Path(html_file_path)
    name = p.name
    if name.endswith(".html"):
        stem = name[: -len(".html")]
    else:
        stem = p.stem

    # Retire un éventuel suffixe de langue existant pour obtenir la base
    base = stem
    for lang in REPORT_LANGS:
        suffix = f"_{lang}"
        if stem.endswith(suffix):
            base = stem[: -len(suffix)]
            break

    results: List[Tuple[str, Path]] = []
    for lang in REPORT_LANGS:
        candidate = p.with_name(f"{base}_{lang}.html")
        if candidate.exists():
            results.append((lang, candidate))

    if not results and p.exists():
        # Compat : aucune variante de langue, on attache le fichier reçu
        results.append((REPORT_LANGS[0] if REPORT_LANGS else "fr", p))

    return results


def send_to_email(
    from_email: str,
    password: str,
    to_email: str,
    report_type: str,
    html_file_path: str,
    custom_smtp_server: Optional[str] = None,
    custom_smtp_port: Optional[int] = None,
    *,
    get_time_func: Callable = None,
) -> bool:
    """
    Envoie une notification par e-mail.

    Le corps de l'e-mail utilise le HTML de la langue par défaut (FR). Les deux
    versions du rapport (FR + EN) sont jointes en pièces jointes lorsqu'elles existent.

    Args:
        from_email: adresse de l'expéditeur
        password: mot de passe / code d'autorisation de la boîte
        to_email: adresse(s) du/des destinataire(s) (séparées par des virgules)
        report_type: type de rapport
        html_file_path: chemin du fichier de rapport HTML
        custom_smtp_server: serveur SMTP personnalisé (optionnel)
        custom_smtp_port: port SMTP personnalisé (optionnel)
        get_time_func: fonction renvoyant l'heure courante

    Returns:
        bool: succès de l'envoi

    Note:
        Le contenu de l'analyse IA est déjà intégré lors de la génération du HTML, inutile de le réajouter.
    """
    try:
        if not html_file_path or not Path(html_file_path).exists():
            # Le fichier non suffixé peut ne pas exister : on tente quand même la résolution par langue
            lang_files_check = _resolve_language_html_files(html_file_path)
            if not lang_files_check:
                print(f"Erreur : fichier HTML inexistant ou non fourni : {html_file_path}")
                return False

        # Déduit les fichiers HTML par langue (FR + EN)
        lang_files = _resolve_language_html_files(html_file_path)

        # Corps de l'e-mail : HTML de la langue par défaut (FR si disponible, sinon le premier)
        body_path = None
        for lang, path in lang_files:
            if lang == "fr":
                body_path = path
                break
        if body_path is None and lang_files:
            body_path = lang_files[0][1]
        if body_path is None and Path(html_file_path).exists():
            body_path = Path(html_file_path)

        print(f"Fichier HTML utilisé comme corps : {body_path}")
        with open(body_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        domain = from_email.split("@")[-1].lower()

        if custom_smtp_server and custom_smtp_port:
            # Utilise la configuration SMTP personnalisée
            smtp_server = custom_smtp_server
            smtp_port = int(custom_smtp_port)
            # Détermine le mode de chiffrement selon le port : 465=SSL, 587=TLS
            if smtp_port == 465:
                use_tls = False  # Mode SSL (SMTP_SSL)
            elif smtp_port == 587:
                use_tls = True  # Mode TLS (STARTTLS)
            else:
                # Pour les autres ports, on privilégie TLS (plus sûr et plus largement supporté)
                use_tls = True
        elif domain in SMTP_CONFIGS:
            # Utilise la configuration prédéfinie
            config = SMTP_CONFIGS[domain]
            smtp_server = config["server"]
            smtp_port = config["port"]
            use_tls = config["encryption"] == "TLS"
        else:
            print(f"Fournisseur de messagerie non reconnu : {domain}, utilisation de la configuration SMTP générique")
            smtp_server = f"smtp.{domain}"
            smtp_port = 587
            use_tls = True

        # Conteneur "mixed" : partie alternative (texte + HTML) + pièces jointes
        msg = MIMEMultipart("mixed")

        # Définit le header From strictement selon le standard RFC
        sender_name = "TrendRadar"
        msg["From"] = formataddr((sender_name, from_email))

        # Définit le(s) destinataire(s)
        recipients = [addr.strip() for addr in to_email.split(",")]
        if len(recipients) == 1:
            msg["To"] = recipients[0]
        else:
            msg["To"] = ", ".join(recipients)

        # Définit l'objet de l'e-mail
        now = get_time_func() if get_time_func else datetime.now()
        subject = f"Rapport d'analyse des tendances TrendRadar - {report_type} - {now.strftime('%d/%m %H:%M')}"
        msg["Subject"] = Header(subject, "utf-8")

        # Définit les autres headers standards
        msg["MIME-Version"] = "1.0"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        # Partie alternative : texte brut (repli) + HTML
        alt_part = MIMEMultipart("alternative")

        text_content = f"""
Rapport d'analyse des tendances TrendRadar
==========================================
Type de rapport : {report_type}
Heure de génération : {now.strftime('%Y-%m-%d %H:%M:%S')}

Veuillez utiliser un client de messagerie compatible HTML pour consulter le rapport complet.
Les versions FR et EN du rapport sont jointes en pièces jointes.
        """
        text_part = MIMEText(text_content, "plain", "utf-8")
        alt_part.attach(text_part)

        html_part = MIMEText(html_content, "html", "utf-8")
        alt_part.attach(html_part)

        msg.attach(alt_part)

        # Joint les deux versions du rapport (FR + EN) en pièces jointes
        for lang, path in lang_files:
            try:
                with open(path, "rb") as af:
                    attach_part = MIMEApplication(af.read(), _subtype="html")
                attach_filename = f"TrendRadar_{report_type}_{lang}.html"
                attach_part.add_header(
                    "Content-Disposition", "attachment", filename=attach_filename
                )
                msg.attach(attach_part)
                print(f"Pièce jointe ajoutée [{lang}] : {path}")
            except Exception as attach_err:
                # N'échoue pas si une pièce jointe est manquante : on attache ce qui existe
                print(f"Impossible de joindre le fichier [{lang}] {path} : {attach_err}")

        print(f"Envoi de l'e-mail à {to_email}...")
        print(f"Serveur SMTP : {smtp_server}:{smtp_port}")
        print(f"Expéditeur : {from_email}")

        try:
            if use_tls:
                # Mode TLS
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                server.set_debuglevel(0)  # mettre à 1 pour afficher les informations de débogage détaillées
                server.ehlo()
                server.starttls()
                server.ehlo()
            else:
                # Mode SSL
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
                server.set_debuglevel(0)
                server.ehlo()

            # Connexion
            server.login(from_email, password)

            # Envoi de l'e-mail
            server.send_message(msg)
            server.quit()

            print(f"E-mail envoyé avec succès [{report_type}] -> {to_email}")
            return True

        except smtplib.SMTPServerDisconnected:
            print("Échec de l'envoi de l'e-mail : le serveur s'est déconnecté de manière inattendue, vérifiez le réseau ou réessayez plus tard")
            return False

    except smtplib.SMTPAuthenticationError as e:
        print("Échec de l'envoi de l'e-mail : erreur d'authentification, vérifiez l'adresse et le mot de passe / code d'autorisation")
        print(f"Erreur détaillée : {str(e)}")
        return False
    except smtplib.SMTPRecipientsRefused as e:
        print(f"Échec de l'envoi de l'e-mail : adresse du destinataire refusée {e}")
        return False
    except smtplib.SMTPSenderRefused as e:
        print(f"Échec de l'envoi de l'e-mail : adresse de l'expéditeur refusée {e}")
        return False
    except smtplib.SMTPDataError as e:
        print(f"Échec de l'envoi de l'e-mail : erreur de données de l'e-mail {e}")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"Échec de l'envoi de l'e-mail : impossible de se connecter au serveur SMTP {smtp_server}:{smtp_port}")
        print(f"Erreur détaillée : {str(e)}")
        return False
    except Exception as e:
        print(f"Échec de l'envoi de l'e-mail [{report_type}] : {e}")
        import traceback
        traceback.print_exc()
        return False


def send_to_ntfy(
    server_url: str,
    topic: str,
    token: Optional[str],
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 3800,
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    Envoie vers ntfy (envoi par lots, respecte strictement la limite de 4 Ko, prend en charge Tendances + RSS fusionnés + Zone d'affichage autonome)

    Args:
        server_url: ntfy serveur URL
        topic: ntfy objet
        token: ntfy accèdejeton (optionnel) 
        report_data: données du rapport
        report_type: type de rapport
        update_info: informations de mise à jour (optionnel)
        proxy_url: URL du proxy (optionnel)
        mode: mode du rapport (daily/current)
        account_label: libellé du compte (affiché en mode multi-comptes)
        batch_size: taille des lots (octets)
        split_content_func: fonction de découpage du contenu en lots
        rss_items: liste des entrées RSS pour les statistiques (optionnel, pour l'envoi fusionné)
        rss_new_items: liste des nouvelles entrées RSS (optionnel, pour le bloc des nouveautés)

    Returns:
        bool : succès de l'envoi
    """
    # préfixe des journaux
    log_prefix = f"ntfy{account_label}" if account_label else "ntfy"

    # évite les problèmes d'encodage des en-têtes HTTP
    report_type_en_map = {
        "Synthèse de la journée": "Daily Summary",
        "Classement actuel": "Current Ranking",
        "Analyse incrémentale": "Incremental Update",
        "Test de connectivité des notifications": "Notification Test",
    }
    report_type_en = report_type_en_map.get(report_type, "News Report")

    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Markdown": "yes",
        "Title": report_type_en,
        "Priority": "default",
        "Tags": "news",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    # construit l'URL complète en garantissant un format correct
    base_url = server_url.rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    url = f"{base_url}/{topic}"

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # rend le contenu de l'Analyse IA et extrait les données statistiques
    ai_content = _render_ai_analysis(ai_analysis, "ntfy") if ai_analysis else None
    ai_stats = _extract_ai_stats(ai_analysis)

    # récupère le contenu découpé en lots, en réservant de l'espace pour l'en-tête de lot
    header_reserve = get_max_batch_header_size("ntfy")
    batches = split_content_func(
        report_data, "ntfy", update_info, max_bytes=batch_size - header_reserve, mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    # ajoute uniformément les en-têtes de lot (l'espace est déjà réservé, pas de dépassement)
    batches = add_batch_headers(batches, "ntfy", batch_size)

    total_batches = len(batches)
    print(f"{log_prefix} : message divisé en {total_batches} lots à envoyer [{report_type}]")

    # inverse l'ordre des lots pour qu'ils s'affichent dans le bon ordre dans le client ntfy
    # ntfy affiche le message le plus récent en haut, on commence donc l'envoi par le dernier lot
    reversed_batches = list(reversed(batches))

    print(f"{log_prefix} : envoi dans l'ordre inverse (le dernier lot en premier), pour garantir le bon ordre d'affichage côté client")

    # envoi lot par lot (ordre inversé)
    success_count = 0
    for idx, batch_content in enumerate(reversed_batches, 1):
        # calcule le numéro de lot réel (du point de vue de l'utilisateur)
        actual_batch_num = total_batches - idx + 1

        content_size = len(batch_content.encode("utf-8"))
        print(
            f"{log_prefix} : envoi du lot n° {actual_batch_num}/{total_batches} (ordre d'envoi : {idx}/{total_batches}), taille : {content_size} octets [{report_type}]"
        )

        # vérifie la taille du message pour ne pas dépasser 4 Ko
        if content_size > 4096:
            print(f"avertissement : {log_prefix} : le lot n° {actual_batch_num} est trop volumineux ({content_size} octets), il pourrait être refusé")

        # met à jour l'identifiant de lot dans les headers
        current_headers = headers.copy()
        if total_batches > 1:
            current_headers["Title"] = f"{report_type_en} ({actual_batch_num}/{total_batches})"

        try:
            response = requests.post(
                url,
                headers=current_headers,
                data=batch_content.encode("utf-8"),
                proxies=proxies,
                timeout=30,
            )

            if response.status_code == 200:
                print(f"{log_prefix} : lot n° {actual_batch_num}/{total_batches} envoyé avec succès [{report_type}]")
                success_count += 1
                if idx < total_batches:
                    # le serveur public recommande 2 à 3 secondes, l'auto-hébergement peut être plus court
                    interval = 2 if "ntfy.sh" in server_url else 1
                    time.sleep(interval)
            elif response.status_code == 429:
                print(
                    f"{log_prefix} : lot n° {actual_batch_num}/{total_batches} limité en débit [{report_type}], nouvelle tentative après attente"
                )
                time.sleep(10)  # attend 10 secondes avant de réessayer
                # réessaie une fois
                retry_response = requests.post(
                    url,
                    headers=current_headers,
                    data=batch_content.encode("utf-8"),
                    proxies=proxies,
                    timeout=30,
                )
                if retry_response.status_code == 200:
                    print(f"{log_prefix} : nouvelle tentative réussie pour le lot n° {actual_batch_num}/{total_batches} [{report_type}]")
                    success_count += 1
                else:
                    print(
                        f"{log_prefix} : échec de la nouvelle tentative pour le lot n° {actual_batch_num}/{total_batches}, code d'état : {retry_response.status_code}"
                    )
            elif response.status_code == 413:
                print(
                    f"{log_prefix} : lot n° {actual_batch_num}/{total_batches} refusé car trop volumineux [{report_type}], taille du message : {content_size} octets"
                )
            else:
                print(
                    f"{log_prefix} : échec de l'envoi du lot n° {actual_batch_num}/{total_batches} [{report_type}], code d'état : {response.status_code}"
                )
                try:
                    print(f"détails de l'erreur : {response.text}")
                except:
                    pass

        except requests.exceptions.ConnectTimeout:
            print(f"{log_prefix} : délai de connexion dépassé pour le lot n° {actual_batch_num}/{total_batches} [{report_type}]")
        except requests.exceptions.ReadTimeout:
            print(f"{log_prefix} : délai de lecture dépassé pour le lot n° {actual_batch_num}/{total_batches} [{report_type}]")
        except requests.exceptions.ConnectionError as e:
            print(f"{log_prefix} : erreur de connexion pour le lot n° {actual_batch_num}/{total_batches} [{report_type}] : {e}")
        except Exception as e:
            print(f"{log_prefix} : exception lors de l'envoi du lot n° {actual_batch_num}/{total_batches} [{report_type}] : {e}")

    # détermine si l'envoi global a réussi
    if success_count == total_batches:
        print(f"{log_prefix} : les {total_batches} lots ont été envoyés [{report_type}]")
    elif success_count > 0:
        print(f"{log_prefix} : envoi partiellement réussi : {success_count}/{total_batches} lots [{report_type}]")
    else:
        print(f"{log_prefix} : échec total de l'envoi [{report_type}]")
        return False

    return True


def send_to_bark(
    bark_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 3600,
    batch_interval: float = 1.0,
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    Envoie vers Bark (envoi par lots, utilise le format markdown, prend en charge Tendances + RSS fusionnés + Zone d'affichage autonome)

    Args:
        bark_url: Bark URL (contient device_key) 
        report_data: données du rapport
        report_type: type de rapport
        update_info: informations de mise à jour (optionnel)
        proxy_url: URL du proxy (optionnel)
        mode: mode du rapport (daily/current)
        account_label: libellé du compte (affiché en mode multi-comptes)
        batch_size: taille des lots (octets)
        batch_interval: intervalle entre les envois de lots (secondes)
        split_content_func: fonction de découpage du contenu en lots
        rss_items: liste des entrées RSS pour les statistiques (optionnel, pour l'envoi fusionné)
        rss_new_items: liste des nouvelles entrées RSS (optionnel, pour le bloc des nouveautés)

    Returns:
        bool : succès de l'envoi
    """
    # préfixe des journaux
    log_prefix = f"Bark{account_label}" if account_label else "Bark"

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # analyse l'URL Bark, extrait device_key et le point de terminaison de l'API
    # format de l'URL Bark : https://api.day.app/device_key ou https://bark.day.app/device_key
    parsed_url = urlparse(bark_url)
    device_key = parsed_url.path.strip('/').split('/')[0] if parsed_url.path else None

    if not device_key:
        print(f"{log_prefix} : format d'URL invalide, impossible d'extraire device_key : {bark_url}")
        return False

    # construit le bon point de terminaison de l'API
    api_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}/push"

    # rend le contenu de l'Analyse IA et extrait les données statistiques
    ai_content = _render_ai_analysis(ai_analysis, "bark") if ai_analysis else None
    ai_stats = _extract_ai_stats(ai_analysis)

    # récupère le contenu découpé en lots, en réservant de l'espace pour l'en-tête de lot
    header_reserve = get_max_batch_header_size("bark")
    batches = split_content_func(
        report_data, "bark", update_info, max_bytes=batch_size - header_reserve, mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    # ajoute uniformément les en-têtes de lot (l'espace est déjà réservé, pas de dépassement)
    batches = add_batch_headers(batches, "bark", batch_size)

    total_batches = len(batches)
    print(f"{log_prefix} : message divisé en {total_batches} lots à envoyer [{report_type}]")

    # inverse l'ordre des lots pour qu'ils s'affichent dans le bon ordre dans le client Bark
    # Bark affiche le message le plus récent en haut, on commence donc l'envoi par le dernier lot
    reversed_batches = list(reversed(batches))

    print(f"{log_prefix} : envoi dans l'ordre inverse (le dernier lot en premier), pour garantir le bon ordre d'affichage côté client")

    # envoi lot par lot (ordre inversé)
    success_count = 0
    for idx, batch_content in enumerate(reversed_batches, 1):
        # calcule le numéro de lot réel (du point de vue de l'utilisateur)
        actual_batch_num = total_batches - idx + 1

        content_size = len(batch_content.encode("utf-8"))
        print(
            f"{log_prefix} : envoi du lot n° {actual_batch_num}/{total_batches} (ordre d'envoi : {idx}/{total_batches}), taille : {content_size} octets [{report_type}]"
        )

        # vérifie la taille du message (Bark utilise APNs, limite de 4 Ko)
        if content_size > 4096:
            print(
                f"avertissement : {log_prefix} : le lot n° {actual_batch_num}/{total_batches} est trop volumineux ({content_size} octets), il pourrait être refusé"
            )

        # construit le payload JSON
        payload = {
            "title": report_type,
            "markdown": batch_content,
            "device_key": device_key,
            "sound": "default",
            "group": "TrendRadar",
            "action": "none",  # un clic ouvre l'app sans afficher de fenêtre contextuelle, pour faciliter la lecture
        }

        try:
            response = requests.post(
                api_endpoint,
                json=payload,
                proxies=proxies,
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 200:
                    print(f"{log_prefix} : lot n° {actual_batch_num}/{total_batches} envoyé avec succès [{report_type}]")
                    success_count += 1
                    # intervalle entre les lots
                    if idx < total_batches:
                        time.sleep(batch_interval)
                else:
                    print(
                        f"{log_prefix} : échec de l'envoi du lot n° {actual_batch_num}/{total_batches} [{report_type}], erreur : {result.get('message', 'erreur inconnue')}"
                    )
            else:
                print(
                    f"{log_prefix} : échec de l'envoi du lot n° {actual_batch_num}/{total_batches} [{report_type}], code d'état : {response.status_code}"
                )
                try:
                    print(f"détails de l'erreur : {response.text}")
                except:
                    pass

        except requests.exceptions.ConnectTimeout:
            print(f"{log_prefix} : délai de connexion dépassé pour le lot n° {actual_batch_num}/{total_batches} [{report_type}]")
        except requests.exceptions.ReadTimeout:
            print(f"{log_prefix} : délai de lecture dépassé pour le lot n° {actual_batch_num}/{total_batches} [{report_type}]")
        except requests.exceptions.ConnectionError as e:
            print(f"{log_prefix} : erreur de connexion pour le lot n° {actual_batch_num}/{total_batches} [{report_type}] : {e}")
        except Exception as e:
            print(f"{log_prefix} : exception lors de l'envoi du lot n° {actual_batch_num}/{total_batches} [{report_type}] : {e}")

    # détermine si l'envoi global a réussi
    if success_count == total_batches:
        print(f"{log_prefix} : les {total_batches} lots ont été envoyés [{report_type}]")
    elif success_count > 0:
        print(f"{log_prefix} : envoi partiellement réussi : {success_count}/{total_batches} lots [{report_type}]")
    else:
        print(f"{log_prefix} : échec total de l'envoi [{report_type}]")
        return False

    return True


def send_to_slack(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 4000,
    batch_interval: float = 1.0,
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    Envoie vers Slack (envoi par lots, utilise le format mrkdwn, prend en charge Tendances + RSS fusionnés + Zone d'affichage autonome)

    Args:
        webhook_url: Slack Webhook URL
        report_data: données du rapport
        report_type: type de rapport
        update_info: informations de mise à jour (optionnel)
        proxy_url: URL du proxy (optionnel)
        mode: mode du rapport (daily/current)
        account_label: libellé du compte (affiché en mode multi-comptes)
        batch_size: taille des lots (octets)
        batch_interval: intervalle entre les envois de lots (secondes)
        split_content_func: fonction de découpage du contenu en lots
        rss_items: liste des entrées RSS pour les statistiques (optionnel, pour l'envoi fusionné)
        rss_new_items: liste des nouvelles entrées RSS (optionnel, pour le bloc des nouveautés)

    Returns:
        bool : succès de l'envoi
    """
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # préfixe des journaux
    log_prefix = f"Slack{account_label}" if account_label else "Slack"

    # rend le contenu de l'Analyse IA et extrait les données statistiques
    ai_content = _render_ai_analysis(ai_analysis, "slack") if ai_analysis else None
    ai_stats = _extract_ai_stats(ai_analysis)

    # récupère le contenu découpé en lots, en réservant de l'espace pour l'en-tête de lot
    header_reserve = get_max_batch_header_size("slack")
    batches = split_content_func(
        report_data, "slack", update_info, max_bytes=batch_size - header_reserve, mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    # ajoute uniformément les en-têtes de lot (l'espace est déjà réservé, pas de dépassement)
    batches = add_batch_headers(batches, "slack", batch_size)

    print(f"{log_prefix} : message divisé en {len(batches)} lots à envoyer [{report_type}]")

    # envoi lot par lot
    for i, batch_content in enumerate(batches, 1):
        # convertit le Markdown au format mrkdwn
        mrkdwn_content = convert_markdown_to_mrkdwn(batch_content)

        content_size = len(mrkdwn_content.encode("utf-8"))
        print(
            f"{log_prefix} : envoi du lot n° {i}/{len(batches)}, taille : {content_size} octets [{report_type}]"
        )

        # construit le payload Slack (utilise un simple champ text, compatible mrkdwn)
        payload = {"text": mrkdwn_content}

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )

            # les Slack Incoming Webhooks renvoient le texte "ok" en cas de succès
            if response.status_code == 200 and response.text == "ok":
                print(f"{log_prefix} : lot n° {i}/{len(batches)} envoyé avec succès [{report_type}]")
                # intervalle entre les lots
                if i < len(batches):
                    time.sleep(batch_interval)
            else:
                error_msg = response.text if response.text else f"code d'état : {response.status_code}"
                print(
                    f"{log_prefix} : échec de l'envoi du lot n° {i}/{len(batches)} [{report_type}], erreur : {error_msg}"
                )
                return False
        except Exception as e:
            print(f"{log_prefix} : erreur lors de l'envoi du lot n° {i}/{len(batches)} [{report_type}] : {e}")
            return False

    print(f"{log_prefix} : les {len(batches)} lots ont été envoyés [{report_type}]")

    return True


def send_to_generic_webhook(
    webhook_url: str,
    payload_template: Optional[str],
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 4000,
    batch_interval: float = 1.0,
    split_content_func: Optional[Callable] = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    Envoie vers un Webhook générique (envoi par lots, prend en charge un modèle JSON personnalisé, ainsi que Tendances + RSS fusionnés + Zone d'affichage autonome)

    Args:
        webhook_url: Webhook URL
        payload_template: chaîne de modèle JSON, prend en charge les espaces réservés {title} et {content}
        report_data: données du rapport
        report_type: type de rapport
        update_info: informations de mise à jour (optionnel)
        proxy_url: URL du proxy (optionnel)
        mode: mode du rapport (daily/current)
        account_label: libellé du compte (affiché en mode multi-comptes)
        batch_size: taille des lots (octets)
        batch_interval: intervalle entre les envois de lots (secondes)
        split_content_func: fonction de découpage du contenu en lots
        rss_items: liste des entrées RSS pour les statistiques (optionnel, pour l'envoi fusionné)
        rss_new_items: liste des nouvelles entrées RSS (optionnel, pour le bloc des nouveautés)

    Returns:
        bool : succès de l'envoi
    """
    if split_content_func is None:
        raise ValueError("split_content_func is required")

    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # préfixe des journaux
    log_prefix = f"Webhook générique {account_label}" if account_label else "Webhook générique"

    # rend le contenu de l'Analyse IA et extrait les données statistiques (le Webhook générique utilise le format markdown)
    ai_content = _render_ai_analysis(ai_analysis, "wework") if ai_analysis else None
    ai_stats = _extract_ai_stats(ai_analysis)

    # récupère le contenu découpé en lots
    # utilise 'wework' comme format_type pour obtenir une sortie générique au format markdown
    # réserve un espace fixe pour l'enveloppe du modèle
    template_overhead = 200
    batches = split_content_func(
        report_data, "wework", update_info, max_bytes=batch_size - template_overhead, mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    # ajoute uniformément les en-têtes de lot
    batches = add_batch_headers(batches, "wework", batch_size)

    print(f"{log_prefix} : message divisé en {len(batches)} lots à envoyer [{report_type}]")

    # envoi lot par lot
    for i, batch_content in enumerate(batches, 1):
        content_size = len(batch_content.encode("utf-8"))
        print(
            f"{log_prefix} : envoi du lot n° {i}/{len(batches)}, taille : {content_size} octets [{report_type}]"
        )

        try:
            # construit le payload
            if payload_template:
                # simple remplacement de chaîne
                # remarque : content peut contenir des caractères spéciaux JSON, à échapper au préalable
                json_content = json.dumps(batch_content)[1:-1]  # retire les guillemets de début et de fin
                json_title = json.dumps(report_type)[1:-1]
                
                payload_str = payload_template.replace("{content}", json_content).replace("{title}", json_title)
                
                # tente de l'analyser comme objet JSON pour le valider
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError as e:
                    print(f"{log_prefix} : échec de l'analyse du modèle JSON : {e}")
                    # repli sur le format par défaut
                    payload = {"title": report_type, "content": batch_content}
            else:
                # format par défaut
                payload = {"title": report_type, "content": batch_content}

            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                print(f"{log_prefix} : lot n° {i}/{len(batches)} envoyé avec succès [{report_type}]")
                if i < len(batches):
                    time.sleep(batch_interval)
            else:
                print(
                    f"{log_prefix} : échec de l'envoi du lot n° {i}/{len(batches)} [{report_type}], code d'état : {response.status_code}, réponse : {response.text}"
                )
                return False
        except Exception as e:
            print(f"{log_prefix} : erreur lors de l'envoi du lot n° {i}/{len(batches)} [{report_type}] : {e}")
            return False

    print(f"{log_prefix} : les {len(batches)} lots ont été envoyés [{report_type}]")

    return True
