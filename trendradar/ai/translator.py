# coding=utf-8
"""
Module traducteur IA

Traduit le contenu diffusé dans plusieurs langues.
Basé sur l'interface unifiée de LiteLLM, il prend en charge plus de 100 fournisseurs d'IA.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from trendradar.ai.client import AIClient
from trendradar.ai.prompt_loader import load_prompt_template


@dataclass
class TranslationResult:
    """Résultat de traduction"""
    translated_text: str = ""       # Texte traduit
    original_text: str = ""         # Texte original
    success: bool = False           # Indique si la traduction a réussi
    error: str = ""                 # Message d'erreur


@dataclass
class BatchTranslationResult:
    """Résultat de traduction par lot"""
    results: List[TranslationResult] = field(default_factory=list)
    success_count: int = 0
    fail_count: int = 0
    total_count: int = 0
    prompt: str = ""                # debug : prompt complet envoyé à l'IA
    raw_response: str = ""          # debug : réponse brute de l'IA
    parsed_count: int = 0           # debug : nombre d'entrées extraites de la réponse de l'IA


class AITranslator:
    """Traducteur IA"""

    def __init__(self, translation_config: Dict[str, Any], ai_config: Dict[str, Any]):
        """
        Initialise le traducteur IA

        Args:
            translation_config: configuration de traduction IA (AI_TRANSLATION)
            ai_config: configuration du modèle d'IA (format LiteLLM)
        """
        self.translation_config = translation_config
        self.ai_config = ai_config

        # Configuration de la traduction
        self.enabled = translation_config.get("ENABLED", False)
        self.target_language = translation_config.get("LANGUAGE", "English")
        self.scope = translation_config.get("SCOPE", {"HOTLIST": True, "RSS": True, "STANDALONE": True})

        # Création du client IA (basé sur LiteLLM)
        self.client = AIClient(ai_config)

        # Chargement du modèle de prompt
        self.system_prompt, self.user_prompt_template = load_prompt_template(
            translation_config.get("PROMPT_FILE", "ai_translation_prompt.txt"),
            label="Traduction",
        )

    def translate(self, text: str) -> TranslationResult:
        """
        Traduit une seule entrée de texte

        Args:
            text: texte à traduire

        Returns:
            TranslationResult: résultat de la traduction
        """
        result = TranslationResult(original_text=text)

        if not self.enabled:
            result.error = "La fonction de traduction n'est pas activée"
            return result

        if not self.client.api_key:
            result.error = "Aucune clé d'API IA configurée"
            return result

        if not text or not text.strip():
            result.translated_text = text
            result.success = True
            return result

        try:
            # Construction du prompt
            user_prompt = self.user_prompt_template
            user_prompt = user_prompt.replace("{target_language}", self.target_language)
            user_prompt = user_prompt.replace("{content}", text)

            # Appel de l'API IA
            response = self._call_ai(user_prompt)
            result.translated_text = response.strip()
            result.success = True

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            result.error = f"Échec de la traduction ({error_type}) : {error_msg}"

        return result

    def translate_batch(self, texts: List[str]) -> BatchTranslationResult:
        """
        Traduit des textes par lot (un seul appel à l'API)

        Args:
            texts: liste des textes à traduire

        Returns:
            BatchTranslationResult: résultat de la traduction par lot
        """
        batch_result = BatchTranslationResult(total_count=len(texts))

        if not self.enabled:
            for text in texts:
                batch_result.results.append(TranslationResult(
                    original_text=text,
                    error="La fonction de traduction n'est pas activée"
                ))
            batch_result.fail_count = len(texts)
            return batch_result

        if not self.client.api_key:
            for text in texts:
                batch_result.results.append(TranslationResult(
                    original_text=text,
                    error="Aucune clé d'API IA configurée"
                ))
            batch_result.fail_count = len(texts)
            return batch_result

        if not texts:
            return batch_result

        # Filtrage des textes vides
        non_empty_indices = []
        non_empty_texts = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_indices.append(i)
                non_empty_texts.append(text)

        # Initialisation de la liste des résultats
        for text in texts:
            batch_result.results.append(TranslationResult(original_text=text))

        # Les textes vides sont directement marqués comme réussis
        for i, text in enumerate(texts):
            if not text or not text.strip():
                batch_result.results[i].translated_text = text
                batch_result.results[i].success = True
                batch_result.success_count += 1

        if not non_empty_texts:
            return batch_result

        try:
            # Construction du contenu à traduire par lot (avec un format numéroté)
            batch_content = self._format_batch_content(non_empty_texts)

            # Construction du prompt
            user_prompt = self.user_prompt_template
            user_prompt = user_prompt.replace("{target_language}", self.target_language)
            user_prompt = user_prompt.replace("{content}", batch_content)

            # Enregistrement des informations de debug (incluant le prompt system + user complet)
            if self.system_prompt:
                batch_result.prompt = f"[system]\n{self.system_prompt}\n\n[user]\n{user_prompt}"
            else:
                batch_result.prompt = user_prompt

            # Appel de l'API IA
            response = self._call_ai(user_prompt)

            # Enregistrement de la réponse brute de l'IA
            batch_result.raw_response = response

            # Analyse du résultat de la traduction par lot
            translated_texts, raw_parsed_count = self._parse_batch_response(response, len(non_empty_texts))
            batch_result.parsed_count = raw_parsed_count

            # Remplissage des résultats (on ignore les traductions vides afin de ne pas écraser le titre original par une chaîne vide)
            for idx, translated in zip(non_empty_indices, translated_texts):
                if translated and translated.strip():
                    batch_result.results[idx].translated_text = translated
                    batch_result.results[idx].success = True
                    batch_result.success_count += 1
                else:
                    batch_result.results[idx].translated_text = batch_result.results[idx].original_text
                    batch_result.results[idx].success = True
                    batch_result.success_count += 1

        except Exception as e:
            error_msg = f"Échec de la traduction par lot : {type(e).__name__}: {str(e)[:100]}"
            for idx in non_empty_indices:
                batch_result.results[idx].error = error_msg
            batch_result.fail_count = len(non_empty_indices)

        return batch_result

    def _format_batch_content(self, texts: List[str]) -> str:
        """Met en forme le contenu à traduire par lot"""
        lines = []
        for i, text in enumerate(texts, 1):
            lines.append(f"[{i}] {text}")
        return "\n".join(lines)

    def _parse_batch_response(self, response: str, expected_count: int) -> tuple:
        """
        Analyse la réponse de traduction par lot

        Args:
            response: texte de la réponse de l'IA
            expected_count: nombre de traductions attendu

        Returns:
            tuple: (liste des résultats de traduction, nombre d'entrées initialement extraites de la réponse de l'IA)
        """
        results = []
        lines = response.strip().split("\n")

        current_idx = None
        current_text = []

        for line in lines:
            # Tentative de correspondance avec le format [numéro]
            stripped = line.strip()
            if stripped.startswith("[") and "]" in stripped:
                bracket_end = stripped.index("]")
                try:
                    idx = int(stripped[1:bracket_end])
                    # Sauvegarde du contenu précédent
                    if current_idx is not None:
                        results.append((current_idx, "\n".join(current_text).strip()))
                    current_idx = idx
                    current_text = [stripped[bracket_end + 1:].strip()]
                except ValueError:
                    if current_idx is not None:
                        current_text.append(line)
            else:
                if current_idx is not None:
                    current_text.append(line)

        # Sauvegarde de la dernière entrée
        if current_idx is not None:
            results.append((current_idx, "\n".join(current_text).strip()))

        # Tri par index et extraction du texte
        results.sort(key=lambda x: x[0])
        translated = [text for _, text in results]
        raw_parsed_count = len(translated)

        # Si le nombre de résultats analysés ne correspond pas, on tente un simple découpage ligne par ligne
        if len(translated) != expected_count:
            # Solution de repli : découpage ligne par ligne (en retirant le numéro)
            translated = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("[") and "]" in stripped:
                    bracket_end = stripped.index("]")
                    translated.append(stripped[bracket_end + 1:].strip())
                elif stripped:
                    translated.append(stripped)
            raw_parsed_count = len(translated)

        # On garantit le retour du bon nombre d'éléments
        while len(translated) < expected_count:
            translated.append("")

        return translated[:expected_count], raw_parsed_count

    def _call_ai(self, user_prompt: str) -> str:
        """Appelle l'API IA (via LiteLLM)"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        return self.client.chat(messages)
