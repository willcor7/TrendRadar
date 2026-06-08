# coding=utf-8
"""
Module de chargement de la configuration des mots-clés de fréquence

Responsable du chargement des règles de mots-clés depuis le fichier de configuration. Prend en charge :
- les groupes de mots ordinaires
- les mots obligatoires (préfixe +)
- les mots de filtrage (préfixe !)
- les mots de filtrage global (section [GLOBAL_FILTER])
- le nombre maximal d'affichages (préfixe @)
- les expressions régulières (syntaxe /pattern/)
- le nom d'affichage (syntaxe d'alias =>)
- l'alias de groupe (syntaxe [alias de groupe], placée en première ligne du groupe de mots)
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union


def _parse_word(word: str) -> Dict:
    """
    Analyse un mot unique, détermine s'il s'agit d'une expression régulière et prend en charge le nom d'affichage.

    Args:
        word: ligne de configuration d'origine (e.g. "/Paris|Lutèce/ => Paris")

    Returns:
        Dict: contient word, is_regex, pattern, display_name
    """
    display_name = None

    # 1. On traite en priorité le nom d'affichage (=>)
    # On sépare d'abord le « contenu de configuration » du « nom d'affichage »
    if '=>' in word:
        parts = re.split(r'\s*=>\s*', word, 1)
        word_config = parts[0].strip()
        # On ne prend la partie droite de => comme display_name que si elle contient du texte
        if len(parts) > 1 and parts[1].strip():
            display_name = parts[1].strip()
    else:
        word_config = word.strip()

    # 2. On analyse l'expression régulière
    # Règle : commence par /, se termine par / (éventuellement suivi de flags), le contenu intermédiaire est extrait de façon gourmande
    # [a-z]*$ indique que des flags finaux (comme i, g) sont autorisés, mais ils sont ignorés dans le code ci-dessous
    regex_match = re.match(r'^/(.+)/[a-z]*$', word_config)

    if regex_match:
        pattern_str = regex_match.group(1)
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            
            return {
                "word": pattern_str,
                "is_regex": True,
                "pattern": pattern,
                "display_name": display_name,
            }
        except re.error as e:
            print(f"Warning: Invalid regex pattern '/{pattern_str}/': {e}")
            pass

    return {
        "word": word_config, 
        "is_regex": False, 
        "pattern": None, 
        "display_name": display_name
    }


def _word_matches(word_config: Union[str, Dict], title_lower: str) -> bool:
    """
    Vérifie si le mot correspond dans le titre.

    Args:
        word_config: configuration du mot (chaîne de caractères ou dictionnaire)
        title_lower: titre en minuscules

    Returns:
        s'il y a correspondance
    """
    if isinstance(word_config, str):
        # Rétrocompatibilité : chaîne de caractères simple
        return word_config.lower() in title_lower

    if word_config.get("is_regex") and word_config.get("pattern"):
        # Correspondance par expression régulière
        return bool(word_config["pattern"].search(title_lower))
    else:
        # Correspondance par sous-chaîne
        return word_config["word"].lower() in title_lower


def load_frequency_words(
    frequency_file: Optional[str] = None,
) -> Tuple[List[Dict], List[str], List[str]]:
    """
    Charge la configuration des mots-clés de fréquence.

    Format du fichier de configuration :
    - chaque groupe de mots est séparé par une ligne vide
    - la section [GLOBAL_FILTER] définit les mots de filtrage global
    - la section [WORD_GROUPS] définit les groupes de mots (par défaut)

    Syntaxe des groupes de mots :
    - mot ordinaire : écrit tel quel, une correspondance quelconque suffit
    - +mot : mot obligatoire, tous les mots obligatoires doivent correspondre
    - !mot : mot de filtrage, le titre est exclu en cas de correspondance
    - @nombre : nombre maximal d'entrées affichées pour ce groupe de mots

    Args:
        frequency_file: chemin du fichier de configuration des mots-clés ; par défaut, récupéré depuis la variable d'environnement FREQUENCY_WORDS_PATH ou config/frequency_words.txt ; un nom de fichier court est recherché dans config/custom/keyword/

    Returns:
        (liste des groupes de mots, mots de filtrage propres aux groupes, mots de filtrage global)

    Raises:
        FileNotFoundError: le fichier de mots-clés n'existe pas
    """
    if frequency_file is None:
        frequency_file = os.environ.get(
            "FREQUENCY_WORDS_PATH", "config/frequency_words.txt"
        )

    frequency_path = Path(frequency_file)
    if not frequency_path.exists():
        # On l'interprète comme un nom de fichier court en lui ajoutant le préfixe config/custom/keyword/
        custom_path = Path("config/custom/keyword") / frequency_file
        if custom_path.exists():
            frequency_path = custom_path
        else:
            raise FileNotFoundError(f"Le fichier de mots-clés {frequency_file} n'existe pas")

    with open(frequency_path, "r", encoding="utf-8") as f:
        content = f.read()

    word_groups = [group.strip() for group in content.split("\n\n") if group.strip()]

    processed_groups = []
    filter_words = []
    global_filters = []

    # Section par défaut (rétrocompatibilité)
    current_section = "WORD_GROUPS"

    for group in word_groups:
        # On filtre les lignes vides et les lignes de commentaire (commençant par #)
        lines = [line.strip() for line in group.split("\n") if line.strip() and not line.strip().startswith("#")]

        if not lines:
            continue

        # On vérifie s'il s'agit d'un marqueur de section
        if lines[0].startswith("[") and lines[0].endswith("]"):
            section_name = lines[0][1:-1].upper()
            if section_name in ("GLOBAL_FILTER", "WORD_GROUPS"):
                current_section = section_name
                lines = lines[1:]  # On retire la ligne du marqueur

        # On traite la section de filtrage global
        if current_section == "GLOBAL_FILTER":
            # On ajoute directement toutes les lignes non vides à la liste de filtrage global
            for line in lines:
                # On ignore les préfixes de syntaxe spéciale, on n'extrait que le texte brut
                if line.startswith(("!", "+", "@")):
                    continue  # la section de filtrage global ne prend pas en charge la syntaxe spéciale
                if line:
                    global_filters.append(line)
            continue

        # On traite la section des groupes de mots
        words = lines
        group_alias = None  # alias de groupe (syntaxe [alias])

        # On vérifie si la première ligne est un alias de groupe (et non un marqueur de section)
        if words and words[0].startswith("[") and words[0].endswith("]"):
            potential_alias = words[0][1:-1].strip()
            # On exclut les marqueurs de section (GLOBAL_FILTER, WORD_GROUPS)
            if potential_alias.upper() not in ("GLOBAL_FILTER", "WORD_GROUPS"):
                group_alias = potential_alias
                words = words[1:]  # On retire la ligne de l'alias de groupe

        group_required_words = []
        group_normal_words = []
        group_max_count = 0  # aucune limite par défaut

        for word in words:
            if word.startswith("@"):
                # On analyse le nombre maximal d'affichages (seuls les entiers positifs sont acceptés)
                try:
                    count = int(word[1:])
                    if count > 0:
                        group_max_count = count
                except (ValueError, IndexError):
                    pass  # On ignore un format @nombre invalide
            elif word.startswith("!"):
                # Mot de filtrage (prend en charge la syntaxe des expressions régulières)
                filter_word = word[1:]
                parsed = _parse_word(filter_word)
                filter_words.append(parsed)
            elif word.startswith("+"):
                # Mot obligatoire (prend en charge la syntaxe des expressions régulières)
                req_word = word[1:]
                group_required_words.append(_parse_word(req_word))
            else:
                # Mot ordinaire (prend en charge la syntaxe des expressions régulières)
                group_normal_words.append(_parse_word(word))

        if group_required_words or group_normal_words:
            if group_normal_words:
                group_key = " ".join(w["word"] for w in group_normal_words)
            else:
                group_key = " ".join(w["word"] for w in group_required_words)

            # On génère le nom d'affichage
            # Priorité : alias de groupe > concaténation des alias de ligne > concaténation des mots-clés
            if group_alias:
                # Un alias de groupe est présent, on l'utilise directement
                display_name = group_alias
            else:
                # Aucun alias de groupe : on concatène le nom d'affichage de chaque ligne (alias de ligne ou mot-clé lui-même)
                all_words = group_normal_words + group_required_words
                display_parts = []
                for w in all_words:
                    # On privilégie l'alias de ligne, sinon on utilise le mot-clé lui-même
                    part = w.get("display_name") or w["word"]
                    display_parts.append(part)
                # On concatène les différents mots avec " / "
                display_name = " / ".join(display_parts) if display_parts else None

            processed_groups.append(
                {
                    "required": group_required_words,
                    "normal": group_normal_words,
                    "group_key": group_key,
                    "display_name": display_name,  # peut être None
                    "max_count": group_max_count,
                }
            )

    return processed_groups, filter_words, global_filters


def matches_word_groups(
    title: str,
    word_groups: List[Dict],
    filter_words: List,
    global_filters: Optional[List[str]] = None
) -> bool:
    """
    Vérifie si le titre correspond aux règles des groupes de mots.

    Args:
        title: texte du titre
        word_groups: liste des groupes de mots
        filter_words: liste des mots de filtrage (peut être une liste de chaînes ou de dictionnaires)
        global_filters: liste des mots de filtrage global

    Returns:
        s'il y a correspondance
    """
    # Vérification de type défensive : on s'assure que title est une chaîne valide
    if not isinstance(title, str):
        title = str(title) if title is not None else ""
    if not title.strip():
        return False

    title_lower = title.lower()

    # Vérification du filtrage global (priorité la plus élevée)
    if global_filters:
        if any(global_word.lower() in title_lower for global_word in global_filters):
            return False

    # Si aucun groupe de mots n'est configuré, tous les titres correspondent (permet d'afficher toutes les actualités)
    if not word_groups:
        return True

    # Vérification des mots de filtrage (compatible avec l'ancien et le nouveau format)
    for filter_item in filter_words:
        if _word_matches(filter_item, title_lower):
            return False

    # Vérification de la correspondance avec les groupes de mots
    for group in word_groups:
        required_words = group["required"]
        normal_words = group["normal"]

        # Vérification des mots obligatoires
        if required_words:
            all_required_present = all(
                _word_matches(req_item, title_lower) for req_item in required_words
            )
            if not all_required_present:
                continue

        # Vérification des mots ordinaires
        if normal_words:
            any_normal_present = any(
                _word_matches(normal_item, title_lower) for normal_item in normal_words
            )
            if not any_normal_present:
                continue

        return True

    return False
