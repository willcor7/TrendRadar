#!/bin/bash

# Définition des couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}╔════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  TrendRadar MCP - Installation (Mac)   ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════╝${NC}"
echo ""

# Récupérer le répertoire racine du projet
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo -e "📍 Répertoire du projet : ${BLUE}${PROJECT_ROOT}${NC}"
echo ""

# Vérifier si UV est déjà installé
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}[1/3] 🔧 UV n'est pas installé, installation automatique en cours...${NC}"
    echo "Astuce : UV est un gestionnaire de paquets Python rapide, à installer une seule fois"
    echo ""
    curl -LsSf https://astral.sh/uv/install.sh | sh

    echo ""
    echo "Rafraîchissement de la variable d'environnement PATH..."
    echo ""

    # Ajouter UV au PATH
    export PATH="$HOME/.cargo/bin:$PATH"

    # Vérifier qu'UV est réellement disponible
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}❌ [Erreur] Échec de l'installation d'UV${NC}"
        echo ""
        echo "Causes possibles :"
        echo "  1. Problème de connexion réseau, impossible de télécharger le script d'installation"
        echo "  2. Permissions insuffisantes sur le chemin d'installation"
        echo "  3. Exécution anormale du script d'installation"
        echo ""
        echo "Solutions :"
        echo "  1. Vérifiez que la connexion réseau fonctionne"
        echo "  2. Installation manuelle : https://docs.astral.sh/uv/getting-started/installation/"
        echo "  3. Ou lancez : curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi

    echo -e "${GREEN}✅ [Succès] UV est installé${NC}"
    echo -e "${YELLOW}⚠️  Veuillez relancer ce script pour continuer${NC}"
    exit 0
else
    echo -e "${GREEN}[1/3] ✅ UV est installé${NC}"
    uv --version
fi

echo ""
echo "[2/3] 📦 Installation des dépendances du projet..."
echo "Astuce : cela peut prendre 1 à 2 minutes, merci de patienter"
echo ""

# Créer l'environnement virtuel et installer les dépendances
uv sync

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ [Erreur] Échec de l'installation des dépendances${NC}"
    echo "Veuillez vérifier la connexion réseau puis réessayer"
    exit 1
fi

echo ""
echo -e "${GREEN}[3/3] ✅ Vérification du fichier de configuration...${NC}"
echo ""

# Vérifier le fichier de configuration
if [ ! -f "config/config.yaml" ]; then
    echo -e "${YELLOW}⚠️  [Avertissement] Fichier de configuration introuvable : config/config.yaml${NC}"
    echo "Veuillez vous assurer que le fichier de configuration existe"
    echo ""
fi

# Ajouter les droits d'exécution
chmod +x start-http.sh 2>/dev/null || true

# Récupérer le chemin d'UV
UV_PATH=$(which uv)

echo ""
echo -e "${BOLD}╔════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║         Installation terminée !        ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════╝${NC}"
echo ""
echo "📋 Étape suivante :"
echo ""
echo "  1️⃣  Ouvrez Cherry Studio"
echo "  2️⃣  Allez dans Paramètres > MCP Servers > Ajouter un serveur"
echo "  3️⃣  Renseignez la configuration suivante :"
echo ""
echo "      Nom : TrendRadar"
echo "      Description : outil d'agrégation des actualités tendance"
echo "      Type : STDIO"
echo -e "      Commande : ${BLUE}${UV_PATH}${NC}"
echo "      Arguments (un par ligne) :"
echo -e "        ${BLUE}--directory${NC}"
echo -e "        ${BLUE}${PROJECT_ROOT}${NC}"
echo -e "        ${BLUE}run${NC}"
echo -e "        ${BLUE}python${NC}"
echo -e "        ${BLUE}-m${NC}"
echo -e "        ${BLUE}mcp_server.server${NC}"
echo ""
echo "  4️⃣  Enregistrez et activez l'interrupteur MCP"
echo ""
echo "📖 Tutoriel détaillé : README-Cherry-Studio.md ; ne fermez pas cette fenêtre, elle servira tout à l'heure pour renseigner les arguments"
echo ""
