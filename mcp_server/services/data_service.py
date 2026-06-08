"""
Service d'accès aux données

Fournit une interface unifiée de requête des données et encapsule la logique d'accès aux données.
"""

import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .cache_service import get_cache
from .parser_service import ParserService
from ..utils.errors import DataNotFoundError


class DataService:
    """Classe du service d'accès aux données"""

    # Liste des mots vides en français (utilisée pour le mode auto_extract)
    STOPWORDS = {
        'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'mais',
        'donc', 'or', 'ni', 'car', 'que', 'qui', 'quoi', 'dont', 'où', 'a',
        'au', 'aux', 'ce', 'ces', 'cet', 'cette', 'son', 'sa', 'ses', 'leur',
        'leurs', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes', 'notre', 'nos', 'votre',
        'vos', 'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles',
        'me', 'te', 'se', 'lui', 'en', 'y', 'dans', 'sur', 'sous', 'avec',
        'sans', 'pour', 'par', 'vers', 'chez', 'entre', 'pendant', 'avant',
        'apres', 'depuis', 'plus', 'moins', 'tres', 'trop', 'tout', 'tous',
        'toute', 'toutes', 'meme', 'aussi', 'encore', 'deja', 'puis', 'alors',
        'ainsi', 'comme', 'comment', 'pourquoi', 'quand', 'combien', 'est',
        'sont', 'etre', 'avoir', 'fait', 'faire', 'dit', 'dire', 'peut',
        'pouvoir', 'doit', 'devoir', 'selon', 'face', 'apres', 'cela', 'ceci'
    }

    def __init__(self, project_root: str = None):
        """
        Initialise le service de données

        Args:
            project_root: répertoire racine du projet
        """
        self.parser = ParserService(project_root)
        self.cache = get_cache()

    def get_latest_news(
        self,
        platforms: Optional[List[str]] = None,
        limit: int = 50,
        include_url: bool = False
    ) -> List[Dict]:
        """
        Récupère le dernier lot de données d'actualités collectées

        Args:
            platforms: liste des ID de plateformes, None signifie toutes les plateformes
            limit: limite du nombre de résultats
            include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

        Returns:
            liste d'actualités

        Raises:
            DataNotFoundError: données inexistantes
        """
        # Essaie de récupérer depuis le cache
        cache_key = f"latest_news:{','.join(platforms or [])}:{limit}:{include_url}"
        cached = self.cache.get(cache_key, ttl=900)  # Cache de 15 minutes
        if cached:
            return cached

        # Lit les données d'aujourd'hui
        all_titles, id_to_name, timestamps = self.parser.read_all_titles_for_date(
            date=None,
            platform_ids=platforms
        )

        # Récupère l'heure du fichier le plus récent
        if timestamps:
            latest_timestamp = max(timestamps.values())
            fetch_time = datetime.fromtimestamp(latest_timestamp)
        else:
            fetch_time = datetime.now()

        # Convertit en liste d'actualités
        news_list = []
        for platform_id, titles in all_titles.items():
            platform_name = id_to_name.get(platform_id, platform_id)

            for title, info in titles.items():
                # Prend le premier classement
                rank = info["ranks"][0] if info["ranks"] else 0

                news_item = {
                    "title": title,
                    "platform": platform_id,
                    "platform_name": platform_name,
                    "rank": rank,
                    "timestamp": fetch_time.strftime("%Y-%m-%d %H:%M:%S")
                }

                # Ajoute conditionnellement les champs URL
                if include_url:
                    news_item["url"] = info.get("url", "")
                    news_item["mobileUrl"] = info.get("mobileUrl", "")

                news_list.append(news_item)

        # Trie par classement
        news_list.sort(key=lambda x: x["rank"])

        # Limite le nombre de résultats
        result = news_list[:limit]

        # Met le résultat en cache
        self.cache.set(cache_key, result)

        return result

    def get_news_by_date(
        self,
        target_date: datetime,
        platforms: Optional[List[str]] = None,
        limit: int = 50,
        include_url: bool = False
    ) -> List[Dict]:
        """
        Récupère les actualités pour une date donnée

        Args:
            target_date: date cible
            platforms: liste des ID de plateformes, None signifie toutes les plateformes
            limit: limite du nombre de résultats
            include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

        Returns:
            liste d'actualités

        Raises:
            DataNotFoundError: données inexistantes

        Examples:
            >>> service = DataService()
            >>> news = service.get_news_by_date(
            ...     target_date=datetime(2025, 10, 10),
            ...     platforms=['zhihu'],
            ...     limit=20
            ... )
        """
        # Essaie de récupérer depuis le cache
        date_str = target_date.strftime("%Y-%m-%d")
        cache_key = f"news_by_date:{date_str}:{','.join(platforms or [])}:{limit}:{include_url}"
        cached = self.cache.get(cache_key, ttl=900)  # Cache de 15 minutes
        if cached:
            return cached

        # Lit les données de la date indiquée
        all_titles, id_to_name, timestamps = self.parser.read_all_titles_for_date(
            date=target_date,
            platform_ids=platforms
        )

        # Convertit en liste d'actualités
        news_list = []
        for platform_id, titles in all_titles.items():
            platform_name = id_to_name.get(platform_id, platform_id)

            for title, info in titles.items():
                # Calcule le classement moyen
                avg_rank = sum(info["ranks"]) / len(info["ranks"]) if info["ranks"] else 0

                news_item = {
                    "title": title,
                    "platform": platform_id,
                    "platform_name": platform_name,
                    "rank": info["ranks"][0] if info["ranks"] else 0,
                    "avg_rank": round(avg_rank, 2),
                    "count": len(info["ranks"]),
                    "date": date_str
                }

                # Ajoute conditionnellement les champs URL
                if include_url:
                    news_item["url"] = info.get("url", "")
                    news_item["mobileUrl"] = info.get("mobileUrl", "")

                news_list.append(news_item)

        # Trie par classement
        news_list.sort(key=lambda x: x["rank"])

        # Limite le nombre de résultats
        result = news_list[:limit]

        # Met le résultat en cache (les données historiques restent en cache plus longtemps)
        self.cache.set(cache_key, result)

        return result

    def search_news_by_keyword(
        self,
        keyword: str,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Dict:
        """
        Recherche des actualités par mot-clé

        Args:
            keyword: mot-clé de recherche
            date_range: plage de dates (start_date, end_date)
            platforms: liste de filtrage des plateformes
            limit: limite du nombre de résultats (facultatif)

        Returns:
            dictionnaire des résultats de recherche

        Raises:
            DataNotFoundError: données inexistantes
        """
        # Détermine la plage de dates de recherche
        if date_range:
            start_date, end_date = date_range
        else:
            # Par défaut, recherche aujourd'hui
            start_date = end_date = datetime.now()

        # Collecte toutes les actualités correspondantes
        results = []
        platform_distribution = Counter()

        # Parcourt la plage de dates
        current_date = start_date
        while current_date <= end_date:
            try:
                all_titles, id_to_name, _ = self.parser.read_all_titles_for_date(
                    date=current_date,
                    platform_ids=platforms
                )

                # Recherche les titres contenant le mot-clé
                for platform_id, titles in all_titles.items():
                    platform_name = id_to_name.get(platform_id, platform_id)

                    for title, info in titles.items():
                        if keyword.lower() in title.lower():
                            # Calcule le classement moyen
                            avg_rank = sum(info["ranks"]) / len(info["ranks"]) if info["ranks"] else 0

                            results.append({
                                "title": title,
                                "platform": platform_id,
                                "platform_name": platform_name,
                                "ranks": info["ranks"],
                                "count": len(info["ranks"]),
                                "avg_rank": round(avg_rank, 2),
                                "url": info.get("url", ""),
                                "mobileUrl": info.get("mobileUrl", ""),
                                "date": current_date.strftime("%Y-%m-%d")
                            })

                            platform_distribution[platform_id] += 1

            except DataNotFoundError:
                # Aucune donnée pour cette date, on passe au jour suivant
                pass

            # Jour suivant
            current_date += timedelta(days=1)

        if not results:
            raise DataNotFoundError(
                f"Aucune actualité contenant le mot-clé '{keyword}' n'a été trouvée",
                suggestion="Veuillez essayer un autre mot-clé ou élargir la plage de dates"
            )

        # Calcule les statistiques
        total_ranks = []
        for item in results:
            total_ranks.extend(item["ranks"])

        avg_rank = sum(total_ranks) / len(total_ranks) if total_ranks else 0

        # Limite le nombre de résultats (si spécifié)
        total_found = len(results)
        if limit is not None and limit > 0:
            results = results[:limit]

        return {
            "results": results,
            "total": len(results),
            "total_found": total_found,
            "statistics": {
                "platform_distribution": dict(platform_distribution),
                "avg_rank": round(avg_rank, 2),
                "keyword": keyword
            }
        }

    def _extract_words_from_title(self, title: str, min_length: int = 2) -> List[str]:
        """
        Extrait les mots significatifs d'un titre (utilisé pour le mode auto_extract)

        Args:
            title: titre de l'actualité
            min_length: longueur minimale des mots

        Returns:
            liste de mots-clés
        """
        # Supprime les URL et les caractères spéciaux
        title = re.sub(r'http[s]?://\S+', '', title)
        title = re.sub(r'\[.*?\]', '', title)  # Supprime le contenu entre crochets
        title = re.sub(r'[【】《》「」『』""''・·•]', '', title)  # Supprime la ponctuation CJK

        # Découpe en mots à l'aide d'une expression régulière (CJK et latin)
        # Correspond aux suites de caractères CJK ou aux mots latins
        words = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}[a-zA-Z0-9]*', title)

        # Filtre les mots vides et les mots courts
        keywords = [
            word for word in words
            if word and len(word) >= min_length and word.lower() not in self.STOPWORDS
            and word not in self.STOPWORDS
        ]

        return keywords

    def get_trending_topics(
        self,
        top_n: int = 10,
        mode: str = "current",
        extract_mode: str = "keywords"
    ) -> Dict:
        """
        Récupère les statistiques des sujets tendances

        Args:
            top_n: retourne les TOP N sujets
            mode: mode temporel
                - "daily": statistiques cumulées de la journée
                - "current": statistiques du dernier lot de données (par défaut)
            extract_mode: mode d'extraction
                - "keywords": comptabilise les mots-clés prédéfinis (basé sur config/frequency_words.txt)
                - "auto_extract": extrait automatiquement les mots de fréquence des titres d'actualités

        Returns:
            dictionnaire des statistiques de fréquence des sujets

        Raises:
            DataNotFoundError: données inexistantes
        """
        # Essaie de récupérer depuis le cache
        cache_key = f"trending_topics:{top_n}:{mode}:{extract_mode}"
        cached = self.cache.get(cache_key, ttl=900)  # Cache de 15 minutes
        if cached:
            return cached

        # Lit les données d'aujourd'hui
        all_titles, id_to_name, timestamps = self.parser.read_all_titles_for_date()

        if not all_titles:
            raise DataNotFoundError(
                "Aucune donnée d'actualités trouvée pour aujourd'hui",
                suggestion="Veuillez vous assurer que le collecteur a été exécuté et a généré des données"
            )

        # Sélectionne les données de titres à traiter selon mode
        if mode == "daily":
            titles_to_process = all_titles
        elif mode == "current":
            titles_to_process = all_titles  # Implémentation simplifiée
        else:
            raise ValueError(f"Mode non pris en charge : {mode}. Modes pris en charge : daily, current")

        # Comptabilise la fréquence des mots
        word_frequency = Counter()
        keyword_to_news = {}

        # Précharge les données de mots-clés (évite les appels répétés dans la boucle)
        if extract_mode == "keywords":
            from trendradar.core.frequency import _word_matches
            word_groups = self.parser.parse_frequency_words()

        # Parcourt les titres à traiter
        for platform_id, titles in titles_to_process.items():
            for title in titles.keys():
                if extract_mode == "keywords":
                    # Comptabilisation basée sur les mots-clés prédéfinis (prend en charge la correspondance regex)
                    title_lower = title.lower()

                    for group in word_groups:
                        all_words = group.get("required", []) + group.get("normal", [])
                        # Vérifie la correspondance avec l'un des mots du groupe
                        matched = any(_word_matches(word_config, title_lower) for word_config in all_words)

                        if matched:
                            # Utilise le display_name du groupe (alias de groupe ou concaténation des alias de ligne)
                            display_key = group.get("display_name") or group.get("group_key", "")

                            word_frequency[display_key] += 1
                            if display_key not in keyword_to_news:
                                keyword_to_news[display_key] = []
                            keyword_to_news[display_key].append(title)
                            break  # Chaque titre n'est compté que pour le premier groupe de mots correspondant

                elif extract_mode == "auto_extract":
                    # Extraction automatique des mots-clés
                    extracted_words = self._extract_words_from_title(title)
                    for word in extracted_words:
                        word_frequency[word] += 1
                        if word not in keyword_to_news:
                            keyword_to_news[word] = []
                        keyword_to_news[word].append(title)

        # Récupère les TOP N mots-clés
        top_keywords = word_frequency.most_common(top_n)

        # Construit la liste des sujets
        topics = []
        for keyword, frequency in top_keywords:
            matched_news = keyword_to_news.get(keyword, [])

            topics.append({
                "keyword": keyword,
                "frequency": frequency,
                "matched_news": len(set(matched_news)),  # Nombre d'actualités après déduplication
                "trend": "stable",
                "weight_score": 0.0
            })

        # Construit le résultat
        result = {
            "topics": topics,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "extract_mode": extract_mode,
            "total_keywords": len(word_frequency),
            "description": self._get_mode_description(mode, extract_mode)
        }

        # Met le résultat en cache
        self.cache.set(cache_key, result)

        return result

    def _get_mode_description(self, mode: str, extract_mode: str = "keywords") -> str:
        """Récupère la description du mode"""
        mode_desc = {
            "daily": "statistiques cumulées de la journée",
            "current": "statistiques du dernier lot"
        }.get(mode, "mode temporel inconnu")

        extract_desc = {
            "keywords": "basé sur les mots-clés prédéfinis",
            "auto_extract": "extraction automatique des mots de fréquence"
        }.get(extract_mode, "mode d'extraction inconnu")

        return f"{mode_desc} - {extract_desc}"

    def get_current_config(self, section: str = "all") -> Dict:
        """
        Récupère la configuration actuelle du système

        Args:
            section: section de configuration - all/crawler/push/keywords/weights

        Returns:
            dictionnaire de configuration

        Raises:
            FileParseError: erreur d'analyse du fichier de configuration
        """
        # Analyse le fichier de configuration
        config_data = self.parser.parse_yaml_config()
        word_groups = self.parser.parse_frequency_words()

        # Retourne la configuration correspondante selon section
        advanced = config_data.get("advanced", {})
        advanced_crawler = advanced.get("crawler", {})
        platforms_config = config_data.get("platforms", {})

        if section == "all" or section == "crawler":
            crawler_config = {
                "enable_crawler": platforms_config.get("enabled", True),
                "use_proxy": advanced_crawler.get("use_proxy", False),
                "request_interval": advanced_crawler.get("request_interval", 1),
                "retry_times": 3,
                "platforms": [p["id"] for p in platforms_config.get("sources", []) if p.get("enabled", True)]
            }

        if section == "all" or section == "push":
            notification = config_data.get("notification", {})
            batch_size = advanced.get("batch_size", {})
            push_config = {
                "enable_notification": notification.get("enabled", True),
                "enabled_channels": [],
                "message_batch_size": batch_size.get("default", 4000),
                "push_window": {}  # Migré vers le système de planification (schedule + timeline.yaml)
            }

            # Détecte les canaux de notification configurés (fusion de config.yaml + .env)
            from trendradar.core.loader import _load_webhook_config

            webhook_config = _load_webhook_config(config_data)

            channel_checks = {
                "feishu": [webhook_config.get("FEISHU_WEBHOOK_URL")],
                "dingtalk": [webhook_config.get("DINGTALK_WEBHOOK_URL")],
                "wework": [webhook_config.get("WEWORK_WEBHOOK_URL")],
                "telegram": [webhook_config.get("TELEGRAM_BOT_TOKEN"), webhook_config.get("TELEGRAM_CHAT_ID")],
                "email": [webhook_config.get("EMAIL_FROM"), webhook_config.get("EMAIL_PASSWORD"), webhook_config.get("EMAIL_TO")],
                "ntfy": [webhook_config.get("NTFY_SERVER_URL"), webhook_config.get("NTFY_TOPIC")],
                "bark": [webhook_config.get("BARK_URL")],
                "slack": [webhook_config.get("SLACK_WEBHOOK_URL")],
                "generic_webhook": [webhook_config.get("GENERIC_WEBHOOK_URL")],
            }
            for ch_id, required_values in channel_checks.items():
                if all(required_values):
                    push_config["enabled_channels"].append(ch_id)

        if section == "all" or section == "keywords":
            keywords_config = {
                "word_groups": word_groups,
                "total_groups": len(word_groups)
            }

        if section == "all" or section == "weights":
            weight = advanced.get("weight", {})
            weights_config = {
                "rank_weight": weight.get("rank", 0.6),
                "frequency_weight": weight.get("frequency", 0.3),
                "hotness_weight": weight.get("hotness", 0.1)
            }

        # Assemble le résultat
        if section == "all":
            result = {
                "crawler": crawler_config,
                "push": push_config,
                "keywords": keywords_config,
                "weights": weights_config
            }
        elif section == "crawler":
            result = crawler_config
        elif section == "push":
            result = push_config
        elif section == "keywords":
            result = keywords_config
        elif section == "weights":
            result = weights_config
        else:
            result = {}

        return result

    def get_available_date_range(self, db_type: str = "news") -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Parcourt le répertoire output et retourne la plage de dates réellement disponible

        Args:
            db_type: type de base de données ("news" ou "rss")

        Returns:
            tuple (date la plus ancienne, date la plus récente), ou (None, None) s'il n'y a pas de données

        Examples:
            >>> service = DataService()
            >>> earliest, latest = service.get_available_date_range()
            >>> print(f"Plage de dates disponible : {earliest} à {latest}")
        """
        return self.parser.get_available_date_range(db_type)

    def get_system_status(self) -> Dict:
        """
        Récupère l'état de fonctionnement du système

        Returns:
            dictionnaire de l'état du système
        """
        # Récupère les statistiques des données
        output_dir = self.parser.project_root / "output"

        total_storage = 0

        # Utilise la méthode du parser pour récupérer la plage de dates
        oldest_record, latest_record = self.get_available_date_range(db_type="news")

        # Calcule la taille totale de stockage du répertoire output
        if output_dir.exists():
            for item in output_dir.rglob("*"):
                if item.is_file():
                    total_storage += item.stat().st_size

        # Lit les informations de version
        version_file = self.parser.project_root / "version"
        version = "unknown"
        if version_file.exists():
            try:
                with open(version_file, "r") as f:
                    version = f.read().strip()
            except (OSError, ValueError):
                pass

        return {
            "system": {
                "version": version,
                "project_root": str(self.parser.project_root)
            },
            "data": {
                "total_storage": f"{total_storage / 1024 / 1024:.2f} MB",
                "oldest_record": oldest_record.strftime("%Y-%m-%d") if oldest_record else None,
                "latest_record": latest_record.strftime("%Y-%m-%d") if latest_record else None,
            },
            "cache": self.cache.get_stats(),
            "health": "healthy"
        }

    # ========================================
    # Méthodes de requête des données RSS
    # ========================================

    def get_latest_rss(
        self,
        feeds: Optional[List[str]] = None,
        days: int = 1,
        limit: int = 50,
        include_summary: bool = False
    ) -> List[Dict]:
        """
        Récupère les dernières données RSS (prend en charge la requête sur plusieurs jours)

        Args:
            feeds: liste des ID de sources RSS, None signifie toutes les sources
            days: récupère les données des N derniers jours, 1 par défaut (aujourd'hui uniquement), 30 maximum
            limit: limite du nombre de résultats
            include_summary: indique s'il faut inclure le résumé, False par défaut (économie de tokens)

        Returns:
            liste des entrées RSS (dédupliquées par URL)

        Raises:
            DataNotFoundError: données inexistantes
        """
        days = min(max(days, 1), 30)  # Limite à 1-30 jours
        cache_key = f"latest_rss:{','.join(feeds or [])}:{days}:{limit}:{include_summary}"
        cached = self.cache.get(cache_key, ttl=900)
        if cached:
            return cached

        rss_list = []
        seen_urls = set()  # Déduplication des URL entre les dates
        today = datetime.now()

        for i in range(days):
            target_date = today - timedelta(days=i)

            try:
                all_items, id_to_name, timestamps = self.parser.read_all_titles_for_date(
                    date=target_date,
                    platform_ids=feeds,
                    db_type="rss"
                )

                # Récupère l'heure de collecte
                if timestamps:
                    latest_timestamp = max(timestamps.values())
                    fetch_time = datetime.fromtimestamp(latest_timestamp)
                else:
                    fetch_time = target_date

                # Convertit en liste
                for feed_id, items in all_items.items():
                    feed_name = id_to_name.get(feed_id, feed_id)

                    for title, info in items.items():
                        # Déduplication des URL entre les dates
                        url = info.get("url", "")
                        if url and url in seen_urls:
                            continue
                        if url:
                            seen_urls.add(url)

                        rss_item = {
                            "title": title,
                            "feed_id": feed_id,
                            "feed_name": feed_name,
                            "url": url,
                            "published_at": info.get("published_at", ""),
                            "author": info.get("author", ""),
                            "date": target_date.strftime("%Y-%m-%d"),
                            "fetch_time": fetch_time.strftime("%Y-%m-%d %H:%M:%S") if isinstance(fetch_time, datetime) else target_date.strftime("%Y-%m-%d")
                        }

                        if include_summary:
                            rss_item["summary"] = info.get("summary", "")

                        rss_list.append(rss_item)

            except DataNotFoundError:
                continue

        # Trie par date de publication (les plus récents en premier)
        rss_list.sort(key=lambda x: x.get("published_at", ""), reverse=True)

        # Limite le nombre de résultats
        result = rss_list[:limit]

        # Met le résultat en cache
        self.cache.set(cache_key, result)

        return result

    def search_rss(
        self,
        keyword: str,
        feeds: Optional[List[str]] = None,
        days: int = 7,
        limit: int = 50,
        include_summary: bool = False
    ) -> List[Dict]:
        """
        Recherche dans les données RSS (déduplication automatique entre les dates)

        Args:
            keyword: mot-clé de recherche
            feeds: liste des ID de sources RSS, None signifie toutes les sources
            days: recherche dans les données des N derniers jours
            limit: limite du nombre de résultats
            include_summary: indique s'il faut inclure le résumé

        Returns:
            liste des entrées RSS correspondantes (dédupliquées par URL)
        """
        cache_key = f"search_rss:{keyword}:{','.join(feeds or [])}:{days}:{limit}:{include_summary}"
        cached = self.cache.get(cache_key, ttl=900)
        if cached:
            return cached

        results = []
        seen_urls = set()  # Pour la déduplication des URL
        today = datetime.now()

        for i in range(days):
            target_date = today - timedelta(days=i)

            try:
                all_items, id_to_name, _ = self.parser.read_all_titles_for_date(
                    date=target_date,
                    platform_ids=feeds,
                    db_type="rss"
                )

                for feed_id, items in all_items.items():
                    feed_name = id_to_name.get(feed_id, feed_id)

                    for title, info in items.items():
                        # Déduplication entre les dates : on ignore si l'URL est déjà apparue
                        url = info.get("url", "")
                        if url and url in seen_urls:
                            continue
                        if url:
                            seen_urls.add(url)

                        # Correspondance du mot-clé (titre ou résumé)
                        summary = info.get("summary", "")
                        if keyword.lower() in title.lower() or keyword.lower() in summary.lower():
                            rss_item = {
                                "title": title,
                                "feed_id": feed_id,
                                "feed_name": feed_name,
                                "url": url,
                                "published_at": info.get("published_at", ""),
                                "author": info.get("author", ""),
                                "date": target_date.strftime("%Y-%m-%d")
                            }

                            if include_summary:
                                rss_item["summary"] = summary

                            results.append(rss_item)

            except DataNotFoundError:
                continue

        # Trie par date de publication
        results.sort(key=lambda x: x.get("published_at", ""), reverse=True)

        # Limite le nombre de résultats
        result = results[:limit]

        # Met le résultat en cache
        self.cache.set(cache_key, result)

        return result

    def get_rss_feeds_status(self) -> Dict:
        """
        Récupère l'état des sources RSS

        Returns:
            informations sur l'état des sources RSS
        """
        cache_key = "rss_feeds_status"
        cached = self.cache.get(cache_key, ttl=900)
        if cached:
            return cached

        # Récupère les dates RSS disponibles
        available_dates = self.parser.get_available_dates(db_type="rss")

        # Récupère les statistiques des données RSS d'aujourd'hui
        today_stats = {}
        try:
            all_items, id_to_name, _ = self.parser.read_all_titles_for_date(
                date=None,
                platform_ids=None,
                db_type="rss"
            )

            for feed_id, items in all_items.items():
                today_stats[feed_id] = {
                    "name": id_to_name.get(feed_id, feed_id),
                    "item_count": len(items)
                }

        except DataNotFoundError:
            pass

        result = {
            "available_dates": available_dates[:10],  # 10 derniers jours
            "total_dates": len(available_dates),
            "today_feeds": today_stats,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        self.cache.set(cache_key, result)

        return result
