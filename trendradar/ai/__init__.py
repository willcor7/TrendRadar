# coding=utf-8
"""
Module IA de TrendRadar

Fournit l'analyse approfondie et la traduction des actualités tendances
grâce aux grands modèles de langage (LLM).
"""

from .analyzer import AIAnalyzer, AIAnalysisResult
from .filter import AIFilter, AIFilterResult
from .translator import AITranslator, TranslationResult, BatchTranslationResult
from .formatter import (
    get_ai_analysis_renderer,
    render_ai_analysis_markdown,
    render_ai_analysis_feishu,
    render_ai_analysis_dingtalk,
    render_ai_analysis_html_rich,
    render_ai_analysis_plain,
)

__all__ = [
    # Analyseur
    "AIAnalyzer",
    "AIAnalysisResult",
    # Filtrage intelligent
    "AIFilter",
    "AIFilterResult",
    # Traducteur
    "AITranslator",
    "TranslationResult",
    "BatchTranslationResult",
    # Formatage
    "get_ai_analysis_renderer",
    "render_ai_analysis_markdown",
    "render_ai_analysis_feishu",
    "render_ai_analysis_dingtalk",
    "render_ai_analysis_html_rich",
    "render_ai_analysis_plain",
]
