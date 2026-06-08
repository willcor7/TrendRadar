#!/bin/bash
set -e

# Vérifier les fichiers de configuration
if [ ! -f "/app/config/config.yaml" ] || [ ! -f "/app/config/frequency_words.txt" ]; then
    echo "❌ Fichiers de configuration manquants"
    exit 1
fi

case "${RUN_MODE:-cron}" in
"once")
    echo "🔄 Exécution unique"
    exec python -m trendradar
    ;;
"cron")
    # Valider le format de CRON_SCHEDULE (seuls les caractères valides d'une expression cron sont autorisés)
    CRON_EXPR="${CRON_SCHEDULE:-*/30 * * * *}"
    if ! echo "$CRON_EXPR" | grep -qE '^[0-9*/,[:space:]-]+$'; then
        echo "❌ Format de CRON_SCHEDULE invalide : $CRON_EXPR"
        exit 1
    fi

    # Générer le crontab
    echo "$CRON_EXPR cd /app && python -m trendradar" > /tmp/crontab

    echo "📅 Contenu du crontab généré :"
    cat /tmp/crontab

    if ! /usr/local/bin/supercronic -test /tmp/crontab; then
        echo "❌ Échec de la validation du format du crontab"
        exit 1
    fi

    # Exécuter une fois immédiatement (si configuré)
    if [ "${IMMEDIATE_RUN:-false}" = "true" ]; then
        echo "▶️ Exécution immédiate unique"
        python -m trendradar
    fi

    # Démarrer le serveur web
    echo "🌐 Démarrage du serveur web..."
    python manage.py start_webserver

    echo "⏰ Démarrage de supercronic : $CRON_EXPR"
    echo "🎯 supercronic s'exécutera en tant que PID 1"

    exec /usr/local/bin/supercronic -passthrough-logs /tmp/crontab
    ;;
*)
    exec "$@"
    ;;
esac
