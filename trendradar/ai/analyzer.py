# coding=utf-8
"""
Module d'analyse IA

Analyse en profondeur les actualités tendances en appelant un grand modèle de langage.
Basé sur l'interface unifiée de LiteLLM, il prend en charge plus de 100 fournisseurs d'IA.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from trendradar.ai.client import AIClient
from trendradar.ai.prompt_loader import load_prompt_template


@dataclass
class AIAnalysisResult:
    """Résultat de l'analyse IA"""
    # Nouvelle version : 5 sections principales
    core_trends: str = ""                # Tendances majeures et climat de l'opinion
    sentiment_controversy: str = ""      # Orientation de l'opinion publique et controverses
    signals: str = ""                    # Mouvements inhabituels et signaux faibles
    rss_insights: str = ""               # Analyse approfondie des flux RSS
    outlook_strategy: str = ""           # Analyse prospective et recommandations stratégiques
    standalone_summaries: Dict[str, str] = field(default_factory=dict)  # Résumés de la zone d'affichage autonome {identifiant de source: résumé}

    # Métadonnées de base
    raw_response: str = ""               # Réponse brute
    success: bool = False                # Indique si l'analyse a réussi
    skipped: bool = False                # Indique si l'analyse a été ignorée faute de contenu (et non par échec)
    error: str = ""                      # Message d'erreur

    # Statistiques sur le nombre d'actualités
    total_news: int = 0                  # Nombre total d'actualités (tendances + RSS)
    analyzed_news: int = 0               # Nombre d'actualités réellement analysées
    max_news_limit: int = 0              # Valeur configurée du plafond d'analyse
    hotlist_count: int = 0               # Nombre d'actualités tendances (total)
    rss_count: int = 0                   # Nombre d'actualités RSS (total)
    hotlist_analyzed: int = 0            # Nombre d'actualités tendances réellement analysées
    rss_analyzed: int = 0               # Nombre d'actualités RSS réellement analysées
    standalone_analyzed: int = 0        # Nombre d'entrées de la zone d'affichage autonome réellement analysées
    ai_mode: str = ""                    # Mode utilisé pour l'analyse IA (daily/current/incremental)
    include_rss: bool = True             # Indique si l'analyse des flux RSS est activée
    include_standalone: bool = False     # Indique si l'analyse de la zone d'affichage autonome est activée


class AIAnalyzer:
    """Analyseur IA"""

    def __init__(
        self,
        ai_config: Dict[str, Any],
        analysis_config: Dict[str, Any],
        get_time_func: Callable,
        debug: bool = False,
    ):
        """
        Initialise l'analyseur IA

        Args:
            ai_config: configuration du modèle d'IA (format LiteLLM)
            analysis_config: configuration de la fonction d'analyse IA (language, prompt_file, etc.)
            get_time_func: fonction renvoyant l'heure courante
            debug: indique si le mode débogage est activé
        """
        self.ai_config = ai_config
        self.analysis_config = analysis_config
        self.get_time_func = get_time_func
        self.debug = debug

        # Création du client IA (basé sur LiteLLM)
        self.client = AIClient(ai_config)

        # Vérification de la configuration
        valid, error = self.client.validate_config()
        if not valid:
            print(f"[AI] Avertissement de configuration : {error}")

        # Récupération des paramètres de la fonction depuis la configuration d'analyse
        self.max_news = analysis_config.get("MAX_NEWS_FOR_ANALYSIS", 50)
        self.include_rss = analysis_config.get("INCLUDE_RSS", True)
        self.include_rank_timeline = analysis_config.get("INCLUDE_RANK_TIMELINE", False)
        self.include_standalone = analysis_config.get("INCLUDE_STANDALONE", False)
        self.language = analysis_config.get("LANGUAGE", "Chinese")

        # Chargement du modèle de prompt
        self.system_prompt, self.user_prompt_template = load_prompt_template(
            analysis_config.get("PROMPT_FILE", "ai_analysis_prompt.txt"),
            label="AI",
        )

    def analyze(
        self,
        stats: List[Dict],
        rss_stats: Optional[List[Dict]] = None,
        report_mode: str = "daily",
        report_type: str = "Résumé du jour",
        platforms: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        standalone_data: Optional[Dict] = None,
    ) -> AIAnalysisResult:
        """
        Exécute l'analyse IA

        Args:
            stats: données statistiques des tendances
            rss_stats: données statistiques des flux RSS
            report_mode: mode du rapport
            report_type: type du rapport
            platforms: liste des plateformes
            keywords: liste des mots-clés

        Returns:
            AIAnalysisResult: résultat de l'analyse
        """

        # Affichage des informations de configuration pour faciliter le débogage
        model = self.ai_config.get("MODEL", "unknown")
        api_key = self.client.api_key or ""
        api_base = self.ai_config.get("API_BASE", "")
        masked_key = f"{api_key[:5]}******" if len(api_key) >= 5 else "******"
        model_display = model.replace("/", "/\u200b") if model else "unknown"

        print(f"[AI] Modèle : {model_display}")
        print(f"[AI] Clé : {masked_key}")

        if api_base:
            print(f"[AI] Interface : point de terminaison API personnalisé détecté")

        timeout = self.ai_config.get("TIMEOUT", 120)
        max_tokens = self.ai_config.get("MAX_TOKENS", 5000)
        print(f"[AI] Paramètres : timeout={timeout}, max_tokens={max_tokens}")

        if not self.client.api_key:
            return AIAnalysisResult(
                success=False,
                error="Aucune clé d'API IA configurée ; veuillez la définir dans config.yaml ou via la variable d'environnement AI_API_KEY"
            )

        # Préparation du contenu des actualités et récupération des données statistiques
        news_content, rss_content, hotlist_total, rss_total, analyzed_count, hotlist_analyzed, rss_analyzed = self._prepare_news_content(stats, rss_stats)
        total_news = hotlist_total + rss_total

        if not news_content and not rss_content:
            return AIAnalysisResult(
                success=False,
                skipped=True,
                error="Aucun nouveau contenu tendance pour ce cycle ; analyse IA ignorée",
                total_news=total_news,
                hotlist_count=hotlist_total,
                rss_count=rss_total,
                analyzed_news=0,
                max_news_limit=self.max_news
            )

        # Construction du prompt
        current_time = self.get_time_func().strftime("%Y-%m-%d %H:%M:%S")

        # Extraction des mots-clés
        if not keywords:
            keywords = [s.get("word", "") for s in stats if s.get("word")] if stats else []

        # On utilise un remplacement de chaîne sûr, afin d'éviter que d'autres accolades du modèle (comme les exemples JSON) soient interprétées à tort
        user_prompt = self.user_prompt_template
        user_prompt = user_prompt.replace("{report_mode}", report_mode)
        user_prompt = user_prompt.replace("{report_type}", report_type)
        user_prompt = user_prompt.replace("{current_time}", current_time)
        user_prompt = user_prompt.replace("{news_count}", str(hotlist_total))
        user_prompt = user_prompt.replace("{rss_count}", str(rss_total))
        user_prompt = user_prompt.replace("{platforms}", ", ".join(platforms) if platforms else "plusieurs plateformes")
        user_prompt = user_prompt.replace("{keywords}", ", ".join(keywords[:20]) if keywords else "aucun")
        user_prompt = user_prompt.replace("{news_content}", news_content)
        user_prompt = user_prompt.replace("{rss_content}", rss_content)
        user_prompt = user_prompt.replace("{language}", self.language)

        # Construction du contenu de la zone d'affichage autonome
        standalone_content = ""
        standalone_count = 0
        if self.include_standalone and standalone_data:
            standalone_content, standalone_count = self._prepare_standalone_content(standalone_data)
        user_prompt = user_prompt.replace("{standalone_content}", standalone_content)

        if self.debug:
            print("\n" + "=" * 80)
            print("[AI débogage] Prompt complet envoyé à l'IA")
            print("=" * 80)
            if self.system_prompt:
                print("\n--- System Prompt ---")
                print(self.system_prompt)
            print("\n--- User Prompt ---")
            print(user_prompt)
            print("=" * 80 + "\n")

        # Appel de l'API IA (via LiteLLM)
        try:
            response = self._call_ai(user_prompt)
            result = self._parse_response(response)

            # Repli avec nouvelle tentative en cas d'échec d'analyse JSON (une seule tentative)
            if result.error and "Erreur d'analyse JSON" in result.error:
                print(f"[AI] Échec de l'analyse JSON ; tentative de correction par l'IA...")
                retry_result = self._retry_fix_json(response, result.error)
                if retry_result and retry_result.success and not retry_result.error:
                    print("[AI] Correction du JSON réussie")
                    retry_result.raw_response = response
                    result = retry_result
                else:
                    print("[AI] Échec de la correction du JSON ; repli sur le texte brut")

            # Si l'analyse des flux RSS n'est pas activée dans la configuration, on vide de force les insights RSS renvoyés par l'IA
            if not self.include_rss:
                result.rss_insights = ""

            # Si l'analyse de la zone autonome n'est pas activée dans la configuration, on vide de force le résultat
            if not self.include_standalone:
                result.standalone_summaries = {}

            # Remplissage des données statistiques
            result.total_news = total_news
            result.hotlist_count = hotlist_total
            result.rss_count = rss_total
            result.analyzed_news = analyzed_count
            result.hotlist_analyzed = hotlist_analyzed
            result.rss_analyzed = rss_analyzed
            result.standalone_analyzed = standalone_count
            result.max_news_limit = self.max_news
            result.include_rss = self.include_rss
            result.include_standalone = self.include_standalone
            return result
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            # On tronque les messages d'erreur trop longs
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            friendly_msg = f"Échec de l'analyse IA ({error_type}) : {error_msg}"

            return AIAnalysisResult(
                success=False,
                error=friendly_msg
            )

    def _prepare_news_content(
        self,
        stats: List[Dict],
        rss_stats: Optional[List[Dict]] = None,
    ) -> tuple:
        """
        Prépare le texte du contenu des actualités (version enrichie)

        Une actualité tendance contient : source, titre, plage de classement, plage horaire, nombre d'occurrences
        Un flux RSS contient : source, titre, date de publication

        Returns:
            tuple: (news_content, rss_content, hotlist_total, rss_total, analyzed_count, hotlist_analyzed, rss_analyzed)
        """
        news_lines = []
        rss_lines = []
        news_count = 0
        rss_count = 0

        # Calcul du nombre total d'actualités
        hotlist_total = sum(len(s.get("titles", [])) for s in stats) if stats else 0
        rss_total = sum(len(s.get("titles", [])) for s in rss_stats) if rss_stats else 0

        # Contenu des tendances
        if stats:
            for stat in stats:
                word = stat.get("word", "")
                titles = stat.get("titles", [])
                if word and titles:
                    news_lines.append(f"\n**{word}** ({len(titles)} entrées)")
                    for t in titles:
                        if not isinstance(t, dict):
                            continue
                        title = t.get("title", "")
                        if not title:
                            continue

                        # Source
                        source = t.get("source_name", t.get("source", ""))

                        # Construction de la ligne
                        if source:
                            line = f"- [{source}] {title}"
                        else:
                            line = f"- {title}"

                        # Affichage systématique du format simplifié : plage de classement + plage horaire + nombre d'occurrences
                        ranks = t.get("ranks", [])
                        if ranks:
                            min_rank = min(ranks)
                            max_rank = max(ranks)
                            rank_str = f"{min_rank}" if min_rank == max_rank else f"{min_rank}-{max_rank}"
                        else:
                            rank_str = "-"

                        first_time = t.get("first_time", "")
                        last_time = t.get("last_time", "")
                        time_str = self._format_time_range(first_time, last_time)

                        appear_count = t.get("count", 1)

                        line += f" | classement : {rank_str} | heure : {time_str} | occurrences : {appear_count}"

                        # Lorsque la chronologie complète est activée, on ajoute la trajectoire
                        if self.include_rank_timeline:
                            rank_timeline = t.get("rank_timeline", [])
                            timeline_str = self._format_rank_timeline(rank_timeline)
                            line += f" | trajectoire : {timeline_str}"

                        news_lines.append(line)

                        news_count += 1
                        if news_count >= self.max_news:
                            break
                if news_count >= self.max_news:
                    break

        # Contenu RSS (construit uniquement si l'option est activée)
        if self.include_rss and rss_stats:
            remaining = self.max_news - news_count
            for stat in rss_stats:
                if rss_count >= remaining:
                    break
                word = stat.get("word", "")
                titles = stat.get("titles", [])
                if word and titles:
                    rss_lines.append(f"\n**{word}** ({len(titles)} entrées)")
                    for t in titles:
                        if not isinstance(t, dict):
                            continue
                        title = t.get("title", "")
                        if not title:
                            continue

                        # Source
                        source = t.get("source_name", t.get("feed_name", ""))

                        # Date de publication
                        time_display = t.get("time_display", "")

                        # Construction de la ligne : [source] titre | date de publication
                        if source:
                            line = f"- [{source}] {title}"
                        else:
                            line = f"- {title}"
                        if time_display:
                            line += f" | {time_display}"
                        rss_lines.append(line)

                        rss_count += 1
                        if rss_count >= remaining:
                            break

        news_content = "\n".join(news_lines) if news_lines else ""
        rss_content = "\n".join(rss_lines) if rss_lines else ""
        total_count = news_count + rss_count

        return news_content, rss_content, hotlist_total, rss_total, total_count, news_count, rss_count

    def _call_ai(self, user_prompt: str) -> str:
        """Appelle l'API IA (via LiteLLM)"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        return self.client.chat(messages)

    def _retry_fix_json(self, original_response: str, error_msg: str) -> Optional[AIAnalysisResult]:
        """
        En cas d'échec d'analyse JSON, demande à l'IA de corriger le JSON (une seule tentative)

        Utilise un prompt allégé qui ne reprend pas le system prompt de l'analyse initiale, afin d'économiser des tokens.

        Args:
            original_response: réponse brute de l'IA (JSON au format incorrect)
            error_msg: message d'erreur de l'analyse JSON

        Returns:
            le résultat d'analyse après correction, ou None en cas d'échec
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "Tu es un assistant de correction de JSON. L'utilisateur va te fournir un JSON au format incorrect ainsi qu'un message d'erreur ; "
                    "tu dois corriger les erreurs de format du JSON et renvoyer un JSON valide.\n"
                    "Problèmes courants : guillemets doubles non échappés à l'intérieur d'une valeur de chaîne, virgules manquantes, chaînes mal fermées, etc.\n"
                    "Renvoie uniquement du JSON brut, sans marqueur de bloc de code markdown (comme ```json) ni aucun texte explicatif."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"L'analyse du JSON suivant a échoué :\n\n"
                    f"Erreur : {error_msg}\n\n"
                    f"Contenu original :\n{original_response}\n\n"
                    f"Corrige les problèmes de format du JSON ci-dessus (par exemple en remplaçant les guillemets doubles présents dans une valeur par les guillemets 「」 ou en les échappant avec \\\", "
                    f"en ajoutant les virgules manquantes, en complétant les chaînes incomplètes, etc.), en préservant le sens du contenu d'origine et en ne corrigeant que le format. "
                    f"Renvoie directement le JSON brut corrigé."
                ),
            },
        ]

        try:
            response = self.client.chat(messages)
            return self._parse_response(response)
        except Exception as e:
            print(f"[AI] Exception lors de la nouvelle tentative de correction du JSON : {type(e).__name__}: {e}")
            return None

    def _format_time_range(self, first_time: str, last_time: str) -> str:
        """Met en forme une plage horaire (affichage simplifié, on ne conserve que les heures et minutes)"""
        def extract_time(time_str: str) -> str:
            if not time_str:
                return "-"
            # On tente d'extraire la partie HH:MM
            if " " in time_str:
                parts = time_str.split(" ")
                if len(parts) >= 2:
                    time_part = parts[1]
                    if ":" in time_part:
                        return time_part[:5]  # HH:MM
            elif ":" in time_str:
                return time_str[:5]
            # Traitement du format HH-MM
            result = time_str[:5] if len(time_str) >= 5 else time_str
            if len(result) == 5 and result[2] == '-':
                result = result.replace('-', ':')
            return result

        first = extract_time(first_time)
        last = extract_time(last_time)

        if first == last or last == "-":
            return first
        return f"{first}~{last}"

    def _format_rank_timeline(self, rank_timeline: List[Dict]) -> str:
        """Met en forme la chronologie des classements"""
        if not rank_timeline:
            return "-"

        parts = []
        for item in rank_timeline:
            time_str = item.get("time", "")
            if len(time_str) == 5 and time_str[2] == '-':
                time_str = time_str.replace('-', ':')
            rank = item.get("rank")
            if rank is None:
                parts.append(f"0({time_str})")
            else:
                parts.append(f"{rank}({time_str})")

        return "→".join(parts)

    def _prepare_standalone_content(self, standalone_data: Dict) -> tuple:
        """
        Convertit les données de la zone d'affichage autonome en texte, pour injection dans le prompt d'analyse IA

        Args:
            standalone_data: données de la zone d'affichage autonome {"platforms": [...], "rss_feeds": [...]}

        Returns:
            tuple: (contenu textuel mis en forme, nombre d'entrées de la zone d'affichage autonome)
        """
        lines = []

        # Plateformes de tendances
        for platform in standalone_data.get("platforms", []):
            platform_id = platform.get("id", "")
            platform_name = platform.get("name", platform_id)
            items = platform.get("items", [])
            if not items:
                continue

            lines.append(f"### [{platform_name}]")
            for item in items:
                title = item.get("title", "")
                if not title:
                    continue

                line = f"- {title}"

                # Informations de classement
                ranks = item.get("ranks", [])
                if ranks:
                    min_rank = min(ranks)
                    max_rank = max(ranks)
                    rank_str = f"{min_rank}" if min_rank == max_rank else f"{min_rank}-{max_rank}"
                    line += f" | classement : {rank_str}"

                # Plage horaire
                first_time = item.get("first_time", "")
                last_time = item.get("last_time", "")
                if first_time:
                    time_str = self._format_time_range(first_time, last_time)
                    line += f" | heure : {time_str}"

                # Nombre d'occurrences
                count = item.get("count", 1)
                if count > 1:
                    line += f" | occurrences : {count}"

                # Trajectoire de classement (si activée)
                if self.include_rank_timeline:
                    rank_timeline = item.get("rank_timeline", [])
                    if rank_timeline:
                        timeline_str = self._format_rank_timeline(rank_timeline)
                        line += f" | trajectoire : {timeline_str}"

                lines.append(line)
            lines.append("")

        # Sources RSS
        for feed in standalone_data.get("rss_feeds", []):
            feed_id = feed.get("id", "")
            feed_name = feed.get("name", feed_id)
            items = feed.get("items", [])
            if not items:
                continue

            lines.append(f"### [{feed_name}]")
            for item in items:
                title = item.get("title", "")
                if not title:
                    continue

                line = f"- {title}"
                published_at = item.get("published_at", "")
                if published_at:
                    line += f" | {published_at}"

                lines.append(line)
            lines.append("")

        standalone_count = sum(
            len(p.get("items", [])) for p in standalone_data.get("platforms", [])
        ) + sum(
            len(f.get("items", [])) for f in standalone_data.get("rss_feeds", [])
        )
        return "\n".join(lines), standalone_count

    def _parse_response(self, response: str) -> AIAnalysisResult:
        """Analyse la réponse de l'IA"""
        result = AIAnalysisResult(raw_response=response)

        if not response or not response.strip():
            result.error = "L'IA a renvoyé une réponse vide"
            return result

        # Extraction du texte JSON (en retirant les marqueurs de bloc de code markdown)
        json_str = response

        if "```json" in response:
            parts = response.split("```json", 1)
            if len(parts) > 1:
                code_block = parts[1]
                end_idx = code_block.find("```")
                if end_idx != -1:
                    json_str = code_block[:end_idx]
                else:
                    json_str = code_block
        elif "```" in response:
            parts = response.split("```", 2)
            if len(parts) >= 2:
                json_str = parts[1]

        json_str = json_str.strip()
        if not json_str:
            result.error = "Le contenu JSON extrait est vide"
            result.core_trends = response[:500] + "..." if len(response) > 500 else response
            result.success = True
            return result

        # Première étape : analyse JSON standard
        data = None
        parse_error = None

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            parse_error = e

        # Deuxième étape : correction locale via json_repair
        if data is None:
            try:
                from json_repair import repair_json
                repaired = repair_json(json_str, return_objects=True)
                if isinstance(repaired, dict):
                    data = repaired
                    print("[AI] Correction locale du JSON réussie (json_repair)")
            except Exception:
                pass

        # Si les deux étapes échouent, on enregistre l'erreur (traitée ensuite par le mécanisme de nouvelle tentative de la méthode analyze)
        if data is None:
            if parse_error:
                error_context = json_str[max(0, parse_error.pos - 30):parse_error.pos + 30] if json_str and parse_error.pos else ""
                result.error = f"Erreur d'analyse JSON (position {parse_error.pos}) : {parse_error.msg}"
                if error_context:
                    result.error += f", contexte : ...{error_context}..."
            else:
                result.error = "Échec de l'analyse JSON"
            # Repli : on réutilise le json_str déjà extrait (sans les marqueurs markdown), afin d'éviter l'apparition de ```json dans la diffusion
            result.core_trends = json_str[:500] + "..." if len(json_str) > 500 else json_str
            result.success = True
            return result

        # Analyse réussie : extraction des champs
        try:
            result.core_trends = data.get("core_trends", "")
            result.sentiment_controversy = data.get("sentiment_controversy", "")
            result.signals = data.get("signals", "")
            result.rss_insights = data.get("rss_insights", "")
            result.outlook_strategy = data.get("outlook_strategy", "")

            # Extraction des résumés de la zone d'affichage autonome
            summaries = data.get("standalone_summaries", {})
            if isinstance(summaries, dict):
                result.standalone_summaries = {
                    str(k): str(v) for k, v in summaries.items()
                }

            result.success = True
        except (KeyError, TypeError, AttributeError) as e:
            result.error = f"Erreur d'extraction des champs : {type(e).__name__}: {e}"
            result.core_trends = json_str[:500] + "..." if len(json_str) > 500 else json_str
            result.success = True

        return result
