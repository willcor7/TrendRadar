@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ==========================================
echo   TrendRadar MCP - Installation (Windows)
echo ==========================================
echo.

REM Correctif : utiliser le répertoire du script, et non le répertoire de travail courant
set "PROJECT_ROOT=%~dp0"
REM Supprimer la barre oblique inverse finale
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

echo 📍 Répertoire du projet : %PROJECT_ROOT%
echo.

REM Se placer dans le répertoire du projet
cd /d "%PROJECT_ROOT%"
if %errorlevel% neq 0 (
    echo ❌ Impossible d'accéder au répertoire du projet
    pause
    exit /b 1
)

REM Vérifier la structure du projet
echo [0/4] 🔍 Vérification de la structure du projet...
if not exist "pyproject.toml" (
    echo ❌ Fichier pyproject.toml introuvable : %PROJECT_ROOT%
    echo.
    echo Veuillez vérifier :
    echo   1. setup-windows.bat est-il bien à la racine du projet ?
    echo   2. Les fichiers du projet sont-ils complets ?
    echo.
    echo Contenu du répertoire courant :
    dir /b
    echo.
    pause
    exit /b 1
)
echo ✅ pyproject.toml trouvé
echo.

REM Vérifier Python
echo [1/4] 🐍 Vérification de Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python non détecté, veuillez d'abord installer Python 3.10+
    echo Lien de téléchargement : https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo ✅ %%i
echo.

REM Vérifier UV
echo [2/4] 🔧 Vérification d'UV...
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo UV n'est pas installé, installation automatique en cours...
    echo.

    echo Tentative méthode 1 : installation via PowerShell...
    powershell -ExecutionPolicy Bypass -Command "try { irm https://astral.sh/uv/install.ps1 | iex; exit 0 } catch { Write-Host 'Installation via PowerShell echouee'; exit 1 }"

    if %errorlevel% neq 0 (
        echo.
        echo Échec de la méthode 1, tentative méthode 2 : installation via pip...
        python -m pip install --upgrade uv

        if %errorlevel% neq 0 (
            echo.
            echo ❌ Échec de l'installation automatique
            echo.
            echo Veuillez installer UV manuellement, méthodes possibles :
            echo.
            echo   Méthode 1 - pip :
            echo     python -m pip install uv
            echo.
            echo   Méthode 2 - pipx :
            echo     pip install pipx
            echo     pipx install uv
            echo.
            echo   Méthode 3 - téléchargement manuel :
            echo     Rendez-vous sur : https://docs.astral.sh/uv/getting-started/installation/
            echo.
            pause
            exit /b 1
        )
    )

    echo.
    echo ✅ Installation d'UV terminée !
    echo.
    echo ⚠️  Important : veuillez suivre les étapes ci-dessous :
    echo   1. Fermez cette fenêtre
    echo   2. Rouvrez l'invite de commandes (ou PowerShell)
    echo   3. Revenez dans le répertoire du projet : %PROJECT_ROOT%
    echo   4. Relancez ce script : setup-windows.bat
    echo.
    pause
    exit /b 0
) else (
    for /f "tokens=*" %%i in ('uv --version') do echo ✅ %%i
)
echo.

echo [3/4] 📦 Installation des dépendances du projet...
echo Répertoire de travail : %PROJECT_ROOT%
echo.

REM S'assurer de l'exécution dans le répertoire du projet
cd /d "%PROJECT_ROOT%"
uv sync
if %errorlevel% neq 0 (
    echo.
    echo ❌ Échec de l'installation des dépendances
    echo.
    echo Causes possibles :
    echo   1. Problème de connexion réseau
    echo   2. Version de Python incompatible (^>= 3.10 requise)
    echo   3. Erreur de format du fichier pyproject.toml
    echo.
    echo Dépannage :
    echo   - Vérifiez la connexion réseau
    echo   - Vérifiez la version de Python : python --version
    echo   - Essayez la sortie détaillée : uv sync --verbose
    echo.
    echo Répertoire du projet : %PROJECT_ROOT%
    echo.
    pause
    exit /b 1
)
echo.
echo ✅ Installation des dépendances réussie
echo.

echo [4/4] ⚙️  Vérification du fichier de configuration...
if not exist "config\config.yaml" (
    echo ⚠️  Le fichier de configuration n'existe pas : config\config.yaml
    if exist "config\config.example.yaml" (
        echo.
        echo Créer le fichier de configuration :
        echo   1. Copier : copy config\config.example.yaml config\config.yaml
        echo   2. Éditer : notepad config\config.yaml
        echo   3. Renseigner la clé API
    )
    echo.
) else (
    echo ✅ config\config.yaml existe déjà
)
echo.

REM Récupérer le chemin d'UV
for /f "tokens=*" %%i in ('where uv 2^>nul') do set "UV_PATH=%%i"
if not defined UV_PATH (
    set "UV_PATH=uv"
)

echo.
echo ==========================================
echo          Installation terminée !
echo ==========================================
echo.
echo 📋 Informations de configuration du serveur MCP (pour Claude Desktop) :
echo.
echo   Commande : %UV_PATH%
echo   Répertoire de travail : %PROJECT_ROOT%
echo.
echo   Arguments (à renseigner ligne par ligne) :
echo     --directory
echo     %PROJECT_ROOT%
echo     run
echo     python
echo     -m
echo     mcp_server.server
echo.
echo 📖 Tutoriel détaillé : README-Cherry-Studio.md
echo.
echo.
pause