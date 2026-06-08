# coding=utf-8
"""
Classe de base abstraite des backends de stockage et modèles de données

Définit une interface de stockage uniforme : tous les backends de stockage doivent implémenter ces méthodes
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set


@dataclass
class NewsItem:
    """Modèle de données d'une entrée d'actualité (données de tendances)"""

    title: str                          # Titre de l'actualité
    source_id: str                      # ID de la plateforme source (par ex. toutiao, baidu)
    source_name: str = ""               # Nom de la plateforme source (utilisé à l'exécution, non stocké en base)
    rank: int = 0                       # Classement
    url: str = ""                       # Lien URL
    mobile_url: str = ""                # URL mobile
    crawl_time: str = ""                # Heure de collecte (format HH:MM)

    # Informations statistiques (utilisées pour l'analyse)
    ranks: List[int] = field(default_factory=list)  # Liste des classements historiques
    first_time: str = ""                # Heure de première apparition
    last_time: str = ""                 # Heure de dernière apparition
    count: int = 1                      # Nombre d'apparitions
    rank_timeline: List[Dict[str, Any]] = field(default_factory=list)  # Chronologie complète des classements
                                        # format: [{"time": "09:30", "rank": 1}, {"time": "10:00", "rank": 2}, ...]
                                        # None indique une sortie du classement: [{"time": "11:00", "rank": None}]

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "title": self.title,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "rank": self.rank,
            "url": self.url,
            "mobile_url": self.mobile_url,
            "crawl_time": self.crawl_time,
            "ranks": self.ranks,
            "first_time": self.first_time,
            "last_time": self.last_time,
            "count": self.count,
            "rank_timeline": self.rank_timeline,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NewsItem":
        """Crée à partir d'un dictionnaire"""
        return cls(
            title=data.get("title", ""),
            source_id=data.get("source_id", ""),
            source_name=data.get("source_name", ""),
            rank=data.get("rank", 0),
            url=data.get("url", ""),
            mobile_url=data.get("mobile_url", ""),
            crawl_time=data.get("crawl_time", ""),
            ranks=data.get("ranks", []),
            first_time=data.get("first_time", ""),
            last_time=data.get("last_time", ""),
            count=data.get("count", 1),
            rank_timeline=data.get("rank_timeline", []),
        )


@dataclass
class RSSItem:
    """Modèle de données d'une entrée RSS"""

    title: str                          # Titre
    feed_id: str                        # ID du flux RSS (par ex. "hacker-news")
    feed_name: str = ""                 # Nom du flux RSS (utilisé à l'exécution)
    url: str = ""                       # Lien de l'article
    guid: str = ""                      # GUID/ID (guid RSS ou id Atom)
    published_at: str = ""              # Heure de publication RSS (format ISO)
    summary: str = ""                   # Résumé/description
    author: str = ""                    # Auteur
    crawl_time: str = ""                # Heure de collecte (format HH:MM)

    # Informations statistiques
    first_time: str = ""                # Heure de première collecte
    last_time: str = ""                 # Heure de dernière collecte
    count: int = 1                      # Nombre de collectes

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "title": self.title,
            "feed_id": self.feed_id,
            "feed_name": self.feed_name,
            "url": self.url,
            "published_at": self.published_at,
            "summary": self.summary,
            "author": self.author,
            "crawl_time": self.crawl_time,
            "first_time": self.first_time,
            "last_time": self.last_time,
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RSSItem":
        """Crée à partir d'un dictionnaire"""
        return cls(
            title=data.get("title", ""),
            feed_id=data.get("feed_id", ""),
            feed_name=data.get("feed_name", ""),
            url=data.get("url", ""),
            published_at=data.get("published_at", ""),
            summary=data.get("summary", ""),
            author=data.get("author", ""),
            crawl_time=data.get("crawl_time", ""),
            first_time=data.get("first_time", ""),
            last_time=data.get("last_time", ""),
            count=data.get("count", 1),
        )


@dataclass
class RSSData:
    """
    Ensemble de données RSS

    Structure :
    - date : date (YYYY-MM-DD)
    - crawl_time : heure de collecte (HH:MM)
    - items : entrées RSS regroupées par feed_id
    - id_to_name : correspondance feed_id vers nom
    - failed_ids : liste des feed_id en échec
    """

    date: str                                   # Date
    crawl_time: str                             # Heure de collecte
    items: Dict[str, List[RSSItem]]             # Entrées regroupées par feed_id
    id_to_name: Dict[str, str] = field(default_factory=dict)   # Correspondance ID vers nom
    failed_ids: List[str] = field(default_factory=list)        # ID en échec

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        items_dict = {}
        for feed_id, rss_list in self.items.items():
            items_dict[feed_id] = [item.to_dict() for item in rss_list]

        return {
            "date": self.date,
            "crawl_time": self.crawl_time,
            "items": items_dict,
            "id_to_name": self.id_to_name,
            "failed_ids": self.failed_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RSSData":
        """Crée à partir d'un dictionnaire"""
        items = {}
        items_data = data.get("items", {})
        for feed_id, rss_list in items_data.items():
            items[feed_id] = [RSSItem.from_dict(item) for item in rss_list]

        return cls(
            date=data.get("date", ""),
            crawl_time=data.get("crawl_time", ""),
            items=items,
            id_to_name=data.get("id_to_name", {}),
            failed_ids=data.get("failed_ids", []),
        )

    def get_total_count(self) -> int:
        """Récupère le nombre total d'entrées"""
        return sum(len(rss_list) for rss_list in self.items.values())


@dataclass
class NewsData:
    """
    Ensemble de données d'actualités

    Structure :
    - date : date (YYYY-MM-DD)
    - crawl_time : heure de collecte (HH heures MM minutes)
    - items : entrées d'actualités regroupées par ID de source
    - id_to_name : correspondance ID de source vers nom
    - failed_ids : liste des ID de source en échec
    """

    date: str                                   # Date
    crawl_time: str                             # Heure de collecte
    items: Dict[str, List[NewsItem]]            # Actualités regroupées par source
    id_to_name: Dict[str, str] = field(default_factory=dict)   # Correspondance ID vers nom
    failed_ids: List[str] = field(default_factory=list)        # ID en échec

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        items_dict = {}
        for source_id, news_list in self.items.items():
            items_dict[source_id] = [item.to_dict() for item in news_list]

        return {
            "date": self.date,
            "crawl_time": self.crawl_time,
            "items": items_dict,
            "id_to_name": self.id_to_name,
            "failed_ids": self.failed_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NewsData":
        """Crée à partir d'un dictionnaire"""
        items = {}
        items_data = data.get("items", {})
        for source_id, news_list in items_data.items():
            items[source_id] = [NewsItem.from_dict(item) for item in news_list]

        return cls(
            date=data.get("date", ""),
            crawl_time=data.get("crawl_time", ""),
            items=items,
            id_to_name=data.get("id_to_name", {}),
            failed_ids=data.get("failed_ids", []),
        )

    def get_total_count(self) -> int:
        """Récupère le nombre total d'actualités"""
        return sum(len(news_list) for news_list in self.items.values())

    def merge_with(self, other: "NewsData") -> "NewsData":
        """
        Fusionne un autre NewsData dans les données actuelles

        Règles de fusion :
        - les actualités ayant le même source_id + title voient leur historique de classements fusionné
        - mise à jour de last_time et count
        - conservation du first_time le plus ancien
        """
        merged_items = {}

        # Copie les données actuelles
        for source_id, news_list in self.items.items():
            merged_items[source_id] = {item.title: item for item in news_list}

        # Fusionne les autres données
        for source_id, news_list in other.items.items():
            if source_id not in merged_items:
                merged_items[source_id] = {}

            for item in news_list:
                if item.title in merged_items[source_id]:
                    # Fusionne avec l'actualité déjà existante
                    existing = merged_items[source_id][item.title]

                    # Fusionne les classements
                    existing_ranks = set(existing.ranks) if existing.ranks else set()
                    new_ranks = set(item.ranks) if item.ranks else set()
                    merged_ranks = sorted(existing_ranks | new_ranks)
                    existing.ranks = merged_ranks

                    # Met à jour les heures
                    if item.first_time and (not existing.first_time or item.first_time < existing.first_time):
                        existing.first_time = item.first_time
                    if item.last_time and (not existing.last_time or item.last_time > existing.last_time):
                        existing.last_time = item.last_time

                    # Met à jour le compteur
                    existing.count += 1

                    # Conserve l'URL (si elle était absente à l'origine)
                    if not existing.url and item.url:
                        existing.url = item.url
                    if not existing.mobile_url and item.mobile_url:
                        existing.mobile_url = item.mobile_url
                else:
                    # Ajoute la nouvelle actualité
                    merged_items[source_id][item.title] = item

        # Reconvertit au format liste
        final_items = {}
        for source_id, items_dict in merged_items.items():
            final_items[source_id] = list(items_dict.values())

        # Fusionne id_to_name
        merged_id_to_name = {**self.id_to_name, **other.id_to_name}

        # Fusionne failed_ids (avec déduplication)
        merged_failed_ids = list(set(self.failed_ids + other.failed_ids))

        return NewsData(
            date=self.date or other.date,
            crawl_time=other.crawl_time,  # Utilise l'heure de collecte la plus récente
            items=final_items,
            id_to_name=merged_id_to_name,
            failed_ids=merged_failed_ids,
        )


class StorageBackend(ABC):
    """
    Classe de base abstraite des backends de stockage

    Tous les backends de stockage doivent implémenter ces méthodes, afin de permettre :
    - l'enregistrement des données d'actualités
    - la lecture de toutes les données du jour
    - la détection des nouvelles actualités
    - la génération de fichiers de rapport (TXT/HTML)
    """

    @abstractmethod
    def save_news_data(self, data: NewsData) -> bool:
        """
        Enregistre les données d'actualités

        Args:
            data: données d'actualités

        Returns:
            True si l'enregistrement a réussi
        """
        pass

    @abstractmethod
    def get_today_all_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """
        Récupère toutes les données d'actualités d'une date donnée

        Args:
            date: chaîne de date (YYYY-MM-DD), aujourd'hui par défaut

        Returns:
            les données d'actualités fusionnées, ou None s'il n'y a aucune donnée
        """
        pass

    @abstractmethod
    def get_latest_crawl_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """
        Récupère les données de la collecte la plus récente

        Args:
            date: chaîne de date, aujourd'hui par défaut

        Returns:
            les données d'actualités de la collecte la plus récente
        """
        pass

    @abstractmethod
    def detect_new_titles(self, current_data: NewsData) -> Dict[str, Dict]:
        """
        Détecte les nouveaux titres

        Args:
            current_data: données de la collecte en cours

        Returns:
            les données des nouveaux titres, format: {source_id: {title: title_data}}
        """
        pass

    @abstractmethod
    def save_txt_snapshot(self, data: NewsData) -> Optional[str]:
        """
        Enregistre un instantané TXT (fonction optionnelle, disponible en environnement local)

        Args:
            data: données d'actualités

        Returns:
            le chemin du fichier enregistré, ou None si non pris en charge
        """
        pass

    @abstractmethod
    def save_html_report(self, html_content: str, filename: str) -> Optional[str]:
        """
        Enregistre un rapport HTML

        Args:
            html_content: contenu HTML
            filename: nom du fichier

        Returns:
            le chemin du fichier enregistré
        """
        pass

    @abstractmethod
    def is_first_crawl_today(self, date: Optional[str] = None) -> bool:
        """
        Vérifie s'il s'agit de la première collecte du jour

        Args:
            date: chaîne de date, aujourd'hui par défaut

        Returns:
            True s'il s'agit de la première collecte
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """
        Libère les ressources (fichiers temporaires, connexions à la base de données, etc.)
        """
        pass

    @abstractmethod
    def cleanup_old_data(self, retention_days: int) -> int:
        """
        Nettoie les données expirées

        Args:
            retention_days: nombre de jours de conservation (0 signifie pas de nettoyage)

        Returns:
            le nombre de répertoires de dates supprimés
        """
        pass

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """
        Nom du backend de stockage
        """
        pass

    @property
    @abstractmethod
    def supports_txt(self) -> bool:
        """
        Indique si la génération d'instantanés TXT est prise en charge
        """
        pass

    # === Enregistrement des exécutions par tranche horaire (système de planification) ===

    def has_period_executed(self, date_str: str, period_key: str, action: str) -> bool:
        """
        Vérifie si une action donnée a déjà été exécutée pour une tranche horaire donnée

        Args:
            date_str: chaîne de date YYYY-MM-DD
            period_key: clé de la tranche horaire
            action: type d'action (analyze / push)

        Returns:
            True si l'action a déjà été exécutée
        """
        return False

    def record_period_execution(self, date_str: str, period_key: str, action: str) -> bool:
        """
        Enregistre l'exécution d'une action pour une tranche horaire

        Args:
            date_str: chaîne de date YYYY-MM-DD
            period_key: clé de la tranche horaire
            action: type d'action (analyze / push)

        Returns:
            True si l'enregistrement a réussi
        """
        return False

    # === Filtrage intelligent par IA (implémentation par défaut, surchargée par les sous-classes via un mixin) ===

    def begin_batch(self) -> None:
        """Active le mode par lots (le backend distant diffère l'envoi, le backend local ne fait rien)"""
        pass

    def end_batch(self) -> None:
        """Termine le mode par lots"""
        pass

    def get_active_ai_filter_tags(self, date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> List[Dict]:
        return []

    def get_latest_prompt_hash(self, date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> Optional[str]:
        return None

    def get_latest_ai_filter_tag_version(self, date: Optional[str] = None) -> int:
        return 0

    def deprecate_all_ai_filter_tags(self, date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> int:
        return 0

    def save_ai_filter_tags(self, tags: List[Dict], version: int, prompt_hash: str, date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> int:
        return 0

    def save_ai_filter_results(self, results: List[Dict], date: Optional[str] = None) -> int:
        return 0

    def get_active_ai_filter_results(self, date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> List[Dict]:
        return []

    def deprecate_specific_ai_filter_tags(self, tag_ids: List[int], date: Optional[str] = None) -> int:
        return 0

    def update_ai_filter_tags_hash(self, interests_file: str, new_hash: str, date: Optional[str] = None) -> int:
        return 0

    def update_ai_filter_tag_descriptions(self, tag_updates: List[Dict], date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> int:
        return 0

    def update_ai_filter_tag_priorities(self, tag_priorities: List[Dict], date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> int:
        return 0

    def save_analyzed_news(self, news_ids: List[str], source_type: str, interests_file: str, prompt_hash: str, matched_ids: Set[str], date: Optional[str] = None) -> int:
        return 0

    def get_analyzed_news_ids(self, source_type: str = "hotlist", date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> Set[str]:
        return set()

    def clear_analyzed_news(self, date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> int:
        return 0

    def clear_unmatched_analyzed_news(self, date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> int:
        return 0

    def get_all_news_ids(self, date: Optional[str] = None) -> List[Dict]:
        return []

    def get_all_rss_ids(self, date: Optional[str] = None) -> List[Dict]:
        return []


def convert_crawl_results_to_news_data(
    results: Dict[str, Dict],
    id_to_name: Dict[str, str],
    failed_ids: List[str],
    crawl_time: str,
    crawl_date: str,
) -> NewsData:
    """
    Convertit les résultats du collecteur au format NewsData

    Args:
        results: résultats renvoyés par le collecteur {source_id: {title: {ranks: [], url: "", mobileUrl: ""}}}
        id_to_name: correspondance ID de source vers nom
        failed_ids: ID de source en échec
        crawl_time: heure de collecte (HH:MM)
        crawl_date: date de collecte (YYYY-MM-DD)

    Returns:
        un objet NewsData
    """
    items = {}

    for source_id, titles_data in results.items():
        source_name = id_to_name.get(source_id, source_id)
        news_list = []

        for title, data in titles_data.items():
            ranks = data.get("ranks", [])
            url = data.get("url", "")
            mobile_url = data.get("mobileUrl", "")

            rank = ranks[0] if ranks else 99

            news_item = NewsItem(
                title=title,
                source_id=source_id,
                source_name=source_name,
                rank=rank,
                url=url,
                mobile_url=mobile_url,
                crawl_time=crawl_time,
                ranks=ranks,
                first_time=crawl_time,
                last_time=crawl_time,
                count=1,
            )
            news_list.append(news_item)

        items[source_id] = news_list

    return NewsData(
        date=crawl_date,
        crawl_time=crawl_time,
        items=items,
        id_to_name=id_to_name,
        failed_ids=failed_ids,
    )
