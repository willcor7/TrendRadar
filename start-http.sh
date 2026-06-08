#!/bin/bash

echo "╔════════════════════════════════════════╗"
echo "║  TrendRadar MCP Server (mode HTTP)     ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Vérifier l'environnement virtuel
if [ ! -d ".venv" ]; then
    echo "❌ [Erreur] Environnement virtuel introuvable"
    echo "Veuillez d'abord lancer ./setup-mac.sh pour l'installation"
    echo ""
    exit 1
fi

echo "[Mode] HTTP (adapté à l'accès distant)"
echo "[Adresse] http://localhost:3333/mcp"
echo "[Astuce] Appuyez sur Ctrl+C pour arrêter le service"
echo ""

uv run python -m mcp_server.server --transport http --host 0.0.0.0 --port 3333
