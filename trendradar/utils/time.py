# coding=utf-8
"""
Module d'utilitaires de gestion du temps

Ce module fournit des fonctions uniformes de traitement du temps ; toutes les opérations liées au
fuseau horaire doivent utiliser la constante DEFAULT_TIMEZONE.
"""

from datetime import datetime
from typing import Optional

import pytz

# Constante de fuseau horaire par défaut - sert uniquement de repli (fallback) ; en fonctionnement normal, on utilise app.timezone dans config.yaml
DEFAULT_TIMEZONE = "Asia/Shanghai"


def get_configured_time(timezone: str = DEFAULT_TIMEZONE) -> datetime:
    """
    Récupère l'heure actuelle dans le fuseau horaire configuré

    Args:
        timezone: nom du fuseau horaire, comme 'Asia/Shanghai', 'America/Los_Angeles'

    Returns:
        l'heure actuelle, avec l'information de fuseau horaire
    """
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        print(f"[Avertissement] Fuseau horaire inconnu '{timezone}', utilisation du fuseau horaire par défaut {DEFAULT_TIMEZONE}")
        tz = pytz.timezone(DEFAULT_TIMEZONE)
    return datetime.now(tz)


def format_date_folder(
    date: Optional[str] = None, timezone: str = DEFAULT_TIMEZONE
) -> str:
    """
    Formate le nom du dossier de date (format ISO : YYYY-MM-DD)

    Args:
        date: chaîne de date indiquée ; si None, utilise la date actuelle
        timezone: nom du fuseau horaire

    Returns:
        la chaîne de date formatée, comme '2025-12-09'
    """
    if date:
        return date
    return get_configured_time(timezone).strftime("%Y-%m-%d")


def format_time_filename(timezone: str = DEFAULT_TIMEZONE) -> str:
    """
    Formate le nom de fichier basé sur l'heure (format : HH-MM, destiné aux noms de fichiers)

    Le système Windows n'accepte pas le deux-points dans les noms de fichiers, c'est pourquoi on utilise un trait d'union

    Args:
        timezone: nom du fuseau horaire

    Returns:
        la chaîne d'heure formatée, comme '15-30'
    """
    return get_configured_time(timezone).strftime("%H-%M")


def get_current_time_display(timezone: str = DEFAULT_TIMEZONE) -> str:
    """
    Récupère l'heure actuelle pour affichage (format : HH:MM, destiné à l'affichage)

    Args:
        timezone: nom du fuseau horaire

    Returns:
        la chaîne d'heure formatée, comme '15:30'
    """
    return get_configured_time(timezone).strftime("%H:%M")


def convert_time_for_display(time_str: str) -> str:
    """
    Convertit le format HH-MM en format HH:MM pour l'affichage

    Args:
        time_str: chaîne d'heure en entrée, comme '15-30'

    Returns:
        la chaîne d'heure après conversion, comme '15:30'
    """
    if time_str and "-" in time_str and len(time_str) == 5:
        return time_str.replace("-", ":")
    return time_str


def format_iso_time_friendly(
    iso_time: str,
    timezone: str = DEFAULT_TIMEZONE,
    include_date: bool = True,
) -> str:
    """
    Convertit une heure au format ISO en un format d'affichage lisible dans le fuseau horaire de l'utilisateur

    Args:
        iso_time: chaîne d'heure au format ISO, comme '2025-12-29T00:20:00' ou '2025-12-29T00:20:00+00:00'
        timezone: nom du fuseau horaire cible
        include_date: indique s'il faut inclure la partie date

    Returns:
        la chaîne d'heure au format lisible, comme '12-29 08:20' ou '08:20'
    """
    if not iso_time:
        return ""

    try:
        # Tente d'analyser les différents formats ISO
        dt = None

        # Tente d'analyser le format avec fuseau horaire
        if "+" in iso_time or iso_time.endswith("Z"):
            iso_time = iso_time.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(iso_time)
            except ValueError:
                pass

        # Tente d'analyser le format sans fuseau horaire (supposé être en UTC)
        if dt is None:
            try:
                # Traite le séparateur T
                if "T" in iso_time:
                    dt = datetime.fromisoformat(iso_time.replace("T", " ").split(".")[0])
                else:
                    dt = datetime.fromisoformat(iso_time.split(".")[0])
                # Supposé être une heure UTC
                dt = pytz.UTC.localize(dt)
            except ValueError:
                pass

        if dt is None:
            # Impossible d'analyser : retourne une version simplifiée de la chaîne d'origine
            if "T" in iso_time:
                parts = iso_time.split("T")
                if len(parts) == 2:
                    date_part = parts[0][5:]  # MM-DD
                    time_part = parts[1][:5]  # HH:MM
                    return f"{date_part} {time_part}" if include_date else time_part
            return iso_time

        # Convertit vers le fuseau horaire cible
        try:
            target_tz = pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            target_tz = pytz.timezone(DEFAULT_TIMEZONE)

        dt_local = dt.astimezone(target_tz)

        # Formate la sortie
        if include_date:
            return dt_local.strftime("%m-%d %H:%M")
        else:
            return dt_local.strftime("%H:%M")

    except Exception:
        # En cas d'erreur, retourne une version simplifiée de la chaîne d'origine
        if "T" in iso_time:
            parts = iso_time.split("T")
            if len(parts) == 2:
                date_part = parts[0][5:]  # MM-DD
                time_part = parts[1][:5]  # HH:MM
                return f"{date_part} {time_part}" if include_date else time_part
        return iso_time


def is_within_days(
    iso_time: str,
    max_days: int,
    timezone: str = DEFAULT_TIMEZONE,
) -> bool:
    """
    Vérifie si une heure au format ISO se situe dans le nombre de jours indiqué

    Sert au filtrage de fraîcheur des articles RSS, pour déterminer si la date de publication d'un article
    dépasse le nombre de jours indiqué.

    Args:
        iso_time: chaîne d'heure au format ISO (comme '2025-12-29T00:20:00' ou avec fuseau horaire)
        max_days: nombre maximal de jours (retourne True si la date de publication de l'article ne dépasse pas ce nombre de jours)
            - max_days > 0 : filtrage normal, conserve les articles des N derniers jours
            - max_days <= 0 : filtrage désactivé, conserve tous les articles
        timezone: nom du fuseau horaire (sert à récupérer l'heure actuelle)

    Returns:
        True si l'heure est dans le nombre de jours indiqué (à conserver), False si elle le dépasse (à filtrer)
        Si l'heure ne peut pas être analysée, retourne True (l'article est conservé)
    """
    # En l'absence d'horodatage ou si le filtrage est désactivé, on conserve l'article
    if not iso_time:
        return True
    if max_days <= 0:
        return True  # max_days=0 signifie que le filtrage est désactivé

    try:
        dt = None

        # Tente d'analyser le format avec fuseau horaire
        if "+" in iso_time or iso_time.endswith("Z"):
            iso_time_normalized = iso_time.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(iso_time_normalized)
            except ValueError:
                pass

        # Tente d'analyser le format sans fuseau horaire (supposé être en UTC)
        if dt is None:
            try:
                if "T" in iso_time:
                    dt = datetime.fromisoformat(iso_time.replace("T", " ").split(".")[0])
                else:
                    dt = datetime.fromisoformat(iso_time.split(".")[0])
                dt = pytz.UTC.localize(dt)
            except ValueError:
                pass

        if dt is None:
            # Impossible d'analyser l'heure, on conserve l'article
            return True

        # Récupère l'heure actuelle (dans le fuseau horaire configuré, avec l'information de fuseau horaire)
        now = get_configured_time(timezone)

        # Calcule l'écart de temps (la soustraction de deux datetime avec fuseau horaire gère automatiquement les différences de fuseau)
        diff = now - dt
        days_diff = diff.total_seconds() / (24 * 60 * 60)

        return days_diff <= max_days

    except Exception:
        # En cas d'erreur, on conserve l'article
        return True


def calculate_days_old(iso_time: str, timezone: str = DEFAULT_TIMEZONE) -> Optional[float]:
    """
    Calcule depuis combien de jours date une heure au format ISO

    Args:
        iso_time: chaîne d'heure au format ISO
        timezone: nom du fuseau horaire

    Returns:
        le nombre de jours écoulés (nombre flottant) ; retourne None si l'analyse échoue
    """
    if not iso_time:
        return None

    try:
        dt = None

        # Tente d'analyser le format avec fuseau horaire
        if "+" in iso_time or iso_time.endswith("Z"):
            iso_time_normalized = iso_time.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(iso_time_normalized)
            except ValueError:
                pass

        # Tente d'analyser le format sans fuseau horaire (supposé être en UTC)
        if dt is None:
            try:
                if "T" in iso_time:
                    dt = datetime.fromisoformat(iso_time.replace("T", " ").split(".")[0])
                else:
                    dt = datetime.fromisoformat(iso_time.split(".")[0])
                dt = pytz.UTC.localize(dt)
            except ValueError:
                pass

        if dt is None:
            return None

        now = get_configured_time(timezone)
        diff = now - dt
        return diff.total_seconds() / (24 * 60 * 60)

    except Exception:
        return None

