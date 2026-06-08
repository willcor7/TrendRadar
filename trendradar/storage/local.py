# coding=utf-8
"""
Backend de stockage local - SQLite + TXT/HTML

Utilise SQLite comme stockage principal, avec prise en charge optionnelle des instantanés TXT et des rapports HTML
"""

import sqlite3
import shutil
import pytz
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from trendradar.storage.base import StorageBackend, NewsData, RSSItem, RSSData
from trendradar.storage.sqlite_mixin import SQLiteStorageMixin
from trendradar.utils.time import (
    DEFAULT_TIMEZONE,
    get_configured_time,
    format_date_folder,
    format_time_filename,
)


class LocalStorageBackend(SQLiteStorageMixin, StorageBackend):
    """
    Backend de stockage local

    Utilise une base de données SQLite pour stocker les données d'actualités, avec prise en charge de :
    - fichiers de base de données SQLite organisés par date
    - instantanés TXT optionnels (utiles pour le débogage)
    - génération de rapports HTML
    """

    def __init__(
        self,
        data_dir: str = "output",
        enable_txt: bool = True,
        enable_html: bool = True,
        timezone: str = DEFAULT_TIMEZONE,
    ):
        """
        Initialise le backend de stockage local

        Args:
            data_dir: chemin du répertoire de données
            enable_txt: activer ou non les instantanés TXT
            enable_html: activer ou non les rapports HTML
            timezone: configuration du fuseau horaire
        """
        self.data_dir = Path(data_dir)
        self.enable_txt = enable_txt
        self.enable_html = enable_html
        self.timezone = timezone
        self._db_connections: Dict[str, sqlite3.Connection] = {}

    @property
    def backend_name(self) -> str:
        return "local"

    @property
    def supports_txt(self) -> bool:
        return self.enable_txt

    # ========================================
    # Implémentation des méthodes abstraites de SQLiteStorageMixin
    # ========================================

    def _get_configured_time(self) -> datetime:
        """Récupère l'heure actuelle dans le fuseau horaire configuré"""
        return get_configured_time(self.timezone)

    def _format_date_folder(self, date: Optional[str] = None) -> str:
        """Formate le nom du dossier de date (format ISO : YYYY-MM-DD)"""
        return format_date_folder(date, self.timezone)

    def _format_time_filename(self) -> str:
        """Formate le nom de fichier basé sur l'heure (format : HH-MM)"""
        return format_time_filename(self.timezone)

    def _get_db_path(self, date: Optional[str] = None, db_type: str = "news") -> Path:
        """
        Récupère le chemin de la base de données SQLite

        Nouvelle structure (à plat) : output/{type}/{date}.db
        - output/news/2025-12-28.db
        - output/rss/2025-12-28.db

        Args:
            date: chaîne de date
            db_type: type de base de données ("news" ou "rss")

        Returns:
            le chemin du fichier de base de données
        """
        date_str = self._format_date_folder(date)
        db_dir = self.data_dir / db_type
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / f"{date_str}.db"

    def _get_connection(self, date: Optional[str] = None, db_type: str = "news") -> sqlite3.Connection:
        """
        Récupère une connexion à la base de données (avec mise en cache)

        Args:
            date: chaîne de date
            db_type: type de base de données ("news" ou "rss")

        Returns:
            une connexion à la base de données
        """
        db_path = str(self._get_db_path(date, db_type))

        if db_path not in self._db_connections:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            self._init_tables(conn, db_type)
            self._db_connections[db_path] = conn

        return self._db_connections[db_path]

    # ========================================
    # Implémentation de l'interface StorageBackend (déléguée au mixin)
    # ========================================

    def save_news_data(self, data: NewsData) -> bool:
        """Enregistre les données d'actualités dans SQLite"""
        db_path = self._get_db_path(data.date)
        if not db_path.exists():
            # Garantit l'existence du répertoire
            db_path.parent.mkdir(parents=True, exist_ok=True)

        success, new_count, updated_count, title_changed_count, off_list_count = \
            self._save_news_data_impl(data, "[stockage local]")

        if success:
            # Affiche un journal détaillé des statistiques de stockage
            log_parts = [f"[stockage local] traitement terminé : {new_count} nouvelles entrées"]
            if updated_count > 0:
                log_parts.append(f"{updated_count} entrées mises à jour")
            if title_changed_count > 0:
                log_parts.append(f"{title_changed_count} titres modifiés")
            if off_list_count > 0:
                log_parts.append(f"{off_list_count} entrées sorties du classement")
            print(", ".join(log_parts))

        return success

    def get_today_all_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """Récupère toutes les données d'actualités d'une date donnée (après fusion)"""
        db_path = self._get_db_path(date)
        if not db_path.exists():
            return None
        return self._get_today_all_data_impl(date)

    def get_latest_crawl_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """Récupère les données de la collecte la plus récente"""
        db_path = self._get_db_path(date)
        if not db_path.exists():
            return None
        return self._get_latest_crawl_data_impl(date)

    def detect_new_titles(self, current_data: NewsData) -> Dict[str, Dict]:
        """Détecte les nouveaux titres"""
        return self._detect_new_titles_impl(current_data)

    def is_first_crawl_today(self, date: Optional[str] = None) -> bool:
        """Vérifie s'il s'agit de la première collecte du jour"""
        db_path = self._get_db_path(date)
        if not db_path.exists():
            return True
        return self._is_first_crawl_today_impl(date)

    def get_crawl_times(self, date: Optional[str] = None) -> List[str]:
        """Récupère la liste de toutes les heures de collecte d'une date donnée"""
        db_path = self._get_db_path(date)
        if not db_path.exists():
            return []
        return self._get_crawl_times_impl(date)

    # ========================================
    # Enregistrement des exécutions par tranche horaire (système de planification)
    # ========================================

    def has_period_executed(self, date_str: str, period_key: str, action: str) -> bool:
        """Vérifie si une action donnée a déjà été exécutée pour une tranche horaire donnée"""
        return self._has_period_executed_impl(date_str, period_key, action)

    def record_period_execution(self, date_str: str, period_key: str, action: str) -> bool:
        """Enregistre l'exécution d'une action pour une tranche horaire"""
        success = self._record_period_execution_impl(date_str, period_key, action)
        if success:
            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[stockage local] enregistrement d'exécution de tranche horaire sauvegardé : {period_key}/{action} à {now_str}")
        return success

    # ========================================
    # Méthodes de stockage des données RSS
    # ========================================

    def save_rss_data(self, data: RSSData) -> bool:
        """Enregistre les données RSS dans SQLite"""
        success, new_count, updated_count = self._save_rss_data_impl(data, "[stockage local]")

        if success:
            # Affiche le journal des statistiques
            log_parts = [f"[stockage local] traitement RSS terminé : {new_count} nouvelles entrées"]
            if updated_count > 0:
                log_parts.append(f"{updated_count} entrées mises à jour")
            print(", ".join(log_parts))

        return success

    def get_rss_data(self, date: Optional[str] = None) -> Optional[RSSData]:
        """Récupère toutes les données RSS d'une date donnée"""
        return self._get_rss_data_impl(date)

    def detect_new_rss_items(self, current_data: RSSData) -> Dict[str, List[RSSItem]]:
        """Détecte les nouvelles entrées RSS"""
        return self._detect_new_rss_items_impl(current_data)

    def get_latest_rss_data(self, date: Optional[str] = None) -> Optional[RSSData]:
        """Récupère les données RSS de la collecte la plus récente"""
        db_path = self._get_db_path(date, db_type="rss")
        if not db_path.exists():
            return None
        return self._get_latest_rss_data_impl(date)

    # ========================================
    # Filtrage intelligent par IA
    # ========================================

    def get_active_ai_filter_tags(self, date=None, interests_file="ai_interests.txt"):
        return self._get_active_tags_impl(date, interests_file)

    def get_latest_prompt_hash(self, date=None, interests_file="ai_interests.txt"):
        return self._get_latest_prompt_hash_impl(date, interests_file)

    def get_latest_ai_filter_tag_version(self, date=None):
        return self._get_latest_tag_version_impl(date)

    def deprecate_all_ai_filter_tags(self, date=None, interests_file="ai_interests.txt"):
        return self._deprecate_all_tags_impl(date, interests_file)

    def save_ai_filter_tags(self, tags, version, prompt_hash, date=None, interests_file="ai_interests.txt"):
        return self._save_tags_impl(date, tags, version, prompt_hash, interests_file)

    def save_ai_filter_results(self, results, date=None):
        return self._save_filter_results_impl(date, results)

    def get_active_ai_filter_results(self, date=None, interests_file="ai_interests.txt"):
        return self._get_active_filter_results_impl(date, interests_file)

    def deprecate_specific_ai_filter_tags(self, tag_ids, date=None):
        return self._deprecate_specific_tags_impl(date, tag_ids)

    def update_ai_filter_tags_hash(self, interests_file, new_hash, date=None):
        return self._update_tags_hash_impl(date, interests_file, new_hash)

    def update_ai_filter_tag_descriptions(self, tag_updates, date=None, interests_file="ai_interests.txt"):
        return self._update_tag_descriptions_impl(date, tag_updates, interests_file)

    def update_ai_filter_tag_priorities(self, tag_priorities, date=None, interests_file="ai_interests.txt"):
        return self._update_tag_priorities_impl(date, tag_priorities, interests_file)

    def save_analyzed_news(self, news_ids, source_type, interests_file, prompt_hash, matched_ids, date=None):
        return self._save_analyzed_news_impl(date, news_ids, source_type, interests_file, prompt_hash, matched_ids)

    def get_analyzed_news_ids(self, source_type="hotlist", date=None, interests_file="ai_interests.txt"):
        return self._get_analyzed_news_ids_impl(date, source_type, interests_file)

    def clear_analyzed_news(self, date=None, interests_file="ai_interests.txt"):
        return self._clear_analyzed_news_impl(date, interests_file)

    def clear_unmatched_analyzed_news(self, date=None, interests_file="ai_interests.txt"):
        return self._clear_unmatched_analyzed_news_impl(date, interests_file)

    def get_all_news_ids(self, date=None):
        return self._get_all_news_ids_impl(date)

    def get_all_rss_ids(self, date=None):
        return self._get_all_rss_ids_impl(date)

    # ========================================
    # Fonctionnalités propres au stockage local : instantanés TXT/HTML
    # ========================================

    def save_txt_snapshot(self, data: NewsData) -> Optional[str]:
        """
        Enregistre un instantané TXT

        Nouvelle structure : output/txt/{date}/{time}.txt

        Args:
            data: données d'actualités

        Returns:
            le chemin du fichier enregistré
        """
        if not self.enable_txt:
            return None

        try:
            date_folder = self._format_date_folder(data.date)
            txt_dir = self.data_dir / "txt" / date_folder
            txt_dir.mkdir(parents=True, exist_ok=True)

            file_path = txt_dir / f"{data.crawl_time}.txt"

            with open(file_path, "w", encoding="utf-8") as f:
                for source_id, news_list in data.items.items():
                    source_name = data.id_to_name.get(source_id, source_id)

                    # Écrit le titre de la source
                    if source_name and source_name != source_id:
                        f.write(f"{source_id} | {source_name}\n")
                    else:
                        f.write(f"{source_id}\n")

                    # Trie par classement
                    sorted_news = sorted(news_list, key=lambda x: x.rank)

                    for item in sorted_news:
                        line = f"{item.rank}. {item.title}"
                        if item.url:
                            line += f" [URL:{item.url}]"
                        if item.mobile_url:
                            line += f" [MOBILE:{item.mobile_url}]"
                        f.write(line + "\n")

                    f.write("\n")

                # Écrit les sources en échec
                if data.failed_ids:
                    f.write("==== Échec de la requête pour les ID suivants ====\n")
                    for failed_id in data.failed_ids:
                        f.write(f"{failed_id}\n")

            print(f"[stockage local] instantané TXT enregistré : {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[stockage local] échec de l'enregistrement de l'instantané TXT : {e}")
            return None

    def save_html_report(self, html_content: str, filename: str) -> Optional[str]:
        """
        Enregistre un rapport HTML

        Nouvelle structure : output/html/{date}/{filename}

        Args:
            html_content: contenu HTML
            filename: nom du fichier

        Returns:
            le chemin du fichier enregistré
        """
        if not self.enable_html:
            return None

        try:
            date_folder = self._format_date_folder()
            html_dir = self.data_dir / "html" / date_folder
            html_dir.mkdir(parents=True, exist_ok=True)

            file_path = html_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"[stockage local] rapport HTML enregistré : {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[stockage local] échec de l'enregistrement du rapport HTML : {e}")
            return None

    # ========================================
    # Fonctionnalités propres au stockage local : libération des ressources
    # ========================================

    def cleanup(self) -> None:
        """Libère les ressources (ferme les connexions à la base de données)"""
        for db_path, conn in self._db_connections.items():
            try:
                conn.close()
                print(f"[stockage local] fermeture de la connexion à la base de données : {db_path}")
            except Exception as e:
                print(f"[stockage local] échec de la fermeture de la connexion {db_path} : {e}")

        self._db_connections.clear()

    def cleanup_old_data(self, retention_days: int) -> int:
        """
        Nettoie les données expirées

        Logique de nettoyage de la nouvelle structure :
        - output/news/{date}.db  -> supprime les fichiers .db expirés
        - output/rss/{date}.db   -> supprime les fichiers .db expirés
        - output/txt/{date}/     -> supprime les répertoires de dates expirés
        - output/html/{date}/    -> supprime les répertoires de dates expirés

        Args:
            retention_days: nombre de jours de conservation (0 signifie pas de nettoyage)

        Returns:
            le nombre de fichiers/répertoires supprimés
        """
        if retention_days <= 0:
            return 0

        deleted_count = 0
        cutoff_date = self._get_configured_time() - timedelta(days=retention_days)

        def parse_date_from_name(name: str) -> Optional[datetime]:
            """Analyse la date à partir d'un nom de fichier ou de répertoire (format ISO : YYYY-MM-DD)"""
            # Retire le suffixe .db
            name = name.replace('.db', '')
            try:
                date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', name)
                if date_match:
                    return datetime(
                        int(date_match.group(1)),
                        int(date_match.group(2)),
                        int(date_match.group(3)),
                        tzinfo=pytz.timezone(self.timezone)
                    )
            except Exception:
                pass
            return None

        try:
            if not self.data_dir.exists():
                return 0

            # Nettoie les fichiers de base de données (news/, rss/)
            for db_type in ["news", "rss"]:
                db_dir = self.data_dir / db_type
                if not db_dir.exists():
                    continue

                for db_file in db_dir.glob("*.db"):
                    file_date = parse_date_from_name(db_file.name)
                    if file_date and file_date < cutoff_date:
                        # Ferme d'abord la connexion à la base de données
                        db_path = str(db_file)
                        if db_path in self._db_connections:
                            try:
                                self._db_connections[db_path].close()
                                del self._db_connections[db_path]
                            except Exception:
                                pass

                        # Supprime le fichier
                        try:
                            db_file.unlink()
                            deleted_count += 1
                            print(f"[stockage local] nettoyage des données expirées : {db_type}/{db_file.name}")
                        except Exception as e:
                            print(f"[stockage local] échec de la suppression du fichier {db_file} : {e}")

            # Nettoie les répertoires d'instantanés (txt/, html/)
            for snapshot_type in ["txt", "html"]:
                snapshot_dir = self.data_dir / snapshot_type
                if not snapshot_dir.exists():
                    continue

                for date_folder in snapshot_dir.iterdir():
                    if not date_folder.is_dir() or date_folder.name.startswith('.'):
                        continue

                    folder_date = parse_date_from_name(date_folder.name)
                    if folder_date and folder_date < cutoff_date:
                        try:
                            shutil.rmtree(date_folder)
                            deleted_count += 1
                            print(f"[stockage local] nettoyage des données expirées : {snapshot_type}/{date_folder.name}")
                        except Exception as e:
                            print(f"[stockage local] échec de la suppression du répertoire {date_folder} : {e}")

            if deleted_count > 0:
                print(f"[stockage local] {deleted_count} fichiers/répertoires expirés nettoyés au total")

            return deleted_count

        except Exception as e:
            print(f"[stockage local] échec du nettoyage des données expirées : {e}")
            return deleted_count

    def __del__(self):
        """Destructeur, garantit la fermeture des connexions"""
        self.cleanup()
