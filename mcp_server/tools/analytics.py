"""
Outils d'analyse de données avancée

Fournit des fonctions d'analyse avancées : analyse de tendance de popularité, comparaison de plateformes, cooccurrence de mots-clés, analyse de sentiment, etc.
"""

import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from difflib import SequenceMatcher

import yaml

from trendradar.core.analyzer import calculate_news_weight as _calculate_news_weight

from ..services.data_service import DataService
from ..utils.validators import (
    validate_platforms,
    validate_limit,
    validate_keyword,
    validate_top_n,
    validate_date_range,
    validate_threshold
)
from ..utils.errors import MCPError, InvalidParameterError, DataNotFoundError


# Cache du mtime de la configuration des pondérations (évite de relire le même fichier de configuration)
_weight_config_cache: Optional[Dict] = None
_weight_config_mtime: float = 0.0
_weight_config_path: Optional[str] = None

_WEIGHT_DEFAULT_CONFIG = {
    "RANK_WEIGHT": 0.6,
    "FREQUENCY_WEIGHT": 0.3,
    "HOTNESS_WEIGHT": 0.1,
}


def _get_weight_config() -> Dict:
    """
    Lit la configuration des pondérations depuis config.yaml (avec cache mtime)

    Ne relit que lorsque le fichier de configuration a été modifié, pour éviter les E/S répétées dans les boucles.

    Returns:
        dictionnaire de configuration des pondérations, contenant RANK_WEIGHT, FREQUENCY_WEIGHT, HOTNESS_WEIGHT
    """
    global _weight_config_cache, _weight_config_mtime, _weight_config_path

    try:
        # Calcule le chemin au premier appel (réutilisé ensuite)
        if _weight_config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            _weight_config_path = os.path.normpath(
                os.path.join(current_dir, "..", "..", "config", "config.yaml")
            )

        current_mtime = os.path.getmtime(_weight_config_path)

        # Fichier non modifié et cache valide, retour direct
        if _weight_config_cache is not None and current_mtime == _weight_config_mtime:
            return _weight_config_cache

        # Fichier modifié ou première lecture, ré-analyse
        with open(_weight_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            weight = config.get('advanced', {}).get('weight', {})
            _weight_config_cache = {
                "RANK_WEIGHT": weight.get('rank', 0.6),
                "FREQUENCY_WEIGHT": weight.get('frequency', 0.3),
                "HOTNESS_WEIGHT": weight.get('hotness', 0.1),
            }
            _weight_config_mtime = current_mtime
            return _weight_config_cache
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        return _WEIGHT_DEFAULT_CONFIG


def calculate_news_weight(news_data: Dict, rank_threshold: int = 5) -> float:
    """
    Calcule la pondération d'une actualité (utilisée pour le tri)

    Réutilise l'implémentation de trendradar.core.analyzer.calculate_news_weight,
    la configuration des pondérations est lue depuis advanced.weight de config.yaml.

    Args:
        news_data: dictionnaire de données d'actualité, contenant les champs ranks et count
        rank_threshold: seuil de classement élevé, 5 par défaut

    Returns:
        score de pondération (nombre flottant entre 0 et 100)
    """
    return _calculate_news_weight(news_data, rank_threshold, _get_weight_config())


class AnalyticsTools:
    """Classe des outils d'analyse de données avancée"""

    def __init__(self, project_root: str = None):
        """
        Initialise les outils d'analyse

        Args:
            project_root: répertoire racine du projet
        """
        self.data_service = DataService(project_root)

    def analyze_data_insights_unified(
        self,
        insight_type: str = "platform_compare",
        topic: Optional[str] = None,
        date_range: Optional[Union[Dict[str, str], str]] = None,
        min_frequency: int = 3,
        top_n: int = 20
    ) -> Dict:
        """
        Outil unifié d'analyse d'insights de données - regroupe plusieurs modes d'analyse de données

        Args:
            insight_type: type d'insight, valeurs possibles :
                - "platform_compare": analyse comparative des plateformes (compare l'attention portée à un sujet selon les plateformes)
                - "platform_activity": statistiques d'activité des plateformes (fréquence de publication et heures d'activité par plateforme)
                - "keyword_cooccur": analyse de cooccurrence des mots-clés (analyse les motifs d'apparition simultanée des mots-clés)
            topic: mot-clé du sujet (facultatif, applicable au mode platform_compare)
            date_range: plage de dates, format : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            min_frequency: fréquence de cooccurrence minimale (mode keyword_cooccur), 3 par défaut
            top_n: retourne les TOP N résultats (mode keyword_cooccur), 20 par défaut

        Returns:
            dictionnaire des résultats d'analyse d'insights de données

        Examples:
            - analyze_data_insights_unified(insight_type="platform_compare", topic="intelligence artificielle")
            - analyze_data_insights_unified(insight_type="platform_activity", date_range={...})
            - analyze_data_insights_unified(insight_type="keyword_cooccur", min_frequency=5)
        """
        try:
            # Validation des paramètres
            if insight_type not in ["platform_compare", "platform_activity", "keyword_cooccur"]:
                raise InvalidParameterError(
                    f"Type d'insight invalide : {insight_type}",
                    suggestion="Types pris en charge : platform_compare, platform_activity, keyword_cooccur"
                )

            # Appelle la méthode correspondante selon le type d'insight
            if insight_type == "platform_compare":
                return self.compare_platforms(
                    topic=topic,
                    date_range=date_range
                )
            elif insight_type == "platform_activity":
                return self.get_platform_activity_stats(
                    date_range=date_range
                )
            else:  # keyword_cooccur
                return self.analyze_keyword_cooccurrence(
                    min_frequency=min_frequency,
                    top_n=top_n
                )

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def analyze_topic_trend_unified(
        self,
        topic: str,
        analysis_type: str = "trend",
        date_range: Optional[Union[Dict[str, str], str]] = None,
        granularity: str = "day",
        threshold: float = 3.0,
        time_window: int = 24,
        lookahead_hours: int = 6,
        confidence_threshold: float = 0.7
    ) -> Dict:
        """
        Outil unifié d'analyse de tendance des sujets - regroupe plusieurs modes d'analyse de tendance

        Args:
            topic: mot-clé du sujet (obligatoire)
            analysis_type: type d'analyse, valeurs possibles :
                - "trend": analyse de tendance de popularité (suit l'évolution de la popularité d'un sujet)
                - "lifecycle": analyse du cycle de vie (cycle complet de l'apparition à la disparition)
                - "viral": détection de popularité anormale (identifie les sujets devenus soudainement viraux)
                - "predict": prédiction de sujets (prédit les sujets potentiellement populaires à venir)
            date_range: plage de dates (modes trend et lifecycle), facultatif
                       - **format** : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                       - **par défaut** : si non précisée, analyse les 7 derniers jours
            granularity: granularité temporelle (mode trend), "day" par défaut (hour/day)
            threshold: seuil de multiplicateur de pic de popularité (mode viral), 3.0 par défaut
            time_window: durée de la fenêtre de détection en heures (mode viral), 24 par défaut
            lookahead_hours: nombre d'heures à prédire (mode predict), 6 par défaut
            confidence_threshold: seuil de confiance (mode predict), 0.7 par défaut

        Returns:
            dictionnaire des résultats d'analyse de tendance

        Examples (en supposant qu'aujourd'hui est le 2025-11-17) :
            - Utilisateur : "analyse la tendance de l'IA sur les 7 derniers jours" → analyze_topic_trend_unified(topic="intelligence artificielle", analysis_type="trend", date_range={"start": "2025-11-11", "end": "2025-11-17"})
            - Utilisateur : "regarde la popularité de Tesla ce mois-ci" → analyze_topic_trend_unified(topic="Tesla", analysis_type="lifecycle", date_range={"start": "2025-11-01", "end": "2025-11-17"})
            - analyze_topic_trend_unified(topic="Bitcoin", analysis_type="viral", threshold=3.0)
            - analyze_topic_trend_unified(topic="ChatGPT", analysis_type="predict", lookahead_hours=6)
        """
        try:
            # Validation des paramètres
            topic = validate_keyword(topic)

            if analysis_type not in ["trend", "lifecycle", "viral", "predict"]:
                raise InvalidParameterError(
                    f"Type d'analyse invalide : {analysis_type}",
                    suggestion="Types pris en charge : trend, lifecycle, viral, predict"
                )

            # Appelle la méthode correspondante selon le type d'analyse
            if analysis_type == "trend":
                return self.get_topic_trend_analysis(
                    topic=topic,
                    date_range=date_range,
                    granularity=granularity
                )
            elif analysis_type == "lifecycle":
                return self.analyze_topic_lifecycle(
                    topic=topic,
                    date_range=date_range
                )
            elif analysis_type == "viral":
                # Le mode viral ne nécessite pas le paramètre topic, utilise une détection générique
                return self.detect_viral_topics(
                    threshold=threshold,
                    time_window=time_window
                )
            else:  # predict
                # Le mode predict ne nécessite pas le paramètre topic, utilise une prédiction générique
                return self.predict_trending_topics(
                    lookahead_hours=lookahead_hours,
                    confidence_threshold=confidence_threshold
                )

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def get_topic_trend_analysis(
        self,
        topic: str,
        date_range: Optional[Union[Dict[str, str], str]] = None,
        granularity: str = "day"
    ) -> Dict:
        """
        Analyse de tendance de popularité - suit l'évolution de la popularité d'un sujet donné

        Args:
            topic: mot-clé du sujet
            date_range: plage de dates (facultatif)
                       - **format** : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                       - **par défaut** : si non précisée, analyse les 7 derniers jours
            granularity: granularité temporelle, prend uniquement en charge day (jour)

        Returns:
            dictionnaire des résultats d'analyse de tendance

        Examples:
            Exemples de questions d'utilisateur :
            - "analyse pour moi la tendance de popularité du sujet 'intelligence artificielle' sur la dernière semaine"
            - "regarde l'évolution de popularité de 'Bitcoin' sur la dernière semaine"
            - "vois comment est la tendance de 'iPhone' sur les 7 derniers jours"
            - "analyse la tendance de popularité de 'Tesla' sur le dernier mois"
            - "regarde l'évolution de tendance de 'ChatGPT' en décembre 2024"

            Exemples d'appel de code :
            >>> tools = AnalyticsTools()
            >>> # Analyse de tendance sur 7 jours (en supposant qu'aujourd'hui est le 2025-11-17)
            >>> result = tools.get_topic_trend_analysis(
            ...     topic="intelligence artificielle",
            ...     date_range={"start": "2025-11-11", "end": "2025-11-17"},
            ...     granularity="day"
            ... )
            >>> # Analyse de tendance d'un mois historique
            >>> result = tools.get_topic_trend_analysis(
            ...     topic="Tesla",
            ...     date_range={"start": "2024-12-01", "end": "2024-12-31"},
            ...     granularity="day"
            ... )
            >>> print(result['trend_data'])
        """
        try:
            # Validation des paramètres
            topic = validate_keyword(topic)

            # Valide le paramètre de granularité (seul day est pris en charge)
            if granularity != "day":
                from ..utils.errors import InvalidParameterError
                raise InvalidParameterError(
                    f"Paramètre de granularité non pris en charge : {granularity}",
                    suggestion="Seule la granularité 'day' est prise en charge actuellement, car les données sous-jacentes sont agrégées par jour"
                )

            # Traite la plage de dates (les 7 derniers jours par défaut si non précisée)
            if date_range:
                from ..utils.validators import validate_date_range
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                # Les 7 derniers jours par défaut
                end_date = datetime.now()
                start_date = end_date - timedelta(days=6)

            # Collecte les données de tendance
            trend_data = []
            current_date = start_date

            while current_date <= end_date:
                try:
                    all_titles, _, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    # Comptabilise le nombre d'occurrences du sujet à cet instant
                    count = 0
                    matched_titles = []

                    for _, titles in all_titles.items():
                        for title in titles.keys():
                            if topic.lower() in title.lower():
                                count += 1
                                matched_titles.append(title)

                    trend_data.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "count": count,
                        "sample_titles": matched_titles[:3]  # Ne conserve que les 3 premiers échantillons
                    })

                except DataNotFoundError:
                    trend_data.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "count": 0,
                        "sample_titles": []
                    })

                # Avance d'un jour
                current_date += timedelta(days=1)

            # Calcule les indicateurs de tendance
            counts = [item["count"] for item in trend_data]
            total_days = (end_date - start_date).days + 1

            if len(counts) >= 2:
                # Calcule l'amplitude de variation
                first_non_zero = next((c for c in counts if c > 0), 0)
                last_count = counts[-1]

                if first_non_zero > 0:
                    change_rate = ((last_count - first_non_zero) / first_non_zero) * 100
                else:
                    change_rate = 0

                # Trouve l'instant du pic
                max_count = max(counts)
                peak_index = counts.index(max_count)
                peak_time = trend_data[peak_index]["date"]
            else:
                change_rate = 0
                peak_time = None
                max_count = 0

            return {
                "success": True,
                "summary": {
                    "description": f"Analyse de tendance de popularité du sujet « {topic} »",
                    "topic": topic,
                    "date_range": {
                        "start": start_date.strftime("%Y-%m-%d"),
                        "end": end_date.strftime("%Y-%m-%d"),
                        "total_days": total_days
                    },
                    "granularity": granularity,
                    "total_mentions": sum(counts),
                    "average_mentions": round(sum(counts) / len(counts), 2) if counts else 0,
                    "peak_count": max_count,
                    "peak_time": peak_time,
                    "change_rate": round(change_rate, 2),
                    "trend_direction": "hausse" if change_rate > 10 else "baisse" if change_rate < -10 else "stable"
                },
                "data": trend_data
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def compare_platforms(
        self,
        topic: Optional[str] = None,
        date_range: Optional[Union[Dict[str, str], str]] = None
    ) -> Dict:
        """
        Analyse comparative des plateformes - compare l'attention portée à un même sujet selon les plateformes

        Args:
            topic: mot-clé du sujet (facultatif, si non précisé compare l'activité globale)
            date_range: plage de dates, format : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}

        Returns:
            résultats de l'analyse comparative des plateformes

        Examples:
            Exemples de questions d'utilisateur :
            - "compare l'attention portée par chaque plateforme au sujet 'intelligence artificielle'"
            - "regarde quelle plateforme entre Zhihu et Weibo s'intéresse le plus aux actualités tech"
            - "analyse la répartition des sujets populaires d'aujourd'hui par plateforme"

            Exemples d'appel de code :
            >>> # Compare les plateformes (en supposant qu'aujourd'hui est le 2025-11-17)
            >>> result = tools.compare_platforms(
            ...     topic="intelligence artificielle",
            ...     date_range={"start": "2025-11-08", "end": "2025-11-17"}
            ... )
            >>> print(result['platform_stats'])
        """
        try:
            # Validation des paramètres
            if topic:
                topic = validate_keyword(topic)
            date_range_tuple = validate_date_range(date_range)

            # Détermine la plage de dates
            if date_range_tuple:
                start_date, end_date = date_range_tuple
            else:
                start_date = end_date = datetime.now()

            # Collecte les données de chaque plateforme
            platform_stats = defaultdict(lambda: {
                "total_news": 0,
                "topic_mentions": 0,
                "unique_titles": set(),
                "top_keywords": Counter()
            })

            # Parcourt la plage de dates
            current_date = start_date
            while current_date <= end_date:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)

                        for title in titles.keys():
                            platform_stats[platform_name]["total_news"] += 1
                            platform_stats[platform_name]["unique_titles"].add(title)

                            # Si un sujet est précisé, comptabilise les actualités le contenant
                            if topic and topic.lower() in title.lower():
                                platform_stats[platform_name]["topic_mentions"] += 1

                            # Extrait les mots-clés (découpage simple)
                            keywords = self._extract_keywords(title)
                            platform_stats[platform_name]["top_keywords"].update(keywords)

                except DataNotFoundError:
                    pass

                current_date += timedelta(days=1)

            # Convertit en format sérialisable
            result_stats = {}
            for platform, stats in platform_stats.items():
                coverage_rate = 0
                if stats["total_news"] > 0:
                    coverage_rate = (stats["topic_mentions"] / stats["total_news"]) * 100

                result_stats[platform] = {
                    "total_news": stats["total_news"],
                    "topic_mentions": stats["topic_mentions"],
                    "unique_titles": len(stats["unique_titles"]),
                    "coverage_rate": round(coverage_rate, 2),
                    "top_keywords": [
                        {"keyword": k, "count": v}
                        for k, v in stats["top_keywords"].most_common(5)
                    ]
                }

            # Identifie les sujets propres à chaque plateforme
            unique_topics = self._find_unique_topics(platform_stats)

            return {
                "success": True,
                "topic": topic,
                "date_range": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                },
                "platform_stats": result_stats,
                "unique_topics": unique_topics,
                "total_platforms": len(result_stats)
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def analyze_keyword_cooccurrence(
        self,
        min_frequency: int = 3,
        top_n: int = 20
    ) -> Dict:
        """
        Analyse de cooccurrence des mots-clés - analyse quels mots-clés apparaissent souvent ensemble

        Args:
            min_frequency: fréquence de cooccurrence minimale
            top_n: retourne les TOP N paires de mots-clés

        Returns:
            résultats de l'analyse de cooccurrence des mots-clés

        Examples:
            Exemples de questions d'utilisateur :
            - "analyse quels mots-clés apparaissent souvent ensemble"
            - "regarde avec quels mots 'intelligence artificielle' apparaît souvent"
            - "trouve les associations de mots-clés dans les actualités d'aujourd'hui"

            Exemples d'appel de code :
            >>> tools = AnalyticsTools()
            >>> result = tools.analyze_keyword_cooccurrence(
            ...     min_frequency=5,
            ...     top_n=15
            ... )
            >>> print(result['cooccurrence_pairs'])
        """
        try:
            # Validation des paramètres
            min_frequency = validate_limit(min_frequency, default=3, max_limit=100)
            top_n = validate_top_n(top_n, default=20)

            # Lit les données d'aujourd'hui
            all_titles, _, _ = self.data_service.parser.read_all_titles_for_date()

            # Statistiques de cooccurrence des mots-clés
            cooccurrence = Counter()
            keyword_titles = defaultdict(list)

            for platform_id, titles in all_titles.items():
                for title in titles.keys():
                    # Extrait les mots-clés
                    keywords = self._extract_keywords(title)

                    # Enregistre les titres où chaque mot-clé apparaît
                    for kw in keywords:
                        keyword_titles[kw].append(title)

                    # Calcule les cooccurrences deux à deux
                    if len(keywords) >= 2:
                        for i, kw1 in enumerate(keywords):
                            for kw2 in keywords[i+1:]:
                                # Tri uniforme pour éviter les doublons
                                pair = tuple(sorted([kw1, kw2]))
                                cooccurrence[pair] += 1

            # Filtre les cooccurrences à faible fréquence
            filtered_pairs = [
                (pair, count) for pair, count in cooccurrence.items()
                if count >= min_frequency
            ]

            # Trie et prend les TOP N
            top_pairs = sorted(filtered_pairs, key=lambda x: x[1], reverse=True)[:top_n]

            # Construit le résultat
            result_pairs = []
            for (kw1, kw2), count in top_pairs:
                # Trouve des échantillons de titres contenant les deux mots-clés à la fois
                titles_with_both = [
                    title for title in keyword_titles[kw1]
                    if kw2 in self._extract_keywords(title)
                ]

                result_pairs.append({
                    "keyword1": kw1,
                    "keyword2": kw2,
                    "cooccurrence_count": count,
                    "sample_titles": titles_with_both[:3]
                })

            return {
                "success": True,
                "summary": {
                    "description": "Résultats de l'analyse de cooccurrence des mots-clés",
                    "total": len(result_pairs),
                    "min_frequency": min_frequency,
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "data": result_pairs
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def analyze_sentiment(
        self,
        topic: Optional[str] = None,
        platforms: Optional[List[str]] = None,
        date_range: Optional[Union[Dict[str, str], str]] = None,
        limit: int = 50,
        sort_by_weight: bool = True,
        include_url: bool = False
    ) -> Dict:
        """
        Analyse de sentiment - génère un prompt structuré pour une analyse de sentiment par IA

        Cet outil collecte des données d'actualités et génère un prompt IA optimisé, que vous pouvez envoyer à une IA pour une analyse de sentiment approfondie.

        Args:
            topic: mot-clé du sujet (facultatif), n'analyse que les actualités contenant ce mot-clé
            platforms: liste de filtrage des plateformes (facultatif), par ex. ['zhihu', 'weibo']
            date_range: plage de dates (facultatif), format : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                       si non précisée, interroge les données d'aujourd'hui par défaut
            limit: limite du nombre d'actualités retournées, 50 par défaut, 100 maximum
            sort_by_weight: indique s'il faut trier par pondération, True par défaut (recommandé)
            include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

        Returns:
            résultat structuré contenant le prompt IA et les données d'actualités

        Examples:
            Exemples de questions d'utilisateur :
            - "analyse le sentiment des actualités d'aujourd'hui"
            - "regarde si les actualités liées à 'Tesla' sont positives ou négatives"
            - "analyse l'attitude de chaque plateforme envers 'intelligence artificielle'"
            - "regarde si les actualités liées à 'Tesla' sont positives ou négatives, choisis les 10 premières actualités de la semaine pour l'analyse"

            Exemples d'appel de code :
            >>> tools = AnalyticsTools()
            >>> # Analyse les actualités Tesla d'aujourd'hui, retourne les 10 premières
            >>> result = tools.analyze_sentiment(
            ...     topic="Tesla",
            ...     limit=10
            ... )
            >>> # Analyse les actualités Tesla de la semaine (en supposant qu'aujourd'hui est le 2025-11-17)
            >>> result = tools.analyze_sentiment(
            ...     topic="Tesla",
            ...     date_range={"start": "2025-11-11", "end": "2025-11-17"},
            ...     limit=10
            ... )
            >>> print(result['ai_prompt'])  # Récupère le prompt généré
        """
        try:
            # Validation des paramètres
            if topic:
                topic = validate_keyword(topic)
            platforms = validate_platforms(platforms)
            limit = validate_limit(limit, default=50)

            # Traite la plage de dates
            if date_range:
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                # Aujourd'hui par défaut
                start_date = end_date = datetime.now()

            # Collecte les données d'actualités (prend en charge plusieurs jours)
            all_news_items = []
            current_date = start_date

            while current_date <= end_date:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date,
                        platform_ids=platforms
                    )

                    # Collecte les actualités de cette date
                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)
                        for title, info in titles.items():
                            # Si un sujet est précisé, ne collecte que les titres le contenant
                            if topic and topic.lower() not in title.lower():
                                continue

                            news_item = {
                                "platform": platform_name,
                                "title": title,
                                "ranks": info.get("ranks", []),
                                "count": len(info.get("ranks", [])),
                                "date": current_date.strftime("%Y-%m-%d")
                            }

                            # Ajoute conditionnellement les champs URL
                            if include_url:
                                news_item["url"] = info.get("url", "")
                                news_item["mobileUrl"] = info.get("mobileUrl", "")

                            all_news_items.append(news_item)

                except DataNotFoundError:
                    # Aucune donnée pour cette date, on passe au jour suivant
                    pass

                # Jour suivant
                current_date += timedelta(days=1)

            if not all_news_items:
                time_desc = "aujourd'hui" if start_date == end_date else f"du {start_date.strftime('%Y-%m-%d')} au {end_date.strftime('%Y-%m-%d')}"
                raise DataNotFoundError(
                    f"Aucune actualité correspondante trouvée ({time_desc})",
                    suggestion="Veuillez essayer un autre sujet, une autre plage de dates ou une autre plateforme"
                )

            # Déduplication (un même titre n'est conservé qu'une fois)
            unique_news = {}
            for item in all_news_items:
                key = f"{item['platform']}::{item['title']}"
                if key not in unique_news:
                    unique_news[key] = item
                else:
                    # Fusionne les ranks (si une même actualité apparaît sur plusieurs jours)
                    existing = unique_news[key]
                    existing["ranks"].extend(item["ranks"])
                    existing["count"] = len(existing["ranks"])

            deduplicated_news = list(unique_news.values())

            # Trie par pondération (si activé)
            if sort_by_weight:
                deduplicated_news.sort(
                    key=lambda x: calculate_news_weight(x),
                    reverse=True
                )

            # Limite le nombre de résultats
            selected_news = deduplicated_news[:limit]

            # Génère le prompt IA
            ai_prompt = self._create_sentiment_analysis_prompt(
                news_data=selected_news,
                topic=topic
            )

            # Construit la description de la plage temporelle
            if start_date == end_date:
                time_range_desc = start_date.strftime("%Y-%m-%d")
            else:
                time_range_desc = f"du {start_date.strftime('%Y-%m-%d')} au {end_date.strftime('%Y-%m-%d')}"

            result = {
                "success": True,
                "method": "ai_prompt_generation",
                "summary": {
                    "description": "Données d'analyse de sentiment et prompt IA",
                    "total_found": len(deduplicated_news),
                    "returned": len(selected_news),
                    "requested_limit": limit,
                    "duplicates_removed": len(all_news_items) - len(deduplicated_news),
                    "topic": topic,
                    "time_range": time_range_desc,
                    "platforms": list(set(item["platform"] for item in selected_news)),
                    "sorted_by_weight": sort_by_weight
                },
                "ai_prompt": ai_prompt,
                "data": selected_news,
                "usage_note": "Veuillez envoyer le contenu du champ ai_prompt à une IA pour l'analyse de sentiment"
            }

            # Si le nombre retourné est inférieur au nombre demandé, ajoute une note
            if len(selected_news) < limit and len(deduplicated_news) >= limit:
                result["note"] = "Le nombre retourné est inférieur au nombre demandé en raison de la déduplication (un même titre n'est conservé qu'une fois sur les différentes plateformes)"
            elif len(deduplicated_news) < limit:
                result["note"] = f"Seules {len(deduplicated_news)} actualités correspondantes ont été trouvées dans la plage temporelle indiquée"

            return result

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def _create_sentiment_analysis_prompt(
        self,
        news_data: List[Dict],
        topic: Optional[str]
    ) -> str:
        """
        Crée le prompt IA pour l'analyse de sentiment

        Args:
            news_data: liste des données d'actualités (déjà triées et limitées en nombre)
            topic: mot-clé du sujet

        Returns:
            prompt IA formaté
        """
        # Regroupe par plateforme
        platform_news = defaultdict(list)
        for item in news_data:
            platform_news[item["platform"]].append({
                "title": item["title"],
                "date": item.get("date", "")
            })

        # Construit le prompt
        prompt_parts = []

        # 1. Description de la tâche
        if topic:
            prompt_parts.append(f"Analyse le sentiment des titres d'actualités suivants concernant « {topic} ».")
        else:
            prompt_parts.append("Analyse le sentiment des titres d'actualités suivants.")

        prompt_parts.append("")
        prompt_parts.append("Consignes d'analyse :")
        prompt_parts.append("1. Identifier le sentiment de chaque actualité (positif/négatif/neutre)")
        prompt_parts.append("2. Comptabiliser le nombre et le pourcentage de chaque catégorie de sentiment")
        prompt_parts.append("3. Analyser les différences de sentiment entre les plateformes")
        prompt_parts.append("4. Résumer la tendance de sentiment globale")
        prompt_parts.append("5. Citer des échantillons typiques d'actualités positives et négatives")
        prompt_parts.append("")

        # 2. Aperçu des données
        prompt_parts.append(f"Aperçu des données :")
        prompt_parts.append(f"- Nombre total d'actualités : {len(news_data)}")
        prompt_parts.append(f"- Plateformes couvertes : {len(platform_news)}")

        # Plage temporelle
        dates = set(item.get("date", "") for item in news_data if item.get("date"))
        if dates:
            date_list = sorted(dates)
            if len(date_list) == 1:
                prompt_parts.append(f"- Plage temporelle : {date_list[0]}")
            else:
                prompt_parts.append(f"- Plage temporelle : du {date_list[0]} au {date_list[-1]}")

        prompt_parts.append("")

        # 3. Affiche les actualités par plateforme
        prompt_parts.append("Liste des actualités (classées par plateforme, triées par importance) :")
        prompt_parts.append("")

        for platform, items in sorted(platform_news.items()):
            prompt_parts.append(f"=== {platform} === ({len(items)} actualité(s))")
            for i, item in enumerate(items, 1):
                title = item["title"]
                date_str = f" [{item['date']}]" if item.get("date") else ""
                prompt_parts.append(f"{i}. {title}{date_str}")
            prompt_parts.append("")

        # 4. Description du format de sortie
        prompt_parts.append("Produis les résultats d'analyse au format suivant :")
        prompt_parts.append("")
        prompt_parts.append("## Répartition des sentiments")
        prompt_parts.append("- Positif : XX (XX%)")
        prompt_parts.append("- Négatif : XX (XX%)")
        prompt_parts.append("- Neutre : XX (XX%)")
        prompt_parts.append("")
        prompt_parts.append("## Comparaison des sentiments par plateforme")
        prompt_parts.append("[différences de sentiment entre les plateformes]")
        prompt_parts.append("")
        prompt_parts.append("## Tendance de sentiment globale")
        prompt_parts.append("[analyse globale et observations clés]")
        prompt_parts.append("")
        prompt_parts.append("## Échantillons typiques")
        prompt_parts.append("Échantillons d'actualités positives :")
        prompt_parts.append("[citer 3 à 5 actualités]")
        prompt_parts.append("")
        prompt_parts.append("Échantillons d'actualités négatives :")
        prompt_parts.append("[citer 3 à 5 actualités]")

        return "\n".join(prompt_parts)

    def find_similar_news(
        self,
        reference_title: str,
        threshold: float = 0.6,
        limit: int = 50,
        include_url: bool = False
    ) -> Dict:
        """
        Recherche d'actualités similaires - trouve des actualités liées en se basant sur la similarité des titres

        Args:
            reference_title: titre de référence
            threshold: seuil de similarité (entre 0 et 1)
            limit: limite du nombre de résultats, 50 par défaut
            include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

        Returns:
            liste des actualités similaires

        Examples:
            Exemples de questions d'utilisateur :
            - "trouve des actualités similaires à 'baisse de prix Tesla'"
            - "cherche des reportages similaires sur la sortie de l'iPhone"
            - "regarde s'il existe des reportages similaires à cette actualité"

            Exemples d'appel de code :
            >>> tools = AnalyticsTools()
            >>> result = tools.find_similar_news(
            ...     reference_title="Tesla annonce une baisse de prix",
            ...     threshold=0.6,
            ...     limit=10
            ... )
            >>> print(result['similar_news'])
        """
        try:
            # Validation des paramètres
            reference_title = validate_keyword(reference_title)
            threshold = validate_threshold(threshold, default=0.6, min_value=0.0, max_value=1.0)
            limit = validate_limit(limit, default=50)

            # Lit les données
            all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date()

            # Calcule la similarité
            similar_items = []

            for platform_id, titles in all_titles.items():
                platform_name = id_to_name.get(platform_id, platform_id)

                for title, info in titles.items():
                    if title == reference_title:
                        continue

                    # Calcule la similarité
                    similarity = self._calculate_similarity(reference_title, title)

                    if similarity >= threshold:
                        news_item = {
                            "title": title,
                            "platform": platform_id,
                            "platform_name": platform_name,
                            "similarity": round(similarity, 3),
                            "rank": info["ranks"][0] if info["ranks"] else 0
                        }

                        # Ajoute conditionnellement les champs URL
                        if include_url:
                            news_item["url"] = info.get("url", "")

                        similar_items.append(news_item)

            # Trie par similarité
            similar_items.sort(key=lambda x: x["similarity"], reverse=True)

            # Limite le nombre de résultats
            result_items = similar_items[:limit]

            if not result_items:
                raise DataNotFoundError(
                    f"Aucune actualité avec une similarité supérieure à {threshold} n'a été trouvée",
                    suggestion="Veuillez réduire le seuil de similarité ou essayer un autre titre"
                )

            result = {
                "success": True,
                "summary": {
                    "description": "Résultats de recherche d'actualités similaires",
                    "total_found": len(similar_items),
                    "returned": len(result_items),
                    "requested_limit": limit,
                    "threshold": threshold,
                    "reference_title": reference_title
                },
                "data": result_items
            }

            if len(similar_items) < limit:
                result["note"] = f"Avec le seuil de similarité {threshold}, seules {len(similar_items)} actualités similaires ont été trouvées"

            return result

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def search_by_entity(
        self,
        entity: str,
        entity_type: Optional[str] = None,
        limit: int = 50,
        sort_by_weight: bool = True
    ) -> Dict:
        """
        Recherche par entité - recherche les actualités contenant une personne/un lieu/une organisation spécifique

        Args:
            entity: nom de l'entité
            entity_type: type d'entité (person/location/organization), facultatif
            limit: limite du nombre de résultats, 50 par défaut, 200 maximum
            sort_by_weight: indique s'il faut trier par pondération, True par défaut

        Returns:
            liste des actualités liées à l'entité

        Examples:
            Exemples de questions d'utilisateur :
            - "recherche les actualités liées à Musk"
            - "cherche les reportages sur la société Tesla, retourne les 20 premiers"
            - "regarde quelles actualités concernent Pékin"

            Exemples d'appel de code :
            >>> tools = AnalyticsTools()
            >>> result = tools.search_by_entity(
            ...     entity="Musk",
            ...     entity_type="person",
            ...     limit=20
            ... )
            >>> print(result['related_news'])
        """
        try:
            # Validation des paramètres
            entity = validate_keyword(entity)
            limit = validate_limit(limit, default=50)

            if entity_type and entity_type not in ["person", "location", "organization"]:
                raise InvalidParameterError(
                    f"Type d'entité invalide : {entity_type}",
                    suggestion="Types pris en charge : person, location, organization"
                )

            # Lit les données
            all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date()

            # Recherche les actualités contenant l'entité
            related_news = []
            entity_context = Counter()  # Comptabilise les mots autour de l'entité

            for platform_id, titles in all_titles.items():
                platform_name = id_to_name.get(platform_id, platform_id)

                for title, info in titles.items():
                    if entity in title:
                        url = info.get("url", "")
                        mobile_url = info.get("mobileUrl", "")
                        ranks = info.get("ranks", [])
                        count = len(ranks)

                        related_news.append({
                            "title": title,
                            "platform": platform_id,
                            "platform_name": platform_name,
                            "url": url,
                            "mobileUrl": mobile_url,
                            "ranks": ranks,
                            "count": count,
                            "rank": ranks[0] if ranks else 999
                        })

                        # Extrait les mots-clés autour de l'entité
                        keywords = self._extract_keywords(title)
                        entity_context.update(keywords)

            if not related_news:
                raise DataNotFoundError(
                    f"Aucune actualité contenant l'entité '{entity}' n'a été trouvée",
                    suggestion="Veuillez essayer un autre nom d'entité"
                )

            # Retire l'entité elle-même
            if entity in entity_context:
                del entity_context[entity]

            # Trie par pondération (si activé)
            if sort_by_weight:
                related_news.sort(
                    key=lambda x: calculate_news_weight(x),
                    reverse=True
                )
            else:
                # Trie par classement
                related_news.sort(key=lambda x: x["rank"])

            # Limite le nombre de résultats
            result_news = related_news[:limit]

            return {
                "success": True,
                "summary": {
                    "description": f"Actualités liées à l'entité « {entity} »",
                    "entity": entity,
                    "entity_type": entity_type or "auto",
                    "total_found": len(related_news),
                    "returned": len(result_news),
                    "sorted_by_weight": sort_by_weight
                },
                "data": result_news,
                "related_keywords": [
                    {"keyword": k, "count": v}
                    for k, v in entity_context.most_common(10)
                ]
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def generate_summary_report(
        self,
        report_type: str = "daily",
        date_range: Optional[Union[Dict[str, str], str]] = None
    ) -> Dict:
        """
        Générateur de résumé quotidien/hebdomadaire - génère automatiquement un rapport de synthèse des sujets populaires

        Args:
            report_type: type de rapport (daily/weekly)
            date_range: plage de dates personnalisée (facultatif)

        Returns:
            rapport de synthèse au format Markdown

        Examples:
            Exemples de questions d'utilisateur :
            - "génère le rapport de synthèse des actualités d'aujourd'hui"
            - "donne-moi une synthèse des sujets populaires de la semaine"
            - "génère un rapport d'analyse des actualités des 7 derniers jours"

            Exemples d'appel de code :
            >>> tools = AnalyticsTools()
            >>> result = tools.generate_summary_report(
            ...     report_type="daily"
            ... )
            >>> print(result['markdown_report'])
        """
        try:
            # Validation des paramètres
            if report_type not in ["daily", "weekly"]:
                raise InvalidParameterError(
                    f"Type de rapport invalide : {report_type}",
                    suggestion="Types pris en charge : daily, weekly"
                )

            # Détermine la plage de dates
            if date_range:
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                if report_type == "daily":
                    start_date = end_date = datetime.now()
                else:  # weekly
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=6)

            # Collecte les données
            all_keywords = Counter()
            all_platforms_news = defaultdict(int)
            all_titles_list = []

            current_date = start_date
            while current_date <= end_date:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)
                        all_platforms_news[platform_name] += len(titles)

                        for title in titles.keys():
                            all_titles_list.append({
                                "title": title,
                                "platform": platform_name,
                                "date": current_date.strftime("%Y-%m-%d")
                            })

                            # Extrait les mots-clés
                            keywords = self._extract_keywords(title)
                            all_keywords.update(keywords)

                except DataNotFoundError:
                    pass

                current_date += timedelta(days=1)

            # Génère le rapport
            report_title = f"Synthèse des sujets d'actualité {'quotidienne' if report_type == 'daily' else 'hebdomadaire'}"
            date_str = f"{start_date.strftime('%Y-%m-%d')}" if report_type == "daily" else f"du {start_date.strftime('%Y-%m-%d')} au {end_date.strftime('%Y-%m-%d')}"

            # Construit le rapport Markdown
            markdown = f"""# {report_title}

**Date du rapport** : {date_str}
**Heure de génération** : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 📊 Aperçu des données

- **Nombre total d'actualités** : {len(all_titles_list)}
- **Plateformes couvertes** : {len(all_platforms_news)}
- **Nombre de mots-clés populaires** : {len(all_keywords)}

## 🔥 TOP 10 des sujets populaires

"""

            # Ajoute les TOP 10 mots-clés
            for i, (keyword, count) in enumerate(all_keywords.most_common(10), 1):
                markdown += f"{i}. **{keyword}** - {count} occurrence(s)\n"

            # Analyse des plateformes
            markdown += "\n## 📱 Activité des plateformes\n\n"
            sorted_platforms = sorted(all_platforms_news.items(), key=lambda x: x[1], reverse=True)

            for platform, count in sorted_platforms:
                markdown += f"- **{platform}** : {count} actualité(s)\n"

            # Évolution des tendances (s'il s'agit d'un rapport hebdomadaire)
            if report_type == "weekly":
                markdown += "\n## 📈 Analyse des tendances\n\n"
                markdown += "Sujets restés populaires cette semaine (données d'échantillon) :\n\n"

                # Analyse de tendance simple
                top_keywords = [kw for kw, _ in all_keywords.most_common(5)]
                for keyword in top_keywords:
                    markdown += f"- **{keyword}** : populaire en continu\n"

            # Ajoute des actualités d'échantillon (sélection par pondération, pour garantir le déterminisme)
            markdown += "\n## 📰 Sélection d'actualités\n\n"

            # Sélection déterministe : trie par pondération du titre, prend les 5 premières
            # Ainsi une même entrée retourne toujours le même résultat
            if all_titles_list:
                # Calcule le score de pondération de chaque actualité (basé sur le nombre d'occurrences des mots-clés)
                news_with_scores = []
                for news in all_titles_list:
                    # Pondération simple : compte le nombre de mots-clés TOP contenus
                    score = 0
                    title_lower = news['title'].lower()
                    for keyword, count in all_keywords.most_common(10):
                        if keyword.lower() in title_lower:
                            score += count
                    news_with_scores.append((news, score))

                # Trie par pondération décroissante, à pondération égale par ordre alphabétique du titre (pour garantir le déterminisme)
                news_with_scores.sort(key=lambda x: (-x[1], x[0]['title']))

                # Prend les 5 premières
                sample_news = [item[0] for item in news_with_scores[:5]]

                for news in sample_news:
                    markdown += f"- [{news['platform']}] {news['title']}\n"

            markdown += "\n---\n\n*Ce rapport est généré automatiquement par TrendRadar MCP*\n"

            return {
                "success": True,
                "report_type": report_type,
                "date_range": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                },
                "markdown_report": markdown,
                "statistics": {
                    "total_news": len(all_titles_list),
                    "platforms_count": len(all_platforms_news),
                    "keywords_count": len(all_keywords),
                    "top_keyword": all_keywords.most_common(1)[0] if all_keywords else None
                }
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def get_platform_activity_stats(
        self,
        date_range: Optional[Union[Dict[str, str], str]] = None
    ) -> Dict:
        """
        Statistiques d'activité des plateformes - statistiques de la fréquence de publication et des plages horaires d'activité par plateforme

        Args:
            date_range: plage de dates (facultatif)

        Returns:
            résultats des statistiques d'activité des plateformes

        Examples:
            Exemples de questions d'utilisateur :
            - "calcule l'activité de chaque plateforme aujourd'hui"
            - "regarde quelle plateforme se met à jour le plus fréquemment"
            - "analyse les habitudes horaires de publication de chaque plateforme"

            Exemples d'appel de code :
            >>> # Consulte l'activité des plateformes (en supposant qu'aujourd'hui est le 2025-11-17)
            >>> result = tools.get_platform_activity_stats(
            ...     date_range={"start": "2025-11-08", "end": "2025-11-17"}
            ... )
            >>> print(result['platform_activity'])
        """
        try:
            # Validation des paramètres
            date_range_tuple = validate_date_range(date_range)

            # Détermine la plage de dates
            if date_range_tuple:
                start_date, end_date = date_range_tuple
            else:
                start_date = end_date = datetime.now()

            # Statistiques d'activité de chaque plateforme
            platform_activity = defaultdict(lambda: {
                "total_updates": 0,
                "days_active": set(),
                "news_count": 0,
                "hourly_distribution": Counter()
            })

            # Parcourt la plage de dates
            current_date = start_date
            while current_date <= end_date:
                try:
                    all_titles, id_to_name, timestamps = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)

                        platform_activity[platform_name]["news_count"] += len(titles)
                        platform_activity[platform_name]["days_active"].add(current_date.strftime("%Y-%m-%d"))

                        # Comptabilise le nombre de mises à jour (basé sur le nombre de fichiers)
                        platform_activity[platform_name]["total_updates"] += len(timestamps)

                        # Comptabilise la répartition horaire (basée sur l'heure dans le nom de fichier)
                        for filename in timestamps.keys():
                            # Analyse l'heure dans le nom de fichier (format : HHMM.txt)
                            match = re.match(r'(\d{2})(\d{2})\.txt', filename)
                            if match:
                                hour = int(match.group(1))
                                platform_activity[platform_name]["hourly_distribution"][hour] += 1

                except DataNotFoundError:
                    pass

                current_date += timedelta(days=1)

            # Convertit en format sérialisable
            result_activity = {}
            for platform, stats in platform_activity.items():
                days_count = len(stats["days_active"])
                avg_news_per_day = stats["news_count"] / days_count if days_count > 0 else 0

                # Identifie les plages horaires les plus actives
                most_active_hours = stats["hourly_distribution"].most_common(3)

                result_activity[platform] = {
                    "total_updates": stats["total_updates"],
                    "news_count": stats["news_count"],
                    "days_active": days_count,
                    "avg_news_per_day": round(avg_news_per_day, 2),
                    "most_active_hours": [
                        {"hour": f"{hour:02d}:00", "count": count}
                        for hour, count in most_active_hours
                    ],
                    "activity_score": round(stats["news_count"] / max(days_count, 1), 2)
                }

            # Trie par activité
            sorted_platforms = sorted(
                result_activity.items(),
                key=lambda x: x[1]["activity_score"],
                reverse=True
            )

            return {
                "success": True,
                "date_range": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                },
                "platform_activity": dict(sorted_platforms),
                "most_active_platform": sorted_platforms[0][0] if sorted_platforms else None,
                "total_platforms": len(result_activity)
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def analyze_topic_lifecycle(
        self,
        topic: str,
        date_range: Optional[Union[Dict[str, str], str]] = None
    ) -> Dict:
        """
        Analyse du cycle de vie d'un sujet - suit le cycle complet d'un sujet, de son apparition à sa disparition

        Args:
            topic: mot-clé du sujet
            date_range: plage de dates (facultatif)
                       - **format** : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                       - **par défaut** : si non précisée, analyse les 7 derniers jours

        Returns:
            résultats de l'analyse du cycle de vie d'un sujet

        Examples:
            Exemples de questions d'utilisateur :
            - "analyse le cycle de vie du sujet 'intelligence artificielle'"
            - "regarde si le sujet 'iPhone' est un feu de paille ou un sujet durablement populaire"
            - "suis l'évolution de popularité du sujet 'Bitcoin'"

            Exemples d'appel de code :
            >>> # Analyse le cycle de vie d'un sujet (en supposant qu'aujourd'hui est le 2025-11-17)
            >>> result = tools.analyze_topic_lifecycle(
            ...     topic="intelligence artificielle",
            ...     date_range={"start": "2025-10-19", "end": "2025-11-17"}
            ... )
            >>> print(result['lifecycle_stage'])
        """
        try:
            # Validation des paramètres
            topic = validate_keyword(topic)

            # Traite la plage de dates (les 7 derniers jours par défaut si non précisée)
            if date_range:
                from ..utils.validators import validate_date_range
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                # Les 7 derniers jours par défaut
                end_date = datetime.now()
                start_date = end_date - timedelta(days=6)

            # Collecte les données historiques du sujet
            lifecycle_data = []
            current_date = start_date
            while current_date <= end_date:
                try:
                    all_titles, _, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    # Comptabilise le nombre d'occurrences du sujet ce jour-là
                    count = 0
                    for _, titles in all_titles.items():
                        for title in titles.keys():
                            if topic.lower() in title.lower():
                                count += 1

                    lifecycle_data.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "count": count
                    })

                except DataNotFoundError:
                    lifecycle_data.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "count": 0
                    })

                current_date += timedelta(days=1)

            # Calcule le nombre de jours analysés
            total_days = (end_date - start_date).days + 1

            # Analyse les phases du cycle de vie
            counts = [item["count"] for item in lifecycle_data]

            if not any(counts):
                time_desc = f"du {start_date.strftime('%Y-%m-%d')} au {end_date.strftime('%Y-%m-%d')}"
                raise DataNotFoundError(
                    f"Le sujet '{topic}' n'a pas été trouvé sur la période {time_desc}",
                    suggestion="Veuillez essayer un autre sujet ou élargir la plage temporelle"
                )

            # Trouve la première et la dernière apparition
            first_appearance = next((item["date"] for item in lifecycle_data if item["count"] > 0), None)
            last_appearance = next((item["date"] for item in reversed(lifecycle_data) if item["count"] > 0), None)

            # Calcule le pic
            max_count = max(counts)
            peak_index = counts.index(max_count)
            peak_date = lifecycle_data[peak_index]["date"]

            # Calcule la moyenne et l'écart-type (implémentation simple)
            non_zero_counts = [c for c in counts if c > 0]
            avg_count = sum(non_zero_counts) / len(non_zero_counts) if non_zero_counts else 0

            # Détermine la phase du cycle de vie
            recent_counts = counts[-3:]  # Les 3 derniers jours
            early_counts = counts[:3]    # Les 3 premiers jours

            if sum(recent_counts) > sum(early_counts):
                lifecycle_stage = "phase de croissance"
            elif sum(recent_counts) < sum(early_counts) * 0.5:
                lifecycle_stage = "phase de déclin"
            elif max_count in recent_counts:
                lifecycle_stage = "phase d'explosion"
            else:
                lifecycle_stage = "phase de stabilité"

            # Classification : feu de paille vs sujet durablement populaire
            active_days = sum(1 for c in counts if c > 0)

            if active_days <= 2 and max_count > avg_count * 2:
                topic_type = "feu de paille"
            elif active_days >= total_days * 0.6:
                topic_type = "sujet durablement populaire"
            else:
                topic_type = "sujet périodique"

            return {
                "success": True,
                "topic": topic,
                "date_range": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d"),
                    "total_days": total_days
                },
                "lifecycle_data": lifecycle_data,
                "analysis": {
                    "first_appearance": first_appearance,
                    "last_appearance": last_appearance,
                    "peak_date": peak_date,
                    "peak_count": max_count,
                    "active_days": active_days,
                    "avg_daily_mentions": round(avg_count, 2),
                    "lifecycle_stage": lifecycle_stage,
                    "topic_type": topic_type
                }
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def detect_viral_topics(
        self,
        threshold: float = 3.0,
        time_window: int = 24
    ) -> Dict:
        """
        Détection de popularité anormale - identifie automatiquement les sujets devenus soudainement viraux

        Args:
            threshold: seuil de multiplicateur de pic de popularité
            time_window: fenêtre de détection (heures)

        Returns:
            liste des sujets viraux

        Examples:
            Exemples de questions d'utilisateur :
            - "détecte quels sujets sont devenus soudainement viraux aujourd'hui"
            - "regarde s'il y a des actualités à popularité anormale"
            - "alerte sur d'éventuels événements majeurs"

            Exemples d'appel de code :
            >>> tools = AnalyticsTools()
            >>> result = tools.detect_viral_topics(
            ...     threshold=3.0,
            ...     time_window=24
            ... )
            >>> print(result['viral_topics'])
        """
        try:
            # Validation des paramètres
            threshold = validate_threshold(threshold, default=3.0, min_value=1.0, max_value=100.0)
            time_window = validate_limit(time_window, default=24, max_limit=72)

            # Lit les données actuelles et précédentes
            current_all_titles, _, _ = self.data_service.parser.read_all_titles_for_date()

            # Lit les données d'hier comme référence
            yesterday = datetime.now() - timedelta(days=1)
            try:
                previous_all_titles, _, _ = self.data_service.parser.read_all_titles_for_date(
                    date=yesterday
                )
            except DataNotFoundError:
                previous_all_titles = {}

            # Comptabilise la fréquence actuelle des mots-clés
            current_keywords = Counter()
            current_keyword_titles = defaultdict(list)

            for _, titles in current_all_titles.items():
                for title in titles.keys():
                    keywords = self._extract_keywords(title)
                    current_keywords.update(keywords)

                    for kw in keywords:
                        current_keyword_titles[kw].append(title)

            # Comptabilise la fréquence précédente des mots-clés
            previous_keywords = Counter()

            for _, titles in previous_all_titles.items():
                for title in titles.keys():
                    keywords = self._extract_keywords(title)
                    previous_keywords.update(keywords)

            # Détecte la popularité anormale
            viral_topics = []

            for keyword, current_count in current_keywords.items():
                previous_count = previous_keywords.get(keyword, 0)

                # Calcule le multiplicateur de croissance
                if previous_count == 0:
                    # Sujet nouvellement apparu
                    if current_count >= 5:  # Au moins 5 occurrences pour être considéré comme viral
                        growth_rate = float('inf')
                        is_viral = True
                    else:
                        continue
                else:
                    growth_rate = current_count / previous_count
                    is_viral = growth_rate >= threshold

                if is_viral:
                    viral_topics.append({
                        "keyword": keyword,
                        "current_count": current_count,
                        "previous_count": previous_count,
                        "growth_rate": round(growth_rate, 2) if growth_rate != float('inf') else "nouveau sujet",
                        "sample_titles": current_keyword_titles[keyword][:3],
                        "alert_level": "élevé" if growth_rate > threshold * 2 else "moyen"
                    })

            # Trie par taux de croissance
            viral_topics.sort(
                key=lambda x: x["current_count"] if x["growth_rate"] == "nouveau sujet" else x["growth_rate"],
                reverse=True
            )

            if not viral_topics:
                return {
                    "success": True,
                    "summary": {
                        "description": "Résultats de la détection de popularité anormale",
                        "total": 0,
                        "threshold": threshold,
                        "time_window": time_window
                    },
                    "data": [],
                    "message": f"Aucun sujet avec une croissance de popularité supérieure à {threshold} fois n'a été détecté"
                }

            return {
                "success": True,
                "summary": {
                    "description": "Résultats de la détection de popularité anormale",
                    "total": len(viral_topics),
                    "threshold": threshold,
                    "time_window": time_window,
                    "detection_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "data": viral_topics
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def predict_trending_topics(
        self,
        lookahead_hours: int = 6,
        confidence_threshold: float = 0.7
    ) -> Dict:
        """
        Prédiction de sujets - prédit les sujets potentiellement populaires à venir en se basant sur les données historiques

        Args:
            lookahead_hours: nombre d'heures à prédire dans le futur
            confidence_threshold: seuil de confiance

        Returns:
            liste des sujets à potentiel prédits

        Examples:
            Exemples de questions d'utilisateur :
            - "prédis les sujets potentiellement populaires pour les 6 prochaines heures"
            - "quels sujets pourraient devenir populaires"
            - "détecte tôt les sujets à potentiel"

            Exemples d'appel de code :
            >>> tools = AnalyticsTools()
            >>> result = tools.predict_trending_topics(
            ...     lookahead_hours=6,
            ...     confidence_threshold=0.7
            ... )
            >>> print(result['predicted_topics'])
        """
        try:
            # Validation des paramètres
            lookahead_hours = validate_limit(lookahead_hours, default=6, max_limit=48)
            confidence_threshold = validate_threshold(
                confidence_threshold,
                default=0.7,
                min_value=0.0,
                max_value=1.0,
                param_name="confidence_threshold"
            )

            # Collecte les données des 3 derniers jours pour la prédiction
            keyword_trends = defaultdict(list)

            for days_ago in range(3, 0, -1):
                date = datetime.now() - timedelta(days=days_ago)

                try:
                    all_titles, _, _ = self.data_service.parser.read_all_titles_for_date(
                        date=date
                    )

                    # Comptabilise les mots-clés
                    keywords_count = Counter()
                    for _, titles in all_titles.items():
                        for title in titles.keys():
                            keywords = self._extract_keywords(title)
                            keywords_count.update(keywords)

                    # Enregistre les données historiques de chaque mot-clé
                    for keyword, count in keywords_count.items():
                        keyword_trends[keyword].append(count)

                except DataNotFoundError:
                    pass

            # Ajoute les données d'aujourd'hui
            try:
                all_titles, _, _ = self.data_service.parser.read_all_titles_for_date()

                keywords_count = Counter()
                keyword_titles = defaultdict(list)

                for _, titles in all_titles.items():
                    for title in titles.keys():
                        keywords = self._extract_keywords(title)
                        keywords_count.update(keywords)

                        for kw in keywords:
                            keyword_titles[kw].append(title)

                for keyword, count in keywords_count.items():
                    keyword_trends[keyword].append(count)

            except DataNotFoundError:
                raise DataNotFoundError(
                    "Aucune donnée trouvée pour aujourd'hui",
                    suggestion="Veuillez attendre la fin de la tâche de collecte"
                )

            # Prédit les sujets à potentiel
            predicted_topics = []

            for keyword, trend_data in keyword_trends.items():
                if len(trend_data) < 2:
                    continue

                # Prédiction de tendance linéaire simple
                # Calcule le taux de croissance
                recent_value = trend_data[-1]
                previous_value = trend_data[-2] if len(trend_data) >= 2 else 0

                if previous_value == 0:
                    if recent_value >= 3:
                        growth_rate = 1.0
                    else:
                        continue
                else:
                    growth_rate = (recent_value - previous_value) / previous_value

                # Détermine s'il s'agit d'une tendance à la hausse
                if growth_rate > 0.3:  # Croissance supérieure à 30 %
                    # Calcule la confiance (basée sur la stabilité de la tendance)
                    if len(trend_data) >= 3:
                        # Vérifie si la croissance est continue
                        is_consistent = all(
                            trend_data[i] <= trend_data[i+1]
                            for i in range(len(trend_data)-1)
                        )
                        confidence = 0.9 if is_consistent else 0.7
                    else:
                        confidence = 0.6

                    if confidence >= confidence_threshold:
                        predicted_topics.append({
                            "keyword": keyword,
                            "current_count": recent_value,
                            "growth_rate": round(growth_rate * 100, 2),
                            "confidence": round(confidence, 2),
                            "trend_data": trend_data,
                            "prediction": "tendance à la hausse, pourrait devenir populaire",
                            "sample_titles": keyword_titles.get(keyword, [])[:3]
                        })

            # Trie par confiance et taux de croissance
            predicted_topics.sort(
                key=lambda x: (x["confidence"], x["growth_rate"]),
                reverse=True
            )

            return {
                "success": True,
                "summary": {
                    "description": "Résultats de la prédiction de sujets populaires",
                    "total": len(predicted_topics),
                    "returned": min(20, len(predicted_topics)),
                    "lookahead_hours": lookahead_hours,
                    "confidence_threshold": confidence_threshold,
                    "prediction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "data": predicted_topics[:20],  # Retourne les TOP 20
                "note": "La prédiction se base sur les tendances historiques, les résultats réels peuvent diverger"
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    # ==================== Méthodes auxiliaires ====================

    def _extract_keywords(self, title: str, min_length: int = 2) -> List[str]:
        """
        Extrait les mots-clés d'un titre (implémentation simple)

        Args:
            title: texte du titre
            min_length: longueur minimale des mots-clés

        Returns:
            liste de mots-clés
        """
        # Supprime les URL et les caractères spéciaux
        title = re.sub(r'http[s]?://\S+', '', title)
        title = re.sub(r'[^\w\s]', ' ', title)

        # Découpage simple (par espaces et séparateurs courants)
        words = re.split(r'[\s，。！？、]+', title)

        # Filtre les mots vides et les mots courts
        stopwords = {'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'que', 'qui', 'dans', 'sur', 'pour', 'par', 'avec', 'est', 'sont', 'ce', 'se', 'ne', 'pas', 'plus', 'au', 'aux'}

        keywords = [
            word.strip() for word in words
            if word.strip() and len(word.strip()) >= min_length and word.strip() not in stopwords
        ]

        return keywords

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calcule la similarité entre deux textes

        Args:
            text1: texte 1
            text2: texte 2

        Returns:
            score de similarité (entre 0 et 1)
        """
        # Utilise SequenceMatcher pour calculer la similarité
        return SequenceMatcher(None, text1, text2).ratio()

    def _find_unique_topics(self, platform_stats: Dict) -> Dict[str, List[str]]:
        """
        Identifie les sujets populaires propres à chaque plateforme

        Args:
            platform_stats: données statistiques des plateformes

        Returns:
            dictionnaire des sujets propres à chaque plateforme
        """
        unique_topics = {}

        # Récupère les TOP mots-clés de chaque plateforme
        platform_keywords = {}
        for platform, stats in platform_stats.items():
            top_keywords = set([kw for kw, _ in stats["top_keywords"].most_common(10)])
            platform_keywords[platform] = top_keywords

        # Identifie les mots-clés propres
        for platform, keywords in platform_keywords.items():
            # Récupère tous les mots-clés des autres plateformes
            other_keywords = set()
            for other_platform, other_kws in platform_keywords.items():
                if other_platform != platform:
                    other_keywords.update(other_kws)

            # Identifie ceux qui sont propres
            unique = keywords - other_keywords
            if unique:
                unique_topics[platform] = list(unique)[:5]  # 5 au maximum

        return unique_topics

    # ==================== Outil d'agrégation multi-plateformes ====================

    def aggregate_news(
        self,
        date_range: Optional[Union[Dict[str, str], str]] = None,
        platforms: Optional[List[str]] = None,
        similarity_threshold: float = 0.7,
        limit: int = 50,
        include_url: bool = False
    ) -> Dict:
        """
        Agrégation multi-plateformes des actualités - déduplique et fusionne les actualités similaires

        Fusionne en une seule actualité agrégée un même événement rapporté par différentes plateformes,
        et affiche la couverture de cette actualité sur chaque plateforme ainsi que sa popularité globale.

        Args:
            date_range: plage de dates (facultatif)
                - non précisée : interroge aujourd'hui
                - {\"start\": \"YYYY-MM-DD\", \"end\": \"YYYY-MM-DD\"} : plage de dates
            platforms: liste de filtrage des plateformes, par ex. ['zhihu', 'weibo']
            similarity_threshold: seuil de similarité, entre 0 et 1, 0.7 par défaut
            limit: nombre d'actualités agrégées retournées, 50 par défaut
            include_url: indique s'il faut inclure les liens URL, False par défaut

        Returns:
            dictionnaire du résultat d'agrégation, contenant :
            - aggregated_news: liste des actualités agrégées
            - statistics: statistiques d'agrégation
        """
        try:
            # Validation des paramètres
            platforms = validate_platforms(platforms)
            similarity_threshold = validate_threshold(
                similarity_threshold, default=0.7, min_value=0.3, max_value=1.0
            )
            limit = validate_limit(limit, default=50)

            # Traite la plage de dates
            if date_range:
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                start_date = end_date = datetime.now()

            # Collecte toutes les actualités
            all_news = []
            current_date = start_date

            while current_date <= end_date:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date,
                        platform_ids=platforms
                    )

                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)

                        for title, info in titles.items():
                            news_item = {
                                "title": title,
                                "platform": platform_id,
                                "platform_name": platform_name,
                                "date": current_date.strftime("%Y-%m-%d"),
                                "ranks": info.get("ranks", []),
                                "count": len(info.get("ranks", [])),
                                "rank": info["ranks"][0] if info["ranks"] else 999
                            }

                            if include_url:
                                news_item["url"] = info.get("url", "")
                                news_item["mobileUrl"] = info.get("mobileUrl", "")

                            # Calcule la pondération
                            news_item["weight"] = calculate_news_weight(news_item)
                            all_news.append(news_item)

                except DataNotFoundError:
                    pass

                current_date += timedelta(days=1)

            if not all_news:
                return {
                    "success": True,
                    "summary": {
                        "description": "Résultats de l'agrégation multi-plateformes des actualités",
                        "total": 0,
                        "returned": 0
                    },
                    "data": [],
                    "message": "Aucune donnée d'actualités trouvée"
                }

            # Exécute l'agrégation
            aggregated = self._aggregate_similar_news(
                all_news, similarity_threshold, include_url
            )

            # Trie par pondération globale
            aggregated.sort(key=lambda x: x["aggregate_weight"], reverse=True)

            # Limite le nombre de résultats
            results = aggregated[:limit]

            # Statistiques
            total_original = len(all_news)
            total_aggregated = len(aggregated)
            dedup_rate = 1 - (total_aggregated / total_original) if total_original > 0 else 0

            platform_coverage = Counter()
            for item in aggregated:
                for p in item["platforms"]:
                    platform_coverage[p] += 1

            return {
                "success": True,
                "summary": {
                    "description": "Résultats de l'agrégation multi-plateformes des actualités",
                    "original_count": total_original,
                    "aggregated_count": total_aggregated,
                    "returned": len(results),
                    "deduplication_rate": f"{dedup_rate * 100:.1f}%",
                    "similarity_threshold": similarity_threshold,
                    "date_range": {
                        "start": start_date.strftime("%Y-%m-%d"),
                        "end": end_date.strftime("%Y-%m-%d")
                    }
                },
                "data": results,
                "statistics": {
                    "platform_coverage": dict(platform_coverage),
                    "multi_platform_news": len([a for a in aggregated if len(a["platforms"]) > 1]),
                    "single_platform_news": len([a for a in aggregated if len(a["platforms"]) == 1])
                }
            }

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def _aggregate_similar_news(
        self,
        news_list: List[Dict],
        threshold: float,
        include_url: bool
    ) -> List[Dict]:
        """
        Agrège la liste d'actualités par similarité

        Utilise une stratégie de filtrage à deux niveaux : d'abord un pré-filtrage rapide par Jaccard, puis un calcul précis par SequenceMatcher

        Args:
            news_list: liste d'actualités
            threshold: seuil de similarité
            include_url: indique s'il faut inclure l'URL

        Returns:
            liste des actualités agrégées
        """
        if not news_list:
            return []

        # Précalcule les ensembles de caractères pour un filtrage rapide
        prepared_news = []
        for news in news_list:
            char_set = set(news["title"])
            prepared_news.append({
                "data": news,
                "char_set": char_set,
                "set_len": len(char_set)
            })

        # Trie par pondération
        sorted_items = sorted(prepared_news, key=lambda x: x["data"].get("weight", 0), reverse=True)

        aggregated = []
        used_indices = set()
        PRE_FILTER_RATIO = 0.5  # Coefficient du seuil de pré-filtrage

        for i, item in enumerate(sorted_items):
            if i in used_indices:
                continue

            news = item["data"]
            base_set = item["char_set"]
            base_len = item["set_len"]

            group = {
                "representative_title": news["title"],
                "platforms": [news["platform_name"]],
                "platform_ids": [news["platform"]],
                "dates": [news["date"]],
                "best_rank": news["rank"],
                "total_count": news["count"],
                "aggregate_weight": news.get("weight", 0),
                "sources": [{
                    "platform": news["platform_name"],
                    "rank": news["rank"],
                    "date": news["date"]
                }]
            }

            if include_url and news.get("url"):
                group["urls"] = [{
                    "platform": news["platform_name"],
                    "url": news.get("url", ""),
                    "mobileUrl": news.get("mobileUrl", "")
                }]

            used_indices.add(i)

            # Recherche les actualités similaires
            for j in range(i + 1, len(sorted_items)):
                if j in used_indices:
                    continue

                compare_item = sorted_items[j]
                compare_set = compare_item["char_set"]
                compare_len = compare_item["set_len"]

                # Pré-filtrage rapide : vérification de longueur
                if base_len == 0 or compare_len == 0:
                    continue

                # Pré-filtrage rapide : vérification du ratio de longueur
                if min(base_len, compare_len) / max(base_len, compare_len) < (threshold * PRE_FILTER_RATIO):
                    continue

                # Pré-filtrage rapide : similarité de Jaccard
                intersection = len(base_set & compare_set)
                union = len(base_set | compare_set)
                jaccard_sim = intersection / union if union > 0 else 0

                if jaccard_sim < (threshold * PRE_FILTER_RATIO):
                    continue

                # Calcul précis : SequenceMatcher
                other_news = compare_item["data"]
                real_similarity = self._calculate_similarity(news["title"], other_news["title"])

                if real_similarity >= threshold:
                    # Fusionne dans le groupe courant
                    if other_news["platform_name"] not in group["platforms"]:
                        group["platforms"].append(other_news["platform_name"])
                        group["platform_ids"].append(other_news["platform"])

                    if other_news["date"] not in group["dates"]:
                        group["dates"].append(other_news["date"])

                    group["best_rank"] = min(group["best_rank"], other_news["rank"])
                    group["total_count"] += other_news["count"]
                    group["aggregate_weight"] += other_news.get("weight", 0) * 0.5  # Pondération supplémentaire

                    group["sources"].append({
                        "platform": other_news["platform_name"],
                        "rank": other_news["rank"],
                        "date": other_news["date"]
                    })

                    if include_url and other_news.get("url"):
                        if "urls" not in group:
                            group["urls"] = []
                        group["urls"].append({
                            "platform": other_news["platform_name"],
                            "url": other_news.get("url", ""),
                            "mobileUrl": other_news.get("mobileUrl", "")
                        })

                    used_indices.add(j)

            # Ajoute les informations d'agrégation
            group["platform_count"] = len(group["platforms"])
            group["is_cross_platform"] = len(group["platforms"]) > 1

            aggregated.append(group)

        return aggregated

    # ==================== Outil d'analyse comparative entre périodes ====================

    def compare_periods(
        self,
        period1: Union[Dict[str, str], str],
        period2: Union[Dict[str, str], str],
        topic: Optional[str] = None,
        compare_type: str = "overview",
        platforms: Optional[List[str]] = None,
        top_n: int = 10
    ) -> Dict:
        """
        Analyse comparative entre périodes - compare les données d'actualités de deux périodes

        Prend en charge plusieurs dimensions de comparaison : popularité, évolution des sujets, activité des plateformes, etc.

        Args:
            period1: première période
                - {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} : plage de dates
                - "today", "yesterday", "last_week", "last_month" : valeurs prédéfinies
            period2: deuxième période (même format que period1)
            topic: mot-clé de sujet facultatif (comparaison ciblée sur un sujet précis)
            compare_type: type de comparaison
                - "overview": aperçu global (par défaut)
                - "topic_shift": analyse de l'évolution des sujets
                - "platform_activity": comparaison de l'activité des plateformes
            platforms: liste de filtrage des plateformes
            top_n: retourne les TOP N résultats, 10 par défaut

        Returns:
            dictionnaire des résultats de l'analyse comparative
        """
        try:
            # Validation des paramètres
            platforms = validate_platforms(platforms)
            top_n = validate_top_n(top_n, default=10)

            if compare_type not in ["overview", "topic_shift", "platform_activity"]:
                raise InvalidParameterError(
                    f"Type de comparaison non pris en charge : {compare_type}",
                    suggestion="Types pris en charge : overview, topic_shift, platform_activity"
                )

            # Analyse les périodes
            date_range1 = self._parse_period(period1)
            date_range2 = self._parse_period(period2)

            if not date_range1 or not date_range2:
                raise InvalidParameterError(
                    "Format de période invalide",
                    suggestion="Utilisez {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'} ou une valeur prédéfinie comme 'last_week'"
                )

            # Collecte les données des deux périodes
            data1 = self._collect_period_data(date_range1, platforms, topic)
            data2 = self._collect_period_data(date_range2, platforms, topic)

            # Exécute une analyse différente selon le type de comparaison
            if compare_type == "overview":
                analysis_result = self._compare_overview(data1, data2, date_range1, date_range2, top_n)
            elif compare_type == "topic_shift":
                analysis_result = self._compare_topic_shift(data1, data2, date_range1, date_range2, top_n)
            else:  # platform_activity
                analysis_result = self._compare_platform_activity(data1, data2, date_range1, date_range2)

            result = {
                "success": True,
                "summary": {
                    "description": f"Analyse comparative entre périodes ({compare_type})",
                    "compare_type": compare_type,
                    "periods": {
                        "period1": {
                            "start": date_range1[0].strftime("%Y-%m-%d"),
                            "end": date_range1[1].strftime("%Y-%m-%d")
                        },
                        "period2": {
                            "start": date_range2[0].strftime("%Y-%m-%d"),
                            "end": date_range2[1].strftime("%Y-%m-%d")
                        }
                    }
                },
                "data": analysis_result
            }

            if topic:
                result["summary"]["topic_filter"] = topic

            return result

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def _parse_period(self, period: Union[Dict[str, str], str]) -> Optional[tuple]:
        """Analyse une période en tuple de plage de dates"""
        today = datetime.now()

        if isinstance(period, str):
            if period == "today":
                return (today, today)
            elif period == "yesterday":
                yesterday = today - timedelta(days=1)
                return (yesterday, yesterday)
            elif period == "last_week":
                return (today - timedelta(days=7), today - timedelta(days=1))
            elif period == "this_week":
                # Du lundi de cette semaine à aujourd'hui
                days_since_monday = today.weekday()
                monday = today - timedelta(days=days_since_monday)
                return (monday, today)
            elif period == "last_month":
                return (today - timedelta(days=30), today - timedelta(days=1))
            elif period == "this_month":
                first_of_month = today.replace(day=1)
                return (first_of_month, today)
            else:
                return None
        elif isinstance(period, dict):
            try:
                start = datetime.strptime(period["start"], "%Y-%m-%d")
                end = datetime.strptime(period["end"], "%Y-%m-%d")
                return (start, end)
            except (KeyError, ValueError):
                return None
        return None

    def _collect_period_data(
        self,
        date_range: tuple,
        platforms: Optional[List[str]],
        topic: Optional[str]
    ) -> Dict:
        """Collecte les données d'actualités d'une période donnée"""
        start_date, end_date = date_range
        all_news = []
        all_keywords = Counter()
        platform_stats = Counter()

        current_date = start_date
        while current_date <= end_date:
            try:
                all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(
                    date=current_date,
                    platform_ids=platforms
                )

                for platform_id, titles in all_titles.items():
                    platform_name = id_to_name.get(platform_id, platform_id)

                    for title, info in titles.items():
                        # Si un sujet est précisé, filtre les actualités non pertinentes
                        if topic and topic.lower() not in title.lower():
                            continue

                        news_item = {
                            "title": title,
                            "platform": platform_id,
                            "platform_name": platform_name,
                            "date": current_date.strftime("%Y-%m-%d"),
                            "ranks": info.get("ranks", []),
                            "rank": info["ranks"][0] if info["ranks"] else 999
                        }
                        news_item["weight"] = calculate_news_weight(news_item)
                        all_news.append(news_item)

                        # Comptabilise la plateforme
                        platform_stats[platform_name] += 1

                        # Extrait les mots-clés
                        keywords = self._extract_keywords(title)
                        all_keywords.update(keywords)

            except DataNotFoundError:
                pass

            current_date += timedelta(days=1)

        return {
            "news": all_news,
            "news_count": len(all_news),
            "keywords": all_keywords,
            "platform_stats": platform_stats,
            "date_range": date_range
        }

    def _compare_overview(
        self,
        data1: Dict,
        data2: Dict,
        range1: tuple,
        range2: tuple,
        top_n: int
    ) -> Dict:
        """Comparaison de l'aperçu global"""
        # Calcule les variations
        count_change = data2["news_count"] - data1["news_count"]
        count_change_pct = (count_change / data1["news_count"] * 100) if data1["news_count"] > 0 else 0

        # Comparaison des TOP mots-clés
        top_kw1 = [kw for kw, _ in data1["keywords"].most_common(top_n)]
        top_kw2 = [kw for kw, _ in data2["keywords"].most_common(top_n)]

        new_keywords = [kw for kw in top_kw2 if kw not in top_kw1]
        disappeared_keywords = [kw for kw in top_kw1 if kw not in top_kw2]
        persistent_keywords = [kw for kw in top_kw1 if kw in top_kw2]

        # Comparaison des TOP actualités
        top_news1 = sorted(data1["news"], key=lambda x: x.get("weight", 0), reverse=True)[:top_n]
        top_news2 = sorted(data2["news"], key=lambda x: x.get("weight", 0), reverse=True)[:top_n]

        return {
            "overview": {
                "period1_count": data1["news_count"],
                "period2_count": data2["news_count"],
                "count_change": count_change,
                "count_change_percent": f"{count_change_pct:+.1f}%"
            },
            "keyword_analysis": {
                "new_keywords": new_keywords[:5],
                "disappeared_keywords": disappeared_keywords[:5],
                "persistent_keywords": persistent_keywords[:5]
            },
            "top_news": {
                "period1": [{"title": n["title"], "platform": n["platform_name"]} for n in top_news1],
                "period2": [{"title": n["title"], "platform": n["platform_name"]} for n in top_news2]
            }
        }

    def _compare_topic_shift(
        self,
        data1: Dict,
        data2: Dict,
        range1: tuple,
        range2: tuple,
        top_n: int
    ) -> Dict:
        """Analyse de l'évolution des sujets"""
        kw1 = data1["keywords"]
        kw2 = data2["keywords"]

        # Calcule l'évolution de popularité
        all_keywords = set(kw1.keys()) | set(kw2.keys())
        keyword_changes = []

        for kw in all_keywords:
            count1 = kw1.get(kw, 0)
            count2 = kw2.get(kw, 0)
            change = count2 - count1

            if count1 > 0:
                change_pct = (change / count1) * 100
            elif count2 > 0:
                change_pct = 100  # Nouvellement apparu
            else:
                change_pct = 0

            keyword_changes.append({
                "keyword": kw,
                "period1_count": count1,
                "period2_count": count2,
                "change": change,
                "change_percent": round(change_pct, 1)
            })

        # Trie par amplitude de variation
        rising = sorted([k for k in keyword_changes if k["change"] > 0],
                       key=lambda x: x["change"], reverse=True)[:top_n]
        falling = sorted([k for k in keyword_changes if k["change"] < 0],
                        key=lambda x: x["change"])[:top_n]
        new_topics = [k for k in keyword_changes if k["period1_count"] == 0 and k["period2_count"] > 0][:top_n]

        return {
            "rising_topics": rising,
            "falling_topics": falling,
            "new_topics": new_topics,
            "total_keywords": {
                "period1": len(kw1),
                "period2": len(kw2)
            }
        }

    def _compare_platform_activity(
        self,
        data1: Dict,
        data2: Dict,
        range1: tuple,
        range2: tuple
    ) -> Dict:
        """Comparaison de l'activité des plateformes"""
        ps1 = data1["platform_stats"]
        ps2 = data2["platform_stats"]

        all_platforms = set(ps1.keys()) | set(ps2.keys())
        platform_changes = []

        for platform in all_platforms:
            count1 = ps1.get(platform, 0)
            count2 = ps2.get(platform, 0)
            change = count2 - count1

            if count1 > 0:
                change_pct = (change / count1) * 100
            elif count2 > 0:
                change_pct = 100
            else:
                change_pct = 0

            platform_changes.append({
                "platform": platform,
                "period1_count": count1,
                "period2_count": count2,
                "change": change,
                "change_percent": round(change_pct, 1)
            })

        # Trie par variation
        platform_changes.sort(key=lambda x: x["change"], reverse=True)

        return {
            "platform_comparison": platform_changes,
            "most_active_growth": platform_changes[0] if platform_changes else None,
            "least_active_growth": platform_changes[-1] if platform_changes else None,
            "total_activity": {
                "period1": sum(ps1.values()),
                "period2": sum(ps2.values())
            }
        }
