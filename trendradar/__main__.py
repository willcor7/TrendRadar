# coding=utf-8
"""
TrendRadar - programme principal

Outil d'agrégation et d'analyse des actualités tendance.
Prend en charge : python -m trendradar
"""

import argparse
import copy
import json
import os
import re
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import requests

from trendradar.context import AppContext
from trendradar import __version__
from trendradar.core import load_config, parse_multi_account_config, validate_paired_configs
from trendradar.core.analyzer import convert_keyword_stats_to_platform_stats
from trendradar.crawler import DataFetcher
from trendradar.storage import convert_crawl_results_to_news_data
from trendradar.utils.time import DEFAULT_TIMEZONE, is_within_days, calculate_days_old
from trendradar.ai import AIAnalyzer, AIAnalysisResult
from trendradar.core.scheduler import ResolvedSchedule
from trendradar.core.cdn import fetch_with_fallback


def _parse_version(version_str: str) -> Tuple[int, int, int]:
    """Analyse une chaîne de numéro de version en un tuple."""
    try:
        parts = version_str.strip().split(".")
        if len(parts) >= 3:
            return int(parts[0]), int(parts[1]), int(parts[2])
        return 0, 0, 0
    except (ValueError, AttributeError, TypeError):
        return 0, 0, 0


def _compare_version(local: str, remote: str) -> str:
    """Compare deux numéros de version et renvoie un texte d'état."""
    local_tuple = _parse_version(local)
    remote_tuple = _parse_version(remote)

    if local_tuple < remote_tuple:
        return "⚠️ mise à jour nécessaire"
    elif local_tuple > remote_tuple:
        return "🔮 version en avance"
    else:
        return "✅ déjà à jour"


def _fetch_remote_version(version_url: str, proxy_url: Optional[str] = None) -> Optional[str]:
    """Récupère le numéro de version distant (avec repli sur plusieurs sources CDN)."""
    return fetch_with_fallback(version_url, proxy_url)


def _parse_config_versions(content: str) -> Dict[str, str]:
    """Analyse le contenu des versions du fichier de configuration en un dictionnaire."""
    versions = {}
    try:
        if not content:
            return versions
        for line in content.splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            name, version = line.split("=", 1)
            versions[name.strip()] = version.strip()
    except Exception as e:
        print(f"[Vérification de version] Échec de l'analyse de la version de configuration : {e}")
    return versions


def check_all_versions(
    version_url: str,
    configs_version_url: Optional[str] = None,
    proxy_url: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Vérification unifiée des versions : version du programme + version des fichiers de configuration

    Args:
        version_url: URL de vérification de la version distante du programme
        configs_version_url: URL de vérification de la version distante des fichiers de configuration (format renvoyé : filename=version)
        proxy_url: URL du proxy

    Returns:
        (need_update, remote_version) : indique si le programme doit être mis à jour, et le numéro de version distant
    """
    # Récupération de la version distante
    remote_version = _fetch_remote_version(version_url, proxy_url)

    # Récupération de la version de configuration distante (si une URL est fournie)
    remote_config_versions = {}
    if configs_version_url:
        content = _fetch_remote_version(configs_version_url, proxy_url)
        if content:
            remote_config_versions = _parse_config_versions(content)

    print("=" * 60)
    print("Vérification de version")
    print("=" * 60)

    if remote_version:
        print(f"Version distante du programme : {remote_version}")
    else:
        print("Version distante du programme : échec de la récupération")

    if configs_version_url:
        if remote_config_versions:
            print(f"Liste des configurations distantes : récupérée avec succès ({len(remote_config_versions)} fichier(s))")
        else:
            print("Liste des configurations distantes : échec de la récupération ou liste vide")

    print("-" * 60)

    program_status = _compare_version(__version__, remote_version) if remote_version else "(comparaison impossible)"
    print(f"  Version du programme principal : {__version__} {program_status}")

    config_files = [
        Path("config/config.yaml"),
        Path("config/timeline.yaml"),
        Path("config/frequency_words.txt"),
        Path("config/ai_interests.txt"),
        Path("config/ai_analysis_prompt.txt"),
        Path("config/ai_translation_prompt.txt"),
    ]

    version_pattern = re.compile(r"Version:\s*(\d+\.\d+\.\d+)", re.IGNORECASE)

    for config_file in config_files:
        if not config_file.exists():
            print(f"  {config_file.name} : fichier introuvable")
            continue

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                local_version = None
                for i, line in enumerate(f):
                    if i >= 20:
                        break
                    match = version_pattern.search(line)
                    if match:
                        local_version = match.group(1)
                        break

                # Récupération de la version distante de ce fichier
                target_remote_version = remote_config_versions.get(config_file.name)

                if local_version:
                    if target_remote_version:
                        status = _compare_version(local_version, target_remote_version)
                        print(f"  {config_file.name} : {local_version} {status}")
                    else:
                        print(f"  {config_file.name} : {local_version} (version distante introuvable)")
                else:
                    print(f"  {config_file.name} : numéro de version local introuvable")
        except Exception as e:
            print(f"  {config_file.name} : échec de lecture - {e}")

    print("=" * 60)

    # Renvoie l'état de mise à jour de la version du programme
    if remote_version:
        need_update = _parse_version(__version__) < _parse_version(remote_version)
        return need_update, remote_version if need_update else None
    return False, None


# === Analyseur principal ===
class NewsAnalyzer:
    """Analyseur d'actualités"""

    # Définition des stratégies de mode
    MODE_STRATEGIES = {
        "incremental": {
            "mode_name": "mode incrémental",
            "description": "mode incrémental (suit uniquement les nouvelles actualités, aucun envoi en l'absence de nouveauté)",
            "report_type": "Analyse incrémentale",
            "should_send_notification": True,
        },
        "current": {
            "mode_name": "mode classement actuel",
            "description": "mode classement actuel (actualités correspondant au classement actuel + zone des nouvelles actualités + envoi programmé)",
            "report_type": "Classement actuel",
            "should_send_notification": True,
        },
        "daily": {
            "mode_name": "mode synthèse de la journée",
            "description": "mode synthèse de la journée (toutes les actualités correspondantes + zone des nouvelles actualités + envoi programmé)",
            "report_type": "Synthèse de la journée",
            "should_send_notification": True,
        },
    }

    def __init__(self, config: Optional[Dict] = None):
        # Utilise la configuration passée en argument ou en charge une nouvelle
        if config is None:
            print("Chargement de la configuration en cours...")
            config = load_config()
        print(f"TrendRadar v{__version__} : configuration chargée")
        print(f"Nombre de plateformes surveillées : {len(config['PLATFORMS'])}")
        print(f"Fuseau horaire : {config.get('TIMEZONE', DEFAULT_TIMEZONE)}")

        # Création du contexte d'application
        self.ctx = AppContext(config)

        self.request_interval = self.ctx.config["REQUEST_INTERVAL"]
        self.report_mode = self.ctx.config["REPORT_MODE"]
        self.frequency_file = None
        self.filter_method = None  # None = utilise la configuration globale ctx.filter_method
        self.interests_file = None  # None = utilise la configuration globale ai_filter.interests_file
        self.rank_threshold = self.ctx.rank_threshold
        self.is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        self.is_docker_container = self._detect_docker_environment()
        self.update_info = None
        self.proxy_url = None
        self._setup_proxy()
        self.data_fetcher = DataFetcher(
            self.proxy_url,
            api_url=self.ctx.config.get("PLATFORMS_API_URL") or None,
        )

        # Métadonnées RSS / plateformes (servent à l'affichage de l'en-tête du rapport)
        self._rss_source_total = 0
        self._rss_source_failed = 0
        self._rss_total_count = 0
        self._rss_matched_count = 0
        self._hotlist_total_count = 0

        # Initialisation du gestionnaire de stockage (via AppContext)
        self._init_storage_manager()
        # Remarque : update_info est défini par la fonction main(), pour éviter une requête redondante de la version distante

    def _init_storage_manager(self) -> None:
        """Initialise le gestionnaire de stockage (via AppContext)."""
        # Récupère le nombre de jours de conservation des données (peut être remplacé par une variable d'environnement)
        env_retention = os.environ.get("STORAGE_RETENTION_DAYS", "").strip()
        if env_retention:
            # La variable d'environnement remplace la configuration
            self.ctx.config["STORAGE"]["RETENTION_DAYS"] = int(env_retention)

        self.storage_manager = self.ctx.get_storage_manager()
        print(f"Backend de stockage : {self.storage_manager.backend_name}")

        retention_days = self.ctx.config.get("STORAGE", {}).get("RETENTION_DAYS", 0)
        if retention_days > 0:
            print(f"Nombre de jours de conservation des données : {retention_days} jour(s)")

    def _detect_docker_environment(self) -> bool:
        """Détecte si le programme s'exécute dans un conteneur Docker."""
        try:
            if os.environ.get("DOCKER_CONTAINER") == "true":
                return True

            if os.path.exists("/.dockerenv"):
                return True

            return False
        except Exception:
            return False

    def _should_open_browser(self) -> bool:
        """Détermine si le navigateur doit être ouvert."""
        return not self.is_github_actions and not self.is_docker_container

    def _setup_proxy(self) -> None:
        """Définit la configuration du proxy."""
        if not self.is_github_actions and self.ctx.config["USE_PROXY"]:
            self.proxy_url = self.ctx.config["DEFAULT_PROXY"]
            print("Environnement local, utilisation du proxy")
        elif not self.is_github_actions and not self.ctx.config["USE_PROXY"]:
            print("Environnement local, proxy non activé")
        else:
            print("Environnement GitHub Actions, proxy non utilisé")

    def _set_update_info_from_config(self) -> None:
        """Définit les informations de mise à jour à partir de la version distante déjà en cache (sans nouvelle requête)."""
        try:
            version_url = self.ctx.config.get("VERSION_CHECK_URL", "")
            if not version_url:
                return

            remote_version = _fetch_remote_version(version_url, self.proxy_url)
            if remote_version:
                need_update = _parse_version(__version__) < _parse_version(remote_version)
                if need_update:
                    self.update_info = {
                        "current_version": __version__,
                        "remote_version": remote_version,
                    }
        except Exception as e:
            print(f"Erreur lors de la vérification de version : {e}")

    def _get_mode_strategy(self) -> Dict:
        """Récupère la configuration de stratégie du mode actuel."""
        return self.MODE_STRATEGIES.get(self.report_mode, self.MODE_STRATEGIES["daily"])

    def _has_notification_configured(self) -> bool:
        """Vérifie si un canal de notification est configuré."""
        cfg = self.ctx.config
        return any(
            [
                cfg["FEISHU_WEBHOOK_URL"],
                cfg["DINGTALK_WEBHOOK_URL"],
                cfg["WEWORK_WEBHOOK_URL"],
                (cfg["TELEGRAM_BOT_TOKEN"] and cfg["TELEGRAM_CHAT_ID"]),
                (
                    cfg["EMAIL_FROM"]
                    and cfg["EMAIL_PASSWORD"]
                    and cfg["EMAIL_TO"]
                ),
                (cfg["NTFY_SERVER_URL"] and cfg["NTFY_TOPIC"]),
                cfg["BARK_URL"],
                cfg["SLACK_WEBHOOK_URL"],
                cfg["GENERIC_WEBHOOK_URL"],
            ]
        )

    def _has_valid_content(
        self, stats: List[Dict], new_titles: Optional[Dict] = None
    ) -> bool:
        """Vérifie s'il existe un contenu d'actualité valide."""
        if self.report_mode == "incremental":
            # Mode incrémental : il suffit qu'une actualité corresponde pour envoyer
            # count_word_frequency garantit déjà qu'on ne traite que les nouvelles actualités (y compris la première collecte de la journée)
            has_matched_news = any(stat["count"] > 0 for stat in stats)
            return has_matched_news
        elif self.report_mode == "current":
            # Mode current : si stats contient des éléments, c'est qu'il y a des actualités correspondantes
            return any(stat["count"] > 0 for stat in stats)
        else:
            # En mode synthèse de la journée, on vérifie s'il y a des actualités correspondant aux mots-clés ou des nouvelles actualités
            has_matched_news = any(stat["count"] > 0 for stat in stats)
            has_new_news = bool(
                new_titles and any(len(titles) > 0 for titles in new_titles.values())
            )
            return has_matched_news or has_new_news

    def _prepare_ai_analysis_data(
        self,
        ai_mode: str,
        current_results: Optional[Dict] = None,
        current_id_to_name: Optional[Dict] = None,
    ) -> Tuple[List[Dict], Optional[Dict]]:
        """
        Prépare les données du mode indiqué pour l'analyse IA

        Args:
            ai_mode: mode d'analyse IA (daily/current/incremental)
            current_results: résultats de la collecte actuelle (utilisés pour le mode incremental)
            current_id_to_name: correspondance des plateformes actuelles (utilisée pour le mode incremental)

        Returns:
            Tuple[stats, id_to_name] : données statistiques et correspondance des plateformes
        """
        try:
            word_groups, filter_words, global_filters = self.ctx.load_frequency_words(self.frequency_file)

            if ai_mode == "incremental":
                # Mode incremental : utilise les données de la collecte actuelle
                if not current_results or not current_id_to_name:
                    print("[AI] Le mode incremental requiert les données de la collecte actuelle, mais elles n'ont pas été fournies")
                    return [], None

                # Préparation des informations d'horodatage actuelles
                time_info = self.ctx.format_time()
                title_info = self._prepare_current_title_info(current_results, time_info)

                # Détection des nouveaux titres
                new_titles = self.ctx.detect_new_titles(list(current_results.keys()))

                # Calcul des statistiques
                stats, _ = self.ctx.count_frequency(
                    current_results,
                    word_groups,
                    filter_words,
                    current_id_to_name,
                    title_info,
                    new_titles,
                    mode="incremental",
                    global_filters=global_filters,
                    quiet=True,
                )

                # En mode platform, on convertit la structure des données
                if self.ctx.display_mode == "platform" and stats:
                    stats = convert_keyword_stats_to_platform_stats(
                        stats,
                        self.ctx.weight_config,
                        self.ctx.rank_threshold,
                    )

                return stats, current_id_to_name

            elif ai_mode in ["daily", "current"]:
                # Chargement des données historiques
                analysis_data = self._load_analysis_data(quiet=True)
                if not analysis_data:
                    print(f"[AI] Impossible de charger les données historiques pour l'analyse en mode {ai_mode}")
                    return [], None

                (
                    all_results,
                    id_to_name,
                    title_info,
                    new_titles,
                    _,
                    _,
                    _,
                ) = analysis_data

                # Calcul des statistiques
                stats, _ = self.ctx.count_frequency(
                    all_results,
                    word_groups,
                    filter_words,
                    id_to_name,
                    title_info,
                    new_titles,
                    mode=ai_mode,
                    global_filters=global_filters,
                    quiet=True,
                )

                # En mode platform, on convertit la structure des données
                if self.ctx.display_mode == "platform" and stats:
                    stats = convert_keyword_stats_to_platform_stats(
                        stats,
                        self.ctx.weight_config,
                        self.ctx.rank_threshold,
                    )

                return stats, id_to_name
            else:
                print(f"[AI] Mode IA inconnu : {ai_mode}")
                return [], None

        except Exception as e:
            print(f"[AI] Erreur lors de la préparation des données du mode {ai_mode} : {e}")
            if self.ctx.config.get("DEBUG", False):
                import traceback
                traceback.print_exc()
            return [], None

    def _run_ai_analysis(
        self,
        stats: List[Dict],
        rss_items: Optional[List[Dict]],
        mode: str,
        report_type: str,
        id_to_name: Optional[Dict],
        current_results: Optional[Dict] = None,
        schedule: ResolvedSchedule = None,
        standalone_data: Optional[Dict] = None,
    ) -> Optional[AIAnalysisResult]:
        """Exécute l'analyse IA."""
        analysis_config = self.ctx.config.get("AI_ANALYSIS", {})
        if not analysis_config.get("ENABLED", False):
            return None

        # Décision du système de planification
        if not schedule.analyze:
            print("[AI] Planification : la plage horaire actuelle n'exécute pas l'analyse IA")
            return None

        if schedule.once_analyze and schedule.period_key:
            scheduler = self.ctx.create_scheduler()
            date_str = self.ctx.format_date()
            if scheduler.already_executed(schedule.period_key, "analyze", date_str):
                print(f"[AI] Planification : la plage horaire {schedule.period_name or schedule.period_key} a déjà été analysée aujourd'hui, on l'ignore")
                return None
            else:
                print(f"[AI] Planification : première analyse de la journée pour la plage horaire {schedule.period_name or schedule.period_key}")

        print("[AI] Analyse IA en cours...")
        try:
            ai_config = self.ctx.config.get("AI", {})
            debug_mode = self.ctx.config.get("DEBUG", False)
            analyzer = AIAnalyzer(ai_config, analysis_config, self.ctx.get_time, debug=debug_mode)

            # Détermine le mode utilisé pour l'analyse IA
            ai_mode_config = analysis_config.get("MODE", "follow_report")
            if ai_mode_config == "follow_report":
                # Suit le mode du rapport envoyé
                ai_mode = mode
                ai_stats = stats
                ai_id_to_name = id_to_name
            elif ai_mode_config in ["daily", "current", "incremental"]:
                # Utilise un mode configuré de façon indépendante, ce qui nécessite de préparer à nouveau les données
                ai_mode = ai_mode_config
                if ai_mode != mode:
                    print(f"[AI] Utilisation d'un mode d'analyse indépendant : {ai_mode} (mode d'envoi : {mode})")
                    print(f"[AI] Préparation des données du mode {ai_mode} en cours...")

                    # Prépare à nouveau les données selon le mode IA
                    ai_stats, ai_id_to_name = self._prepare_ai_analysis_data(
                        ai_mode, current_results, id_to_name
                    )
                    if not ai_stats:
                        print(f"[AI] Avertissement : impossible de préparer les données du mode {ai_mode}, repli sur les données du mode d'envoi")
                        ai_stats = stats
                        ai_id_to_name = id_to_name
                        ai_mode = mode
                else:
                    ai_stats = stats
                    ai_id_to_name = id_to_name
            else:
                # Configuration erronée, repli sur le mode « suivi »
                print(f"[AI] Avertissement : valeur ai_analysis.mode invalide « {ai_mode_config} », utilisation du mode d'envoi « {mode} »")
                ai_mode = mode
                ai_stats = stats
                ai_id_to_name = id_to_name

            # Extraction de la liste des plateformes
            platforms = list(ai_id_to_name.values()) if ai_id_to_name else []

            # Extraction de la liste des mots-clés
            keywords = [s.get("word", "") for s in ai_stats if s.get("word")] if ai_stats else []

            # Détermination du type de rapport
            if ai_mode != mode:
                # Détermine le type de rapport selon le mode IA
                ai_report_type = {
                    "daily": "Synthèse de la journée",
                    "current": "Classement actuel",
                    "incremental": "Mise à jour incrémentale"
                }.get(ai_mode, report_type)
            else:
                ai_report_type = report_type

            result = analyzer.analyze(
                stats=ai_stats,
                rss_stats=rss_items,
                report_mode=ai_mode,
                report_type=ai_report_type,
                platforms=platforms,
                keywords=keywords,
                standalone_data=standalone_data,
            )

            # Enregistre le mode utilisé pour l'analyse IA
            if result.success:
                result.ai_mode = ai_mode
                if result.error:
                    # Succès, mais avec un avertissement (ex. : problème d'analyse JSON, mais le texte brut a été utilisé)
                    print(f"[AI] Analyse terminée (avec avertissement : {result.error})")
                else:
                    print("[AI] Analyse terminée")

                # Enregistrement de l'analyse IA
                if schedule.once_analyze and schedule.period_key:
                    scheduler = self.ctx.create_scheduler()
                    date_str = self.ctx.format_date()
                    scheduler.record_execution(schedule.period_key, "analyze", date_str)
            elif result.skipped:
                print(f"[AI] {result.error}")
            else:
                print(f"[AI] Échec de l'analyse : {result.error}")

            return result
        except Exception as e:
            import traceback
            error_type = type(e).__name__
            error_msg = str(e)
            # Tronque les messages d'erreur trop longs
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            print(f"[AI] Erreur lors de l'analyse ({error_type}) : {error_msg}")
            # Journal d'erreur détaillé envoyé vers stderr
            import sys
            print(f"[AI] Pile d'appels détaillée de l'erreur :", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return AIAnalysisResult(success=False, error=f"{error_type}: {error_msg}")

    def _load_analysis_data(
        self,
        quiet: bool = False,
    ) -> Optional[Tuple[Dict, Dict, Dict, Dict, List, List]]:
        """Chargement et prétraitement unifiés des données : filtre les données historiques selon la liste actuelle des plateformes surveillées."""
        try:
            # Récupère la liste des ID de plateformes surveillées dans la configuration actuelle
            current_platform_ids = self.ctx.platform_ids
            if not quiet:
                print(f"Plateformes actuellement surveillées : {current_platform_ids}")

            all_results, id_to_name, title_info = self.ctx.read_today_titles(
                current_platform_ids, quiet=quiet
            )

            if not all_results:
                print("Aucune donnée trouvée pour aujourd'hui")
                return None

            total_titles = sum(len(titles) for titles in all_results.values())
            if not quiet:
                print(f"{total_titles} titre(s) lu(s) (déjà filtrés selon les plateformes actuellement surveillées)")

            new_titles = self.ctx.detect_new_titles(current_platform_ids, quiet=quiet)
            word_groups, filter_words, global_filters = self.ctx.load_frequency_words(self.frequency_file)

            return (
                all_results,
                id_to_name,
                title_info,
                new_titles,
                word_groups,
                filter_words,
                global_filters,
            )
        except Exception as e:
            print(f"Échec du chargement des données : {e}")
            return None

    def _prepare_current_title_info(self, results: Dict, time_info: str) -> Dict:
        """Construit les informations de titre à partir des résultats de la collecte actuelle."""
        title_info = {}
        for source_id, titles_data in results.items():
            title_info[source_id] = {}
            for title, title_data in titles_data.items():
                ranks = title_data.get("ranks", [])
                url = title_data.get("url", "")
                mobile_url = title_data.get("mobileUrl", "")

                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
        return title_info

    def _prepare_standalone_data(
        self,
        results: Dict,
        id_to_name: Dict,
        title_info: Optional[Dict] = None,
        rss_items: Optional[List[Dict]] = None,
    ) -> Optional[Dict]:
        """
        Extrait les données de la zone d'affichage autonome à partir des données brutes.

        Méthode de préparation de données pure : elle ne vérifie pas l'interrupteur display.regions.standalone.
        Chaque consommateur décide lui-même de l'utiliser ou non :
        - Analyse IA : contrôlée par ai.include_standalone (filtrage dans _run_ai_analysis)
        - Rapport HTML / e-mail : contrôlé par display.regions.standalone (filtrage avant la génération du HTML)
        - Envoi Webhook : contrôlé par display.regions.standalone (filtrage dans le dispatcher)

        Args:
            results: résultats bruts de la collecte {platform_id: {title: title_data}}
            id_to_name: correspondance ID de plateforme -> nom
            title_info: métadonnées des titres (historique des classements, horodatages, etc.)
            rss_items: liste des entrées RSS

        Returns:
            Dictionnaire des données d'affichage autonome ; renvoie None si aucune source de données n'est configurée.
        """
        display_config = self.ctx.config.get("DISPLAY", {})
        standalone_config = display_config.get("STANDALONE", {})

        platform_ids = standalone_config.get("PLATFORMS", [])
        rss_feed_ids = standalone_config.get("RSS_FEEDS", [])
        max_items = standalone_config.get("MAX_ITEMS", 20)

        if not platform_ids and not rss_feed_ids:
            return None

        standalone_data = {
            "platforms": [],
            "rss_feeds": [],
        }

        # Détermine l'horodatage du lot le plus récent (logique de filtrage similaire au mode current)
        latest_time = None
        if title_info:
            for source_titles in title_info.values():
                for title_data in source_titles.values():
                    last_time = title_data.get("last_time", "")
                    if last_time:
                        if latest_time is None or last_time > latest_time:
                            latest_time = last_time

        # Extraction des données des plateformes de tendances
        for platform_id in platform_ids:
            if platform_id not in results:
                continue

            platform_name = id_to_name.get(platform_id, platform_id)
            platform_titles = results[platform_id]

            items = []
            for title, title_data in platform_titles.items():
                # Récupère les métadonnées (si title_info est disponible)
                meta = {}
                if title_info and platform_id in title_info and title in title_info[platform_id]:
                    meta = title_info[platform_id][title]

                # Ne conserve que les sujets actuellement au classement (last_time égal à l'horodatage le plus récent)
                if latest_time and meta:
                    if meta.get("last_time") != latest_time:
                        continue

                # Trie en utilisant les données de classement actuelles des tendances (title_data)
                # title_data contient le classement actuel renvoyé par le collecteur ; il sert à garder l'ordre de la zone d'affichage autonome cohérent avec celui des tendances
                current_ranks = title_data.get("ranks", [])
                current_rank = current_ranks[-1] if current_ranks else 0

                # Plage de classements à afficher : fusion du classement historique et du classement actuel
                historical_ranks = meta.get("ranks", []) if meta else []
                # Fusion avec déduplication, en conservant l'ordre
                all_ranks = historical_ranks.copy()
                for rank in current_ranks:
                    if rank not in all_ranks:
                        all_ranks.append(rank)
                display_ranks = all_ranks if all_ranks else current_ranks

                item = {
                    "title": title,
                    "url": title_data.get("url", ""),
                    "mobileUrl": title_data.get("mobileUrl", ""),
                    "rank": current_rank,  # classement actuel utilisé pour le tri
                    "ranks": display_ranks,  # plage de classements affichée (historique + actuel)
                    "first_time": meta.get("first_time", ""),
                    "last_time": meta.get("last_time", ""),
                    "count": meta.get("count", 1),
                    "rank_timeline": meta.get("rank_timeline", []),
                }
                items.append(item)

            # Tri selon le classement actuel
            items.sort(key=lambda x: x["rank"] if x["rank"] > 0 else 9999)

            # Limitation du nombre d'entrées
            if max_items > 0:
                items = items[:max_items]

            if items:
                standalone_data["platforms"].append({
                    "id": platform_id,
                    "name": platform_name,
                    "items": items,
                })

        # Extraction des données RSS
        if rss_items and rss_feed_ids:
            # Regroupement par feed_id
            feed_items_map = {}
            for item in rss_items:
                feed_id = item.get("feed_id", "")
                if feed_id in rss_feed_ids:
                    if feed_id not in feed_items_map:
                        feed_items_map[feed_id] = {
                            "name": item.get("feed_name", feed_id),
                            "items": [],
                        }
                    feed_items_map[feed_id]["items"].append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "published_at": item.get("published_at", ""),
                        "author": item.get("author", ""),
                    })

            # Limitation du nombre d'entrées et ajout au résultat
            for feed_id in rss_feed_ids:
                if feed_id in feed_items_map:
                    feed_data = feed_items_map[feed_id]
                    items = feed_data["items"]
                    if max_items > 0:
                        items = items[:max_items]
                    if items:
                        standalone_data["rss_feeds"].append({
                            "id": feed_id,
                            "name": feed_data["name"],
                            "items": items,
                        })

        # Renvoie None s'il n'y a aucune donnée
        if not standalone_data["platforms"] and not standalone_data["rss_feeds"]:
            return None

        return standalone_data

    def _run_analysis_pipeline(
        self,
        data_source: Dict,
        mode: str,
        title_info: Dict,
        new_titles: Dict,
        word_groups: List[Dict],
        filter_words: List[str],
        id_to_name: Dict,
        failed_ids: Optional[List] = None,
        global_filters: Optional[List[str]] = None,
        quiet: bool = False,
        rss_items: Optional[List[Dict]] = None,
        rss_new_items: Optional[List[Dict]] = None,
        standalone_data: Optional[Dict] = None,
        schedule: ResolvedSchedule = None,
        rss_new_urls: Optional[set] = None,
    ) -> Tuple[List[Dict], Optional[str], Optional[AIAnalysisResult], Optional[List[Dict]]]:
        """Pipeline d'analyse unifié : traitement des données → calcul des statistiques (filtrage par mots-clés/IA) → analyse IA → génération du HTML."""

        # Choisit le mode de traitement des données selon la stratégie de filtrage
        if self.filter_method == "ai":
            # === Stratégie de filtrage IA ===
            print("[Filtrage] Utilisation de la stratégie de filtrage intelligent par IA")
            ai_filter_result = self.ctx.run_ai_filter(interests_file=self.interests_file)

            if ai_filter_result and ai_filter_result.success:
                print(f"[Filtrage] Filtrage IA terminé : {ai_filter_result.total_matched} entrée(s) correspondante(s), {len(ai_filter_result.tags)} étiquette(s)")
                # Convertit vers la même structure de données que la correspondance par mots-clés
                stats, ai_rss_stats = self.ctx.convert_ai_filter_to_report_data(
                    ai_filter_result, mode=mode,
                    new_titles=new_titles, rss_new_urls=rss_new_urls,
                )
                total_titles = sum(len(titles) for titles in data_source.values())

                # Les résultats RSS du filtrage IA remplacent ceux de la correspondance par mots-clés
                if ai_rss_stats:
                    rss_items = ai_rss_stats
            else:
                # Échec du filtrage IA, repli sur la correspondance par mots-clés
                error_msg = ai_filter_result.error if ai_filter_result else "erreur inconnue"
                print(f"[Filtrage] Échec du filtrage IA : {error_msg}, repli sur la correspondance par mots-clés")
                stats, total_titles = self.ctx.count_frequency(
                    data_source, word_groups, filter_words,
                    id_to_name, title_info, new_titles,
                    mode=mode, global_filters=global_filters, quiet=quiet,
                )
        else:
            # === Stratégie de correspondance par mots-clés (par défaut) ===
            stats, total_titles = self.ctx.count_frequency(
                data_source, word_groups, filter_words,
                id_to_name, title_info, new_titles,
                mode=mode, global_filters=global_filters, quiet=quiet,
            )

        self._hotlist_total_count = total_titles

        # En mode platform, on convertit la structure des données
        if self.ctx.display_mode == "platform" and stats:
            stats = convert_keyword_stats_to_platform_stats(
                stats,
                self.ctx.weight_config,
                self.ctx.rank_threshold,
            )

        # Analyse IA (si activée, pour le rapport HTML)
        ai_result = None
        ai_config = self.ctx.config.get("AI_ANALYSIS", {})
        if ai_config.get("ENABLED", False) and stats:
            # Récupère la stratégie de mode pour déterminer le type de rapport
            mode_strategy = self._get_mode_strategy()
            report_type = mode_strategy["report_type"]
            ai_result = self._run_ai_analysis(
                stats, rss_items, mode, report_type, id_to_name,
                current_results=data_source, schedule=schedule,
                standalone_data=standalone_data
            )

        # Traduction du contenu RSS (si activée) — exécutée avant la génération du HTML, pour que la version web puisse aussi afficher le contenu traduit
        # Remarque : on ne traduit que rss_items et rss_new_items, pas standalone_data (qui est régénéré avant la notification)
        # La traduction des tendances est gérée lors de l'envoi par dispatch_all sur report_data
        trans_config = self.ctx.config.get("AI_TRANSLATION", {})
        if trans_config.get("ENABLED", False):
            dispatcher = self.ctx.create_notification_dispatcher()
            display_regions = self.ctx.config.get("DISPLAY", {}).get("REGIONS", {})
            _, rss_items, rss_new_items, _ = \
                dispatcher.translate_content(
                    report_data={"stats": [], "new_titles": []},
                    rss_items=rss_items,
                    rss_new_items=rss_new_items,
                    display_regions=display_regions,
                )

        # Calcule le nombre d'entrées RSS correspondantes (partagé entre le HTML et l'envoi)
        self._rss_matched_count = sum(stat.get("count", 0) for stat in rss_items) if rss_items else 0

        # Génération du HTML (si activée) — utilise les données après traduction
        html_file = None
        if self.ctx.config["STORAGE"]["FORMATS"]["HTML"]:
            display_regions = self.ctx.config.get("DISPLAY", {}).get("REGIONS", {})
            html_standalone = standalone_data if display_regions.get("STANDALONE", False) else None
            html_ai = ai_result if display_regions.get("AI_ANALYSIS", True) else None
            html_file = self.ctx.generate_html(
                stats,
                total_titles,
                failed_ids=failed_ids,
                new_titles=new_titles,
                id_to_name=id_to_name,
                mode=mode,
                update_info=self.update_info if self.ctx.config["SHOW_VERSION_UPDATE"] else None,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                ai_analysis=html_ai,
                standalone_data=html_standalone,
                frequency_file=self.frequency_file,
                report_metadata={
                    "hotlist_total": total_titles,
                    "platform_total": len(self.ctx.platform_ids),
                    "rss_matched_count": self._rss_matched_count,
                    "rss_total_count": self._rss_total_count,
                    "rss_source_total": self._rss_source_total,
                    "rss_source_failed": self._rss_source_failed,
                },
            )

        return stats, html_file, ai_result, rss_items

    def _send_notification_if_needed(
        self,
        stats: List[Dict],
        report_type: str,
        mode: str,
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        html_file_path: Optional[str] = None,
        rss_items: Optional[List[Dict]] = None,
        rss_new_items: Optional[List[Dict]] = None,
        standalone_data: Optional[Dict] = None,
        ai_result: Optional[AIAnalysisResult] = None,
        current_results: Optional[Dict] = None,
        schedule: ResolvedSchedule = None,
    ) -> bool:
        """Logique d'envoi de notification unifiée, regroupant toutes les conditions ; prend en charge l'envoi combiné tendances + RSS + analyse IA + zone d'affichage autonome."""
        has_notification = self._has_notification_configured()
        cfg = self.ctx.config

        # Vérifie s'il existe un contenu valide (tendances ou RSS)
        has_news_content = self._has_valid_content(stats, new_titles)
        has_rss_content = bool(rss_items and len(rss_items) > 0)
        has_any_content = has_news_content or has_rss_content

        # Calcule le nombre d'entrées de tendances correspondantes
        news_count = sum(len(stat.get("titles", [])) for stat in stats) if stats else 0
        rss_count = sum(stat.get("count", 0) for stat in rss_items) if rss_items else 0

        if (
            cfg["ENABLE_NOTIFICATION"]
            and has_notification
            and has_any_content
        ):
            # Affiche les statistiques du contenu à envoyer
            content_parts = []
            if news_count > 0:
                content_parts.append(f"Tendances : {news_count} entrée(s)")
            if rss_count > 0:
                content_parts.append(f"RSS : {rss_count} entrée(s)")
            total_count = news_count + rss_count
            print(f"[Envoi] Préparation de l'envoi : {' + '.join(content_parts)}, soit {total_count} entrée(s) au total")

            # Décision du système de planification
            if not schedule.push:
                print("[Envoi] Planification : la plage horaire actuelle n'exécute pas d'envoi")
                return False

            if schedule.once_push and schedule.period_key:
                scheduler = self.ctx.create_scheduler()
                date_str = self.ctx.format_date()
                if scheduler.already_executed(schedule.period_key, "push", date_str):
                    print(f"[Envoi] Planification : la plage horaire {schedule.period_name or schedule.period_key} a déjà fait l'objet d'un envoi aujourd'hui, on l'ignore")
                    return False
                else:
                    print(f"[Envoi] Planification : premier envoi de la journée pour la plage horaire {schedule.period_name or schedule.period_key}")

            # Analyse IA : réutilise en priorité le résultat déjà obtenu, pour éviter une analyse redondante
            if ai_result is None:
                ai_config = cfg.get("AI_ANALYSIS", {})
                if ai_config.get("ENABLED", False):
                    ai_result = self._run_ai_analysis(
                        stats, rss_items, mode, report_type, id_to_name,
                        current_results=current_results, schedule=schedule
                    )

            # Préparation des données du rapport
            report_data = self.ctx.prepare_report(stats, failed_ids, new_titles, id_to_name, mode, frequency_file=self.frequency_file)

            # Injection des métadonnées (pour l'affichage de l'en-tête de l'envoi)
            report_data["hotlist_total"] = self._hotlist_total_count
            report_data["platform_total"] = len(self.ctx.platform_ids)
            report_data["rss_matched_count"] = self._rss_matched_count
            report_data["rss_total_count"] = self._rss_total_count
            report_data["rss_source_total"] = self._rss_source_total
            report_data["rss_source_failed"] = self._rss_source_failed

            # Détermine s'il faut envoyer les informations de mise à jour de version
            update_info_to_send = self.update_info if cfg["SHOW_VERSION_UPDATE"] else None

            # Utilise NotificationDispatcher pour envoyer vers tous les canaux
            # Les données RSS / de la zone d'affichage autonome ont déjà été traduites dans le pipeline d'analyse ; on saute la traduction redondante (on ne traduit que les tendances dans report_data)
            dispatcher = self.ctx.create_notification_dispatcher()
            results = dispatcher.dispatch_all(
                report_data=report_data,
                report_type=report_type,
                update_info=update_info_to_send,
                proxy_url=self.proxy_url,
                mode=mode,
                html_file_path=html_file_path,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                ai_analysis=ai_result,
                standalone_data=standalone_data,
                skip_translation=True,
            )

            if not results:
                print("Aucun canal de notification configuré, envoi de la notification ignoré")
                return False

            # Enregistrement de l'envoi réussi
            if any(results.values()):
                if schedule.once_push and schedule.period_key:
                    scheduler = self.ctx.create_scheduler()
                    date_str = self.ctx.format_date()
                    scheduler.record_execution(schedule.period_key, "push", date_str)

            return True

        elif cfg["ENABLE_NOTIFICATION"] and not has_notification:
            print("⚠️ Avertissement : la fonction de notification est activée mais aucun canal de notification n'est configuré ; l'envoi de la notification sera ignoré")
        elif not cfg["ENABLE_NOTIFICATION"]:
            print(f"Notification « {report_type} » ignorée : la fonction de notification est désactivée")
        elif (
            cfg["ENABLE_NOTIFICATION"]
            and has_notification
            and not has_any_content
        ):
            mode_strategy = self._get_mode_strategy()
            if self.report_mode == "incremental":
                if not has_rss_content:
                    print("Notification ignorée : en mode incrémental, aucune actualité correspondante ni aucun flux RSS détecté")
                else:
                    print("Notification ignorée : en mode incrémental, aucune actualité ne correspond aux mots-clés")
            else:
                print(
                    f"Notification ignorée : en {mode_strategy['mode_name']}, aucune actualité correspondante détectée"
                )

        return False

    def _initialize_and_check_config(self) -> bool:
        """Initialisation générique et vérification de la configuration. Renvoie True si l'exécution peut se poursuivre."""
        now = self.ctx.get_time()
        print(f"Heure de Pékin actuelle : {now.strftime('%Y-%m-%d %H:%M:%S')}")

        if not self.ctx.config["ENABLE_CRAWLER"]:
            print("La fonction de collecte est désactivée (ENABLE_CRAWLER=False), le programme s'arrête")
            return False

        has_notification = self._has_notification_configured()
        if not self.ctx.config["ENABLE_NOTIFICATION"]:
            print("La fonction de notification est désactivée (ENABLE_NOTIFICATION=False), seule la collecte des données sera effectuée")
        elif not has_notification:
            print("Aucun canal de notification configuré, seule la collecte des données sera effectuée, sans envoi de notification")
        else:
            print("La fonction de notification est activée, des notifications seront envoyées")

        mode_strategy = self._get_mode_strategy()
        print(f"Mode de rapport : {self.report_mode}")
        print(f"Mode d'exécution : {mode_strategy['description']}")
        return True

    def _crawl_data(self) -> Tuple[Dict, Dict, List]:
        """Exécute la collecte des données."""
        ids = []
        domain_rules = {}
        for platform in self.ctx.platforms:
            if "name" in platform:
                ids.append((platform["id"], platform["name"]))
            else:
                ids.append(platform["id"])
            expected_domain = platform.get("expected_domain", "")
            if expected_domain:
                domain_rules[platform["id"]] = expected_domain

        print(
            f"Plateformes surveillées configurées : {[p.get('name', p['id']) for p in self.ctx.platforms]}"
        )
        print(f"Début de la collecte des données, intervalle entre les requêtes : {self.request_interval} millisecondes")
        Path("output").mkdir(parents=True, exist_ok=True)

        results, id_to_name, failed_ids = self.data_fetcher.crawl_websites(
            ids, self.request_interval, domain_rules=domain_rules
        )

        # Conversion au format NewsData puis enregistrement dans le backend de stockage
        crawl_time = self.ctx.format_time()
        crawl_date = self.ctx.format_date()
        news_data = convert_crawl_results_to_news_data(
            results, id_to_name, failed_ids, crawl_time, crawl_date
        )

        # Enregistrement dans le backend de stockage (SQLite)
        if self.storage_manager.save_news_data(news_data):
            print(f"Données enregistrées dans le backend de stockage : {self.storage_manager.backend_name}")

        # Enregistrement de l'instantané TXT (si activé)
        txt_file = self.storage_manager.save_txt_snapshot(news_data)
        if txt_file:
            print(f"Instantané TXT enregistré : {txt_file}")

        return results, id_to_name, failed_ids

    def _crawl_rss_data(self) -> Tuple[Optional[List[Dict]], Optional[List[Dict]], Optional[List[Dict]], set]:
        """
        Exécute la collecte des données RSS

        Returns:
            tuple (rss_items, rss_new_items, raw_rss_items, rss_new_urls) :
            - rss_items : liste des entrées statistiques (traitées selon le mode, pour le bloc des statistiques)
            - rss_new_items : liste des nouvelles entrées (pour le bloc des nouveautés)
            - raw_rss_items : liste des entrées RSS brutes (pour la zone d'affichage autonome)
            - rss_new_urls : ensemble des URL des nouvelles entrées RSS brutes (pour la détection is_new en mode IA)
            Renvoie (None, None, None, set()) si la fonction n'est pas activée ou en cas d'échec.
        """
        if not self.ctx.rss_enabled:
            return None, None, None, set()

        rss_feeds = self.ctx.rss_feeds
        if not rss_feeds:
            print("[RSS] Aucune source RSS configurée")
            return None, None, None, set()

        try:
            from trendradar.crawler.rss import RSSFetcher, RSSFeedConfig

            # Construction de la configuration des sources RSS
            feeds = []
            for feed_config in rss_feeds:
                # Lecture et validation du max_age_days de chaque flux (facultatif)
                max_age_days_raw = feed_config.get("max_age_days")
                max_age_days = None
                if max_age_days_raw is not None:
                    try:
                        max_age_days = int(max_age_days_raw)
                        if max_age_days < 0:
                            feed_id = feed_config.get("id", "unknown")
                            print(f"[Avertissement] Le max_age_days du flux RSS « {feed_id} » est négatif ; la valeur globale par défaut sera utilisée")
                            max_age_days = None
                    except (ValueError, TypeError):
                        feed_id = feed_config.get("id", "unknown")
                        print(f"[Avertissement] Format de max_age_days incorrect pour le flux RSS « {feed_id} » : {max_age_days_raw}")
                        max_age_days = None

                feed = RSSFeedConfig(
                    id=feed_config.get("id", ""),
                    name=feed_config.get("name", ""),
                    url=feed_config.get("url", ""),
                    max_items=feed_config.get("max_items", 50),
                    enabled=feed_config.get("enabled", True),
                    max_age_days=max_age_days,  # None = valeur globale, 0 = désactivé, >0 = remplace
                )
                if feed.id and feed.url and feed.enabled:
                    feeds.append(feed)

            if not feeds:
                print("[RSS] Aucune source RSS activée")
                return None, None, None, set()

            # Création du collecteur
            rss_config = self.ctx.rss_config
            # Proxy RSS : utilise en priorité le proxy dédié RSS, sinon le proxy par défaut du collecteur
            rss_proxy_url = rss_config.get("PROXY_URL", "") or self.proxy_url or ""
            # Récupération du fuseau horaire configuré
            timezone = self.ctx.config.get("TIMEZONE", DEFAULT_TIMEZONE)
            # Récupération de la configuration du filtrage par fraîcheur
            freshness_config = rss_config.get("FRESHNESS_FILTER", {})
            freshness_enabled = freshness_config.get("ENABLED", True)
            default_max_age_days = freshness_config.get("MAX_AGE_DAYS", 3)

            fetcher = RSSFetcher(
                feeds=feeds,
                request_interval=rss_config.get("REQUEST_INTERVAL", 2000),
                timeout=rss_config.get("TIMEOUT", 15),
                use_proxy=rss_config.get("USE_PROXY", False),
                proxy_url=rss_proxy_url,
                timezone=timezone,
                freshness_enabled=freshness_enabled,
                default_max_age_days=default_max_age_days,
            )

            # Collecte des données
            rss_data = fetcher.fetch_all()

            self._rss_source_total = len(feeds)
            self._rss_source_failed = len(rss_data.failed_ids)

            # Enregistrement dans le backend de stockage
            if self.storage_manager.save_rss_data(rss_data):
                print(f"[RSS] Données enregistrées dans le backend de stockage")

                # Traite les données RSS (filtrage selon le mode) et les renvoie pour l'envoi combiné
                return self._process_rss_data_by_mode(rss_data)
            else:
                print(f"[RSS] Échec de l'enregistrement des données")
                return None, None, None, set()

        except ImportError as e:
            print(f"[RSS] Dépendance manquante : {e}")
            print("[RSS] Veuillez installer feedparser : pip install feedparser")
            return None, None, None, set()
        except Exception as e:
            print(f"[RSS] Échec de la collecte : {e}")
            return None, None, None, set()

    def _process_rss_data_by_mode(self, rss_data) -> Tuple[Optional[List[Dict]], Optional[List[Dict]], Optional[List[Dict]], set]:
        """
        Traite les données RSS selon le mode de rapport et renvoie une structure statistique au même format que les tendances

        Trois modes possibles :
        - daily : synthèse de la journée, statistiques = toutes les entrées du jour, nouveautés = entrées ajoutées lors de cette exécution
        - current : classement actuel, statistiques = entrées du classement actuel, nouveautés = entrées ajoutées lors de cette exécution
        - incremental : mode incrémental, statistiques = entrées ajoutées, nouveautés = aucune

        Args:
            rss_data : objet RSSData de la collecte actuelle

        Returns:
            tuple (rss_stats, rss_new_stats, raw_rss_items, rss_new_urls) :
            - rss_stats : liste des statistiques RSS par mots-clés (même format que les stats des tendances)
            - rss_new_stats : liste des statistiques RSS des nouveautés par mots-clés (même format que les stats des tendances)
            - raw_rss_items : liste des entrées RSS brutes (pour la zone d'affichage autonome)
            - rss_new_urls : ensemble des URL des nouvelles entrées RSS brutes (sans filtrage par mots-clés, pour la détection is_new en mode IA)
        """
        from trendradar.core.analyzer import count_rss_frequency

        # display.regions.rss contrôle de façon unifiée l'analyse et l'affichage RSS
        rss_display_enabled = self.ctx.config.get("DISPLAY", {}).get("REGIONS", {}).get("RSS", True)

        # Chargement de la configuration des mots-clés
        try:
            word_groups, filter_words, global_filters = self.ctx.load_frequency_words(self.frequency_file)
        except FileNotFoundError:
            word_groups, filter_words, global_filters = [], [], []

        timezone = self.ctx.timezone
        max_news_per_keyword = self.ctx.config.get("MAX_NEWS_PER_KEYWORD", 0)
        sort_by_position_first = self.ctx.config.get("SORT_BY_POSITION_FIRST", False)

        rss_stats = None
        rss_new_stats = None
        raw_rss_items = None  # liste des entrées RSS brutes (pour la zone d'affichage autonome)
        rss_new_urls = set()  # URL RSS nouvelles brutes (sans filtrage par mots-clés)

        # 1. On récupère d'abord les entrées brutes (pour la zone d'affichage autonome, indépendamment de display.regions.rss)
        # Récupération des entrées brutes selon le mode
        if self.report_mode == "incremental":
            new_items_dict = self.storage_manager.detect_new_rss_items(rss_data)
            if new_items_dict:
                raw_rss_items = self._convert_rss_items_to_list(new_items_dict, rss_data.id_to_name)
        elif self.report_mode == "current":
            latest_data = self.storage_manager.get_latest_rss_data(rss_data.date)
            if latest_data:
                raw_rss_items = self._convert_rss_items_to_list(latest_data.items, latest_data.id_to_name)
        else:  # daily
            all_data = self.storage_manager.get_rss_data(rss_data.date)
            if all_data:
                raw_rss_items = self._convert_rss_items_to_list(all_data.items, all_data.id_to_name)

        # Si l'affichage RSS n'est pas activé, on saute l'analyse par mots-clés et on ne renvoie que les entrées brutes pour la zone d'affichage autonome
        if not rss_display_enabled:
            return None, None, raw_rss_items, rss_new_urls

        # 2. Récupération des nouvelles entrées (pour les statistiques)
        new_items_dict = self.storage_manager.detect_new_rss_items(rss_data)
        new_items_list = None
        if new_items_dict:
            new_items_list = self._convert_rss_items_to_list(new_items_dict, rss_data.id_to_name)
            if new_items_list:
                print(f"[RSS] {len(new_items_list)} nouvelle(s) entrée(s) détectée(s)")
                # Rassemble les URL des nouveautés brutes (sans filtrage par mots-clés, pour la détection is_new en mode IA)
                rss_new_urls = {item["url"] for item in new_items_list if item.get("url")}

        # 3. Récupération des entrées statistiques selon le mode
        if self.report_mode == "incremental":
            # Mode incrémental : les entrées statistiques sont les nouvelles entrées
            if not new_items_list:
                print("[RSS] Mode incrémental : aucune nouvelle entrée RSS")
                return None, None, raw_rss_items, rss_new_urls

            rss_stats, total = count_rss_frequency(
                rss_items=new_items_list,
                word_groups=word_groups,
                filter_words=filter_words,
                global_filters=global_filters,
                new_items=new_items_list,  # en mode incrémental, toutes les entrées sont des nouveautés
                max_news_per_keyword=max_news_per_keyword,
                sort_by_position_first=sort_by_position_first,
                timezone=timezone,
                rank_threshold=self.rank_threshold,
                quiet=False,
            )
            if not rss_stats:
                print("[RSS] Mode incrémental : aucun contenu après la correspondance par mots-clés")
                # Même si la correspondance par mots-clés est vide, on renvoie les entrées brutes pour la zone d'affichage autonome
                return None, None, raw_rss_items, rss_new_urls

        elif self.report_mode == "current":
            # Mode classement actuel : statistiques = toutes les entrées du classement actuel
            # raw_rss_items a déjà été récupéré plus haut
            if not raw_rss_items:
                print("[RSS] Mode classement actuel : aucune donnée RSS")
                return None, None, None, rss_new_urls

            rss_stats, total = count_rss_frequency(
                rss_items=raw_rss_items,
                word_groups=word_groups,
                filter_words=filter_words,
                global_filters=global_filters,
                new_items=new_items_list,  # marquage des nouveautés
                max_news_per_keyword=max_news_per_keyword,
                sort_by_position_first=sort_by_position_first,
                timezone=timezone,
                rank_threshold=self.rank_threshold,
                quiet=False,
            )
            if not rss_stats:
                print("[RSS] Mode classement actuel : aucun contenu après la correspondance par mots-clés")
                # Même si la correspondance par mots-clés est vide, on renvoie les entrées brutes pour la zone d'affichage autonome
                return None, None, raw_rss_items, rss_new_urls

            # Génération des statistiques des nouveautés
            if new_items_list:
                rss_new_stats, _ = count_rss_frequency(
                    rss_items=new_items_list,
                    word_groups=word_groups,
                    filter_words=filter_words,
                    global_filters=global_filters,
                    new_items=new_items_list,
                    max_news_per_keyword=max_news_per_keyword,
                    sort_by_position_first=sort_by_position_first,
                    timezone=timezone,
                    rank_threshold=self.rank_threshold,
                    quiet=True,
                )

        else:
            # Mode daily : statistiques = toutes les entrées du jour
            # raw_rss_items a déjà été récupéré plus haut
            if not raw_rss_items:
                print("[RSS] Mode synthèse de la journée : aucune donnée RSS")
                return None, None, None, rss_new_urls

            rss_stats, total = count_rss_frequency(
                rss_items=raw_rss_items,
                word_groups=word_groups,
                filter_words=filter_words,
                global_filters=global_filters,
                new_items=new_items_list,  # marquage des nouveautés
                max_news_per_keyword=max_news_per_keyword,
                sort_by_position_first=sort_by_position_first,
                timezone=timezone,
                rank_threshold=self.rank_threshold,
                quiet=False,
            )
            if not rss_stats:
                print("[RSS] Mode synthèse de la journée : aucun contenu après la correspondance par mots-clés")
                # Même si la correspondance par mots-clés est vide, on renvoie les entrées brutes pour la zone d'affichage autonome
                return None, None, raw_rss_items, rss_new_urls

            # Génération des statistiques des nouveautés
            if new_items_list:
                rss_new_stats, _ = count_rss_frequency(
                    rss_items=new_items_list,
                    word_groups=word_groups,
                    filter_words=filter_words,
                    global_filters=global_filters,
                    new_items=new_items_list,
                    max_news_per_keyword=max_news_per_keyword,
                    sort_by_position_first=sort_by_position_first,
                    timezone=timezone,
                    rank_threshold=self.rank_threshold,
                    quiet=True,
                )

        # Lors de la première collecte, toutes les entrées sont des nouveautés ; on supprime alors les statistiques des nouveautés pour éviter une duplication totale avec la zone principale
        if rss_new_stats and rss_stats:
            main_count = sum(len(s.get("titles", [])) for s in rss_stats)
            new_count = sum(len(s.get("titles", [])) for s in rss_new_stats)
            if new_count > 0 and new_count >= main_count:
                rss_new_stats = None

        self._rss_total_count = total
        return rss_stats, rss_new_stats, raw_rss_items, rss_new_urls

    def _convert_rss_items_to_list(self, items_dict: Dict, id_to_name: Dict) -> List[Dict]:
        """Convertit le dictionnaire d'entrées RSS en liste et applique le filtrage par fraîcheur (pour l'envoi)."""
        rss_items = []
        filtered_count = 0
        filtered_details = []  # journal détaillé pour le mode DEBUG

        # Récupération de la configuration du filtrage par fraîcheur
        rss_config = self.ctx.rss_config
        freshness_config = rss_config.get("FRESHNESS_FILTER", {})
        freshness_enabled = freshness_config.get("ENABLED", True)
        default_max_age_days = freshness_config.get("MAX_AGE_DAYS", 3)
        timezone = self.ctx.config.get("TIMEZONE", DEFAULT_TIMEZONE)
        debug_mode = self.ctx.config.get("DEBUG", False)

        # Construction de la correspondance feed_id -> max_age_days
        feed_max_age_map = {}
        for feed_cfg in self.ctx.rss_feeds:
            feed_id = feed_cfg.get("id", "")
            max_age = feed_cfg.get("max_age_days")
            if max_age is not None:
                try:
                    feed_max_age_map[feed_id] = int(max_age)
                except (ValueError, TypeError):
                    pass

        for feed_id, items in items_dict.items():
            # Détermine le max_age_days de ce flux
            max_days = feed_max_age_map.get(feed_id)
            if max_days is None:
                max_days = default_max_age_days

            for item in items:
                # Application du filtrage par fraîcheur (uniquement s'il est activé)
                if freshness_enabled and max_days > 0:
                    if item.published_at and not is_within_days(item.published_at, max_days, timezone):
                        filtered_count += 1
                        # Enregistre les informations détaillées pour le mode DEBUG
                        if debug_mode:
                            days_old = calculate_days_old(item.published_at, timezone)
                            feed_name = id_to_name.get(feed_id, feed_id)
                            filtered_details.append({
                                "title": item.title[:50] + "..." if len(item.title) > 50 else item.title,
                                "feed": feed_name,
                                "days_old": days_old,
                                "max_days": max_days,
                            })
                        continue  # ignore les articles dépassant le nombre de jours indiqué

                rss_items.append({
                    "title": item.title,
                    "feed_id": feed_id,
                    "feed_name": id_to_name.get(feed_id, feed_id),
                    "url": item.url,
                    "published_at": item.published_at,
                    "summary": item.summary,
                    "author": item.author,
                })

        # Affiche les statistiques de filtrage
        if filtered_count > 0:
            print(f"[RSS] Filtrage par fraîcheur : {filtered_count} ancien(s) article(s) dépassant le nombre de jours indiqué ont été ignorés (toujours conservés dans la base de données)")
            # Affiche les informations détaillées en mode DEBUG
            if debug_mode and filtered_details:
                print(f"[RSS] Détail des articles filtrés ({len(filtered_details)} article(s) au total) :")
                for detail in filtered_details[:10]:  # affiche 10 entrées au maximum
                    days_str = f"{detail['days_old']:.1f}" if detail['days_old'] else "inconnu"
                    print(f"  - [il y a {days_str} jour(s)] [{detail['feed']}] {detail['title']} (limite : {detail['max_days']} jour(s))")
                if len(filtered_details) > 10:
                    print(f"  ... et {len(filtered_details) - 10} autre(s) article(s) filtré(s)")

        return rss_items

    def _filter_rss_by_keywords(self, rss_items: List[Dict]) -> List[Dict]:
        """Filtre les entrées RSS à l'aide du fichier de mots-clés."""
        try:
            word_groups, filter_words, global_filters = self.ctx.load_frequency_words(self.frequency_file)
            if word_groups or filter_words or global_filters:
                from trendradar.core.frequency import matches_word_groups
                filtered_items = []
                for item in rss_items:
                    title = item.get("title", "")
                    if matches_word_groups(title, word_groups, filter_words, global_filters):
                        filtered_items.append(item)

                original_count = len(rss_items)
                rss_items = filtered_items
                print(f"[RSS] {len(rss_items)}/{original_count} entrée(s) restante(s) après le filtrage par mots-clés")

                if not rss_items:
                    print("[RSS] Aucun contenu correspondant après le filtrage par mots-clés")
                    return []
        except FileNotFoundError:
            # Si le fichier de mots-clés n'existe pas, on saute le filtrage
            pass
        return rss_items

    def _generate_rss_html_report(self, rss_items: list, feeds_info: dict) -> str:
        """Génère le rapport HTML RSS."""
        try:
            from trendradar.report.rss_html import render_rss_html_content
            from pathlib import Path

            html_content = render_rss_html_content(
                rss_items=rss_items,
                total_count=len(rss_items),
                feeds_info=feeds_info,
                get_time_func=self.ctx.get_time,
            )

            # Enregistrement du fichier HTML (structure aplatie : output/html/date/)
            date_folder = self.ctx.format_date()
            time_filename = self.ctx.format_time()
            output_dir = Path("output") / "html" / date_folder
            output_dir.mkdir(parents=True, exist_ok=True)

            file_path = output_dir / f"rss_{time_filename}.html"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"[RSS] Rapport HTML généré : {file_path}")
            return str(file_path)

        except Exception as e:
            print(f"[RSS] Échec de la génération du rapport HTML : {e}")
            return None

    def _execute_mode_strategy(
        self, mode_strategy: Dict, results: Dict, id_to_name: Dict, failed_ids: List,
        rss_items: Optional[List[Dict]] = None,
        rss_new_items: Optional[List[Dict]] = None,
        raw_rss_items: Optional[List[Dict]] = None,
        rss_new_urls: Optional[set] = None,
    ) -> Optional[str]:
        """Exécute la logique propre au mode, avec prise en charge de l'envoi combiné tendances + RSS

        Logique simplifiée :
        - chaque exécution génère un rapport HTML (instantané horodaté + latest/{mode}.html + index.html)
        - envoi de la notification selon le mode
        """
        # Système de planification
        scheduler = self.ctx.create_scheduler()
        schedule = scheduler.resolve()

        # Le report_mode déterminé par schedule remplace la configuration globale
        effective_mode = schedule.report_mode
        if effective_mode != self.report_mode:
            print(f"[Planification] Mode de rapport remplacé : {self.report_mode} -> {effective_mode}")
        self.report_mode = effective_mode

        # On récupère à nouveau mode_strategy pour garantir la cohérence de report_type avec le report_mode après remplacement
        mode_strategy = self._get_mode_strategy()

        # Le frequency_file déterminé par schedule remplace la valeur par défaut
        self.frequency_file = schedule.frequency_file

        # La stratégie de filtrage déterminée par schedule remplace la valeur par défaut
        self.filter_method = schedule.filter_method or self.ctx.filter_method

        # Le fichier de centres d'intérêt du filtrage IA déterminé par schedule remplace la valeur par défaut
        self.interests_file = schedule.interests_file

        # Si le planificateur indique de ne pas collecter, on passe directement
        if not schedule.collect:
            print("[Planification] La plage horaire actuelle n'exécute pas de collecte de données, le pipeline d'analyse est ignoré")
            return None
        # Récupère la liste des ID de plateformes actuellement surveillées
        current_platform_ids = self.ctx.platform_ids

        new_titles = self.ctx.detect_new_titles(current_platform_ids)
        time_info = self.ctx.format_time()
        word_groups, filter_words, global_filters = self.ctx.load_frequency_words(self.frequency_file)

        html_file = None
        stats = []
        ai_result = None
        title_info = None

        # Le mode current nécessite l'utilisation de l'ensemble des données historiques
        if self.report_mode == "current":
            analysis_data = self._load_analysis_data()
            if analysis_data:
                (
                    all_results,
                    historical_id_to_name,
                    historical_title_info,
                    historical_new_titles,
                    _,
                    _,
                    _,
                ) = analysis_data

                print(
                    f"Mode current : utilisation des données historiques filtrées, plateformes incluses : {list(all_results.keys())}"
                )

                # Préparation des données de la zone d'affichage autonome à partir des données historiques (avec le title_info complet)
                standalone_data = self._prepare_standalone_data(
                    all_results, historical_id_to_name, historical_title_info, raw_rss_items
                )

                stats, html_file, ai_result, rss_items = self._run_analysis_pipeline(
                    all_results,
                    self.report_mode,
                    historical_title_info,
                    historical_new_titles,
                    word_groups,
                    filter_words,
                    historical_id_to_name,
                    failed_ids=failed_ids,
                    global_filters=global_filters,
                    rss_items=rss_items,
                    rss_new_items=rss_new_items,
                    standalone_data=standalone_data,
                    schedule=schedule,
                    rss_new_urls=rss_new_urls,
                )

                combined_id_to_name = {**historical_id_to_name, **id_to_name}
                new_titles = historical_new_titles
                id_to_name = combined_id_to_name
                title_info = historical_title_info
                results = all_results
            elif not current_platform_ids:
                # Mode « RSS seul » (fork halal) : aucune plateforme de palmarès surveillée, donc
                # aucune donnée historique de palmarès n'est attendue. On génère le rapport à
                # partir des données actuelles (flux RSS), comme le fait déjà le mode daily.
                # NB : déviation assumée du « no logic change » pour faire fonctionner la config
                # RSS-only imposée — voir CHANGES.md.
                title_info = self._prepare_current_title_info(results, time_info)
                standalone_data = self._prepare_standalone_data(
                    results, id_to_name, title_info, raw_rss_items
                )
                stats, html_file, ai_result, rss_items = self._run_analysis_pipeline(
                    results,
                    self.report_mode,
                    title_info,
                    new_titles,
                    word_groups,
                    filter_words,
                    id_to_name,
                    failed_ids=failed_ids,
                    global_filters=global_filters,
                    rss_items=rss_items,
                    rss_new_items=rss_new_items,
                    standalone_data=standalone_data,
                    schedule=schedule,
                    rss_new_urls=rss_new_urls,
                )
            else:
                # Avec des plateformes de palmarès surveillées, une lecture vide signale une
                # vraie incohérence de stockage (enregistrement puis lecture immédiate échouée).
                print("❌ Erreur grave : impossible de lire le fichier de données qui vient d'être enregistré")
                raise RuntimeError("Échec de la vérification de cohérence des données : lecture impossible immédiatement après l'enregistrement")
        elif self.report_mode == "daily":
            # Mode daily : utilise les données cumulées de toute la journée
            analysis_data = self._load_analysis_data()
            if analysis_data:
                (
                    all_results,
                    historical_id_to_name,
                    historical_title_info,
                    historical_new_titles,
                    _,
                    _,
                    _,
                ) = analysis_data

                # Préparation des données de la zone d'affichage autonome à partir des données historiques (avec le title_info complet)
                standalone_data = self._prepare_standalone_data(
                    all_results, historical_id_to_name, historical_title_info, raw_rss_items
                )

                stats, html_file, ai_result, rss_items = self._run_analysis_pipeline(
                    all_results,
                    self.report_mode,
                    historical_title_info,
                    historical_new_titles,
                    word_groups,
                    filter_words,
                    historical_id_to_name,
                    failed_ids=failed_ids,
                    global_filters=global_filters,
                    rss_items=rss_items,
                    rss_new_items=rss_new_items,
                    standalone_data=standalone_data,
                    schedule=schedule,
                    rss_new_urls=rss_new_urls,
                )

                combined_id_to_name = {**historical_id_to_name, **id_to_name}
                new_titles = historical_new_titles
                id_to_name = combined_id_to_name
                title_info = historical_title_info
                results = all_results
            else:
                # En l'absence de données historiques, on utilise les données actuelles
                title_info = self._prepare_current_title_info(results, time_info)
                standalone_data = self._prepare_standalone_data(
                    results, id_to_name, title_info, raw_rss_items
                )
                stats, html_file, ai_result, rss_items = self._run_analysis_pipeline(
                    results,
                    self.report_mode,
                    title_info,
                    new_titles,
                    word_groups,
                    filter_words,
                    id_to_name,
                    failed_ids=failed_ids,
                    global_filters=global_filters,
                    rss_items=rss_items,
                    rss_new_items=rss_new_items,
                    standalone_data=standalone_data,
                    schedule=schedule,
                    rss_new_urls=rss_new_urls,
                )
        else:
            # Mode incremental : utilise uniquement les données de la collecte actuelle
            title_info = self._prepare_current_title_info(results, time_info)
            standalone_data = self._prepare_standalone_data(
                results, id_to_name, title_info, raw_rss_items
            )
            stats, html_file, ai_result, rss_items = self._run_analysis_pipeline(
                results,
                self.report_mode,
                title_info,
                new_titles,
                word_groups,
                filter_words,
                id_to_name,
                failed_ids=failed_ids,
                global_filters=global_filters,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                standalone_data=standalone_data,
                schedule=schedule,
                rss_new_urls=rss_new_urls,
            )

        if html_file:
            print(f"Rapport HTML généré : {html_file}")
            print(f"Dernier rapport mis à jour : output/html/latest/{self.report_mode}.html")

        # Envoi de la notification
        if mode_strategy["should_send_notification"]:
            standalone_data = self._prepare_standalone_data(
                results, id_to_name, title_info, raw_rss_items
            )
            self._send_notification_if_needed(
                stats,
                mode_strategy["report_type"],
                self.report_mode,
                failed_ids=failed_ids,
                new_titles=new_titles,
                id_to_name=id_to_name,
                html_file_path=html_file,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                standalone_data=standalone_data,
                ai_result=ai_result,
                current_results=results,
                schedule=schedule,
            )

        # Ouverture du navigateur (uniquement hors environnement conteneurisé)
        if self._should_open_browser() and html_file:
            file_url = "file://" + str(Path(html_file).resolve())
            print(f"Ouverture du rapport HTML en cours : {file_url}")
            webbrowser.open(file_url)
        elif self.is_docker_container and html_file:
            print(f"Rapport HTML généré (environnement Docker) : {html_file}")

        return html_file

    def run(self) -> None:
        """Exécute le processus d'analyse."""
        try:
            if not self._initialize_and_check_config():
                return

            mode_strategy = self._get_mode_strategy()

            # Collecte des données de tendances
            results, id_to_name, failed_ids = self._crawl_data()

            # Collecte des données RSS (si activée) ; renvoie les entrées statistiques, les nouvelles entrées et les entrées brutes
            rss_items, rss_new_items, raw_rss_items, rss_new_urls = self._crawl_rss_data()

            # Exécute la stratégie de mode, en transmettant les données RSS pour l'envoi combiné
            self._execute_mode_strategy(
                mode_strategy, results, id_to_name, failed_ids,
                rss_items=rss_items, rss_new_items=rss_new_items,
                raw_rss_items=raw_rss_items, rss_new_urls=rss_new_urls
            )

        except Exception as e:
            print(f"Erreur lors de l'exécution du processus d'analyse : {e}")
            if self.ctx.config.get("DEBUG", False):
                raise
        finally:
            # Nettoyage des ressources (y compris la purge des données expirées et la fermeture de la connexion à la base de données)
            self.ctx.cleanup()


def _record_doctor_result(results: List[Tuple[str, str, str]], status: str, item: str, detail: str) -> None:
    """Enregistre et affiche le résultat d'une vérification doctor."""
    icon_map = {
        "pass": "✅",
        "warn": "⚠️",
        "fail": "❌",
    }
    icon = icon_map.get(status, "•")
    results.append((status, item, detail))
    print(f"{icon} {item}: {detail}")


def _save_doctor_report(
    results: List[Tuple[str, str, str]],
    pass_count: int,
    warn_count: int,
    fail_count: int,
    config_path: Optional[str],
) -> None:
    """Enregistre le rapport de diagnostic doctor dans un fichier JSON."""
    report = {
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": config_path or os.environ.get("CONFIG_PATH", "config/config.yaml"),
        "summary": {
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
            "ok": fail_count == 0,
        },
        "checks": [
            {"status": status, "item": item, "detail": detail}
            for status, item, detail in results
        ],
    }

    try:
        output_dir = Path("output") / "meta"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "doctor_report.json"
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Rapport de diagnostic enregistré : {output_path}")
    except Exception as e:
        print(f"⚠️ Échec de l'enregistrement du rapport de diagnostic : {e}")


def _run_doctor(config_path: Optional[str] = None) -> bool:
    """Exécute le diagnostic de l'environnement."""
    print("=" * 60)
    print(f"TrendRadar v{__version__} : diagnostic de l'environnement")
    print("=" * 60)

    results: List[Tuple[str, str, str]] = []
    config = None

    # 1) Vérification de la version de Python
    py_ok = sys.version_info >= (3, 10)
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if py_ok:
        _record_doctor_result(results, "pass", "Version de Python", f"{py_version} (satisfait >= 3.10)")
    else:
        _record_doctor_result(results, "fail", "Version de Python", f"{py_version} (ne satisfait pas >= 3.10)")

    # 2) Vérification des fichiers essentiels
    if config_path is None:
        config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

    required_files = [
        (config_path, "Fichier de configuration principal"),
        ("config/frequency_words.txt", "Fichier de mots-clés"),
    ]
    optional_files = [
        ("config/timeline.yaml", "Fichier de planification"),
    ]

    for path_str, desc in required_files:
        if Path(path_str).exists():
            _record_doctor_result(results, "pass", desc, f"trouvé : {path_str}")
        else:
            _record_doctor_result(results, "fail", desc, f"manquant : {path_str}")

    for path_str, desc in optional_files:
        if Path(path_str).exists():
            _record_doctor_result(results, "pass", desc, f"trouvé : {path_str}")
        else:
            _record_doctor_result(results, "warn", desc, f"introuvable : {path_str} (le modèle de planification par défaut sera utilisé)")

    # 3) Vérification du chargement de la configuration
    try:
        config = load_config(config_path)
        _record_doctor_result(results, "pass", "Chargement de la configuration", f"chargement réussi : {config_path}")
    except Exception as e:
        _record_doctor_result(results, "fail", "Chargement de la configuration", f"échec du chargement : {e}")

    # Les vérifications suivantes dépendent de l'objet de configuration
    if config:
        # 4) Vérification de la configuration de planification
        try:
            ctx = AppContext(config)
            schedule = ctx.create_scheduler().resolve()
            detail = f"analyse de la planification réussie (report_mode={schedule.report_mode}, ai_mode={schedule.ai_mode})"
            _record_doctor_result(results, "pass", "Configuration de planification", detail)
        except Exception as e:
            _record_doctor_result(results, "fail", "Configuration de planification", f"échec de l'analyse : {e}")

        # 5) Vérification de la configuration IA (le niveau de gravité dépend du scénario fonctionnel)
        ai_analysis_enabled = config.get("AI_ANALYSIS", {}).get("ENABLED", False)
        ai_translation_enabled = config.get("AI_TRANSLATION", {}).get("ENABLED", False)
        ai_filter_enabled = config.get("FILTER", {}).get("METHOD", "keyword") == "ai"
        ai_enabled = ai_analysis_enabled or ai_translation_enabled or ai_filter_enabled

        if ai_enabled:
            try:
                from trendradar.ai.client import AIClient
                valid, message = AIClient(config.get("AI", {})).validate_config()
                if valid:
                    _record_doctor_result(results, "pass", "Configuration IA", f"modèle : {config.get('AI', {}).get('MODEL', '')}")
                else:
                    # L'analyse et la traduction IA sont des dépendances strictes ; en cas d'absence, le filtrage IA bascule automatiquement sur la correspondance par mots-clés
                    if ai_analysis_enabled or ai_translation_enabled:
                        _record_doctor_result(results, "fail", "Configuration IA", message)
                    else:
                        _record_doctor_result(results, "warn", "Configuration IA", f"{message} (le filtrage IA basculera en mode mots-clés)")
            except Exception as e:
                _record_doctor_result(results, "fail", "Configuration IA", f"exception lors de la vérification : {e}")
        else:
            _record_doctor_result(results, "warn", "Configuration IA", "fonction IA non activée, vérification ignorée")

        # 6) Vérification de la configuration de stockage
        try:
            storage_cfg = config.get("STORAGE", {})
            backend = storage_cfg.get("BACKEND", "auto")
            remote = storage_cfg.get("REMOTE", {})
            missing_remote_keys = [
                k for k in ("BUCKET_NAME", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY", "ENDPOINT_URL")
                if not remote.get(k)
            ]

            if backend == "remote" and missing_remote_keys:
                _record_doctor_result(
                    results, "fail", "Configuration de stockage",
                    f"configuration manquante pour le mode remote : {', '.join(missing_remote_keys)}"
                )
            elif backend == "auto" and os.environ.get("GITHUB_ACTIONS") == "true" and missing_remote_keys:
                _record_doctor_result(
                    results, "warn", "Configuration de stockage",
                    "GitHub Actions + mode auto : stockage distant incomplètement configuré, ce qui peut entraîner une perte de données"
                )
            else:
                sm = AppContext(config).get_storage_manager()
                _record_doctor_result(results, "pass", "Configuration de stockage", f"backend actuel : {sm.backend_name}")
        except Exception as e:
            _record_doctor_result(results, "fail", "Configuration de stockage", f"échec de la vérification : {e}")

        # 7) Vérification de la configuration des canaux de notification
        channel_details = []
        channel_issues = []
        max_accounts = config.get("MAX_ACCOUNTS_PER_CHANNEL", 3)

        # Canaux à valeur unique / valeurs multiples ordinaires
        for key, name in [
            ("FEISHU_WEBHOOK_URL", "Feishu"),
            ("DINGTALK_WEBHOOK_URL", "DingTalk"),
            ("WEWORK_WEBHOOK_URL", "WeCom"),
            ("BARK_URL", "Bark"),
            ("SLACK_WEBHOOK_URL", "Slack"),
            ("GENERIC_WEBHOOK_URL", "Webhook générique"),
        ]:
            values = parse_multi_account_config(config.get(key, ""))
            if values:
                channel_details.append(f"{name} ({min(len(values), max_accounts)})")

        # Vérification de l'appariement Telegram
        tg_tokens = parse_multi_account_config(config.get("TELEGRAM_BOT_TOKEN", ""))
        tg_chats = parse_multi_account_config(config.get("TELEGRAM_CHAT_ID", ""))
        if tg_tokens or tg_chats:
            valid, count = validate_paired_configs(
                {"bot_token": tg_tokens, "chat_id": tg_chats},
                "Telegram",
                required_keys=["bot_token", "chat_id"],
            )
            if valid and count > 0:
                channel_details.append(f"Telegram ({min(count, max_accounts)})")
            else:
                channel_issues.append("Configuration Telegram bot_token/chat_id incomplète ou nombres incohérents")

        # Vérification de l'appariement ntfy (token facultatif)
        ntfy_server = config.get("NTFY_SERVER_URL", "")
        ntfy_topics = parse_multi_account_config(config.get("NTFY_TOPIC", ""))
        ntfy_tokens = parse_multi_account_config(config.get("NTFY_TOKEN", ""))
        if ntfy_server and ntfy_topics:
            if ntfy_tokens:
                valid, count = validate_paired_configs(
                    {"topic": ntfy_topics, "token": ntfy_tokens},
                    "ntfy",
                )
                if valid and count > 0:
                    channel_details.append(f"ntfy ({min(count, max_accounts)})")
                else:
                    channel_issues.append("Nombres ntfy topic/token incohérents")
            else:
                channel_details.append(f"ntfy ({min(len(ntfy_topics), max_accounts)})")

        # Complétude de la configuration e-mail
        email_ready = all(
            [
                config.get("EMAIL_FROM"),
                config.get("EMAIL_PASSWORD"),
                config.get("EMAIL_TO"),
            ]
        )
        if email_ready:
            channel_details.append("e-mail")
        elif any([config.get("EMAIL_FROM"), config.get("EMAIL_PASSWORD"), config.get("EMAIL_TO")]):
            channel_issues.append("Configuration e-mail incomplète (from/password/to doivent être configurés ensemble)")

        if channel_issues and not channel_details:
            _record_doctor_result(results, "fail", "Configuration des notifications", " ; ".join(channel_issues))
        elif channel_issues and channel_details:
            detail = f"Canaux disponibles : {', '.join(channel_details)} ; problèmes : {' ; '.join(channel_issues)}"
            _record_doctor_result(results, "warn", "Configuration des notifications", detail)
        elif channel_details:
            _record_doctor_result(results, "pass", "Configuration des notifications", f"Canaux disponibles : {', '.join(channel_details)}")
        else:
            _record_doctor_result(results, "warn", "Configuration des notifications", "aucun canal de notification configuré")

        # 8) Vérification de l'accès en écriture au répertoire de sortie
        try:
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)
            probe_file = output_dir / ".doctor_write_probe"
            probe_file.write_text("ok", encoding="utf-8")
            probe_file.unlink(missing_ok=True)
            _record_doctor_result(results, "pass", "Répertoire de sortie", f"accessible en écriture : {output_dir}")
        except Exception as e:
            _record_doctor_result(results, "fail", "Répertoire de sortie", f"non accessible en écriture : {e}")

    pass_count = sum(1 for status, _, _ in results if status == "pass")
    warn_count = sum(1 for status, _, _ in results if status == "warn")
    fail_count = sum(1 for status, _, _ in results if status == "fail")

    _save_doctor_report(results, pass_count, warn_count, fail_count, config_path)

    print("-" * 60)
    print(f"Résultat du diagnostic : ✅ {pass_count} réussite(s)  ⚠️ {warn_count} avertissement(s)  ❌ {fail_count} échec(s)")
    print("=" * 60)

    if fail_count == 0:
        print("Diagnostic réussi.")
        return True

    print("Diagnostic échoué, veuillez d'abord corriger les éléments en échec.")
    return False


def _build_test_report_data(ctx: AppContext) -> Dict:
    """Construit les données de rapport utilisées pour le test de notification."""
    now = ctx.get_time()
    time_display = now.strftime("%H:%M")
    title = f"Message de test de notification TrendRadar ({now.strftime('%Y-%m-%d %H:%M:%S')})"

    return {
        "stats": [
            {
                "word": "test de connectivité",
                "count": 1,
                "titles": [
                    {
                        "title": title,
                        "source_name": "TrendRadar",
                        "url": "https://github.com/sansan0/TrendRadar",
                        "mobile_url": "",
                        "ranks": [1],
                        "rank_threshold": ctx.rank_threshold,
                        "count": 1,
                        "is_new": True,
                        "time_display": time_display,
                        "matched_keyword": "test de connectivité",
                    }
                ],
            }
        ],
        "failed_ids": [],
        "new_titles": [],
        "id_to_name": {},
    }


def _create_test_html_file(ctx: AppContext) -> Optional[str]:
    """Crée le fichier HTML utilisé pour le test d'e-mail."""
    try:
        now = ctx.get_time()
        output_dir = Path("output") / "html" / ctx.format_date()
        output_dir.mkdir(parents=True, exist_ok=True)
        html_path = output_dir / f"notification_test_{ctx.format_time()}.html"
        html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Test de notification TrendRadar</title></head>
<body>
<h2>TrendRadar - Test de connectivité des notifications</h2>
<p>Heure du test : {now.strftime('%Y-%m-%d %H:%M:%S')} ({ctx.timezone})</p>
<p>Ceci est un message de test, destiné à vérifier que le canal e-mail est bien joignable.</p>
</body>
</html>"""
        html_path.write_text(html_content, encoding="utf-8")
        return str(html_path)
    except Exception as e:
        print(f"[Test de notification] Échec de la création du HTML de test : {e}")
        return None


def _run_test_notification(config: Dict) -> bool:
    """Envoie une notification de test vers les canaux déjà configurés."""
    from trendradar.notification import NotificationDispatcher

    ctx = AppContext(config)

    try:
        # Vérifie si un canal de notification est configuré
        has_notification = any(
            [
                config.get("FEISHU_WEBHOOK_URL"),
                config.get("DINGTALK_WEBHOOK_URL"),
                config.get("WEWORK_WEBHOOK_URL"),
                (config.get("TELEGRAM_BOT_TOKEN") and config.get("TELEGRAM_CHAT_ID")),
                (config.get("EMAIL_FROM") and config.get("EMAIL_PASSWORD") and config.get("EMAIL_TO")),
                (config.get("NTFY_SERVER_URL") and config.get("NTFY_TOPIC")),
                config.get("BARK_URL"),
                config.get("SLACK_WEBHOOK_URL"),
                config.get("GENERIC_WEBHOOK_URL"),
            ]
        )
        if not has_notification:
            print("Aucun canal de notification disponible détecté, veuillez d'abord en configurer un dans config.yaml ou via une variable d'environnement.")
            return False

        # On fige les zones d'affichage pendant le test, pour éviter qu'une désactivation de HOTLIST par l'utilisateur ne rende le contenu de test vide
        test_config = copy.deepcopy(config)
        test_display = test_config.setdefault("DISPLAY", {})
        test_regions = test_display.setdefault("REGIONS", {})
        test_regions.update(
            {
                "HOTLIST": True,
                "NEW_ITEMS": False,
                "RSS": False,
                "STANDALONE": False,
                "AI_ANALYSIS": False,
            }
        )

        # On désactive la traduction pendant le test, pour éviter de déclencher des appels IA supplémentaires (et la consommation de quota associée)
        if "AI_TRANSLATION" in test_config:
            test_config["AI_TRANSLATION"]["ENABLED"] = False

        proxy_url = test_config.get("DEFAULT_PROXY", "") if test_config.get("USE_PROXY") else None
        if proxy_url:
            print("[Test de notification] Configuration de proxy détectée, l'envoi se fera via le proxy")

        dispatcher = NotificationDispatcher(
            config=test_config,
            get_time_func=ctx.get_time,
            split_content_func=ctx.split_content,
            translator=None,
        )

        report_data = _build_test_report_data(ctx)
        html_file_path = _create_test_html_file(ctx)

        print("=" * 60)
        print("Test de connectivité des notifications")
        print("=" * 60)

        results = dispatcher.dispatch_all(
            report_data=report_data,
            report_type="Test de connectivité des notifications",
            proxy_url=proxy_url,
            mode="daily",
            html_file_path=html_file_path,
        )

        if not results:
            print("Aucun canal de notification valide à tester (la configuration est peut-être incomplète).")
            return False

        print("-" * 60)
        success_count = 0
        for channel, ok in results.items():
            if ok:
                success_count += 1
                print(f"✅ {channel} : test réussi")
            else:
                print(f"❌ {channel} : test échoué")

        print("-" * 60)
        print(f"Résultat du test : {success_count}/{len(results)} canal/canaux réussi(s)")
        return success_count > 0
    finally:
        ctx.cleanup()


def _load_dotenv() -> None:
    """Charge les variables d'un fichier .env dans os.environ (sans rien écraser).

    Recherche un fichier .env dans le répertoire courant puis à la racine du dépôt.
    Les vraies variables d'environnement gardent la priorité (env > .env). Aucune
    dépendance externe. Format : lignes ``CLE=valeur`` ; ``#`` = commentaire ;
    préfixe ``export`` et guillemets simples/doubles tolérés.
    """
    seen = set()
    for path in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        try:
            resolved = path.resolve()
            if resolved in seen or not path.is_file():
                continue
            seen.add(resolved)
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.lower().startswith("export "):
                    line = line[7:].lstrip()
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except OSError:
            continue


def main():
    """Point d'entrée du programme principal."""
    # Charge un éventuel fichier .env (clés API, secrets) avant toute lecture de config
    _load_dotenv()

    # Analyse des arguments de la ligne de commande
    parser = argparse.ArgumentParser(
        description="TrendRadar - outil d'agrégation et d'analyse des actualités tendance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commandes d'état de la planification :
  --show-schedule        affiche l'état actuel de la planification (plage horaire, interrupteurs de comportement)
Commandes de diagnostic :
  --doctor               exécute le diagnostic de l'environnement et de la configuration
  --test-notification    envoie une notification de test vers les canaux déjà configurés

Exemples :
  python -m trendradar                    # exécution normale
  python -m trendradar --show-schedule    # affiche l'état actuel de la planification
  python -m trendradar --doctor           # exécute un diagnostic en une commande
  python -m trendradar --test-notification # teste la connectivité des canaux de notification
"""
    )
    parser.add_argument(
        "--show-schedule",
        action="store_true",
        help="affiche l'état actuel de la planification"
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="exécute le diagnostic de l'environnement et de la configuration"
    )
    parser.add_argument(
        "--test-notification",
        action="store_true",
        help="envoie une notification de test vers les canaux déjà configurés"
    )

    args = parser.parse_args()

    debug_mode = False
    try:
        # Traitement de la commande doctor (ne dépend pas du processus d'exécution complet)
        if args.doctor:
            ok = _run_doctor()
            if not ok:
                raise SystemExit(1)
            return

        # Chargement de la configuration en premier
        config = load_config()

        # Traitement de la commande d'affichage de l'état
        if args.show_schedule:
            _handle_status_commands(config)
            return

        # Traitement de la commande de test de notification
        if args.test_notification:
            ok = _run_test_notification(config)
            if not ok:
                raise SystemExit(1)
            return

        version_url = config.get("VERSION_CHECK_URL", "")
        configs_version_url = config.get("CONFIGS_VERSION_CHECK_URL", "")

        # Vérification unifiée des versions (version du programme + version des fichiers de configuration, une seule requête distante)
        need_update = False
        remote_version = None
        if version_url:
            need_update, remote_version = check_all_versions(version_url, configs_version_url)

        # Réutilise la configuration déjà chargée, pour éviter un double chargement
        analyzer = NewsAnalyzer(config=config)

        # Définit les informations de mise à jour (réutilise la version distante déjà récupérée, sans nouvelle requête)
        if analyzer.is_github_actions and need_update and remote_version:
            analyzer.update_info = {
                "current_version": __version__,
                "remote_version": remote_version,
            }

        # Récupère la configuration debug
        debug_mode = analyzer.ctx.config.get("DEBUG", False)
        analyzer.run()
    except FileNotFoundError as e:
        print(f"❌ Erreur de fichier de configuration : {e}")
        print("\nVeuillez vous assurer que les fichiers suivants existent :")
        print("  • config/config.yaml")
        print("  • config/frequency_words.txt")
        print("\nConsultez la documentation du projet pour une configuration correcte")
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution du programme : {e}")
        if debug_mode:
            raise


def _handle_status_commands(config: Dict) -> None:
    """Traite la commande d'affichage de l'état - affiche l'état actuel de la planification."""
    from trendradar.context import AppContext

    ctx = AppContext(config)

    print("=" * 60)
    print(f"TrendRadar v{__version__} : état de la planification")
    print("=" * 60)

    try:
        scheduler = ctx.create_scheduler()
        schedule = scheduler.resolve()

        now = ctx.get_time()
        date_str = ctx.format_date()

        print(f"\n⏰ Heure actuelle : {now.strftime('%Y-%m-%d %H:%M:%S')} ({ctx.timezone})")
        print(f"📅 Date actuelle : {date_str}")

        print(f"\n📋 Informations de planification :")
        print(f"  Plan du jour : {schedule.day_plan}")
        if schedule.period_key:
            print(f"  Plage horaire actuelle : {schedule.period_name or schedule.period_key} ({schedule.period_key})")
        else:
            print(f"  Plage horaire actuelle : aucune (utilisation de la configuration par défaut)")

        print(f"\n🔧 Interrupteurs de comportement :")
        print(f"  Collecte des données : {'✅ oui' if schedule.collect else '❌ non'}")
        print(f"  Analyse IA :  {'✅ oui' if schedule.analyze else '❌ non'}")
        print(f"  Notification : {'✅ oui' if schedule.push else '❌ non'}")
        print(f"  Mode de rapport : {schedule.report_mode}")
        print(f"  Mode IA :  {schedule.ai_mode}")

        if schedule.period_key:
            print(f"\n🔁 Contrôle d'unicité :")
            if schedule.once_analyze:
                already_analyzed = scheduler.already_executed(schedule.period_key, "analyze", date_str)
                etat_a = "(déjà exécuté aujourd'hui ⚠️)" if already_analyzed else "(pas encore exécuté aujourd'hui ✅)"
                print(f"  Analyse IA :  une seule fois {etat_a}")
            else:
                print(f"  Analyse IA :  nombre de fois illimité")
            if schedule.once_push:
                already_pushed = scheduler.already_executed(schedule.period_key, "push", date_str)
                etat_p = "(déjà exécuté aujourd'hui ⚠️)" if already_pushed else "(pas encore exécuté aujourd'hui ✅)"
                print(f"  Notification : une seule fois {etat_p}")
            else:
                print(f"  Notification : nombre de fois illimité")

    except Exception as e:
        print(f"\n❌ Échec de la récupération de l'état de la planification : {e}")

    print("\n" + "=" * 60)

    # Nettoyage des ressources
    ctx.cleanup()


if __name__ == "__main__":
    main()
