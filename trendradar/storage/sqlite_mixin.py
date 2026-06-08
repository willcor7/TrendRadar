# coding=utf-8
"""
Mixin de stockage SQLite

Fournit la logique commune des opérations sur la base de données SQLite, réutilisée par LocalStorageBackend et RemoteStorageBackend.
"""

import sqlite3
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from trendradar.storage.base import NewsItem, NewsData, RSSItem, RSSData
from trendradar.utils.url import normalize_url


class SQLiteStorageMixin:
    """
    Mixin d'opérations de stockage SQLite

    Les sous-classes doivent implémenter les méthodes abstraites suivantes :
    - _get_connection(date, db_type) -> sqlite3.Connection
    - _get_configured_time() -> datetime
    - _format_date_folder(date) -> str
    - _format_time_filename() -> str
    """

    # ========================================
    # Méthodes abstraites - à implémenter par les sous-classes
    # ========================================

    @abstractmethod
    def _get_connection(self, date: Optional[str] = None, db_type: str = "news") -> sqlite3.Connection:
        """Récupère une connexion à la base de données"""
        pass

    @abstractmethod
    def _get_configured_time(self) -> datetime:
        """Récupère l'heure actuelle dans le fuseau horaire configuré"""
        pass

    @abstractmethod
    def _format_date_folder(self, date: Optional[str] = None) -> str:
        """Formate le nom du dossier de date (format ISO : YYYY-MM-DD)"""
        pass

    @abstractmethod
    def _format_time_filename(self) -> str:
        """Formate le nom de fichier basé sur l'heure (format : HH-MM)"""
        pass

    # ========================================
    # Gestion du schéma
    # ========================================

    def _get_schema_path(self, db_type: str = "news") -> Path:
        """
        Récupère le chemin du fichier schema.sql

        Args:
            db_type: type de base de données ("news" ou "rss")

        Returns:
            le chemin du fichier de schéma
        """
        if db_type == "rss":
            return Path(__file__).parent / "rss_schema.sql"
        return Path(__file__).parent / "schema.sql"

    def _get_ai_filter_schema_path(self) -> Path:
        """Récupère le chemin du fichier de schéma du filtrage IA"""
        return Path(__file__).parent / "ai_filter_schema.sql"

    def _init_tables(self, conn: sqlite3.Connection, db_type: str = "news") -> None:
        """
        Initialise la structure des tables de la base de données depuis schema.sql

        Args:
            conn: connexion à la base de données
            db_type: type de base de données ("news" ou "rss")
        """
        schema_path = self._get_schema_path(db_type)

        if schema_path.exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            conn.executescript(schema_sql)
        else:
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        # La base news charge en plus la structure des tables du filtrage IA
        if db_type == "news":
            ai_filter_schema = self._get_ai_filter_schema_path()
            if ai_filter_schema.exists():
                with open(ai_filter_schema, "r", encoding="utf-8") as f:
                    conn.executescript(f.read())

        if db_type == "rss":
            self._migrate_rss_schema(conn)

        conn.commit()

    def _migrate_rss_schema(self, conn: sqlite3.Connection) -> None:
        """Migre la structure de la table rss_items (ajoute la colonne guid aux bases de données existantes)"""
        cursor = conn.execute("PRAGMA table_info(rss_items)")
        columns = {row[1] for row in cursor.fetchall()}
        if "guid" not in columns:
            conn.execute("ALTER TABLE rss_items ADD COLUMN guid TEXT DEFAULT ''")
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_rss_guid_feed
                ON rss_items(guid, feed_id) WHERE guid != ''
            """)

    # ========================================
    # Stockage des données d'actualités
    # ========================================

    def _save_news_data_impl(self, data: NewsData, log_prefix: str = "[stockage]") -> tuple[bool, int, int, int, int]:
        """
        Enregistre les données d'actualités dans SQLite (implémentation centrale)

        Args:
            data: données d'actualités
            log_prefix: préfixe de journal

        Returns:
            (success, new_count, updated_count, title_changed_count, off_list_count)
        """
        try:
            conn = self._get_connection(data.date)
            cursor = conn.cursor()

            # Récupère l'heure actuelle dans le fuseau horaire configuré
            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")

            # Synchronise d'abord les informations de plateforme dans la table platforms
            for source_id, source_name in data.id_to_name.items():
                cursor.execute("""
                    INSERT INTO platforms (id, name, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        updated_at = excluded.updated_at
                """, (source_id, source_name, now_str))

            # Compteurs statistiques
            new_count = 0
            updated_count = 0
            title_changed_count = 0
            success_sources = []

            for source_id, news_list in data.items.items():
                success_sources.append(source_id)

                for item in news_list:
                    try:
                        # Normalise l'URL (retire les paramètres dynamiques, comme band_rank pour Weibo)
                        normalized_url = normalize_url(item.url, source_id) if item.url else ""

                        # Vérifie si l'entrée existe déjà (via l'URL normalisée + platform_id)
                        if normalized_url:
                            cursor.execute("""
                                SELECT id, title FROM news_items
                                WHERE url = ? AND platform_id = ?
                            """, (normalized_url, source_id))
                            existing = cursor.fetchone()

                            if existing:
                                # Existe déjà, met à jour l'enregistrement
                                existing_id, existing_title = existing

                                update_title = item.title
                                if (update_title and update_title.strip().startswith(("http://", "https://", "//"))
                                        and existing_title and not existing_title.strip().startswith(("http://", "https://", "//"))):
                                    update_title = existing_title

                                # Vérifie si le titre a changé
                                if existing_title != update_title:
                                    # Enregistre le changement de titre
                                    cursor.execute("""
                                        INSERT INTO title_changes
                                        (news_item_id, old_title, new_title, changed_at)
                                        VALUES (?, ?, ?, ?)
                                    """, (existing_id, existing_title, update_title, now_str))
                                    title_changed_count += 1

                                # Enregistre l'historique des classements
                                cursor.execute("""
                                    INSERT INTO rank_history
                                    (news_item_id, rank, crawl_time, created_at)
                                    VALUES (?, ?, ?, ?)
                                """, (existing_id, item.rank, data.crawl_time, now_str))

                                # Met à jour l'enregistrement existant
                                cursor.execute("""
                                    UPDATE news_items SET
                                        title = ?,
                                        rank = ?,
                                        mobile_url = ?,
                                        last_crawl_time = ?,
                                        crawl_count = crawl_count + 1,
                                        updated_at = ?
                                    WHERE id = ?
                                """, (update_title, item.rank, item.mobile_url,
                                      data.crawl_time, now_str, existing_id))
                                updated_count += 1
                            else:
                                # N'existe pas, insère un nouvel enregistrement (stocke l'URL normalisée)
                                cursor.execute("""
                                    INSERT INTO news_items
                                    (title, platform_id, rank, url, mobile_url,
                                     first_crawl_time, last_crawl_time, crawl_count,
                                     created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                                """, (item.title, source_id, item.rank, normalized_url,
                                      item.mobile_url, data.crawl_time, data.crawl_time,
                                      now_str, now_str))
                                new_id = cursor.lastrowid
                                # Enregistre le classement initial
                                cursor.execute("""
                                    INSERT INTO rank_history
                                    (news_item_id, rank, crawl_time, created_at)
                                    VALUES (?, ?, ?, ?)
                                """, (new_id, item.rank, data.crawl_time, now_str))
                                new_count += 1
                        else:
                            # Cas d'une URL vide, insertion directe (sans déduplication)
                            cursor.execute("""
                                INSERT INTO news_items
                                (title, platform_id, rank, url, mobile_url,
                                 first_crawl_time, last_crawl_time, crawl_count,
                                 created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                            """, (item.title, source_id, item.rank, "",
                                  item.mobile_url, data.crawl_time, data.crawl_time,
                                  now_str, now_str))
                            new_id = cursor.lastrowid
                            # Enregistre le classement initial
                            cursor.execute("""
                                INSERT INTO rank_history
                                (news_item_id, rank, crawl_time, created_at)
                                VALUES (?, ?, ?, ?)
                            """, (new_id, item.rank, data.crawl_time, now_str))
                            new_count += 1

                    except sqlite3.Error as e:
                        print(f"{log_prefix} échec de l'enregistrement de l'entrée d'actualité [{item.title[:30]}...] : {e}")

            total_items = new_count + updated_count

            # ========================================
            # Détection des sorties de classement : détecte les actualités présentes au classement précédent mais absentes cette fois-ci
            # ========================================
            off_list_count = 0

            # Récupère l'heure de la collecte précédente
            cursor.execute("""
                SELECT crawl_time FROM crawl_records
                WHERE crawl_time < ?
                ORDER BY crawl_time DESC
                LIMIT 1
            """, (data.crawl_time,))
            prev_record = cursor.fetchone()

            if prev_record:
                prev_crawl_time = prev_record[0]

                # Pour chaque plateforme collectée avec succès, détecte les sorties de classement
                for source_id in success_sources:
                    # Récupère toutes les URL normalisées de cette plateforme dans la collecte en cours
                    current_urls = set()
                    for item in data.items.get(source_id, []):
                        normalized_url = normalize_url(item.url, source_id) if item.url else ""
                        if normalized_url:
                            current_urls.add(normalized_url)

                    # Recherche les actualités présentes au classement précédent (last_crawl_time = prev_crawl_time) mais absentes cette fois-ci
                    # Ces actualités sortent du classement « pour la première fois » et doivent être enregistrées
                    cursor.execute("""
                        SELECT id, url FROM news_items
                        WHERE platform_id = ?
                          AND last_crawl_time = ?
                          AND url != ''
                    """, (source_id, prev_crawl_time))

                    for row in cursor.fetchall():
                        news_id, url = row[0], row[1]
                        if url not in current_urls:
                            # Insère un enregistrement de sortie de classement (rank=0 indique la sortie du classement)
                            cursor.execute("""
                                INSERT INTO rank_history
                                (news_item_id, rank, crawl_time, created_at)
                                VALUES (?, 0, ?, ?)
                            """, (news_id, data.crawl_time, now_str))
                            off_list_count += 1

            # Enregistre les informations de collecte
            cursor.execute("""
                INSERT OR REPLACE INTO crawl_records
                (crawl_time, total_items, created_at)
                VALUES (?, ?, ?)
            """, (data.crawl_time, total_items, now_str))

            # Récupère l'ID du crawl_record qui vient d'être inséré
            cursor.execute("""
                SELECT id FROM crawl_records WHERE crawl_time = ?
            """, (data.crawl_time,))
            record_row = cursor.fetchone()
            if record_row:
                crawl_record_id = record_row[0]

                # Enregistre les sources collectées avec succès
                for source_id in success_sources:
                    cursor.execute("""
                        INSERT OR REPLACE INTO crawl_source_status
                        (crawl_record_id, platform_id, status)
                        VALUES (?, ?, 'success')
                    """, (crawl_record_id, source_id))

                # Enregistre les sources en échec
                for failed_id in data.failed_ids:
                    # Garantit que les plateformes en échec figurent aussi dans la table platforms
                    cursor.execute("""
                        INSERT OR IGNORE INTO platforms (id, name, updated_at)
                        VALUES (?, ?, ?)
                    """, (failed_id, failed_id, now_str))

                    cursor.execute("""
                        INSERT OR REPLACE INTO crawl_source_status
                        (crawl_record_id, platform_id, status)
                        VALUES (?, ?, 'failed')
                    """, (crawl_record_id, failed_id))

            conn.commit()

            return True, new_count, updated_count, title_changed_count, off_list_count

        except Exception as e:
            print(f"{log_prefix} échec de l'enregistrement : {e}")
            return False, 0, 0, 0, 0

    def _get_today_all_data_impl(self, date: Optional[str] = None) -> Optional[NewsData]:
        """
        Récupère toutes les données d'actualités d'une date donnée (après fusion)

        Args:
            date: chaîne de date, aujourd'hui par défaut

        Returns:
            les données d'actualités fusionnées
        """
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            # Récupère toutes les données d'actualités (avec l'id pour interroger l'historique des classements)
            cursor.execute("""
                SELECT n.id, n.title, n.platform_id, p.name as platform_name,
                       n.rank, n.url, n.mobile_url,
                       n.first_crawl_time, n.last_crawl_time, n.crawl_count
                FROM news_items n
                LEFT JOIN platforms p ON n.platform_id = p.id
                ORDER BY n.platform_id, n.last_crawl_time
            """)

            rows = cursor.fetchall()
            if not rows:
                return None

            # Rassemble tous les news_item_id
            news_ids = [row[0] for row in rows]

            # Interroge l'historique des classements par lot (récupère en même temps l'heure et le classement)
            # Logique de filtrage : ne conserve que les enregistrements de sortie de classement (rank=0) antérieurs à last_crawl_time
            # Cela évite d'afficher des enregistrements sans intérêt après la sortie définitive d'une actualité du classement
            rank_history_map: Dict[int, List[int]] = {}
            rank_timeline_map: Dict[int, List[Dict[str, Any]]] = {}
            if news_ids:
                placeholders = ",".join("?" * len(news_ids))
                cursor.execute(f"""
                    SELECT rh.news_item_id, rh.rank, rh.crawl_time
                    FROM rank_history rh
                    JOIN news_items ni ON rh.news_item_id = ni.id
                    WHERE rh.news_item_id IN ({placeholders})
                      AND NOT (rh.rank = 0 AND rh.crawl_time > ni.last_crawl_time)
                    ORDER BY rh.news_item_id, rh.crawl_time
                """, news_ids)
                for rh_row in cursor.fetchall():
                    news_id, rank, crawl_time = rh_row[0], rh_row[1], rh_row[2]

                    if not crawl_time:
                        continue

                    # Construit la liste ranks (avec déduplication, en excluant les sorties de classement rank=0)
                    if news_id not in rank_history_map:
                        rank_history_map[news_id] = []
                    if rank != 0 and rank not in rank_history_map[news_id]:
                        rank_history_map[news_id].append(rank)

                    # Construit la liste rank_timeline (chronologie complète, sorties de classement incluses)
                    if news_id not in rank_timeline_map:
                        rank_timeline_map[news_id] = []
                    # Extrait la partie heure (HH:MM)
                    try:
                        time_part = crawl_time.split()[1][:5] if ' ' in crawl_time else crawl_time[:5]
                    except (IndexError, AttributeError):
                        time_part = "??:??"
                    rank_timeline_map[news_id].append({
                        "time": time_part,
                        "rank": rank if rank != 0 else None  # 0 converti en None pour indiquer la sortie du classement
                    })

            # Regroupe par platform_id
            items: Dict[str, List[NewsItem]] = {}
            id_to_name: Dict[str, str] = {}
            crawl_date = self._format_date_folder(date)

            for row in rows:
                news_id = row[0]
                platform_id = row[2]
                title = row[1]
                platform_name = row[3] or platform_id

                id_to_name[platform_id] = platform_name

                if platform_id not in items:
                    items[platform_id] = []

                # Récupère l'historique des classements, ou utilise le classement actuel à défaut
                ranks = rank_history_map.get(news_id, [row[4]])
                rank_timeline = rank_timeline_map.get(news_id, [])

                items[platform_id].append(NewsItem(
                    title=title,
                    source_id=platform_id,
                    source_name=platform_name,
                    rank=row[4],
                    url=row[5] or "",
                    mobile_url=row[6] or "",
                    crawl_time=row[8],  # last_crawl_time
                    ranks=ranks,
                    first_time=row[7],  # first_crawl_time
                    last_time=row[8],   # last_crawl_time
                    count=row[9],       # crawl_count
                    rank_timeline=rank_timeline,
                ))

            final_items = items

            # Récupère les sources en échec
            cursor.execute("""
                SELECT DISTINCT css.platform_id
                FROM crawl_source_status css
                JOIN crawl_records cr ON css.crawl_record_id = cr.id
                WHERE css.status = 'failed'
            """)
            failed_ids = [row[0] for row in cursor.fetchall()]

            # Récupère l'heure de collecte la plus récente
            cursor.execute("""
                SELECT crawl_time FROM crawl_records
                ORDER BY crawl_time DESC
                LIMIT 1
            """)

            time_row = cursor.fetchone()
            crawl_time = time_row[0] if time_row else self._format_time_filename()

            return NewsData(
                date=crawl_date,
                crawl_time=crawl_time,
                items=final_items,
                id_to_name=id_to_name,
                failed_ids=failed_ids,
            )

        except Exception as e:
            print(f"[stockage] échec de la lecture des données : {e}")
            return None

    def _get_latest_crawl_data_impl(self, date: Optional[str] = None) -> Optional[NewsData]:
        """
        Récupère les données de la collecte la plus récente

        Args:
            date: chaîne de date, aujourd'hui par défaut

        Returns:
            les données d'actualités de la collecte la plus récente
        """
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            # Récupère l'heure de collecte la plus récente
            cursor.execute("""
                SELECT crawl_time FROM crawl_records
                ORDER BY crawl_time DESC
                LIMIT 1
            """)

            time_row = cursor.fetchone()
            if not time_row:
                return None

            latest_time = time_row[0]

            # Récupère les données d'actualités de cette heure (avec l'id pour interroger l'historique des classements)
            cursor.execute("""
                SELECT n.id, n.title, n.platform_id, p.name as platform_name,
                       n.rank, n.url, n.mobile_url,
                       n.first_crawl_time, n.last_crawl_time, n.crawl_count
                FROM news_items n
                LEFT JOIN platforms p ON n.platform_id = p.id
                WHERE n.last_crawl_time = ?
            """, (latest_time,))

            rows = cursor.fetchall()
            if not rows:
                return None

            # Rassemble tous les news_item_id
            news_ids = [row[0] for row in rows]

            # Interroge l'historique des classements par lot (récupère en même temps l'heure et le classement)
            # Logique de filtrage : ne conserve que les enregistrements de sortie de classement (rank=0) antérieurs à last_crawl_time
            # Cela évite d'afficher des enregistrements sans intérêt après la sortie définitive d'une actualité du classement
            rank_history_map: Dict[int, List[int]] = {}
            rank_timeline_map: Dict[int, List[Dict[str, Any]]] = {}
            if news_ids:
                placeholders = ",".join("?" * len(news_ids))
                cursor.execute(f"""
                    SELECT rh.news_item_id, rh.rank, rh.crawl_time
                    FROM rank_history rh
                    JOIN news_items ni ON rh.news_item_id = ni.id
                    WHERE rh.news_item_id IN ({placeholders})
                      AND NOT (rh.rank = 0 AND rh.crawl_time > ni.last_crawl_time)
                    ORDER BY rh.news_item_id, rh.crawl_time
                """, news_ids)
                for rh_row in cursor.fetchall():
                    news_id, rank, crawl_time = rh_row[0], rh_row[1], rh_row[2]

                    if not crawl_time:
                        continue

                    # Construit la liste ranks (avec déduplication, en excluant les sorties de classement rank=0)
                    if news_id not in rank_history_map:
                        rank_history_map[news_id] = []
                    if rank != 0 and rank not in rank_history_map[news_id]:
                        rank_history_map[news_id].append(rank)

                    # Construit la liste rank_timeline (chronologie complète, sorties de classement incluses)
                    if news_id not in rank_timeline_map:
                        rank_timeline_map[news_id] = []
                    # Extrait la partie heure (HH:MM)
                    try:
                        time_part = crawl_time.split()[1][:5] if ' ' in crawl_time else crawl_time[:5]
                    except (IndexError, AttributeError):
                        time_part = "??:??"
                    rank_timeline_map[news_id].append({
                        "time": time_part,
                        "rank": rank if rank != 0 else None  # 0 converti en None pour indiquer la sortie du classement
                    })

            items: Dict[str, List[NewsItem]] = {}
            id_to_name: Dict[str, str] = {}
            crawl_date = self._format_date_folder(date)

            for row in rows:
                news_id = row[0]
                platform_id = row[2]
                platform_name = row[3] or platform_id
                id_to_name[platform_id] = platform_name

                if platform_id not in items:
                    items[platform_id] = []

                # Récupère l'historique des classements, ou utilise le classement actuel à défaut
                ranks = rank_history_map.get(news_id, [row[4]])
                rank_timeline = rank_timeline_map.get(news_id, [])

                items[platform_id].append(NewsItem(
                    title=row[1],
                    source_id=platform_id,
                    source_name=platform_name,
                    rank=row[4],
                    url=row[5] or "",
                    mobile_url=row[6] or "",
                    crawl_time=row[8],  # last_crawl_time
                    ranks=ranks,
                    first_time=row[7],  # first_crawl_time
                    last_time=row[8],   # last_crawl_time
                    count=row[9],       # crawl_count
                    rank_timeline=rank_timeline,
                ))

            # Récupère les sources en échec (pour la collecte la plus récente)
            cursor.execute("""
                SELECT css.platform_id
                FROM crawl_source_status css
                JOIN crawl_records cr ON css.crawl_record_id = cr.id
                WHERE cr.crawl_time = ? AND css.status = 'failed'
            """, (latest_time,))

            failed_ids = [row[0] for row in cursor.fetchall()]

            return NewsData(
                date=crawl_date,
                crawl_time=latest_time,
                items=items,
                id_to_name=id_to_name,
                failed_ids=failed_ids,
            )

        except Exception as e:
            print(f"[stockage] échec de la récupération des données les plus récentes : {e}")
            return None

    def _detect_new_titles_impl(self, current_data: NewsData) -> Dict[str, Dict]:
        """
        Détecte les nouveaux titres

        Cette méthode compare les données de la collecte en cours avec les données historiques pour repérer les nouveaux titres.
        Logique clé : seuls les titres jamais apparus dans les lots historiques sont considérés comme nouveaux.

        Args:
            current_data: données de la collecte en cours

        Returns:
            les données des nouveaux titres {source_id: {title: NewsItem}}
        """
        try:
            # Récupère les données historiques
            historical_data = self._get_today_all_data_impl(current_data.date)

            if not historical_data:
                # Aucune donnée historique, tout est nouveau
                new_titles = {}
                for source_id, news_list in current_data.items.items():
                    new_titles[source_id] = {item.title: item for item in news_list}
                return new_titles

            # Récupère l'heure du lot en cours
            current_time = current_data.crawl_time

            # Rassemble les titres historiques (ceux dont first_time < current_time)
            # Cela permet de traiter correctement le cas d'un même titre donnant plusieurs enregistrements à cause d'un changement d'URL
            historical_titles: Dict[str, set] = {}
            for source_id, news_list in historical_data.items.items():
                historical_titles[source_id] = set()
                for item in news_list:
                    first_time = item.first_time or item.crawl_time
                    if first_time < current_time:
                        historical_titles[source_id].add(item.title)

            # Vérifie s'il existe des données historiques
            has_historical_data = any(len(titles) > 0 for titles in historical_titles.values())
            if not has_historical_data:
                # Première collecte : la notion de « nouveauté » n'a pas de sens
                return {}

            # Détecte les nouveautés
            new_titles = {}
            for source_id, news_list in current_data.items.items():
                hist_set = historical_titles.get(source_id, set())
                for item in news_list:
                    if item.title not in hist_set:
                        if source_id not in new_titles:
                            new_titles[source_id] = {}
                        new_titles[source_id][item.title] = item

            return new_titles

        except Exception as e:
            print(f"[stockage] échec de la détection des nouveaux titres : {e}")
            return {}

    def _is_first_crawl_today_impl(self, date: Optional[str] = None) -> bool:
        """
        Vérifie s'il s'agit de la première collecte du jour

        Args:
            date: chaîne de date, aujourd'hui par défaut

        Returns:
            True s'il s'agit de la première collecte
        """
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) as count FROM crawl_records
            """)

            row = cursor.fetchone()
            count = row[0] if row else 0

            # S'il n'y a qu'un seul enregistrement ou aucun, on considère qu'il s'agit de la première collecte
            return count <= 1

        except Exception as e:
            print(f"[stockage] échec de la vérification de la première collecte : {e}")
            return True

    def _get_crawl_times_impl(self, date: Optional[str] = None) -> List[str]:
        """
        Récupère la liste de toutes les heures de collecte d'une date donnée

        Args:
            date: chaîne de date, aujourd'hui par défaut

        Returns:
            la liste des heures de collecte (triées par heure)
        """
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT crawl_time FROM crawl_records
                ORDER BY crawl_time
            """)

            rows = cursor.fetchall()
            return [row[0] for row in rows]

        except Exception as e:
            print(f"[stockage] échec de la récupération de la liste des heures de collecte : {e}")
            return []

    # ========================================
    # Enregistrement des exécutions par tranche horaire (système de planification)
    # ========================================

    def _has_period_executed_impl(self, date_str: str, period_key: str, action: str) -> bool:
        """
        Vérifie si une action donnée a déjà été exécutée aujourd'hui pour une tranche horaire donnée

        Args:
            date_str: chaîne de date YYYY-MM-DD
            period_key: clé de la tranche horaire
            action: type d'action (analyze / push)

        Returns:
            True si l'action a déjà été exécutée
        """
        try:
            conn = self._get_connection(date_str)
            cursor = conn.cursor()

            # Vérifie d'abord si la table existe
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='period_executions'
            """)
            if not cursor.fetchone():
                return False

            cursor.execute("""
                SELECT 1 FROM period_executions
                WHERE execution_date = ? AND period_key = ? AND action = ?
            """, (date_str, period_key, action))

            return cursor.fetchone() is not None

        except Exception as e:
            print(f"[stockage] échec de la vérification de l'enregistrement d'exécution de tranche horaire : {e}")
            return False

    def _record_period_execution_impl(self, date_str: str, period_key: str, action: str) -> bool:
        """
        Enregistre l'exécution d'une action pour une tranche horaire

        Args:
            date_str: chaîne de date YYYY-MM-DD
            period_key: clé de la tranche horaire
            action: type d'action (analyze / push)

        Returns:
            True si l'enregistrement a réussi
        """
        try:
            conn = self._get_connection(date_str)
            cursor = conn.cursor()

            # Garantit l'existence de la table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS period_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_date TEXT NOT NULL,
                    period_key TEXT NOT NULL,
                    action TEXT NOT NULL,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(execution_date, period_key, action)
                )
            """)

            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT OR IGNORE INTO period_executions (execution_date, period_key, action, executed_at)
                VALUES (?, ?, ?, ?)
            """, (date_str, period_key, action, now_str))

            conn.commit()
            return True

        except Exception as e:
            print(f"[stockage] échec de l'enregistrement de l'exécution de tranche horaire : {e}")
            return False

    # ========================================
    # Stockage des données RSS
    # ========================================

    def _save_rss_data_impl(self, data: RSSData, log_prefix: str = "[stockage]") -> tuple[bool, int, int]:
        """
        Enregistre les données RSS dans SQLite (en utilisant l'URL comme identifiant unique)

        Args:
            data: données RSS
            log_prefix: préfixe de journal

        Returns:
            (success, new_count, updated_count)
        """
        try:
            conn = self._get_connection(data.date, db_type="rss")
            cursor = conn.cursor()

            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")

            # Synchronise les informations des flux RSS dans la table rss_feeds
            for feed_id, feed_name in data.id_to_name.items():
                cursor.execute("""
                    INSERT INTO rss_feeds (id, name, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        updated_at = excluded.updated_at
                """, (feed_id, feed_name, now_str))

            # Compteurs statistiques
            new_count = 0
            updated_count = 0

            for feed_id, rss_list in data.items.items():
                for item in rss_list:
                    try:
                        item_guid = getattr(item, "guid", "") or ""
                        existing = None

                        # Ordre de priorité pour la déduplication : guid > url
                        if item_guid:
                            cursor.execute("""
                                SELECT id, title FROM rss_items
                                WHERE guid = ? AND feed_id = ?
                            """, (item_guid, feed_id))
                            existing = cursor.fetchone()

                        if not existing and item.url:
                            cursor.execute("""
                                SELECT id, title FROM rss_items
                                WHERE url = ? AND feed_id = ?
                            """, (item.url, feed_id))
                            existing = cursor.fetchone()

                        if existing:
                            existing_id = existing[0]
                            existing_title = existing[1]
                            update_title = item.title
                            if (update_title and update_title.strip().startswith(("http://", "https://", "//"))
                                    and existing_title and not existing_title.strip().startswith(("http://", "https://", "//"))):
                                update_title = existing_title
                            cursor.execute("""
                                UPDATE rss_items SET
                                    title = ?,
                                    url = CASE WHEN ? != '' THEN ? ELSE url END,
                                    guid = CASE WHEN ? != '' THEN ? ELSE guid END,
                                    published_at = ?,
                                    summary = ?,
                                    author = ?,
                                    last_crawl_time = ?,
                                    crawl_count = crawl_count + 1,
                                    updated_at = ?
                                WHERE id = ?
                            """, (update_title,
                                  item.url, item.url,
                                  item_guid, item_guid,
                                  item.published_at, item.summary,
                                  item.author, data.crawl_time, now_str, existing_id))
                            updated_count += 1
                        elif item.url or item_guid:
                            try:
                                cursor.execute("""
                                    INSERT INTO rss_items
                                    (title, feed_id, url, guid, published_at, summary, author,
                                     first_crawl_time, last_crawl_time, crawl_count,
                                     created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                                """, (item.title, feed_id, item.url, item_guid,
                                      item.published_at, item.summary, item.author,
                                      data.crawl_time, data.crawl_time, now_str, now_str))
                                new_count += 1
                            except sqlite3.IntegrityError:
                                pass

                    except sqlite3.Error as e:
                        print(f"{log_prefix} échec de l'enregistrement de l'entrée RSS [{item.title[:30]}...] : {e}")

            total_items = new_count + updated_count

            # Enregistre les informations de collecte
            cursor.execute("""
                INSERT OR REPLACE INTO rss_crawl_records
                (crawl_time, total_items, created_at)
                VALUES (?, ?, ?)
            """, (data.crawl_time, total_items, now_str))

            # Enregistre l'état de la collecte
            cursor.execute("""
                SELECT id FROM rss_crawl_records WHERE crawl_time = ?
            """, (data.crawl_time,))
            record_row = cursor.fetchone()
            if record_row:
                crawl_record_id = record_row[0]

                # Enregistre les flux collectés avec succès
                for feed_id in data.items.keys():
                    cursor.execute("""
                        INSERT OR REPLACE INTO rss_crawl_status
                        (crawl_record_id, feed_id, status)
                        VALUES (?, ?, 'success')
                    """, (crawl_record_id, feed_id))

                # Enregistre les flux en échec
                for failed_id in data.failed_ids:
                    cursor.execute("""
                        INSERT OR IGNORE INTO rss_feeds (id, name, updated_at)
                        VALUES (?, ?, ?)
                    """, (failed_id, failed_id, now_str))

                    cursor.execute("""
                        INSERT OR REPLACE INTO rss_crawl_status
                        (crawl_record_id, feed_id, status)
                        VALUES (?, ?, 'failed')
                    """, (crawl_record_id, failed_id))

            conn.commit()

            return True, new_count, updated_count

        except Exception as e:
            print(f"{log_prefix} échec de l'enregistrement des données RSS : {e}")
            return False, 0, 0

    def _get_rss_data_impl(self, date: Optional[str] = None) -> Optional[RSSData]:
        """
        Récupère toutes les données RSS d'une date donnée

        Args:
            date: chaîne de date (YYYY-MM-DD), aujourd'hui par défaut

        Returns:
            un objet RSSData, ou None s'il n'y a aucune donnée
        """
        try:
            conn = self._get_connection(date, db_type="rss")
            cursor = conn.cursor()

            # Récupère toutes les données RSS
            cursor.execute("""
                SELECT i.id, i.title, i.feed_id, f.name as feed_name,
                       i.url, i.published_at, i.summary, i.author,
                       i.first_crawl_time, i.last_crawl_time, i.crawl_count
                FROM rss_items i
                LEFT JOIN rss_feeds f ON i.feed_id = f.id
                ORDER BY i.published_at DESC
            """)

            rows = cursor.fetchall()
            if not rows:
                return None

            items: Dict[str, List[RSSItem]] = {}
            id_to_name: Dict[str, str] = {}
            crawl_date = self._format_date_folder(date)

            for row in rows:
                feed_id = row[2]
                feed_name = row[3] or feed_id

                id_to_name[feed_id] = feed_name

                if feed_id not in items:
                    items[feed_id] = []

                items[feed_id].append(RSSItem(
                    title=row[1],
                    feed_id=feed_id,
                    feed_name=feed_name,
                    url=row[4] or "",
                    published_at=row[5] or "",
                    summary=row[6] or "",
                    author=row[7] or "",
                    crawl_time=row[9],
                    first_time=row[8],
                    last_time=row[9],
                    count=row[10],
                ))

            # Récupère l'heure de collecte la plus récente
            cursor.execute("""
                SELECT crawl_time FROM rss_crawl_records
                ORDER BY crawl_time DESC
                LIMIT 1
            """)
            time_row = cursor.fetchone()
            crawl_time = time_row[0] if time_row else self._format_time_filename()

            # Récupère les flux en échec
            cursor.execute("""
                SELECT DISTINCT cs.feed_id
                FROM rss_crawl_status cs
                JOIN rss_crawl_records cr ON cs.crawl_record_id = cr.id
                WHERE cs.status = 'failed'
            """)
            failed_ids = [row[0] for row in cursor.fetchall()]

            return RSSData(
                date=crawl_date,
                crawl_time=crawl_time,
                items=items,
                id_to_name=id_to_name,
                failed_ids=failed_ids,
            )

        except Exception as e:
            print(f"[stockage] échec de la lecture des données RSS : {e}")
            return None

    def _detect_new_rss_items_impl(self, current_data: RSSData) -> Dict[str, List[RSSItem]]:
        """
        Détecte les nouvelles entrées RSS (mode incrémental)

        Cette méthode compare les données de la collecte en cours avec les données historiques pour repérer les nouvelles entrées RSS.
        Logique clé : seules les URL jamais apparues dans les lots historiques sont considérées comme nouvelles.

        Args:
            current_data: données RSS de la collecte en cours

        Returns:
            les nouvelles entrées RSS {feed_id: [RSSItem, ...]}
        """
        try:
            # Récupère les données historiques
            historical_data = self._get_rss_data_impl(current_data.date)

            if not historical_data:
                # Aucune donnée historique, tout est nouveau
                return current_data.items.copy()

            # Récupère l'heure du lot en cours
            current_time = current_data.crawl_time

            # Rassemble les URL historiques (entrées dont first_time < current_time)
            historical_urls: Dict[str, set] = {}
            for feed_id, rss_list in historical_data.items.items():
                historical_urls[feed_id] = set()
                for item in rss_list:
                    first_time = item.first_time or item.crawl_time
                    if first_time < current_time:
                        if item.url:
                            historical_urls[feed_id].add(item.url)

            # Vérifie s'il existe des données historiques antérieures au lot en cours
            has_historical_data = any(len(urls) > 0 for urls in historical_urls.values())
            if not has_historical_data:
                # Première collecte du jour, toutes les entrées sont nouvelles
                return current_data.items.copy()

            # Détecte les nouveautés
            new_items: Dict[str, List[RSSItem]] = {}
            for feed_id, rss_list in current_data.items.items():
                hist_set = historical_urls.get(feed_id, set())
                for item in rss_list:
                    # Détermine la nouveauté via l'URL
                    if item.url and item.url not in hist_set:
                        if feed_id not in new_items:
                            new_items[feed_id] = []
                        new_items[feed_id].append(item)

            return new_items

        except Exception as e:
            print(f"[stockage] échec de la détection des nouvelles entrées RSS : {e}")
            return {}

    def _get_latest_rss_data_impl(self, date: Optional[str] = None) -> Optional[RSSData]:
        """
        Récupère les données RSS de la collecte la plus récente (mode classement actuel)

        Args:
            date: chaîne de date (YYYY-MM-DD), aujourd'hui par défaut

        Returns:
            les données RSS de la collecte la plus récente, ou None s'il n'y a aucune donnée
        """
        try:
            conn = self._get_connection(date, db_type="rss")
            cursor = conn.cursor()

            # Récupère l'heure de collecte la plus récente
            cursor.execute("""
                SELECT crawl_time FROM rss_crawl_records
                ORDER BY crawl_time DESC
                LIMIT 1
            """)

            time_row = cursor.fetchone()
            if not time_row:
                return None

            latest_time = time_row[0]

            # Récupère les données RSS de cette heure
            cursor.execute("""
                SELECT i.id, i.title, i.feed_id, f.name as feed_name,
                       i.url, i.published_at, i.summary, i.author,
                       i.first_crawl_time, i.last_crawl_time, i.crawl_count
                FROM rss_items i
                LEFT JOIN rss_feeds f ON i.feed_id = f.id
                WHERE i.last_crawl_time = ?
                ORDER BY i.published_at DESC
            """, (latest_time,))

            rows = cursor.fetchall()
            if not rows:
                return None

            items: Dict[str, List[RSSItem]] = {}
            id_to_name: Dict[str, str] = {}
            crawl_date = self._format_date_folder(date)

            for row in rows:
                feed_id = row[2]
                feed_name = row[3] or feed_id

                id_to_name[feed_id] = feed_name

                if feed_id not in items:
                    items[feed_id] = []

                items[feed_id].append(RSSItem(
                    title=row[1],
                    feed_id=feed_id,
                    feed_name=feed_name,
                    url=row[4] or "",
                    published_at=row[5] or "",
                    summary=row[6] or "",
                    author=row[7] or "",
                    crawl_time=row[9],
                    first_time=row[8],
                    last_time=row[9],
                    count=row[10],
                ))

            # Récupère les sources en échec (pour la collecte la plus récente)
            cursor.execute("""
                SELECT cs.feed_id
                FROM rss_crawl_status cs
                JOIN rss_crawl_records cr ON cs.crawl_record_id = cr.id
                WHERE cr.crawl_time = ? AND cs.status = 'failed'
            """, (latest_time,))

            failed_ids = [row[0] for row in cursor.fetchall()]

            return RSSData(
                date=crawl_date,
                crawl_time=latest_time,
                items=items,
                id_to_name=id_to_name,
                failed_ids=failed_ids,
            )

        except Exception as e:
            print(f"[stockage] échec de la récupération des données RSS les plus récentes : {e}")
            return None

    # ========================================
    # Filtrage intelligent par IA - gestion des étiquettes
    # ========================================

    def _get_active_tags_impl(self, date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> List[Dict[str, Any]]:
        """Récupère la liste des étiquettes actives d'un fichier de centres d'intérêt donné"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, tag, description, version, prompt_hash, priority
                FROM ai_filter_tags
                WHERE status = 'active' AND interests_file = ?
                ORDER BY priority ASC, id ASC
            """, (interests_file,))

            return [
                {
                    "id": row[0], "tag": row[1], "description": row[2],
                    "version": row[3], "prompt_hash": row[4], "priority": row[5],
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            print(f"[filtre IA] échec de la récupération des étiquettes : {e}")
            return []

    def _get_latest_prompt_hash_impl(self, date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> Optional[str]:
        """Récupère le prompt_hash de la version la plus récente des étiquettes d'un fichier de centres d'intérêt donné"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT prompt_hash FROM ai_filter_tags
                WHERE status = 'active' AND interests_file = ?
                ORDER BY version DESC
                LIMIT 1
            """, (interests_file,))
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"[filtre IA] échec de la récupération du prompt_hash : {e}")
            return None

    def _get_latest_tag_version_impl(self, date: Optional[str] = None) -> int:
        """Récupère le numéro de version le plus récent"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT MAX(version) FROM ai_filter_tags
            """)
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else 0
        except Exception as e:
            print(f"[filtre IA] échec de la récupération du numéro de version : {e}")
            return 0

    def _deprecate_all_tags_impl(self, date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> int:
        """Marque comme deprecated les étiquettes actives et les résultats de classification associés d'un fichier de centres d'intérêt donné"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()
            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")

            # Récupère les id des étiquettes actives de ce fichier de centres d'intérêt
            cursor.execute(
                "SELECT id FROM ai_filter_tags WHERE status = 'active' AND interests_file = ?",
                (interests_file,)
            )
            tag_ids = [row[0] for row in cursor.fetchall()]

            if not tag_ids:
                return 0

            # Rend les étiquettes obsolètes
            placeholders = ",".join("?" * len(tag_ids))
            cursor.execute(f"""
                UPDATE ai_filter_tags
                SET status = 'deprecated', deprecated_at = ?
                WHERE id IN ({placeholders})
            """, [now_str] + tag_ids)
            tag_count = cursor.rowcount

            # Rend obsolètes les résultats de classification associés
            placeholders = ",".join("?" * len(tag_ids))
            cursor.execute(f"""
                UPDATE ai_filter_results
                SET status = 'deprecated', deprecated_at = ?
                WHERE tag_id IN ({placeholders}) AND status = 'active'
            """, [now_str] + tag_ids)

            conn.commit()
            print(f"[filtre IA] {tag_count} étiquettes et leurs résultats de classification associés rendus obsolètes")
            return tag_count
        except Exception as e:
            print(f"[filtre IA] échec de la mise en obsolescence des étiquettes : {e}")
            return 0

    def _save_tags_impl(
        self, date: Optional[str], tags: List[Dict], version: int, prompt_hash: str,
        interests_file: str = "ai_interests.txt"
    ) -> int:
        """Enregistre les étiquettes nouvellement extraites"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()
            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")

            count = 0
            for idx, tag_data in enumerate(tags, start=1):
                priority = tag_data.get("priority", idx)
                try:
                    priority = int(priority)
                except (TypeError, ValueError):
                    priority = idx
                cursor.execute("""
                    INSERT INTO ai_filter_tags
                    (tag, description, priority, version, prompt_hash, interests_file, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    tag_data["tag"],
                    tag_data.get("description", ""),
                    priority,
                    version,
                    prompt_hash,
                    interests_file,
                    now_str,
                ))
                count += 1

            conn.commit()
            return count
        except Exception as e:
            print(f"[filtre IA] échec de l'enregistrement des étiquettes : {e}")
            return 0

    def _deprecate_specific_tags_impl(
        self, date: Optional[str], tag_ids: List[int]
    ) -> int:
        """Rend obsolètes les étiquettes des ID donnés et leurs résultats de classification associés (utilisé lors des mises à jour incrémentales)"""
        if not tag_ids:
            return 0
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()
            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")

            placeholders = ",".join("?" * len(tag_ids))

            cursor.execute(f"""
                UPDATE ai_filter_tags
                SET status = 'deprecated', deprecated_at = ?
                WHERE id IN ({placeholders})
            """, [now_str] + tag_ids)
            tag_count = cursor.rowcount

            cursor.execute(f"""
                UPDATE ai_filter_results
                SET status = 'deprecated', deprecated_at = ?
                WHERE tag_id IN ({placeholders}) AND status = 'active'
            """, [now_str] + tag_ids)

            conn.commit()
            return tag_count
        except Exception as e:
            print(f"[filtre IA] échec de la mise en obsolescence des étiquettes indiquées : {e}")
            return 0

    def _update_tags_hash_impl(
        self, date: Optional[str], interests_file: str, new_hash: str
    ) -> int:
        """Met à jour le prompt_hash de toutes les étiquettes actives d'un fichier de centres d'intérêt donné (utilisé lors des mises à jour incrémentales)"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE ai_filter_tags
                SET prompt_hash = ?
                WHERE interests_file = ? AND status = 'active'
            """, (new_hash, interests_file))
            count = cursor.rowcount

            conn.commit()
            return count
        except Exception as e:
            print(f"[filtre IA] échec de la mise à jour du hash des étiquettes : {e}")
            return 0

    # ========================================
    # Filtrage intelligent par IA - gestion des résultats de classification
    # ========================================

    def _update_tag_descriptions_impl(
        self, date: Optional[str], tag_updates: List[Dict],
        interests_file: str = "ai_interests.txt"
    ) -> int:
        """Met à jour le champ description des étiquettes actives, par correspondance sur le nom du tag"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            count = 0
            for t in tag_updates:
                tag_name = t.get("tag", "")
                description = t.get("description", "")
                if not tag_name:
                    continue
                cursor.execute("""
                    UPDATE ai_filter_tags
                    SET description = ?
                    WHERE tag = ? AND interests_file = ? AND status = 'active'
                """, (description, tag_name, interests_file))
                count += cursor.rowcount

            conn.commit()
            return count
        except Exception as e:
            print(f"[filtre IA] échec de la mise à jour de la description des étiquettes : {e}")
            return 0

    def _update_tag_priorities_impl(
        self, date: Optional[str], tag_priorities: List[Dict],
        interests_file: str = "ai_interests.txt"
    ) -> int:
        """Met à jour le champ priority des étiquettes actives, par correspondance sur le nom du tag"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            count = 0
            for t in tag_priorities:
                tag_name = t.get("tag", "")
                priority = t.get("priority")
                if not tag_name:
                    continue
                try:
                    priority = int(priority)
                except (TypeError, ValueError):
                    continue
                cursor.execute("""
                    UPDATE ai_filter_tags
                    SET priority = ?
                    WHERE tag = ? AND interests_file = ? AND status = 'active'
                """, (priority, tag_name, interests_file))
                count += cursor.rowcount

            conn.commit()
            return count
        except Exception as e:
            print(f"[filtre IA] échec de la mise à jour de la priorité des étiquettes : {e}")
            return 0

    # ========================================
    # Filtrage intelligent par IA - suivi des actualités déjà analysées
    # ========================================

    def _save_analyzed_news_impl(
        self, date: Optional[str], news_ids: List[int], source_type: str,
        interests_file: str, prompt_hash: str, matched_ids: set
    ) -> int:
        """Enregistre en masse les actualités déjà analysées (les correspondances comme les non-correspondances sont enregistrées)"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()
            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")

            count = 0
            for nid in news_ids:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO ai_filter_analyzed_news
                        (news_item_id, source_type, interests_file, prompt_hash, matched, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        nid, source_type, interests_file, prompt_hash,
                        1 if nid in matched_ids else 0,
                        now_str,
                    ))
                    count += 1
                except Exception:
                    pass

            conn.commit()
            return count
        except Exception as e:
            print(f"[filtre IA] échec de l'enregistrement des analyses : {e}")
            return 0

    def _get_analyzed_news_ids_impl(
        self, date: Optional[str] = None, source_type: str = "hotlist",
        interests_file: str = "ai_interests.txt"
    ) -> set:
        """Récupère l'ensemble des ID d'actualités déjà analysées (sert à la déduplication)"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT news_item_id FROM ai_filter_analyzed_news
                WHERE source_type = ? AND interests_file = ?
            """, (source_type, interests_file))

            return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            print(f"[filtre IA] échec de la récupération des ID déjà analysés : {e}")
            return set()

    def _clear_analyzed_news_impl(
        self, date: Optional[str] = None, interests_file: str = "ai_interests.txt"
    ) -> int:
        """Efface tous les enregistrements d'analyse d'un fichier de centres d'intérêt donné (utilisé lors d'une reclassification complète)"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM ai_filter_analyzed_news
                WHERE interests_file = ?
            """, (interests_file,))

            count = cursor.rowcount
            conn.commit()
            return count
        except Exception as e:
            print(f"[filtre IA] échec de l'effacement des enregistrements d'analyse : {e}")
            return 0

    def _clear_unmatched_analyzed_news_impl(
        self, date: Optional[str] = None, interests_file: str = "ai_interests.txt"
    ) -> int:
        """Efface les enregistrements d'analyse sans correspondance, pour donner à ces actualités une chance d'être réanalysées par de nouvelles étiquettes"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM ai_filter_analyzed_news
                WHERE interests_file = ? AND matched = 0
            """, (interests_file,))

            count = cursor.rowcount
            conn.commit()
            return count
        except Exception as e:
            print(f"[filtre IA] échec de l'effacement des enregistrements sans correspondance : {e}")
            return 0

    # ========================================
    # Filtrage intelligent par IA - gestion des résultats de classification (existant)
    # ========================================

    def _save_filter_results_impl(
        self, date: Optional[str], results: List[Dict]
    ) -> int:
        """Enregistre en masse les résultats de classification"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()
            now_str = self._get_configured_time().strftime("%Y-%m-%d %H:%M:%S")

            count = 0
            for r in results:
                try:
                    cursor.execute("""
                        INSERT INTO ai_filter_results
                        (news_item_id, source_type, tag_id, relevance_score, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        r["news_item_id"],
                        r.get("source_type", "hotlist"),
                        r["tag_id"],
                        r.get("relevance_score", 0.0),
                        now_str,
                    ))
                    count += 1
                except sqlite3.IntegrityError:
                    pass  # Enregistrement en double, ignoré

            conn.commit()
            return count
        except Exception as e:
            print(f"[filtre IA] échec de l'enregistrement des résultats de classification : {e}")
            return 0

    def _get_active_filter_results_impl(self, date: Optional[str] = None, interests_file: str = "ai_interests.txt") -> List[Dict[str, Any]]:
        """Récupère les résultats de classification actifs d'un fichier de centres d'intérêt donné, en JOIN avec news_items pour obtenir les détails des actualités"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            # Résultats des tendances
            cursor.execute("""
                SELECT
                    r.news_item_id, r.source_type, r.tag_id, r.relevance_score,
                    t.tag, t.description as tag_description, t.priority,
                    n.title, n.platform_id as source_id, p.name as source_name,
                    n.url, n.mobile_url, n.rank,
                    n.first_crawl_time, n.last_crawl_time, n.crawl_count
                FROM ai_filter_results r
                JOIN ai_filter_tags t ON r.tag_id = t.id
                JOIN news_items n ON r.news_item_id = n.id
                LEFT JOIN platforms p ON n.platform_id = p.id
                WHERE r.status = 'active' AND r.source_type = 'hotlist'
                    AND t.status = 'active' AND t.interests_file = ?
                ORDER BY t.priority ASC, t.id ASC, r.relevance_score DESC
            """, (interests_file,))

            results = []
            hotlist_news_ids = []
            for row in cursor.fetchall():
                results.append({
                    "news_item_id": row[0], "source_type": row[1],
                    "tag_id": row[2], "relevance_score": row[3],
                    "tag": row[4], "tag_description": row[5], "tag_priority": row[6],
                    "title": row[7], "source_id": row[8],
                    "source_name": row[9] or row[8],
                    "url": row[10] or "", "mobile_url": row[11] or "",
                    "rank": row[12],
                    "first_time": row[13], "last_time": row[14],
                    "count": row[15],
                })
                hotlist_news_ids.append(row[0])

            # Interroge l'historique des classements par lot (tendances)
            ranks_map: Dict[int, List[int]] = {}
            rank_timeline_map: Dict[int, List[Dict[str, Any]]] = {}
            if hotlist_news_ids:
                unique_ids = list(set(hotlist_news_ids))
                placeholders = ",".join("?" * len(unique_ids))
                cursor.execute(f"""
                    SELECT news_item_id, rank, crawl_time FROM rank_history
                    WHERE news_item_id IN ({placeholders})
                    ORDER BY news_item_id, crawl_time
                """, unique_ids)
                for rh_row in cursor.fetchall():
                    nid, rank, crawl_time = rh_row[0], rh_row[1], rh_row[2]

                    if not crawl_time:
                        continue

                    if nid not in ranks_map:
                        ranks_map[nid] = []
                    if rank != 0 and rank not in ranks_map[nid]:
                        ranks_map[nid].append(rank)

                    if nid not in rank_timeline_map:
                        rank_timeline_map[nid] = []
                    try:
                        time_part = crawl_time.split()[1][:5] if ' ' in crawl_time else crawl_time[:5]
                    except (IndexError, AttributeError):
                        time_part = "??:??"
                    rank_timeline_map[nid].append({
                        "time": time_part,
                        "rank": rank if rank != 0 else None
                    })

            for item in results:
                item["ranks"] = ranks_map.get(item["news_item_id"], [item["rank"]])
                item["rank_timeline"] = rank_timeline_map.get(item["news_item_id"], [])

            # Résultats RSS (s'il existe une base rss)
            try:
                rss_conn = self._get_connection(date, db_type="rss")
                rss_cursor = rss_conn.cursor()

                # Récupère depuis la base news les ID des résultats de classification de type rss
                cursor.execute("""
                    SELECT r.news_item_id, r.tag_id, r.relevance_score,
                           t.tag, t.description, t.priority
                    FROM ai_filter_results r
                    JOIN ai_filter_tags t ON r.tag_id = t.id
                    WHERE r.status = 'active' AND r.source_type = 'rss'
                        AND t.status = 'active' AND t.interests_file = ?
                    ORDER BY t.priority ASC, t.id ASC, r.relevance_score DESC
                """, (interests_file,))

                rss_filter_rows = cursor.fetchall()
                if rss_filter_rows:
                    rss_ids = [row[0] for row in rss_filter_rows]
                    placeholders = ",".join("?" * len(rss_ids))
                    rss_cursor.execute(f"""
                        SELECT i.id, i.title, i.feed_id, f.name as feed_name,
                               i.url, i.published_at
                        FROM rss_items i
                        LEFT JOIN rss_feeds f ON i.feed_id = f.id
                        WHERE i.id IN ({placeholders})
                    """, rss_ids)

                    rss_info = {row[0]: row for row in rss_cursor.fetchall()}

                    for fr_row in rss_filter_rows:
                        rss_id = fr_row[0]
                        info = rss_info.get(rss_id)
                        if info:
                            results.append({
                                "news_item_id": rss_id,
                                "source_type": "rss",
                                "tag_id": fr_row[1],
                                "relevance_score": fr_row[2],
                                "tag": fr_row[3],
                                "tag_description": fr_row[4],
                                "tag_priority": fr_row[5],
                                "title": info[1],
                                "source_id": info[2],
                                "source_name": info[3] or info[2],
                                "url": info[4] or "",
                                "mobile_url": "",
                                "rank": 0,
                                "ranks": [],
                                "first_time": info[5] or "",
                                "last_time": info[5] or "",
                                "count": 1,
                            })
            except Exception:
                pass  # Ignore silencieusement lorsque la base RSS n'existe pas

            return results
        except Exception as e:
            print(f"[filtre IA] échec de la récupération des résultats de classification : {e}")
            return []

    def _get_all_news_ids_impl(self, date: Optional[str] = None) -> List[Dict]:
        """Récupère l'id et le titre de toutes les actualités du jour (pour la classification du filtrage IA)"""
        try:
            conn = self._get_connection(date)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT n.id, n.title, n.platform_id, p.name as platform_name
                FROM news_items n
                LEFT JOIN platforms p ON n.platform_id = p.id
                ORDER BY n.id
            """)

            return [
                {
                    "id": row[0], "title": row[1],
                    "source_id": row[2], "source_name": row[3] or row[2],
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            print(f"[filtre IA] échec de la récupération de la liste des actualités : {e}")
            return []

    def _get_all_rss_ids_impl(self, date: Optional[str] = None) -> List[Dict]:
        """Récupère l'id et le titre de toutes les entrées RSS du jour (pour la classification du filtrage IA)"""
        try:
            conn = self._get_connection(date, db_type="rss")
            cursor = conn.cursor()

            cursor.execute("""
                SELECT i.id, i.title, i.feed_id, f.name as feed_name, i.published_at
                FROM rss_items i
                LEFT JOIN rss_feeds f ON i.feed_id = f.id
                ORDER BY i.id
            """)

            return [
                {
                    "id": row[0], "title": row[1],
                    "source_id": row[2], "source_name": row[3] or row[2],
                    "published_at": row[4] or "",
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            print(f"[filtre IA] échec de la récupération de la liste RSS : {e}")
            return []
