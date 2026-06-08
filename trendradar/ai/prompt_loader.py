# coding=utf-8
"""
Outil de chargement des modèles de prompts

Charge depuis le répertoire de configuration les fichiers de prompts au format
[system] / [user], partagés par les modules analyzer, translator, filter, etc.
"""

from pathlib import Path
from typing import Tuple

# Répertoire racine config du projet
_CONFIG_ROOT = Path(__file__).parent.parent.parent / "config"


def load_prompt_template(
    prompt_file: str,
    config_subdir: str = "",
    label: str = "AI",
) -> Tuple[str, str]:
    """
    Charge un fichier de modèle de prompt et analyse les parties [system] et [user].

    Args:
        prompt_file: nom du fichier de prompt
        config_subdir: sous-répertoire dans config (par exemple "ai_filter") ; si vide, la recherche se fait directement dans config/
        label: étiquette de journal, utilisée pour l'affichage lorsque le fichier est manquant

    Returns:
        tuple (system_prompt, user_prompt_template)
    """
    config_dir = _CONFIG_ROOT / config_subdir if config_subdir else _CONFIG_ROOT
    prompt_path = config_dir / prompt_file

    if not prompt_path.exists():
        print(f"[{label}] Fichier de prompt introuvable : {prompt_path}")
        return "", ""

    content = prompt_path.read_text(encoding="utf-8")

    system_prompt = ""
    user_prompt = ""

    if "[system]" in content and "[user]" in content:
        parts = content.split("[user]")
        system_part = parts[0]
        user_part = parts[1] if len(parts) > 1 else ""

        if "[system]" in system_part:
            system_prompt = system_part.split("[system]")[1].strip()

        user_prompt = user_part.strip()
    else:
        user_prompt = content

    return system_prompt, user_prompt
