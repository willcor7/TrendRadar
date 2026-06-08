"""
Classes d'erreurs personnalisées

Définit tous les types d'exceptions personnalisées utilisés par le serveur MCP.
"""

from typing import Optional, List, Callable


# ==================== Chargement différé de la liste des plateformes prises en charge ====================

_get_supported_platforms: Optional[Callable[[], List[str]]] = None


def _load_supported_platforms() -> List[str]:
    """Charge de manière différée la liste des plateformes prises en charge"""
    global _get_supported_platforms
    if _get_supported_platforms is None:
        try:
            from .validators import get_supported_platforms
            _get_supported_platforms = get_supported_platforms
        except ImportError:
            # Repli : retourne une liste vide
            return []
    return _get_supported_platforms()


class MCPError(Exception):
    """Classe de base des erreurs des outils MCP"""

    def __init__(self, message: str, code: str = "MCP_ERROR", suggestion: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        """Convertit au format dictionnaire"""
        error_dict = {
            "code": self.code,
            "message": self.message
        }
        if self.suggestion:
            error_dict["suggestion"] = self.suggestion
        return error_dict


class DataNotFoundError(MCPError):
    """Erreur de données inexistantes"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="DATA_NOT_FOUND",
            suggestion=suggestion or "Veuillez vérifier la plage de dates ou attendre la fin de la tâche de collecte"
        )


class InvalidParameterError(MCPError):
    """Erreur de paramètre invalide"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="INVALID_PARAMETER",
            suggestion=suggestion or "Veuillez vérifier que le format des paramètres est correct"
        )


class ConfigurationError(MCPError):
    """Erreur de configuration"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            suggestion=suggestion or "Veuillez vérifier que le fichier de configuration est correct"
        )


class PlatformNotSupportedError(MCPError):
    """Erreur de plateforme non prise en charge"""

    def __init__(self, platform: str):
        supported = _load_supported_platforms()
        suggestion = f"Plateformes prises en charge : {', '.join(supported)}" if supported else "Veuillez vérifier la configuration des plateformes dans config/config.yaml"
        super().__init__(
            message=f"La plateforme '{platform}' n'est pas prise en charge",
            code="PLATFORM_NOT_SUPPORTED",
            suggestion=suggestion
        )


class CrawlTaskError(MCPError):
    """Erreur de tâche de collecte"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(
            message=message,
            code="CRAWL_TASK_ERROR",
            suggestion=suggestion or "Veuillez réessayer plus tard ou consulter les journaux"
        )


class FileParseError(MCPError):
    """Erreur d'analyse de fichier"""

    def __init__(self, file_path: str, reason: str):
        super().__init__(
            message=f"Échec de l'analyse du fichier {file_path} : {reason}",
            code="FILE_PARSE_ERROR",
            suggestion="Veuillez vérifier que le format du fichier est correct"
        )
