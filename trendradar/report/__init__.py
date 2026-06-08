# coding=utf-8
"""
Module de génération de rapports.

Fournit les fonctions de génération et de formatage des rapports, notamment :
- la génération de rapports HTML
- des outils de formatage des titres

Structure du module :
- helpers : fonctions auxiliaires du rapport (nettoyage, échappement, formatage)
- formatter : formatage des titres par plateforme
- html : rendu des rapports HTML
- generator : génération des rapports
"""

from trendradar.report.helpers import (
    clean_title,
    html_escape,
    format_rank_display,
)
from trendradar.report.formatter import format_title_for_platform
from trendradar.report.html import render_html_content
from trendradar.report.generator import (
    prepare_report_data,
    generate_html_report,
)

__all__ = [
    # fonctions auxiliaires
    "clean_title",
    "html_escape",
    "format_rank_display",
    # fonctions de formatage
    "format_title_for_platform",
    # rendu HTML
    "render_html_content",
    # génération des rapports
    "prepare_report_data",
    "generate_html_report",
]
