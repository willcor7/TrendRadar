# Halal Niche Radar

> Plateforme de **veille bilingue (FR / EN)** dédiée au marché halal : suivi des tendances
> et détection d'opportunités de niche, de la collecte des sources jusqu'aux rapports et
> notifications, le tout enrichi par l'IA.

[![Licence](https://img.shields.io/badge/licence-GPL--3.0-blue.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![RSS](https://img.shields.io/badge/RSS-Atom-orange.svg?style=flat-square&logo=rss&logoColor=white)](#fonctionnalites)
[![IA](https://img.shields.io/badge/IA-Filtrage_%26_Analyse-9B59B6?style=flat-square)](#fonctionnalites)
[![Docker](https://img.shields.io/badge/Docker-Déploiement-2496ED?style=flat-square&logo=docker&logoColor=white)](#deploiement)
[![MCP](https://img.shields.io/badge/MCP-Serveur_d'analyse-FF6B6B?style=flat-square)](#serveur-mcp)

---

## Projet dérivé — attribution

Ce dépôt est un **fork** (œuvre dérivée) de
**[TrendRadar](https://github.com/sansan0/TrendRadar)**, créé par **sansan0**, distribué sous
licence **GPL-3.0**. Le code amont a été re-ciblé et traduit en français pour servir une
application de veille spécialisée dans le marché halal.

Conformément à la GPL-3.0, ce fork reste sous la **même licence GPL-3.0**. Tous les crédits
pour l'architecture d'origine reviennent à l'auteur initial. Voir les sections
[Licence](#licence) et [Crédits](#credits).

---

## Objectif

Le marché halal est mondial, fragmenté et en croissance rapide, mais l'information utile y est
dispersée entre médias spécialisés, organismes de certification, presse économique et réseaux
professionnels. **Halal Niche Radar** centralise cette information, la filtre selon vos centres
d'intérêt, puis la restitue dans deux langues (français et anglais).

Domaines de niche couverts :

- Agroalimentaire halal
- Finance islamique
- Mode modeste (modest fashion)
- Cosmétiques halal
- Voyage et tourisme halal
- Certification et normes
- Logistique et chaîne d'approvisionnement
- Tech et médias

L'application aide à répondre à deux questions : *« que se passe-t-il en ce moment ? »* et
*« où sont les opportunités émergentes ? »*

---

## Fonctionnalités

- **Collecte multi-sources** — agrégation de palmarès (plateformes de tendances) et de sources
  RSS / Atom. Chaque source se configure dans `config/config.yaml` ; aucune source n'est codée
  en dur.
- **Filtrage IA** — décrivez vos intérêts en langage naturel ; l'IA en extrait des étiquettes,
  note chaque titre et ne retient que ce qui est réellement pertinent. Repli automatique sur le
  filtrage par mots-clés en cas d'erreur, pour ne jamais interrompre la veille.
- **Filtrage par mots-clés** — alternative déterministe, sans coût de tokens, via des groupes de
  mots-clés (mots requis, mots d'exclusion, expressions régulières, alias d'affichage).
- **Traduction et analyse IA** — traduction des contenus vers la langue cible et synthèses IA
  (tendances de fond, signaux faibles, controverses, perspectives stratégiques). Compatible avec
  de nombreux fournisseurs via LiteLLM.
- **Notifications** — envoi vers **Telegram**, **e-mail (SMTP)**, et d'autres canaux
  (webhooks génériques compatibles Discord / IFTTT, etc.). Multi-comptes pris en charge.
- **Rapports HTML bilingues FR + EN** — un rapport web autonome, adaptatif (mode sombre,
  recherche, navigation par onglets), généré localement et exploitable hors ligne.
- **Éditeur de configuration web bilingue** — interface graphique pour modifier la configuration
  sans éditer le YAML à la main.
- **Serveur MCP** — expose les données de veille à un assistant IA (Model Context Protocol) pour
  l'exploration conversationnelle (recherche, agrégation, comparaison de périodes, lecture
  d'articles).
- **Planification** — plages horaires configurables par jour de la semaine, avec stratégie de
  filtrage et mode de rapport propres à chaque plage horaire.

---

## Architecture

```
trendradar/        Application principale (collecte, filtrage, rapports, notifications)
  crawler/         Collecte des palmarès et des sources RSS
  ai/              Filtrage, traduction et analyse IA
  report/          Génération des rapports HTML
  notification/    Envoi multi-canal (Telegram, e-mail, webhooks…)
  storage/         Stockage local (SQLite) ou distant (S3-compatible)
mcp_server/        Serveur MCP d'analyse pour assistants IA
config/            Fichiers de configuration (voir ci-dessous)
docker/            Dockerfile, docker-compose, scripts de déploiement
```

---

## Installation

Prérequis : **Python 3.12+**.

Avec [uv](https://github.com/astral-sh/uv) (recommandé) :

```bash
uv sync
```

Avec pip :

```bash
pip install -r requirements.txt
```

---

## Configuration

La configuration vit dans le dossier `config/` :

| Fichier | Rôle |
| --- | --- |
| `config/config.yaml` | Configuration principale : sources, filtrage, IA, notifications, stockage, planification |
| `config/frequency_words.txt` | Groupes de mots-clés (filtrage déterministe) |
| `config/ai_interests.txt` | Description en langage naturel de vos intérêts (filtrage IA) |
| `config/ai_analysis_prompt.txt` | Modèle de prompt pour l'analyse IA |
| `config/ai_translation_prompt.txt` | Modèle de prompt pour la traduction IA |
| `config/timeline.yaml` | Plages horaires de la planification |

### Sources

- **Palmarès / plateformes de tendances** : section `platforms` de `config/config.yaml`. Chaque
  source possède un `id`, un `name` et un `expected_domain` optionnel (validation de domaine).
- **Sources RSS** : section `rss`. Chaque flux possède un `id`, un `name` et une `url`. Renseignez
  les flux pertinents pour votre veille (médias spécialisés, certification, finance islamique,
  etc.) — aucune URL n'est imposée par défaut.

### Filtre IA

Réglez `filter.method` sur `ai` puis décrivez vos centres d'intérêt dans
`config/ai_interests.txt`. Ajustez le seuil de pertinence via `ai_filter.min_score`.

### Secrets (variables d'environnement)

Ne placez **jamais** de secret dans un fichier versionné. Utilisez des variables
d'environnement :

| Variable | Usage |
| --- | --- |
| `AI_API_KEY` | Clé API du fournisseur IA (ex. OpenRouter) |
| `AI_MODEL` | Modèle au format LiteLLM `fournisseur/modèle` |
| `AI_API_BASE` | Point de terminaison personnalisé (optionnel) |
| `TELEGRAM_BOT_TOKEN` | Jeton du bot Telegram |
| `TELEGRAM_CHAT_ID` | Identifiant de conversation Telegram |
| `EMAIL_FROM` | Adresse d'expédition |
| `EMAIL_PASSWORD` | Mot de passe ou code d'application SMTP |
| `EMAIL_TO` | Destinataires (séparés par des virgules) |
| `EMAIL_SMTP_SERVER` / `EMAIL_SMTP_PORT` | Serveur / port SMTP (optionnels, autodétectés) |

Pour utiliser **OpenRouter**, renseignez `AI_API_KEY` avec votre clé OpenRouter et indiquez un
modèle au format LiteLLM (par exemple `openrouter/<fournisseur>/<modèle>`). La configuration du
modèle IA est partagée entre le filtrage, la traduction et l'analyse.

---

## Exécution

```bash
python -m trendradar
```

Le rapport HTML généré est exploitable directement dans un navigateur. Les notifications sont
envoyées selon les canaux activés dans `config/config.yaml`.

---

## Serveur MCP

Le serveur MCP expose les données de veille à un assistant IA compatible Model Context Protocol
(recherche, agrégation inter-sources, comparaison de périodes, lecture d'articles). Démarrage :

```bash
trendradar-mcp
```

---

## Déploiement

- **Docker** — un `Dockerfile`, un `docker-compose.yml` et un fichier `.env` d'exemple sont
  fournis dans `docker/`. Le mode `cron` exécute la veille à intervalle régulier et sert le
  rapport via un serveur web intégré.
- **GitHub Actions** — automatisation planifiée dans le cloud, avec stockage local ou distant
  (compatible S3 : R2 / OSS / COS, etc.).
- **Local** — exécution directe avec Python 3.12+.

Renseignez les secrets via les variables d'environnement (ou les *secrets* GitHub Actions),
jamais dans les fichiers de configuration versionnés.

---

## Licence

Distribué sous licence **GNU GPL-3.0**, comme le projet d'origine. Voir le fichier
[LICENSE](LICENSE).

En tant qu'œuvre dérivée d'un projet GPL-3.0, ce fork conserve la même licence. Toute
redistribution doit préserver cette licence et l'attribution.

## Crédits

- Projet d'origine : **[TrendRadar](https://github.com/sansan0/TrendRadar)** par **sansan0**
  (licence GPL-3.0).
- Données de palmarès : projet open source **[newsnow](https://github.com/ourongxing/newsnow)**.
- Interface IA unifiée : **[LiteLLM](https://github.com/BerriAI/litellm)**.

Merci aux auteurs et contributeurs de ces projets, sans lesquels ce fork n'existerait pas.
