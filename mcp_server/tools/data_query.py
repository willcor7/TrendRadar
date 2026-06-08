"""
Outils de requête de données

Implémente les outils de requête de données du cœur P0.
"""

from typing import Dict, List, Optional, Union

from ..services.data_service import DataService
from ..utils.validators import (
    validate_platforms,
    validate_limit,
    validate_keyword,
    validate_date_range,
    validate_top_n,
    validate_mode,
    validate_date_query,
    normalize_date_range
)
from ..utils.errors import MCPError


class DataQueryTools:
    """Classe des outils de requête de données"""

    def __init__(self, project_root: str = None):
        """
        Initialise les outils de requête de données

        Args:
            project_root: répertoire racine du projet
        """
        self.data_service = DataService(project_root)

    def get_latest_news(
        self,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None,
        include_url: bool = False
    ) -> Dict:
        """
        Récupère le dernier lot de données d'actualités collectées

        Args:
            platforms: liste des ID de plateformes, par ex. ['zhihu', 'weibo']
            limit: limite du nombre de résultats, 20 par défaut
            include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

        Returns:
            dictionnaire de la liste d'actualités

        Example:
            >>> tools = DataQueryTools()
            >>> result = tools.get_latest_news(platforms=['zhihu'], limit=10)
            >>> print(result['total'])
            10
        """
        try:
            # Validation des paramètres
            platforms = validate_platforms(platforms)
            limit = validate_limit(limit, default=50)

            # Récupère les données
            news_list = self.data_service.get_latest_news(
                platforms=platforms,
                limit=limit,
                include_url=include_url
            )

            return {
                "success": True,
                "summary": {
                    "description": "Dernier lot de données d'actualités collectées",
                    "total": len(news_list),
                    "returned": len(news_list),
                    "platforms": platforms or "toutes les plateformes"
                },
                "data": news_list
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

    def search_news_by_keyword(
        self,
        keyword: str,
        date_range: Optional[Union[Dict, str]] = None,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Dict:
        """
        Recherche des actualités historiques par mot-clé

        Args:
            keyword: mot-clé de recherche (obligatoire)
            date_range: plage de dates, format : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            platforms: liste de filtrage des plateformes
            limit: limite du nombre de résultats (facultatif, retourne tout par défaut)

        Returns:
            dictionnaire des résultats de recherche

        Example (en supposant qu'aujourd'hui est le 2025-11-17) :
            >>> tools = DataQueryTools()
            >>> result = tools.search_news_by_keyword(
            ...     keyword="intelligence artificielle",
            ...     date_range={"start": "2025-11-08", "end": "2025-11-17"},
            ...     limit=50
            ... )
            >>> print(result['total'])
        """
        try:
            # Validation des paramètres
            keyword = validate_keyword(keyword)
            date_range_tuple = validate_date_range(date_range)
            platforms = validate_platforms(platforms)

            if limit is not None:
                limit = validate_limit(limit, default=100)

            # Recherche les données
            search_result = self.data_service.search_news_by_keyword(
                keyword=keyword,
                date_range=date_range_tuple,
                platforms=platforms,
                limit=limit
            )

            return {
                **search_result,
                "success": True
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

    def get_trending_topics(
        self,
        top_n: Optional[int] = None,
        mode: Optional[str] = None,
        extract_mode: Optional[str] = None
    ) -> Dict:
        """
        Récupère les statistiques des sujets tendances

        Args:
            top_n: retourne les TOP N sujets, 10 par défaut
            mode: mode temporel
                - "daily": statistiques cumulées de la journée
                - "current": statistiques du dernier lot de données (par défaut)
            extract_mode: mode d'extraction
                - "keywords": comptabilise les mots-clés prédéfinis (basé sur config/frequency_words.txt, par défaut)
                - "auto_extract": extrait automatiquement les mots de fréquence des titres d'actualités

        Returns:
            dictionnaire des statistiques de fréquence des sujets

        Example:
            >>> tools = DataQueryTools()
            >>> # Utilisation des mots-clés prédéfinis
            >>> result = tools.get_trending_topics(top_n=5, mode="current")
            >>> # Extraction automatique des mots de fréquence
            >>> result = tools.get_trending_topics(top_n=10, extract_mode="auto_extract")
        """
        try:
            # Validation des paramètres
            top_n = validate_top_n(top_n, default=10)
            valid_modes = ["daily", "current"]
            mode = validate_mode(mode, valid_modes, default="current")

            # Valide extract_mode
            if extract_mode is None:
                extract_mode = "keywords"
            elif extract_mode not in ["keywords", "auto_extract"]:
                return {
                    "success": False,
                    "error": {
                        "code": "INVALID_PARAMETER",
                        "message": f"Mode d'extraction non pris en charge : {extract_mode}",
                        "suggestion": "Modes pris en charge : keywords, auto_extract"
                    }
                }

            # Récupère les sujets tendances
            trending_result = self.data_service.get_trending_topics(
                top_n=top_n,
                mode=mode,
                extract_mode=extract_mode
            )

            return {
                **trending_result,
                "success": True
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

    def get_news_by_date(
        self,
        date_range: Optional[Union[Dict[str, str], str]] = None,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None,
        include_url: bool = False
    ) -> Dict:
        """
        Interroge les actualités par date, prend en charge les dates en langage naturel

        Args:
            date_range: plage de dates (facultatif, "aujourd'hui" par défaut), prend en charge :
                - objet de plage : {"start": "2025-01-01", "end": "2025-01-07"}
                - dates relatives : aujourd'hui, hier, avant-hier, il y a 3 jours
                - chaîne d'un seul jour : 2025-10-10
            platforms: liste des ID de plateformes, par ex. ['zhihu', 'weibo']
            limit: limite du nombre de résultats, 50 par défaut
            include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

        Returns:
            dictionnaire de la liste d'actualités

        Example:
            >>> tools = DataQueryTools()
            >>> # Sans date précisée, interroge aujourd'hui par défaut
            >>> result = tools.get_news_by_date(platforms=['zhihu'], limit=20)
            >>> # Date précisée
            >>> result = tools.get_news_by_date(
            ...     date_range="hier",
            ...     platforms=['zhihu'],
            ...     limit=20
            ... )
            >>> print(result['total'])
            20
        """
        try:
            # Validation des paramètres - aujourd'hui par défaut
            if date_range is None:
                date_range = "aujourd'hui"

            # Normalise date_range (gère le problème de sérialisation des chaînes JSON)
            date_range = normalize_date_range(date_range)

            # Traite date_range : prend en charge une chaîne ou un objet
            if isinstance(date_range, dict):
                # Objet de plage, prend la date start
                date_str = date_range.get('start', "aujourd'hui")
            else:
                date_str = date_range
            target_date = validate_date_query(date_str)
            platforms = validate_platforms(platforms)
            limit = validate_limit(limit, default=50)

            # Récupère les données
            news_list = self.data_service.get_news_by_date(
                target_date=target_date,
                platforms=platforms,
                limit=limit,
                include_url=include_url
            )

            return {
                "success": True,
                "summary": {
                    "description": f"Actualités interrogées par date ({target_date.strftime('%Y-%m-%d')})",
                    "total": len(news_list),
                    "returned": len(news_list),
                    "date": target_date.strftime("%Y-%m-%d"),
                    "date_range": date_range,
                    "platforms": platforms or "toutes les plateformes"
                },
                "data": news_list
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

    # ========================================
    # Méthodes de requête des données RSS
    # ========================================

    def get_latest_rss(
        self,
        feeds: Optional[List[str]] = None,
        days: int = 1,
        limit: Optional[int] = None,
        include_summary: bool = False
    ) -> Dict:
        """
        Récupère les dernières données RSS (prend en charge la requête sur plusieurs jours)

        Args:
            feeds: liste des ID de sources RSS, par ex. ['hacker-news', '36kr']
            days: récupère les données des N derniers jours, 1 par défaut (aujourd'hui uniquement), 30 maximum
            limit: limite du nombre de résultats, 50 par défaut
            include_summary: indique s'il faut inclure le résumé, False par défaut (économie de tokens)

        Returns:
            dictionnaire de la liste des entrées RSS
        """
        try:
            limit = validate_limit(limit, default=50)

            rss_list = self.data_service.get_latest_rss(
                feeds=feeds,
                days=days,
                limit=limit,
                include_summary=include_summary
            )

            return {
                "success": True,
                "summary": {
                    "description": f"Données d'abonnements RSS des {days} derniers jours" if days > 1 else "Dernières données d'abonnements RSS",
                    "total": len(rss_list),
                    "returned": len(rss_list),
                    "days": days,
                    "feeds": feeds or "toutes les sources d'abonnement"
                },
                "data": rss_list
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

    def search_rss(
        self,
        keyword: str,
        feeds: Optional[List[str]] = None,
        days: int = 7,
        limit: Optional[int] = None,
        include_summary: bool = False
    ) -> Dict:
        """
        Recherche dans les données RSS

        Args:
            keyword: mot-clé de recherche
            feeds: liste des ID de sources RSS
            days: recherche dans les données des N derniers jours, 7 jours par défaut
            limit: limite du nombre de résultats, 50 par défaut
            include_summary: indique s'il faut inclure le résumé

        Returns:
            liste des entrées RSS correspondantes
        """
        try:
            keyword = validate_keyword(keyword)
            limit = validate_limit(limit, default=50)

            if days < 1 or days > 30:
                days = 7

            rss_list = self.data_service.search_rss(
                keyword=keyword,
                feeds=feeds,
                days=days,
                limit=limit,
                include_summary=include_summary
            )

            return {
                "success": True,
                "summary": {
                    "description": f"Résultats de recherche RSS (mot-clé : {keyword})",
                    "total": len(rss_list),
                    "returned": len(rss_list),
                    "keyword": keyword,
                    "feeds": feeds or "toutes les sources d'abonnement",
                    "days": days
                },
                "data": rss_list
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

    def get_rss_feeds_status(self) -> Dict:
        """
        Récupère l'état des sources RSS

        Returns:
            informations sur l'état des sources RSS
        """
        try:
            status = self.data_service.get_rss_feeds_status()

            return {
                **status,
                "success": True
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

