/**
 * Couche d'internationalisation (i18n) pour l'editeur de configuration TrendRadar.
 *
 * Le francais est la langue par defaut affichee directement dans le HTML/JS.
 * Ce module ajoute une couche ANGLAISE par-dessus, sans toucher au reste de la logique :
 *   - dictionnaire I18N : cle = texte FRANCAIS exact tel qu'affiche -> valeur = traduction ANGLAISE
 *   - lecture/ecriture de la langue dans localStorage (cle 'trendradar_ui_lang', defaut 'fr')
 *   - applyLang(lang) : parcourt le DOM (noeuds texte + attributs) et bascule FR <-> EN
 *   - WeakMap : memorise le texte FR d'origine de chaque noeud pour revenir au FR sans collision
 *   - quelques motifs templates (regex) : temps relatif, compteurs
 *   - MutationObserver : localise automatiquement les noeuds ajoutes dynamiquement (en mode EN)
 *   - selecteur de langue FR/EN injecte dans la barre de navigation
 *
 * NB : seul i18n.js contient la machinerie ; script.js n'est pas modifie (hormis l'inclusion du tag).
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'trendradar_ui_lang';
    var DEFAULT_LANG = 'fr';

    // ==========================================
    // Dictionnaire FR -> EN
    // Cle = texte FRANCAIS exact tel qu'affiche dans l'UI (statique ou genere par JS).
    // ==========================================
    var I18N = {
        // ---- Barre de navigation / titre ----
        "TrendRadar - Editeur de configuration": "TrendRadar - Configuration Editor",
        "Editeur de configuration visuel": "Visual configuration editor",
        "Page 100% statique : vos donnees restent dans votre navigateur local, en toute serenite":
            "Fully static page: your data stays in your local browser, with peace of mind",
        "Charger la derniere configuration officielle": "Load the latest official configuration",
        "Copier la configuration": "Copy configuration",
        // ---- Badges d'heure d'enregistrement ----
        "Enregistre : ": "Saved: ",
        "Non enregistre": "Not saved",
        // ---- Panneau de droite ----
        "Modules de configuration": "Configuration modules",
        "Verifier la version de config.yaml": "Check config.yaml version",
        "Verifier la version de frequency_words.txt": "Check frequency_words.txt version",
        "Verifier la version": "Check version",
        "Reinitialiser le contenu actuel a l'etat par defaut": "Reset the current content to its default state",
        // ---- Barre laterale de soutien ----
        "Soutenir le projet": "Support the project",
        "Si TrendRadar vous a deja apporte de la valeur, donnez-lui un coup de pouce pour l'aider a evoluer":
            "If TrendRadar has ever brought you value, give it a boost to help it keep evolving",
        "Mettre une etoile": "Give a Star",
        "Pour le faire decouvrir a plus de monde": "To help more people discover it",
        "Aller sur GitHub": "Go to GitHub",
        "Ne rien manquer": "Stay in the loop",
        "Recevoir les notifications de mise a jour": "Get update notifications",
        "Compte officiel WeChat": "WeChat official account",
        "Cliquer pour agrandir": "Click to enlarge",
        "Scannez pour suivre le compte officiel": "Scan to follow the official account",
        "Faire un don libre": "Donate freely",
        "Meme 1 yuan encourage": "Even 1 yuan is encouraging",
        "Paiement WeChat": "WeChat Pay",
        "Scannez avec WeChat - montant libre": "Scan with WeChat - any amount",
        "Decouvrir plus": "Explore more",
        "Un autre projet realise avec soin": "Another project crafted with care",
        "Aller voir": "Take a look",
        '"L\'open source demande des efforts, merci de votre soutien"':
            '"Open source takes effort, thank you for your support"',
        // ---- Fenetre RSS ----
        "Ajouter une source RSS": "Add an RSS source",
        "Modifier la source RSS": "Edit RSS source",
        "ID de la source (identifiant unique, en anglais)": "Source ID (unique identifier, in English)",
        "ex. : my-blog": "e.g.: my-blog",
        "Nom affiche": "Display name",
        "ex. : mon-blog": "e.g.: my-blog",
        "Age maximal des articles (jours, optionnel)": "Maximum article age (days, optional)",
        "Laisser vide pour utiliser le reglage global": "Leave empty to use the global setting",
        "Idees d'abonnements RSS et bibliotheque de references": "RSS subscription ideas & reference library",
        "(sources courantes incluses)": "(common sources included)",
        "Actualites Bing (tout mot-cle accepte)": "Bing News (any keyword accepted)",
        "Tech / programmation": "Tech / programming",
        "Actualites mondiales": "World news",
        "Intelligence artificielle": "Artificial intelligence",
        "Or / finance": "Gold / finance",
        "Cliquer pour remplir": "Click to fill",
        "💡 Astuce : modifiez le parametre ": "💡 Tip: change the ",
        " dans l'URL pour suivre n'importe quel sujet qui vous interesse.": " parameter in the URL to monitor any topic you are interested in.",
        "Plus de references de sources RSS": "More RSS source references",
        "Avertissement : les exemples RSS et outils tiers ci-dessus proviennent d'Internet ; le developpeur n'a pas verifie leur validite a long terme, merci de les controler avant usage.":
            "Disclaimer: the RSS examples and third-party tools above come from the Internet; the developer has not verified their long-term validity, please check them before use.",
        "Annuler": "Cancel",
        "Ajouter": "Add",
        // ---- Fenetre plateforme ----
        "Ajouter une plateforme de palmares": "Add a leaderboard platform",
        "Choisir un preset": "Choose a preset",
        "Saisie manuelle": "Manual input",
        "Toutes les plateformes predefinies sont deja ajoutees": "All preset platforms are already added",
        "Une plateforme personnalisee necessite la prise en charge du collecteur backend ; ce champ ne sert ici que de placeholder de configuration.":
            "A custom platform requires backend collector support; this field is only a configuration placeholder.",
        "Cle de plateforme (en anglais)": "Platform key (in English)",
        "ex. : sspai": "e.g.: sspai",
        "ex. : Sspai": "e.g.: Sspai",
        // ---- Fenetre type de groupe de mots ----
        "Choisir le type de groupe de mots": "Choose the word group type",
        "Groupe multi mots-cles (recommande)": "Multi-keyword group (recommended)",
        "Pour : regrouper plusieurs mots-cles, affiches sous un nom de groupe unique":
            "For: grouping several keywords, shown under a single group name",
        "Regex / mot-cle + alias": "Regex / keyword + alias",
        "Pour : faire correspondre plusieurs termes via regex, affiches sous un seul alias (separe par des lignes vides)":
            "For: matching several terms via regex, shown under a single alias (separated by blank lines)",
        "Groupe d'alias consecutifs": "Consecutive alias group",
        "Plusieurs marques / groupes de mots lies": "Several related brands / word groups",
        "Robot Zhiyuan": "Zhiyuan Robot",
        "Robot Zhongqing": "Zhongqing Robot",
        "Pour : regrouper plusieurs marques liees (": "For: grouping several related brands (",
        "sans ligne vide separatrice": "no blank line separator",
        "Groupe simple": "Simple group",
        "Mots-cles simples": "Simple keywords",
        "Pour : un seul ou quelques mots-cles ordinaires": "For: a single or a few ordinary keywords",
        "Asie de l'Est": "East Asia",
        "Japon": "Japan",
        "Coree": "Korea",
        "Coree du Nord": "North Korea",
        "Candidature olympique": "Olympic bid",
        // ---- Fenetres timeline ----
        "Nouveau mode de planification": "New scheduling mode",
        "Identifiant du mode (key)": "Mode identifier (key)",
        "Identifiant en anglais, ex. my_schedule": "Identifier in English, e.g. my_schedule",
        "Seuls lettres, chiffres et underscores sont acceptes ; ce sera la cle dans le YAML":
            "Only letters, digits and underscores are allowed; it will be the key in the YAML",
        "ex. : Ma planification": "e.g.: My schedule",
        "Description (optionnel)": "Description (optional)",
        "Breve description de l'usage de ce mode": "Short description of what this mode is for",
        "A partir d'un modele": "Based on a template",
        "Modele vierge (collecte seule, sans notification ni analyse)": "Blank template (collect only, no push, no analysis)",
        "Copie toute la configuration d'un mode existant comme point de depart":
            "Copies the entire configuration of an existing mode as a starting point",
        "Creer": "Create",
        "Ajouter une plage horaire": "Add a time period",
        "Identifiant de plage horaire (key)": "Time period identifier (key)",
        "Identifiant en anglais, ex. morning_push": "Identifier in English, e.g. morning_push",
        "Seuls lettres, chiffres et underscores sont acceptes": "Only letters, digits and underscores are allowed",
        "ex. : Notification du matin": "e.g.: Morning push",
        "Heure de debut": "Start time",
        "Heure de fin": "End time",
        "Si l'heure de debut est superieure a l'heure de fin (ex. 22:00 a 01:00), la plage est automatiquement consideree comme franchissant minuit.":
            "If the start time is later than the end time (e.g. 22:00 to 01:00), the period is automatically treated as crossing midnight.",

        // ---- MODULE_DEFS ----
        "1. Reglages de base": "1. Basic settings",
        "2. Source de donnees - Plateformes de palmares": "2. Data source - Leaderboard platforms",
        "3. Source de donnees - Abonnements RSS": "3. Data source - RSS subscriptions",
        "4. Mode de rapport": "4. Report mode",
        "4.5 Strategie de filtrage": "4.5 Filtering strategy",
        "4.6 Filtrage intelligent par IA": "4.6 AI smart filtering",
        "5. Controle du contenu des notifications": "5. Push content control",
        "6. Notifications": "6. Push notifications",
        "7. Configuration du stockage": "7. Storage configuration",
        "8. Configuration du modele IA": "8. AI model configuration",
        "9. Fonction d'analyse IA": "9. AI analysis feature",
        "10. Fonction de traduction IA": "10. AI translation feature",
        "11. Reglages avances": "11. Advanced settings",
        "Aller a l'editeur de gauche": "Jump to the left editor",
        "Lecture seule (editez a gauche)": "Read-only (edit on the left)",
        "Aller au module ": "Jump to module ",

        // ---- Controles des modules ----
        "Activer la collecte des palmares": "Enable leaderboard scraping",
        "Liste des plateformes": "Platform list",
        "(reordonnable par glisser-deposer)": "(drag to reorder)",
        "Ajouter une plateforme": "Add a platform",
        "Ajouter une autre plateforme": "Add another platform",
        "Activer la collecte RSS": "Enable RSS scraping",
        "Filtre de fraicheur": "Freshness filter",
        "Activer le filtre de fraicheur": "Enable freshness filter",
        "Age maximal des articles (jours)": "Maximum article age (days)",
        "Liste des sources RSS": "RSS source list",
        "(bibliotheque de references RSS incluse)": "(RSS reference library included)",
        "Attention : ": "Warning: ",
        "Certains medias etrangers peuvent aborder des sujets sensibles ; le modele IA peut refuser de les traduire ou de les analyser. Selectionnez vos abonnements selon vos besoins reels.":
            "Some foreign media may cover sensitive topics; the AI model may refuse to translate or analyze them. Select your subscriptions according to your actual needs.",
        "Mode de rapport": "Report mode",
        "Critere de regroupement": "Grouping dimension",
        "Trier selon l'ordre de definition": "Sort by definition order",
        "Seuil de surbrillance du classement": "Rank highlight threshold",
        "Nombre maximal d'elements affiches par mot-cle": "Maximum items shown per keyword",
        "Methode de filtrage": "Filtering method",
        "En mode IA, trier par priorite des etiquettes": "In AI mode, sort by tag priority",
        "Explication : ": "Explanation: ",
        "Nombre de titres par lot": "Titles per batch",
        "Intervalle entre lots (secondes)": "Batch interval (seconds)",
        "Seuil de score minimal (0 a 1)": "Minimum score threshold (0 to 1)",
        "Fichier de description des centres d'interet (optionnel)": "Interests description file (optional)",
        "Seuil de reclassement complet (0 a 1)": "Full reclassification threshold (0 to 1)",
        "Fichier de prompt de classification": "Classification prompt file",
        "Fichier de prompt d'extraction d'etiquettes": "Tag extraction prompt file",
        "Fichier de prompt de mise a jour d'etiquettes": "Tag update prompt file",
        "Astuce : l'ordre de la liste determine l'ordre d'affichage dans le rapport":
            "Tip: the list order determines the display order in the report",
        "Configuration de la zone autonome": "Standalone area configuration",
        "(l'affichage des notifications est controle par l'interrupteur ci-dessus, l'analyse IA est controlee independamment par l'interrupteur du module IA)":
            "(push display is controlled by the switch above, AI analysis is controlled independently by the AI module switch)",
        "Nombre maximal d'elements affiches par source": "Maximum items shown per source",
        "Choisir les plateformes de palmares a afficher": "Choose which leaderboard platforms to show",
        "Choisir les sources RSS a afficher": "Choose which RSS sources to show",
        "Nom du modele": "Model name",
        "URL de base de l'API (optionnel)": "API base URL (optional)",
        "Delai d'expiration des requetes (secondes)": "Request timeout (seconds)",
        "Temperature d'echantillonnage (0.0-2.0)": "Sampling temperature (0.0-2.0)",
        "Nombre maximal de tokens generes": "Maximum generated tokens",
        "Activer le rapport d'analyse IA": "Enable AI analysis report",
        "Autres reglages de l'analyse IA": "Other AI analysis settings",
        "Configuration du contenu de l'analyse": "Analysis content configuration",
        "Langue de sortie": "Output language",
        "Fichier de configuration du prompt": "Prompt configuration file",
        "Mode d'analyse IA": "AI analysis mode",
        "Nombre maximal d'elements analyses": "Maximum analyzed items",
        "Inclure le contenu RSS": "Include RSS content",
        "Inclure les donnees de la zone autonome": "Include standalone area data",
        "Transmettre la chronologie complete du classement": "Pass the full rank timeline",
        "Activer la traduction automatique par IA": "Enable AI automatic translation",
        "Langue cible": "Target language",
        "Non defini": "Not set",
        "Copie !": "Copied!",
        "Edition des mots de frequence": "Frequency word editing",
        "Planification temporelle": "Timeline scheduling",

        // ---- Editeur Frequency ----
        "Obligatoire": "Required",
        "Exclure": "Exclude",
        "Restreindre": "Restrict",
        "Regex": "Regex",
        "Alias": "Alias",
        "Glissez pour reordonner": "Drag to reorder",
        "Numero d'ordre du groupe": "Group order number",
        "Ce groupe est lie au groupe adjacent (sans ligne vide separatrice)":
            "This group is related to the adjacent group (no blank line separator)",
        "Groupe lie ": "Related group ",
        "Alias de groupe": "Group alias",
        "Alias de groupe (ex. : Asie de l'Est)": "Group alias (e.g.: East Asia)",
        "Liste des mots-cles :": "Keyword list:",
        "Saisissez un mot-cle puis appuyez sur Entree...": "Type a keyword then press Enter...",
        "Generer une regex par IA": "Generate regex with AI",
        "Alias unique": "Single alias",
        "/regex/ ou mot-cle": "/regex/ or keyword",
        "Exemple : /Pangdonglai|Yu Donglai/ => Pangdonglai": "Example: /Pangdonglai|Yu Donglai/ => Pangdonglai",
        "Liste des alias (sans ligne vide separatrice) :": "Alias list (no blank line separator):",
        "Ces lignes d'alias ne sont pas separees par des lignes vides dans le fichier et appartiennent au meme groupe":
            "These alias lines are not separated by blank lines in the file and belong to the same group",
        "Description des quatre types de groupes de mots": "Description of the four word group types",
        "Plusieurs mots-cles, affiches sous un nom de groupe unique": "Several keywords, shown under a single group name",
        "Correspondance par regex, affichee en alias": "Regex matching, shown as an alias",
        "Plusieurs alias sans ligne vide separatrice": "Several aliases without blank line separators",
        "Mots de filtrage global": "Global filter words",
        "Saisissez un mot de filtrage puis appuyez sur Entree...": "Type a filter word then press Enter...",
        "Astuce : les expressions regulieres sont acceptees (entourees de /.../) ":
            "Tip: regular expressions are supported (wrapped in /.../) ",
        "Groupes de mots-cles": "Keyword groups",
        "Ajouter un groupe": "Add group",
        "Ajouter un groupe en bas": "Add group at the bottom",
        "Supprimer": "Delete",
        "Modifier": "Edit",
        "Activer": "Enable",
        "Desactiver": "Disable",
        "Desactive": "Disabled",
        "Retirer": "Remove",

        // ---- DeepSeek prompt ----
        "Saisissez le mot-cle principal (ex. : Huawei) :": "Enter the core keyword (e.g.: Huawei):",
        "Echec de la copie automatique : copiez manuellement le contenu ci-dessous, puis ouvrez DeepSeek vous-meme :":
            "Automatic copy failed: copy the content below manually, then open DeepSeek yourself:",

        // ---- Gestion des plateformes ----
        "Aucune plateforme pour l'instant, veuillez en ajouter": "No platform yet, please add one",
        "Reordonne les plateformes": "Reorder platforms",
        "Aucune source RSS pour l'instant, veuillez en ajouter": "No RSS source yet, please add one",

        // ---- Zones d'affichage ----
        "Zone des palmares": "Leaderboard area",
        "Zone des nouveautes": "New items area",
        "Zone des abonnements RSS": "RSS subscriptions area",
        "Zone autonome": "Standalone area",
        "Zone d'analyse IA": "AI analysis area",
        "Aucune plateforme disponible": "No available platform",
        "Aucune source RSS disponible": "No available RSS source",

        // ---- Verification de version ----
        "Verification...": "Checking...",
        "Aucune information de version detectee": "No version information detected",
        "Fermer": "Close",
        "Mettre a jour vers la derniere version": "Update to the latest version",
        "Nouvelle version disponible": "New version available",
        "Mettre a jour plus tard": "Update later",
        "Mettre a jour maintenant": "Update now",
        "La version actuelle est plus recente (version de developpement ?)":
            "The current version is newer (development version?)",
        "Deja a la derniere version": "Already on the latest version",
        "Resultat de la verification de version": "Version check result",
        "Fichier de configuration": "Configuration file",
        "Version actuelle": "Current version",
        "Inconnue": "Unknown",
        "Derniere version": "Latest version",
        "Astuce : ": "Tip: ",
        "Astuce : modifiez le parametre ": "Tip: change the ",

        // ---- Plateformes predefinies ----
        "Toutiao": "Toutiao",
        "Recherches populaires Baidu": "Baidu Hot Search",
        "Wallstreetcn": "Wallstreetcn",
        "The Paper": "The Paper",
        "Recherches populaires Bilibili": "Bilibili Hot Search",
        "CLS Populaire": "CLS Hot",
        "ifeng": "ifeng",
        "Tieba": "Tieba",
        "Weibo": "Weibo",
        "Douyin": "Douyin",
        "Zhihu": "Zhihu",

        // ---- Timeline ----
        "Lun": "Mon",
        "Mar": "Tue",
        "Mer": "Wed",
        "Jeu": "Thu",
        "Ven": "Fri",
        "Sam": "Sat",
        "Dim": "Sun",
        "Collez le contenu de timeline.yaml a gauche": "Paste the timeline.yaml content on the left",
        "Ou cliquez en haut a droite sur « Charger la derniere configuration officielle »":
            "Or click « Load the latest official configuration » in the top right",
        "Mode de planification": "Scheduling mode",
        "Recommande": "Recommended",
        "Copier": "Copy",
        "Actuel": "Current",
        "Nouveau mode": "New mode",
        "Creer un schema de planification personnalise": "Create a custom scheduling scheme",
        "Vue hebdomadaire": "Week view",
        "Heure actuelle ": "Current time ",
        "Legende": "Legend",
        "Notification": "Push",
        "Analyse IA": "AI analysis",
        "Notification + analyse": "Push + analysis",
        "Collecte seule": "Collect only",
        "Par defaut (default)": "Default (default)",
        "Analyse": "Analysis",
        "Mode : ": "Mode: ",
        "Configuration par defaut (default)": "Default configuration (default)",
        "Lorsqu'aucune plage horaire ne s'applique, on utilise la configuration suivante :":
            "When no time period applies, the following configuration is used:",
        "Plages horaires (Periods)": "Time periods (Periods)",
        "Ajouter": "Add",
        "Ce mode n'a pas de plage horaire personnalisee ; la configuration default s'applique toute la journee":
            "This mode has no custom time period; the default configuration applies all day",
        "Plans journaliers (Day Plans)": "Day plans (Day Plans)",
        "Supprimer le plan journalier": "Delete day plan",
        "Vide (default toute la journee)": "Empty (default all day)",
        "+ Ajouter": "+ Add",
        "Correspondance hebdomadaire (Week Map)": "Week mapping (Week Map)",
        "Toute la semaine identique": "Whole week the same",
        "Jours ouvres identiques": "Weekdays the same",
        "Jours ouvres / week-end": "Weekdays / weekend",
        "Strategie de conflit (Overlap)": "Conflict strategy (Overlap)",
        " (recommande)": " (recommended)",
        " (le dernier defini prime)": " (last defined wins)",
        "Collecte": "Collect",
        "Rapport :": "Report:",
        "Analyser une seule fois": "Analyze only once",
        "Notifier une seule fois": "Push only once",
        "Heure :": "Time:",
        "Surcharge de filtrage (optionnel)": "Filter override (optional)",
        "Heriter": "Inherit",
        "ex. tech.txt": "e.g. tech.txt",
        "ex. geopolitics.txt": "e.g. geopolitics.txt",
        "Astuce": "Tip",
        "Supprimer la plage horaire": "Delete time period",
        "Copier la plage horaire": "Copy time period",
        "Aller voir": "Take a look",

        // ---- Fenetre nouveau mode / plage ----
        "Le mode de planification « ": "The scheduling mode « ",
        " » a ete cree avec succes": " » was created successfully",
        "La plage horaire « ": "The time period « ",
        " » a ete ajoutee avec succes": " » was added successfully",

        // ---- Plan journalier non defini ----
        "(non defini)": "(not set)",
        "Plan journalier : ": "Day plan: ",
        "Utilise la configuration default": "Uses the default configuration",
        "Personnalise": "Custom",

        // ---- Barre laterale repli ----
        "Deplier la barre laterale": "Expand sidebar",
        "Replier la barre laterale": "Collapse sidebar"
    };

    // Index inverse (EN -> FR) construit a la volee, utile pour quelques cas.
    var I18N_REVERSE = null;
    function buildReverse() {
        if (I18N_REVERSE) return I18N_REVERSE;
        I18N_REVERSE = {};
        for (var k in I18N) {
            if (Object.prototype.hasOwnProperty.call(I18N, k)) {
                I18N_REVERSE[I18N[k]] = k;
            }
        }
        return I18N_REVERSE;
    }

    // ==========================================
    // Motifs templates (regex) FR -> EN
    // Chaque entree : { fr: RegExp sur le texte FR, en: fn(match)->texte EN }
    // Couvre le temps relatif et les compteurs generes dynamiquement par script.js.
    // ==========================================
    var TEMPLATES = [
        // "a l'instant"
        { test: function (s) { return s === "a l'instant"; }, en: function () { return "just now"; } },
        // "5 min" (formatSaveTime -> "${n} min")
        { test: function (s) { return /^\d+\s*min$/.test(s.trim()); },
          en: function (s) { var n = s.trim().match(/^(\d+)/)[1]; return n + " min ago"; } },
        // "2 h"
        { test: function (s) { return /^\d+\s*h$/.test(s.trim()); },
          en: function (s) { var n = s.trim().match(/^(\d+)/)[1]; return n + " h ago"; } },
        // "3 j"
        { test: function (s) { return /^\d+\s*j$/.test(s.trim()); },
          en: function (s) { var n = s.trim().match(/^(\d+)/)[1]; return n + " d ago"; } },
        // "5 mot(s)-cle(s)" (compteur de mots-cles)
        { test: function (s) { return /^\d+\s*mot\(s\)-cle\(s\)$/.test(s.trim()); },
          en: function (s) { var n = s.trim().match(/^(\d+)/)[1]; return n + " keyword(s)"; } },
        // "3 groupe(s))" -> partie "(N groupe(s))" dans un span separe
        { test: function (s) { return /^\d+\s*groupe\(s\)\)$/.test(s.trim()); },
          en: function (s) { var n = s.trim().match(/^(\d+)/)[1]; return n + " group(s))"; } },
        // "Groupe lie 1/2"
        { test: function (s) { return /^Groupe lie\s+\d+\/\d+$/.test(s.trim()); },
          en: function (s) { return s.replace("Groupe lie", "Related group"); } }
    ];

    // Version EN -> FR des memes motifs, pour revenir au FR proprement si besoin.
    var TEMPLATES_REVERSE = [
        { test: function (s) { return s === "just now"; }, fr: function () { return "a l'instant"; } },
        { test: function (s) { return /^\d+\s*min ago$/.test(s.trim()); },
          fr: function (s) { var n = s.trim().match(/^(\d+)/)[1]; return n + " min"; } },
        { test: function (s) { return /^\d+\s*h ago$/.test(s.trim()); },
          fr: function (s) { var n = s.trim().match(/^(\d+)/)[1]; return n + " h"; } },
        { test: function (s) { return /^\d+\s*d ago$/.test(s.trim()); },
          fr: function (s) { var n = s.trim().match(/^(\d+)/)[1]; return n + " j"; } },
        { test: function (s) { return /^\d+\s*keyword\(s\)$/.test(s.trim()); },
          fr: function (s) { var n = s.trim().match(/^(\d+)/)[1]; return n + " mot(s)-cle(s)"; } },
        { test: function (s) { return /^\d+\s*group\(s\)\)$/.test(s.trim()); },
          fr: function (s) { var n = s.trim().match(/^(\d+)/)[1]; return n + " groupe(s))"; } },
        { test: function (s) { return /^Related group\s+\d+\/\d+$/.test(s.trim()); },
          fr: function (s) { return s.replace("Related group", "Groupe lie"); } }
    ];

    // ==========================================
    // Memoire du texte FR d'origine par noeud (evite les collisions / doubles traductions)
    // ==========================================
    var FR_TEXT = new WeakMap();   // noeud texte -> chaine FR d'origine
    var FR_ATTR = new WeakMap();   // element -> { attrName: valeur FR d'origine }

    var ATTR_NAMES = ['placeholder', 'title', 'value', 'alt'];
    // Les <input type="value"> ne doivent pas voir leur valeur saisie ecrasee :
    // on ne traduit 'value' que pour les boutons / options statiques.
    function attrTranslatable(el, attr) {
        if (attr !== 'value') return true;
        var tag = el.tagName;
        if (tag === 'OPTION') return true;
        if (tag === 'INPUT') {
            var t = (el.getAttribute('type') || 'text').toLowerCase();
            return t === 'button' || t === 'submit' || t === 'reset';
        }
        return false;
    }

    function translateString(fr, toEn) {
        if (toEn) {
            if (Object.prototype.hasOwnProperty.call(I18N, fr)) return I18N[fr];
            for (var i = 0; i < TEMPLATES.length; i++) {
                if (TEMPLATES[i].test(fr)) return TEMPLATES[i].en(fr);
            }
            return null; // pas de traduction connue
        }
        return null;
    }

    // Traduit un noeud texte (toLang = 'fr' ou 'en')
    function applyToTextNode(node, toLang) {
        var raw = node.nodeValue;
        if (!raw) return;
        var trimmed = raw.trim();
        if (!trimmed) return;

        if (toLang === 'en') {
            // memorise le FR d'origine une seule fois
            if (!FR_TEXT.has(node)) FR_TEXT.set(node, raw);
            var frRef = FR_TEXT.get(node);
            var frTrim = frRef.trim();
            var en = translateString(frTrim, true);
            if (en !== null) {
                node.nodeValue = frRef.replace(frTrim, en);
            }
        } else { // retour au FR
            if (FR_TEXT.has(node)) {
                node.nodeValue = FR_TEXT.get(node);
            }
        }
    }

    function applyToAttributes(el, toLang) {
        for (var i = 0; i < ATTR_NAMES.length; i++) {
            var attr = ATTR_NAMES[i];
            if (!el.hasAttribute(attr)) continue;
            if (!attrTranslatable(el, attr)) continue;

            if (toLang === 'en') {
                var store = FR_ATTR.get(el);
                if (!store) { store = {}; FR_ATTR.set(el, store); }
                if (!(attr in store)) store[attr] = el.getAttribute(attr);
                var frVal = store[attr];
                var frTrim = (frVal || '').trim();
                if (!frTrim) continue;
                var en = translateString(frTrim, true);
                if (en !== null) el.setAttribute(attr, frVal.replace(frTrim, en));
            } else {
                var st = FR_ATTR.get(el);
                if (st && attr in st) el.setAttribute(attr, st[attr]);
            }
        }
    }

    function walk(node, toLang) {
        if (!node) return;
        if (node.nodeType === Node.TEXT_NODE) {
            applyToTextNode(node, toLang);
            return;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return;
        var tag = node.tagName;
        if (tag === 'SCRIPT' || tag === 'STYLE') return;
        if (node.id === 'lang-switcher') return; // ne pas traduire le selecteur lui-meme

        applyToAttributes(node, toLang);

        var children = node.childNodes;
        for (var i = 0; i < children.length; i++) {
            walk(children[i], toLang);
        }
    }

    // ==========================================
    // API principale
    // ==========================================
    function getLang() {
        try {
            var v = localStorage.getItem(STORAGE_KEY);
            return v === 'en' ? 'en' : DEFAULT_LANG;
        } catch (e) { return DEFAULT_LANG; }
    }

    function setLang(lang) {
        try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) {}
    }

    function applyLang(lang) {
        var toLang = lang === 'en' ? 'en' : 'fr';

        // <html lang> + titre
        document.documentElement.setAttribute('lang', toLang);
        if (toLang === 'en') {
            document.title = "TrendRadar - Configuration Editor";
        } else {
            document.title = "TrendRadar - Editeur de configuration";
        }

        // Parcours du DOM
        if (document.body) walk(document.body, toLang);

        // Etat du selecteur
        updateSwitcherUI(toLang);
    }

    // Traduit un sous-arbre nouvellement ajoute (utilise par le MutationObserver en mode EN)
    function localizeSubtree(node) {
        walk(node, 'en');
    }

    // ==========================================
    // Selecteur de langue FR / EN
    // ==========================================
    function buildSwitcher() {
        if (document.getElementById('lang-switcher')) return;

        // Cible : barre de nav, a cote du bouton "Copier la configuration"
        var copyBtn = document.querySelector('button[onclick="copyResult()"]');
        var container = copyBtn ? copyBtn.parentElement : null;
        if (!container) {
            // repli : premier conteneur de boutons dans la nav
            container = document.querySelector('nav .flex.gap-3') || document.querySelector('nav');
        }
        if (!container) return;

        var wrap = document.createElement('div');
        wrap.id = 'lang-switcher';
        wrap.setAttribute('role', 'group');
        wrap.setAttribute('aria-label', 'Langue / Language');
        wrap.style.cssText = 'display:inline-flex;align-items:center;border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;font-size:12px;line-height:1;';

        var frBtn = document.createElement('button');
        frBtn.type = 'button';
        frBtn.id = 'lang-btn-fr';
        frBtn.textContent = 'FR';
        frBtn.setAttribute('aria-label', 'Francais');
        frBtn.style.cssText = 'padding:6px 10px;border:none;cursor:pointer;background:#fff;color:#374151;font-weight:600;';

        var enBtn = document.createElement('button');
        enBtn.type = 'button';
        enBtn.id = 'lang-btn-en';
        enBtn.textContent = 'EN';
        enBtn.setAttribute('aria-label', 'English');
        enBtn.style.cssText = 'padding:6px 10px;border:none;cursor:pointer;background:#fff;color:#374151;font-weight:600;border-left:1px solid #e5e7eb;';

        frBtn.addEventListener('click', function () { switchTo('fr'); });
        enBtn.addEventListener('click', function () { switchTo('en'); });

        wrap.appendChild(frBtn);
        wrap.appendChild(enBtn);

        // Insertion en tete du conteneur de boutons (a gauche de "Copier la configuration")
        container.insertBefore(wrap, container.firstChild);
    }

    function updateSwitcherUI(lang) {
        var frBtn = document.getElementById('lang-btn-fr');
        var enBtn = document.getElementById('lang-btn-en');
        if (!frBtn || !enBtn) return;
        var activeBg = '#2563eb', activeColor = '#fff', idleBg = '#fff', idleColor = '#374151';
        if (lang === 'en') {
            enBtn.style.background = activeBg; enBtn.style.color = activeColor;
            frBtn.style.background = idleBg; frBtn.style.color = idleColor;
            enBtn.setAttribute('aria-pressed', 'true');
            frBtn.setAttribute('aria-pressed', 'false');
        } else {
            frBtn.style.background = activeBg; frBtn.style.color = activeColor;
            enBtn.style.background = idleBg; enBtn.style.color = idleColor;
            frBtn.setAttribute('aria-pressed', 'true');
            enBtn.setAttribute('aria-pressed', 'false');
        }
    }

    function switchTo(lang) {
        setLang(lang);
        applyLang(lang);
    }

    // ==========================================
    // MutationObserver : localise les noeuds ajoutes dynamiquement (modales, toasts, listes...)
    // ==========================================
    var observer = null;
    function startObserver() {
        if (observer || !document.body) return;
        observer = new MutationObserver(function (mutations) {
            if (getLang() !== 'en') return; // en mode FR, le DOM est deja en FR par defaut
            for (var i = 0; i < mutations.length; i++) {
                var m = mutations[i];
                if (m.type === 'childList') {
                    for (var j = 0; j < m.addedNodes.length; j++) {
                        var n = m.addedNodes[j];
                        if (n.id === 'lang-switcher') continue;
                        if (n.nodeType === Node.ELEMENT_NODE || n.nodeType === Node.TEXT_NODE) {
                            localizeSubtree(n);
                        }
                    }
                } else if (m.type === 'characterData') {
                    if (m.target && m.target.nodeType === Node.TEXT_NODE) {
                        // un texte a change (ex. mise a jour de l'heure d'enregistrement)
                        FR_TEXT.delete(m.target); // re-memorise la nouvelle valeur FR
                        applyToTextNode(m.target, 'en');
                    }
                }
            }
        });
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true
        });
    }

    // ==========================================
    // Initialisation
    // ==========================================
    function init() {
        buildSwitcher();
        startObserver();
        applyLang(getLang());
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose l'API au scope global (pratique pour le debogage / appels externes)
    window.TrendRadarI18N = {
        applyLang: applyLang,
        getLang: getLang,
        setLang: setLang,
        switchTo: switchTo,
        I18N: I18N,
        buildReverse: buildReverse
    };
})();
