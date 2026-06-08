"""
TrendRadar MCP Server - implémentation FastMCP 2.0

Fournit un serveur d'outils MCP de niveau production grâce à FastMCP 2.0.
Prend en charge deux modes de transport : stdio et HTTP.
"""

import asyncio
import json
from typing import List, Optional, Dict, Union

from fastmcp import FastMCP

from .tools.data_query import DataQueryTools
from .tools.analytics import AnalyticsTools
from .tools.search_tools import SearchTools
from .tools.config_mgmt import ConfigManagementTools
from .tools.system import SystemManagementTools
from .tools.storage_sync import StorageSyncTools
from .tools.article_reader import ArticleReaderTools
from .tools.notification import NotificationTools
from .utils.date_parser import DateParser
from .utils.errors import MCPError


# Crée l'application FastMCP 2.0
mcp = FastMCP('trendradar-news')

# Instances d'outils globales (initialisées à la première requête)
_tools_instances = {}


def _get_tools(project_root: Optional[str] = None):
    """Récupère ou crée les instances d'outils (modèle singleton)"""
    if not _tools_instances:
        _tools_instances['data'] = DataQueryTools(project_root)
        _tools_instances['analytics'] = AnalyticsTools(project_root)
        _tools_instances['search'] = SearchTools(project_root)
        _tools_instances['config'] = ConfigManagementTools(project_root)
        _tools_instances['system'] = SystemManagementTools(project_root)
        _tools_instances['storage'] = StorageSyncTools(project_root)
        _tools_instances['article'] = ArticleReaderTools(project_root)
        _tools_instances['notification'] = NotificationTools(project_root)
    return _tools_instances


# ==================== Ressources MCP ====================

@mcp.resource("config://platforms")
async def get_platforms_resource() -> str:
    """
    Récupère la liste des plateformes prises en charge

    Retourne toutes les informations des plateformes configurées dans config.yaml, y compris l'ID et le nom.
    """
    tools = _get_tools()
    config = await asyncio.to_thread(
        tools['config'].get_current_config, section="crawler"
    )
    return json.dumps({
        "platforms": config.get("platforms", []),
        "description": "Liste des plateformes de palmarès prises en charge par TrendRadar"
    }, ensure_ascii=False, indent=2)


@mcp.resource("config://rss-feeds")
async def get_rss_feeds_resource() -> str:
    """
    Récupère la liste des sources d'abonnement RSS

    Retourne les informations de toutes les sources RSS actuellement configurées.
    """
    tools = _get_tools()
    status = await asyncio.to_thread(tools['data'].get_rss_feeds_status)
    return json.dumps({
        "feeds": status.get("today_feeds", {}),
        "description": "Liste des sources d'abonnement RSS prises en charge par TrendRadar"
    }, ensure_ascii=False, indent=2)


@mcp.resource("data://available-dates")
async def get_available_dates_resource() -> str:
    """
    Récupère la plage de dates de données disponible

    Retourne la liste des dates consultables dans le stockage local.
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['storage'].list_available_dates, source="local"
    )
    return json.dumps({
        "dates": result.get("data", {}).get("local", {}).get("dates", []),
        "description": "Liste des dates consultables dans le stockage local"
    }, ensure_ascii=False, indent=2)


@mcp.resource("config://keywords")
async def get_keywords_resource() -> str:
    """
    Récupère la configuration des mots-clés

    Retourne les groupes de mots-clés configurés dans frequency_words.txt.
    """
    tools = _get_tools()
    config = await asyncio.to_thread(
        tools['config'].get_current_config, section="keywords"
    )
    return json.dumps({
        "word_groups": config.get("word_groups", []),
        "total_groups": config.get("total_groups", 0),
        "description": "Configuration des mots-clés de TrendRadar"
    }, ensure_ascii=False, indent=2)


# ==================== Outil d'analyse de dates (à appeler en priorité) ====================

@mcp.tool
async def resolve_date_range(
    expression: str
) -> str:
    """
    [À appeler en priorité, recommandé] Analyse une expression de date en langage naturel en une plage de dates standard

    **Pourquoi cet outil est-il nécessaire ?**
    Les utilisateurs emploient souvent des expressions en langage naturel comme "cette semaine" ou "les 7 derniers jours",
    mais si le modèle IA calcule lui-même les dates, le résultat peut être incohérent. Cet outil effectue le calcul
    côté serveur avec l'heure actuelle exacte, garantissant que tous les modèles IA obtiennent une plage de dates cohérente.

    **Flux d'utilisation recommandé :**
    1. L'utilisateur dit "analyse le sentiment sur l'IA cette semaine"
    2. L'IA appelle resolve_date_range("cette semaine") → obtient la plage de dates exacte
    3. L'IA appelle analyze_sentiment(topic="ai", date_range=le date_range retourné à l'étape précédente)

    Args:
        expression: expression de date en langage naturel, prend en charge :
            - jour unique : "aujourd'hui", "hier", "today", "yesterday"
            - semaine : "cette semaine", "la semaine dernière", "this week", "last week"
            - mois : "ce mois", "le mois dernier", "this month", "last month"
            - N derniers jours : "7 derniers jours", "30 derniers jours", "last 7 days", "last 30 days"
            - dynamique : "5 derniers jours", "last 10 days" (nombre de jours quelconque)

    Returns:
        plage de dates au format JSON, directement utilisable comme paramètre date_range des autres outils :
        {
            "success": true,
            "expression": "cette semaine",
            "date_range": {
                "start": "2025-11-18",
                "end": "2025-11-26"
            },
            "current_date": "2025-11-26",
            "description": "cette semaine (du lundi au dimanche, du 11-18 au 11-26)"
        }

    Examples:
        Utilisateur : "analyse le sentiment sur l'IA cette semaine"
        Étapes d'appel de l'IA :
        1. resolve_date_range("cette semaine")
           → {"date_range": {"start": "2025-11-18", "end": "2025-11-26"}, ...}
        2. analyze_sentiment(topic="ai", date_range={"start": "2025-11-18", "end": "2025-11-26"})

        Utilisateur : "regarde les actualités Tesla des 7 derniers jours"
        Étapes d'appel de l'IA :
        1. resolve_date_range("7 derniers jours")
           → {"date_range": {"start": "2025-11-20", "end": "2025-11-26"}, ...}
        2. search_news(query="Tesla", date_range={"start": "2025-11-20", "end": "2025-11-26"})
    """
    try:
        result = await asyncio.to_thread(DateParser.resolve_date_range_expression, expression)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except MCPError as e:
        return json.dumps({
            "success": False,
            "error": e.to_dict()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


# ==================== Outils de requête de données ====================

@mcp.tool
async def get_latest_news(
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    Récupère le dernier lot de données d'actualités collectées, pour avoir un aperçu rapide des sujets populaires actuels

    Args:
        platforms: liste des ID de plateformes, par ex. ['zhihu', 'weibo'], utilise toutes les plateformes si non précisé
        limit: limite du nombre de résultats, 50 par défaut, 1000 maximum
        include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

    Returns:
        liste d'actualités au format JSON

    **Conseils d'affichage des données**
    - Affiche par défaut toutes les données retournées, sauf demande explicite de synthèse de l'utilisateur
    - Ne filtre que lorsque l'utilisateur demande de "résumer" ou de "garder l'essentiel"
    - Si l'utilisateur demande "pourquoi seule une partie est affichée", c'est qu'il a besoin des données complètes
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['data'].get_latest_news,
        platforms=platforms, limit=limit, include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_trending_topics(
    top_n: int = 10,
    mode: str = 'current',
    extract_mode: str = 'keywords'
) -> str:
    """
    Récupère les statistiques des sujets tendances

    Args:
        top_n: retourne les TOP N sujets, 10 par défaut
        mode: mode temporel
            - "daily": statistiques cumulées de la journée
            - "current": statistiques du dernier lot de données (par défaut)
        extract_mode: mode d'extraction
            - "keywords": comptabilise les mots-clés prédéfinis (basé sur config/frequency_words.txt, par défaut)
            - "auto_extract": extrait automatiquement les mots de fréquence des titres (sans prédéfinition, découverte automatique des sujets)

    Returns:
        liste des statistiques de fréquence des sujets au format JSON

    Examples:
        - Avec les mots-clés prédéfinis : get_trending_topics(mode="current")
        - Extraction automatique des sujets : get_trending_topics(extract_mode="auto_extract", top_n=20)
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['data'].get_trending_topics,
        top_n=top_n, mode=mode, extract_mode=extract_mode
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== Outils de requête de données RSS ====================

@mcp.tool
async def get_latest_rss(
    feeds: Optional[List[str]] = None,
    days: int = 1,
    limit: int = 50,
    include_summary: bool = False
) -> str:
    """
    Récupère les dernières données d'abonnements RSS (prend en charge la requête sur plusieurs jours)

    Les données RSS sont stockées séparément des actualités de palmarès, affichées sous forme de flux temporel, adaptées pour récupérer le contenu le plus récent d'une source précise.

    Args:
        feeds: liste des ID de sources RSS, par ex. ['hacker-news', '36kr'], retourne toutes les sources si non précisé
        days: récupère les données des N derniers jours, 1 par défaut (aujourd'hui uniquement), 30 maximum
        limit: limite du nombre de résultats, 50 par défaut, 500 maximum
        include_summary: indique s'il faut inclure le résumé de l'article, False par défaut (économie de tokens)

    Returns:
        liste des entrées RSS au format JSON

    Examples:
        - get_latest_rss()
        - get_latest_rss(days=7, feeds=['hacker-news'])
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['data'].get_latest_rss,
        feeds=feeds, days=days, limit=limit, include_summary=include_summary
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def search_rss(
    keyword: str,
    feeds: Optional[List[str]] = None,
    days: int = 7,
    limit: int = 50,
    include_summary: bool = False
) -> str:
    """
    Recherche dans les données RSS

    Recherche dans les données d'abonnements RSS les articles contenant le mot-clé indiqué.

    Args:
        keyword: mot-clé de recherche (obligatoire)
        feeds: liste des ID de sources RSS, par ex. ['hacker-news', '36kr']
               - si non précisé : recherche dans toutes les sources RSS
        days: recherche dans les données des N derniers jours, 7 jours par défaut, 30 maximum
        limit: limite du nombre de résultats, 50 par défaut
        include_summary: indique s'il faut inclure le résumé de l'article, False par défaut

    Returns:
        liste des entrées RSS correspondantes au format JSON

    Examples:
        - search_rss(keyword="AI")
        - search_rss(keyword="machine learning", feeds=['hacker-news'], days=14)
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['data'].search_rss,
        keyword=keyword,
        feeds=feeds,
        days=days,
        limit=limit,
        include_summary=include_summary
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_rss_feeds_status() -> str:
    """
    Récupère les informations d'état des sources RSS

    Consulte les sources RSS actuellement configurées et leurs statistiques de données.

    Returns:
        état des sources RSS au format JSON, contenant :
        - available_dates : liste des dates ayant des données RSS
        - total_dates : nombre total de dates
        - today_feeds : statistiques des données de chaque source RSS aujourd'hui
            - {feed_id}: { name, item_count }
        - generated_at : heure de génération

    Examples:
        - get_rss_feeds_status()  # Consulte l'état de toutes les sources RSS
    """
    tools = _get_tools()
    result = await asyncio.to_thread(tools['data'].get_rss_feeds_status)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_news_by_date(
    date_range: Optional[Union[Dict[str, str], str]] = None,
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    Récupère les données d'actualités d'une date donnée, pour l'analyse et la comparaison de données historiques

    Args:
        date_range: plage de dates, plusieurs formats pris en charge :
            - objet de plage : {"start": "2025-01-01", "end": "2025-01-07"}
            - langage naturel : "aujourd'hui", "hier", "cette semaine", "7 derniers jours"
            - chaîne d'un seul jour : "2025-01-15"
            - valeur par défaut : "aujourd'hui"
        platforms: liste des ID de plateformes, par ex. ['zhihu', 'weibo'], utilise toutes les plateformes si non précisé
        limit: limite du nombre de résultats, 50 par défaut, 1000 maximum
        include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

    Returns:
        liste d'actualités au format JSON, contenant le titre, la plateforme, le classement, etc.
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['data'].get_news_by_date,
        date_range=date_range,
        platforms=platforms,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)



# ==================== Outils d'analyse de données avancée ====================

@mcp.tool
async def analyze_topic_trend(
    topic: str,
    analysis_type: str = "trend",
    date_range: Optional[Union[Dict[str, str], str]] = None,
    granularity: str = "day",
    spike_threshold: float = 3.0,
    time_window: int = 24,
    lookahead_hours: int = 6,
    confidence_threshold: float = 0.7
) -> str:
    """
    Outil unifié d'analyse de tendance des sujets - regroupe plusieurs modes d'analyse de tendance

    Conseil : avec des dates en langage naturel, appelez d'abord resolve_date_range pour obtenir la plage de dates exacte.

    Args:
        topic: mot-clé du sujet (obligatoire)
        analysis_type: type d'analyse
            - "trend": analyse de tendance de popularité (par défaut)
            - "lifecycle": analyse du cycle de vie
            - "viral": détection de popularité anormale
            - "predict": prédiction de sujets
        date_range: plage de dates, format {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}, les 7 derniers jours par défaut
        granularity: granularité temporelle, "day" par défaut
        spike_threshold: seuil de multiplicateur de pic de popularité (mode viral), 3.0 par défaut
        time_window: durée de la fenêtre de détection en heures (mode viral), 24 par défaut
        lookahead_hours: nombre d'heures à prédire (mode predict), 6 par défaut
        confidence_threshold: seuil de confiance (mode predict), 0.7 par défaut

    Returns:
        résultats de l'analyse de tendance au format JSON

    Examples:
        - analyze_topic_trend(topic="AI", date_range={"start": "2025-01-01", "end": "2025-01-07"})
        - analyze_topic_trend(topic="Tesla", analysis_type="lifecycle")
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['analytics'].analyze_topic_trend_unified,
        topic=topic,
        analysis_type=analysis_type,
        date_range=date_range,
        granularity=granularity,
        threshold=spike_threshold,
        time_window=time_window,
        lookahead_hours=lookahead_hours,
        confidence_threshold=confidence_threshold
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def analyze_data_insights(
    insight_type: str = "platform_compare",
    topic: Optional[str] = None,
    date_range: Optional[Union[Dict[str, str], str]] = None,
    min_frequency: int = 3,
    top_n: int = 20
) -> str:
    """
    Outil unifié d'analyse d'insights de données - regroupe plusieurs modes d'analyse de données

    Args:
        insight_type: type d'insight, valeurs possibles :
            - "platform_compare": analyse comparative des plateformes (compare l'attention portée à un sujet selon les plateformes)
            - "platform_activity": statistiques d'activité des plateformes (fréquence de publication et heures d'activité par plateforme)
            - "keyword_cooccur": analyse de cooccurrence des mots-clés (analyse les motifs d'apparition simultanée des mots-clés)
        topic: mot-clé du sujet (facultatif, applicable au mode platform_compare)
        date_range: **[type objet]** plage de dates (facultatif)
                    - **format** : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **exemple** : {"start": "2025-01-01", "end": "2025-01-07"}
                    - **important** : doit être au format objet, ne pas passer un entier
        min_frequency: fréquence de cooccurrence minimale (mode keyword_cooccur), 3 par défaut
        top_n: retourne les TOP N résultats (mode keyword_cooccur), 20 par défaut

    Returns:
        résultats de l'analyse d'insights de données au format JSON

    Examples:
        - analyze_data_insights(insight_type="platform_compare", topic="intelligence artificielle")
        - analyze_data_insights(insight_type="platform_activity", date_range={"start": "2025-01-01", "end": "2025-01-07"})
        - analyze_data_insights(insight_type="keyword_cooccur", min_frequency=5, top_n=15)
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['analytics'].analyze_data_insights_unified,
        insight_type=insight_type,
        topic=topic,
        date_range=date_range,
        min_frequency=min_frequency,
        top_n=top_n
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def analyze_sentiment(
    topic: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    date_range: Optional[Union[Dict[str, str], str]] = None,
    limit: int = 50,
    sort_by_weight: bool = True,
    include_url: bool = False
) -> str:
    """
    Analyse le sentiment et la tendance de popularité des actualités

    Conseil : avec des dates en langage naturel, appelez d'abord resolve_date_range pour obtenir la plage de dates exacte.

    Args:
        topic: mot-clé du sujet (facultatif)
        platforms: liste des ID de plateformes, par ex. ['zhihu', 'weibo'], utilise toutes les plateformes si non précisé
        date_range: plage de dates, format {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}, aujourd'hui par défaut
        limit: nombre d'actualités retournées, 50 par défaut, 100 maximum (les titres sont dédupliqués)
        sort_by_weight: indique s'il faut trier par pondération de popularité, True par défaut
        include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

    Returns:
        résultats de l'analyse au format JSON, contenant la répartition des sentiments, la tendance de popularité et les actualités liées

    Examples:
        - analyze_sentiment(topic="AI", date_range={"start": "2025-01-01", "end": "2025-01-07"})
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['analytics'].analyze_sentiment,
        topic=topic,
        platforms=platforms,
        date_range=date_range,
        limit=limit,
        sort_by_weight=sort_by_weight,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def find_related_news(
    reference_title: str,
    date_range: Optional[Union[Dict[str, str], str]] = None,
    threshold: float = 0.5,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    Trouve d'autres actualités liées à un titre d'actualité donné (prend en charge le jour même et les données historiques)

    Args:
        reference_title: titre d'actualité de référence (complet ou partiel)
        date_range: plage de dates (facultatif)
            - non précisée : interroge uniquement les données d'aujourd'hui
            - "today", "yesterday", "last_week", "last_month" : valeurs prédéfinies
            - {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} : plage personnalisée
        threshold: seuil de similarité, entre 0 et 1, 0.5 par défaut (plus il est élevé, plus la correspondance est stricte)
        limit: limite du nombre de résultats, 50 par défaut
        include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

    Returns:
        liste des actualités liées au format JSON, triée par similarité

    Examples:
        - find_related_news(reference_title="baisse de prix Tesla")
        - find_related_news(reference_title="percée IA", date_range="last_week")
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['search'].find_related_news_unified,
        reference_title=reference_title,
        date_range=date_range,
        threshold=threshold,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def generate_summary_report(
    report_type: str = "daily",
    date_range: Optional[Union[Dict[str, str], str]] = None
) -> str:
    """
    Générateur de résumé quotidien/hebdomadaire - génère automatiquement un rapport de synthèse des sujets populaires

    Args:
        report_type: type de rapport (daily/weekly)
        date_range: **[type objet]** plage de dates personnalisée (facultatif)
                    - **format** : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **exemple** : {"start": "2025-01-01", "end": "2025-01-07"}
                    - **important** : doit être au format objet, ne pas passer un entier

    Returns:
        rapport de synthèse au format JSON, contenant du contenu au format Markdown
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['analytics'].generate_summary_report,
        report_type=report_type,
        date_range=date_range
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def aggregate_news(
    date_range: Optional[Union[Dict[str, str], str]] = None,
    platforms: Optional[List[str]] = None,
    similarity_threshold: float = 0.7,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    Agrégation multi-plateformes des actualités - déduplique et fusionne les actualités similaires

    Fusionne en une seule actualité agrégée un même événement rapporté par différentes plateformes, et affiche la couverture multi-plateformes ainsi que la popularité globale.

    Args:
        date_range: plage de dates, interroge aujourd'hui si non précisée
        platforms: liste des ID de plateformes, par ex. ['zhihu', 'weibo'], utilise toutes les plateformes si non précisé
        similarity_threshold: seuil de similarité, 0.3-1.0, 0.7 par défaut (plus il est élevé, plus c'est strict)
        limit: nombre d'actualités agrégées retournées, 50 par défaut
        include_url: indique s'il faut inclure les liens URL, False par défaut

    Returns:
        résultat d'agrégation au format JSON, contenant les statistiques de déduplication, la liste des actualités agrégées et les statistiques de couverture des plateformes

    Examples:
        - aggregate_news()
        - aggregate_news(similarity_threshold=0.8)
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['analytics'].aggregate_news,
        date_range=date_range,
        platforms=platforms,
        similarity_threshold=similarity_threshold,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def compare_periods(
    period1: Union[Dict[str, str], str],
    period2: Union[Dict[str, str], str],
    topic: Optional[str] = None,
    compare_type: str = "overview",
    platforms: Optional[List[str]] = None,
    top_n: int = 10
) -> str:
    """
    Analyse comparative entre périodes - compare les données d'actualités de deux périodes

    Compare les sujets populaires, l'activité des plateformes, le nombre d'actualités et d'autres dimensions entre différentes périodes.

    **Cas d'usage :**
    - Comparer l'évolution des sujets populaires entre cette semaine et la semaine dernière
    - Analyser la différence de popularité d'un sujet entre deux périodes
    - Consulter les variations cycliques de l'activité des plateformes

    Args:
        period1: première période (période de référence)
            - {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} : plage de dates
            - "today", "yesterday", "this_week", "last_week", "this_month", "last_month" : valeurs prédéfinies
        period2: deuxième période (période de comparaison, même format que period1)
        topic: mot-clé de sujet facultatif (comparaison ciblée sur un sujet précis)
        compare_type: type de comparaison
            - "overview": aperçu global (par défaut) - nombre d'actualités, évolution des mots-clés, TOP actualités
            - "topic_shift": analyse de l'évolution des sujets - sujets en hausse, sujets en baisse, sujets nouvellement apparus
            - "platform_activity": comparaison de l'activité des plateformes - variation du nombre d'actualités par plateforme
        platforms: liste de filtrage des plateformes, par ex. ['zhihu', 'weibo']
        top_n: retourne les TOP N résultats, 10 par défaut

    Returns:
        résultats de l'analyse comparative au format JSON, contenant :
        - periods : les plages de dates des deux périodes
        - compare_type : type de comparaison
        - overview/topic_shift/platform_comparison : résultats de comparaison détaillés (selon le type)

    Examples:
        - compare_periods(period1="last_week", period2="this_week")  # Comparaison hebdomadaire
        - compare_periods(period1="last_month", period2="this_month", compare_type="topic_shift")
        - compare_periods(
            period1={"start": "2025-01-01", "end": "2025-01-07"},
            period2={"start": "2025-01-08", "end": "2025-01-14"},
            topic="intelligence artificielle"
          )
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['analytics'].compare_periods,
        period1=period1,
        period2=period2,
        topic=topic,
        compare_type=compare_type,
        platforms=platforms,
        top_n=top_n
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== Outils de recherche intelligente ====================

@mcp.tool
async def search_news(
    query: str,
    search_mode: str = "keyword",
    date_range: Optional[Union[Dict[str, str], str]] = None,
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    sort_by: str = "relevance",
    threshold: float = 0.6,
    include_url: bool = False,
    include_rss: bool = False,
    rss_limit: int = 20
) -> str:
    """
    Interface de recherche unifiée, prend en charge plusieurs modes de recherche, peut rechercher simultanément dans les palmarès et le RSS

    Conseil : avec des dates en langage naturel, appelez d'abord resolve_date_range pour obtenir la plage de dates exacte.

    Args:
        query: mot-clé de recherche ou extrait de contenu
        search_mode: mode de recherche
            - "keyword": correspondance exacte par mot-clé (par défaut)
            - "fuzzy": correspondance floue du contenu
            - "entity": recherche par nom d'entité (personne/lieu/organisation)
        date_range: plage de dates, format {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}, aujourd'hui par défaut
        platforms: liste des ID de plateformes, par ex. ['zhihu', 'weibo'], utilise toutes les plateformes si non précisé
        limit: limite du nombre de résultats des palmarès, 50 par défaut
        sort_by: méthode de tri - "relevance" (pertinence) / "weight" (pondération) / "date" (date)
        threshold: seuil de similarité (mode fuzzy uniquement), 0-1, 0.6 par défaut
        include_url: indique s'il faut inclure les liens URL, False par défaut
        include_rss: indique s'il faut aussi rechercher dans les données RSS, False par défaut
        rss_limit: limite du nombre de résultats RSS, 20 par défaut

    Returns:
        résultats de recherche au format JSON, contenant la liste des actualités de palmarès et, facultativement, les résultats RSS

    Examples:
        - search_news(query="AI")
        - search_news(query="AI", include_rss=True)
        - search_news(query="Tesla", date_range={"start": "2025-01-01", "end": "2025-01-07"})
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['search'].search_news_unified,
        query=query,
        search_mode=search_mode,
        date_range=date_range,
        platforms=platforms,
        limit=limit,
        sort_by=sort_by,
        threshold=threshold,
        include_url=include_url,
        include_rss=include_rss,
        rss_limit=rss_limit
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== Outils de configuration et de gestion système ====================

@mcp.tool
async def get_current_config(
    section: str = "all"
) -> str:
    """
    Récupère la configuration actuelle du système

    Args:
        section: section de configuration, valeurs possibles :
            - "all": toute la configuration (par défaut)
            - "crawler": configuration du collecteur
            - "push": configuration des notifications
            - "keywords": configuration des mots-clés
            - "weights": configuration des pondérations

    Returns:
        informations de configuration au format JSON
    """
    tools = _get_tools()
    result = await asyncio.to_thread(tools['config'].get_current_config, section=section)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_system_status() -> str:
    """
    Récupère l'état de fonctionnement du système et les informations de vérification de santé

    Retourne la version du système, les statistiques de données, l'état du cache, etc.

    Returns:
        informations sur l'état du système au format JSON
    """
    tools = _get_tools()
    result = await asyncio.to_thread(tools['system'].get_system_status)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def check_version(
    proxy_url: Optional[str] = None
) -> str:
    """
    Vérifie les mises à jour de version (vérifie simultanément TrendRadar et MCP Server)

    Compare la version locale à la version distante sur GitHub pour déterminer si une mise à jour est nécessaire.

    Args:
        proxy_url: URL de proxy facultative, utilisée pour accéder à GitHub (par ex. http://127.0.0.1:7890)

    Returns:
        résultats de la vérification de version au format JSON, contenant la comparaison de version des deux composants et l'indication d'une éventuelle mise à jour

    Examples:
        - check_version()
        - check_version(proxy_url="http://127.0.0.1:7890")
    """
    tools = _get_tools()
    result = await asyncio.to_thread(tools['system'].check_version, proxy_url=proxy_url)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def trigger_crawl(
    platforms: Optional[List[str]] = None,
    save_to_local: bool = False,
    include_url: bool = False
) -> str:
    """
    Déclenche manuellement une tâche de collecte (persistance facultative)

    Args:
        platforms: liste des ID de plateformes, par ex. ['zhihu', 'weibo'], utilise toutes les plateformes si non précisé
        save_to_local: indique s'il faut enregistrer dans le répertoire output local, False par défaut
        include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

    Returns:
        informations sur l'état de la tâche au format JSON, contenant la liste des plateformes réussies/en échec et les données d'actualités

    Examples:
        - trigger_crawl(platforms=['zhihu'])
        - trigger_crawl(save_to_local=True)
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['system'].trigger_crawl,
        platforms=platforms, save_to_local=save_to_local, include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== Outils de synchronisation du stockage ====================

@mcp.tool
async def sync_from_remote(
    days: int = 7
) -> str:
    """
    Récupère les données du stockage distant vers le local

    Pour des scénarios comme le MCP Server : le collecteur enregistre sur un stockage cloud distant (par ex. Cloudflare R2),
    et le MCP Server récupère les données en local pour l'analyse et la requête.

    Args:
        days: récupère les données des N derniers jours, 7 jours par défaut
              - 0 : ne récupère rien
              - 7 : récupère les données de la dernière semaine
              - 30 : récupère les données du dernier mois

    Returns:
        résultat de synchronisation au format JSON, contenant :
        - success : indique si l'opération a réussi
        - synced_files : nombre de fichiers synchronisés avec succès
        - synced_dates : liste des dates synchronisées avec succès
        - skipped_dates : dates ignorées (déjà présentes localement)
        - failed_dates : dates en échec et messages d'erreur
        - message : description du résultat de l'opération

    Examples:
        - sync_from_remote()  # Récupère les 7 derniers jours
        - sync_from_remote(days=30)  # Récupère les 30 derniers jours

    Note:
        Il faut configurer le stockage distant (storage.remote) dans config/config.yaml ou définir les variables d'environnement :
        - S3_ENDPOINT_URL : point de terminaison du service
        - S3_BUCKET_NAME : nom du bucket de stockage
        - S3_ACCESS_KEY_ID : ID de la clé d'accès
        - S3_SECRET_ACCESS_KEY : clé d'accès secrète
    """
    tools = _get_tools()
    result = await asyncio.to_thread(tools['storage'].sync_from_remote, days=days)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_storage_status() -> str:
    """
    Récupère la configuration et l'état du stockage

    Consulte la configuration du backend de stockage actuel ainsi que l'état du stockage local et distant.

    Returns:
        informations sur l'état du stockage au format JSON, contenant l'état du stockage local/distant et la configuration de récupération
    """
    tools = _get_tools()
    result = await asyncio.to_thread(tools['storage'].get_storage_status)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def list_available_dates(
    source: str = "both"
) -> str:
    """
    Liste les plages de dates disponibles en local/à distance

    Consulte quelles dates de données sont disponibles dans le stockage local et distant.

    Args:
        source: source des données
            - "local": local uniquement
            - "remote": distant uniquement
            - "both": liste les deux et compare (par défaut)

    Returns:
        liste des dates au format JSON, contenant les informations de dates de chaque source et les résultats de comparaison

    Examples:
        - list_available_dates()
        - list_available_dates(source="local")
    """
    tools = _get_tools()
    result = await asyncio.to_thread(tools['storage'].list_available_dates, source=source)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== Outils de lecture du contenu des articles ====================

@mcp.tool
async def read_article(
    url: str,
    timeout: int = 30
) -> str:
    """
    Lit le contenu de l'article d'une URL donnée, retourne un format Markdown adapté aux LLM

    Convertit la page web en Markdown propre via Jina AI Reader, en retirant automatiquement les publicités, barres de navigation et autre bruit.
    Adapté pour : lire le corps d'une actualité, obtenir les détails d'un article, analyser le contenu d'un article.

    **Flux d'utilisation typique :**
    1. Utiliser d'abord search_news(include_url=True) pour rechercher des actualités et obtenir des liens
    2. Puis utiliser read_article(url=lien) pour lire le corps du texte
    3. L'IA analyse, résume, traduit, etc. le corps Markdown

    Args:
        url: lien de l'article (obligatoire), commençant par http:// ou https://
        timeout: délai d'expiration de la requête (secondes), 30 par défaut, 60 maximum

    Returns:
        contenu de l'article au format JSON, contenant le corps Markdown complet

    Examples:
        - read_article(url="https://example.com/news/123")

    Note:
        - Utilise le service gratuit Jina AI Reader (limite de 100 RPM)
        - Intervalle de 5 secondes entre chaque requête (contrôle de débit intégré)
        - Certaines pages avec péage/connexion obligatoire peuvent ne pas être récupérées intégralement
    """
    tools = _get_tools()
    timeout = min(max(timeout, 10), 60)
    result = await asyncio.to_thread(
        tools['article'].read_article,
        url=url, timeout=timeout
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def read_articles_batch(
    urls: List[str],
    timeout: int = 30
) -> str:
    """
    Lit le contenu de plusieurs articles par lot (5 maximum, intervalle de 5 secondes)

    Requête le contenu des articles un par un, avec un intervalle automatique de 5 secondes entre chacun pour respecter la limite de débit.

    **Flux d'utilisation typique :**
    1. Utiliser d'abord search_news(include_url=True) pour rechercher des actualités et obtenir plusieurs liens
    2. Puis utiliser read_articles_batch(urls=[...]) pour lire les corps de texte par lot
    3. L'IA effectue une analyse comparative et un rapport de synthèse sur plusieurs articles

    Args:
        urls: liste des liens d'articles (obligatoire), 5 articles traités au maximum
        timeout: délai d'expiration de la requête pour chaque article (secondes), 30 par défaut

    Returns:
        résultat de la lecture par lot au format JSON, contenant le contenu complet et l'état de chaque article

    Examples:
        - read_articles_batch(urls=["https://a.com/1", "https://b.com/2"])

    Note:
        - 5 articles maximum par appel, le surplus est ignoré
        - 5 articles prennent environ 25-30 secondes (intervalle de 5 secondes par article)
        - L'échec d'un article n'affecte pas la lecture des autres
    """
    tools = _get_tools()
    timeout = min(max(timeout, 10), 60)
    result = await asyncio.to_thread(
        tools['article'].read_articles_batch,
        urls=urls, timeout=timeout
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== Outils de notification (push) ====================


@mcp.tool
async def get_channel_format_guide(channel: Optional[str] = None) -> str:
    """
    Récupère le guide des stratégies de formatage des canaux de notification

    Retourne pour chaque canal les fonctionnalités Markdown prises en charge, les limites de format et les meilleures
    consignes de formatage. Utilisez cet outil avant d'appeler send_notification pour connaître les exigences de format
    du canal cible et ainsi générer un contenu de message à la mise en forme optimale.

    Aperçu des différences de format par canal :
    - Feishu : prend en charge **gras**, <font color>texte coloré, [lien](url), --- ligne de séparation
    - DingTalk : prend en charge ### titres, **gras**, > citation, --- ligne de séparation, mais pas la couleur
    - WeCom : prend en charge uniquement **gras**, [lien](url), > citation, mais pas les titres ni les lignes de séparation
    - Telegram : converti automatiquement en HTML, prend en charge gras/italique/barré/code/lien/bloc de citation
    - ntfy : prend en charge le Markdown standard, mais pas la couleur
    - Bark : notification push iOS, prend en charge uniquement le gras et les liens, contenu à garder concis
    - Slack : converti automatiquement en mrkdwn, *gras*, ~barré~, <url|lien>
    - E-mail : converti automatiquement en page HTML complète, prend en charge titres/styles/lignes de séparation
    - Webhook générique : Markdown standard ou modèle personnalisé

    Args:
        channel: ID de canal indiqué (facultatif), si non précisé retourne les stratégies de tous les canaux
                 valeurs possibles : feishu, dingtalk, wework, telegram, email, ntfy, bark, slack, generic_webhook

    Returns:
        stratégies de formatage des canaux au format JSON, contenant les fonctionnalités prises en charge, les limites et les consignes de formatage

    Examples:
        - get_channel_format_guide()  # Récupère les stratégies de tous les canaux
        - get_channel_format_guide(channel="feishu")  # Récupère la stratégie Feishu
        - get_channel_format_guide(channel="telegram")  # Récupère la stratégie Telegram
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['notification'].get_channel_format_guide,
        channel=channel
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_notification_channels() -> str:
    """
    Récupère tous les canaux de notification configurés et leur état

    Détecte la configuration des canaux de notification dans config.yaml et les variables d'environnement .env.
    Prend en charge 9 canaux : Feishu, DingTalk, WeCom, Telegram, e-mail, ntfy, Bark, Slack, Webhook générique.

    Returns:
        état des canaux au format JSON, contenant pour chaque canal s'il est configuré et la source de configuration

    Examples:
        - get_notification_channels()
    """
    tools = _get_tools()
    result = await asyncio.to_thread(tools['notification'].get_notification_channels)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def send_notification(
    message: str,
    title: str = "Notification TrendRadar",
    channels: Optional[List[str]] = None,
) -> str:
    """
    Envoie un message vers les canaux de notification configurés

    Accepte du contenu au format markdown, adapté automatiquement en interne aux exigences et limites de format de chaque canal :
    - Feishu : message carte Markdown (prend en charge **gras**, <font color>texte coloré, [lien](url), ---)
    - DingTalk : Markdown (rétrograde automatiquement les titres en ###, retire les balises <font> et le barré)
    - WeCom : Markdown (retire automatiquement les titres #, ---, les balises <font>, le barré)
    - Telegram : HTML (convertit automatiquement **→<b>, *→<i>, ~~→<s>, >→<blockquote>)
    - E-mail : e-mail HTML (style page web complète, prend en charge les titres #, ---, gras et italique)
    - ntfy : Markdown (retire automatiquement les balises <font>)
    - Bark : Markdown (simplifié automatiquement en gras + liens, adapté à la notification push iOS)
    - Slack : mrkdwn (convertit automatiquement **→*, ~~→~, [text](url)→<url|text>)
    - Webhook générique : Markdown (prend en charge un modèle personnalisé)

    Conseil : avant l'envoi, vous pouvez appeler get_channel_format_guide pour obtenir la stratégie de formatage détaillée
    du canal cible, afin de générer un contenu de message à la mise en forme optimale.

    Args:
        message: contenu du message au format markdown (obligatoire)
        title: titre du message, "Notification TrendRadar" par défaut
        channels: liste des canaux d'envoi indiqués, si non précisée envoie vers tous les canaux configurés
                  valeurs possibles : feishu, dingtalk, wework, telegram, email, ntfy, bark, slack, generic_webhook

    Returns:
        résultat d'envoi au format JSON, contenant l'état d'envoi de chaque canal

    Examples:
        - send_notification(message="**Message de test**\\nCeci est une notification de test")
        - send_notification(message="Notification urgente", title="Alerte système", channels=["feishu", "dingtalk"])
    """
    tools = _get_tools()
    result = await asyncio.to_thread(
        tools['notification'].send_notification,
        message=message, title=title, channels=channels
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== Point d'entrée de démarrage ====================

def run_server(
    project_root: Optional[str] = None,
    transport: str = 'stdio',
    host: str = '0.0.0.0',
    port: int = 3333
):
    """
    Démarre le serveur MCP

    Args:
        project_root: chemin du répertoire racine du projet
        transport: mode de transport, 'stdio' ou 'http'
        host: adresse d'écoute en mode HTTP, 0.0.0.0 par défaut
        port: port d'écoute en mode HTTP, 3333 par défaut
    """
    # Initialise les instances d'outils
    _get_tools(project_root)

    # Affiche les informations de démarrage
    print()
    print("=" * 60)
    print("  TrendRadar MCP Server - FastMCP 2.0")
    print("=" * 60)
    print(f"  Mode de transport : {transport.upper()}")

    if transport == 'stdio':
        print("  Protocole : MCP over stdio (entrée/sortie standard)")
        print("  Description : communique avec le client MCP via l'entrée/sortie standard")
    elif transport == 'http':
        print(f"  Protocole : MCP over HTTP (environnement de production)")
        print(f"  Écoute du serveur : {host}:{port}")

    if project_root:
        print(f"  Répertoire du projet : {project_root}")
    else:
        print("  Répertoire du projet : répertoire courant")

    print()
    print("  Outils enregistrés :")
    print("    === Outil d'analyse de dates (à appeler en priorité) ===")
    print("    0. resolve_date_range       - Analyse une date en langage naturel au format standard")
    print()
    print("    === Requête de données de base (cœur P0) ===")
    print("    1. get_latest_news        - Récupère les dernières actualités")
    print("    2. get_news_by_date       - Interroge les actualités par date (langage naturel pris en charge)")
    print("    3. get_trending_topics    - Récupère les sujets tendances (extraction automatique prise en charge)")
    print()
    print("    === Requête de données RSS ===")
    print("    4. get_latest_rss         - Récupère les dernières données d'abonnements RSS")
    print("    5. search_rss             - Recherche dans les données RSS")
    print("    6. get_rss_feeds_status   - Récupère l'état des sources RSS")
    print()
    print("    === Outils de recherche intelligente ===")
    print("    7. search_news            - Recherche unifiée d'actualités (mot-clé/floue/entité)")
    print("    8. find_related_news      - Recherche d'actualités connexes (données historiques prises en charge)")
    print()
    print("    === Analyse de données avancée ===")
    print("    9. analyze_topic_trend      - Analyse unifiée de tendance des sujets (popularité/cycle de vie/viralité/prédiction)")
    print("    10. analyze_data_insights   - Analyse unifiée d'insights de données (comparaison de plateformes/activité/cooccurrence de mots-clés)")
    print("    11. analyze_sentiment       - Analyse de sentiment")
    print("    12. aggregate_news          - Agrégation et déduplication multi-plateformes des actualités")
    print("    13. compare_periods         - Analyse comparative entre périodes (hebdomadaire/mensuelle)")
    print("    14. generate_summary_report - Génération de résumé quotidien/hebdomadaire")
    print()
    print("    === Configuration et gestion système ===")
    print("    15. get_current_config      - Récupère la configuration actuelle du système")
    print("    16. get_system_status       - Récupère l'état de fonctionnement du système")
    print("    17. check_version           - Vérifie les mises à jour (compare version locale et distante)")
    print("    18. trigger_crawl           - Déclenche manuellement une tâche de collecte")
    print()
    print("    === Outils de synchronisation du stockage ===")
    print("    19. sync_from_remote        - Récupère les données du stockage distant vers le local")
    print("    20. get_storage_status      - Récupère la configuration et l'état du stockage")
    print("    21. list_available_dates    - Liste les dates disponibles en local/à distance")
    print()
    print("    === Lecture du contenu des articles ===")
    print("    22. read_article            - Lit le contenu d'un seul article (format Markdown)")
    print("    23. read_articles_batch     - Lit plusieurs articles par lot (limitation de débit automatique)")
    print()
    print("    === Outils de notification (push) ===")
    print("    24. get_channel_format_guide  - Récupère le guide des stratégies de formatage des canaux (consignes)")
    print("    25. get_notification_channels - Récupère l'état des canaux de notification configurés")
    print("    26. send_notification         - Envoie un message vers les canaux de notification (adaptation automatique du format)")
    print("=" * 60)
    print()

    # Lance le serveur selon le mode de transport
    if transport == 'stdio':
        mcp.run(transport='stdio')
    elif transport == 'http':
        # Mode HTTP (recommandé en production)
        mcp.run(
            transport='http',
            host=host,
            port=port,
            path='/mcp'  # Chemin du point de terminaison HTTP
        )
    else:
        raise ValueError(f"Mode de transport non pris en charge : {transport}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='TrendRadar MCP Server - serveur d\'outils MCP d\'agrégation de sujets d\'actualité',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pour un tutoriel de configuration détaillé, consultez : README-Cherry-Studio.md
        """
    )
    parser.add_argument(
        '--transport',
        choices=['stdio', 'http'],
        default='stdio',
        help='mode de transport : stdio (par défaut) ou http (environnement de production)'
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='adresse d\'écoute en mode HTTP, 0.0.0.0 par défaut'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=3333,
        help='port d\'écoute en mode HTTP, 3333 par défaut'
    )
    parser.add_argument(
        '--project-root',
        help='chemin du répertoire racine du projet'
    )

    args = parser.parse_args()

    run_server(
        project_root=args.project_root,
        transport=args.transport,
        host=args.host,
        port=args.port
    )
