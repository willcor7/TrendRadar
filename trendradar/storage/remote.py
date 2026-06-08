# coding=utf-8
"""
Backend de stockage distant (protocole compatible S3)

Prend en charge Cloudflare R2, Alibaba Cloud OSS, Tencent Cloud COS, AWS S3, MinIO, etc.
Utilise une API compatible S3 (boto3) pour accéder au stockage objet
Flux de données : téléchargement du SQLite du jour → fusion des nouvelles données → renvoi vers le stockage distant
"""

import pytz
import re
import shutil
import sys
import tempfile
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

try:
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    boto3 = None
    BotoConfig = None
    ClientError = Exception

from trendradar.storage.base import StorageBackend, NewsData, RSSItem, RSSData
from trendradar.storage.sqlite_mixin import SQLiteStorageMixin
from trendradar.utils.time import (
    DEFAULT_TIMEZONE,
    get_configured_time,
    format_date_folder,
    format_time_filename,
)


class RemoteStorageBackend(SQLiteStorageMixin, StorageBackend):
    """
    Backend de stockage cloud distant (protocole compatible S3)

    Caractéristiques :
    - accède au stockage distant via une API compatible S3
    - prend en charge Cloudflare R2, Alibaba Cloud OSS, Tencent Cloud COS, AWS S3, MinIO, etc.
    - télécharge le SQLite dans un répertoire temporaire pour y opérer
    - prend en charge la fusion et l'envoi des données
    - prend en charge le téléchargement des données historiques distantes vers le stockage local
    - nettoie automatiquement les fichiers temporaires en fin d'exécution
    """

    def __init__(
        self,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str,
        region: str = "",
        enable_txt: bool = False,  # En mode distant, pas de génération TXT par défaut
        enable_html: bool = True,
        temp_dir: Optional[str] = None,
        timezone: str = DEFAULT_TIMEZONE,
    ):
        """
        Initialise le backend de stockage distant

        Args:
            bucket_name: nom du bucket de stockage
            access_key_id: ID de la clé d'accès
            secret_access_key: clé d'accès secrète
            endpoint_url: URL du point de terminaison du service
            region: région (optionnel, requis par certains fournisseurs)
            enable_txt: activer ou non les instantanés TXT (désactivé par défaut)
            enable_html: activer ou non les rapports HTML
            temp_dir: chemin du répertoire temporaire (par défaut, le répertoire temporaire du système)
            timezone: configuration du fuseau horaire
        """
        if not HAS_BOTO3:
            raise ImportError("le backend de stockage distant nécessite l'installation de boto3 : pip install boto3")

        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region = region
        self.enable_txt = enable_txt
        self.enable_html = enable_html
        self.timezone = timezone

        # Crée le répertoire temporaire
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp(prefix="trendradar_"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Initialise le client S3
        # Utilise l'adressage de type virtual-hosted (le plus courant)
        # Choisit la version de signature selon le fournisseur :
        # - Tencent Cloud COS et Alibaba Cloud OSS utilisent SigV2 pour éviter les problèmes de chunked encoding
        # - les autres fournisseurs (AWS S3, Cloudflare R2, MinIO, etc.) utilisent SigV4 par défaut
        use_sigv2 = "myqcloud.com" in endpoint_url.lower() or "aliyuncs.com" in endpoint_url.lower()
        signature_version = 's3' if use_sigv2 else 's3v4'

        s3_config = BotoConfig(
            s3={"addressing_style": "virtual"},
            signature_version=signature_version,
        )

        client_kwargs = {
            "endpoint_url": endpoint_url,
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
            "config": s3_config,
        }
        if region:
            client_kwargs["region_name"] = region

        self.s3_client = boto3.client("s3", **client_kwargs)

        # Suit les fichiers téléchargés (pour le nettoyage)
        self._downloaded_files: List[Path] = []
        self._db_connections: Dict[str, sqlite3.Connection] = {}

        # Mode par lots : envoi différé, pour éviter d'envoyer fréquemment le même fichier
        self._batch_mode = False
        self._batch_dirty: set = set()  # Ensemble des (date, db_type) en attente d'envoi

        print(f"[stockage distant] initialisation terminée, bucket de stockage : {bucket_name}, version de signature : {signature_version}")

    @property
    def backend_name(self) -> str:
        return "remote"

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

    def _get_remote_db_key(self, date: Optional[str] = None, db_type: str = "news") -> str:
        """
        Récupère la clé d'objet du fichier SQLite dans le stockage distant

        Args:
            date: chaîne de date
            db_type: type de base de données ("news" ou "rss")

        Returns:
            la clé d'objet distante, par ex. "news/2025-12-28.db" ou "rss/2025-12-28.db"
        """
        date_folder = self._format_date_folder(date)
        return f"{db_type}/{date_folder}.db"

    def _get_local_db_path(self, date: Optional[str] = None, db_type: str = "news") -> Path:
        """
        Récupère le chemin du fichier SQLite temporaire local

        Args:
            date: chaîne de date
            db_type: type de base de données ("news" ou "rss")

        Returns:
            le chemin du fichier temporaire local
        """
        date_folder = self._format_date_folder(date)
        db_dir = self.temp_dir / db_type
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / f"{date_folder}.db"

    def _check_object_exists(self, r2_key: str) -> bool:
        """
        Vérifie si un objet existe dans le stockage distant

        Args:
            r2_key: clé d'objet distante

        Returns:
            True si l'objet existe
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=r2_key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            # Un stockage compatible S3 peut renvoyer 404, NoSuchKey ou d'autres variantes
            if error_code in ("404", "NoSuchKey", "Not Found"):
                return False
            # Les autres erreurs (par ex. problème de permissions) sont aussi considérées comme « inexistant », mais avec un avertissement
            print(f"[stockage distant] échec de la vérification de l'existence de l'objet ({r2_key}) : {e}")
            return False
        except Exception as e:
            print(f"[stockage distant] exception lors de la vérification de l'existence de l'objet ({r2_key}) : {e}")
            return False

    def _download_sqlite(self, date: Optional[str] = None, db_type: str = "news") -> Optional[Path]:
        """
        Télécharge le fichier SQLite du jour depuis le stockage distant vers le répertoire temporaire local

        Utilise get_object + iter_chunks à la place de download_file,
        afin de traiter correctement le chunked transfer encoding de Tencent Cloud COS.

        Args:
            date: chaîne de date
            db_type: type de base de données ("news" ou "rss")

        Returns:
            le chemin du fichier local, ou None si le fichier n'existe pas
        """
        r2_key = self._get_remote_db_key(date, db_type)
        local_path = self._get_local_db_path(date, db_type)

        # Garantit l'existence du répertoire
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Vérifie d'abord si le fichier existe
        if not self._check_object_exists(r2_key):
            print(f"[stockage distant] fichier inexistant, une nouvelle base de données va être créée : {r2_key}")
            return None

        try:
            # Utilise get_object + iter_chunks à la place de download_file
            # iter_chunks traite automatiquement le chunked transfer encoding
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=r2_key)
            with open(local_path, 'wb') as f:
                for chunk in response['Body'].iter_chunks(chunk_size=1024*1024):
                    f.write(chunk)
            self._downloaded_files.append(local_path)
            print(f"[stockage distant] téléchargé : {r2_key} -> {local_path}")
            return local_path
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            # Un stockage compatible S3 peut renvoyer différents codes d'erreur
            if error_code in ("404", "NoSuchKey", "Not Found"):
                print(f"[stockage distant] fichier inexistant, une nouvelle base de données va être créée : {r2_key}")
                return None
            else:
                print(f"[stockage distant] échec du téléchargement (code d'erreur : {error_code}) : {e}")
                raise
        except Exception as e:
            print(f"[stockage distant] exception lors du téléchargement : {e}")
            raise

    def begin_batch(self):
        """Active le mode par lots : envoi différé, pour éviter d'envoyer fréquemment le même fichier"""
        self._batch_mode = True
        self._batch_dirty.clear()

    def end_batch(self):
        """Termine le mode par lots : envoi groupé de toutes les bases de données modifiées"""
        self._batch_mode = False
        for date, db_type in self._batch_dirty:
            self._upload_sqlite(date, db_type)
        self._batch_dirty.clear()

    def _upload_sqlite(self, date: Optional[str] = None, db_type: str = "news") -> bool:
        """
        Envoie le fichier SQLite local vers le stockage distant

        En mode par lots, l'envoi est différé et déclenché de façon groupée par end_batch().

        Args:
            date: chaîne de date
            db_type: type de base de données ("news" ou "rss")

        Returns:
            True si l'envoi a réussi
        """
        if self._batch_mode:
            self._batch_dirty.add((date, db_type))
            return True
        local_path = self._get_local_db_path(date, db_type)
        r2_key = self._get_remote_db_key(date, db_type)

        if not local_path.exists():
            print(f"[stockage distant] fichier local inexistant, envoi impossible : {local_path}")
            return False

        try:
            # Récupère la taille du fichier local
            local_size = local_path.stat().st_size
            print(f"[stockage distant] préparation de l'envoi : {local_path} ({local_size} octets) -> {r2_key}")

            # Lit le contenu du fichier sous forme de bytes avant l'envoi
            # Évite que la bibliothèque requests utilise le chunked transfer encoding lorsqu'on lui passe un objet fichier
            # Des services compatibles S3 comme Tencent Cloud COS peuvent ne pas traiter correctement le chunked encoding
            with open(local_path, 'rb') as f:
                file_content = f.read()

            # Utilise put_object en définissant explicitement ContentLength, pour garantir l'absence de chunked encoding
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=r2_key,
                Body=file_content,
                ContentLength=local_size,
                ContentType='application/x-sqlite3',
            )
            print(f"[stockage distant] envoyé : {local_path} -> {r2_key}")

            # Valide la réussite de l'envoi
            if self._check_object_exists(r2_key):
                print(f"[stockage distant] validation de l'envoi réussie : {r2_key}")
                return True
            else:
                print(f"[stockage distant] échec de la validation de l'envoi : fichier introuvable dans le stockage distant")
                return False

        except Exception as e:
            print(f"[stockage distant] échec de l'envoi : {e}")
            return False

    def _get_connection(self, date: Optional[str] = None, db_type: str = "news") -> sqlite3.Connection:
        """
        Récupère une connexion à la base de données

        Args:
            date: chaîne de date
            db_type: type de base de données ("news" ou "rss")

        Returns:
            une connexion à la base de données
        """
        local_path = self._get_local_db_path(date, db_type)
        db_path = str(local_path)

        if db_path not in self._db_connections:
            # Garantit l'existence du répertoire
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Si le fichier local n'existe pas, tente de le télécharger depuis le stockage distant
            if not local_path.exists():
                self._download_sqlite(date, db_type)

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            self._init_tables(conn, db_type)
            self._db_connections[db_path] = conn

        return self._db_connections[db_path]

    # ========================================
    # Implémentation de l'interface StorageBackend (déléguée au mixin + envoi)
    # ========================================

    def save_news_data(self, data: NewsData) -> bool:
        """
        Enregistre les données d'actualités vers le stockage distant

        Flux : télécharge la base de données existante → insère/met à jour les données → renvoie vers le stockage distant
        """
        # Interroge le nombre d'enregistrements existants
        conn = self._get_connection(data.date)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM news_items")
        row = cursor.fetchone()
        existing_count = row[0] if row else 0
        if existing_count > 0:
            print(f"[stockage distant] {existing_count} enregistrements historiques déjà présents, les nouvelles données vont être fusionnées")

        # Utilise l'implémentation du mixin pour enregistrer les données
        success, new_count, updated_count, title_changed_count, off_list_count = \
            self._save_news_data_impl(data, "[stockage distant]")

        if not success:
            return False

        # Interroge le nombre total d'enregistrements après fusion
        cursor.execute("SELECT COUNT(*) as count FROM news_items")
        row = cursor.fetchone()
        final_count = row[0] if row else 0

        # Affiche un journal détaillé des statistiques de stockage
        log_parts = [f"[stockage distant] traitement terminé : {new_count} nouvelles entrées"]
        if updated_count > 0:
            log_parts.append(f"{updated_count} entrées mises à jour")
        if title_changed_count > 0:
            log_parts.append(f"{title_changed_count} titres modifiés")
        if off_list_count > 0:
            log_parts.append(f"{off_list_count} entrées sorties du classement")
        log_parts.append(f"(total après déduplication : {final_count} entrées)")
        print(", ".join(log_parts))

        # Envoie vers le stockage distant
        if self._upload_sqlite(data.date):
            print(f"[stockage distant] données synchronisées vers le stockage distant")
            return True
        else:
            print(f"[stockage distant] échec de l'envoi vers le stockage distant")
            return False

    def get_today_all_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """Récupère toutes les données d'actualités d'une date donnée (après fusion)"""
        return self._get_today_all_data_impl(date)

    def get_latest_crawl_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """Récupère les données de la collecte la plus récente"""
        return self._get_latest_crawl_data_impl(date)

    def detect_new_titles(self, current_data: NewsData) -> Dict[str, Dict]:
        """Détecte les nouveaux titres"""
        return self._detect_new_titles_impl(current_data)

    def is_first_crawl_today(self, date: Optional[str] = None) -> bool:
        """Vérifie s'il s'agit de la première collecte du jour"""
        return self._is_first_crawl_today_impl(date)

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
            print(f"[stockage distant] enregistrement d'exécution de tranche horaire sauvegardé : {period_key}/{action} à {now_str}")

            # Envoie vers le stockage distant pour garantir la persistance de l'enregistrement
            if self._upload_sqlite(date_str):
                print(f"[stockage distant] enregistrement d'exécution de tranche horaire synchronisé vers le stockage distant")
                return True
            else:
                print(f"[stockage distant] échec de la synchronisation de l'enregistrement d'exécution de tranche horaire vers le stockage distant")
                return False

        return False

    # ========================================
    # Méthodes de stockage des données RSS
    # ========================================

    def save_rss_data(self, data: RSSData) -> bool:
        """
        Enregistre les données RSS vers le stockage distant

        Flux : télécharge la base de données existante → insère/met à jour les données → renvoie vers le stockage distant
        """
        success, new_count, updated_count = self._save_rss_data_impl(data, "[stockage distant]")

        if not success:
            return False

        # Affiche le journal des statistiques
        log_parts = [f"[stockage distant] traitement RSS terminé : {new_count} nouvelles entrées"]
        if updated_count > 0:
            log_parts.append(f"{updated_count} entrées mises à jour")
        print(", ".join(log_parts))

        # Envoie vers le stockage distant
        if self._upload_sqlite(data.date, db_type="rss"):
            print(f"[stockage distant] données RSS synchronisées vers le stockage distant")
            return True
        else:
            print(f"[stockage distant] échec de l'envoi RSS vers le stockage distant")
            return False

    def get_rss_data(self, date: Optional[str] = None) -> Optional[RSSData]:
        """Récupère toutes les données RSS d'une date donnée"""
        return self._get_rss_data_impl(date)

    def detect_new_rss_items(self, current_data: RSSData) -> Dict[str, List[RSSItem]]:
        """Détecte les nouvelles entrées RSS"""
        return self._detect_new_rss_items_impl(current_data)

    def get_latest_rss_data(self, date: Optional[str] = None) -> Optional[RSSData]:
        """Récupère les données RSS de la collecte la plus récente"""
        return self._get_latest_rss_data_impl(date)

    # ========================================
    # Méthodes de stockage du filtrage intelligent par IA
    # ========================================

    def get_active_ai_filter_tags(self, date=None, interests_file="ai_interests.txt"):
        return self._get_active_tags_impl(date, interests_file)

    def get_latest_prompt_hash(self, date=None, interests_file="ai_interests.txt"):
        return self._get_latest_prompt_hash_impl(date, interests_file)

    def get_latest_ai_filter_tag_version(self, date=None):
        return self._get_latest_tag_version_impl(date)

    def deprecate_all_ai_filter_tags(self, date=None, interests_file="ai_interests.txt"):
        count = self._deprecate_all_tags_impl(date, interests_file)
        if count > 0:
            self._upload_sqlite(date)
        return count

    def save_ai_filter_tags(self, tags, version, prompt_hash, date=None, interests_file="ai_interests.txt"):
        count = self._save_tags_impl(date, tags, version, prompt_hash, interests_file)
        if count > 0:
            self._upload_sqlite(date)
        return count

    def save_ai_filter_results(self, results, date=None):
        count = self._save_filter_results_impl(date, results)
        if count > 0:
            self._upload_sqlite(date)
        return count

    def get_active_ai_filter_results(self, date=None, interests_file="ai_interests.txt"):
        return self._get_active_filter_results_impl(date, interests_file)

    def deprecate_specific_ai_filter_tags(self, tag_ids, date=None):
        count = self._deprecate_specific_tags_impl(date, tag_ids)
        if count > 0:
            self._upload_sqlite(date)
        return count

    def update_ai_filter_tags_hash(self, interests_file, new_hash, date=None):
        count = self._update_tags_hash_impl(date, interests_file, new_hash)
        if count > 0:
            self._upload_sqlite(date)
        return count

    def update_ai_filter_tag_descriptions(self, tag_updates, date=None, interests_file="ai_interests.txt"):
        count = self._update_tag_descriptions_impl(date, tag_updates, interests_file)
        if count > 0:
            self._upload_sqlite(date)
        return count

    def update_ai_filter_tag_priorities(self, tag_priorities, date=None, interests_file="ai_interests.txt"):
        count = self._update_tag_priorities_impl(date, tag_priorities, interests_file)
        if count > 0:
            self._upload_sqlite(date)
        return count

    def save_analyzed_news(self, news_ids, source_type, interests_file, prompt_hash, matched_ids, date=None):
        count = self._save_analyzed_news_impl(date, news_ids, source_type, interests_file, prompt_hash, matched_ids)
        if count > 0:
            self._upload_sqlite(date)
        return count

    def get_analyzed_news_ids(self, source_type="hotlist", date=None, interests_file="ai_interests.txt"):
        return self._get_analyzed_news_ids_impl(date, source_type, interests_file)

    def clear_analyzed_news(self, date=None, interests_file="ai_interests.txt"):
        count = self._clear_analyzed_news_impl(date, interests_file)
        if count > 0:
            self._upload_sqlite(date)
        return count

    def clear_unmatched_analyzed_news(self, date=None, interests_file="ai_interests.txt"):
        count = self._clear_unmatched_analyzed_news_impl(date, interests_file)
        if count > 0:
            self._upload_sqlite(date)
        return count

    def get_all_news_ids(self, date=None):
        return self._get_all_news_ids_impl(date)

    def get_all_rss_ids(self, date=None):
        return self._get_all_rss_ids_impl(date)

    # ========================================
    # Fonctionnalités propres au stockage distant : instantanés TXT/HTML (répertoire temporaire)
    # ========================================

    def save_txt_snapshot(self, data: NewsData) -> Optional[str]:
        """Enregistre un instantané TXT (non pris en charge par défaut en mode stockage distant)"""
        if not self.enable_txt:
            return None

        # S'il est activé, enregistre dans le répertoire temporaire local
        try:
            date_folder = self._format_date_folder(data.date)
            txt_dir = self.temp_dir / date_folder / "txt"
            txt_dir.mkdir(parents=True, exist_ok=True)

            file_path = txt_dir / f"{data.crawl_time}.txt"

            with open(file_path, "w", encoding="utf-8") as f:
                for source_id, news_list in data.items.items():
                    source_name = data.id_to_name.get(source_id, source_id)

                    if source_name and source_name != source_id:
                        f.write(f"{source_id} | {source_name}\n")
                    else:
                        f.write(f"{source_id}\n")

                    sorted_news = sorted(news_list, key=lambda x: x.rank)

                    for item in sorted_news:
                        line = f"{item.rank}. {item.title}"
                        if item.url:
                            line += f" [URL:{item.url}]"
                        if item.mobile_url:
                            line += f" [MOBILE:{item.mobile_url}]"
                        f.write(line + "\n")

                    f.write("\n")

                if data.failed_ids:
                    f.write("==== Échec de la requête pour les ID suivants ====\n")
                    for failed_id in data.failed_ids:
                        f.write(f"{failed_id}\n")

            print(f"[stockage distant] instantané TXT enregistré : {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[stockage distant] échec de l'enregistrement de l'instantané TXT : {e}")
            return None

    def save_html_report(self, html_content: str, filename: str) -> Optional[str]:
        """Enregistre un rapport HTML dans le répertoire temporaire"""
        if not self.enable_html:
            return None

        try:
            date_folder = self._format_date_folder()
            html_dir = self.temp_dir / date_folder / "html"
            html_dir.mkdir(parents=True, exist_ok=True)

            file_path = html_dir / filename

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"[stockage distant] rapport HTML enregistré : {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[stockage distant] échec de l'enregistrement du rapport HTML : {e}")
            return None

    # ========================================
    # Fonctionnalités propres au stockage distant : libération des ressources
    # ========================================

    def cleanup(self) -> None:
        """Libère les ressources (ferme les connexions et supprime les fichiers temporaires)"""
        # Vérifie si Python est en cours d'arrêt
        if sys.meta_path is None:
            return

        # Ferme les connexions à la base de données
        db_connections = getattr(self, "_db_connections", {})
        for db_path, conn in list(db_connections.items()):
            try:
                conn.close()
                print(f"[stockage distant] fermeture de la connexion à la base de données : {db_path}")
            except Exception as e:
                print(f"[stockage distant] échec de la fermeture de la connexion {db_path} : {e}")

        if db_connections:
            db_connections.clear()

        # Supprime le répertoire temporaire
        temp_dir = getattr(self, "temp_dir", None)
        if temp_dir:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    print(f"[stockage distant] répertoire temporaire nettoyé : {temp_dir}")
            except Exception as e:
                # Ignore les erreurs survenant pendant l'arrêt de Python
                if sys.meta_path is not None:
                    print(f"[stockage distant] échec du nettoyage du répertoire temporaire : {e}")

        downloaded_files = getattr(self, "_downloaded_files", None)
        if downloaded_files:
            downloaded_files.clear()

    def cleanup_old_data(self, retention_days: int) -> int:
        """
        Nettoie les données expirées dans le stockage distant

        Args:
            retention_days: nombre de jours de conservation (0 signifie pas de nettoyage)

        Returns:
            le nombre de fichiers de base de données supprimés
        """
        if retention_days <= 0:
            return 0

        deleted_count = 0
        cutoff_date = self._get_configured_time() - timedelta(days=retention_days)

        try:
            # Liste tous les objets sous le préfixe news/ dans le stockage distant
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix="news/")

            # Rassemble les clés d'objets à supprimer
            objects_to_delete = []
            deleted_dates = set()

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    key = obj['Key']

                    # Analyse la date (format : news/YYYY-MM-DD.db)
                    folder_date = None
                    date_str = None
                    try:
                        date_match = re.match(r'news/(\d{4})-(\d{2})-(\d{2})\.db$', key)
                        if date_match:
                            folder_date = datetime(
                                int(date_match.group(1)),
                                int(date_match.group(2)),
                                int(date_match.group(3)),
                                tzinfo=pytz.timezone(self.timezone)
                            )
                            date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                    except Exception:
                        continue

                    if folder_date and folder_date < cutoff_date:
                        objects_to_delete.append({'Key': key})
                        deleted_dates.add(date_str)

            # Supprime les objets par lots (au plus 1000 à la fois)
            if objects_to_delete:
                batch_size = 1000
                for i in range(0, len(objects_to_delete), batch_size):
                    batch = objects_to_delete[i:i + batch_size]
                    try:
                        self.s3_client.delete_objects(
                            Bucket=self.bucket_name,
                            Delete={'Objects': batch}
                        )
                        print(f"[stockage distant] {len(batch)} objets supprimés")
                    except Exception as e:
                        print(f"[stockage distant] échec de la suppression par lots : {e}")

                deleted_count = len(deleted_dates)
                for date_str in sorted(deleted_dates):
                    print(f"[stockage distant] nettoyage des données expirées : news/{date_str}.db")

                print(f"[stockage distant] {deleted_count} fichiers de base de données de dates expirées nettoyés au total")

            return deleted_count

        except Exception as e:
            print(f"[stockage distant] échec du nettoyage des données expirées : {e}")
            return deleted_count

    def __del__(self):
        """Destructeur"""
        # Vérifie si Python est en cours d'arrêt
        if sys.meta_path is None:
            return
        try:
            self.cleanup()
        except Exception:
            # Une erreur peut survenir pendant l'arrêt de Python, on l'ignore
            pass

    # ========================================
    # Fonctionnalités propres au stockage distant : téléchargement et listage des données
    # ========================================

    def pull_recent_days(self, days: int, local_data_dir: str = "output") -> int:
        """
        Télécharge les données des N derniers jours depuis le stockage distant vers le stockage local

        Args:
            days: nombre de jours à télécharger
            local_data_dir: répertoire de données local

        Returns:
            le nombre de fichiers de base de données téléchargés avec succès
        """
        if days <= 0:
            return 0

        local_dir = Path(local_data_dir)
        local_dir.mkdir(parents=True, exist_ok=True)

        pulled_count = 0
        now = self._get_configured_time()

        print(f"[stockage distant] début du téléchargement des données des {days} derniers jours...")

        for i in range(days):
            date = now - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")

            # Chemin cible local
            local_date_dir = local_dir / date_str
            local_db_path = local_date_dir / "news.db"

            # Si le fichier local existe déjà, on l'ignore
            if local_db_path.exists():
                print(f"[stockage distant] ignoré (déjà présent en local) : {date_str}")
                continue

            # Clé d'objet distante
            remote_key = f"news/{date_str}.db"

            # Vérifie si l'objet existe à distance
            if not self._check_object_exists(remote_key):
                print(f"[stockage distant] ignoré (inexistant à distance) : {date_str}")
                continue

            # Télécharge (utilise get_object + iter_chunks pour traiter le chunked encoding)
            try:
                local_date_dir.mkdir(parents=True, exist_ok=True)
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=remote_key)
                with open(local_db_path, 'wb') as f:
                    for chunk in response['Body'].iter_chunks(chunk_size=1024*1024):
                        f.write(chunk)
                print(f"[stockage distant] téléchargé : {remote_key} -> {local_db_path}")
                pulled_count += 1
            except Exception as e:
                print(f"[stockage distant] échec du téléchargement ({date_str}) : {e}")

        print(f"[stockage distant] téléchargement terminé, {pulled_count} fichiers de base de données téléchargés au total")
        return pulled_count

    def list_remote_dates(self) -> List[str]:
        """
        Liste toutes les dates disponibles dans le stockage distant

        Returns:
            une liste de chaînes de dates (format YYYY-MM-DD)
        """
        dates = []

        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix="news/")

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    key = obj['Key']
                    # Analyse la date
                    date_match = re.match(r'news/(\d{4}-\d{2}-\d{2})\.db$', key)
                    if date_match:
                        dates.append(date_match.group(1))

            return sorted(dates, reverse=True)

        except Exception as e:
            print(f"[stockage distant] échec du listage des dates distantes : {e}")
            return []
