# coding=utf-8
"""
Outils de synchronisation du stockage

Implémente la récupération des données du stockage distant vers le local, la consultation de l'état du stockage, la liste des dates disponibles, etc.
"""

import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import yaml

from ..utils.errors import MCPError


class StorageSyncTools:
    """Classe des outils de synchronisation du stockage"""

    def __init__(self, project_root: str = None):
        """
        Initialise les outils de synchronisation du stockage

        Args:
            project_root: répertoire racine du projet
        """
        if project_root:
            self.project_root = Path(project_root)
        else:
            current_file = Path(__file__)
            self.project_root = current_file.parent.parent.parent

        self._config = None
        self._remote_backend = None

    def _load_config(self) -> dict:
        """Charge le fichier de configuration"""
        if self._config is None:
            config_path = self.project_root / "config" / "config.yaml"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f)
            else:
                self._config = {}
        return self._config

    def _get_storage_config(self) -> dict:
        """Récupère la configuration du stockage"""
        config = self._load_config()
        return config.get("storage", {})

    def _get_remote_config(self) -> dict:
        """
        Récupère la configuration du stockage distant (fusion du fichier de configuration et des variables d'environnement)
        """
        storage_config = self._get_storage_config()
        remote_config = storage_config.get("remote", {})

        return {
            "endpoint_url": remote_config.get("endpoint_url") or os.environ.get("S3_ENDPOINT_URL", ""),
            "bucket_name": remote_config.get("bucket_name") or os.environ.get("S3_BUCKET_NAME", ""),
            "access_key_id": remote_config.get("access_key_id") or os.environ.get("S3_ACCESS_KEY_ID", ""),
            "secret_access_key": remote_config.get("secret_access_key") or os.environ.get("S3_SECRET_ACCESS_KEY", ""),
            "region": remote_config.get("region") or os.environ.get("S3_REGION", ""),
        }

    def _has_remote_config(self) -> bool:
        """Vérifie s'il existe une configuration de stockage distant valide"""
        config = self._get_remote_config()
        return bool(
            config.get("bucket_name") and
            config.get("access_key_id") and
            config.get("secret_access_key") and
            config.get("endpoint_url")
        )

    def _get_remote_backend(self):
        """Récupère l'instance du backend de stockage distant"""
        if self._remote_backend is not None:
            return self._remote_backend

        if not self._has_remote_config():
            return None

        try:
            from trendradar.storage.remote import RemoteStorageBackend

            remote_config = self._get_remote_config()
            config = self._load_config()
            timezone = config.get("app", {}).get("timezone", "Asia/Shanghai")

            self._remote_backend = RemoteStorageBackend(
                bucket_name=remote_config["bucket_name"],
                access_key_id=remote_config["access_key_id"],
                secret_access_key=remote_config["secret_access_key"],
                endpoint_url=remote_config["endpoint_url"],
                region=remote_config.get("region", ""),
                timezone=timezone,
            )
            return self._remote_backend
        except ImportError:
            print("[Synchronisation du stockage] Le backend de stockage distant nécessite boto3 : pip install boto3")
            return None
        except Exception as e:
            print(f"[Synchronisation du stockage] Échec de la création du backend distant : {e}")
            return None

    def _get_local_data_dir(self) -> Path:
        """Récupère le répertoire de données local"""
        storage_config = self._get_storage_config()
        local_config = storage_config.get("local", {})
        data_dir = local_config.get("data_dir", "output")
        return self.project_root / data_dir

    def _parse_date_folder_name(self, folder_name: str) -> Optional[datetime]:
        """
        Analyse le nom d'un dossier de date (format ISO)

        Format pris en charge :
        - format ISO : YYYY-MM-DD
        """
        # Essaie le format ISO
        iso_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', folder_name)
        if iso_match:
            try:
                return datetime(
                    int(iso_match.group(1)),
                    int(iso_match.group(2)),
                    int(iso_match.group(3))
                )
            except ValueError:
                pass

        return None

    def _get_local_dates(self, db_type: str = "news") -> List[str]:
        """
        Récupère la liste des dates disponibles localement

        Structure de stockage : output/{db_type}/{date}.db
        Par exemple : output/news/2025-12-30.db, output/rss/2025-12-30.db

        Args:
            db_type: type de base de données ("news" ou "rss"), "news" par défaut

        Returns:
            liste des dates (ordre chronologique décroissant)
        """
        local_dir = self._get_local_data_dir()
        dates = set()

        if not local_dir.exists():
            return []

        # Parcourt les fichiers output/{db_type}/{date}.db
        type_dir = local_dir / db_type
        if type_dir.exists():
            for item in type_dir.iterdir():
                if item.is_file() and item.suffix == ".db":
                    # Analyse la date à partir du nom de fichier (2025-12-30.db -> 2025-12-30)
                    date_str = item.stem  # Retire le suffixe .db
                    folder_date = self._parse_date_folder_name(date_str)
                    if folder_date:
                        dates.add(folder_date.strftime("%Y-%m-%d"))

        return sorted(list(dates), reverse=True)

    def _get_all_local_dates(self) -> Dict[str, List[str]]:
        """
        Récupère toutes les dates disponibles localement (y compris news et rss)

        Returns:
            {
                "news": ["2025-12-30", ...],
                "rss": ["2025-12-30", ...],
                "all": ["2025-12-30", ...]  # Fusion dédupliquée
            }
        """
        news_dates = set(self._get_local_dates("news"))
        rss_dates = set(self._get_local_dates("rss"))
        all_dates = news_dates | rss_dates

        return {
            "news": sorted(list(news_dates), reverse=True),
            "rss": sorted(list(rss_dates), reverse=True),
            "all": sorted(list(all_dates), reverse=True)
        }

    def _calculate_dir_size(self, path: Path) -> int:
        """Calcule la taille d'un répertoire (octets)"""
        total_size = 0
        if path.exists():
            for item in path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
        return total_size

    def sync_from_remote(self, days: int = 7) -> Dict:
        """
        Récupère les données du stockage distant vers le local

        Args:
            days: récupère les données des N derniers jours, 7 jours par défaut

        Returns:
            dictionnaire du résultat de synchronisation
        """
        try:
            # Vérifie la configuration distante
            if not self._has_remote_config():
                return {
                    "success": False,
                    "error": {
                        "code": "REMOTE_NOT_CONFIGURED",
                        "message": "Stockage distant non configuré",
                        "suggestion": "Veuillez configurer storage.remote dans config/config.yaml ou définir les variables d'environnement"
                    }
                }

            # Récupère le backend distant
            remote_backend = self._get_remote_backend()
            if remote_backend is None:
                return {
                    "success": False,
                    "error": {
                        "code": "REMOTE_BACKEND_FAILED",
                        "message": "Impossible de créer le backend de stockage distant",
                        "suggestion": "Veuillez vérifier la configuration du stockage distant et que boto3 est installé"
                    }
                }

            # Récupère le répertoire de données local
            local_dir = self._get_local_data_dir()
            local_dir.mkdir(parents=True, exist_ok=True)

            # Récupère les dates disponibles à distance
            remote_dates = remote_backend.list_remote_dates()

            # Récupère les dates déjà présentes localement
            local_dates = set(self._get_local_dates())

            # Calcule les dates à récupérer (les N derniers jours)
            from trendradar.utils.time import get_configured_time
            config = self._load_config()
            timezone = config.get("app", {}).get("timezone", "Asia/Shanghai")
            now = get_configured_time(timezone)

            target_dates = []
            for i in range(days):
                date = now - timedelta(days=i)
                date_str = date.strftime("%Y-%m-%d")
                if date_str in remote_dates:
                    target_dates.append(date_str)

            # Exécute la récupération
            synced_dates = []
            skipped_dates = []
            failed_dates = []

            for date_str in target_dates:
                # Vérifie si la date existe déjà localement
                if date_str in local_dates:
                    skipped_dates.append(date_str)
                    continue

                # Récupère une date unique
                try:
                    local_date_dir = local_dir / date_str
                    local_db_path = local_date_dir / "news.db"
                    remote_key = f"news/{date_str}.db"

                    local_date_dir.mkdir(parents=True, exist_ok=True)
                    remote_backend.s3_client.download_file(
                        remote_backend.bucket_name,
                        remote_key,
                        str(local_db_path)
                    )
                    synced_dates.append(date_str)
                    print(f"[Synchronisation du stockage] Récupéré : {date_str}")
                except Exception as e:
                    failed_dates.append({"date": date_str, "error": str(e)})
                    print(f"[Synchronisation du stockage] Échec de la récupération ({date_str}) : {e}")

            return {
                "success": True,
                "summary": {
                    "description": "Résultat de synchronisation du stockage distant",
                    "synced_files": len(synced_dates),
                    "skipped_count": len(skipped_dates),
                    "failed_count": len(failed_dates)
                },
                "data": {
                    "synced_dates": synced_dates,
                    "skipped_dates": skipped_dates,
                    "failed_dates": failed_dates
                },
                "message": f"{len(synced_dates)} jour(s) de données synchronisé(s) avec succès" + (
                    f", {len(skipped_dates)} jour(s) ignoré(s) (déjà présent(s) localement)" if skipped_dates else ""
                ) + (
                    f", {len(failed_dates)} jour(s) en échec" if failed_dates else ""
                )
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

    def get_storage_status(self) -> Dict:
        """
        Récupère la configuration et l'état du stockage

        Returns:
            dictionnaire de l'état du stockage
        """
        try:
            storage_config = self._get_storage_config()
            config = self._load_config()

            # État du stockage local
            local_config = storage_config.get("local", {})
            local_dir = self._get_local_data_dir()
            local_size = self._calculate_dir_size(local_dir)

            # Récupère les listes de dates par catégorie
            all_dates = self._get_all_local_dates()
            news_dates = all_dates["news"]
            rss_dates = all_dates["rss"]
            combined_dates = all_dates["all"]

            local_status = {
                "data_dir": local_config.get("data_dir", "output"),
                "retention_days": local_config.get("retention_days", 0),
                "total_size": f"{local_size / 1024 / 1024:.2f} MB",
                "total_size_bytes": local_size,
                "date_count": len(combined_dates),
                "earliest_date": combined_dates[-1] if combined_dates else None,
                "latest_date": combined_dates[0] if combined_dates else None,
                "news": {
                    "date_count": len(news_dates),
                    "dates": news_dates[:10],  # 10 derniers jours
                },
                "rss": {
                    "date_count": len(rss_dates),
                    "dates": rss_dates[:10],  # 10 derniers jours
                },
            }

            # État du stockage distant
            remote_config = storage_config.get("remote", {})
            has_remote = self._has_remote_config()

            remote_status = {
                "configured": has_remote,
                "retention_days": remote_config.get("retention_days", 0),
            }

            if has_remote:
                merged_config = self._get_remote_config()
                # Affichage anonymisé
                endpoint = merged_config.get("endpoint_url", "")
                bucket = merged_config.get("bucket_name", "")
                remote_status["endpoint_url"] = endpoint
                remote_status["bucket_name"] = bucket

                # Essaie de récupérer la liste des dates distantes
                remote_backend = self._get_remote_backend()
                if remote_backend:
                    try:
                        remote_dates = remote_backend.list_remote_dates()
                        remote_status["date_count"] = len(remote_dates)
                        remote_status["earliest_date"] = remote_dates[-1] if remote_dates else None
                        remote_status["latest_date"] = remote_dates[0] if remote_dates else None
                    except Exception as e:
                        remote_status["error"] = str(e)

            # État de la configuration de récupération
            pull_config = storage_config.get("pull", {})
            pull_status = {
                "enabled": pull_config.get("enabled", False),
                "days": pull_config.get("days", 7),
            }

            return {
                "success": True,
                "summary": {
                    "description": "Informations sur la configuration et l'état du stockage",
                    "backend": storage_config.get("backend", "auto")
                },
                "data": {
                    "local": local_status,
                    "remote": remote_status,
                    "pull": pull_status
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

    def list_available_dates(self, source: str = "both") -> Dict:
        """
        Liste les plages de dates disponibles

        Args:
            source: source des données
                - "local": local uniquement
                - "remote": distant uniquement
                - "both": liste les deux (par défaut)

        Returns:
            dictionnaire de la liste des dates
        """
        try:
            data_result = {}
            summary_info = {
                "description": "Liste des dates disponibles",
                "source": source
            }

            # Dates locales
            if source in ("local", "both"):
                all_dates = self._get_all_local_dates()
                news_dates = all_dates["news"]
                rss_dates = all_dates["rss"]
                combined_dates = all_dates["all"]

                data_result["local"] = {
                    "dates": combined_dates,
                    "count": len(combined_dates),
                    "earliest": combined_dates[-1] if combined_dates else None,
                    "latest": combined_dates[0] if combined_dates else None,
                    "news": {
                        "dates": news_dates,
                        "count": len(news_dates),
                    },
                    "rss": {
                        "dates": rss_dates,
                        "count": len(rss_dates),
                    },
                }

            # Dates distantes
            if source in ("remote", "both"):
                if not self._has_remote_config():
                    data_result["remote"] = {
                        "configured": False,
                        "dates": [],
                        "count": 0,
                        "earliest": None,
                        "latest": None,
                        "error": "Stockage distant non configuré"
                    }
                else:
                    remote_backend = self._get_remote_backend()
                    if remote_backend:
                        try:
                            remote_dates = remote_backend.list_remote_dates()
                            data_result["remote"] = {
                                "configured": True,
                                "dates": remote_dates,
                                "count": len(remote_dates),
                                "earliest": remote_dates[-1] if remote_dates else None,
                                "latest": remote_dates[0] if remote_dates else None,
                            }
                        except Exception as e:
                            data_result["remote"] = {
                                "configured": True,
                                "dates": [],
                                "count": 0,
                                "earliest": None,
                                "latest": None,
                                "error": str(e)
                            }
                    else:
                        data_result["remote"] = {
                            "configured": True,
                            "dates": [],
                            "count": 0,
                            "earliest": None,
                            "latest": None,
                            "error": "Impossible de créer le backend de stockage distant"
                        }

            # Si les deux sont interrogés, calcule les différences
            if source == "both" and "local" in data_result and "remote" in data_result:
                local_set = set(data_result["local"]["dates"])
                remote_set = set(data_result["remote"].get("dates", []))

                data_result["comparison"] = {
                    "only_local": sorted(list(local_set - remote_set), reverse=True),
                    "only_remote": sorted(list(remote_set - local_set), reverse=True),
                    "both": sorted(list(local_set & remote_set), reverse=True),
                }

            return {
                "success": True,
                "summary": summary_info,
                "data": data_result
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
