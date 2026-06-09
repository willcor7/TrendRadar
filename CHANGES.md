# CHANGES — Fork « Halal Niche Radar »

Ce dépôt est un **fork dérivé** de [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar),
sous licence **GPL-3.0** (licence et attribution de l'auteur original conservées — voir `LICENSE`).
Il transforme TrendRadar en une application **bilingue FR/EN** de **veille et de détection
d'opportunités de niche sur le marché halal** (agroalimentaire, finance islamique, mode modeste,
cosmétiques, voyage, certification/normes, logistique, tech & médias du consommateur musulman).

L'architecture, les fonctionnalités et les dépendances d'origine sont préservées. Les changements
se limitent à : localisation (+ bascule FR/EN), contenu de configuration/profil, textes des
prompts IA, et **une** petite adaptation de pipeline (voir §4).

---

## 1. Phase 0 — Fork & socle

- Branche de travail : `halal-niche-fr-en`.
- `.gitignore` ajouté (environnement `.venv/`, caches, sorties runtime `output/html|rss`,
  `output/index.html`, DB datées).
- Baseline de l'app d'origine validée avant modifications (crawl + RSS + rendu HTML).

## 2. Phase 1 — Localisation bilingue FR/EN

Aucun framework i18n lourd : catalogues légers + bascule.

- **Éditeur de configuration web** (`docs/`) : tout le texte traduit en **français (défaut)** ;
  nouveau `docs/assets/i18n.js` (catalogue FR→EN, namespace `TrendRadarI18N`) ; bascule **FR/EN**
  dans la barre de navigation (`#lang-switcher`), choix **persisté** dans
  `localStorage['trendradar_ui_lang']`, appliqué au chargement et au changement ; `<html lang>` et
  `<title>` dynamiques ; un `MutationObserver` localise le contenu généré dynamiquement.
- **Rapports HTML** : nouveau module `trendradar/i18n.py` (catalogue `LABELS = {fr, en}`,
  helpers `t()`, `ui_lang()`, `REPORT_LANGS`). `render_html_content` / `render_rss_html_content`
  prennent un paramètre `language`. Le générateur produit désormais **deux fichiers par rapport**
  (`…_fr.html` et `…_en.html`, + version par défaut FR aux chemins existants).
- **E-mail** : l'envoi joint **les deux** rapports FR + EN (MIMEMultipart « mixed », corps FR par
  défaut, tolère un fichier manquant).
- **Textes Python user-facing** (notifications, libellés, messages console/log) traduits en
  français ; le « chrome » des notifications/rapports passe par le catalogue i18n.
- **Serveur MCP** (`mcp_server/`), **infrastructure** (`.github/`, `docker/`, scripts `setup-*`,
  `start-http*`) et **commentaires/docstrings** : traduits en français.
- **README.md** réécrit en français (marque le projet comme dérivé). `README-EN.md` (anglais),
  `README-MCP-FAQ.md` / `README-MCP-FAQ-EN.md`, `README-Cherry-Studio.md` mis à jour/traduits.
- **Réglages** : `app.timezone: "Europe/Paris"` ; `ai_analysis.language` et
  `ai_translation.language` = `"Français"`. Le prompt de traduction
  (`config/ai_translation_prompt.txt`) gère explicitement le **contenu source arabe** (→ FR/EN).
- Toutes les clés de configuration et tous les placeholders de prompt sont préservés.

## 3. Phase 2 — Re-profilage « halal-niche »

- **`config/ai_interests.txt`** : profil priorisé (8 verticales), chaque verticale avec une
  double lentille **tendance** + **opportunité/niche** (demande non satisfaite, nouveaux entrants,
  ouvertures réglementaires) + exclusions de qualité de titre.
- **`config/frequency_words.txt`** : groupes de mots-clés halal en **FR + EN + translittérations
  arabes** (halal, tayyib, sukuk, takaful, zakat, hijab, abaya, umrah/hajj…) + `[GLOBAL_FILTER]`.
- **`config/ai_analysis_prompt.txt`** : re-tuné « intelligence de marché halal », avec deux
  livrables explicites (synthèse de tendances + détection d'opportunités). Placeholders et champs
  JSON (`core_trends`, `sentiment_controversy`, `signals`, `rss_insights`, `outlook_strategy`,
  `standalone_summaries`) intacts.
- **`config/config.yaml`** :
  - Palmarès chinois **désactivés** via `platforms.sources: []` (avec `platforms.enabled: true` —
    voir §4 ; sources d'origine conservées en commentaire « legacy »).
  - `filter.method: "ai"`.
  - Modèles **via OpenRouter** : `ai.model: "openrouter/anthropic/claude-sonnet-4"`,
    `ai.fallback_models: ["openrouter/deepseek/deepseek-v4-flash"]` (slugs confirmés sur l'API
    publique OpenRouter). Clé via `AI_API_KEY`.
  - `ai_analysis.include_rss: true` (analyse du contenu RSS).

### Sources RSS — vérifiées vs TODO

**Activées (HTTP 200 + items réels au moment de l'écriture)** : Salaam Gateway, Islamic Finance
Guru, The National (Golfe), Middle East Eye, Al Jazeera, MuslimMatters, About Islam, Saphirnews,
Al-Kanz, Oumma, Mizane.info.

**En TODO commenté (non vérifiées — à confirmer avant activation, jamais présentées comme
valides)** : Dinar Standard (404), Islamic Finance News (403), Arab News (403), Gulf News (404),
Vogue Arabia (400), Halal Times et Le Muslim Post (URL de flux à confirmer).

## 4. Adaptation de pipeline (déviation assumée du « no logic change »)

Le pipeline de rapport d'origine **exige des données de palmarès** : avec `platforms.sources: []`
(RSS seul), `_load_analysis_data` ne renvoyait aucune donnée et le mode `current` levait une
`RuntimeError` **avant** le rendu — rendant la configuration imposée non fonctionnelle.

**Changement minimal** (`trendradar/__main__.py`) : en mode `current`, lorsqu'**aucune plateforme
de palmarès n'est surveillée** (`current_platform_ids` vide = mode RSS seul), on génère le rapport
à partir des données actuelles (flux RSS) — comme le font déjà les modes `daily`/`incremental`.
Le contrôle de cohérence d'origine est **préservé** pour le cas normal avec palmarès. Validé par
dry-run (rapports FR+EN générés à partir de 11 flux RSS).

## 5. Configuration & secrets

Ne **jamais** mettre de secret dans `config.yaml`. Utiliser des variables d'environnement /
GitHub Secrets (elles surchargent `config.yaml`) :

> **Chargement `.env` (local)** : au démarrage, `trendradar/__main__.py::_load_dotenv()` charge
> automatiquement un fichier `.env` (répertoire courant puis racine du dépôt) dans
> `os.environ`, **sans écraser** les variables déjà définies. Copiez `.env.example` en `.env`,
> renseignez `AI_API_KEY`, etc. Le fichier `.env` est ignoré par git (`.gitignore`).
> Priorité : variables d'environnement réelles > `.env` > `config.yaml`.

| Variable | Usage |
|---|---|
| `AI_API_KEY` | Clé OpenRouter (filtrage / traduction / analyse IA) |
| `AI_MODEL`, `AI_API_BASE` | Surcharge modèle / endpoint (optionnel) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Canal Telegram |
| `EMAIL_FROM`, `EMAIL_PASSWORD`, `EMAIL_TO`, `EMAIL_SMTP_SERVER`, `EMAIL_SMTP_PORT` | Canal e-mail |
| `UI_LANG` | Langue par défaut des textes console Python (`fr` par défaut) |

**Sources** : ajouter/retirer des flux dans `config/config.yaml` → `rss.feeds` (vérifier que
l'URL renvoie un flux valide avant activation). Les palmarès se réactivent en remplissant
`platforms.sources`.

## 6. Exécution & déploiement

- Local : `uv sync` (ou `pip install -r requirements.txt`, Python 3.12+), puis
  `python -m trendradar`. Un run sans envoi : `notification.enabled: false` (ou canaux vides) +
  `storage.formats.html: true` → rapports dans `output/html/`.
- Docker + GitHub Actions : workflows fournis sous `.github/workflows/` ; mettre les secrets
  ci-dessus dans **GitHub Secrets**.

## 7. Vérifications effectuées

- `compileall` (trendradar + mcp_server + docker) : OK ; imports OK ; YAML (`config.yaml`,
  `timeline.yaml`) parsés.
- **Scan CJK** : 0 caractère chinois résiduel dans le code, la config, l'éditeur web, le serveur
  MCP, l'infra et la documentation (hors ponctuation CJK volontairement conservée dans des regex
  de traitement de texte de `mcp_server/`).
- **Dry-run** : 11 flux RSS récupérés (~194 entrées), rapports **FR + EN** générés sans erreur,
  console en français fluide. Le filtrage/analyse/traduction IA nécessite `AI_API_KEY` (sinon
  repli gracieux sur la correspondance par mots-clés).
- **Éditeur web** : bascule FR/EN fonctionnelle et persistée, français par défaut (vérifié au
  navigateur).
- **Dry-run IA complet (clé OpenRouter via `.env`)** : extraction des étiquettes halal,
  classification IA des RSS (≈140 → correspondances filtrées par score ≥ 0.7), **traduction des
  titres en français (8/8)**, section « Analyse IA » présente dans les rapports FR + EN, 0 CJK.

## 8. Modèle IA — décision finale

Les modèles **gratuits** OpenRouter se sont révélés **non fiables** pour ce pipeline multi-appels
(`nvidia/nemotron-3-ultra-550b-a55b:free` → timeout ; `meta-llama/llama-3.3-70b-instruct:free` →
429 rate-limited). Modèle retenu : **`openrouter/deepseek/deepseek-v4-flash`** (payant, rapide,
fiable, ~centimes par run), `fallback_models: []`. Modifiable dans `config/config.yaml`.
Robustesse en place : chargement `.env`, `litellm.drop_params=True`, extraction JSON équilibrée
tolérant les modèles de raisonnement.

## 8. Limitations & recommandations (non implémentées)

- **Modèle** : `claude-sonnet-4` est utilisé tel que demandé ; des variantes plus récentes
  existent sur OpenRouter (`anthropic/claude-sonnet-4.5`, `anthropic/claude-sonnet-4.6`) si l'on
  souhaite monter en gamme.
- **Flux non vérifiés** : confirmer les URL des flux en TODO avant de les activer.
- **Verticales sans flux RSS dédié vérifié** (mode modeste, cosmétiques, voyage) : couvertes via
  les flux halal généralistes (Salaam Gateway, Al-Kanz…) ; ajouter des flux dédiés est recommandé.
- **E-mail** : la double pièce jointe FR/EN est construite et testée hors réseau ; un envoi SMTP
  réel reste à valider avec des identifiants.
- **RSS-only** : la prise en charge native d'un mode « RSS sans palmarès » dans tout le pipeline
  (au-delà du correctif minimal du §4) serait une amélioration plus profonde, laissée en
  recommandation.

## Crédits

Projet original : **TrendRadar** par **sansan0** — https://github.com/sansan0/TrendRadar (GPL-3.0).
Ce fork conserve la licence GPL-3.0 et l'attribution.
