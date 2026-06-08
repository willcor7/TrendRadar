"""
Outils de validation des paramètres

Fournit des fonctions de validation des paramètres unifiées.
Gère le cas où les clients MCP sérialisent les paramètres sous forme de chaînes.
"""

from datetime import datetime
from typing import List, Optional, Union
import os
import json
import yaml
import ast

from .errors import InvalidParameterError
from .date_parser import DateParser


# ==================== Fonctions auxiliaires : gestion de la sérialisation des chaînes ====================

def _parse_string_to_list(value: str) -> List[str]:
    """
    Analyse une chaîne en liste

    Formats pris en charge :
    - tableau JSON : '["zhihu", "weibo"]'
    - chaîne de liste Python : "['zhihu', 'weibo']"
    - séparée par des virgules : "zhihu, weibo" ou "zhihu,weibo"

    Args:
        value: valeur sous forme de chaîne

    Returns:
        liste analysée

    Raises:
        InvalidParameterError: échec de l'analyse
    """
    value = value.strip()

    if not value:
        return []

    # Essaie l'analyse JSON : '["zhihu", "weibo"]'
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        # Si le résultat de l'analyse n'est pas une liste, on essaie d'autres méthodes
    except json.JSONDecodeError:
        pass

    # Essaie l'analyse de littéral Python : "['zhihu', 'weibo']"
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        if isinstance(parsed, str):
            # Chaîne unique, on l'enveloppe dans une liste
            return [parsed]
    except (ValueError, SyntaxError):
        pass

    # Essaie la séparation par virgules : "zhihu, weibo" ou "zhihu,weibo"
    if ',' in value:
        items = [item.strip() for item in value.split(',')]
        return [item for item in items if item]

    # Valeur unique
    return [value]


def _parse_string_to_int(value: str, param_name: str = "paramètre") -> int:
    """
    Analyse une chaîne en entier

    Args:
        value: valeur sous forme de chaîne
        param_name: nom du paramètre (pour le message d'erreur)

    Returns:
        entier analysé

    Raises:
        InvalidParameterError: échec de l'analyse
    """
    value = value.strip()

    try:
        # Essaie une conversion directe
        return int(value)
    except ValueError:
        pass

    # Essaie d'analyser un nombre flottant puis l'arrondit
    try:
        return int(float(value))
    except ValueError:
        raise InvalidParameterError(
            f"{param_name} doit être un entier, analyse impossible : {value}",
            suggestion=f"Veuillez fournir une valeur entière valide, par ex. : 10, 50, 100"
        )


def _parse_string_to_float(value: str, param_name: str = "paramètre") -> float:
    """
    Analyse une chaîne en nombre flottant

    Args:
        value: valeur sous forme de chaîne
        param_name: nom du paramètre (pour le message d'erreur)

    Returns:
        nombre flottant analysé

    Raises:
        InvalidParameterError: échec de l'analyse
    """
    value = value.strip()

    try:
        return float(value)
    except ValueError:
        raise InvalidParameterError(
            f"{param_name} doit être un nombre, analyse impossible : {value}",
            suggestion=f"Veuillez fournir une valeur numérique valide, par ex. : 0.6, 3.0"
        )


def _parse_string_to_bool(value: str) -> bool:
    """
    Analyse une chaîne en booléen

    Args:
        value: valeur sous forme de chaîne

    Returns:
        booléen analysé
    """
    value = value.strip().lower()

    if value in ('true', '1', 'yes', 'on'):
        return True
    elif value in ('false', '0', 'no', 'off', ''):
        return False
    else:
        # Par défaut, une chaîne non vide vaut True
        return bool(value)


# Cache du mtime de la liste des plateformes (évite de relire config.yaml à chaque appel MCP)
_platforms_cache: Optional[List[str]] = None
_platforms_config_mtime: float = 0.0
_platforms_config_path: Optional[str] = None


def get_supported_platforms() -> List[str]:
    """
    Récupère dynamiquement la liste des plateformes prises en charge depuis config.yaml (avec cache mtime)

    Ne relit que lorsque config.yaml a été modifié, pour éviter les E/S répétées à chaque appel MCP.

    Returns:
        liste des ID de plateformes

    Note:
        - en cas d'échec de lecture, retourne une liste vide et laisse passer toutes les plateformes (stratégie de repli)
        - la liste des plateformes provient de la configuration platforms dans config/config.yaml
    """
    global _platforms_cache, _platforms_config_mtime, _platforms_config_path

    try:
        if _platforms_config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            _platforms_config_path = os.path.normpath(
                os.path.join(current_dir, "..", "..", "config", "config.yaml")
            )

        current_mtime = os.path.getmtime(_platforms_config_path)

        if _platforms_cache is not None and current_mtime == _platforms_config_mtime:
            return _platforms_cache

        with open(_platforms_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            platforms_config = config.get('platforms', {})
            sources = platforms_config.get('sources', [])
            _platforms_cache = [p['id'] for p in sources if 'id' in p and p.get('enabled', True)]
            _platforms_config_mtime = current_mtime
            return _platforms_cache
    except Exception as e:
        print(f"Avertissement : impossible de charger la configuration des plateformes : {e}")
        return []


def validate_platforms(platforms: Optional[Union[List[str], str]]) -> List[str]:
    """
    Valide la liste des plateformes

    Args:
        platforms: liste ou chaîne d'ID de plateformes, None signifie utiliser toutes les plateformes configurées dans config.yaml
                   Plusieurs formats sont pris en charge :
                   - None : utilise les plateformes par défaut
                   - ["zhihu", "weibo"] : tableau JSON
                   - '["zhihu", "weibo"]' : chaîne de tableau JSON
                   - "['zhihu', 'weibo']" : chaîne de liste Python
                   - "zhihu, weibo" : chaîne séparée par des virgules
                   - "zhihu" : chaîne d'une seule plateforme

    Returns:
        liste des plateformes validée

    Raises:
        InvalidParameterError: plateforme non prise en charge

    Note:
        - quand platforms=None, retourne la liste des plateformes configurées dans config.yaml
        - vérifie si l'ID de plateforme figure dans la configuration platforms de config.yaml
        - en cas d'échec de chargement de la configuration, laisse passer toutes les plateformes (stratégie de repli)
    """
    supported_platforms = get_supported_platforms()

    if platforms is None:
        # Retourne la liste des plateformes du fichier de configuration (configuration par défaut de l'utilisateur)
        return supported_platforms if supported_platforms else []

    # Prend en charge une liste fournie sous forme de chaîne (certains clients MCP sérialisent les tableaux JSON en chaînes)
    if isinstance(platforms, str):
        platforms = _parse_string_to_list(platforms)
        if not platforms:
            # Chaîne vide ou vide après analyse, utilise les plateformes par défaut
            return supported_platforms if supported_platforms else []

    if not isinstance(platforms, list):
        raise InvalidParameterError("Le paramètre platforms doit être de type liste")

    if not platforms:
        # Liste vide : retourne la liste des plateformes du fichier de configuration
        return supported_platforms if supported_platforms else []

    # Si le chargement de la configuration a échoué (supported_platforms vide), laisse passer toutes les plateformes
    if not supported_platforms:
        print("Avertissement : configuration des plateformes non chargée, validation des plateformes ignorée")
        return platforms

    # Vérifie si chaque plateforme figure dans la configuration
    invalid_platforms = [p for p in platforms if p not in supported_platforms]
    if invalid_platforms:
        raise InvalidParameterError(
            f"Plateformes non prises en charge : {', '.join(invalid_platforms)}",
            suggestion=f"Plateformes prises en charge (depuis config.yaml) : {', '.join(supported_platforms)}"
        )

    return platforms


def validate_limit(limit: Optional[Union[int, str]], default: int = 20, max_limit: int = 1000) -> int:
    """
    Valide le paramètre de limite de quantité

    Args:
        limit: quantité limite (entier ou chaîne)
        default: valeur par défaut
        max_limit: limite maximale

    Returns:
        valeur de limite validée

    Raises:
        InvalidParameterError: paramètre invalide
    """
    if limit is None:
        return default

    # Prend en charge un entier fourni sous forme de chaîne (certains clients MCP sérialisent les nombres en chaînes)
    if isinstance(limit, str):
        limit = _parse_string_to_int(limit, "limit")

    if not isinstance(limit, int):
        raise InvalidParameterError("Le paramètre limit doit être de type entier")

    if limit <= 0:
        raise InvalidParameterError("limit doit être supérieur à 0")

    if limit > max_limit:
        raise InvalidParameterError(
            f"limit ne peut pas dépasser {max_limit}",
            suggestion=f"Veuillez utiliser la pagination ou réduire la valeur de limit"
        )

    return limit


def validate_date(date_str: str) -> datetime:
    """
    Valide le format de date

    Args:
        date_str: chaîne de date (YYYY-MM-DD)

    Returns:
        objet datetime

    Raises:
        InvalidParameterError: format de date erroné
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise InvalidParameterError(
            f"Format de date erroné : {date_str}",
            suggestion="Veuillez utiliser le format YYYY-MM-DD, par exemple : 2025-10-11"
        )


def normalize_date_range(date_range: Optional[Union[dict, str]]) -> Optional[Union[dict, str]]:
    """
    Normalise le paramètre date_range

    Certains clients MCP (notamment via HTTP) sérialisent les objets JSON en chaînes lors de la transmission.
    Cette fonction tente d'analyser la chaîne JSON en dict ; si ce n'est pas du JSON, elle la laisse telle quelle.

    Args:
        date_range: plage de dates, qui peut être :
            - dict : {"start": "2025-01-01", "end": "2025-01-07"}
            - chaîne JSON : '{"start": "2025-01-01", "end": "2025-01-07"}'
            - chaîne simple : "aujourd'hui", "hier", "2025-01-01"
            - None

    Returns:
        date_range normalisée (dict ou chaîne simple)

    Examples:
        >>> normalize_date_range('{"start":"2025-01-01","end":"2025-01-07"}')
        {"start": "2025-01-01", "end": "2025-01-07"}
        >>> normalize_date_range("aujourd'hui")
        "aujourd'hui"
        >>> normalize_date_range({"start": "2025-01-01", "end": "2025-01-07"})
        {"start": "2025-01-01", "end": "2025-01-07"}
    """
    if date_range is None:
        return None

    # Si c'est déjà un dict, on le retourne directement
    if isinstance(date_range, dict):
        return date_range

    # Si c'est une chaîne, on essaie de l'analyser en JSON
    if isinstance(date_range, str):
        # Vérifie si elle ressemble à un objet JSON
        stripped = date_range.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass  # Échec de l'analyse, on la traite comme une chaîne simple

    return date_range


def validate_date_range(date_range: Optional[Union[dict, str]]) -> Optional[tuple]:
    """
    Valide la plage de dates

    Args:
        date_range: plage de dates, plusieurs formats pris en charge :
            - dict : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            - chaîne JSON : '{"start": "2025-01-01", "end": "2025-01-07"}'
            - chaîne d'un seul jour : "2025-01-01" (convertie automatiquement en plage d'un même jour)
            - langage naturel : "aujourd'hui", "hier", "cette semaine", "les 7 derniers jours", etc.

    Returns:
        tuple (start_date, end_date), ou None

    Raises:
        InvalidParameterError: plage de dates invalide
    """
    if date_range is None:
        return None

    # Prend en charge une entrée fournie sous forme de chaîne
    if isinstance(date_range, str):
        stripped = date_range.strip()

        # 1. Vérifie si c'est au format objet JSON
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                date_range = json.loads(stripped)
            except json.JSONDecodeError as e:
                raise InvalidParameterError(
                    f"Échec de l'analyse JSON de date_range : {e}",
                    suggestion='Veuillez utiliser le format JSON correct : {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}'
                )
        # 2. Vérifie si c'est une chaîne d'un seul jour au format YYYY-MM-DD
        elif len(stripped) == 10 and stripped[4] == '-' and stripped[7] == '-':
            try:
                single_date = datetime.strptime(stripped, "%Y-%m-%d")
                return (single_date, single_date)
            except ValueError:
                raise InvalidParameterError(
                    f"Format de date erroné : {stripped}",
                    suggestion="Veuillez utiliser le format YYYY-MM-DD, par exemple : 2025-10-11"
                )
        # 3. Essaie une analyse en langage naturel
        else:
            try:
                result = DateParser.resolve_date_range_expression(stripped)
                if result.get("success"):
                    dr = result["date_range"]
                    start_date = datetime.strptime(dr["start"], "%Y-%m-%d")
                    end_date = datetime.strptime(dr["end"], "%Y-%m-%d")
                    return (start_date, end_date)
                else:
                    raise InvalidParameterError(
                        f"Expression de date non reconnue : {stripped}",
                        suggestion="Formats pris en charge : YYYY-MM-DD, {\"start\": \"...\", \"end\": \"...\"}, ou langage naturel (aujourd'hui, cette semaine, les 7 derniers jours, etc.)"
                    )
            except InvalidParameterError:
                raise
            except Exception:
                raise InvalidParameterError(
                    f"Échec de l'analyse de la date : {stripped}",
                    suggestion="Formats pris en charge : YYYY-MM-DD, {\"start\": \"...\", \"end\": \"...\"}, ou langage naturel (aujourd'hui, cette semaine, les 7 derniers jours, etc.)"
                )

    if not isinstance(date_range, dict):
        raise InvalidParameterError(
            "date_range doit être un dictionnaire, une chaîne de date ou une chaîne JSON valide",
            suggestion='par exemple : {"start": "2025-10-01", "end": "2025-10-11"} ou "2025-10-01"'
        )

    start_str = date_range.get("start")
    end_str = date_range.get("end")

    if not start_str or not end_str:
        raise InvalidParameterError(
            "date_range doit contenir les champs start et end",
            suggestion='par exemple : {"start": "2025-10-01", "end": "2025-10-11"}'
        )

    start_date = validate_date(start_str)
    end_date = validate_date(end_str)

    if start_date > end_date:
        raise InvalidParameterError(
            "La date de début ne peut pas être postérieure à la date de fin",
            suggestion=f"start: {start_str}, end: {end_str}"
        )

    # Vérifie si la date est dans le futur
    today = datetime.now().date()
    if start_date.date() > today or end_date.date() > today:
        # Récupère un indice de la plage de dates disponible
        try:
            from ..services.data_service import DataService
            data_service = DataService()
            earliest, latest = data_service.get_available_date_range()

            if earliest and latest:
                available_range = f"{earliest.strftime('%Y-%m-%d')} à {latest.strftime('%Y-%m-%d')}"
            else:
                available_range = "aucune donnée disponible"
        except Exception:
            available_range = "inconnue (veuillez vérifier le répertoire output)"

        future_dates = []
        if start_date.date() > today:
            future_dates.append(start_str)
        if end_date.date() > today and end_str != start_str:
            future_dates.append(end_str)

        raise InvalidParameterError(
            f"La consultation de dates futures n'est pas autorisée : {', '.join(future_dates)} (date actuelle : {today.strftime('%Y-%m-%d')})",
            suggestion=f"Plage de données actuellement disponible : {available_range}"
        )

    return (start_date, end_date)


def validate_keyword(keyword: str) -> str:
    """
    Valide le mot-clé

    Args:
        keyword: mot-clé de recherche

    Returns:
        mot-clé traité

    Raises:
        InvalidParameterError: mot-clé invalide
    """
    if not keyword:
        raise InvalidParameterError("keyword ne peut pas être vide")

    if not isinstance(keyword, str):
        raise InvalidParameterError("keyword doit être de type chaîne")

    keyword = keyword.strip()

    if not keyword:
        raise InvalidParameterError("keyword ne peut pas être composé uniquement d'espaces")

    if len(keyword) > 100:
        raise InvalidParameterError(
            "La longueur de keyword ne peut pas dépasser 100 caractères",
            suggestion="Veuillez utiliser un mot-clé plus concis"
        )

    return keyword


def validate_top_n(top_n: Optional[Union[int, str]], default: int = 10) -> int:
    """
    Valide le paramètre TOP N

    Args:
        top_n: quantité TOP N (entier ou chaîne)
        default: valeur par défaut

    Returns:
        valeur validée

    Raises:
        InvalidParameterError: paramètre invalide
    """
    return validate_limit(top_n, default=default, max_limit=100)


def validate_mode(mode: Optional[str], valid_modes: List[str], default: str) -> str:
    """
    Valide le paramètre de mode

    Args:
        mode: chaîne de mode
        valid_modes: liste des modes valides
        default: mode par défaut

    Returns:
        mode validé

    Raises:
        InvalidParameterError: mode invalide
    """
    if mode is None:
        return default

    if not isinstance(mode, str):
        raise InvalidParameterError("mode doit être de type chaîne")

    if mode not in valid_modes:
        raise InvalidParameterError(
            f"Mode invalide : {mode}",
            suggestion=f"Modes pris en charge : {', '.join(valid_modes)}"
        )

    return mode


def validate_config_section(section: Optional[str]) -> str:
    """
    Valide le paramètre de section de configuration

    Args:
        section: nom de la section de configuration

    Returns:
        section de configuration validée

    Raises:
        InvalidParameterError: section de configuration invalide
    """
    valid_sections = ["all", "crawler", "push", "keywords", "weights"]
    return validate_mode(section, valid_sections, "all")


def validate_threshold(
    threshold: Optional[Union[float, int, str]],
    default: float = 0.6,
    min_value: float = 0.0,
    max_value: float = 1.0,
    param_name: str = "threshold"
) -> float:
    """
    Valide le paramètre de seuil (nombre flottant)

    Args:
        threshold: seuil (nombre flottant, entier ou chaîne)
        default: valeur par défaut
        min_value: valeur minimale
        max_value: valeur maximale
        param_name: nom du paramètre (pour le message d'erreur)

    Returns:
        seuil validé

    Raises:
        InvalidParameterError: paramètre invalide
    """
    if threshold is None:
        return default

    # Prend en charge un nombre fourni sous forme de chaîne (certains clients MCP sérialisent les nombres en chaînes)
    if isinstance(threshold, str):
        threshold = _parse_string_to_float(threshold, param_name)

    # Conversion entier vers flottant
    if isinstance(threshold, int):
        threshold = float(threshold)

    if not isinstance(threshold, float):
        raise InvalidParameterError(
            f"{param_name} doit être de type numérique",
            suggestion=f"Veuillez fournir un nombre compris entre {min_value} et {max_value}"
        )

    if threshold < min_value or threshold > max_value:
        raise InvalidParameterError(
            f"{param_name} doit être compris entre {min_value} et {max_value}, valeur actuelle : {threshold}",
            suggestion=f"Valeur recommandée : {default}"
        )

    return threshold


def validate_date_query(
    date_query: str,
    allow_future: bool = False,
    max_days_ago: int = 365
) -> datetime:
    """
    Valide et analyse la chaîne de requête de date

    Args:
        date_query: chaîne de requête de date
        allow_future: indique si les dates futures sont autorisées
        max_days_ago: nombre maximal de jours autorisé pour la requête

    Returns:
        objet datetime analysé

    Raises:
        InvalidParameterError: requête de date invalide

    Examples:
        >>> validate_date_query("hier")
        datetime(2025, 10, 10)
        >>> validate_date_query("2025-10-10")
        datetime(2025, 10, 10)
    """
    if not date_query:
        raise InvalidParameterError(
            "La chaîne de requête de date ne peut pas être vide",
            suggestion="Veuillez fournir une requête de date, par ex. : aujourd'hui, hier, 2025-10-10"
        )

    # Analyse la date avec DateParser
    parsed_date = DateParser.parse_date_query(date_query)

    # Vérifie que la date n'est pas dans le futur
    if not allow_future:
        DateParser.validate_date_not_future(parsed_date)

    # Vérifie que la date n'est pas trop ancienne
    DateParser.validate_date_not_too_old(parsed_date, max_days=max_days_ago)

    return parsed_date

