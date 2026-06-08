"""
Service d'analyse des données

v2.0.0 : prend uniquement en charge la base de données SQLite, suppression de la prise en charge des fichiers TXT
Nouvelle structure de stockage : output/{type}/{date}.db
"""

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import yaml

from ..utils.errors import FileParseError, DataNotFoundError
from .cache_service import get_cache


class ParserService:
    """Classe du service d'analyse des données"""

    def __init__(self, project_root: str = None):
        """
        Initialise le service d'analyse

        Args:
            project_root: répertoire racine du projet, par défaut le répertoire parent du répertoire courant
        """
        if project_root is None:
            current_file = Path(__file__)
            self.project_root = current_file.parent.parent.parent
        else:
            self.project_root = Path(project_root)

        self.cache = get_cache()

        # Cache du mtime de frequency_words.txt
        self._freq_words_cache: Optional[List[Dict]] = None
        self._freq_words_mtime: float = 0.0

    @staticmethod
    def clean_title(title: str) -> str:
        """Nettoie le texte du titre"""
        title = re.sub(r'\s+', ' ', title)
        title = title.strip()
        return title

    def get_date_folder_name(self, date: datetime = None) -> str:
        """
        Récupère la chaîne de date (format ISO)

        Args:
            date: objet date, par défaut aujourd'hui

        Returns:
            chaîne de date (YYYY-MM-DD)
        """
        if date is None:
            date = datetime.now()
        return date.strftime("%Y-%m-%d")

    def _get_db_path(self, date: datetime = None, db_type: str = "news") -> Optional[Path]:
        """
        Récupère le chemin du fichier de base de données

        Nouvelle structure : output/{type}/{date}.db

        Args:
            date: objet date, par défaut aujourd'hui
            db_type: type de base de données ("news" ou "rss")

        Returns:
            chemin du fichier de base de données, ou None s'il n'existe pas
        """
        date_str = self.get_date_folder_name(date)
        db_path = self.project_root / "output" / db_type / f"{date_str}.db"
        if db_path.exists():
            return db_path
        return None

    def _read_from_sqlite(
        self,
        date: datetime = None,
        platform_ids: Optional[List[str]] = None,
        db_type: str = "news"
    ) -> Optional[Tuple[Dict, Dict, Dict]]:
        """
        Lit les données depuis la base de données SQLite

        Args:
            date: objet date, par défaut aujourd'hui
            platform_ids: liste des ID de plateformes, None signifie toutes les plateformes
            db_type: type de base de données ("news" ou "rss")

        Returns:
            tuple (all_titles, id_to_name, all_timestamps), ou None si la base de données n'existe pas
        """
        db_path = self._get_db_path(date, db_type)
        if db_path is None:
            return None

        all_titles = {}
        id_to_name = {}
        all_timestamps = {}

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if db_type == "news":
                return self._read_news_from_sqlite(cursor, platform_ids, all_titles, id_to_name, all_timestamps)
            elif db_type == "rss":
                return self._read_rss_from_sqlite(cursor, platform_ids, all_titles, id_to_name, all_timestamps)

        except Exception as e:
            print(f"Warning: échec de la lecture des données depuis SQLite : {e}")
            return None
        finally:
            if 'conn' in locals():
                conn.close()

    def _read_news_from_sqlite(
        self,
        cursor,
        platform_ids: Optional[List[str]],
        all_titles: Dict,
        id_to_name: Dict,
        all_timestamps: Dict
    ) -> Optional[Tuple[Dict, Dict, Dict]]:
        """Lit les données depuis la base de données des palmarès"""
        # Vérifie si la table existe
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='news_items'
        """)
        if not cursor.fetchone():
            return None

        # Construit la requête
        if platform_ids:
            placeholders = ','.join(['?' for _ in platform_ids])
            query = f"""
                SELECT n.id, n.platform_id, p.name as platform_name, n.title,
                       n.rank, n.url, n.mobile_url,
                       n.first_crawl_time, n.last_crawl_time, n.crawl_count
                FROM news_items n
                LEFT JOIN platforms p ON n.platform_id = p.id
                WHERE n.platform_id IN ({placeholders})
            """
            cursor.execute(query, platform_ids)
        else:
            cursor.execute("""
                SELECT n.id, n.platform_id, p.name as platform_name, n.title,
                       n.rank, n.url, n.mobile_url,
                       n.first_crawl_time, n.last_crawl_time, n.crawl_count
                FROM news_items n
                LEFT JOIN platforms p ON n.platform_id = p.id
            """)

        rows = cursor.fetchall()

        # Collecte tous les news_item_id pour interroger l'historique des classements
        news_ids = [row['id'] for row in rows]
        rank_history_map = {}

        if news_ids:
            placeholders = ",".join("?" * len(news_ids))
            cursor.execute(f"""
                SELECT news_item_id, rank FROM rank_history
                WHERE news_item_id IN ({placeholders})
                ORDER BY news_item_id, crawl_time
            """, news_ids)

            for rh_row in cursor.fetchall():
                news_id = rh_row['news_item_id']
                rank = rh_row['rank']
                if news_id not in rank_history_map:
                    rank_history_map[news_id] = []
                rank_history_map[news_id].append(rank)

        for row in rows:
            news_id = row['id']
            platform_id = row['platform_id']
            platform_name = row['platform_name'] or platform_id
            title = row['title']

            if platform_id not in id_to_name:
                id_to_name[platform_id] = platform_name

            if platform_id not in all_titles:
                all_titles[platform_id] = {}

            ranks = rank_history_map.get(news_id, [row['rank']])

            all_titles[platform_id][title] = {
                "ranks": ranks,
                "url": row['url'] or "",
                "mobileUrl": row['mobile_url'] or "",
                "first_time": row['first_crawl_time'] or "",
                "last_time": row['last_crawl_time'] or "",
                "count": row['crawl_count'] or 1,
            }

        # Récupère les heures de collecte comme timestamps
        cursor.execute("""
            SELECT crawl_time, created_at FROM crawl_records
            ORDER BY crawl_time
        """)
        for row in cursor.fetchall():
            crawl_time = row['crawl_time']
            created_at = row['created_at']
            try:
                ts = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").timestamp()
            except (ValueError, TypeError):
                ts = datetime.now().timestamp()
            all_timestamps[f"{crawl_time}.db"] = ts

        if not all_titles:
            return None

        return (all_titles, id_to_name, all_timestamps)

    def _read_rss_from_sqlite(
        self,
        cursor,
        feed_ids: Optional[List[str]],
        all_items: Dict,
        id_to_name: Dict,
        all_timestamps: Dict
    ) -> Optional[Tuple[Dict, Dict, Dict]]:
        """Lit les données depuis la base de données RSS"""
        # Vérifie si la table existe
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rss_items'
        """)
        if not cursor.fetchone():
            return None

        # Construit la requête
        if feed_ids:
            placeholders = ','.join(['?' for _ in feed_ids])
            query = f"""
                SELECT i.id, i.feed_id, f.name as feed_name, i.title,
                       i.url, i.published_at, i.summary, i.author,
                       i.first_crawl_time, i.last_crawl_time, i.crawl_count
                FROM rss_items i
                LEFT JOIN rss_feeds f ON i.feed_id = f.id
                WHERE i.feed_id IN ({placeholders})
                ORDER BY i.published_at DESC
            """
            cursor.execute(query, feed_ids)
        else:
            cursor.execute("""
                SELECT i.id, i.feed_id, f.name as feed_name, i.title,
                       i.url, i.published_at, i.summary, i.author,
                       i.first_crawl_time, i.last_crawl_time, i.crawl_count
                FROM rss_items i
                LEFT JOIN rss_feeds f ON i.feed_id = f.id
                ORDER BY i.published_at DESC
            """)

        rows = cursor.fetchall()

        for row in rows:
            feed_id = row['feed_id']
            feed_name = row['feed_name'] or feed_id
            title = row['title']

            if feed_id not in id_to_name:
                id_to_name[feed_id] = feed_name

            if feed_id not in all_items:
                all_items[feed_id] = {}

            all_items[feed_id][title] = {
                "url": row['url'] or "",
                "published_at": row['published_at'] or "",
                "summary": row['summary'] or "",
                "author": row['author'] or "",
                "first_time": row['first_crawl_time'] or "",
                "last_time": row['last_crawl_time'] or "",
                "count": row['crawl_count'] or 1,
            }

        # Récupère les heures de collecte
        cursor.execute("""
            SELECT crawl_time, created_at FROM rss_crawl_records
            ORDER BY crawl_time
        """)
        for row in cursor.fetchall():
            crawl_time = row['crawl_time']
            created_at = row['created_at']
            try:
                ts = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").timestamp()
            except (ValueError, TypeError):
                ts = datetime.now().timestamp()
            all_timestamps[f"{crawl_time}.db"] = ts

        if not all_items:
            return None

        return (all_items, id_to_name, all_timestamps)

    def read_all_titles_for_date(
        self,
        date: datetime = None,
        platform_ids: Optional[List[str]] = None,
        db_type: str = "news"
    ) -> Tuple[Dict, Dict, Dict]:
        """
        Lit toutes les données d'une date donnée (avec cache)

        Args:
            date: objet date, par défaut aujourd'hui
            platform_ids: liste des ID de plateformes/flux, None signifie tous
            db_type: type de base de données ("news" ou "rss")

        Returns:
            tuple (all_titles, id_to_name, all_timestamps)

        Raises:
            DataNotFoundError: données inexistantes
        """
        date_str = self.get_date_folder_name(date)
        platform_key = ','.join(sorted(platform_ids)) if platform_ids else 'all'
        cache_key = f"read_all:{db_type}:{date_str}:{platform_key}"

        is_today = (date is None) or (date.date() == datetime.now().date())
        ttl = 900 if is_today else 900

        cached = self.cache.get(cache_key, ttl=ttl)
        if cached:
            return cached

        result = self._read_from_sqlite(date, platform_ids, db_type)
        if result:
            self.cache.set(cache_key, result)
            return result

        raise DataNotFoundError(
            f"Aucune donnée {db_type} trouvée pour {date_str}",
            suggestion="Veuillez d'abord lancer le collecteur ou vérifier que la date est correcte"
        )

    def parse_yaml_config(self, config_path: str = None) -> dict:
        """
        Analyse le fichier de configuration YAML

        Args:
            config_path: chemin du fichier de configuration, par défaut config/config.yaml

        Returns:
            dictionnaire de configuration

        Raises:
            FileParseError: erreur d'analyse du fichier de configuration
        """
        if config_path is None:
            config_path = self.project_root / "config" / "config.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileParseError(str(config_path), "le fichier de configuration n'existe pas")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
            return config_data
        except Exception as e:
            raise FileParseError(str(config_path), str(e))

    def parse_frequency_words(self, words_file: str = None) -> List[Dict]:
        """
        Analyse le fichier de configuration des mots-clés (avec cache mtime)

        Ne ré-analyse que lorsque frequency_words.txt a été modifié, pour éviter les E/S répétées dans les boucles.

        Réutilise la logique d'analyse de trendradar.core.frequency, prend en charge :
        - lignes de commentaire commençant par #
        - lignes vides séparant les groupes de mots
        - [alias de groupe] comme première ligne d'un groupe de mots, donne un alias à tout le groupe
        - mots obligatoires préfixés par +, mots de filtrage préfixés par !, limite de quantité avec @
        - syntaxe d'expression régulière /pattern/
        - syntaxe de nom d'affichage avec => alias
        - zone de filtrage global [GLOBAL_FILTER]

        Priorité du nom d'affichage : alias de groupe > concaténation des alias de ligne > concaténation des mots-clés

        Args:
            words_file: chemin du fichier de mots-clés, par défaut config/frequency_words.txt

        Returns:
            liste des groupes de mots

        Raises:
            FileParseError: erreur d'analyse du fichier
        """
        import os
        from trendradar.core.frequency import load_frequency_words

        if words_file is None:
            words_file = str(self.project_root / "config" / "frequency_words.txt")
        else:
            words_file = str(words_file)

        try:
            current_mtime = os.path.getmtime(words_file)

            if self._freq_words_cache is not None and current_mtime == self._freq_words_mtime:
                return self._freq_words_cache

            word_groups, filter_words, global_filters = load_frequency_words(words_file)
            self._freq_words_cache = word_groups
            self._freq_words_mtime = current_mtime
            return word_groups
        except FileNotFoundError:
            return []
        except Exception as e:
            raise FileParseError(words_file, str(e))

    def get_available_dates(self, db_type: str = "news") -> List[str]:
        """
        Récupère la liste des dates disponibles

        Args:
            db_type: type de base de données ("news" ou "rss")

        Returns:
            liste de chaînes de dates (format YYYY-MM-DD, ordre décroissant)
        """
        db_dir = self.project_root / "output" / db_type
        if not db_dir.exists():
            return []

        dates = []
        for db_file in db_dir.glob("*.db"):
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})\.db$', db_file.name)
            if date_match:
                dates.append(date_match.group(1))

        return sorted(dates, reverse=True)

    def get_available_date_range(self, db_type: str = "news") -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Récupère la plage de dates disponible

        Args:
            db_type: type de base de données ("news" ou "rss")

        Returns:
            tuple (date la plus ancienne, date la plus récente), ou (None, None) s'il n'y a pas de données
        """
        dates = self.get_available_dates(db_type)
        if not dates:
            return (None, None)

        earliest = datetime.strptime(dates[-1], "%Y-%m-%d")
        latest = datetime.strptime(dates[0], "%Y-%m-%d")
        return (earliest, latest)
