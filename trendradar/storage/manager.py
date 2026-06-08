# coding=utf-8
"""
Gestionnaire de stockage - gestion unifiée des backends de stockage

Sélectionne automatiquement le backend de stockage approprié selon l'environnement et la configuration
"""

import os
from typing import Optional

from trendradar.storage.base import StorageBackend, NewsData, RSSData
from trendradar.utils.time import DEFAULT_TIMEZONE


# Singleton du gestionnaire de stockage
_storage_manager: Optional["StorageManager"] = None


class StorageManager:
    """
    Gestionnaire de stockage

    Fonctionnalités :
    - détection automatique de l'environnement d'exécution (GitHub Actions / Docker / local)
    - sélection du backend de stockage selon la configuration (local / remote / auto)
    - fourniture d'une interface de stockage unifiée
    - prise en charge du téléchargement des données distantes vers le stockage local
    """

    def __init__(
        self,
        backend_type: str = "auto",
        data_dir: str = "output",
        enable_txt: bool = True,
        enable_html: bool = True,
        remote_config: Optional[dict] = None,
        local_retention_days: int = 0,
        remote_retention_days: int = 0,
        pull_enabled: bool = False,
        pull_days: int = 0,
        timezone: str = DEFAULT_TIMEZONE,
    ):
        """
        Initialise le gestionnaire de stockage

        Args:
            backend_type: type de backend de stockage (local / remote / auto)
            data_dir: répertoire de données local
            enable_txt: activer ou non les instantanés TXT
            enable_html: activer ou non les rapports HTML
            remote_config: configuration du stockage distant (endpoint_url, bucket_name, access_key_id, etc.)
            local_retention_days: nombre de jours de conservation des données locales (0 = illimité)
            remote_retention_days: nombre de jours de conservation des données distantes (0 = illimité)
            pull_enabled: activer ou non le téléchargement automatique au démarrage
            pull_days: télécharger les données des N derniers jours
            timezone: configuration du fuseau horaire
        """
        self.backend_type = backend_type
        self.data_dir = data_dir
        self.enable_txt = enable_txt
        self.enable_html = enable_html
        self.remote_config = remote_config or {}
        self.local_retention_days = local_retention_days
        self.remote_retention_days = remote_retention_days
        self.pull_enabled = pull_enabled
        self.pull_days = pull_days
        self.timezone = timezone

        self._backend: Optional[StorageBackend] = None
        self._remote_backend: Optional[StorageBackend] = None

    @staticmethod
    def is_github_actions() -> bool:
        """Détecte si l'exécution a lieu dans un environnement GitHub Actions"""
        return os.environ.get("GITHUB_ACTIONS") == "true"

    @staticmethod
    def is_docker() -> bool:
        """Détecte si l'exécution a lieu dans un conteneur Docker"""
        # Méthode 1 : vérifier le fichier /.dockerenv
        if os.path.exists("/.dockerenv"):
            return True

        # Méthode 2 : vérifier le cgroup (Linux)
        try:
            with open("/proc/1/cgroup", "r") as f:
                return "docker" in f.read()
        except (FileNotFoundError, PermissionError):
            pass

        # Méthode 3 : vérifier la variable d'environnement
        return os.environ.get("DOCKER_CONTAINER") == "true"

    def _resolve_backend_type(self) -> str:
        """Détermine le type de backend réellement utilisé"""
        if self.backend_type == "auto":
            if self.is_github_actions():
                # Environnement GitHub Actions : vérifie si le stockage distant est configuré
                if self._has_remote_config():
                    return "remote"
                else:
                    print("[gestionnaire de stockage] environnement GitHub Actions sans stockage distant configuré, utilisation du stockage local")
                    return "local"
            else:
                return "local"
        return self.backend_type

    def _has_remote_config(self) -> bool:
        """Vérifie s'il existe une configuration de stockage distant valide"""
        # Vérifie la configuration ou les variables d'environnement
        bucket_name = self.remote_config.get("bucket_name") or os.environ.get("S3_BUCKET_NAME")
        access_key = self.remote_config.get("access_key_id") or os.environ.get("S3_ACCESS_KEY_ID")
        secret_key = self.remote_config.get("secret_access_key") or os.environ.get("S3_SECRET_ACCESS_KEY")
        endpoint = self.remote_config.get("endpoint_url") or os.environ.get("S3_ENDPOINT_URL")

        # Journal de débogage
        has_config = bool(bucket_name and access_key and secret_key and endpoint)
        if not has_config:
            print(f"[gestionnaire de stockage] échec de la vérification de la configuration du stockage distant :")
            print(f"  - bucket_name: {'configuré' if bucket_name else 'non configuré'}")
            print(f"  - access_key_id: {'configuré' if access_key else 'non configuré'}")
            print(f"  - secret_access_key: {'configuré' if secret_key else 'non configuré'}")
            print(f"  - endpoint_url: {'configuré' if endpoint else 'non configuré'}")

        return has_config

    def _create_remote_backend(self) -> Optional[StorageBackend]:
        """Crée le backend de stockage distant"""
        try:
            from trendradar.storage.remote import RemoteStorageBackend

            return RemoteStorageBackend(
                bucket_name=self.remote_config.get("bucket_name") or os.environ.get("S3_BUCKET_NAME", ""),
                access_key_id=self.remote_config.get("access_key_id") or os.environ.get("S3_ACCESS_KEY_ID", ""),
                secret_access_key=self.remote_config.get("secret_access_key") or os.environ.get("S3_SECRET_ACCESS_KEY", ""),
                endpoint_url=self.remote_config.get("endpoint_url") or os.environ.get("S3_ENDPOINT_URL", ""),
                region=self.remote_config.get("region") or os.environ.get("S3_REGION", ""),
                enable_txt=self.enable_txt,
                enable_html=self.enable_html,
                timezone=self.timezone,
            )
        except ImportError as e:
            print(f"[gestionnaire de stockage] échec de l'import du backend distant : {e}")
            print("[gestionnaire de stockage] veuillez vérifier que boto3 est installé : pip install boto3")
            return None
        except Exception as e:
            print(f"[gestionnaire de stockage] échec de l'initialisation du backend distant : {e}")
            return None

    def get_backend(self) -> StorageBackend:
        """Récupère l'instance du backend de stockage"""
        if self._backend is None:
            resolved_type = self._resolve_backend_type()

            if resolved_type == "remote":
                self._backend = self._create_remote_backend()
                if self._backend:
                    print(f"[gestionnaire de stockage] utilisation du backend de stockage distant")
                else:
                    print("[gestionnaire de stockage] repli sur le stockage local")
                    resolved_type = "local"

            if resolved_type == "local" or self._backend is None:
                from trendradar.storage.local import LocalStorageBackend

                self._backend = LocalStorageBackend(
                    data_dir=self.data_dir,
                    enable_txt=self.enable_txt,
                    enable_html=self.enable_html,
                    timezone=self.timezone,
                )
                print(f"[gestionnaire de stockage] utilisation du backend de stockage local (répertoire de données : {self.data_dir})")

        return self._backend

    def pull_from_remote(self) -> int:
        """
        Télécharge les données distantes vers le stockage local

        Returns:
            le nombre de fichiers téléchargés avec succès
        """
        if not self.pull_enabled or self.pull_days <= 0:
            return 0

        if not self._has_remote_config():
            print("[gestionnaire de stockage] stockage distant non configuré, téléchargement impossible")
            return 0

        # Crée le backend distant (s'il n'existe pas encore)
        if self._remote_backend is None:
            self._remote_backend = self._create_remote_backend()

        if self._remote_backend is None:
            print("[gestionnaire de stockage] impossible de créer le backend distant, échec du téléchargement")
            return 0

        # Appelle la méthode de téléchargement
        return self._remote_backend.pull_recent_days(self.pull_days, self.data_dir)

    def save_news_data(self, data: NewsData) -> bool:
        """Enregistre les données d'actualités"""
        return self.get_backend().save_news_data(data)

    def save_rss_data(self, data: RSSData) -> bool:
        """Enregistre les données RSS"""
        return self.get_backend().save_rss_data(data)

    def get_rss_data(self, date: Optional[str] = None) -> Optional[RSSData]:
        """Récupère toutes les données RSS d'une date donnée (mode synthèse du jour)"""
        return self.get_backend().get_rss_data(date)

    def get_latest_rss_data(self, date: Optional[str] = None) -> Optional[RSSData]:
        """Récupère les données RSS de la collecte la plus récente (mode classement actuel)"""
        return self.get_backend().get_latest_rss_data(date)

    def detect_new_rss_items(self, current_data: RSSData) -> dict:
        """Détecte les nouvelles entrées RSS (mode incrémental)"""
        return self.get_backend().detect_new_rss_items(current_data)

    def get_today_all_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """Récupère toutes les données du jour"""
        return self.get_backend().get_today_all_data(date)

    def get_latest_crawl_data(self, date: Optional[str] = None) -> Optional[NewsData]:
        """Récupère les données de la collecte la plus récente"""
        return self.get_backend().get_latest_crawl_data(date)

    def detect_new_titles(self, current_data: NewsData) -> dict:
        """Détecte les nouveaux titres"""
        return self.get_backend().detect_new_titles(current_data)

    def save_txt_snapshot(self, data: NewsData) -> Optional[str]:
        """Enregistre un instantané TXT"""
        return self.get_backend().save_txt_snapshot(data)

    def save_html_report(self, html_content: str, filename: str) -> Optional[str]:
        """Enregistre un rapport HTML"""
        return self.get_backend().save_html_report(html_content, filename)

    def is_first_crawl_today(self, date: Optional[str] = None) -> bool:
        """Vérifie s'il s'agit de la première collecte du jour"""
        return self.get_backend().is_first_crawl_today(date)

    def cleanup(self) -> None:
        """Libère les ressources"""
        if self._backend:
            self._backend.cleanup()
        if self._remote_backend:
            self._remote_backend.cleanup()

    def cleanup_old_data(self) -> int:
        """
        Nettoie les données expirées

        Returns:
            le nombre de répertoires de dates supprimés
        """
        total_deleted = 0

        # Nettoie les données locales
        if self.local_retention_days > 0:
            total_deleted += self.get_backend().cleanup_old_data(self.local_retention_days)

        # Nettoie les données distantes (si configurées)
        if self.remote_retention_days > 0 and self._has_remote_config():
            if self._remote_backend is None:
                self._remote_backend = self._create_remote_backend()
            if self._remote_backend:
                total_deleted += self._remote_backend.cleanup_old_data(self.remote_retention_days)

        return total_deleted

    @property
    def backend_name(self) -> str:
        """Récupère le nom du backend actuel"""
        return self.get_backend().backend_name

    @property
    def supports_txt(self) -> bool:
        """Indique si les instantanés TXT sont pris en charge"""
        return self.get_backend().supports_txt

    def has_period_executed(self, date_str: str, period_key: str, action: str) -> bool:
        """Vérifie si une action donnée a déjà été exécutée pour une tranche horaire donnée"""
        return self.get_backend().has_period_executed(date_str, period_key, action)

    def record_period_execution(self, date_str: str, period_key: str, action: str) -> bool:
        """Enregistre l'exécution d'une action pour une tranche horaire"""
        return self.get_backend().record_period_execution(date_str, period_key, action)

    # === Opérations de stockage du filtrage intelligent par IA ===

    def begin_batch(self):
        """Active le mode par lots (le backend distant diffère l'envoi)"""
        self.get_backend().begin_batch()

    def end_batch(self):
        """Termine le mode par lots (envoi groupé des bases de données modifiées)"""
        self.get_backend().end_batch()

    def get_active_ai_filter_tags(self, date=None, interests_file="ai_interests.txt"):
        """Récupère les étiquettes actives d'un fichier de centres d'intérêt donné"""
        return self.get_backend().get_active_ai_filter_tags(date, interests_file)

    def get_latest_prompt_hash(self, date=None, interests_file="ai_interests.txt"):
        """Récupère le dernier prompt_hash d'un fichier de centres d'intérêt donné"""
        return self.get_backend().get_latest_prompt_hash(date, interests_file)

    def get_latest_ai_filter_tag_version(self, date=None):
        """Récupère le numéro de la dernière version des étiquettes"""
        return self.get_backend().get_latest_ai_filter_tag_version(date)

    def deprecate_all_ai_filter_tags(self, date=None, interests_file="ai_interests.txt"):
        """Rend obsolètes les étiquettes actives et les résultats de classification d'un fichier de centres d'intérêt donné"""
        return self.get_backend().deprecate_all_ai_filter_tags(date, interests_file)

    def save_ai_filter_tags(self, tags, version, prompt_hash, date=None, interests_file="ai_interests.txt"):
        """Enregistre les étiquettes nouvellement extraites"""
        return self.get_backend().save_ai_filter_tags(tags, version, prompt_hash, date, interests_file)

    def save_ai_filter_results(self, results, date=None):
        """Enregistre les résultats de classification"""
        return self.get_backend().save_ai_filter_results(results, date)

    def get_active_ai_filter_results(self, date=None, interests_file="ai_interests.txt"):
        """Récupère les résultats de classification actifs d'un fichier de centres d'intérêt donné"""
        return self.get_backend().get_active_ai_filter_results(date, interests_file)

    def deprecate_specific_ai_filter_tags(self, tag_ids, date=None):
        """Rend obsolètes les étiquettes des ID donnés ainsi que leurs résultats de classification associés"""
        return self.get_backend().deprecate_specific_ai_filter_tags(tag_ids, date)

    def update_ai_filter_tags_hash(self, interests_file, new_hash, date=None):
        """Met à jour le prompt_hash de toutes les étiquettes actives d'un fichier de centres d'intérêt donné"""
        return self.get_backend().update_ai_filter_tags_hash(interests_file, new_hash, date)

    def update_ai_filter_tag_descriptions(self, tag_updates, date=None, interests_file="ai_interests.txt"):
        """Met à jour la description des étiquettes actives, par correspondance sur le nom du tag"""
        return self.get_backend().update_ai_filter_tag_descriptions(tag_updates, date, interests_file)

    def update_ai_filter_tag_priorities(self, tag_priorities, date=None, interests_file="ai_interests.txt"):
        """Met à jour la priorité des étiquettes actives, par correspondance sur le nom du tag"""
        return self.get_backend().update_ai_filter_tag_priorities(tag_priorities, date, interests_file)

    def save_analyzed_news(self, news_ids, source_type, interests_file, prompt_hash, matched_ids, date=None):
        """Enregistre en masse les actualités déjà analysées (les correspondances comme les non-correspondances sont enregistrées)"""
        return self.get_backend().save_analyzed_news(news_ids, source_type, interests_file, prompt_hash, matched_ids, date)

    def get_analyzed_news_ids(self, source_type="hotlist", date=None, interests_file="ai_interests.txt"):
        """Récupère l'ensemble des ID d'actualités déjà analysées"""
        return self.get_backend().get_analyzed_news_ids(source_type, date, interests_file)

    def clear_analyzed_news(self, date=None, interests_file="ai_interests.txt"):
        """Efface tous les enregistrements d'analyse d'un fichier de centres d'intérêt donné"""
        return self.get_backend().clear_analyzed_news(date, interests_file)

    def clear_unmatched_analyzed_news(self, date=None, interests_file="ai_interests.txt"):
        """Efface les enregistrements d'analyse sans correspondance"""
        return self.get_backend().clear_unmatched_analyzed_news(date, interests_file)

    def get_all_news_ids(self, date=None):
        """Récupère tous les ID et titres d'actualités"""
        return self.get_backend().get_all_news_ids(date)

    def get_all_rss_ids(self, date=None):
        """Récupère tous les ID et titres RSS"""
        return self.get_backend().get_all_rss_ids(date)



def get_storage_manager(
    backend_type: str = "auto",
    data_dir: str = "output",
    enable_txt: bool = True,
    enable_html: bool = True,
    remote_config: Optional[dict] = None,
    local_retention_days: int = 0,
    remote_retention_days: int = 0,
    pull_enabled: bool = False,
    pull_days: int = 0,
    timezone: str = DEFAULT_TIMEZONE,
    force_new: bool = False,
) -> StorageManager:
    """
    Récupère le singleton du gestionnaire de stockage

    Args:
        backend_type: type de backend de stockage
        data_dir: répertoire de données local
        enable_txt: activer ou non les instantanés TXT
        enable_html: activer ou non les rapports HTML
        remote_config: configuration du stockage distant
        local_retention_days: nombre de jours de conservation des données locales (0 = illimité)
        remote_retention_days: nombre de jours de conservation des données distantes (0 = illimité)
        pull_enabled: activer ou non le téléchargement automatique au démarrage
        pull_days: télécharger les données des N derniers jours
        timezone: configuration du fuseau horaire
        force_new: forcer ou non la création d'une nouvelle instance

    Returns:
        une instance de StorageManager
    """
    global _storage_manager

    if _storage_manager is None or force_new:
        _storage_manager = StorageManager(
            backend_type=backend_type,
            data_dir=data_dir,
            enable_txt=enable_txt,
            enable_html=enable_html,
            remote_config=remote_config,
            local_retention_days=local_retention_days,
            remote_retention_days=remote_retention_days,
            pull_enabled=pull_enabled,
            pull_days=pull_days,
            timezone=timezone,
        )

    return _storage_manager
