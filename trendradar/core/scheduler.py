# coding=utf-8
"""
Planificateur de timeline

Système de planification unifié par timeline, qui remplace la logique dispersée
de push_window / analysis_window.
Met en œuvre une planification souple par plages horaires, fondée sur le modèle
periods + day_plans + week_map.
"""

import copy
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from datetime import datetime


@dataclass
class ResolvedSchedule:
    """Résultat de planification après analyse de l'heure actuelle"""
    period_key: Optional[str]       # period key correspondante, None=configuration par défaut
    period_name: Optional[str]      # nom d'affichage correspondant
    day_plan: str                   # plan du jour actuel
    collect: bool
    analyze: bool
    push: bool
    report_mode: str
    ai_mode: str
    once_analyze: bool
    once_push: bool
    frequency_file: Optional[str] = None  # chemin du fichier de mots-clés, None=valeur par défaut
    filter_method: Optional[str] = None   # stratégie de filtrage : "keyword"|"ai", None=configuration globale
    interests_file: Optional[str] = None  # fichier de centres d'intérêt pour le filtrage IA, None=valeur par défaut


class Scheduler:
    """
    Planificateur de timeline

    Détermine, d'après la configuration timeline (periods + day_plans + week_map),
    les actions à exécuter à l'heure actuelle.
    Prend en charge :
    - les modèles prédéfinis + le mode personnalisé
    - les plages horaires à cheval sur deux jours (par exemple 22:00-07:00)
    - une configuration différenciée par jour / par semaine
    - la déduplication des exécutions « once » (analyze / push de façon indépendante)
    - les stratégies de conflit (error_on_overlap / last_wins)
    """

    def __init__(
        self,
        schedule_config: Dict[str, Any],
        timeline_data: Dict[str, Any],
        storage_backend: Any,
        get_time_func: Callable[[], datetime],
        fallback_report_mode: str = "current",
    ):
        """
        Initialise le planificateur.

        Args:
            schedule_config: section schedule de config.yaml (contenant preset, etc.)
            timeline_data: données complètes de timeline.yaml
            storage_backend: backend de stockage (sert à l'enregistrement de déduplication « once »)
            get_time_func: fonction qui récupère l'heure actuelle (doit utiliser le fuseau horaire configuré)
            fallback_report_mode: report_mode de repli utilisé lorsque la planification n'est pas activée (provient de report.mode dans config.yaml)
        """
        self.schedule_config = schedule_config
        self.storage = storage_backend
        self.get_time = get_time_func
        self.enabled = schedule_config.get("enabled", True)
        self.fallback_report_mode = fallback_report_mode

        # On charge et construit la timeline finale
        self.timeline = self._build_timeline(schedule_config, timeline_data)
        if self.enabled:
            self._validate_timeline(self.timeline)

    def _build_timeline(
        self,
        schedule_config: Dict[str, Any],
        timeline_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construit la timeline à partir de preset ou de custom"""
        preset = schedule_config.get("preset", "always_on")

        if preset == "custom":
            timeline = copy.deepcopy(timeline_data.get("custom", {}))
        else:
            presets = timeline_data.get("presets", {})
            if preset not in presets:
                raise ValueError(
                    f"Modèle prédéfini inconnu : '{preset}', valeurs possibles : "
                    f"{', '.join(presets.keys())}, custom"
                )
            timeline = copy.deepcopy(presets[preset])

        # On s'assure que periods est un dict (éventuellement vide {})
        if timeline.get("periods") is None:
            timeline["periods"] = {}

        return timeline

    def resolve(self) -> ResolvedSchedule:
        """
        Analyse la configuration de planification correspondant à l'heure actuelle.

        Returns:
            ResolvedSchedule contenant les actions à exécuter actuellement
        """
        if not self.enabled:
            # Quand la planification n'est pas activée, on retourne la configuration complète par défaut ; report_mode bascule sur report.mode de config.yaml
            return ResolvedSchedule(
                period_key=None,
                period_name=None,
                day_plan="disabled",
                collect=True,
                analyze=True,
                push=True,
                report_mode=self.fallback_report_mode,
                ai_mode="follow_report",
                once_analyze=False,
                once_push=False,
            )

        now = self.get_time()
        weekday = now.isoweekday()  # 1=lundi ... 7=dimanche
        now_hhmm = now.strftime("%H:%M")

        # On recherche le plan du jour
        day_plan_key = self.timeline["week_map"].get(weekday)
        if day_plan_key is None:
            raise ValueError(f"week_map : correspondance manquante pour le jour de la semaine : {weekday}")

        day_plan = self.timeline["day_plans"].get(day_plan_key)
        if day_plan is None:
            raise ValueError(f"week_map[{weekday}] référence un day_plan inexistant : {day_plan_key}")

        # On recherche la plage horaire actuellement active
        period_key = self._find_active_period(now_hhmm, day_plan)

        # On fusionne la configuration par défaut et celle de la plage horaire
        merged = self._merge_with_default(period_key)

        # On affiche le journal de planification
        weekday_names = {1: "lundi", 2: "mardi", 3: "mercredi", 4: "jeudi", 5: "vendredi", 6: "samedi", 7: "dimanche"}
        period_display = "configuration par défaut (aucune plage horaire ne correspond)"
        if period_key:
            period_cfg = self.timeline["periods"][period_key]
            period_name = period_cfg.get("name", period_key)
            start = period_cfg.get("start", "?")
            end = period_cfg.get("end", "?")
            period_display = f"{period_name} ({start}-{end})"

        print(f"[planification] {weekday_names.get(weekday, '?')}, plan du jour : {day_plan_key}")
        print(f"[planification] Plage horaire actuelle : {period_display}")

        resolved = ResolvedSchedule(
            period_key=period_key,
            period_name=(
                self.timeline["periods"][period_key].get("name")
                if period_key
                else None
            ),
            day_plan=day_plan_key,
            collect=merged.get("collect", True),
            analyze=merged.get("analyze", False),
            push=merged.get("push", False),
            report_mode=merged.get("report_mode", "current"),
            ai_mode=self._resolve_ai_mode(merged),
            once_analyze=merged.get("once", {}).get("analyze", False),
            once_push=merged.get("once", {}).get("push", False),
            frequency_file=merged.get("frequency_file"),
            filter_method=merged.get("filter_method"),
            interests_file=merged.get("interests_file"),
        )

        # On affiche le résumé des actions
        actions = []
        if resolved.collect:
            actions.append("collecte")
        if resolved.analyze:
            actions.append(f"analyse(IA:{resolved.ai_mode})")
        if resolved.push:
            actions.append(f"envoi(mode:{resolved.report_mode})")
        print(f"[planification] Actions : {', '.join(actions) if actions else 'aucune'}")
        if resolved.frequency_file:
            print(f"[planification] Fichier de mots-clés : {resolved.frequency_file}")

        return resolved

    def _find_active_period(
        self, now_hhmm: str, day_plan: Dict[str, Any]
    ) -> Optional[str]:
        """
        Recherche la plage horaire active correspondant à l'heure actuelle.

        Args:
            now_hhmm: heure actuelle au format HH:MM
            day_plan: configuration du plan du jour

        Returns:
            la period key correspondante, ou None
        """
        candidates = []
        for idx, key in enumerate(day_plan.get("periods", [])):
            period = self.timeline["periods"].get(key)
            if period is None:
                continue
            if self._in_range(now_hhmm, period["start"], period["end"]):
                candidates.append((idx, key))

        if not candidates:
            return None

        # On vérifie les conflits
        if len(candidates) > 1:
            policy = self.timeline.get("overlap", {}).get("policy", "error_on_overlap")
            conflicting = [c[1] for c in candidates]

            if policy == "error_on_overlap":
                raise ValueError(
                    f"Conflit de chevauchement de plages horaires détecté : {', '.join(conflicting)} se chevauchent à {now_hhmm}. "
                    f"Veuillez ajuster la configuration des plages horaires, ou définir overlap.policy sur 'last_wins'"
                )

            # last_wins : on émet un avertissement de chevauchement, la dernière de la liste l'emporte
            print(
                f"[planification] Chevauchement de plages horaires détecté : {', '.join(conflicting)} se chevauchent à {now_hhmm}"
            )
            winner = candidates[-1]
            print(f"[planification] Stratégie de conflit : last_wins, plage horaire retenue : {winner[1]}")
            return winner[1]

        return candidates[0][1]

    @staticmethod
    def _in_range(now_hhmm: str, start: str, end: str) -> bool:
        """
        Vérifie si l'heure est dans la plage (prend en charge le passage d'un jour à l'autre).

        Args:
            now_hhmm: heure actuelle au format HH:MM
            start: heure de début HH:MM
            end: heure de fin HH:MM

        Returns:
            si l'heure est dans la plage
        """
        if start <= end:
            # Plage normale, par exemple 08:00-09:00 (intervalle semi-ouvert [start, end))
            return start <= now_hhmm < end
        else:
            # Plage à cheval sur deux jours, par exemple 22:00-07:00 (intervalle semi-ouvert [start, end))
            return now_hhmm >= start or now_hhmm < end

    def _merge_with_default(self, period_key: Optional[str]) -> Dict[str, Any]:
        """Fusionne la configuration par défaut et celle de la plage horaire"""
        base = copy.deepcopy(self.timeline.get("default", {}))
        if not period_key:
            return base

        period = copy.deepcopy(self.timeline["periods"][period_key])

        # On fusionne d'abord le sous-objet once
        merged_once = dict(base.get("once", {}))
        merged_once.update(period.get("once", {}))

        # Les champs scalaires sont écrasés
        base.update(period)

        # On restaure le once fusionné
        if merged_once:
            base["once"] = merged_once

        return base

    @staticmethod
    def _resolve_ai_mode(cfg: Dict[str, Any]) -> str:
        """Détermine le mode IA final"""
        ai_mode = cfg.get("ai_mode", "follow_report")
        if ai_mode == "follow_report":
            return cfg.get("report_mode", "current")
        return ai_mode

    def already_executed(self, period_key: str, action: str, date_str: str) -> bool:
        """
        Vérifie si une action donnée d'une plage horaire a déjà été exécutée aujourd'hui.

        Args:
            period_key: key de la plage horaire
            action: type d'action (analyze / push)
            date_str: date au format YYYY-MM-DD

        Returns:
            si l'action a déjà été exécutée
        """
        return self.storage.has_period_executed(date_str, period_key, action)

    def record_execution(self, period_key: str, action: str, date_str: str) -> None:
        """
        Enregistre l'exécution d'une action d'une plage horaire.

        Args:
            period_key: key de la plage horaire
            action: type d'action (analyze / push)
            date_str: date au format YYYY-MM-DD
        """
        self.storage.record_period_execution(date_str, period_key, action)

    # ========================================
    # Validation
    # ========================================

    def _validate_timeline(self, timeline: Dict[str, Any]) -> None:
        """
        Valide la configuration timeline au démarrage.

        Raises:
            ValueError: levée lorsque la configuration est invalide
        """
        required_top_keys = ["default", "periods", "day_plans", "week_map"]
        for key in required_top_keys:
            if key not in timeline:
                raise ValueError(f"timeline : champ obligatoire manquant : {key}")

        # week_map doit couvrir 1..7
        for day in range(1, 8):
            if day not in timeline["week_map"]:
                raise ValueError(f"week_map : correspondance manquante pour le jour de la semaine : {day}")

        # Intégrité des références day_plan
        for day, plan_key in timeline["week_map"].items():
            if plan_key not in timeline["day_plans"]:
                raise ValueError(
                    f"week_map[{day}] référence un day_plan inexistant : {plan_key}"
                )

        # Intégrité des références period
        for plan_key, plan in timeline["day_plans"].items():
            for period_key in plan.get("periods", []):
                if period_key not in timeline["periods"]:
                    raise ValueError(
                        f"day_plan[{plan_key}] référence un period inexistant : {period_key}"
                    )

        # Validation du format des heures
        for period_key, period in timeline["periods"].items():
            if "start" not in period or "end" not in period:
                raise ValueError(
                    f"period '{period_key}' : champ start ou end manquant"
                )
            self._validate_hhmm(period["start"], f"{period_key}.start")
            self._validate_hhmm(period["end"], f"{period_key}.end")
            if period["start"] == period["end"]:
                raise ValueError(
                    f"period '{period_key}' : start et end ne peuvent pas être identiques : {period['start']}"
                )

        # On vérifie les chevauchements sous la stratégie de conflit
        policy = timeline.get("overlap", {}).get("policy", "error_on_overlap")
        if policy == "error_on_overlap":
            self._check_period_overlaps(timeline)

    def _check_period_overlaps(self, timeline: Dict[str, Any]) -> None:
        """
        Vérifie si les plages horaires de chaque plan du jour se chevauchent.

        Appelée uniquement lorsque overlap.policy == "error_on_overlap"
        """
        periods = timeline.get("periods", {})

        for plan_key, plan in timeline["day_plans"].items():
            period_keys = plan.get("periods", [])
            if len(period_keys) <= 1:
                continue

            # On rassemble la plage de chaque période
            ranges = []
            for pk in period_keys:
                p = periods.get(pk, {})
                if "start" in p and "end" in p:
                    ranges.append((pk, p["start"], p["end"]))

            # On vérifie les chevauchements deux à deux
            for i in range(len(ranges)):
                for j in range(i + 1, len(ranges)):
                    if self._ranges_overlap(
                        ranges[i][1], ranges[i][2],
                        ranges[j][1], ranges[j][2],
                    ):
                        raise ValueError(
                            f"day_plan '{plan_key}' : les plages horaires '{ranges[i][0]}' "
                            f"({ranges[i][1]}-{ranges[i][2]}) et '{ranges[j][0]}' "
                            f"({ranges[j][1]}-{ranges[j][2]}) se chevauchent. "
                            f"Veuillez ajuster les plages horaires, ou définir overlap.policy sur 'last_wins'"
                        )

    @staticmethod
    def _ranges_overlap(s1: str, e1: str, s2: str, e2: str) -> bool:
        """Vérifie si deux plages horaires se chevauchent (prend en charge le passage d'un jour à l'autre)"""
        def to_minutes(t: str) -> int:
            h, m = t.split(":")
            return int(h) * 60 + int(m)

        def expand_range(start: str, end: str) -> List[tuple]:
            """Développe une plage horaire en liste de segments en minutes ; en cas de passage d'un jour à l'autre, la découpe en deux segments"""
            s = to_minutes(start)
            e = to_minutes(end)
            if s <= e:
                return [(s, e)]
            else:
                # Passage d'un jour à l'autre : découpe en [start, 24:00) et [00:00, end)
                return [(s, 24 * 60), (0, e)]

        segs1 = expand_range(s1, e1)
        segs2 = expand_range(s2, e2)

        for a_start, a_end in segs1:
            for b_start, b_end in segs2:
                # Condition de chevauchement de deux intervalles semi-ouverts
                if a_start < b_end and b_start < a_end:
                    return True
        return False

    @staticmethod
    def _validate_hhmm(value: str, field_name: str) -> None:
        """Valide le format HH:MM"""
        if not re.match(r"^\d{2}:\d{2}$", value):
            raise ValueError(f"{field_name} : format incorrect : '{value}', format attendu HH:MM")
        h, m = value.split(":")
        if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            raise ValueError(f"{field_name} : valeur horaire hors plage : '{value}'")
