"""
Outils de gestion système

Implémente la requête de l'état du système et le déclenchement du collecteur.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

from ..services.data_service import DataService
from ..utils.validators import validate_platforms
from ..utils.errors import MCPError, CrawlTaskError


class SystemManagementTools:
    """Classe des outils de gestion système"""

    def __init__(self, project_root: str = None):
        """
        Initialise les outils de gestion système

        Args:
            project_root: répertoire racine du projet
        """
        self.data_service = DataService(project_root)
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Récupère le répertoire racine du projet
            current_file = Path(__file__)
            self.project_root = current_file.parent.parent.parent

    def get_system_status(self) -> Dict:
        """
        Récupère l'état de fonctionnement du système et les informations de vérification de santé

        Returns:
            dictionnaire de l'état du système

        Example:
            >>> tools = SystemManagementTools()
            >>> result = tools.get_system_status()
            >>> print(result['system']['version'])
        """
        try:
            # Récupère l'état du système
            status = self.data_service.get_system_status()

            return {
                "success": True,
                "summary": {
                    "description": "État de fonctionnement du système et informations de vérification de santé"
                },
                "data": status
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

    def _load_crawl_config(self):
        """Charge la configuration de collecte, retourne (config_data, target_platforms_config)"""
        import yaml

        config_path = self.project_root / "config" / "config.yaml"
        if not config_path.exists():
            raise CrawlTaskError(
                "Le fichier de configuration n'existe pas",
                suggestion=f"Veuillez vous assurer que le fichier de configuration existe : {config_path}"
            )

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        platforms_config = config_data.get("platforms", {})
        if not platforms_config.get("enabled", True):
            raise CrawlTaskError(
                "Les plateformes de palmarès sont désactivées",
                suggestion="Veuillez vérifier la configuration platforms.enabled dans config/config.yaml"
            )
        all_platforms = [p for p in platforms_config.get("sources", []) if p.get("enabled", True)]
        if not all_platforms:
            raise CrawlTaskError(
                "Aucune configuration de plateforme dans le fichier de configuration",
                suggestion="Veuillez vérifier la configuration platforms.sources dans config/config.yaml"
            )

        return config_data, all_platforms

    def _resolve_target_platforms(self, all_platforms: list, platforms: Optional[List[str]]):
        """Filtre selon la liste de plateformes indiquée par l'utilisateur, retourne (target_platforms, ids_list)"""
        if platforms:
            target_platforms = [p for p in all_platforms if p["id"] in platforms]
            if not target_platforms:
                raise CrawlTaskError(
                    f"Les plateformes indiquées n'existent pas : {platforms}",
                    suggestion=f"Plateformes disponibles : {[p['id'] for p in all_platforms]}"
                )
        else:
            target_platforms = all_platforms

        ids = []
        for platform in target_platforms:
            if "name" in platform:
                ids.append((platform["id"], platform["name"]))
            else:
                ids.append(platform["id"])

        return target_platforms, ids

    def _persist_crawl_data(self, storage, news_data, save_to_local, results, id_to_name, failed_ids, current_time, crawl_time_str):
        """Persiste les données de collecte, retourne (save_success, save_error_msg, saved_files)"""
        save_success = False
        save_error_msg = ""
        saved_files = {}

        try:
            if storage.save_news_data(news_data):
                save_success = True

            if save_to_local:
                txt_path = storage.save_txt_snapshot(news_data)
                if txt_path:
                    saved_files["txt"] = txt_path

                html_content = self._generate_simple_html(results, id_to_name, failed_ids, current_time)
                html_filename = f"{crawl_time_str}.html"
                html_path = storage.save_html_report(html_content, html_filename)
                if html_path:
                    saved_files["html"] = html_path

        except Exception as e:
            print(f"[System] Échec de l'enregistrement des données : {e}")
            save_success = False
            save_error_msg = str(e)

        return save_success, save_error_msg, saved_files

    def _build_crawl_response(self, results, id_to_name, failed_ids, current_time, include_url,
                               save_success, save_to_local, save_error_msg, saved_files):
        """Construit le dictionnaire de réponse du résultat de collecte"""
        import time

        news_response_data = []
        for platform_id, titles_data in results.items():
            platform_name = id_to_name.get(platform_id, platform_id)
            for title, info in titles_data.items():
                news_item = {
                    "platform_id": platform_id,
                    "platform_name": platform_name,
                    "title": title,
                    "ranks": info.get("ranks", [])
                }
                if include_url:
                    news_item["url"] = info.get("url", "")
                    news_item["mobile_url"] = info.get("mobileUrl", "")
                news_response_data.append(news_item)

        result = {
            "success": True,
            "summary": {
                "description": "Résultat d'exécution de la tâche de collecte",
                "task_id": f"crawl_{int(time.time())}",
                "status": "completed",
                "crawl_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_news": len(news_response_data),
                "platforms": list(results.keys()),
                "failed_platforms": failed_ids,
                "saved_to_local": save_success and save_to_local
            },
            "data": news_response_data
        }

        if save_success:
            if save_to_local:
                result["saved_files"] = saved_files
                result["note"] = "Données enregistrées dans la base de données SQLite et le dossier output"
            else:
                result["note"] = "Données enregistrées dans la base de données SQLite (résultats retournés en mémoire uniquement, aucun instantané TXT généré)"
        else:
            result["saved_to_local"] = False
            result["save_error"] = save_error_msg
            if "Read-only file system" in save_error_msg or "Permission denied" in save_error_msg:
                result["note"] = "Collecte réussie, mais écriture impossible dans la base de données (mode Docker en lecture seule). Les données ne sont valides que dans cette réponse."
            else:
                result["note"] = f"Collecte réussie mais échec de l'enregistrement : {save_error_msg}"

        return result

    def trigger_crawl(self, platforms: Optional[List[str]] = None, save_to_local: bool = False, include_url: bool = False) -> Dict:
        """
        Déclenche manuellement une tâche de collecte ponctuelle (persistance facultative)

        Args:
            platforms: liste de plateformes indiquée, vide pour collecter toutes les plateformes
            save_to_local: indique s'il faut enregistrer dans le répertoire output local, False par défaut
            include_url: indique s'il faut inclure les liens URL, False par défaut (économie de tokens)

        Returns:
            dictionnaire du résultat de collecte, contenant les données d'actualités et les chemins d'enregistrement (le cas échéant)
        """
        try:
            from trendradar.crawler.fetcher import DataFetcher
            from trendradar.storage.local import LocalStorageBackend
            from trendradar.storage.base import convert_crawl_results_to_news_data
            from trendradar.utils.time import get_configured_time, format_date_folder, format_time_filename
            from ..services.cache_service import get_cache

            platforms = validate_platforms(platforms)

            # 1. Charge la configuration
            config_data, all_platforms = self._load_crawl_config()
            target_platforms, ids = self._resolve_target_platforms(all_platforms, platforms)

            print(f"Démarrage de la collecte ponctuelle, plateformes : {[p.get('name', p['id']) for p in target_platforms]}")

            # 2. Exécute la collecte
            advanced = config_data.get("advanced", {})
            crawler_config = advanced.get("crawler", {})
            platforms_config = config_data.get("platforms", {})
            proxy_url = crawler_config.get("default_proxy") if crawler_config.get("use_proxy") else None
            api_url = (
                os.environ.get("PLATFORMS_API_URL", "").strip()
                or platforms_config.get("api_url", "")
            ) or None

            domain_rules = {}
            for p in target_platforms:
                ed = p.get("expected_domain", "")
                if ed:
                    domain_rules[p["id"]] = ed

            fetcher = DataFetcher(proxy_url=proxy_url, api_url=api_url)
            results, id_to_name, failed_ids = fetcher.crawl_websites(
                ids_list=ids,
                request_interval=crawler_config.get("request_interval", 100),
                domain_rules=domain_rules,
            )

            # 3. Conversion et persistance
            timezone = config_data.get("app", {}).get("timezone", "Asia/Shanghai")
            current_time = get_configured_time(timezone)
            crawl_date = format_date_folder(None, timezone)
            crawl_time_str = format_time_filename(timezone)

            news_data = convert_crawl_results_to_news_data(
                results=results, id_to_name=id_to_name,
                failed_ids=failed_ids, crawl_time=crawl_time_str, crawl_date=crawl_date
            )

            storage = LocalStorageBackend(
                data_dir=str(self.project_root / "output"),
                enable_txt=True, enable_html=True, timezone=timezone
            )

            try:
                save_success, save_error_msg, saved_files = self._persist_crawl_data(
                    storage, news_data, save_to_local, results, id_to_name, failed_ids, current_time, crawl_time_str
                )
            finally:
                get_cache().clear()
                print("[System] Cache vidé")
                storage.cleanup()

            # 4. Construit la réponse
            return self._build_crawl_response(
                results, id_to_name, failed_ids, current_time, include_url,
                save_success, save_to_local, save_error_msg, saved_files
            )

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
            }

    def _generate_simple_html(self, results: Dict, id_to_name: Dict, failed_ids: List, now) -> str:
        """Génère un rapport HTML simplifié"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Résultat de collecte MCP</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }
        .platform { margin-bottom: 30px; }
        .platform-name { background: #4CAF50; color: white; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
        .news-item { padding: 8px; border-bottom: 1px solid #eee; }
        .rank { color: #666; font-weight: bold; margin-right: 10px; }
        .title { color: #333; }
        .link { color: #1976D2; text-decoration: none; margin-left: 10px; font-size: 0.9em; }
        .link:hover { text-decoration: underline; }
        .failed { background: #ffebee; padding: 10px; border-radius: 5px; margin-top: 20px; }
        .failed h3 { color: #c62828; margin-top: 0; }
        .timestamp { color: #666; font-size: 0.9em; text-align: right; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Résultat de collecte MCP</h1>
"""

        # Ajoute l'horodatage
        html += f'        <p class="timestamp">Heure de collecte : {now.strftime("%Y-%m-%d %H:%M:%S")}</p>\n\n'

        # Parcourt chaque plateforme
        for platform_id, titles_data in results.items():
            platform_name = id_to_name.get(platform_id, platform_id)
            html += f'        <div class="platform">\n'
            html += f'            <div class="platform-name">{platform_name}</div>\n'

            # Trie les titres
            sorted_items = []
            for title, info in titles_data.items():
                ranks = info.get("ranks", [])
                url = info.get("url", "")
                mobile_url = info.get("mobileUrl", "")
                rank = ranks[0] if ranks else 999
                sorted_items.append((rank, title, url, mobile_url))

            sorted_items.sort(key=lambda x: x[0])

            # Affiche les actualités
            for rank, title, url, mobile_url in sorted_items:
                html += f'            <div class="news-item">\n'
                html += f'                <span class="rank">{rank}.</span>\n'
                html += f'                <span class="title">{self._html_escape(title)}</span>\n'
                if url:
                    html += f'                <a class="link" href="{self._html_escape(url)}" target="_blank">Lien</a>\n'
                if mobile_url and mobile_url != url:
                    html += f'                <a class="link" href="{self._html_escape(mobile_url)}" target="_blank">Version mobile</a>\n'
                html += '            </div>\n'

            html += '        </div>\n\n'

        # Plateformes en échec
        if failed_ids:
            html += '        <div class="failed">\n'
            html += '            <h3>Plateformes dont la requête a échoué</h3>\n'
            html += '            <ul>\n'
            for platform_id in failed_ids:
                html += f'                <li>{self._html_escape(platform_id)}</li>\n'
            html += '            </ul>\n'
            html += '        </div>\n'

        html += """    </div>
</body>
</html>"""

        return html

    def _html_escape(self, text: str) -> str:
        """Échappement HTML"""
        if not isinstance(text, str):
            text = str(text)
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    def check_version(self, proxy_url: Optional[str] = None) -> Dict:
        """
        Vérifie les mises à jour de version

        Vérifie simultanément les mises à jour de version des deux composants TrendRadar et MCP Server.
        Les URL de version distante sont récupérées depuis config.yaml :
        - version_check_url : version de TrendRadar
        - mcp_version_check_url : version de MCP Server

        Args:
            proxy_url: URL de proxy facultative, utilisée pour accéder à la version distante

        Returns:
            dictionnaire du résultat de vérification de version, contenant :
            - success : indique si l'opération a réussi
            - trendradar : résultat de la vérification de version de TrendRadar
            - mcp : résultat de la vérification de version de MCP Server
            - any_update : indique si un composant nécessite une mise à jour

        Example:
            >>> tools = SystemManagementTools()
            >>> result = tools.check_version()
            >>> print(result['data']['any_update'])
        """
        import yaml
        import requests

        def parse_version(version_str: str):
            """Analyse une chaîne de numéro de version en tuple"""
            try:
                parts = version_str.strip().split(".")
                if len(parts) != 3:
                    raise ValueError("Format de numéro de version incorrect")
                return int(parts[0]), int(parts[1]), int(parts[2])
            except (ValueError, AttributeError, TypeError):
                return 0, 0, 0

        def check_single_version(
            name: str,
            local_version: str,
            remote_url: str,
            proxies: Optional[Dict],
            headers: Dict
        ) -> Dict:
            """Vérifie la version d'un composant unique (prend en charge le repli multi-source CDN)"""
            try:
                from trendradar.core.cdn import fetch_with_fallback
                proxy_url = None
                if proxies:
                    proxy_url = proxies.get("https") or proxies.get("http")
                remote_version = fetch_with_fallback(remote_url, proxy_url)

                if not remote_version:
                    return {
                        "success": False,
                        "name": name,
                        "current_version": local_version,
                        "error": "Toutes les sources de vérification de version sont indisponibles"
                    }

                local_tuple = parse_version(local_version)
                remote_tuple = parse_version(remote_version)
                need_update = local_tuple < remote_tuple

                if need_update:
                    message = f"Nouvelle version {remote_version} disponible, version actuelle {local_version}, mise à jour recommandée"
                elif local_tuple > remote_tuple:
                    message = f"La version actuelle {local_version} est supérieure à la version distante {remote_version} (probablement une version de développement)"
                else:
                    message = f"La version actuelle {local_version} est déjà la plus récente"

                return {
                    "success": True,
                    "name": name,
                    "current_version": local_version,
                    "remote_version": remote_version,
                    "need_update": need_update,
                    "current_parsed": list(local_tuple),
                    "remote_parsed": list(remote_tuple),
                    "message": message
                }
            except Exception as e:
                return {
                    "success": False,
                    "name": name,
                    "current_version": local_version,
                    "error": str(e)
                }

        try:
            # Importe la version locale
            from trendradar import __version__ as trendradar_version
            from mcp_server import __version__ as mcp_version

            # Récupère les URL de version distante depuis le fichier de configuration
            config_path = self.project_root / "config" / "config.yaml"
            if not config_path.exists():
                return {
                    "success": False,
                    "error": {
                        "code": "CONFIG_NOT_FOUND",
                        "message": f"Le fichier de configuration n'existe pas : {config_path}"
                    }
                }

            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            advanced_config = config_data.get("advanced", {})
            trendradar_url = advanced_config.get(
                "version_check_url",
                "https://raw.githubusercontent.com/sansan0/TrendRadar/refs/heads/master/version"
            )
            mcp_url = advanced_config.get(
                "mcp_version_check_url",
                "https://raw.githubusercontent.com/sansan0/TrendRadar/refs/heads/master/version_mcp"
            )

            # Configure le proxy
            proxies = None
            if proxy_url:
                proxies = {"http": proxy_url, "https": proxy_url}

            # En-têtes de requête
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/plain, */*",
                "Cache-Control": "no-cache",
            }

            # Vérifie les deux versions
            trendradar_result = check_single_version(
                "TrendRadar", trendradar_version, trendradar_url, proxies, headers
            )
            mcp_result = check_single_version(
                "MCP Server", mcp_version, mcp_url, proxies, headers
            )

            # Détermine s'il y a une mise à jour
            any_update = (
                (trendradar_result.get("success") and trendradar_result.get("need_update", False)) or
                (mcp_result.get("success") and mcp_result.get("need_update", False))
            )

            return {
                "success": True,
                "summary": {
                    "description": "Résultat de la vérification de version (TrendRadar + MCP Server)",
                    "any_update": any_update
                },
                "data": {
                    "trendradar": trendradar_result,
                    "mcp": mcp_result,
                    "any_update": any_update
                }
            }

        except ImportError as e:
            return {
                "success": False,
                "error": {
                    "code": "IMPORT_ERROR",
                    "message": f"Impossible d'importer les informations de version : {str(e)}"
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }
