# coding=utf-8
"""
Module client IA

Interface unifiée vers les modèles d'IA, basée sur LiteLLM.
Prend en charge plus de 100 fournisseurs d'IA (OpenAI, DeepSeek, Gemini, Claude,
modèles nationaux chinois, etc.).
"""

import os
from typing import Any, Dict, List

from litellm import completion


class AIClient:
    """Client IA unifié (basé sur LiteLLM)"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialise le client IA

        Args:
            config: dictionnaire de configuration de l'IA
                - MODEL: identifiant du modèle (format : provider/model_name)
                - API_KEY: clé d'API
                - API_BASE: URL de base de l'API (facultatif)
                - TEMPERATURE: température d'échantillonnage
                - MAX_TOKENS: nombre maximal de tokens générés
                - TIMEOUT: délai d'expiration de la requête (en secondes)
                - NUM_RETRIES: nombre de tentatives (facultatif)
                - FALLBACK_MODELS: liste des modèles de secours (facultatif)
        """
        self.model = config.get("MODEL", "deepseek/deepseek-chat")
        self.api_key = config.get("API_KEY") or os.environ.get("AI_API_KEY", "")
        self.api_base = config.get("API_BASE", "")
        self.temperature = config.get("TEMPERATURE", 1.0)
        self.max_tokens = config.get("MAX_TOKENS", 5000)
        self.timeout = config.get("TIMEOUT", 120)
        self.num_retries = config.get("NUM_RETRIES", 2)
        self.fallback_models = config.get("FALLBACK_MODELS", [])

    def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        Appelle le modèle d'IA pour engager une conversation

        Args:
            messages: liste de messages, au format [{"role": "system/user/assistant", "content": "..."}]
            **kwargs: paramètres supplémentaires, qui remplacent la configuration par défaut

        Returns:
            str: contenu de la réponse de l'IA

        Raises:
            Exception: levée en cas d'échec de l'appel à l'API
        """
        # Construction des paramètres de la requête
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "timeout": kwargs.get("timeout", self.timeout),
            "num_retries": kwargs.get("num_retries", self.num_retries),
        }

        # Ajout de la clé d'API
        if self.api_key:
            params["api_key"] = self.api_key

        # Ajout de l'URL de base de l'API (si configurée)
        if self.api_base:
            params["api_base"] = self.api_base

        # Ajout de max_tokens (si configuré et différent de 0)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        if max_tokens and max_tokens > 0:
            params["max_tokens"] = max_tokens

        # Ajout des modèles de secours (si configurés)
        if self.fallback_models:
            params["fallbacks"] = self.fallback_models

        # Fusion des autres paramètres supplémentaires
        for key, value in kwargs.items():
            if key not in params:
                params[key] = value

        # Appel de LiteLLM
        response = completion(**params)

        # Extraction du contenu de la réponse
        # Certains modèles ou fournisseurs renvoient une liste (blocs de contenu) plutôt qu'une chaîne ; on convertit le tout en chaîne
        content = response.choices[0].message.content
        if isinstance(content, list):
            content = "\n".join(
                item.get("text", str(item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        return content or ""

    def validate_config(self) -> tuple[bool, str]:
        """
        Vérifie la validité de la configuration

        Returns:
            tuple: (validité, message d'erreur)
        """
        if not self.model:
            return False, "Aucun modèle d'IA configuré (model)"

        if not self.api_key:
            return False, "Aucune clé d'API IA configurée ; veuillez la définir dans config.yaml ou via la variable d'environnement AI_API_KEY"

        # Vérification du format du modèle (il doit contenir provider/model)
        if "/" not in self.model:
            return False, f"Format de modèle incorrect : {self.model} ; le format attendu est 'provider/model' (par exemple 'deepseek/deepseek-chat')"

        return True, ""
