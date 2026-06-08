# coding=utf-8
"""
Module utilitaire de configuration - analyse et validation des configurations multi-comptes

Fournit l'analyse, la validation et la limitation des configurations d'envoi multi-comptes.
"""

from typing import Dict, List, Optional, Tuple


def parse_multi_account_config(config_value: str, separator: str = ";") -> List[str]:
    """
    Analyse une configuration multi-comptes et retourne la liste des comptes.

    Args:
        config_value: chaîne de configuration, les comptes étant séparés par le séparateur
        separator: séparateur, ";" par défaut

    Returns:
        la liste des comptes ; les chaînes vides sont conservées (pour servir de marque-place)

    Examples:
        >>> parse_multi_account_config("url1;url2;url3")
        ['url1', 'url2', 'url3']
        >>> parse_multi_account_config(";token2")  # le premier compte n'a pas de token
        ['', 'token2']
        >>> parse_multi_account_config("")
        []
    """
    if not config_value:
        return []
    # On conserve les chaînes vides comme marque-place (par exemple ";token2" indique que le premier compte n'a pas de token)
    accounts = [acc.strip() for acc in config_value.split(separator)]
    # On filtre le cas où tout est vide
    if all(not acc for acc in accounts):
        return []
    return accounts


def validate_paired_configs(
    configs: Dict[str, List[str]],
    channel_name: str,
    required_keys: Optional[List[str]] = None
) -> Tuple[bool, int]:
    """
    Vérifie que le nombre d'éléments des configurations appariées est cohérent.

    Pour les canaux qui nécessitent l'appariement de plusieurs éléments de configuration
    (par exemple le token et le chat_id de Telegram), vérifie que le nombre de comptes
    est cohérent entre tous les éléments de configuration.

    Args:
        configs: dictionnaire de configuration ; la clé est le nom de configuration, la valeur est la liste des comptes
        channel_name: nom du canal, utilisé pour la sortie des journaux
        required_keys: liste des éléments de configuration qui doivent avoir une valeur

    Returns:
        (validation réussie ou non, nombre de comptes)

    Examples:
        >>> validate_paired_configs({
        ...     "token": ["t1", "t2"],
        ...     "chat_id": ["c1", "c2"]
        ... }, "Telegram", ["token", "chat_id"])
        (True, 2)

        >>> validate_paired_configs({
        ...     "token": ["t1", "t2"],
        ...     "chat_id": ["c1"]  # le nombre ne correspond pas
        ... }, "Telegram", ["token", "chat_id"])
        (False, 0)
    """
    # On filtre les listes vides
    non_empty_configs = {k: v for k, v in configs.items() if v}

    if not non_empty_configs:
        return True, 0

    # On vérifie les éléments obligatoires
    if required_keys:
        for key in required_keys:
            if key not in non_empty_configs or not non_empty_configs[key]:
                return True, 0  # un élément obligatoire est vide, considéré comme non configuré

    # On récupère la longueur de toutes les configurations non vides
    lengths = {k: len(v) for k, v in non_empty_configs.items()}
    unique_lengths = set(lengths.values())

    if len(unique_lengths) > 1:
        print(f"❌ Erreur de configuration {channel_name} : le nombre des configurations appariées est incohérent, l'envoi sur ce canal sera ignoré")
        for key, length in lengths.items():
            print(f"   - {key} : {length}")
        return False, 0

    return True, list(unique_lengths)[0] if unique_lengths else 0


def limit_accounts(
    accounts: List[str],
    max_count: int,
    channel_name: str
) -> List[str]:
    """
    Limite le nombre de comptes.

    Lorsque le nombre de comptes configurés dépasse la limite maximale, seuls les
    N premiers comptes sont utilisés et un message d'avertissement est affiché.

    Args:
        accounts: liste des comptes
        max_count: nombre maximal de comptes
        channel_name: nom du canal, utilisé pour la sortie des journaux

    Returns:
        la liste des comptes après limitation

    Examples:
        >>> limit_accounts(["a1", "a2", "a3"], 2, "Feishu")
        ⚠️ Feishu : 3 comptes configurés, ce qui dépasse la limite maximale de 2 ; seuls les 2 premiers seront utilisés
        ['a1', 'a2']
    """
    if len(accounts) > max_count:
        print(f"⚠️ {channel_name} : {len(accounts)} comptes configurés, ce qui dépasse la limite maximale de {max_count} ; seuls les {max_count} premiers seront utilisés")
        print(f"   ⚠️ Avertissement : si vous êtes un utilisateur de fork, un trop grand nombre de comptes peut allonger excessivement le temps d'exécution de GitHub Actions et présenter un risque pour vos comptes")
        return accounts[:max_count]
    return accounts


def get_account_at_index(accounts: List[str], index: int, default: str = "") -> str:
    """
    Récupère de manière sûre la valeur du compte à l'index indiqué.

    Lorsque l'index est hors limites ou que la valeur du compte est vide, la valeur
    par défaut est retournée.

    Args:
        accounts: liste des comptes
        index: index
        default: valeur par défaut

    Returns:
        la valeur du compte ou la valeur par défaut

    Examples:
        >>> get_account_at_index(["a", "b", "c"], 1)
        'b'
        >>> get_account_at_index(["a", "", "c"], 1, "default")
        'default'
        >>> get_account_at_index(["a"], 5, "default")
        'default'
    """
    if index < len(accounts):
        return accounts[index] if accounts[index] else default
    return default
