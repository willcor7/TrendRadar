"""
Outils d'analyse de dates

Prend en charge l'analyse de plusieurs formats de date en langage naturel, y compris les dates relatives et absolues.
"""

import re
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional

from .errors import InvalidParameterError


class DateParser:
    """Classe de l'analyseur de dates"""

    # Correspondance des dates en français
    FR_DATE_MAPPING = {
        "aujourd'hui": 0,
        "hier": 1,
        "avant-hier": 2,
    }

    # Correspondance des dates en anglais
    EN_DATE_MAPPING = {
        "today": 0,
        "yesterday": 1,
    }

    # Expressions de plage de dates (utilisées par resolve_date_range_expression)
    RANGE_EXPRESSIONS = {
        # Expressions en français
        "aujourd'hui": "today",
        "hier": "yesterday",
        "cette semaine": "this_week",
        "semaine courante": "this_week",
        "semaine en cours": "this_week",
        "la semaine dernière": "last_week",
        "semaine dernière": "last_week",
        "ce mois": "this_month",
        "ce mois-ci": "this_month",
        "mois courant": "this_month",
        "mois en cours": "this_month",
        "le mois dernier": "last_month",
        "mois dernier": "last_month",
        "3 derniers jours": "last_3_days",
        "les 3 derniers jours": "last_3_days",
        "7 derniers jours": "last_7_days",
        "les 7 derniers jours": "last_7_days",
        "la dernière semaine": "last_7_days",
        "14 derniers jours": "last_14_days",
        "les 14 derniers jours": "last_14_days",
        "les deux dernières semaines": "last_14_days",
        "30 derniers jours": "last_30_days",
        "les 30 derniers jours": "last_30_days",
        "le dernier mois": "last_30_days",
        # Expressions en anglais
        "today": "today",
        "yesterday": "yesterday",
        "this week": "this_week",
        "current week": "this_week",
        "last week": "last_week",
        "this month": "this_month",
        "current month": "this_month",
        "last month": "last_month",
        "last 3 days": "last_3_days",
        "past 3 days": "last_3_days",
        "last 7 days": "last_7_days",
        "past 7 days": "last_7_days",
        "past week": "last_7_days",
        "last 14 days": "last_14_days",
        "past 14 days": "last_14_days",
        "last 30 days": "last_30_days",
        "past 30 days": "last_30_days",
        "past month": "last_30_days",
    }

    # Correspondance des jours de la semaine
    WEEKDAY_FR = {
        "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
        "vendredi": 4, "samedi": 5, "dimanche": 6
    }

    WEEKDAY_EN = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }

    @staticmethod
    def parse_date_query(date_query: str) -> datetime:
        """
        Analyse une chaîne de requête de date

        Formats pris en charge :
        - dates relatives (français) : aujourd'hui, hier, avant-hier, il y a N jours
        - dates relatives (anglais) : today, yesterday, N days ago
        - jours de la semaine (français) : lundi dernier, mercredi dernier, ce mercredi
        - jours de la semaine (anglais) : last monday, this friday
        - dates absolues : 2025-10-10, 10/10, 2025/10/10

        Args:
            date_query: chaîne de requête de date

        Returns:
            objet datetime

        Raises:
            InvalidParameterError: format de date non reconnu

        Examples:
            >>> DateParser.parse_date_query("aujourd'hui")
            datetime(2025, 10, 11)
            >>> DateParser.parse_date_query("hier")
            datetime(2025, 10, 10)
            >>> DateParser.parse_date_query("il y a 3 jours")
            datetime(2025, 10, 8)
            >>> DateParser.parse_date_query("2025-10-10")
            datetime(2025, 10, 10)
        """
        if not date_query or not isinstance(date_query, str):
            raise InvalidParameterError(
                "La chaîne de requête de date ne peut pas être vide",
                suggestion="Veuillez fournir une requête de date valide, par ex. : aujourd'hui, hier, 2025-10-10"
            )

        date_query = date_query.strip().lower()

        # 1. Essaie d'analyser les dates relatives courantes en français
        if date_query in DateParser.FR_DATE_MAPPING:
            days_ago = DateParser.FR_DATE_MAPPING[date_query]
            return datetime.now() - timedelta(days=days_ago)

        # 2. Essaie d'analyser les dates relatives courantes en anglais
        if date_query in DateParser.EN_DATE_MAPPING:
            days_ago = DateParser.EN_DATE_MAPPING[date_query]
            return datetime.now() - timedelta(days=days_ago)

        # 3. Essaie d'analyser "il y a N jours" ou "N days ago"
        fr_days_ago_match = re.match(r'il y a\s+(\d+)\s*jours?', date_query)
        if fr_days_ago_match:
            days = int(fr_days_ago_match.group(1))
            if days > 365:
                raise InvalidParameterError(
                    f"Nombre de jours trop élevé : {days} jours",
                    suggestion="Veuillez utiliser une date relative inférieure à 365 jours ou une date absolue"
                )
            return datetime.now() - timedelta(days=days)

        en_days_ago_match = re.match(r'(\d+)\s*days?\s+ago', date_query)
        if en_days_ago_match:
            days = int(en_days_ago_match.group(1))
            if days > 365:
                raise InvalidParameterError(
                    f"Nombre de jours trop élevé : {days} jours",
                    suggestion="Veuillez utiliser une date relative inférieure à 365 jours ou une date absolue"
                )
            return datetime.now() - timedelta(days=days)

        # 4. Essaie d'analyser les jours de la semaine (français) : lundi dernier, ce mercredi
        fr_weekday_match = re.match(r'(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+dernier', date_query)
        if fr_weekday_match:
            weekday_str = fr_weekday_match.group(1)
            target_weekday = DateParser.WEEKDAY_FR[weekday_str]
            return DateParser._get_date_by_weekday(target_weekday, True)

        fr_this_weekday_match = re.match(r'ce\s+(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)', date_query)
        if fr_this_weekday_match:
            weekday_str = fr_this_weekday_match.group(1)
            target_weekday = DateParser.WEEKDAY_FR[weekday_str]
            return DateParser._get_date_by_weekday(target_weekday, False)

        # 5. Essaie d'analyser les jours de la semaine (anglais) : last monday, this friday
        en_weekday_match = re.match(r'(last|this)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', date_query)
        if en_weekday_match:
            week_type = en_weekday_match.group(1)  # last ou this
            weekday_str = en_weekday_match.group(2)
            target_weekday = DateParser.WEEKDAY_EN[weekday_str]
            return DateParser._get_date_by_weekday(target_weekday, week_type == "last")

        # 6. Essaie d'analyser une date absolue : YYYY-MM-DD
        iso_date_match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_query)
        if iso_date_match:
            year = int(iso_date_match.group(1))
            month = int(iso_date_match.group(2))
            day = int(iso_date_match.group(3))
            try:
                return datetime(year, month, day)
            except ValueError as e:
                raise InvalidParameterError(
                    f"Date invalide : {date_query}",
                    suggestion=f"Valeur de date erronée : {str(e)}"
                )

        # 7. Essaie d'analyser le format avec barres obliques : YYYY/MM/DD ou MM/DD
        slash_date_match = re.match(r'(?:(\d{4})/)?(\d{1,2})/(\d{1,2})', date_query)
        if slash_date_match:
            year_str = slash_date_match.group(1)
            month = int(slash_date_match.group(2))
            day = int(slash_date_match.group(3))

            if year_str:
                year = int(year_str)
            else:
                year = datetime.now().year
                current_month = datetime.now().month
                if month > current_month:
                    year -= 1

            try:
                return datetime(year, month, day)
            except ValueError as e:
                raise InvalidParameterError(
                    f"Date invalide : {date_query}",
                    suggestion=f"Valeur de date erronée : {str(e)}"
                )

        # Si aucun format ne correspond
        raise InvalidParameterError(
            f"Format de date non reconnu : {date_query}",
            suggestion=(
                "Formats pris en charge :\n"
                "- dates relatives : aujourd'hui, hier, avant-hier, il y a 3 jours, today, yesterday, 3 days ago\n"
                "- jours de la semaine : lundi dernier, ce mercredi, last monday, this friday\n"
                "- dates absolues : 2025-10-10, 10/10, 2025/10/10"
            )
        )

    @staticmethod
    def _get_date_by_weekday(target_weekday: int, is_last_week: bool) -> datetime:
        """
        Récupère la date en fonction du jour de la semaine

        Args:
            target_weekday: jour de la semaine cible (0=lundi, 6=dimanche)
            is_last_week: indique s'il s'agit de la semaine dernière

        Returns:
            objet datetime
        """
        today = datetime.now()
        current_weekday = today.weekday()

        # Calcule la différence en jours
        if is_last_week:
            # Un jour de la semaine dernière
            days_diff = current_weekday - target_weekday + 7
        else:
            # Un jour de cette semaine
            days_diff = current_weekday - target_weekday
            if days_diff < 0:
                days_diff += 7

        return today - timedelta(days=days_diff)

    @staticmethod
    def format_date_folder(date: datetime) -> str:
        """
        Formate la date en nom de dossier

        Args:
            date: objet datetime

        Returns:
            nom de dossier, au format : YYYY-MM-DD

        Examples:
            >>> DateParser.format_date_folder(datetime(2025, 10, 11))
            '2025-10-11'
        """
        return date.strftime("%Y-%m-%d")

    @staticmethod
    def validate_date_not_future(date: datetime) -> None:
        """
        Vérifie que la date n'est pas dans le futur

        Args:
            date: date à vérifier

        Raises:
            InvalidParameterError: la date est dans le futur
        """
        if date.date() > datetime.now().date():
            raise InvalidParameterError(
                f"Impossible de consulter une date future : {date.strftime('%Y-%m-%d')}",
                suggestion="Veuillez utiliser la date d'aujourd'hui ou une date passée"
            )

    @staticmethod
    def validate_date_not_too_old(date: datetime, max_days: int = 365) -> None:
        """
        Vérifie que la date n'est pas trop ancienne

        Args:
            date: date à vérifier
            max_days: nombre maximal de jours

        Raises:
            InvalidParameterError: la date est trop ancienne
        """
        days_ago = (datetime.now().date() - date.date()).days
        if days_ago > max_days:
            raise InvalidParameterError(
                f"Date trop ancienne : {date.strftime('%Y-%m-%d')} (il y a {days_ago} jours)",
                suggestion=f"Veuillez consulter les données des {max_days} derniers jours"
            )

    @staticmethod
    def resolve_date_range_expression(expression: str) -> Dict:
        """
        Analyse une expression de date en langage naturel en une plage de dates standard

        Cette méthode est spécialement conçue pour les outils MCP afin d'analyser les expressions
        de date côté serveur, et d'éviter les incohérences dues au calcul des dates par le modèle IA.

        Args:
            expression: expression de date en langage naturel, prend en charge :
                - jour unique : "aujourd'hui", "hier", "today", "yesterday"
                - cette semaine / semaine dernière : "cette semaine", "la semaine dernière", "this week", "last week"
                - ce mois / mois dernier : "ce mois", "le mois dernier", "this month", "last month"
                - N derniers jours : "7 derniers jours", "30 derniers jours", "last 7 days", "last 30 days"
                - N jours dynamiques : "5 derniers jours", "last 10 days"

        Returns:
            dictionnaire du résultat de l'analyse :
            {
                "success": True,
                "expression": "cette semaine",
                "normalized": "this_week",
                "date_range": {
                    "start": "2025-11-18",
                    "end": "2025-11-24"
                },
                "current_date": "2025-11-26",
                "description": "cette semaine (du lundi au dimanche)"
            }

        Raises:
            InvalidParameterError: expression de date non reconnue

        Examples:
            >>> DateParser.resolve_date_range_expression("cette semaine")
            {"success": True, "date_range": {"start": "2025-11-18", "end": "2025-11-24"}, ...}

            >>> DateParser.resolve_date_range_expression("7 derniers jours")
            {"success": True, "date_range": {"start": "2025-11-20", "end": "2025-11-26"}, ...}
        """
        if not expression or not isinstance(expression, str):
            raise InvalidParameterError(
                "L'expression de date ne peut pas être vide",
                suggestion="Veuillez fournir une expression de date valide, par ex. : cette semaine, 7 derniers jours, last week"
            )

        expression_lower = expression.strip().lower()
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")

        # 1. Essaie de faire correspondre une expression prédéfinie
        normalized = DateParser.RANGE_EXPRESSIONS.get(expression_lower)

        # 2. Essaie de faire correspondre le motif dynamique "N derniers jours" / "last N days"
        if not normalized:
            # Français : N derniers jours
            fr_match = re.match(r'(?:les\s+)?(\d+)\s+derniers?\s+jours?', expression_lower)
            if fr_match:
                days = int(fr_match.group(1))
                normalized = f"last_{days}_days"

            # Anglais : last N days
            en_match = re.match(r'(?:last|past)\s+(\d+)\s+days?', expression_lower)
            if en_match:
                days = int(en_match.group(1))
                normalized = f"last_{days}_days"

        if not normalized:
            # Fournit la liste des expressions prises en charge
            supported_fr = ["aujourd'hui", "hier", "cette semaine", "la semaine dernière", "ce mois", "le mois dernier",
                           "7 derniers jours", "30 derniers jours", "N derniers jours"]
            supported_en = ["today", "yesterday", "this week", "last week",
                           "this month", "last month", "last 7 days", "last N days"]
            raise InvalidParameterError(
                f"Expression de date non reconnue : {expression}",
                suggestion=f"Expressions prises en charge :\nFrançais : {', '.join(supported_fr)}\nAnglais : {', '.join(supported_en)}"
            )

        # 3. Calcule la plage de dates selon le type normalized
        start_date, end_date, description = DateParser._calculate_date_range(
            normalized, today
        )

        return {
            "success": True,
            "expression": expression,
            "normalized": normalized,
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "current_date": today_str,
            "description": description
        }

    @staticmethod
    def _calculate_date_range(
        normalized: str,
        today: datetime
    ) -> Tuple[datetime, datetime, str]:
        """
        Calcule la plage de dates réelle selon le type de date normalisé

        Args:
            normalized: type de date normalisé
            today: date actuelle

        Returns:
            tuple (start_date, end_date, description)
        """
        # Type jour unique
        if normalized == "today":
            return today, today, "aujourd'hui"

        if normalized == "yesterday":
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday, "hier"

        # Cette semaine (du lundi au dimanche)
        if normalized == "this_week":
            # Calcule le lundi de cette semaine
            weekday = today.weekday()  # 0=lundi, 6=dimanche
            start = today - timedelta(days=weekday)
            end = start + timedelta(days=6)
            # Si la semaine n'est pas terminée, end ne peut pas dépasser aujourd'hui
            if end > today:
                end = today
            return start, end, f"cette semaine (du lundi au dimanche, du {start.strftime('%m-%d')} au {end.strftime('%m-%d')})"

        # Semaine dernière (du lundi au dimanche de la semaine dernière)
        if normalized == "last_week":
            weekday = today.weekday()
            # Lundi de cette semaine
            this_monday = today - timedelta(days=weekday)
            # Lundi de la semaine dernière
            start = this_monday - timedelta(days=7)
            end = start + timedelta(days=6)
            return start, end, f"semaine dernière (du {start.strftime('%m-%d')} au {end.strftime('%m-%d')})"

        # Ce mois (du 1er du mois à aujourd'hui)
        if normalized == "this_month":
            start = today.replace(day=1)
            return start, today, f"ce mois (du {start.strftime('%m-%d')} au {today.strftime('%m-%d')})"

        # Mois dernier (du 1er au dernier jour du mois dernier)
        if normalized == "last_month":
            # Dernier jour du mois dernier = 1er de ce mois - 1 jour
            first_of_this_month = today.replace(day=1)
            end = first_of_this_month - timedelta(days=1)
            start = end.replace(day=1)
            return start, end, f"mois dernier (du {start.strftime('%Y-%m-%d')} au {end.strftime('%Y-%m-%d')})"

        # N derniers jours (format last_N_days)
        match = re.match(r'last_(\d+)_days', normalized)
        if match:
            days = int(match.group(1))
            start = today - timedelta(days=days - 1)  # Inclut aujourd'hui, donc days-1
            return start, today, f"{days} derniers jours (du {start.strftime('%m-%d')} au {today.strftime('%m-%d')})"

        # Repli : retourne aujourd'hui
        return today, today, "aujourd'hui (par défaut)"

    @staticmethod
    def get_supported_expressions() -> Dict[str, list]:
        """
        Récupère la liste des expressions de date prises en charge

        Returns:
            liste des expressions classées par catégorie
        """
        return {
            "jour unique": ["aujourd'hui", "hier", "today", "yesterday"],
            "semaine": ["cette semaine", "la semaine dernière", "this week", "last week"],
            "mois": ["ce mois", "le mois dernier", "this month", "last month"],
            "N derniers jours": ["3 derniers jours", "7 derniers jours", "14 derniers jours", "30 derniers jours",
                      "last 3 days", "last 7 days", "last 14 days", "last 30 days"],
            "nombre de jours dynamique": ["N derniers jours", "last N days"]
        }
