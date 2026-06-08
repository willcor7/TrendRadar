# coding=utf-8
"""
Module de chargement de la configuration

Responsable du chargement de la configuration depuis les fichiers YAML et les variables d'environnement.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

import yaml

from .config import parse_multi_account_config, validate_paired_configs
from trendradar.utils.time import DEFAULT_TIMEZONE


def _get_env_bool(key: str) -> Optional[bool]:
    """Récupère une valeur booléenne depuis une variable d'environnement ; retourne None si elle n'est pas définie"""
    value = os.environ.get(key, "").strip().lower()
    if not value:
        return None
    return value in ("true", "1")


def _get_env_int(key: str, default: int = 0) -> int:
    """Récupère une valeur entière depuis une variable d'environnement"""
    value = os.environ.get(key, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_int_or_none(key: str) -> Optional[int]:
    """Récupère une valeur entière depuis une variable d'environnement ; retourne None si elle n'est pas définie"""
    value = os.environ.get(key, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _get_env_str(key: str, default: str = "") -> str:
    """Récupère une valeur de type chaîne depuis une variable d'environnement"""
    return os.environ.get(key, "").strip() or default


def _load_app_config(config_data: Dict) -> Dict:
    """Charge la configuration de l'application"""
    app_config = config_data.get("app", {})
    advanced = config_data.get("advanced", {})
    return {
        "VERSION_CHECK_URL": advanced.get("version_check_url", ""),
        "CONFIGS_VERSION_CHECK_URL": advanced.get("configs_version_check_url", ""),
        "SHOW_VERSION_UPDATE": app_config.get("show_version_update", True),
        "TIMEZONE": _get_env_str("TIMEZONE") or app_config.get("timezone", DEFAULT_TIMEZONE),
        "DEBUG": _get_env_bool("DEBUG") if _get_env_bool("DEBUG") is not None else advanced.get("debug", False),
    }


def _load_crawler_config(config_data: Dict) -> Dict:
    """Charge la configuration du collecteur"""
    advanced = config_data.get("advanced", {})
    crawler_config = advanced.get("crawler", {})
    platforms_config = config_data.get("platforms", {})
    return {
        "REQUEST_INTERVAL": crawler_config.get("request_interval", 100),
        "USE_PROXY": crawler_config.get("use_proxy", False),
        "DEFAULT_PROXY": crawler_config.get("default_proxy", ""),
        "ENABLE_CRAWLER": platforms_config.get("enabled", True),
        "PLATFORMS_API_URL": _get_env_str("PLATFORMS_API_URL") or platforms_config.get("api_url", ""),
    }


def _load_report_config(config_data: Dict) -> Dict:
    """Charge la configuration des rapports"""
    report_config = config_data.get("report", {})

    # Surcharge par variables d'environnement
    sort_by_position_env = _get_env_bool("SORT_BY_POSITION_FIRST")
    max_news_env = _get_env_int("MAX_NEWS_PER_KEYWORD")

    return {
        "REPORT_MODE": report_config.get("mode", "daily"),
        "DISPLAY_MODE": report_config.get("display_mode", "keyword"),
        "RANK_THRESHOLD": report_config.get("rank_threshold", 10),
        "SORT_BY_POSITION_FIRST": sort_by_position_env if sort_by_position_env is not None else report_config.get("sort_by_position_first", False),
        "MAX_NEWS_PER_KEYWORD": max_news_env or report_config.get("max_news_per_keyword", 0),
    }


def _load_notification_config(config_data: Dict) -> Dict:
    """Charge la configuration des notifications"""
    notification = config_data.get("notification", {})
    advanced = config_data.get("advanced", {})
    batch_size = advanced.get("batch_size", {})

    return {
        "ENABLE_NOTIFICATION": notification.get("enabled", True),
        "MESSAGE_BATCH_SIZE": batch_size.get("default", 4000),
        "DINGTALK_BATCH_SIZE": batch_size.get("dingtalk", 20000),
        "FEISHU_BATCH_SIZE": batch_size.get("feishu", 29000),
        "BARK_BATCH_SIZE": batch_size.get("bark", 3600),
        "SLACK_BATCH_SIZE": batch_size.get("slack", 4000),
        "BATCH_SEND_INTERVAL": advanced.get("batch_send_interval", 1.0),
        "FEISHU_MESSAGE_SEPARATOR": advanced.get("feishu_message_separator", "---"),
        "MAX_ACCOUNTS_PER_CHANNEL": _get_env_int("MAX_ACCOUNTS_PER_CHANNEL") or advanced.get("max_accounts_per_channel", 3),
    }


def _load_schedule_config(config_data: Dict) -> Dict:
    """
    Charge la configuration de planification unifiée.

    Lue depuis la section schedule de config.yaml ; prend en charge la surcharge par variables d'environnement.
    """
    schedule = config_data.get("schedule", {})

    # Surcharge par variables d'environnement
    enabled_env = _get_env_bool("SCHEDULE_ENABLED")
    preset_env = _get_env_str("SCHEDULE_PRESET")

    enabled = enabled_env if enabled_env is not None else schedule.get("enabled", False)
    preset = preset_env or schedule.get("preset", "always_on")

    return {
        "enabled": enabled,
        "preset": preset,
    }


def _load_timeline_data(config_dir: str = "config") -> Dict:
    """
    Charge timeline.yaml.

    Args:
        config_dir: chemin du répertoire de configuration

    Returns:
        les données complètes de timeline.yaml ; retourne un modèle vide s'il est introuvable
    """
    timeline_path = Path(config_dir) / "timeline.yaml"
    if not timeline_path.exists():
        print(f"[planification] timeline.yaml introuvable : {timeline_path}, utilisation d'un modèle vide")
        return {
            "presets": {},
            "custom": {
                "default": {
                    "collect": True,
                    "analyze": False,
                    "push": False,
                    "report_mode": "current",
                    "ai_mode": "follow_report",
                    "once": {"analyze": False, "push": False},
                },
                "periods": {},
                "day_plans": {"all_day": {"periods": []}},
                "week_map": {i: "all_day" for i in range(1, 8)},
            },
        }

    with open(timeline_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    print(f"[planification] timeline.yaml chargé avec succès : {timeline_path}")
    return data or {}


def _load_weight_config(config_data: Dict) -> Dict:
    """Charge la configuration des poids"""
    advanced = config_data.get("advanced", {})
    weight = advanced.get("weight", {})
    return {
        "RANK_WEIGHT": weight.get("rank", 0.6),
        "FREQUENCY_WEIGHT": weight.get("frequency", 0.3),
        "HOTNESS_WEIGHT": weight.get("hotness", 0.1),
    }


def _load_rss_config(config_data: Dict) -> Dict:
    """Charge la configuration RSS"""
    rss = config_data.get("rss", {})
    advanced = config_data.get("advanced", {})
    advanced_rss = advanced.get("rss", {})
    advanced_crawler = advanced.get("crawler", {})

    # Configuration du proxy RSS : on privilégie le proxy dédié au RSS, sinon on réutilise le default_proxy du collecteur
    rss_proxy_url = advanced_rss.get("proxy_url", "") or advanced_crawler.get("default_proxy", "")

    # Configuration du filtrage par fraîcheur
    freshness_filter = rss.get("freshness_filter", {})

    # On valide et on fixe la valeur par défaut de max_age_days
    raw_max_age = freshness_filter.get("max_age_days", 3)
    try:
        max_age_days = int(raw_max_age)
        if max_age_days < 0:
            print(f"[avertissement] RSS freshness_filter.max_age_days est négatif ({max_age_days}), utilisation de la valeur par défaut 3")
            max_age_days = 3
    except (ValueError, TypeError):
        print(f"[avertissement] RSS freshness_filter.max_age_days : format incorrect ({raw_max_age}), utilisation de la valeur par défaut 3")
        max_age_days = 3

    # La configuration RSS est lue directement depuis config.yaml et ne prend plus en charge les variables d'environnement
    return {
        "ENABLED": rss.get("enabled", False),
        "REQUEST_INTERVAL": advanced_rss.get("request_interval", 2000),
        "TIMEOUT": advanced_rss.get("timeout", 15),
        "USE_PROXY": advanced_rss.get("use_proxy", False),
        "PROXY_URL": rss_proxy_url,
        "FEEDS": rss.get("feeds", []),
        "FRESHNESS_FILTER": {
            "ENABLED": freshness_filter.get("enabled", True),  # activé par défaut
            "MAX_AGE_DAYS": max_age_days,
        },
    }


def _load_display_config(config_data: Dict) -> Dict:
    """Charge la configuration d'affichage du contenu envoyé"""
    display = config_data.get("display", {})
    regions = display.get("regions", {})
    standalone = display.get("standalone", {})

    # Ordre des zones par défaut
    default_region_order = ["hotlist", "rss", "new_items", "standalone", "ai_analysis"]
    region_order = display.get("region_order", default_region_order)

    # On vérifie que les valeurs de region_order sont valides
    valid_regions = {"hotlist", "rss", "new_items", "standalone", "ai_analysis"}
    region_order = [r for r in region_order if r in valid_regions]

    # Si la liste est vide après filtrage, on utilise l'ordre par défaut
    if not region_order:
        region_order = default_region_order

    return {
        # Ordre d'affichage des zones
        "REGION_ORDER": region_order,
        # Interrupteurs des zones
        "REGIONS": {
            "HOTLIST": regions.get("hotlist", True),
            "NEW_ITEMS": regions.get("new_items", True),
            "RSS": regions.get("rss", True),
            "STANDALONE": regions.get("standalone", False),
            "AI_ANALYSIS": regions.get("ai_analysis", True),
        },
        # Configuration de la zone d'affichage autonome
        "STANDALONE": {
            "PLATFORMS": standalone.get("platforms", []),
            "RSS_FEEDS": standalone.get("rss_feeds", []),
            "MAX_ITEMS": standalone.get("max_items", 20),
        },
    }


def _load_ai_config(config_data: Dict) -> Dict:
    """Charge la configuration du modèle IA (format LiteLLM)"""
    ai_config = config_data.get("ai", {})

    timeout_env = _get_env_int_or_none("AI_TIMEOUT")

    return {
        # Configuration principale LiteLLM
        "MODEL": _get_env_str("AI_MODEL") or ai_config.get("model", ""),
        "API_KEY": _get_env_str("AI_API_KEY") or ai_config.get("api_key", ""),
        "API_BASE": _get_env_str("AI_API_BASE") or ai_config.get("api_base", ""),

        # Paramètres de génération
        "TIMEOUT": timeout_env if timeout_env is not None else ai_config.get("timeout", 120),
        "TEMPERATURE": ai_config.get("temperature", 1.0),
        "MAX_TOKENS": ai_config.get("max_tokens", 5000),

        # Options avancées LiteLLM
        "NUM_RETRIES": ai_config.get("num_retries", 2),
        "FALLBACK_MODELS": ai_config.get("fallback_models", []),
        "EXTRA_PARAMS": ai_config.get("extra_params", {}),
    }


def _load_ai_analysis_config(config_data: Dict) -> Dict:
    """Charge la configuration de l'analyse IA (configuration fonctionnelle ; pour la configuration du modèle, voir _load_ai_config)"""
    ai_config = config_data.get("ai_analysis", {})

    enabled_env = _get_env_bool("AI_ANALYSIS_ENABLED")

    return {
        "ENABLED": enabled_env if enabled_env is not None else ai_config.get("enabled", False),
        "LANGUAGE": ai_config.get("language", "Chinese"),
        "PROMPT_FILE": ai_config.get("prompt_file", "ai_analysis_prompt.txt"),
        "MODE": ai_config.get("mode", "follow_report"),
        "MAX_NEWS_FOR_ANALYSIS": ai_config.get("max_news_for_analysis", 50),
        "INCLUDE_RSS": ai_config.get("include_rss", True),
        "INCLUDE_RANK_TIMELINE": ai_config.get("include_rank_timeline", False),
        "INCLUDE_STANDALONE": ai_config.get("include_standalone", False),
    }


def _load_ai_translation_config(config_data: Dict) -> Dict:
    """Charge la configuration de la traduction IA (configuration fonctionnelle ; pour la configuration du modèle, voir _load_ai_config)"""
    trans_config = config_data.get("ai_translation", {})

    enabled_env = _get_env_bool("AI_TRANSLATION_ENABLED")

    scope = trans_config.get("scope", {})

    return {
        "ENABLED": enabled_env if enabled_env is not None else trans_config.get("enabled", False),
        "LANGUAGE": _get_env_str("AI_TRANSLATION_LANGUAGE") or trans_config.get("language", "English"),
        "PROMPT_FILE": trans_config.get("prompt_file", "ai_translation_prompt.txt"),
        "SCOPE": {
            "HOTLIST": scope.get("hotlist", True),
            "RSS": scope.get("rss", True),
            "STANDALONE": scope.get("standalone", True),
        },
    }


def _load_ai_filter_config(config_data: Dict) -> Dict:
    """Charge la configuration du filtrage intelligent par IA (l'activation est contrôlée par filter.method)"""
    ai_filter = config_data.get("ai_filter", {})

    return {
        "BATCH_SIZE": ai_filter.get("batch_size", 200),
        "BATCH_INTERVAL": ai_filter.get("batch_interval", 5),
        "INTERESTS_FILE": ai_filter.get("interests_file"),  # None = utilise par défaut config/ai_interests.txt
        "PROMPT_FILE": ai_filter.get("prompt_file", "prompt.txt"),
        "EXTRACT_PROMPT_FILE": ai_filter.get("extract_prompt_file", "extract_prompt.txt"),
        "UPDATE_TAGS_PROMPT_FILE": ai_filter.get("update_tags_prompt_file", "update_tags_prompt.txt"),
        "RECLASSIFY_THRESHOLD": ai_filter.get("reclassify_threshold", 0.6),
        "MIN_SCORE": float(ai_filter.get("min_score", 0)),
    }


def _load_filter_config(config_data: Dict) -> Dict:
    """Charge la configuration de la stratégie de filtrage"""
    filter_cfg = config_data.get("filter", {})

    # Compatibilité avec les variables d'environnement : AI_FILTER_ENABLED=true → method=ai
    env_ai_filter = _get_env_bool("AI_FILTER_ENABLED")

    method = filter_cfg.get("method", "keyword")
    if env_ai_filter is True:
        method = "ai"

    # Compatibilité avec l'ancienne configuration : si ai_filter.enabled=true et que filter.method n'est pas défini explicitement
    if method == "keyword" and not filter_cfg.get("method"):
        ai_filter = config_data.get("ai_filter", {})
        if ai_filter.get("enabled", False):
            method = "ai"

    return {
        "METHOD": method,  # "keyword" | "ai"
        "PRIORITY_SORT_ENABLED": filter_cfg.get("priority_sort_enabled", False),  # interrupteur du tri par priorité des étiquettes en mode IA
    }


def _load_storage_config(config_data: Dict) -> Dict:
    """Charge la configuration du stockage"""
    storage = config_data.get("storage", {})
    formats = storage.get("formats", {})
    local = storage.get("local", {})
    remote = storage.get("remote", {})
    pull = storage.get("pull", {})

    txt_enabled_env = _get_env_bool("STORAGE_TXT_ENABLED")
    html_enabled_env = _get_env_bool("STORAGE_HTML_ENABLED")
    pull_enabled_env = _get_env_bool("PULL_ENABLED")

    return {
        "BACKEND": _get_env_str("STORAGE_BACKEND") or storage.get("backend", "auto"),
        "FORMATS": {
            "SQLITE": formats.get("sqlite", True),
            "TXT": txt_enabled_env if txt_enabled_env is not None else formats.get("txt", True),
            "HTML": html_enabled_env if html_enabled_env is not None else formats.get("html", True),
        },
        "LOCAL": {
            "DATA_DIR": local.get("data_dir", "output"),
            "RETENTION_DAYS": _get_env_int("LOCAL_RETENTION_DAYS") or local.get("retention_days", 0),
        },
        "REMOTE": {
            "ENDPOINT_URL": _get_env_str("S3_ENDPOINT_URL") or remote.get("endpoint_url", ""),
            "BUCKET_NAME": _get_env_str("S3_BUCKET_NAME") or remote.get("bucket_name", ""),
            "ACCESS_KEY_ID": _get_env_str("S3_ACCESS_KEY_ID") or remote.get("access_key_id", ""),
            "SECRET_ACCESS_KEY": _get_env_str("S3_SECRET_ACCESS_KEY") or remote.get("secret_access_key", ""),
            "REGION": _get_env_str("S3_REGION") or remote.get("region", ""),
            "RETENTION_DAYS": _get_env_int("REMOTE_RETENTION_DAYS") or remote.get("retention_days", 0),
        },
        "PULL": {
            "ENABLED": pull_enabled_env if pull_enabled_env is not None else pull.get("enabled", False),
            "DAYS": _get_env_int("PULL_DAYS") or pull.get("days", 7),
        },
    }


def _load_webhook_config(config_data: Dict) -> Dict:
    """Charge la configuration des Webhooks"""
    notification = config_data.get("notification", {})
    channels = notification.get("channels", {})

    # Configuration de chaque canal
    feishu = channels.get("feishu", {})
    dingtalk = channels.get("dingtalk", {})
    wework = channels.get("wework", {})
    telegram = channels.get("telegram", {})
    email = channels.get("email", {})
    ntfy = channels.get("ntfy", {})
    bark = channels.get("bark", {})
    slack = channels.get("slack", {})
    generic = channels.get("generic_webhook", {})

    return {
        # Feishu
        "FEISHU_WEBHOOK_URL": _get_env_str("FEISHU_WEBHOOK_URL") or feishu.get("webhook_url", ""),
        # DingTalk
        "DINGTALK_WEBHOOK_URL": _get_env_str("DINGTALK_WEBHOOK_URL") or dingtalk.get("webhook_url", ""),
        # WeCom
        "WEWORK_WEBHOOK_URL": _get_env_str("WEWORK_WEBHOOK_URL") or wework.get("webhook_url", ""),
        "WEWORK_MSG_TYPE": _get_env_str("WEWORK_MSG_TYPE") or wework.get("msg_type", "markdown"),
        # Telegram
        "TELEGRAM_BOT_TOKEN": _get_env_str("TELEGRAM_BOT_TOKEN") or telegram.get("bot_token", ""),
        "TELEGRAM_CHAT_ID": _get_env_str("TELEGRAM_CHAT_ID") or telegram.get("chat_id", ""),
        # e-mail
        "EMAIL_FROM": _get_env_str("EMAIL_FROM") or email.get("from", ""),
        "EMAIL_PASSWORD": _get_env_str("EMAIL_PASSWORD") or email.get("password", ""),
        "EMAIL_TO": _get_env_str("EMAIL_TO") or email.get("to", ""),
        "EMAIL_SMTP_SERVER": _get_env_str("EMAIL_SMTP_SERVER") or email.get("smtp_server", ""),
        "EMAIL_SMTP_PORT": _get_env_str("EMAIL_SMTP_PORT") or email.get("smtp_port", ""),
        # ntfy
        "NTFY_SERVER_URL": _get_env_str("NTFY_SERVER_URL") or ntfy.get("server_url") or "https://ntfy.sh",
        "NTFY_TOPIC": _get_env_str("NTFY_TOPIC") or ntfy.get("topic", ""),
        "NTFY_TOKEN": _get_env_str("NTFY_TOKEN") or ntfy.get("token", ""),
        # Bark
        "BARK_URL": _get_env_str("BARK_URL") or bark.get("url", ""),
        # Slack
        "SLACK_WEBHOOK_URL": _get_env_str("SLACK_WEBHOOK_URL") or slack.get("webhook_url", ""),
        # Webhook générique
        "GENERIC_WEBHOOK_URL": _get_env_str("GENERIC_WEBHOOK_URL") or generic.get("webhook_url", ""),
        "GENERIC_WEBHOOK_TEMPLATE": _get_env_str("GENERIC_WEBHOOK_TEMPLATE") or generic.get("payload_template", ""),
    }


def _print_notification_sources(config: Dict) -> None:
    """Affiche les informations sur la source de configuration des canaux de notification"""
    notification_sources = []
    max_accounts = config["MAX_ACCOUNTS_PER_CHANNEL"]

    if config["FEISHU_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["FEISHU_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "variable d'environnement" if os.environ.get("FEISHU_WEBHOOK_URL") else "fichier de configuration"
        notification_sources.append(f"Feishu ({source}, {count} compte(s))")

    if config["DINGTALK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["DINGTALK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "variable d'environnement" if os.environ.get("DINGTALK_WEBHOOK_URL") else "fichier de configuration"
        notification_sources.append(f"DingTalk ({source}, {count} compte(s))")

    if config["WEWORK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["WEWORK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "variable d'environnement" if os.environ.get("WEWORK_WEBHOOK_URL") else "fichier de configuration"
        notification_sources.append(f"WeCom ({source}, {count} compte(s))")

    if config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]:
        tokens = parse_multi_account_config(config["TELEGRAM_BOT_TOKEN"])
        chat_ids = parse_multi_account_config(config["TELEGRAM_CHAT_ID"])
        valid, count = validate_paired_configs(
            {"bot_token": tokens, "chat_id": chat_ids},
            "Telegram",
            required_keys=["bot_token", "chat_id"]
        )
        if valid and count > 0:
            count = min(count, max_accounts)
            token_source = "variable d'environnement" if os.environ.get("TELEGRAM_BOT_TOKEN") else "fichier de configuration"
            notification_sources.append(f"Telegram ({token_source}, {count} compte(s))")

    if config["EMAIL_FROM"] and config["EMAIL_PASSWORD"] and config["EMAIL_TO"]:
        from_source = "variable d'environnement" if os.environ.get("EMAIL_FROM") else "fichier de configuration"
        notification_sources.append(f"e-mail ({from_source})")

    if config["NTFY_SERVER_URL"] and config["NTFY_TOPIC"]:
        topics = parse_multi_account_config(config["NTFY_TOPIC"])
        tokens = parse_multi_account_config(config["NTFY_TOKEN"])
        if tokens:
            valid, count = validate_paired_configs(
                {"topic": topics, "token": tokens},
                "ntfy"
            )
            if valid and count > 0:
                count = min(count, max_accounts)
                server_source = "variable d'environnement" if os.environ.get("NTFY_SERVER_URL") else "fichier de configuration"
                notification_sources.append(f"ntfy ({server_source}, {count} compte(s))")
        else:
            count = min(len(topics), max_accounts)
            server_source = "variable d'environnement" if os.environ.get("NTFY_SERVER_URL") else "fichier de configuration"
            notification_sources.append(f"ntfy ({server_source}, {count} compte(s))")

    if config["BARK_URL"]:
        accounts = parse_multi_account_config(config["BARK_URL"])
        count = min(len(accounts), max_accounts)
        bark_source = "variable d'environnement" if os.environ.get("BARK_URL") else "fichier de configuration"
        notification_sources.append(f"Bark ({bark_source}, {count} compte(s))")

    if config["SLACK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["SLACK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        slack_source = "variable d'environnement" if os.environ.get("SLACK_WEBHOOK_URL") else "fichier de configuration"
        notification_sources.append(f"Slack ({slack_source}, {count} compte(s))")

    if config.get("GENERIC_WEBHOOK_URL"):
        accounts = parse_multi_account_config(config["GENERIC_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "variable d'environnement" if os.environ.get("GENERIC_WEBHOOK_URL") else "fichier de configuration"
        notification_sources.append(f"Webhook générique ({source}, {count} compte(s))")

    if notification_sources:
        print(f"Source de configuration des canaux de notification : {', '.join(notification_sources)}")
        print(f"Nombre maximal de comptes par canal : {max_accounts}")
    else:
        print("Aucun canal de notification configuré")


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge le fichier de configuration.

    Args:
        config_path: chemin du fichier de configuration ; par défaut, récupéré depuis la variable d'environnement CONFIG_PATH ou config/config.yaml

    Returns:
        un dictionnaire contenant toute la configuration

    Raises:
        FileNotFoundError: le fichier de configuration n'existe pas
    """
    if config_path is None:
        config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

    if not Path(config_path).exists():
        raise FileNotFoundError(f"Le fichier de configuration {config_path} n'existe pas")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    print(f"Fichier de configuration chargé avec succès : {config_path}")

    # On fusionne toute la configuration
    config = {}

    # Configuration de l'application
    config.update(_load_app_config(config_data))

    # Configuration du collecteur
    config.update(_load_crawler_config(config_data))

    # Configuration des rapports
    config.update(_load_report_config(config_data))

    # Configuration des notifications
    config.update(_load_notification_config(config_data))

    # Configuration de planification unifiée
    config["SCHEDULE"] = _load_schedule_config(config_data)
    config["_TIMELINE_DATA"] = _load_timeline_data(
        str(Path(config_path).parent) if config_path else "config"
    )

    # Configuration des poids
    config["WEIGHT_CONFIG"] = _load_weight_config(config_data)

    # Configuration des plateformes
    platforms_config = config_data.get("platforms", {})
    config["PLATFORMS"] = [p for p in platforms_config.get("sources", []) if p.get("enabled", True)]

    # Configuration RSS
    config["RSS"] = _load_rss_config(config_data)

    # Configuration partagée du modèle IA
    config["AI"] = _load_ai_config(config_data)

    # Configuration de l'analyse IA
    config["AI_ANALYSIS"] = _load_ai_analysis_config(config_data)

    # Configuration de la traduction IA
    config["AI_TRANSLATION"] = _load_ai_translation_config(config_data)

    # Configuration du filtrage intelligent par IA
    config["AI_FILTER"] = _load_ai_filter_config(config_data)

    # Configuration de la stratégie de filtrage
    config["FILTER"] = _load_filter_config(config_data)

    # Configuration d'affichage du contenu envoyé
    config["DISPLAY"] = _load_display_config(config_data)

    # Configuration du stockage
    config["STORAGE"] = _load_storage_config(config_data)

    # Configuration des Webhooks
    config.update(_load_webhook_config(config_data))

    # On affiche la source de configuration des canaux de notification
    _print_notification_sources(config)

    return config
