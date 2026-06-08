"""
Outils de recherche intelligente d'actualités

Fournit des fonctions de recherche avancées : recherche floue, requête par lien, recherche d'actualités historiques connexes, etc.
"""

import re
from collections import Counter
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple, Union

from ..services.data_service import DataService
from ..utils.validators import validate_keyword, validate_limit, validate_threshold, normalize_date_range
from ..utils.errors import MCPError, InvalidParameterError, DataNotFoundError


class SearchTools:
    """Classe des outils de recherche intelligente d'actualités"""

    def __init__(self, project_root: str = None):
        """
        Initialise les outils de recherche intelligente

        Args:
            project_root: répertoire racine du projet
        """
        self.data_service = DataService(project_root)

    def search_news_unified(
        self,
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
    ) -> Dict:
        """
        Outil de recherche unifiée d'actualités - regroupe plusieurs modes de recherche, prend en charge la recherche simultanée dans les palmarès et le RSS

        Args:
            query: contenu de la requête (obligatoire) - mot-clé, extrait de contenu ou nom d'entité
            search_mode: mode de recherche, valeurs possibles :
                - "keyword": correspondance exacte par mot-clé (par défaut)
                - "fuzzy": correspondance floue du contenu (utilise un algorithme de similarité)
                - "entity": recherche par nom d'entité (tri automatique par pondération)
            date_range: plage de dates (facultatif)
                       - **format** : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                       - **exemple** : {"start": "2025-01-01", "end": "2025-01-07"}
                       - **par défaut** : si non précisée, interroge aujourd'hui par défaut
                       - **remarque** : start et end peuvent être identiques (recherche sur un seul jour)
            platforms: liste de filtrage des plateformes, par ex. ['zhihu', 'weibo']
            limit: limite du nombre de résultats des palmarès, 50 par défaut
            sort_by: méthode de tri, valeurs possibles :
                - "relevance": tri par pertinence (par défaut)
                - "weight": tri par pondération de l'actualité
                - "date": tri par date
            threshold: seuil de similarité (valable uniquement en mode fuzzy), entre 0 et 1, 0.6 par défaut
            include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)
            include_rss: indique s'il faut aussi rechercher dans les données RSS, False par défaut
            rss_limit: limite du nombre de résultats RSS, 20 par défaut

        Returns:
            dictionnaire des résultats de recherche, contenant la liste des actualités correspondantes (palmarès et RSS affichés séparément)

        Examples:
            - search_news_unified(query="intelligence artificielle", search_mode="keyword")
            - search_news_unified(query="baisse de prix Tesla", search_mode="fuzzy", threshold=0.4)
            - search_news_unified(query="Musk", search_mode="entity", limit=20)
            - search_news_unified(query="AI", include_rss=True)  # Recherche simultanée palmarès et RSS
            - search_news_unified(query="iPhone 16", date_range={"start": "2025-01-01", "end": "2025-01-07"})
        """
        try:
            # Validation des paramètres
            query = validate_keyword(query)

            if search_mode not in ["keyword", "fuzzy", "entity"]:
                raise InvalidParameterError(
                    f"Mode de recherche invalide : {search_mode}",
                    suggestion="Modes pris en charge : keyword, fuzzy, entity"
                )

            if sort_by not in ["relevance", "weight", "date"]:
                raise InvalidParameterError(
                    f"Méthode de tri invalide : {sort_by}",
                    suggestion="Tris pris en charge : relevance, weight, date"
                )

            limit = validate_limit(limit, default=50)
            threshold = validate_threshold(threshold, default=0.6, min_value=0.0, max_value=1.0)

            # Traite la plage de dates
            if date_range:
                from ..utils.validators import validate_date_range
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                # Sans date précisée, utilise la date de données la plus récente disponible (et non datetime.now())
                earliest, latest = self.data_service.get_available_date_range()

                if latest is None:
                    # Aucune donnée disponible
                    return {
                        "success": False,
                        "error": {
                            "code": "NO_DATA_AVAILABLE",
                            "message": "Aucune donnée d'actualités disponible dans le répertoire output",
                            "suggestion": "Veuillez d'abord lancer le collecteur pour générer des données, ou vérifier le répertoire output"
                        }
                    }

                # Utilise la date la plus récente disponible
                start_date = end_date = latest

            # Collecte toutes les actualités correspondantes
            all_matches = []
            current_date = start_date

            while current_date <= end_date:
                try:
                    all_titles, id_to_name, timestamps = self.data_service.parser.read_all_titles_for_date(
                        date=current_date,
                        platform_ids=platforms
                    )

                    # Exécute une logique de recherche différente selon le mode de recherche
                    if search_mode == "keyword":
                        matches = self._search_by_keyword_mode(
                            query, all_titles, id_to_name, current_date, include_url
                        )
                    elif search_mode == "fuzzy":
                        matches = self._search_by_fuzzy_mode(
                            query, all_titles, id_to_name, current_date, threshold, include_url
                        )
                    else:  # entity
                        matches = self._search_by_entity_mode(
                            query, all_titles, id_to_name, current_date, include_url
                        )

                    all_matches.extend(matches)

                except DataNotFoundError:
                    # Aucune donnée pour cette date, on passe au jour suivant
                    pass

                current_date += timedelta(days=1)

            if not all_matches:
                # Récupère la plage de dates disponible pour le message d'erreur
                earliest, latest = self.data_service.get_available_date_range()

                # Détermine la description de la plage temporelle
                if start_date.date() == datetime.now().date() and start_date == end_date:
                    time_desc = "aujourd'hui"
                elif start_date == end_date:
                    time_desc = start_date.strftime("%Y-%m-%d")
                else:
                    time_desc = f"du {start_date.strftime('%Y-%m-%d')} au {end_date.strftime('%Y-%m-%d')}"

                # Construit le message d'erreur
                if earliest and latest:
                    available_desc = f"du {earliest.strftime('%Y-%m-%d')} au {latest.strftime('%Y-%m-%d')}"
                    message = f"Aucune actualité correspondante trouvée (plage interrogée : {time_desc}, données disponibles : {available_desc})"
                else:
                    message = f"Aucune actualité correspondante trouvée ({time_desc})"

                result = {
                    "success": True,
                    "results": [],
                    "total": 0,
                    "query": query,
                    "search_mode": search_mode,
                    "time_range": time_desc,
                    "message": message
                }
                return result

            # Logique de tri unifiée
            if sort_by == "relevance":
                all_matches.sort(key=lambda x: x.get("similarity_score", 1.0), reverse=True)
            elif sort_by == "weight":
                from .analytics import calculate_news_weight
                all_matches.sort(key=lambda x: calculate_news_weight(x), reverse=True)
            elif sort_by == "date":
                all_matches.sort(key=lambda x: x.get("date", ""), reverse=True)

            # Limite le nombre de résultats
            results = all_matches[:limit]

            # Construit la description de la plage temporelle (détermine correctement s'il s'agit d'aujourd'hui)
            if start_date.date() == datetime.now().date() and start_date == end_date:
                time_range_desc = "aujourd'hui"
            elif start_date == end_date:
                time_range_desc = start_date.strftime("%Y-%m-%d")
            else:
                time_range_desc = f"du {start_date.strftime('%Y-%m-%d')} au {end_date.strftime('%Y-%m-%d')}"

            result = {
                "success": True,
                "summary": {
                    "description": f"Résultats de recherche d'actualités (mode {search_mode})",
                    "total_found": len(all_matches),
                    "returned": len(results),
                    "requested_limit": limit,
                    "search_mode": search_mode,
                    "query": query,
                    "platforms": platforms or "toutes les plateformes",
                    "time_range": time_range_desc,
                    "sort_by": sort_by
                },
                "data": results
            }

            if search_mode == "fuzzy":
                result["summary"]["threshold"] = threshold
                if len(all_matches) < limit:
                    result["note"] = f"En mode recherche floue, le seuil de similarité {threshold} n'a trouvé que {len(all_matches)} résultat(s)"

            # Si la recherche RSS est activée, recherche aussi dans les données RSS
            if include_rss:
                rss_results = self._search_rss_by_keyword(
                    query=query,
                    start_date=start_date,
                    end_date=end_date,
                    limit=rss_limit,
                    include_url=include_url
                )
                result["rss"] = rss_results["items"]
                result["rss_total"] = rss_results["total"]
                result["summary"]["include_rss"] = True
                result["summary"]["rss_found"] = rss_results["total"]
                result["summary"]["rss_returned"] = len(rss_results["items"])

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

    def _search_titles(
        self,
        all_titles: Dict,
        id_to_name: Dict,
        current_date: datetime,
        include_url: bool,
        match_func,
    ) -> List[Dict]:
        """
        Méthode générique de recherche dans les titres

        Args:
            all_titles: dictionnaire de tous les titres
            id_to_name: correspondance ID de plateforme -> nom
            current_date: date actuelle
            include_url: indique s'il faut inclure l'URL
            match_func: fonction de correspondance, reçoit (title, info), retourne (is_match, similarity_score) ou None

        Returns:
            liste des actualités correspondantes
        """
        matches = []

        for platform_id, titles in all_titles.items():
            platform_name = id_to_name.get(platform_id, platform_id)

            for title, info in titles.items():
                result = match_func(title, info)
                if result is None:
                    continue

                is_match, similarity = result
                if not is_match:
                    continue

                news_item = {
                    "title": title,
                    "platform": platform_id,
                    "platform_name": platform_name,
                    "date": current_date.strftime("%Y-%m-%d"),
                    "similarity_score": round(similarity, 4),
                    "ranks": info.get("ranks", []),
                    "count": len(info.get("ranks", [])),
                    "rank": info["ranks"][0] if info["ranks"] else 999
                }

                if include_url:
                    news_item["url"] = info.get("url", "")
                    news_item["mobileUrl"] = info.get("mobileUrl", "")

                matches.append(news_item)

        return matches

    def _search_by_keyword_mode(
        self, query: str, all_titles: Dict, id_to_name: Dict,
        current_date: datetime, include_url: bool
    ) -> List[Dict]:
        """Mode de recherche par mot-clé (correspondance exacte)"""
        query_lower = query.lower()
        return self._search_titles(
            all_titles, id_to_name, current_date, include_url,
            match_func=lambda title, info: (True, 1.0) if query_lower in title.lower() else (False, 0),
        )

    def _search_by_fuzzy_mode(
        self, query: str, all_titles: Dict, id_to_name: Dict,
        current_date: datetime, threshold: float, include_url: bool
    ) -> List[Dict]:
        """Mode de recherche floue (utilise un algorithme de similarité)"""
        return self._search_titles(
            all_titles, id_to_name, current_date, include_url,
            match_func=lambda title, info: self._fuzzy_match(query, title, threshold),
        )

    def _search_by_entity_mode(
        self, query: str, all_titles: Dict, id_to_name: Dict,
        current_date: datetime, include_url: bool
    ) -> List[Dict]:
        """Mode de recherche par entité (contient exactement le nom de l'entité)"""
        return self._search_titles(
            all_titles, id_to_name, current_date, include_url,
            match_func=lambda title, info: (True, 1.0) if query in title else (False, 0),
        )

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calcule la similarité entre deux textes

        Args:
            text1: texte 1
            text2: texte 2

        Returns:
            score de similarité (entre 0 et 1)
        """
        # Utilise difflib.SequenceMatcher pour calculer la similarité de séquence
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def _fuzzy_match(self, query: str, text: str, threshold: float = 0.3) -> Tuple[bool, float]:
        """
        Fonction de correspondance floue

        Args:
            query: texte de la requête
            text: texte à comparer
            threshold: seuil de correspondance

        Returns:
            (correspond ou non, score de similarité)
        """
        # Vérification d'inclusion directe
        if query.lower() in text.lower():
            return True, 1.0

        # Calcule la similarité globale
        similarity = self._calculate_similarity(query, text)
        if similarity >= threshold:
            return True, similarity

        # Correspondance partielle après découpage en mots
        query_words = set(self._extract_keywords(query))
        text_words = set(self._extract_keywords(text))

        if not query_words or not text_words:
            return False, 0.0

        # Calcule le taux de recouvrement des mots-clés
        common_words = query_words & text_words
        keyword_overlap = len(common_words) / len(query_words)

        if keyword_overlap >= 0.5:  # 50 % de recouvrement des mots-clés
            return True, keyword_overlap

        return False, similarity

    def _extract_keywords(self, text: str, min_length: int = 2) -> List[str]:
        """
        Extrait les mots-clés d'un texte

        Args:
            text: texte d'entrée
            min_length: longueur minimale des mots

        Returns:
            liste de mots-clés
        """
        # Supprime les URL et les caractères spéciaux
        text = re.sub(r'http[s]?://\S+', '', text)
        text = re.sub(r'\[.*?\]', '', text)  # Supprime le contenu entre crochets

        # Découpe en mots à l'aide d'une expression régulière (CJK et latin)
        words = re.findall(r'[\w]+', text)

        # Filtre les mots courts
        keywords = [word for word in words if word and len(word) >= min_length]

        return keywords

    def _calculate_keyword_overlap(self, keywords1: List[str], keywords2: List[str]) -> float:
        """
        Calcule le taux de recouvrement entre deux listes de mots-clés

        Args:
            keywords1: liste de mots-clés 1
            keywords2: liste de mots-clés 2

        Returns:
            score de recouvrement (entre 0 et 1)
        """
        if not keywords1 or not keywords2:
            return 0.0

        set1 = set(keywords1)
        set2 = set(keywords2)

        # Similarité de Jaccard
        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union

    def _jaccard_similarity(self, list1: List[str], list2: List[str]) -> float:
        """
        Calcule la similarité de Jaccard entre deux listes

        Args:
            list1: liste 1
            list2: liste 2

        Returns:
            similarité de Jaccard (entre 0 et 1)
        """
        if not list1 or not list2:
            return 0.0

        set1 = set(list1)
        set2 = set(list2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union

    def search_related_news_history(
        self,
        reference_title: str,
        time_preset: str = "yesterday",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        threshold: float = 0.4,
        limit: int = 50,
        include_url: bool = False
    ) -> Dict:
        """
        Recherche dans les données historiques les actualités liées à une actualité donnée

        Args:
            reference_title: titre ou contenu de l'actualité de référence
            time_preset: valeur prédéfinie de plage temporelle, au choix :
                - "yesterday": hier
                - "last_week": la semaine dernière (7 jours)
                - "last_month": le mois dernier (30 jours)
                - "custom": plage de dates personnalisée (nécessite start_date et end_date)
            start_date: date de début personnalisée (valable uniquement si time_preset="custom")
            end_date: date de fin personnalisée (valable uniquement si time_preset="custom")
            threshold: seuil de similarité (entre 0 et 1), 0.4 par défaut
            limit: limite du nombre de résultats, 50 par défaut
            include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

        Returns:
            dictionnaire des résultats de recherche, contenant la liste des actualités connexes

        Example:
            >>> tools = SearchTools()
            >>> result = tools.search_related_news_history(
            ...     reference_title="percée technologique en intelligence artificielle",
            ...     time_preset="last_week",
            ...     threshold=0.4,
            ...     limit=50
            ... )
            >>> for news in result['results']:
            ...     print(f"{news['date']}: {news['title']} (similarité : {news['similarity_score']})")
        """
        try:
            # Validation des paramètres
            reference_title = validate_keyword(reference_title)
            threshold = validate_threshold(threshold, default=0.4, min_value=0.0, max_value=1.0)
            limit = validate_limit(limit, default=50)

            # Détermine la plage de dates de la requête
            today = datetime.now()

            if time_preset == "yesterday":
                search_start = today - timedelta(days=1)
                search_end = today - timedelta(days=1)
            elif time_preset == "last_week":
                search_start = today - timedelta(days=7)
                search_end = today - timedelta(days=1)
            elif time_preset == "last_month":
                search_start = today - timedelta(days=30)
                search_end = today - timedelta(days=1)
            elif time_preset == "custom":
                if not start_date or not end_date:
                    raise InvalidParameterError(
                        "Une plage temporelle personnalisée nécessite start_date et end_date",
                        suggestion="Veuillez fournir les paramètres start_date et end_date"
                    )
                search_start = start_date
                search_end = end_date
            else:
                raise InvalidParameterError(
                    f"Plage temporelle non prise en charge : {time_preset}",
                    suggestion="Veuillez utiliser 'yesterday', 'last_week', 'last_month' ou 'custom'"
                )

            # Extrait les mots-clés du texte de référence
            reference_keywords = self._extract_keywords(reference_title)

            if not reference_keywords:
                raise InvalidParameterError(
                    "Impossible d'extraire des mots-clés du texte de référence",
                    suggestion="Veuillez fournir un contenu textuel plus détaillé"
                )

            # Collecte toutes les actualités connexes
            all_related_news = []
            current_date = search_start

            while current_date <= search_end:
                try:
                    # Lit les données de cette date
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(current_date)

                    # Recherche les actualités connexes
                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)

                        for title, info in titles.items():
                            # Calcule la similarité des titres
                            title_similarity = self._calculate_similarity(reference_title, title)

                            # Extrait les mots-clés du titre
                            title_keywords = self._extract_keywords(title)

                            # Calcule le taux de recouvrement des mots-clés
                            keyword_overlap = self._calculate_keyword_overlap(
                                reference_keywords,
                                title_keywords
                            )

                            # Similarité globale (70 % recouvrement des mots-clés + 30 % similarité textuelle)
                            combined_score = keyword_overlap * 0.7 + title_similarity * 0.3

                            if combined_score >= threshold:
                                news_item = {
                                    "title": title,
                                    "platform": platform_id,
                                    "platform_name": platform_name,
                                    "date": current_date.strftime("%Y-%m-%d"),
                                    "similarity_score": round(combined_score, 4),
                                    "keyword_overlap": round(keyword_overlap, 4),
                                    "text_similarity": round(title_similarity, 4),
                                    "common_keywords": list(set(reference_keywords) & set(title_keywords)),
                                    "rank": info["ranks"][0] if info["ranks"] else 0
                                }

                                # Ajoute conditionnellement les champs URL
                                if include_url:
                                    news_item["url"] = info.get("url", "")
                                    news_item["mobileUrl"] = info.get("mobileUrl", "")

                                all_related_news.append(news_item)

                except DataNotFoundError:
                    # Aucune donnée pour cette date, on passe au jour suivant
                    pass
                except Exception as e:
                    # Enregistre l'erreur mais continue avec les autres dates
                    print(f"Warning: erreur lors du traitement de la date {current_date.strftime('%Y-%m-%d')} : {e}")

                # Passe au jour suivant
                current_date += timedelta(days=1)

            if not all_related_news:
                return {
                    "success": True,
                    "results": [],
                    "total": 0,
                    "query": reference_title,
                    "time_preset": time_preset,
                    "date_range": {
                        "start": search_start.strftime("%Y-%m-%d"),
                        "end": search_end.strftime("%Y-%m-%d")
                    },
                    "message": "Aucune actualité connexe trouvée"
                }

            # Trie par similarité
            all_related_news.sort(key=lambda x: x["similarity_score"], reverse=True)

            # Limite le nombre de résultats
            results = all_related_news[:limit]

            # Statistiques
            platform_distribution = Counter([news["platform"] for news in all_related_news])
            date_distribution = Counter([news["date"] for news in all_related_news])

            result = {
                "success": True,
                "summary": {
                    "description": "Résultats de recherche d'actualités historiques connexes",
                    "total_found": len(all_related_news),
                    "returned": len(results),
                    "requested_limit": limit,
                    "threshold": threshold,
                    "reference_title": reference_title,
                    "reference_keywords": reference_keywords,
                    "time_preset": time_preset,
                    "date_range": {
                        "start": search_start.strftime("%Y-%m-%d"),
                        "end": search_end.strftime("%Y-%m-%d")
                    }
                },
                "data": results,
                "statistics": {
                    "platform_distribution": dict(platform_distribution),
                    "date_distribution": dict(date_distribution),
                    "avg_similarity": round(
                        sum([news["similarity_score"] for news in all_related_news]) / len(all_related_news),
                        4
                    ) if all_related_news else 0.0
                }
            }

            if len(all_related_news) < limit:
                result["note"] = f"Avec le seuil de pertinence {threshold}, seules {len(all_related_news)} actualité(s) connexe(s) ont été trouvées"

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

    def find_related_news_unified(
        self,
        reference_title: str,
        date_range: Optional[Union[Dict[str, str], str]] = None,
        threshold: float = 0.5,
        limit: int = 50,
        include_url: bool = False
    ) -> Dict:
        """
        Outil unifié de recherche d'actualités connexes - regroupe la recherche d'actualités similaires et la recherche historique connexe

        Args:
            reference_title: titre de l'actualité de référence
            date_range: plage de dates (facultatif)
                - non précisée : interroge uniquement les données d'aujourd'hui
                - {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} : interroge la plage de dates indiquée
                - "today": aujourd'hui
                - "yesterday": hier
                - "last_week": les 7 derniers jours
                - "last_month": les 30 derniers jours
            threshold: seuil de similarité, entre 0 et 1, 0.5 par défaut
            limit: limite du nombre de résultats, 50 par défaut
            include_url: indique s'il faut inclure les liens URL, False par défaut

        Returns:
            liste des actualités connexes, triée par similarité
        """
        try:
            # Validation des paramètres
            reference_title = validate_keyword(reference_title)
            threshold = validate_threshold(threshold, default=0.5, min_value=0.0, max_value=1.0)
            limit = validate_limit(limit, default=50)

            # Détermine la plage de dates
            today = datetime.now()

            # Normalise date_range (gère le problème de sérialisation des chaînes JSON)
            date_range = normalize_date_range(date_range)

            if date_range is None or date_range == "today":
                # Interroge uniquement aujourd'hui
                search_dates = [today]
            elif isinstance(date_range, str):
                # Plage temporelle prédéfinie
                if date_range == "yesterday":
                    search_dates = [today - timedelta(days=1)]
                elif date_range == "last_week":
                    search_dates = [today - timedelta(days=i) for i in range(7)]
                elif date_range == "last_month":
                    search_dates = [today - timedelta(days=i) for i in range(30)]
                else:
                    # Format chaîne d'un seul jour
                    try:
                        single_date = datetime.strptime(date_range, "%Y-%m-%d")
                        search_dates = [single_date]
                    except ValueError:
                        search_dates = [today]
            elif isinstance(date_range, dict):
                # Objet de plage de dates
                start_str = date_range.get("start")
                end_str = date_range.get("end")
                if start_str and end_str:
                    start_date = datetime.strptime(start_str, "%Y-%m-%d")
                    end_date = datetime.strptime(end_str, "%Y-%m-%d")
                    search_dates = []
                    current = start_date
                    while current <= end_date:
                        search_dates.append(current)
                        current += timedelta(days=1)
                else:
                    search_dates = [today]
            else:
                search_dates = [today]

            # Extrait les mots-clés du titre de référence
            reference_keywords = self._extract_keywords(reference_title)

            # Collecte toutes les actualités connexes
            all_related_news = []

            for search_date in search_dates:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(search_date)

                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)

                        for title, info in titles.items():
                            if title == reference_title:
                                continue

                            # Calcule la similarité (utilise un algorithme hybride)
                            text_similarity = self._calculate_similarity(reference_title, title)

                            # S'il y a des mots-clés, calcule aussi le taux de recouvrement
                            if reference_keywords:
                                title_keywords = self._extract_keywords(title)
                                keyword_similarity = self._jaccard_similarity(reference_keywords, title_keywords)
                                # Similarité hybride : 70 % texte + 30 % mots-clés
                                similarity = 0.7 * text_similarity + 0.3 * keyword_similarity
                            else:
                                similarity = text_similarity
                            
                            if similarity >= threshold:
                                news_item = {
                                    "title": title,
                                    "platform": platform_id,
                                    "platform_name": platform_name,
                                    "date": search_date.strftime("%Y-%m-%d"),
                                    "similarity": round(similarity, 3),
                                    "rank": info["ranks"][0] if info["ranks"] else 0
                                }
                                
                                if include_url:
                                    news_item["url"] = info.get("url", "")
                                
                                all_related_news.append(news_item)

                except (OSError, KeyError, TypeError, ValueError):
                    # Échec de lecture des données d'un jour, on ignore
                    continue

            # Trie par similarité
            all_related_news.sort(key=lambda x: x["similarity"], reverse=True)

            # Limite le nombre de résultats
            results = all_related_news[:limit]

            # Statistiques
            from collections import Counter
            platform_dist = Counter([n["platform_name"] for n in all_related_news])
            date_dist = Counter([n["date"] for n in all_related_news])

            return {
                "success": True,
                "summary": {
                    "description": "Résultats de recherche d'actualités connexes",
                    "total_found": len(all_related_news),
                    "returned": len(results),
                    "reference_title": reference_title,
                    "threshold": threshold,
                    "date_range": {
                        "start": min(search_dates).strftime("%Y-%m-%d"),
                        "end": max(search_dates).strftime("%Y-%m-%d")
                    } if search_dates else None
                },
                "data": results,
                "statistics": {
                    "platform_distribution": dict(platform_dist),
                    "date_distribution": dict(date_dist)
                }
            }

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def _search_rss_by_keyword(
        self,
        query: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 20,
        include_url: bool = False
    ) -> Dict:
        """
        Recherche un mot-clé dans les données RSS

        Args:
            query: mot-clé de recherche
            start_date: date de début
            end_date: date de fin
            limit: limite du nombre de résultats
            include_url: indique s'il faut inclure l'URL

        Returns:
            dictionnaire des résultats de recherche RSS
        """
        all_rss_matches = []
        query_lower = query.lower()
        current_date = start_date

        while current_date <= end_date:
            try:
                # Lit les données RSS de cette date
                all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(
                    date=current_date,
                    platform_ids=None,
                    db_type="rss"
                )

                for feed_id, items in all_titles.items():
                    feed_name = id_to_name.get(feed_id, feed_id)

                    for title, info in items.items():
                        # Correspondance du mot-clé (titre ou résumé)
                        title_match = query_lower in title.lower()
                        summary = info.get("summary", "")
                        summary_match = query_lower in summary.lower() if summary else False

                        if title_match or summary_match:
                            rss_item = {
                                "title": title,
                                "feed_id": feed_id,
                                "feed_name": feed_name,
                                "date": current_date.strftime("%Y-%m-%d"),
                                "published_at": info.get("published_at", ""),
                                "author": info.get("author", ""),
                                "match_in": "title" if title_match else "summary"
                            }

                            if include_url:
                                rss_item["url"] = info.get("url", "")

                            all_rss_matches.append(rss_item)

            except DataNotFoundError:
                # Aucune donnée RSS pour cette date, on passe au jour suivant
                pass
            except (OSError, KeyError, TypeError, ValueError):
                # Autre erreur, on ignore
                pass

            current_date += timedelta(days=1)

        # Trie par date de publication (les plus récents en premier)
        all_rss_matches.sort(key=lambda x: x.get("published_at", ""), reverse=True)

        return {
            "items": all_rss_matches[:limit],
            "total": len(all_rss_matches)
        }
