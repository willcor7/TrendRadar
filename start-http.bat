@echo off
chcp 65001 >nul

echo ============================================================
echo   TrendRadar MCP Server (mode HTTP)
echo ============================================================
echo.

REM Vérifier l'environnement virtuel
if not exist ".venv\Scripts\python.exe" (
    echo ❌ [Erreur] Environnement virtuel introuvable
    echo Veuillez d'abord lancer setup-windows.bat ou setup-windows-en.bat pour l'installation
    echo.
    pause
    exit /b 1
)

echo [Mode] HTTP (adapté à l'accès distant)
echo [Adresse] http://localhost:3333/mcp
echo [Astuce] Appuyez sur Ctrl+C pour arrêter le service
echo.

uv run python -m mcp_server.server --transport http --host 0.0.0.0 --port 3333

pause
