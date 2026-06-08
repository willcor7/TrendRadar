# coding=utf-8
"""
Module de contexte d'application

Fournit une classe de contexte qui encapsule les opérations dépendant de la configuration, éliminant l'état global et les fonctions d'enrobage.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from trendradar.utils.time import (
    DEFAULT_TIMEZONE,
    get_configured_time,
    format_date_folder,
    format_time_filename,
    get_current_time_display,
    convert_time_for_display,
    format_iso_time_friendly,
    is_within_days,
)
from trendradar.core import (
    load_frequency_words,
    matches_word_groups,
    read_all_today_titles,
    detect_latest_new_titles,
    count_word_frequency,
    Scheduler,
)
from trendradar.report import (
    prepare_report_data,
    generate_html_report,
    render_html_content,
)
from trendradar.notification import (
    render_feishu_content,
    render_dingtalk_content,
    split_content_into_batches,
    NotificationDispatcher,
)
from trendradar.ai import AITranslator
from trendradar.ai.filter import AIFilter, AIFilterResult
from trendradar.storage import get_storage_manager


class AppContext:
    """
    Classe de contexte d'application

    Encapsule toutes les opérations dépendant de la configuration et fournit une interface unifiée.
    Supprime la dépendance au CONFIG global, améliore la testabilité.

    Exemple d'utilisation:
        config = load_config()
        ctx = AppContext(config)

        # Opérations sur le temps
        now = ctx.get_time()
        date_folder = ctx.format_date()

        # Opérations de stockage
        storage = ctx.get_storage_manager()

        # Génération du rapport
        html = ctx.generate_html_report(stats, total_titles, ...)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialise le contexte d'application

        Args:
            config: dictionnaire de configuration complet
        """
        self.config = config
        self._storage_manager = None
        self._scheduler = None

    # === Accès à la configuration ===

    @property
    def timezone(self) -> str:
        """Renvoie le fuseau horaire configuré"""
        return self.config.get("TIMEZONE", DEFAULT_TIMEZONE)

    @property
    def rank_threshold(self) -> int:
        """Renvoie le seuil de classement"""
        return self.config.get("RANK_THRESHOLD", 50)

    @property
    def weight_config(self) -> Dict:
        """Renvoie la configuration des pondérations"""
        return self.config.get("WEIGHT_CONFIG", {})

    @property
    def platforms(self) -> List[Dict]:
        """Renvoie la liste de configuration des plateformes"""
        return self.config.get("PLATFORMS", [])

    @property
    def platform_ids(self) -> List[str]:
        """Renvoie la liste des identifiants de plateformes"""
        return [p["id"] for p in self.platforms]

    @property
    def rss_config(self) -> Dict:
        """Renvoie la configuration RSS"""
        return self.config.get("RSS", {})

    @property
    def rss_enabled(self) -> bool:
        """Indique si les flux RSS sont activés"""
        return self.rss_config.get("ENABLED", False)

    @property
    def rss_feeds(self) -> List[Dict]:
        """Renvoie la liste des sources RSS"""
        return self.rss_config.get("FEEDS", [])

    @property
    def display_mode(self) -> str:
        """Renvoie le mode d'affichage (keyword | platform)"""
        return self.config.get("DISPLAY_MODE", "keyword")

    @property
    def show_new_section(self) -> bool:
        """Indique s'il faut afficher la zone des nouvelles tendances"""
        return self.config.get("DISPLAY", {}).get("REGIONS", {}).get("NEW_ITEMS", True)

    @property
    def region_order(self) -> List[str]:
        """Renvoie l'ordre d'affichage des zones"""
        default_order = ["hotlist", "rss", "new_items", "standalone", "ai_analysis"]
        return self.config.get("DISPLAY", {}).get("REGION_ORDER", default_order)

    @property
    def filter_method(self) -> str:
        """Renvoie la stratégie de filtrage : keyword | ai"""
        return self.config.get("FILTER", {}).get("METHOD", "keyword")

    @property
    def ai_priority_sort_enabled(self) -> bool:
        """Interrupteur de tri des étiquettes en mode IA (découplé du sort_by_position_first du mode keyword)"""
        return self.config.get("FILTER", {}).get("PRIORITY_SORT_ENABLED", False)

    @property
    def ai_filter_config(self) -> Dict:
        """Renvoie la configuration du filtrage IA"""
        return self.config.get("AI_FILTER", {})

    @property
    def ai_filter_enabled(self) -> bool:
        """Indique si le filtrage IA est activé (déterminé d'après filter.method)"""
        return self.filter_method == "ai"

    # === Opérations sur le temps ===

    def get_time(self) -> datetime:
        """Renvoie l'heure courante dans le fuseau horaire configuré"""
        return get_configured_time(self.timezone)

    def format_date(self) -> str:
        """Met en forme le dossier de date (YYYY-MM-DD)"""
        return format_date_folder(timezone=self.timezone)

    def format_time(self) -> str:
        """Met en forme le nom de fichier horaire (HH-MM)"""
        return format_time_filename(self.timezone)

    def get_time_display(self) -> str:
        """Renvoie l'heure d'affichage (HH:MM)"""
        return get_current_time_display(self.timezone)

    @staticmethod
    def convert_time_display(time_str: str) -> str:
        """Convertit HH-MM en HH:MM"""
        return convert_time_for_display(time_str)

    # === Opérations de stockage ===

    def get_storage_manager(self):
        """Renvoie le gestionnaire de stockage (initialisation paresseuse, singleton)"""
        if self._storage_manager is None:
            storage_config = self.config.get("STORAGE", {})
            remote_config = storage_config.get("REMOTE", {})
            local_config = storage_config.get("LOCAL", {})
            pull_config = storage_config.get("PULL", {})

            self._storage_manager = get_storage_manager(
                backend_type=storage_config.get("BACKEND", "auto"),
                data_dir=local_config.get("DATA_DIR", "output"),
                enable_txt=storage_config.get("FORMATS", {}).get("TXT", True),
                enable_html=storage_config.get("FORMATS", {}).get("HTML", True),
                remote_config={
                    "bucket_name": remote_config.get("BUCKET_NAME", ""),
                    "access_key_id": remote_config.get("ACCESS_KEY_ID", ""),
                    "secret_access_key": remote_config.get("SECRET_ACCESS_KEY", ""),
                    "endpoint_url": remote_config.get("ENDPOINT_URL", ""),
                    "region": remote_config.get("REGION", ""),
                },
                local_retention_days=local_config.get("RETENTION_DAYS", 0),
                remote_retention_days=remote_config.get("RETENTION_DAYS", 0),
                pull_enabled=pull_config.get("ENABLED", False),
                pull_days=pull_config.get("DAYS", 7),
                timezone=self.timezone,
            )
        return self._storage_manager

    def get_output_path(self, subfolder: str, filename: str) -> str:
        """Renvoie le chemin de sortie (structure aplatie : output/type/date/nom_de_fichier)"""
        output_dir = Path("output") / subfolder / self.format_date()
        output_dir.mkdir(parents=True, exist_ok=True)
        return str(output_dir / filename)

    # === Traitement des données ===

    def read_today_titles(
        self, platform_ids: Optional[List[str]] = None, quiet: bool = False
    ) -> Tuple[Dict, Dict, Dict]:
        """Lit tous les titres du jour"""
        return read_all_today_titles(self.get_storage_manager(), platform_ids, quiet=quiet)

    def detect_new_titles(
        self, platform_ids: Optional[List[str]] = None, quiet: bool = False
    ) -> Dict:
        """Détecte les nouveaux titres du lot le plus récent"""
        return detect_latest_new_titles(self.get_storage_manager(), platform_ids, quiet=quiet)

    def is_first_crawl(self) -> bool:
        """Détecte s'il s'agit de la première collecte de la journée"""
        return self.get_storage_manager().is_first_crawl_today()

    # === Traitement des mots de fréquence ===

    def load_frequency_words(
        self, frequency_file: Optional[str] = None
    ) -> Tuple[List[Dict], List[str], List[str]]:
        """Charge la configuration des mots de fréquence"""
        return load_frequency_words(frequency_file)

    def matches_word_groups(
        self,
        title: str,
        word_groups: List[Dict],
        filter_words: List[str],
        global_filters: Optional[List[str]] = None,
    ) -> bool:
        """Vérifie si le titre correspond aux règles de groupes de mots"""
        return matches_word_groups(title, word_groups, filter_words, global_filters)

    # === Analyse statistique ===

    def count_frequency(
        self,
        results: Dict,
        word_groups: List[Dict],
        filter_words: List[str],
        id_to_name: Dict,
        title_info: Optional[Dict] = None,
        new_titles: Optional[Dict] = None,
        mode: str = "daily",
        global_filters: Optional[List[str]] = None,
        quiet: bool = False,
    ) -> Tuple[List[Dict], int]:
        """Calcule la fréquence des mots"""
        return count_word_frequency(
            results=results,
            word_groups=word_groups,
            filter_words=filter_words,
            id_to_name=id_to_name,
            title_info=title_info,
            rank_threshold=self.rank_threshold,
            new_titles=new_titles,
            mode=mode,
            global_filters=global_filters,
            weight_config=self.weight_config,
            max_news_per_keyword=self.config.get("MAX_NEWS_PER_KEYWORD", 0),
            sort_by_position_first=self.config.get("SORT_BY_POSITION_FIRST", False),
            is_first_crawl_func=self.is_first_crawl,
            convert_time_func=self.convert_time_display,
            quiet=quiet,
        )

    # === Génération du rapport ===

    def prepare_report(
        self,
        stats: List[Dict],
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        mode: str = "daily",
        frequency_file: Optional[str] = None,
    ) -> Dict:
        """Prépare les données du rapport"""
        return prepare_report_data(
            stats=stats,
            failed_ids=failed_ids,
            new_titles=new_titles,
            id_to_name=id_to_name,
            mode=mode,
            rank_threshold=self.rank_threshold,
            show_new_section=self.show_new_section,
        )

    def generate_html(
        self,
        stats: List[Dict],
        total_titles: int,
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        mode: str = "daily",
        update_info: Optional[Dict] = None,
        rss_items: Optional[List[Dict]] = None,
        rss_new_items: Optional[List[Dict]] = None,
        ai_analysis: Optional[Any] = None,
        standalone_data: Optional[Dict] = None,
        frequency_file: Optional[str] = None,
        report_metadata: Optional[Dict] = None,
    ) -> str:
        """Génère le rapport HTML."""
        return generate_html_report(
            stats=stats,
            total_titles=total_titles,
            failed_ids=failed_ids,
            new_titles=new_titles,
            id_to_name=id_to_name,
            mode=mode,
            update_info=update_info,
            rank_threshold=self.rank_threshold,
            output_dir="output",
            date_folder=self.format_date(),
            time_filename=self.format_time(),
            render_html_func=lambda *args, language="fr", **kwargs: self.render_html(*args, rss_items=rss_items, rss_new_items=rss_new_items, ai_analysis=ai_analysis, standalone_data=standalone_data, language=language, **kwargs),
            report_metadata=report_metadata,
        )

    def render_html(
        self,
        report_data: Dict,
        total_titles: int,
        mode: str = "daily",
        update_info: Optional[Dict] = None,
        rss_items: Optional[List[Dict]] = None,
        rss_new_items: Optional[List[Dict]] = None,
        ai_analysis: Optional[Any] = None,
        standalone_data: Optional[Dict] = None,
        language: str = "fr",
    ) -> str:
        """Rend le contenu HTML."""
        return render_html_content(
            report_data=report_data,
            total_titles=total_titles,
            mode=mode,
            update_info=update_info,
            region_order=self.region_order,
            get_time_func=self.get_time,
            rss_items=rss_items,
            rss_new_items=rss_new_items,
            display_mode=self.display_mode,
            ai_analysis=ai_analysis,
            show_new_section=self.show_new_section,
            standalone_data=standalone_data,
            language=language,
        )

    # === Rendu du contenu de notification ===

    def render_feishu(
        self,
        report_data: Dict,
        update_info: Optional[Dict] = None,
        mode: str = "daily",
    ) -> str:
        """Rend le contenu pour Feishu"""
        return render_feishu_content(
            report_data=report_data,
            update_info=update_info,
            mode=mode,
            separator=self.config.get("FEISHU_MESSAGE_SEPARATOR", "---"),
            region_order=self.region_order,
            get_time_func=self.get_time,
            show_new_section=self.show_new_section,
        )

    def render_dingtalk(
        self,
        report_data: Dict,
        update_info: Optional[Dict] = None,
        mode: str = "daily",
    ) -> str:
        """Rend le contenu pour DingTalk"""
        return render_dingtalk_content(
            report_data=report_data,
            update_info=update_info,
            mode=mode,
            region_order=self.region_order,
            get_time_func=self.get_time,
            show_new_section=self.show_new_section,
        )

    def split_content(
        self,
        report_data: Dict,
        format_type: str,
        update_info: Optional[Dict] = None,
        max_bytes: Optional[int] = None,
        mode: str = "daily",
        rss_items: Optional[list] = None,
        rss_new_items: Optional[list] = None,
        ai_content: Optional[str] = None,
        standalone_data: Optional[Dict] = None,
        ai_stats: Optional[Dict] = None,
        report_type: str = "Rapport d'analyse des tendances",
    ) -> List[str]:
        """Découpe le contenu du message en lots (prend en charge tendances + RSS fusionnés + analyse IA + zone d'affichage autonome)

        Args:
            report_data: données du rapport
            format_type: type de format
            update_info: informations de mise à jour
            max_bytes: nombre maximal d'octets
            mode: mode du rapport
            rss_items: liste des entrées statistiques RSS
            rss_new_items: liste des nouvelles entrées RSS
            ai_content: contenu de l'analyse IA (déjà rendu sous forme de chaîne)
            standalone_data: données de la zone d'affichage autonome
            ai_stats: données statistiques de l'analyse IA
            report_type: type du rapport

        Returns:
            liste des contenus de messages après découpage en lots
        """
        return split_content_into_batches(
            report_data=report_data,
            format_type=format_type,
            update_info=update_info,
            max_bytes=max_bytes,
            mode=mode,
            batch_sizes={
                "dingtalk": self.config.get("DINGTALK_BATCH_SIZE", 20000),
                "feishu": self.config.get("FEISHU_BATCH_SIZE", 29000),
                "default": self.config.get("MESSAGE_BATCH_SIZE", 4000),
            },
            feishu_separator=self.config.get("FEISHU_MESSAGE_SEPARATOR", "---"),
            region_order=self.region_order,
            get_time_func=self.get_time,
            rss_items=rss_items,
            rss_new_items=rss_new_items,
            timezone=self.config.get("TIMEZONE", DEFAULT_TIMEZONE),
            display_mode=self.display_mode,
            ai_content=ai_content,
            standalone_data=standalone_data,
            rank_threshold=self.rank_threshold,
            ai_stats=ai_stats,
            report_type=report_type,
            show_new_section=self.show_new_section,
        )

    # === Envoi des notifications ===

    def create_notification_dispatcher(self) -> NotificationDispatcher:
        """Crée le répartiteur de notifications"""
        # Création du traducteur (si activé)
        translator = None
        trans_config = self.config.get("AI_TRANSLATION", {})
        if trans_config.get("ENABLED", False):
            ai_config = self.config.get("AI", {})
            translator = AITranslator(trans_config, ai_config)

        return NotificationDispatcher(
            config=self.config,
            get_time_func=self.get_time,
            split_content_func=self.split_content,
            translator=translator,
        )

    def create_scheduler(self) -> Scheduler:
        """
        Crée le planificateur (initialisation paresseuse, singleton)

        Construit à partir de la section schedule de config.yaml et de timeline.yaml.
        """
        if self._scheduler is None:
            schedule_config = self.config.get("SCHEDULE", {})
            timeline_data = self.config.get("_TIMELINE_DATA", {})

            self._scheduler = Scheduler(
                schedule_config=schedule_config,
                timeline_data=timeline_data,
                storage_backend=self.get_storage_manager(),
                get_time_func=self.get_time,
                fallback_report_mode=self.config.get("REPORT_MODE", "current"),
            )
        return self._scheduler

    # === Filtrage intelligent par IA ===

    @staticmethod
    def _with_ordered_priorities(tags: List[Dict], start_priority: int = 1) -> List[Dict]:
        """Attribue les priorités selon l'ordre actuel de la liste (plus la valeur est petite, plus la priorité est élevée)"""
        normalized: List[Dict] = []
        priority = start_priority
        for tag_data in tags:
            if not isinstance(tag_data, dict):
                continue
            tag_name = str(tag_data.get("tag", "")).strip()
            if not tag_name:
                continue
            item = dict(tag_data)
            item["tag"] = tag_name
            item["priority"] = priority
            normalized.append(item)
            priority += 1
        return normalized

    def run_ai_filter(self, interests_file: Optional[str] = None) -> Optional[AIFilterResult]:
        """
        Exécute le flux complet du filtrage intelligent par IA

        Args:
            interests_file: nom du fichier de description des centres d'intérêt (situé dans config/custom/ai/) ; None = utilise par défaut config/ai_interests.txt

        1. Lit le fichier de description des centres d'intérêt et calcule son hash
        2. Compare avec le prompt_hash en base de données pour décider s'il faut réextraire les étiquettes
        3. Rassemble les actualités à classer (avec déduplication)
        4. Appelle l'IA pour classer par groupes de batch_size
        5. Enregistre les résultats
        6. Interroge les résultats actifs et les renvoie regroupés par étiquette

        Returns:
            AIFilterResult, ou None (filtrage non activé ou erreur)
        """
        if not self.ai_filter_enabled:
            return None

        filter_config = self.ai_filter_config
        ai_config = self.config.get("AI", {})
        debug = self.config.get("DEBUG", False)

        # Création de l'instance AIFilter
        ai_filter = AIFilter(ai_config, filter_config, self.get_time, debug)

        # Détermination du nom de fichier de centres d'intérêt réellement utilisé
        # None = utilise par défaut config/ai_interests.txt ; un nom de fichier indiqué = config/custom/ai/{name}
        configured_interests = interests_file or filter_config.get("INTERESTS_FILE")
        effective_interests_file = configured_interests or "ai_interests.txt"

        if debug:
            print(f"[Filtrage IA][DEBUG] === Informations de configuration ===")
            print(f"[Filtrage IA][DEBUG] Backend de stockage : {self.get_storage_manager().backend_name}")
            print(f"[Filtrage IA][DEBUG] batch_size={filter_config.get('BATCH_SIZE', 200)}, "
                  f"batch_interval={filter_config.get('BATCH_INTERVAL', 5)}")
            print(f"[Filtrage IA][DEBUG] interests_file={effective_interests_file}")
            print(f"[Filtrage IA][DEBUG] prompt_file={filter_config.get('PROMPT_FILE', 'prompt.txt')}")
            print(f"[Filtrage IA][DEBUG] extract_prompt_file={filter_config.get('EXTRACT_PROMPT_FILE', 'extract_prompt.txt')}")

        # 1. Lecture de la description des centres d'intérêt
        # On transmet configured_interests (qui peut valoir None) à load_interests_content,
        # afin de distinguer le « fichier par défaut (config/ai_interests.txt) » du « fichier personnalisé (config/custom/ai/) »
        interests_content = ai_filter.load_interests_content(configured_interests)
        if not interests_content:
            return AIFilterResult(success=False, error="Le fichier de description des centres d'intérêt est vide ou introuvable")

        current_hash = ai_filter.compute_interests_hash(interests_content, effective_interests_file)
        storage = self.get_storage_manager()

        if debug:
            print(f"[Filtrage IA][DEBUG] Hash de la description des centres d'intérêt : {current_hash}")
            print(f"[Filtrage IA][DEBUG] Contenu de la description des centres d'intérêt ({len(interests_content)} caractères) :\n{interests_content}")

        # 2. Activation du mode par lot (le téléversement vers le backend distant est différé : tout est téléversé en une fois une fois les écritures terminées)
        storage.begin_batch()

        # 3. Vérification d'un éventuel changement du prompt
        stored_hash = storage.get_latest_prompt_hash(interests_file=effective_interests_file)

        if debug:
            print(f"[Filtrage IA][DEBUG] Hash stocké en base de données : {stored_hash}")
            print(f"[Filtrage IA][DEBUG] Comparaison des hash : stored={stored_hash} vs current={current_hash} → {'correspondance' if stored_hash == current_hash else 'pas de correspondance'}")

        if stored_hash != current_hash:
            new_version = storage.get_latest_ai_filter_tag_version() + 1
            threshold = filter_config.get("RECLASSIFY_THRESHOLD", 0.6)

            if stored_hash is None:
                # Première exécution : on extrait et on enregistre directement toutes les étiquettes
                print(f"[Filtrage IA] Première exécution ({effective_interests_file}), extraction des étiquettes...")
                tags_data = ai_filter.extract_tags(interests_content)
                if not tags_data:
                    storage.end_batch()
                    return AIFilterResult(success=False, error="Échec de l'extraction des étiquettes")
                tags_data = self._with_ordered_priorities(tags_data, start_priority=1)
                saved_count = storage.save_ai_filter_tags(tags_data, new_version, current_hash, interests_file=effective_interests_file)
                print(f"[Filtrage IA] {saved_count} étiquette(s) enregistrée(s) (version {new_version})")
            else:
                # La description des centres d'intérêt a changé : on demande à l'IA de comparer les anciennes étiquettes aux nouveaux centres d'intérêt et de proposer un plan de mise à jour
                old_tags = storage.get_active_ai_filter_tags(interests_file=effective_interests_file)
                update_result = ai_filter.update_tags(old_tags, interests_content)

                if update_result is None:
                    # Échec de la mise à jour des étiquettes par l'IA : repli vers une réextraction de toutes les étiquettes
                    print(f"[Filtrage IA] Échec de la mise à jour des étiquettes par l'IA ; repli vers une réextraction")
                    tags_data = ai_filter.extract_tags(interests_content)
                    if not tags_data:
                        storage.end_batch()
                        return AIFilterResult(success=False, error="Échec de l'extraction des étiquettes")
                    tags_data = self._with_ordered_priorities(tags_data, start_priority=1)
                    deprecated_count = storage.deprecate_all_ai_filter_tags(interests_file=effective_interests_file)
                    storage.clear_analyzed_news(interests_file=effective_interests_file)
                    saved_count = storage.save_ai_filter_tags(tags_data, new_version, current_hash, interests_file=effective_interests_file)
                    print(f"[Filtrage IA] {deprecated_count} ancienne(s) étiquette(s) rendue(s) obsolète(s), {saved_count} nouvelle(s) étiquette(s) enregistrée(s) (version {new_version})")
                else:
                    change_ratio = update_result["change_ratio"]
                    keep_tags = update_result["keep"]
                    add_tags = update_result["add"]
                    remove_tags = update_result["remove"]

                    if debug:
                        print(f"[Filtrage IA][DEBUG] Mise à jour des étiquettes par l'IA : keep={len(keep_tags)}, add={len(add_tags)}, remove={len(remove_tags)}, change_ratio={change_ratio:.2f}, threshold={threshold:.2f}")

                    if change_ratio >= threshold:
                        # Reclassification complète : on rend obsolètes toutes les anciennes étiquettes et on réextrait via extract_tags
                        print(f"[Filtrage IA] Le fichier de centres d'intérêt a changé : {effective_interests_file} (IA change_ratio={change_ratio:.2f} >= threshold={threshold:.2f} → reclassification complète)")
                        tags_data = ai_filter.extract_tags(interests_content)
                        if not tags_data:
                            storage.end_batch()
                            return AIFilterResult(success=False, error="Échec de l'extraction des étiquettes")
                        tags_data = self._with_ordered_priorities(tags_data, start_priority=1)
                        deprecated_count = storage.deprecate_all_ai_filter_tags(interests_file=effective_interests_file)
                        storage.clear_analyzed_news(interests_file=effective_interests_file)
                        saved_count = storage.save_ai_filter_tags(tags_data, new_version, current_hash, interests_file=effective_interests_file)
                        print(f"[Filtrage IA] {deprecated_count} ancienne(s) étiquette(s) rendue(s) obsolète(s), {saved_count} nouvelle(s) étiquette(s) enregistrée(s) (version {new_version})")
                    else:
                        # Mise à jour incrémentale : opérations ciblées indiquées par l'IA
                        print(f"[Filtrage IA] Le fichier de centres d'intérêt a changé : {effective_interests_file} (IA change_ratio={change_ratio:.2f} < threshold={threshold:.2f} → mise à jour incrémentale)")
                        print(f"[Filtrage IA]   {len(keep_tags)} étiquette(s) conservée(s), {len(add_tags)} ajoutée(s), {len(remove_tags)} rendue(s) obsolète(s)")

                        # On rend obsolètes les étiquettes que l'IA a marquées comme à retirer
                        if remove_tags:
                            remove_set = set(remove_tags)
                            removed_ids = [t["id"] for t in old_tags if t["tag"] in remove_set]
                            if removed_ids:
                                storage.deprecate_specific_ai_filter_tags(removed_ids)
                                if debug:
                                    print(f"[Filtrage IA][DEBUG] Identifiants des étiquettes rendues obsolètes : {removed_ids}")

                        # Mise à jour des descriptions des étiquettes conservées
                        keep_with_priority = []
                        if keep_tags:
                            storage.update_ai_filter_tag_descriptions(keep_tags, interests_file=effective_interests_file)
                            keep_with_priority = self._with_ordered_priorities(keep_tags, start_priority=1)
                            storage.update_ai_filter_tag_priorities(keep_with_priority, interests_file=effective_interests_file)

                        # Enregistrement des nouvelles étiquettes
                        if add_tags:
                            add_start = keep_with_priority[-1]["priority"] + 1 if keep_with_priority else 1
                            add_with_priority = self._with_ordered_priorities(add_tags, start_priority=add_start)
                            saved_count = storage.save_ai_filter_tags(add_with_priority, new_version, current_hash, interests_file=effective_interests_file)
                            if debug:
                                print(f"[Filtrage IA][DEBUG] {saved_count} nouvelle(s) étiquette(s) enregistrée(s)")

                        # Mise à jour du hash des étiquettes conservées (marquées comme déjà traitées)
                        storage.update_ai_filter_tags_hash(effective_interests_file, current_hash)

                        # Mise à jour incrémentale : on efface les enregistrements d'analyse des actualités non correspondantes, afin qu'elles soient réanalysées sous les nouvelles étiquettes
                        if add_tags:
                            cleared = storage.clear_unmatched_analyzed_news(interests_file=effective_interests_file)
                            if cleared > 0:
                                print(f"[Filtrage IA]   {cleared} enregistrement(s) non correspondant(s) effacé(s) ; ces actualités seront réanalysées sous les nouvelles étiquettes")

        # 3. Récupération des étiquettes actuellement actives
        active_tags = storage.get_active_ai_filter_tags(interests_file=effective_interests_file)
        if debug:
            print(f"[Filtrage IA][DEBUG] Étiquettes actives récupérées depuis la base de données : {len(active_tags)}")
            for t in active_tags:
                print(f"[Filtrage IA][DEBUG]   id={t['id']} tag={t['tag']} priority={t.get('priority', 9999)} version={t.get('version')} hash={t.get('prompt_hash', '')[:8]}...")

        if not active_tags:
            storage.end_batch()
            return AIFilterResult(success=False, error="Aucune étiquette disponible")

        print(f"[Filtrage IA] {len(active_tags)} étiquette(s) utilisée(s)")

        # 4. Rassemblement des actualités à classer
        # Tendances
        all_news = storage.get_all_news_ids()
        analyzed_hotlist = storage.get_analyzed_news_ids("hotlist", interests_file=effective_interests_file)
        pending_news = [n for n in all_news if n["id"] not in analyzed_hotlist]

        # RSS (on applique d'abord le filtrage par fraîcheur, puis on retire les entrées déjà classées)
        pending_rss = []
        freshness_filtered_rss = 0
        if self.rss_enabled:
            all_rss = storage.get_all_rss_ids()

            # Application du filtrage par fraîcheur (cohérent avec l'étape de diffusion)
            rss_config = self.rss_config
            freshness_config = rss_config.get("FRESHNESS_FILTER", {})
            freshness_enabled = freshness_config.get("ENABLED", True)
            default_max_age_days = freshness_config.get("MAX_AGE_DAYS", 3)
            timezone = self.config.get("TIMEZONE", DEFAULT_TIMEZONE)

            # Construction de la correspondance feed_id -> max_age_days
            feed_max_age_map = {}
            for feed_cfg in self.rss_feeds:
                feed_id = feed_cfg.get("id", "")
                max_age = feed_cfg.get("max_age_days")
                if max_age is not None:
                    try:
                        feed_max_age_map[feed_id] = int(max_age)
                    except (ValueError, TypeError):
                        pass

            fresh_rss = []
            for n in all_rss:
                published_at = n.get("published_at", "")
                feed_id = n.get("source_id", "")
                max_days = feed_max_age_map.get(feed_id, default_max_age_days)
                if freshness_enabled and max_days > 0 and published_at:
                    if not is_within_days(published_at, max_days, timezone):
                        freshness_filtered_rss += 1
                        continue
                fresh_rss.append(n)

            analyzed_rss = storage.get_analyzed_news_ids("rss", interests_file=effective_interests_file)
            pending_rss = [n for n in fresh_rss if n["id"] not in analyzed_rss]

        # On affiche les détails : total / déjà analysés / à analyser
        hotlist_total = len(all_news)
        hotlist_skipped = len(analyzed_hotlist)
        hotlist_pending = len(pending_news)
        print(f"[Filtrage IA] Tendances : {hotlist_total} entrées au total, {hotlist_skipped} déjà analysées et ignorées, {hotlist_pending} envoyées à l'analyse IA pour cette exécution")
        if self.rss_enabled:
            rss_total = len(all_rss)
            rss_skipped = len(analyzed_rss)
            rss_pending = len(pending_rss)
            freshness_info = f", {freshness_filtered_rss} filtrées par fraîcheur" if freshness_filtered_rss > 0 else ""
            print(f"[Filtrage IA] RSS : {rss_total} entrées au total{freshness_info}, {rss_skipped} déjà analysées et ignorées, {rss_pending} envoyées à l'analyse IA pour cette exécution")

        total_pending = len(pending_news) + len(pending_rss)
        if total_pending == 0:
            print("[Filtrage IA] Aucune nouvelle actualité à classer")

        # 5. Classification par lot
        batch_size = filter_config.get("BATCH_SIZE", 200)
        batch_interval = filter_config.get("BATCH_INTERVAL", 5)
        total_results = []
        batch_count = 0  # Compteur global de lots, couvrant à la fois les tendances et les flux RSS

        # Traitement des tendances
        for i in range(0, len(pending_news), batch_size):
            if batch_count > 0 and batch_interval > 0:
                import time
                print(f"[Filtrage IA] Attente de {batch_interval} secondes entre les lots...")
                time.sleep(batch_interval)
            batch = pending_news[i:i + batch_size]
            titles_for_ai = [
                {"id": n["id"], "title": n["title"], "source": n.get("source_name", "")}
                for n in batch
            ]
            batch_results = ai_filter.classify_batch(titles_for_ai, active_tags, interests_content)
            for r in batch_results:
                r["source_type"] = "hotlist"
            total_results.extend(batch_results)
            batch_count += 1
            print(f"[Filtrage IA] Lot de tendances {i // batch_size + 1} : {len(batch)} entrées → {len(batch_results)} correspondances")

        # Traitement des flux RSS
        for i in range(0, len(pending_rss), batch_size):
            if batch_count > 0 and batch_interval > 0:
                import time
                print(f"[Filtrage IA] Attente de {batch_interval} secondes entre les lots...")
                time.sleep(batch_interval)
            batch = pending_rss[i:i + batch_size]
            titles_for_ai = [
                {"id": n["id"], "title": n["title"], "source": n.get("source_name", "")}
                for n in batch
            ]
            batch_results = ai_filter.classify_batch(titles_for_ai, active_tags, interests_content)
            for r in batch_results:
                r["source_type"] = "rss"
            total_results.extend(batch_results)
            batch_count += 1
            print(f"[Filtrage IA] Lot RSS {i // batch_size + 1} : {len(batch)} entrées → {len(batch_results)} correspondances")

        # 6. Enregistrement des résultats
        if total_results:
            saved = storage.save_ai_filter_results(total_results)
            print(f"[Filtrage IA] {saved} résultat(s) de classification enregistré(s)")
            if debug and saved != len(total_results):
                print(f"[Filtrage IA][DEBUG] !! Nombre d'enregistrements incohérent : attendu {len(total_results)}, réel {saved} (des doublons ont peut-être été ignorés)")

        # 6.5 Enregistrement de toutes les actualités déjà analysées (correspondantes + non correspondantes, pour la déduplication)
        matched_hotlist_ids = {r["news_item_id"] for r in total_results if r.get("source_type") == "hotlist"}
        matched_rss_ids = {r["news_item_id"] for r in total_results if r.get("source_type") == "rss"}

        if pending_news:
            hotlist_ids = [n["id"] for n in pending_news]
            storage.save_analyzed_news(
                hotlist_ids, "hotlist", effective_interests_file,
                current_hash, matched_hotlist_ids
            )

        if pending_rss:
            rss_ids = [n["id"] for n in pending_rss]
            storage.save_analyzed_news(
                rss_ids, "rss", effective_interests_file,
                current_hash, matched_rss_ids
            )

        if pending_news or pending_rss:
            total_analyzed = len(pending_news) + len(pending_rss)
            total_matched = len(matched_hotlist_ids) + len(matched_rss_ids)
            print(f"[Filtrage IA] État d'analyse enregistré pour {total_analyzed} actualité(s) ({total_matched} correspondante(s), {total_analyzed - total_matched} non correspondante(s))")

        # 7. Fin du mode par lot (téléversement groupé de la base de données vers le stockage distant)
        storage.end_batch()

        # 8. Interrogation, assemblage et renvoi des résultats
        all_results = storage.get_active_ai_filter_results(interests_file=effective_interests_file)

        if debug:
            print(f"[Filtrage IA][DEBUG] === Synthèse finale ===")
            print(f"[Filtrage IA][DEBUG] Résultats de classification actifs en base de données : {len(all_results)} entrées")
            # Statistiques par étiquette
            tag_counts: dict = {}
            for r in all_results:
                tag_name = r.get("tag", "?")
                src_type = r.get("source_type", "?")
                key = f"{tag_name}({src_type})"
                tag_counts[key] = tag_counts.get(key, 0) + 1
            for key, count in sorted(tag_counts.items()):
                print(f"[Filtrage IA][DEBUG]   {key} : {count} entrées")

        return self._build_filter_result(all_results, active_tags, total_pending)

    def _build_filter_result(
        self,
        raw_results: List[Dict],
        tags: List[Dict],
        total_processed: int,
    ) -> AIFilterResult:
        """Assemble les résultats issus de la base de données en un objet AIFilterResult"""
        priority_sort_enabled = self.ai_priority_sort_enabled
        tag_priority_map = {}
        for idx, t in enumerate(tags, start=1):
            tag_name = str(t.get("tag", "")).strip() if isinstance(t, dict) else ""
            if not tag_name:
                continue
            try:
                tag_priority_map[tag_name] = int(t.get("priority", idx))
            except (TypeError, ValueError):
                tag_priority_map[tag_name] = idx

        # Regroupement par étiquette
        tag_groups: Dict[str, Dict] = {}
        seen_titles: Dict[str, set] = {}  # Déduplication au sein de chaque étiquette

        for r in raw_results:
            tag_name = r["tag"]
            if tag_name not in tag_groups:
                raw_priority = r.get("tag_priority", tag_priority_map.get(tag_name, 9999))
                try:
                    tag_position = int(raw_priority)
                except (TypeError, ValueError):
                    tag_position = 9999
                tag_groups[tag_name] = {
                    "tag": tag_name,
                    "description": r.get("tag_description", ""),
                    "position": tag_position,
                    "count": 0,
                    "items": [],
                }
                seen_titles[tag_name] = set()

            title = r["title"]
            if title in seen_titles[tag_name]:
                continue
            seen_titles[tag_name].add(title)

            tag_groups[tag_name]["items"].append({
                "title": title,
                "source_id": r.get("source_id", ""),
                "source_name": r.get("source_name", ""),
                "url": r.get("url", ""),
                "mobile_url": r.get("mobile_url", ""),
                "rank": r.get("rank", 0),
                "ranks": r.get("ranks", []),
                "first_time": r.get("first_time", ""),
                "last_time": r.get("last_time", ""),
                "count": r.get("count", 1),
                "relevance_score": r.get("relevance_score", 0),
                "source_type": r.get("source_type", "hotlist"),
            })
            tag_groups[tag_name]["count"] += 1

        # Tri selon la configuration : priorité par position / priorité par nombre
        if priority_sort_enabled:
            sorted_tags = sorted(
                tag_groups.values(),
                key=lambda x: (x.get("position", 9999), -x["count"], x["tag"]),
            )
        else:
            sorted_tags = sorted(
                tag_groups.values(),
                key=lambda x: (-x["count"], x.get("position", 9999), x["tag"]),
            )

        total_matched = sum(t["count"] for t in sorted_tags)

        return AIFilterResult(
            tags=sorted_tags,
            total_matched=total_matched,
            total_processed=total_processed,
            success=True,
        )

    def convert_ai_filter_to_report_data(
        self,
        ai_filter_result: AIFilterResult,
        mode: str = "daily",
        new_titles: Optional[Dict] = None,
        rss_new_urls: Optional[set] = None,
    ) -> tuple:
        """
        Convertit le résultat du filtrage IA dans la même structure de données que la correspondance par mots-clés

        Dans AIFilterResult.tags, chaque tag correspond à un « word » (groupe de mots-clés).
        Dans tag.items, les entrées avec source_type="hotlist" alimentent les stats des tendances,
        et celles avec source_type="rss" alimentent les stats de rss_items.

        Args:
            ai_filter_result: résultat du filtrage IA
            mode: mode du rapport ("daily" | "current" | "incremental")
            new_titles: nouveaux titres des tendances {source_id: {title: data}}, utilisé pour la détection de is_new
            rss_new_urls: ensemble des URL des nouvelles entrées RSS, utilisé pour la détection de is_new

        Returns:
            (hotlist_stats, rss_stats) :
            - hotlist_stats : format cohérent avec la sortie de count_word_frequency()
            - rss_stats : format cohérent avec rss_items
        """
        hotlist_stats = []
        rss_stats = []
        max_news = self.config.get("MAX_NEWS_PER_KEYWORD", 0)
        min_score = self.ai_filter_config.get("MIN_SCORE", 0)

        # Mode current : on calcule l'heure la plus récente et on ne conserve que les actualités tendances actuellement classées
        # afin de s'aligner sur la logique de filtrage de count_word_frequency(mode="current")
        latest_time = None
        if mode == "current":
            for tag_data in ai_filter_result.tags:
                for item in tag_data.get("items", []):
                    if item.get("source_type", "hotlist") == "hotlist":
                        last_time = item.get("last_time", "")
                        if last_time and (latest_time is None or last_time > latest_time):
                            latest_time = last_time
            if latest_time:
                print(f"[Filtrage IA] Mode current : heure la plus récente {latest_time}, filtrage des actualités déjà déclassées")

        # Configuration du filtrage par fraîcheur des flux RSS (cohérente avec l'étape de diffusion)
        rss_config = self.rss_config
        freshness_config = rss_config.get("FRESHNESS_FILTER", {})
        freshness_enabled = freshness_config.get("ENABLED", True)
        default_max_age_days = freshness_config.get("MAX_AGE_DAYS", 3)
        timezone = self.config.get("TIMEZONE", DEFAULT_TIMEZONE)

        feed_max_age_map = {}
        for feed_cfg in self.rss_feeds:
            feed_id = feed_cfg.get("id", "")
            max_age = feed_cfg.get("max_age_days")
            if max_age is not None:
                try:
                    feed_max_age_map[feed_id] = int(max_age)
                except (ValueError, TypeError):
                    pass

        filtered_count = 0
        for tag_data in ai_filter_result.tags:
            tag_name = tag_data.get("tag", "")
            items = tag_data.get("items", [])
            if not items:
                continue

            hotlist_titles = []
            rss_titles = []

            for item in items:
                source_type = item.get("source_type", "hotlist")

                # Mode current : on ignore les actualités tendances déjà déclassées
                if mode == "current" and latest_time and source_type == "hotlist":
                    if item.get("last_time", "") != latest_time:
                        filtered_count += 1
                        continue

                # Filtrage par seuil de score : on ignore les actualités dont la pertinence est inférieure à min_score
                if min_score > 0:
                    score = item.get("relevance_score", 0)
                    if score < min_score:
                        continue

                # Construction de l'affichage de l'heure
                first_time = item.get("first_time", "")
                last_time = item.get("last_time", "")
                if source_type == "rss":
                    # Filtrage par fraîcheur des flux RSS : on ignore les anciens articles dépassant max_age_days
                    if freshness_enabled and first_time:
                        feed_id = item.get("source_id", "")
                        max_days = feed_max_age_map.get(feed_id, default_max_age_days)
                        if max_days > 0 and not is_within_days(first_time, max_days, timezone):
                            continue

                    # Entrée RSS : first_time est au format ISO ; on l'affiche dans un format lisible
                    if first_time:
                        time_display = format_iso_time_friendly(first_time, timezone, include_date=True)
                    else:
                        time_display = ""
                else:
                    # Entrée de tendance : on utilise le format [HH:MM ~ HH:MM] (cohérent avec le mode keyword)
                    if first_time and last_time and first_time != last_time:
                        first_display = convert_time_for_display(first_time)
                        last_display = convert_time_for_display(last_time)
                        time_display = f"[{first_display} ~ {last_display}]"
                    elif first_time:
                        time_display = convert_time_for_display(first_time)
                    else:
                        time_display = ""

                # Calcul de is_new (aligné sur le mode keyword, core/analyzer.py:335-342)
                if source_type == "rss":
                    is_new = False
                    if rss_new_urls:
                        item_url = item.get("url", "")
                        is_new = item_url in rss_new_urls if item_url else False
                else:
                    is_new = False
                    if new_titles:
                        item_source_id = item.get("source_id", "")
                        item_title = item.get("title", "")
                        if item_source_id in new_titles:
                            is_new = item_title in new_titles[item_source_id]

                # En mode incremental, on ne conserve que les nouvelles entrées correspondantes de ce cycle.
                # run_ai_filter() renvoie l'ensemble des résultats actifs ; il faut donc filtrer ici
                # les anciennes entrées déjà correspondantes de l'historique, afin de rester aligné sur le mode keyword.
                if mode == "incremental" and not is_new:
                    continue

                title_entry = {
                    "title": item.get("title", ""),
                    "source_name": item.get("source_name", ""),
                    "url": item.get("url", ""),
                    "mobile_url": item.get("mobile_url", ""),
                    "ranks": item.get("ranks", []),
                    "rank_threshold": self.rank_threshold,
                    "count": item.get("count", 1),
                    "is_new": is_new,
                    "time_display": time_display,
                    "matched_keyword": tag_name,
                }

                if source_type == "rss":
                    rss_titles.append(title_entry)
                else:
                    hotlist_titles.append(title_entry)

            if hotlist_titles:
                if max_news > 0:
                    hotlist_titles = hotlist_titles[:max_news]
                hotlist_stats.append({
                    "word": tag_name,
                    "count": len(hotlist_titles),
                    "position": tag_data.get("position", 9999),
                    "titles": hotlist_titles,
                })

            if rss_titles:
                if max_news > 0:
                    rss_titles = rss_titles[:max_news]
                rss_stats.append({
                    "word": tag_name,
                    "count": len(rss_titles),
                    "position": tag_data.get("position", 9999),
                    "titles": rss_titles,
                })

        if mode == "current" and filtered_count > 0:
            total_kept = sum(s["count"] for s in hotlist_stats)
            print(f"[Filtrage IA] Mode current : {filtered_count} actualité(s) déjà déclassée(s) filtrée(s), {total_kept} actualité(s) actuellement classée(s) conservée(s)")

        if min_score > 0:
            hotlist_kept = sum(s["count"] for s in hotlist_stats)
            rss_kept = sum(s["count"] for s in rss_stats)
            total_kept = hotlist_kept + rss_kept
            parts = [f"Tendances : {hotlist_kept} entrées"]
            if rss_kept > 0:
                parts.append(f"RSS : {rss_kept} entrées")
            print(f"[Filtrage IA] Filtrage par score : min_score={min_score}, {total_kept} entrée(s) conservée(s) avec un score ≥ {min_score} ({', '.join(parts)})")

        priority_sort_enabled = self.ai_priority_sort_enabled
        if priority_sort_enabled:
            hotlist_stats.sort(key=lambda x: (x.get("position", 9999), -x["count"], x["word"]))
            rss_stats.sort(key=lambda x: (x.get("position", 9999), -x["count"], x["word"]))
        else:
            hotlist_stats.sort(key=lambda x: (-x["count"], x.get("position", 9999), x["word"]))
            rss_stats.sort(key=lambda x: (-x["count"], x.get("position", 9999), x["word"]))

        return hotlist_stats, rss_stats

    # === Nettoyage des ressources ===

    def cleanup(self):
        """Nettoie les ressources"""
        if self._storage_manager:
            self._storage_manager.cleanup_old_data()
            self._storage_manager.cleanup()
            self._storage_manager = None
