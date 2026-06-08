"""
Outils de gestion de la configuration

Implémente les fonctions de requête et de gestion de la configuration.
"""

from typing import Dict, Optional, Any, TypedDict

from ..services.data_service import DataService
from ..utils.validators import validate_config_section
from ..utils.errors import MCPError


class ErrorInfo(TypedDict, total=False):
    """Structure des informations d'erreur"""
    code: str
    message: str
    suggestion: str


class ConfigResult(TypedDict):
    """Résultat de la requête de configuration - le champ success est obligatoire, les autres facultatifs"""
    success: bool
    config: Optional[Dict[str, Any]]
    section: Optional[str]
    error: Optional[ErrorInfo]


class ConfigManagementTools:
    """Classe des outils de gestion de la configuration"""

    def __init__(self, project_root: str = None):
        """
        Initialise les outils de gestion de la configuration

        Args:
            project_root: répertoire racine du projet
        """
        self.data_service = DataService(project_root)

    def get_current_config(self, section: Optional[str] = None) -> ConfigResult:
        """
        Récupère la configuration actuelle du système

        Args:
            section: section de configuration - all/crawler/push/keywords/weights, all par défaut

        Returns:
            dictionnaire de configuration

        Example:
            >>> tools = ConfigManagementTools()
            >>> result = tools.get_current_config(section="crawler")
            >>> print(result['crawler']['platforms'])
        """
        try:
            # Validation des paramètres
            section = validate_config_section(section)

            # Récupère la configuration
            config = self.data_service.get_current_config(section=section)

            return ConfigResult(
                success=True,
                config=config,
                section=section,
                error=None
            )

        except MCPError as e:
            return ConfigResult(
                success=False,
                config=None,
                section=None,
                error=e.to_dict()
            )
        except Exception as e:
            return ConfigResult(
                success=False,
                config=None,
                section=None,
                error={"code": "INTERNAL_ERROR", "message": str(e), "suggestion": "Veuillez consulter les journaux du service pour plus de détails"}
            )
