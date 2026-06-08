#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Outil de gestion du conteneur de collecte d'actualités - supercronic
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path
from datetime import datetime

# Configuration du serveur web
WEBSERVER_PORT = int(os.environ.get("WEBSERVER_PORT", "8080"))
WEBSERVER_DIR = "/app/output"
WEBSERVER_PID_FILE = "/tmp/webserver.pid"
def get_timestamp():
    """Récupère la chaîne d'horodatage actuelle"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_command(cmd, shell=True, capture_output=True):
    """Exécute une commande système"""
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=capture_output, text=True
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def manual_run():
    """Exécute manuellement le collecteur une fois"""
    print("🔄 Exécution manuelle du collecteur...")
    try:
        result = subprocess.run(
            ["python", "-m", "trendradar"], cwd="/app", capture_output=False, text=True
        )
        if result.returncode == 0:
            print("✅ Exécution terminée")
        else:
            print(f"❌ Échec de l'exécution, code de sortie : {result.returncode}")
    except Exception as e:
        print(f"❌ Erreur d'exécution : {e}")


def parse_cron_schedule(cron_expr):
    """Analyse une expression cron et renvoie une description lisible"""
    if not cron_expr or cron_expr == "Non défini":
        return "Non défini"
    
    try:
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return f"Expression brute : {cron_expr}"

        minute, hour, day, month, weekday = parts

        # Analyse des minutes
        if minute == "*":
            minute_desc = "chaque minute"
        elif minute.startswith("*/"):
            interval = minute[2:]
            minute_desc = f"toutes les {interval} minutes"
        elif "," in minute:
            minute_desc = f"à la minute {minute}"
        else:
            minute_desc = f"à la minute {minute}"

        # Analyse des heures
        if hour == "*":
            hour_desc = "chaque heure"
        elif hour.startswith("*/"):
            interval = hour[2:]
            hour_desc = f"toutes les {interval} heures"
        elif "," in hour:
            hour_desc = f"à {hour} h"
        else:
            hour_desc = f"à {hour} h"

        # Analyse du jour
        if day == "*":
            day_desc = "chaque jour"
        elif day.startswith("*/"):
            interval = day[2:]
            day_desc = f"tous les {interval} jours"
        else:
            day_desc = f"le {day} du mois"

        # Analyse du mois
        if month == "*":
            month_desc = "chaque mois"
        else:
            month_desc = f"au mois {month}"

        # Analyse du jour de la semaine
        weekday_names = {
            "0": "dimanche", "1": "lundi", "2": "mardi", "3": "mercredi",
            "4": "jeudi", "5": "vendredi", "6": "samedi", "7": "dimanche"
        }
        if weekday == "*":
            weekday_desc = ""
        else:
            weekday_desc = f"le {weekday_names.get(weekday, weekday)}"

        # Composition de la description
        if minute.startswith("*/") and hour == "*" and day == "*" and month == "*" and weekday == "*":
            # Schéma d'intervalle simple, par ex. */30 * * * *
            return f"exécution toutes les {minute[2:]} minutes"
        elif hour != "*" and minute != "*" and day == "*" and month == "*" and weekday == "*":
            # Heure précise chaque jour, par ex. 0 9 * * *
            return f"exécution chaque jour à {hour}:{minute.zfill(2)}"
        elif weekday != "*" and day == "*":
            # Heure précise chaque semaine
            return f"exécution {weekday_desc} à {hour}:{minute.zfill(2)}"
        else:
            # Schéma complexe, affichage des détails
            desc_parts = [part for part in [month_desc, day_desc, weekday_desc, hour_desc, minute_desc] if part and part != "chaque mois" and part != "chaque jour" and part != "chaque heure"]
            if desc_parts:
                return " ".join(desc_parts) + " : exécution"
            else:
                return f"Expression complexe : {cron_expr}"

    except Exception as e:
        return f"Échec de l'analyse : {cron_expr}"


def show_status():
    """Affiche l'état du conteneur"""
    print("📊 État du conteneur :")

    # Vérifier l'état du PID 1
    supercronic_is_pid1 = False
    pid1_cmdline = ""
    try:
        with open('/proc/1/cmdline', 'r') as f:
            pid1_cmdline = f.read().replace('\x00', ' ').strip()
        print(f"  🔍 Processus PID 1 : {pid1_cmdline}")

        if "supercronic" in pid1_cmdline.lower():
            print("  ✅ supercronic s'exécute correctement en tant que PID 1")
            supercronic_is_pid1 = True
        else:
            print("  ❌ Le PID 1 n'est pas supercronic")
            print(f"  📋 PID 1 réel : {pid1_cmdline}")
    except Exception as e:
        print(f"  ❌ Impossible de lire les informations du PID 1 : {e}")

    # Vérifier les variables d'environnement
    cron_schedule = os.environ.get("CRON_SCHEDULE", "Non défini")
    run_mode = os.environ.get("RUN_MODE", "Non défini")
    immediate_run = os.environ.get("IMMEDIATE_RUN", "Non défini")

    print(f"  ⚙️ Configuration d'exécution :")
    print(f"    CRON_SCHEDULE: {cron_schedule}")

    # Analyser et afficher la signification de l'expression cron
    cron_description = parse_cron_schedule(cron_schedule)
    print(f"    ⏰ Fréquence d'exécution : {cron_description}")

    print(f"    RUN_MODE: {run_mode}")
    print(f"    IMMEDIATE_RUN: {immediate_run}")

    # Vérifier les fichiers de configuration
    config_files = ["/app/config/config.yaml", "/app/config/frequency_words.txt"]
    print("  📁 Fichiers de configuration :")
    for file_path in config_files:
        if Path(file_path).exists():
            print(f"    ✅ {Path(file_path).name}")
        else:
            print(f"    ❌ {Path(file_path).name} manquant")

    # Vérifier les fichiers essentiels
    key_files = [
        ("/usr/local/bin/supercronic-linux-amd64", "binaire supercronic"),
        ("/usr/local/bin/supercronic", "lien symbolique supercronic"),
        ("/tmp/crontab", "fichier crontab"),
        ("/entrypoint.sh", "script de démarrage")
    ]

    print("  📂 Vérification des fichiers essentiels :")
    for file_path, description in key_files:
        if Path(file_path).exists():
            print(f"    ✅ {description} : présent")
            # Pour le fichier crontab, afficher le contenu
            if file_path == "/tmp/crontab":
                try:
                    with open(file_path, 'r') as f:
                        crontab_content = f.read().strip()
                        print(f"         Contenu : {crontab_content}")
                except:
                    pass
        else:
            print(f"    ❌ {description} : absent")

    # Vérifier la durée d'exécution du conteneur
    print("  ⏱️ Informations temporelles du conteneur :")
    try:
        # Vérifier l'heure de démarrage du PID 1
        with open('/proc/1/stat', 'r') as f:
            stat_content = f.read().strip().split()
            if len(stat_content) >= 22:
                # starttime est le 22e champ (index 21)
                starttime_ticks = int(stat_content[21])

                # Lire l'heure de démarrage du système
                with open('/proc/stat', 'r') as stat_f:
                    for line in stat_f:
                        if line.startswith('btime'):
                            boot_time = int(line.split()[1])
                            break
                    else:
                        boot_time = 0

                # Lire la fréquence de l'horloge système
                clock_ticks = os.sysconf(os.sysconf_names['SC_CLK_TCK'])

                if boot_time > 0:
                    pid1_start_time = boot_time + (starttime_ticks / clock_ticks)
                    current_time = time.time()
                    uptime_seconds = int(current_time - pid1_start_time)
                    uptime_minutes = uptime_seconds // 60
                    uptime_hours = uptime_minutes // 60

                    if uptime_hours > 0:
                        print(f"    Durée d'exécution du PID 1 : {uptime_hours} heures {uptime_minutes % 60} minutes")
                    else:
                        print(f"    Durée d'exécution du PID 1 : {uptime_minutes} minutes ({uptime_seconds} secondes)")
                else:
                    print(f"    Durée d'exécution du PID 1 : calcul précis impossible")
            else:
                print("    ❌ Impossible d'analyser les statistiques du PID 1")
    except Exception as e:
        print(f"    ❌ Échec de la vérification temporelle : {e}")

    # Récapitulatif de l'état et conseils
    print("  📊 Récapitulatif de l'état :")
    if supercronic_is_pid1:
        print("    ✅ supercronic s'exécute correctement en tant que PID 1")
        print("    ✅ La tâche planifiée devrait fonctionner normalement")

        # Afficher les informations de planification actuelles
        if cron_schedule != "Non défini":
            print(f"    ⏰ Planification actuelle : {cron_description}")

            # Fournir quelques conseils de planification courants
            if "minute" in cron_description and "toutes les 30 minutes" not in cron_description and "toutes les 60 minutes" not in cron_description:
                print("    💡 Mode d'exécution fréquente, adapté à la surveillance en temps réel")
            elif "heure" in cron_description:
                print("    💡 Mode d'exécution horaire, adapté aux synthèses régulières")
            elif "jour" in cron_description:
                print("    💡 Mode d'exécution quotidienne, adapté à la génération de rapports journaliers")

        print("    💡 Si la tâche planifiée ne s'exécute pas, vérifiez :")
        print("       • si le format du crontab est correct")
        print("       • si le fuseau horaire est correctement réglé")
        print("       • si l'application présente des erreurs")
    else:
        print("    ❌ État anormal de supercronic")
        if pid1_cmdline:
            print(f"    📋 PID 1 actuel : {pid1_cmdline}")
        print("    💡 Actions recommandées :")
        print("       • Redémarrer le conteneur : docker restart trendradar")
        print("       • Consulter les logs du conteneur : docker logs trendradar")

    # Afficher les conseils de vérification des logs
    print("  📋 Vérification de l'état d'exécution :")
    print("    • Consulter les logs complets du conteneur : docker logs trendradar")
    print("    • Consulter les logs en temps réel : docker logs -f trendradar")
    print("    • Tester par exécution manuelle : python manage.py run")
    print("    • Redémarrer le service du conteneur : docker restart trendradar")


def show_config():
    """Affiche la configuration actuelle"""
    print("⚙️ Configuration actuelle :")

    env_vars = [
        # Configuration d'exécution
        "CRON_SCHEDULE",
        "RUN_MODE",
        "IMMEDIATE_RUN",
        # Canaux de notification
        "FEISHU_WEBHOOK_URL",
        "DINGTALK_WEBHOOK_URL",
        "WEWORK_WEBHOOK_URL",
        "WEWORK_MSG_TYPE",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "NTFY_SERVER_URL",
        "NTFY_TOPIC",
        "NTFY_TOKEN",
        "BARK_URL",
        "SLACK_WEBHOOK_URL",
        # Configuration de l'analyse IA
        "AI_ANALYSIS_ENABLED",
        "AI_API_KEY",
        "AI_PROVIDER",
        "AI_MODEL",
        "AI_BASE_URL",
        # Configuration du stockage distant
        "S3_BUCKET_NAME",
        "S3_ACCESS_KEY_ID",
        "S3_ENDPOINT_URL",
        "S3_REGION",
    ]

    for var in env_vars:
        value = os.environ.get(var, "Non défini")
        # Masquer les informations sensibles
        if any(sensitive in var for sensitive in ["WEBHOOK", "TOKEN", "KEY", "SECRET"]):
            if value and value != "Non défini":
                masked_value = value[:10] + "***" if len(value) > 10 else "***"
                print(f"  {var}: {masked_value}")
            else:
                print(f"  {var}: {value}")
        else:
            print(f"  {var}: {value}")

    crontab_file = "/tmp/crontab"
    if Path(crontab_file).exists():
        print("  📅 Contenu du crontab :")
        try:
            with open(crontab_file, "r") as f:
                content = f.read().strip()
                print(f"    {content}")
        except Exception as e:
            print(f"    Échec de la lecture : {e}")
    else:
        print("  📅 Le fichier crontab n'existe pas")


def show_files():
    """Affiche les fichiers de sortie"""
    print("📁 Fichiers de sortie :")

    output_dir = Path("/app/output")
    if not output_dir.exists():
        print("  📭 Le répertoire de sortie n'existe pas")
        return

    # Nouvelle structure : répertoires à plat
    # - output/news/*.db
    # - output/rss/*.db
    # - output/txt/{date}/*.txt
    # - output/html/{date}/*.html

    # Vérifier la base de données news
    news_dir = output_dir / "news"
    if news_dir.exists():
        db_files = sorted(news_dir.glob("*.db"), key=lambda x: x.name, reverse=True)
        if db_files:
            print(f"  💾 Base de données des palmarès (news/) : {len(db_files)}")
            for db_file in db_files[:5]:
                mtime = time.ctime(db_file.stat().st_mtime)
                size_kb = db_file.stat().st_size // 1024
                print(f"    📀 {db_file.name} ({size_kb}KB, {mtime.split()[3][:5]})")
            if len(db_files) > 5:
                print(f"    ... et {len(db_files) - 5} de plus")

    # Vérifier la base de données RSS
    rss_dir = output_dir / "rss"
    if rss_dir.exists():
        db_files = sorted(rss_dir.glob("*.db"), key=lambda x: x.name, reverse=True)
        if db_files:
            print(f"  📰 Base de données RSS (rss/) : {len(db_files)}")
            for db_file in db_files[:5]:
                mtime = time.ctime(db_file.stat().st_mtime)
                size_kb = db_file.stat().st_size // 1024
                print(f"    📀 {db_file.name} ({size_kb}KB, {mtime.split()[3][:5]})")
            if len(db_files) > 5:
                print(f"    ... et {len(db_files) - 5} de plus")

    # Vérifier le répertoire des instantanés TXT
    txt_dir = output_dir / "txt"
    if txt_dir.exists():
        date_dirs = sorted([d for d in txt_dir.iterdir() if d.is_dir()], reverse=True)
        if date_dirs:
            print(f"  📄 Instantanés TXT (txt/) : {len(date_dirs)} jours")
            for date_dir in date_dirs[:3]:
                txt_files = list(date_dir.glob("*.txt"))
                if txt_files:
                    recent = sorted(txt_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                    mtime = time.ctime(recent.stat().st_mtime)
                    print(f"    📅 {date_dir.name} : {len(txt_files)} fichiers (le plus récent : {mtime.split()[3][:5]})")

    # Vérifier le répertoire des rapports HTML
    html_dir = output_dir / "html"
    if html_dir.exists():
        date_dirs = sorted([d for d in html_dir.iterdir() if d.is_dir()], reverse=True)
        if date_dirs:
            print(f"  🌐 Rapports HTML (html/) : {len(date_dirs)} jours")
            for date_dir in date_dirs[:3]:
                html_files = list(date_dir.glob("*.html"))
                if html_files:
                    recent = sorted(html_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                    mtime = time.ctime(recent.stat().st_mtime)
                    print(f"    📅 {date_dir.name} : {len(html_files)} fichiers (le plus récent : {mtime.split()[3][:5]})")


def show_logs():
    """Affiche les logs en temps réel"""
    print("📋 Logs en temps réel (appuyez sur Ctrl+C pour quitter) :")
    print("💡 Astuce : ceci affichera la sortie du processus PID 1")
    try:
        # Essayer plusieurs méthodes pour consulter les logs
        log_files = [
            "/proc/1/fd/1",  # sortie standard du PID 1
            "/proc/1/fd/2",  # erreur standard du PID 1
        ]

        for log_file in log_files:
            if Path(log_file).exists():
                print(f"📄 Tentative de lecture : {log_file}")
                subprocess.run(["tail", "-f", log_file], check=True)
                break
        else:
            print("📋 Impossible de trouver les fichiers de logs standard, utilisez plutôt : docker logs trendradar")

    except KeyboardInterrupt:
        print("\n👋 Sortie de la consultation des logs")
    except Exception as e:
        print(f"❌ Échec de la consultation des logs : {e}")
        print("💡 Utilisez plutôt : docker logs trendradar")


def restart_supercronic():
    """Redémarre le processus supercronic"""
    print("🔄 Redémarrage de supercronic...")
    print("⚠️ Attention : supercronic est le PID 1, il ne peut pas être redémarré directement")

    # Vérifier le PID 1 actuel
    try:
        with open('/proc/1/cmdline', 'r') as f:
            pid1_cmdline = f.read().replace('\x00', ' ').strip()
        print(f"  🔍 PID 1 actuel : {pid1_cmdline}")

        if "supercronic" in pid1_cmdline.lower():
            print("  ✅ Le PID 1 est supercronic")
            print("  💡 Pour redémarrer supercronic, il faut redémarrer tout le conteneur :")
            print("    docker restart trendradar")
        else:
            print("  ❌ Le PID 1 n'est pas supercronic, c'est un état anormal")
            print("  💡 Il est recommandé de redémarrer le conteneur pour corriger le problème :")
            print("    docker restart trendradar")
    except Exception as e:
        print(f"  ❌ Impossible de vérifier le PID 1 : {e}")
        print("  💡 Il est recommandé de redémarrer le conteneur : docker restart trendradar")


def _read_proc_cmdline(pid: int) -> str:
    """Lit la cmdline d'un processus, renvoie une chaîne vide en cas d'échec."""
    proc_cmdline = Path(f"/proc/{pid}/cmdline")
    if not proc_cmdline.exists():
        return ""
    try:
        with open(proc_cmdline, "rb") as f:
            return f.read().replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _is_expected_webserver_process(pid: int) -> bool:
    """Vérifie si le pid correspond au processus http.server du port actuel."""
    cmdline = _read_proc_cmdline(pid)
    if not cmdline:
        return False
    return "http.server" in cmdline and str(WEBSERVER_PORT) in cmdline


def _terminate_webserver_process(pid: int, require_expected: bool = True) -> bool:
    """Tente de terminer le processus du serveur web.

    Lorsque require_expected=True, ne termine que les processus confirmés comme étant http.server, pour éviter de tuer le mauvais processus.
    """
    try:
        os.kill(pid, 0)
    except OSError:
        return True

    if require_expected and not _is_expected_webserver_process(pid):
        print(f"  ⚠️ Le PID {pid} existe mais n'est pas le processus du serveur web, terminaison ignorée")
        return False

    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
            print(f"  ⚠️ Arrêt forcé du serveur web (PID : {pid})")
        except OSError:
            print(f"  ✅ Serveur web arrêté (PID : {pid})")
        return True
    except OSError:
        return True


def _is_webserver_running(pid: int) -> bool:
    """Vérifie si le processus du serveur web est réellement en cours d'exécution."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False

    if not _is_expected_webserver_process(pid):
        return False

    try:
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{WEBSERVER_PORT}/", method="HEAD")
        urllib.request.urlopen(req, timeout=3)
        return True
    except Exception:
        try:
            time.sleep(1)
            import urllib.request
            req = urllib.request.Request(f"http://127.0.0.1:{WEBSERVER_PORT}/", method="HEAD")
            urllib.request.urlopen(req, timeout=3)
            return True
        except Exception:
            return False


def _cleanup_stale_pid():
    """Nettoie le fichier PID obsolète"""
    if not Path(WEBSERVER_PID_FILE).exists():
        return False

    try:
        with open(WEBSERVER_PID_FILE, 'r') as f:
            old_pid = int(f.read().strip())
        os.remove(WEBSERVER_PID_FILE)
        print(f"  🧹 Nettoyage du fichier PID obsolète (PID : {old_pid})")
        return True
    except Exception:
        return False


def start_webserver():
    """Démarre le serveur web pour héberger le répertoire output"""
    print(f"🌐 Démarrage du serveur web (port : {WEBSERVER_PORT})...")
    print(f"  🔒 Note de sécurité : accès aux fichiers statiques uniquement, limité au répertoire {WEBSERVER_DIR}")

    # Vérifier s'il est déjà en cours d'exécution
    if Path(WEBSERVER_PID_FILE).exists():
        try:
            with open(WEBSERVER_PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())

            # Utiliser la vérification de processus renforcée
            if _is_webserver_running(old_pid):
                print(f"  ⚠️ Le serveur web est déjà en cours d'exécution (PID : {old_pid})")
                print(f"  💡 Accès : http://localhost:{WEBSERVER_PORT}")
                print("  💡 Arrêter le service : python manage.py stop_webserver")
                return

            # En cas de processus anormal, tenter d'abord de terminer l'ancien processus pour éviter qu'un port occupé fasse échouer le redémarrage
            _terminate_webserver_process(old_pid, require_expected=True)
            _cleanup_stale_pid()
            print(f"  ℹ️ Fichier PID obsolète détecté et nettoyé")

        except Exception as e:
            print(f"  ⚠️ Nettoyage de l'ancien fichier PID : {e}")
            _cleanup_stale_pid()

    # Vérifier si le répertoire existe
    if not Path(WEBSERVER_DIR).exists():
        print(f"  ❌ Le répertoire n'existe pas : {WEBSERVER_DIR}")
        return

    try:
        # Démarrer le serveur HTTP
        # Utiliser --bind pour se lier à 0.0.0.0 et rendre le serveur accessible depuis l'intérieur du conteneur
        # Le répertoire de travail est limité à WEBSERVER_DIR pour empêcher l'accès à d'autres répertoires
        process = subprocess.Popen(
            [sys.executable, '-m', 'http.server', str(WEBSERVER_PORT), '--bind', '0.0.0.0'],
            cwd=WEBSERVER_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        # Attendre un peu pour s'assurer que le serveur a démarré
        time.sleep(1)

        # Vérifier si le processus est toujours en cours d'exécution
        if process.poll() is None:
            # Enregistrer le PID
            with open(WEBSERVER_PID_FILE, 'w') as f:
                f.write(str(process.pid))
            print(f"  ✅ Serveur web démarré (PID : {process.pid})")
            print(f"  📁 Répertoire servi : {WEBSERVER_DIR} (lecture seule, fichiers statiques uniquement)")
            print(f"  🌐 Adresse d'accès : http://localhost:{WEBSERVER_PORT}")
            print(f"  📄 Page d'accueil : http://localhost:{WEBSERVER_PORT}/index.html")
            print("  💡 Arrêter le service : python manage.py stop_webserver")
        else:
            print(f"  ❌ Échec du démarrage du serveur web")
    except Exception as e:
        print(f"  ❌ Échec du démarrage : {e}")


def stop_webserver():
    """Arrête le serveur web"""
    print("🛑 Arrêt du serveur web...")

    if not Path(WEBSERVER_PID_FILE).exists():
        print("  ℹ️ Le serveur web n'est pas en cours d'exécution")
        return

    try:
        with open(WEBSERVER_PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        _terminate_webserver_process(pid, require_expected=True)
        if Path(WEBSERVER_PID_FILE).exists():
            os.remove(WEBSERVER_PID_FILE)
    except Exception as e:
        print(f"  ❌ Échec de l'arrêt : {e}")
        # Tenter de nettoyer le fichier PID
        try:
            os.remove(WEBSERVER_PID_FILE)
        except:
            pass


def webserver_status():
    """Affiche l'état du serveur web"""
    print("🌐 État du serveur web :")

    if not Path(WEBSERVER_PID_FILE).exists():
        print("  ⭕ Non démarré")
        print(f"  💡 Démarrer le service : python manage.py start_webserver")
        return

    try:
        with open(WEBSERVER_PID_FILE, 'r') as f:
            pid = int(f.read().strip())

        # Utiliser la vérification de processus renforcée
        if _is_webserver_running(pid):
            print(f"  ✅ En cours d'exécution (PID : {pid})")
            print(f"  📁 Répertoire servi : {WEBSERVER_DIR}")
            print(f"  🌐 Adresse d'accès : http://localhost:{WEBSERVER_PORT}")
            print(f"  📄 Page d'accueil : http://localhost:{WEBSERVER_PORT}/index.html")
            print("  💡 Arrêter le service : python manage.py stop_webserver")
        else:
            print(f"  ⭕ Non démarré (le fichier PID existe mais le processus est indisponible)")
            _cleanup_stale_pid()
            print("  💡 Démarrer le service : python manage.py start_webserver")
    except Exception as e:
        print(f"  ❌ Échec de la vérification de l'état : {e}")


def show_help():
    """Affiche les informations d'aide"""
    help_text = """
🐳 Outil de gestion du conteneur TrendRadar

📋 Liste des commandes :
  run              - Exécuter manuellement le collecteur une fois
  status           - Afficher l'état d'exécution du conteneur
  config           - Afficher la configuration actuelle
  files            - Afficher les fichiers de sortie
  logs             - Consulter les logs en temps réel
  restart          - Instructions de redémarrage
  start_webserver  - Démarrer le serveur web pour héberger le répertoire output
  stop_webserver   - Arrêter le serveur web
  webserver_status - Afficher l'état du serveur web
  help             - Afficher cette aide

📖 Exemples d'utilisation :
  # Exécuter dans le conteneur
  python manage.py run
  python manage.py status
  python manage.py logs
  python manage.py start_webserver

  # Exécuter depuis l'hôte
  docker exec -it trendradar python manage.py run
  docker exec -it trendradar python manage.py status
  docker exec -it trendradar python manage.py start_webserver
  docker logs trendradar

💡 Guide des opérations courantes :
  1. Vérifier l'état d'exécution : status
     - Vérifier si supercronic est bien le PID 1
     - Vérifier les fichiers de configuration et les fichiers essentiels
     - Consulter le réglage de la planification cron

  2. Test par exécution manuelle : run
     - Exécuter immédiatement une collecte d'actualités
     - Tester si le programme fonctionne correctement

  3. Consulter les logs : logs
     - Surveiller l'exécution en temps réel
     - Vous pouvez aussi utiliser : docker logs trendradar

  4. Redémarrer le service : restart
     - Comme supercronic est le PID 1, il faut redémarrer tout le conteneur
     - Utilisez : docker restart trendradar

  5. Gestion du serveur web :
     - Démarrer : start_webserver
     - Arrêter : stop_webserver
     - État : webserver_status
     - Accès : http://localhost:8080
"""
    print(help_text)


def main():
    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1]
    commands = {
        "run": manual_run,
        "status": show_status,
        "config": show_config,
        "files": show_files,
        "logs": show_logs,
        "restart": restart_supercronic,
        "start_webserver": start_webserver,
        "stop_webserver": stop_webserver,
        "webserver_status": webserver_status,
        "help": show_help,
    }

    if command in commands:
        try:
            commands[command]()
        except KeyboardInterrupt:
            print("\n👋 Opération annulée")
        except Exception as e:
            print(f"❌ Erreur d'exécution : {e}")
    else:
        print(f"❌ Commande inconnue : {command}")
        print("Lancez 'python manage.py help' pour voir les commandes disponibles")


if __name__ == "__main__":
    main()
