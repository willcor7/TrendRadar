# coding=utf-8
"""
Module d'envoi de notifications

Fournit l'envoi de notifications sur plusieurs canaux, notamment :
- Feishu, DingTalk, WeCom
- Telegram, Slack
- Email, ntfy, Bark

Structure du module :
- formatters : conversion de format du contenu
- batch : utilitaires de traitement par lots
- renderer : rendu du contenu des notifications
- splitter : découpage des messages en lots
- senders : émetteurs de messages (fonction d'envoi pour chaque canal)
- dispatcher : planificateur de notifications multi-comptes
"""

from trendradar.notification.formatters import (
    strip_markdown,
    convert_markdown_to_mrkdwn,
)
from trendradar.notification.batch import (
    get_batch_header,
    get_max_batch_header_size,
    truncate_to_bytes,
    add_batch_headers,
)
from trendradar.notification.renderer import (
    render_feishu_content,
    render_dingtalk_content,
)
from trendradar.notification.splitter import (
    split_content_into_batches,
    DEFAULT_BATCH_SIZES,
)
from trendradar.notification.senders import (
    send_to_feishu,
    send_to_dingtalk,
    send_to_wework,
    send_to_telegram,
    send_to_email,
    send_to_ntfy,
    send_to_bark,
    send_to_slack,
    SMTP_CONFIGS,
)
from trendradar.notification.dispatcher import NotificationDispatcher

__all__ = [
    # conversion de format
    "strip_markdown",
    "convert_markdown_to_mrkdwn",
    # traitement par lots
    "get_batch_header",
    "get_max_batch_header_size",
    "truncate_to_bytes",
    "add_batch_headers",
    # rendu du contenu
    "render_feishu_content",
    "render_dingtalk_content",
    # découpage des messages
    "split_content_into_batches",
    "DEFAULT_BATCH_SIZES",
    # émetteurs de messages
    "send_to_feishu",
    "send_to_dingtalk",
    "send_to_wework",
    "send_to_telegram",
    "send_to_email",
    "send_to_ntfy",
    "send_to_bark",
    "send_to_slack",
    "SMTP_CONFIGS",
    # planificateur de notifications
    "NotificationDispatcher",
]
