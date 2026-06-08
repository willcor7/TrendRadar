<div align="center">

**Français** | **[English](README-MCP-FAQ-EN.md)**

</div>

# Questions-réponses sur l'utilisation des outils MCP de TrendRadar

> Guide des requêtes IA - Comment utiliser les outils d'analyse des tendances d'actualités via une conversation naturelle (v3.1.7)

---

## 📋 Vue d'ensemble des outils

| Catégorie | Nom de l'outil | Description |
|:----:|---------|---------|
| **Date** | `resolve_date_range` | Convertit « cette semaine », « les 7 derniers jours » et autres expressions en langage naturel en dates standard |
| **Requête** | `get_latest_news` | Récupère le dernier lot d'actualités tendances collectées |
| | `get_news_by_date` | Interroge les actualités historiques par plage de dates |
| | `get_trending_topics` | Récupère les statistiques des sujets populaires (extraction automatique prise en charge) |
| **RSS** | `get_latest_rss` | Récupère le contenu RSS le plus récent |
| | `search_rss` | Recherche des mots-clés dans les données RSS |
| | `get_rss_feeds_status` | Affiche la configuration des sources RSS et l'état des données |
| **Recherche** | `search_news` | Recherche unifiée (mot-clé / approximative / entité, RSS optionnel) |
| | `find_related_news` | Trouve des actualités similaires à un titre donné |
| **Analyse** | `analyze_topic_trend` | Analyse de tendance d'un sujet (popularité / cycle de vie / pic viral / prévision) |
| | `analyze_data_insights` | Analyse approfondie des données (comparaison de plateformes / activité / cooccurrence de mots-clés) |
| | `analyze_sentiment` | Analyse du sentiment des actualités |
| | `aggregate_news` | Agrégation et déduplication des actualités multiplateformes |
| | `compare_periods` | Comparaison entre périodes (évolution hebdomadaire / mensuelle) |
| | `generate_summary_report` | Génère des rapports de synthèse quotidiens / hebdomadaires |
| **Système** | `get_current_config` | Récupère la configuration actuelle du système |
| | `get_system_status` | Récupère l'état de fonctionnement du système |
| | `check_version` | Vérifie les mises à jour de version (TrendRadar + serveur MCP) |
| | `trigger_crawl` | Déclenche manuellement une tâche de collecte |
| **Stockage** | `sync_from_remote` | Récupère les données du stockage distant vers le local |
| | `get_storage_status` | Récupère la configuration et l'état du stockage |
| | `list_available_dates` | Liste les dates disponibles en local / à distance |
| **Article** | `read_article` | Lit le contenu d'un article (format Markdown) |
| | `read_articles_batch` | Lit plusieurs articles en lot (5 maximum) |
| **Notification** | `get_notification_channels` | Récupère tous les canaux de notification configurés et leur état |
| | `send_notification` | Envoie des messages aux canaux de notification configurés (conversion de format automatique) |

---

## ⚙️ Réglages par défaut (important !)

Les stratégies d'optimisation suivantes sont appliquées par défaut, principalement pour économiser les tokens consommés par l'IA :

| Réglage par défaut | Description | Comment l'ajuster |
| -------------- | --------------------------------------- | ------------------------------------- |
| **Nombre d'éléments** | Renvoie 50 actualités par défaut | Dites « renvoie les 10 premières » ou « donne-m'en 100 » dans la conversation |
| **Plage temporelle** | Interroge par défaut les données du jour | Dites « interroge hier », « la dernière semaine » ou « du 1er au 7 janvier » |
| **Liens URL** | N'inclut pas les liens par défaut (économie d'environ 160 tokens par élément) | Dites « avec les liens » ou « inclus les URL » |
| **Liste de mots-clés** | N'utilise pas `frequency_words.txt` pour filtrer les actualités par défaut | Utilisé uniquement lors de l'appel à l'outil « sujets populaires » |

**⚠️ Important :** le choix du modèle d'IA influe directement sur l'efficacité des appels d'outils : plus l'IA est performante, plus les appels sont précis. Lorsque vous levez les restrictions ci-dessus, par exemple en passant d'une requête sur aujourd'hui à une requête sur une semaine, il faut d'abord disposer localement d'une semaine de données ; ensuite, la consommation de tokens peut être multipliée.

**💡 Astuce :** ce projet fournit un outil dédié d'analyse de dates, capable d'interpréter précisément les expressions en langage naturel comme « les 7 derniers jours » ou « cette semaine », garantissant que tous les modèles d'IA obtiennent des plages de dates cohérentes. Voir la Q18 ci-dessous pour plus de détails.


## 💰 Modèles d'IA

Ci-dessous, je prends comme exemple la plateforme **[SiliconFlow](https://cloud.siliconflow.cn)**, qui propose de nombreux grands modèles au choix. Pendant le développement et les tests de ce projet, j'ai utilisé cette plateforme pour de nombreux essais et validations de fonctionnalités.

### 📊 Comparaison des modes d'inscription

| Mode d'inscription | Inscription directe sans lien de parrainage | Inscription avec lien de parrainage |
|:-------:|:-------:|:-----------------:|
| Lien d'inscription | [siliconflow.cn](https://cloud.siliconflow.cn) | [Lien de parrainage](https://cloud.siliconflow.cn/i/fqnyVaIU) |
| Crédit gratuit | 0 token | **20 millions de tokens** (≈ 2 $) |
| Bonus supplémentaire | ❌ | ✅ Le parrain reçoit également 20 millions de tokens |

> 💡 **Astuce** : le crédit offert ci-dessus devrait permettre **plus de 200 requêtes**.


### 🚀 Démarrage rapide

#### 1️⃣ S'inscrire et obtenir une clé API

1. Terminez votre inscription via le lien ci-dessus.
2. Rendez-vous sur la [page de gestion des clés API](https://cloud.siliconflow.cn/me/account/ak).
3. Cliquez sur « Créer une nouvelle clé API ».
4. Copiez la clé générée (conservez-la précieusement).

#### 2️⃣ Configurer dans Cherry Studio

1. Ouvrez **Cherry Studio**.
2. Allez dans les paramètres « Services de modèles ».
3. Trouvez « SiliconFlow ».
4. Collez la clé copiée dans le champ **[Clé API]**.
5. Assurez-vous que la case en haut à droite, une fois activée, s'affiche en **vert** ✅.

---

### ✨ Configuration terminée !

Vous pouvez maintenant commencer à utiliser ce projet et profiter d'un service d'IA stable et rapide !

Après votre première requête de test, rendez-vous immédiatement sur la [facturation SiliconFlow](https://cloud.siliconflow.cn/me/bills) pour consulter la consommation de cette requête et vous faire une idée des coûts.


---

## Requêtes de base

### Q1 : Comment consulter les actualités les plus récentes ?

**Vous pouvez demander, par exemple :**

- « Montre-moi les dernières actualités »
- « Interroge les actualités tendances du jour »
- « Récupère les 10 dernières actualités de Zhihu et Weibo »
- « Affiche les dernières actualités, avec les liens »

**Comportement de l'outil :**

- L'outil renvoie les 50 actualités les plus récentes de toutes les plateformes.
- Les liens URL ne sont pas inclus par défaut (économie de tokens).

**Comportement d'affichage de l'IA (important) :**

- ⚠️ **L'IA résume généralement de façon automatique** et n'affiche qu'une partie des actualités (par exemple le TOP 10 à 20).
- ✅ Si vous voulez voir les 50 actualités, demandez-le explicitement : « affiche toutes les actualités » ou « liste les 50 en intégralité ».
- 💡 C'est un comportement naturel du modèle d'IA, pas une limite de l'outil.

**Vous pouvez ajuster :**

- La plateforme : par exemple « seulement Zhihu ».
- Le nombre : par exemple « renvoie les 20 premières ».
- L'inclusion des liens : par exemple « avec les liens ».
- **Demander un affichage complet** : par exemple « affiche tout, sans résumer ».

---

### Q2 : Comment interroger les actualités d'une date précise ?

**Vous pouvez demander, par exemple :**

- « Interroge les actualités d'hier »
- « Montre les actualités de Zhihu d'il y a 3 jours »
- « Quelles actualités y avait-il le 2025-10-10 »
- « Les actualités de lundi dernier »
- « Montre-moi les dernières actualités » (interroge automatiquement aujourd'hui)

**Formats de date pris en charge :**

- Dates relatives : aujourd'hui, hier, avant-hier, il y a 3 jours.
- Jours de la semaine : lundi dernier, ce mercredi, last monday.
- Dates absolues : 2025-10-10, 10 octobre.

**Comportement de l'outil :**

- Interroge automatiquement aujourd'hui si aucune date n'est précisée (économie de tokens).
- L'outil renvoie 50 actualités de toutes les plateformes.
- Les liens URL ne sont pas inclus par défaut.

**Comportement d'affichage de l'IA (important) :**

- ⚠️ **L'IA résume généralement de façon automatique** et n'affiche qu'une partie des actualités (par exemple le TOP 10 à 20).
- ✅ Si vous voulez tout voir, demandez-le explicitement : « affiche toutes les actualités, sans résumer ».

---

### Q3 : Comment consulter les statistiques des sujets populaires ?

**Vous pouvez demander, par exemple :**

- « Combien de fois mes mots-clés sont-ils apparus aujourd'hui ? » (utilise les mots-clés prédéfinis)
- « Analyse automatiquement les sujets populaires dans les actualités du jour » (extraction automatique)
- « Quels sont les mots les plus présents dans les actualités ? » (extraction automatique)

**Deux modes d'extraction :**

| Mode | Description | Exemple de formulation |
|------|------|---------|
| **Mots-clés prédéfinis** | Comptabilise les mots-clés que vous avez définis à l'avance (basé sur le fichier de configuration, par défaut) | « Combien de fois mes mots-clés sont-ils apparus ? » |
| **Extraction automatique** | Extrait automatiquement les mots fréquents des titres d'actualités (sans réglage préalable) | « Analyse automatiquement les sujets populaires » |

---

## Requêtes sur les flux RSS

### Q4.1 : Comment consulter le contenu RSS le plus récent ?

**Vous pouvez demander, par exemple :**

- « Affiche le contenu RSS le plus récent »
- « Récupère les derniers articles de Hacker News »
- « Affiche les 20 derniers éléments de toutes les sources RSS »
- « Récupère les flux RSS, avec les résumés »
- « Montre-moi le contenu RSS de la dernière semaine » (requête multi-jours prise en charge)
- « Récupère les articles Hacker News des 7 derniers jours »

**Comportement de l'outil :**

- Renvoie par défaut les éléments RSS du jour (50 maximum).
- Prend en charge le paramètre `days` pour récupérer plusieurs jours de données (1 à 30 jours).
- N'inclut pas les résumés par défaut (économie de tokens).
- Trié par date de publication décroissante.
- Déduplication automatique entre les dates (par URL).

**Comportement d'affichage de l'IA (important) :**

- ⚠️ **L'IA résume généralement de façon automatique** et n'affiche qu'une partie des éléments.
- ✅ Si vous voulez tout voir, demandez-le explicitement : « affiche tout le contenu RSS ».

**Vous pouvez ajuster :**

- La source RSS : par exemple « seulement Hacker News ».
- Le nombre de jours : par exemple « les 7 derniers jours », « la dernière semaine ».
- Le nombre : par exemple « renvoie les 20 premiers ».
- L'inclusion des résumés : par exemple « avec les résumés ».

---

### Q4.2 : Comment rechercher dans le contenu des flux RSS ?

**Vous pouvez demander, par exemple :**

- « Recherche les articles RSS relatifs à « IA » »
- « Recherche dans le RSS des 7 derniers jours le contenu sur « machine learning » »
- « Recherche « Python » dans Hacker News »

**Comportement de l'outil :**

- Recherche les titres des éléments RSS à partir de mots-clés.
- Recherche par défaut dans les données des 7 derniers jours.
- L'outil renvoie 50 résultats maximum.

**Vous pouvez ajuster :**

- La source RSS : par exemple « recherche uniquement dans Hacker News ».
- Le nombre de jours : par exemple « recherche dans les 14 derniers jours ».
- L'inclusion des résumés : par exemple « avec les résumés ».

---

### Q4.3 : Comment consulter l'état des sources RSS ?

**Vous pouvez demander, par exemple :**

- « Affiche l'état des sources RSS »
- « Combien de données le RSS a-t-il collectées ? »
- « Quelles sources RSS contiennent des données ? »

**Informations renvoyées :**

| Champ | Description |
|------|------|
| **Dates disponibles** | Liste des dates pour lesquelles des données RSS existent |
| **Nombre total de dates** | Combien de jours de données au total |
| **Statistiques du jour par source** | Statistiques des données du jour, source RSS par source RSS |
| **Heure de génération** | Heure de génération de l'état |

---

## Recherche et récupération

### Q4 : Comment rechercher des actualités contenant un mot-clé précis ?

**Vous pouvez demander, par exemple :**

- « Recherche les actualités contenant « intelligence artificielle » »
- « Trouve les articles sur « la baisse de prix de Tesla » »
- « Recherche les actualités liées à Musk, renvoie les 20 premières »
- « Trouve les actualités des 7 derniers jours sur « iPhone 16 » »
- « Trouve les actualités liées à « Tesla » du 1er au 7 janvier 2025 »
- « Trouve le lien de l'actualité « sortie de l'iPhone 16 » »

**Comportement de l'outil :**

- Utilise le mode de recherche par mot-clé.
- Recherche par défaut dans les données du jour.
- L'IA convertit automatiquement les expressions temporelles relatives comme « les 7 derniers jours » ou « la semaine dernière » en plages de dates précises.
- L'outil renvoie 50 résultats maximum.
- Les liens URL ne sont pas inclus par défaut.

**Comportement d'affichage de l'IA (important) :**

- ⚠️ **L'IA résume généralement de façon automatique** et n'affiche qu'une partie des résultats.
- ✅ Si vous voulez tout voir, demandez-le explicitement : « affiche tous les résultats de recherche ».

**Vous pouvez ajuster :**

- La plage temporelle :
  - De façon relative : « recherche sur la dernière semaine » (l'IA calcule les dates automatiquement).
  - Par dates absolues : « recherche du 1er au 7 janvier 2025 ».
- La plateforme : par exemple « recherche uniquement dans Zhihu ».
- Le tri : par exemple « trie par poids ».
- L'inclusion des liens : par exemple « avec les liens ».

---

### Q4.4 : Comment rechercher simultanément dans les actualités tendances et le RSS ?

**Vous pouvez demander, par exemple :**

- « Recherche le contenu sur « IA », RSS inclus »
- « Trouve les actualités sur « intelligence artificielle » et recherche aussi dans les flux RSS »
- « Recherche « Tesla », à la fois dans les tendances et le RSS »

**Comportement de l'outil :**

- Les résultats des tendances et les résultats RSS sont **affichés séparément**.
- Les tendances sont triées par classement / pertinence, le RSS par date de publication.
- Les résultats RSS n'affectent pas l'affichage du classement des tendances.
- Renvoie par défaut 50 actualités tendances + 20 éléments RSS.

**Vous pouvez ajuster :**

- Le nombre d'éléments RSS : par exemple « renvoie 10 éléments RSS ».
- Rechercher uniquement dans les tendances : ne dites pas « RSS inclus » (comportement par défaut).
- Rechercher uniquement dans le RSS : dites « recherche uniquement dans le RSS ».

---

### Q5 : Comment trouver des actualités similaires ?

**Vous pouvez demander, par exemple :**

- « Trouve les actualités similaires à « la baisse de prix de Tesla » » (aujourd'hui)
- « Trouve les actualités d'hier liées à « percée de l'IA » » (historique)
- « Recherche les articles de la semaine dernière sur « ChatGPT » » (historique)
- « Regarde s'il y a des articles similaires à cette actualité dans les 7 derniers jours » (historique)

**Plages temporelles prises en charge :**

| Méthode | Description | Exemple |
|------|------|------|
| Non précisée | Interroge uniquement les données du jour (par défaut) | « Trouve des actualités similaires » |
| Valeurs prédéfinies | hier, la semaine dernière, le mois dernier | « Trouve les actualités liées d'hier » |
| Plage de dates | Précise une date de début et de fin | « Trouve les articles liés du 1er au 7 janvier » |

**Comportement de l'outil :**

- Seuil de similarité de 0,5 (ajustable).
- L'outil renvoie 50 résultats maximum.
- Trié par similarité.
- Les liens URL ne sont pas inclus par défaut.

**Comportement d'affichage de l'IA (important) :**

- ⚠️ **L'IA résume généralement de façon automatique** et n'affiche qu'une partie des actualités liées.
- ✅ Si vous voulez tout voir, demandez-le explicitement : « affiche toutes les actualités liées ».

**Vous pouvez ajuster :**

- La période : par exemple « trouve celles de la semaine dernière ».
- Le seuil : par exemple « toutes celles dont la similarité dépasse 0,3 ».
- L'inclusion des liens : dites « avec les liens ».

---

## Analyse des tendances

### Q6 : Comment analyser la tendance de popularité d'un sujet ?

**Vous pouvez demander, par exemple :**

- « Analyse la tendance de popularité de « l'intelligence artificielle » sur la dernière semaine »
- « Le sujet « Tesla » est-il un feu de paille ou une tendance durable ? »
- « Détecte les sujets devenus soudainement viraux aujourd'hui »
- « Prédis les sujets susceptibles de devenir populaires prochainement »
- « Analyse le cycle de vie de « Bitcoin » en décembre 2024 »

**Quatre modes d'analyse :**

| Mode | Description | Exemple de formulation |
|------|------|---------|
| **Tendance de popularité** | Suit l'évolution de la popularité d'un sujet | « Analyse la tendance de popularité de « IA » » |
| **Cycle de vie** | Cycle complet, de l'apparition à la disparition | « « XX » est-il un feu de paille ou une tendance durable ? » |
| **Détection d'anomalies** | Identifie les sujets devenus soudainement viraux | « Quels sujets sont devenus soudainement viraux aujourd'hui ? » |
| **Prévision** | Prédit les futurs sujets populaires | « Prédis les sujets populaires à venir » |

**Comportement de l'outil :**

- L'IA convertit automatiquement les expressions temporelles relatives comme « la dernière semaine » en plages de dates précises.
- Analyse par défaut les données des 7 derniers jours.
- Statistiques à la granularité du jour.

---

## Analyse approfondie des données

### Q7 : Comment comparer l'intérêt des différentes plateformes pour un sujet ?

**Vous pouvez demander, par exemple :**

- « Compare l'intérêt des différentes plateformes pour le sujet « intelligence artificielle » »
- « Quelle plateforme se met à jour le plus souvent ? »
- « Analyse quels mots-clés apparaissent souvent ensemble »

**Trois modes d'analyse :**

| Mode | Fonction | Exemple de formulation |
| -------------- | ---------------- | -------------------------- |
| **Comparaison de plateformes** | Compare l'intérêt de chaque plateforme | « Compare l'intérêt des plateformes pour « IA » » |
| **Statistiques d'activité** | Comptabilise la fréquence de publication des plateformes | « Quelle plateforme se met à jour le plus souvent ? » |
| **Cooccurrence de mots-clés** | Analyse les associations entre mots-clés | « Quels mots-clés apparaissent souvent ensemble ? » |

**Comportement de l'outil :**

- Utilise par défaut le mode de comparaison de plateformes.
- Analyse les données du jour.
- Fréquence minimale de cooccurrence de mots-clés : 3 occurrences.

---

## Analyse du sentiment

### Q8 : Comment analyser le sentiment des actualités ?

**Vous pouvez demander, par exemple :**

- « Analyse le sentiment des actualités du jour »
- « Les actualités liées à « Tesla » sont-elles positives ou négatives ? »
- « Analyse l'attitude des différentes plateformes envers « l'intelligence artificielle » »
- « Analyse le sentiment de « Bitcoin » sur une semaine, en prenant les 20 actualités les plus importantes »

**Comportement de l'outil :**

- Analyse par défaut les données du jour.
- L'outil renvoie 50 actualités maximum.
- Trié par poids (les actualités importantes sont affichées en priorité).
- Les liens URL ne sont pas inclus par défaut.

**Comportement d'affichage de l'IA (important) :**

- ⚠️ Cet outil renvoie une **invite (prompt) pour l'IA**, et non un résultat d'analyse de sentiment direct.
- L'IA génère un rapport d'analyse de sentiment à partir de cette invite.
- Elle affiche généralement la distribution des sentiments, les constats clés et des actualités représentatives.

**Vous pouvez ajuster :**

- Le sujet : par exemple « à propos de « Tesla » ».
- La période : par exemple « la dernière semaine ».
- Le nombre : par exemple « renvoie les 20 premières ».

---

### Q9 : Comment obtenir des actualités multiplateformes dédupliquées ?

**Vous pouvez demander, par exemple :**

- « Agrège les actualités du jour en supprimant les doublons »
- « Quelles actualités sont relayées sur plusieurs plateformes ? »
- « Montre-moi les actualités tendances après déduplication »
- « Quelles actualités sont des tendances multiplateformes ? »

**Fonction de l'outil :**

- Identifie automatiquement le même événement rapporté par différentes plateformes.
- Fusionne les actualités similaires en une seule actualité agrégée.
- Affiche la couverture par plateforme de chaque actualité.
- Calcule un poids de popularité global.

**Informations renvoyées :**

| Champ | Description |
|------|------|
| **Titre représentatif** | Titre représentatif de ce groupe d'actualités |
| **Plateformes couvertes** | Quelles plateformes ont relayé cette actualité |
| **Nombre de plateformes** | Combien de plateformes l'ont couverte |
| **Caractère multiplateforme** | S'agit-il ou non d'une tendance multiplateforme |
| **Meilleur classement** | Meilleur classement obtenu sur l'ensemble des plateformes |
| **Poids global** | Score de popularité global |
| **Sources par plateforme** | Informations détaillées de chaque plateforme |

**Vous pouvez ajuster :**

- La période : par exemple « celles de la dernière semaine ».
- Le seuil de similarité : par exemple « correspondance plus stricte » ou « correspondance plus souple ».
- La plateforme : par exemple « seulement Zhihu et Weibo ».

---

### Q10 : Comment générer une synthèse quotidienne ou hebdomadaire des tendances ?

**Vous pouvez demander, par exemple :**

- « Génère le rapport de synthèse des actualités du jour »
- « Donne-moi un récapitulatif des tendances de la semaine »
- « Génère un rapport d'analyse des actualités des 7 derniers jours »

**Types de rapports :**

- Synthèse quotidienne : récapitule les actualités tendances du jour.
- Synthèse hebdomadaire : récapitule les tendances de la semaine.

---

### Q11 : Comment comparer l'évolution des tendances entre différentes périodes ?

**Vous pouvez demander, par exemple :**

- « Compare l'évolution des tendances entre cette semaine et la semaine dernière »
- « Qu'est-ce qui change entre ce mois et le mois dernier ? »
- « Analyse la différence de popularité de « l'intelligence artificielle » entre deux périodes »
- « Compare l'évolution de l'activité des plateformes »

**Trois modes de comparaison :**

| Mode | Description | Cas d'usage |
|------|------|---------|
| **Vue d'ensemble** | Évolution du nombre d'actualités, des mots-clés, comparaison des TOP actualités | Comprendre rapidement l'évolution globale |
| **Évolution des sujets** | Sujets en hausse, en baisse, nouvellement apparus | Analyser les déplacements de tendances |
| **Activité des plateformes** | Évolution du nombre d'actualités par plateforme | Comprendre la dynamique des plateformes |

**Valeurs de période prédéfinies :**

- Aujourd'hui / Hier
- Cette semaine / La semaine dernière
- Ce mois / Le mois dernier
- Ou une plage de dates personnalisée

---

## Gestion du système

### Q12 : Comment consulter la configuration du système ?

**Vous pouvez demander, par exemple :**

- « Affiche la configuration actuelle du système »
- « Montre le contenu du fichier de configuration »
- « Quelles sont les plateformes disponibles ? »
- « Quelle est la configuration de poids actuelle ? »

**Vous pouvez interroger :**

- La liste des plateformes disponibles.
- La configuration du robot d'exploration (intervalle entre requêtes, délais d'expiration).
- La configuration des poids (poids du classement, poids de la fréquence).
- La configuration des notifications (Feishu, DingTalk, WeCom, Telegram, Email, ntfy, Bark, Slack, Webhook générique).

---

### Q13 : Comment vérifier l'état de fonctionnement du système ?

**Vous pouvez demander, par exemple :**

- « Vérifie l'état du système »
- « Le système fonctionne-t-il normalement ? »
- « Quand a eu lieu la dernière collecte ? »
- « Combien de jours de données historiques y a-t-il ? »

**Informations renvoyées :**

- Version et état du système.
- Heure de la dernière collecte.
- Nombre de jours de données historiques.
- Résultats du contrôle de santé.

---

### Q13.1 : Comment vérifier les mises à jour de version ?

**Vous pouvez demander, par exemple :**

- « Vérifie les mises à jour de version »
- « Y a-t-il une nouvelle version ? »
- « La version actuelle est-elle à jour ? »

**Informations renvoyées :**

La vérification porte simultanément sur les deux composants :

| Composant | Description |
|------|------|
| **TrendRadar** | Moteur principal de collecte et d'analyse |
| **Serveur MCP** | Service d'outils conversationnels pour l'IA |

Pour chaque composant, vous obtenez :
- La version actuellement installée.
- La dernière version disponible.
- Si une mise à jour est nécessaire.
- Une recommandation de mise à jour.

**Vous pouvez ajuster :**

- Si l'accès à GitHub est lent, vous pouvez dire « vérifie les mises à jour de version en utilisant le proxy http://127.0.0.1:10801 ».

---

### Q14 : Comment déclencher manuellement une tâche de collecte ?

**Vous pouvez demander, par exemple :**

- « Collecte les actualités actuelles de Toutiao » (requête temporaire)
- « Récupère et enregistre les dernières actualités de Zhihu et Weibo » (persistant)
- « Déclenche une collecte et enregistre les données » (persistant)
- « Récupère les données en temps réel de 36Kr sans les enregistrer » (requête temporaire)

**Deux modes :**

| Mode | Usage | Exemple |
| -------------- | -------------------- | -------------------- |
| **Collecte temporaire** | Renvoie les données sans les enregistrer | « Collecte les actualités de Toutiao » |
| **Collecte persistante** | Enregistre dans le dossier `output` | « Récupère et enregistre les actualités de Zhihu » |

**Comportement de l'outil :**

- Mode collecte temporaire par défaut (sans enregistrement).
- Collecte toutes les plateformes par défaut.
- Les liens URL ne sont pas inclus par défaut.

**Comportement d'affichage de l'IA (important) :**

- ⚠️ **L'IA résume généralement les résultats de la collecte** et n'affiche qu'une partie des actualités.
- ✅ Si vous voulez tout voir, demandez-le explicitement : « affiche toutes les actualités collectées ».

**Vous pouvez ajuster :**

- La plateforme : par exemple « collecte uniquement Zhihu ».
- L'enregistrement des données : dites « et enregistre » ou « enregistre en local ».
- L'inclusion des liens : dites « avec les liens ».

---

## Synchronisation du stockage

### Q15 : Comment synchroniser les données du stockage distant vers le local ?

**Vous pouvez demander, par exemple :**

- « Synchronise les données des 7 derniers jours depuis le distant »
- « Récupère les données du stockage distant vers le local »
- « Synchronise les données d'actualités des 30 derniers jours »

**Cas d'usage :**

- Le robot d'exploration est déployé dans le cloud (par exemple GitHub Actions) et les données sont stockées à distance (par exemple Cloudflare R2).
- Le serveur MCP est déployé en local et doit récupérer les données distantes pour l'analyse.

**Informations renvoyées :**

- Nombre de fichiers synchronisés avec succès.
- Liste des dates synchronisées avec succès.
- Dates ignorées (déjà présentes en local).
- Dates en échec et messages d'erreur.

**Prérequis :**

Il faut configurer le stockage distant dans le fichier de configuration ou définir des variables d'environnement :
- URL du point de terminaison du service.
- Nom du bucket de stockage.
- Identifiant de la clé d'accès.
- Clé d'accès secrète.

---

### Q16 : Comment consulter l'état du stockage ?

**Vous pouvez demander, par exemple :**

- « Affiche l'état actuel du stockage »
- « Quelle est la configuration du stockage ? »
- « Combien de données y a-t-il en local ? »
- « Le stockage distant est-il configuré ? »

**Informations renvoyées :**

| Catégorie | Informations |
|------|------|
| **Stockage local** | Répertoire des données, taille totale, nombre de dates, plage de dates |
| **Stockage distant** | Configuré ou non, adresse du point de terminaison, nom du bucket, nombre de dates |
| **Configuration de récupération** | Récupération automatique activée ou non, nombre de jours à récupérer |

---

### Q17 : Comment consulter les dates de données disponibles ?

**Vous pouvez demander, par exemple :**

- « Quelles dates sont disponibles en local ? »
- « Quelles dates sont présentes dans le stockage distant ? »
- « Compare les dates de données locales et distantes »
- « Quelles dates n'existent qu'à distance ? »

**Trois modes de requête :**

| Mode | Description | Exemple de formulation |
|------|------|---------|
| **Local** | Consulte uniquement le local | « Quelles dates sont disponibles en local ? » |
| **Distant** | Consulte uniquement le distant | « Quelles dates sont présentes à distance ? » |
| **Comparaison** | Compare les deux (par défaut) | « Compare les données locales et distantes » |

**Informations renvoyées (mode comparaison) :**

- Dates présentes uniquement en local.
- Dates présentes uniquement à distance (utile pour décider quelles dates synchroniser).
- Dates présentes des deux côtés.

---

### Q18 : Comment interpréter une expression de date en langage naturel ? (à utiliser en priorité, recommandé)

**Vous pouvez demander, par exemple :**

- « Quels jours correspondent à « cette semaine » ? »
- « À quelle plage de dates correspondent « les 7 derniers jours » ? »
- « La plage de dates du mois dernier »
- « Convertis « les 30 derniers jours » en dates précises »

**Pourquoi cet outil est-il utile ?**

Les utilisateurs emploient souvent un langage naturel comme « cette semaine » ou « les 7 derniers jours » pour exprimer des dates, mais différents modèles d'IA calculant les dates par eux-mêmes produisent des résultats incohérents. Cet outil utilise un calcul temporel précis côté serveur afin de garantir que tous les modèles d'IA obtiennent des plages de dates cohérentes.

**Expressions de date prises en charge :**

| Type | Expression en français | Expression en anglais |
|------|---------|---------|
| Jour unique | aujourd'hui, hier | today, yesterday |
| Semaine | cette semaine, la semaine dernière | this week, last week |
| Mois | ce mois, le mois dernier | this month, last month |
| N derniers jours | 7 derniers jours, 30 derniers jours | last 7 days, last 30 days |
| Dynamique | N derniers jours (nombre quelconque) | last N days |

**Avantages :**

- ✅ **Cohérence** : tous les modèles d'IA obtiennent la même plage de dates.
- ✅ **Précision** : basé sur un calcul temporel précis côté serveur.
- ✅ **Standardisation** : renvoie un format de date standard.
- ✅ **Souplesse** : prend en charge le français et l'anglais, ainsi qu'un nombre de jours dynamique.

---

## Lecture du contenu des articles

### Q19 : Comment lire le contenu intégral d'un article d'actualité ?

**Vous pouvez demander, par exemple :**

- « Lis pour moi le contenu de cette actualité : https://example.com/news/123 »
- « Récupère le corps de l'article de ce lien »
- « Lis le contenu détaillé de cet article »

**Fonction de l'outil :**

- Convertit la page web en un format Markdown propre via Jina AI Reader.
- Supprime automatiquement les publicités, barres de navigation, barres latérales et autres parasites.
- Renvoie un contenu structuré adapté aux LLM.

**Flux d'utilisation typique :**

1. Utilisez d'abord `search_news(include_url=True)` pour rechercher des actualités et obtenir des liens.
2. Utilisez ensuite `read_article(url=lien)` pour lire le corps de l'article.
3. L'IA analyse, résume ou traduit le corps Markdown.

**Informations renvoyées :**

| Champ | Description |
|------|------|
| **content** | Corps de l'article au format Markdown |
| **url** | Lien d'origine |
| **content_length** | Longueur du contenu (nombre de caractères) |

**Vous pouvez ajuster :**

- Le délai d'expiration : par exemple « fixe le délai à 60 secondes » (30 secondes par défaut, 60 secondes maximum).

**À noter :**

- Un intervalle de 5 secondes entre chaque requête (contrôle de débit intégré).
- Utilise le service gratuit Jina AI Reader (limite de 100 requêtes par minute).
- Certaines pages derrière un péage ou nécessitant une connexion peuvent ne pas être récupérées intégralement.

---

### Q20 : Comment lire plusieurs articles en lot ?

**Vous pouvez demander, par exemple :**

- « Lis pour moi le contenu de ces quelques actualités »
- « Récupère en lot le corps de ces articles »
- « Lis le contenu détaillé des 3 premiers résultats de recherche »

**Flux d'utilisation typique :**

1. Utilisez d'abord `search_news(include_url=True)` pour rechercher des actualités et obtenir plusieurs liens.
2. Utilisez ensuite `read_articles_batch(urls=[...])` pour lire les corps d'articles en lot.
3. L'IA réalise une analyse comparative et un rapport de synthèse sur plusieurs articles.

**Limites de l'outil :**

| Limite | Valeur |
|------|------|
| Nombre maximal d'articles par appel | **5** |
| Intervalle entre requêtes | **5 secondes** |
| Durée estimée (5 articles) | **25 à 30 secondes** |

**Informations renvoyées :**

| Champ | Description |
|------|------|
| **summary** | Statistiques de la lecture en lot |
| **articles** | Contenu et état de chaque article |
| **note** | Si des articles ont été ignorés, en explique la raison |

**À noter :**

- Les articles au-delà de 5 sont automatiquement ignorés.
- L'échec d'un article n'affecte pas la lecture des autres.
- Plus il y a d'articles, plus l'opération est longue : merci de patienter.

---

## Envoi de notifications

### Q21 : Comment envoyer des messages de notification via MCP ?

**Vous pouvez demander, par exemple :**

- « Affiche les canaux de notification actuellement configurés »
- « Envoie un message de test à tous les canaux »
- « Pousse ce contenu vers Feishu »
- « Envoie la synthèse des actualités du jour vers DingTalk et Telegram »

**Canaux de notification pris en charge (9) :**

| Canal | Format de message | Source de configuration |
|------|---------|---------|
| **Feishu** (feishu) | Texte brut | `FEISHU_WEBHOOK_URL` |
| **DingTalk** (dingtalk) | Markdown | `DINGTALK_WEBHOOK_URL` |
| **WeCom** (wework) | Markdown | `WEWORK_WEBHOOK_URL` |
| **Telegram** | HTML | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` |
| **Email** | HTML | `EMAIL_FROM` + `EMAIL_PASSWORD` + `EMAIL_TO` |
| **ntfy** | Markdown | `NTFY_SERVER_URL` + `NTFY_TOPIC` |
| **Bark** | Markdown | `BARK_URL` |
| **Slack** | mrkdwn | `SLACK_WEBHOOK_URL` |
| **Webhook générique** | Markdown | `GENERIC_WEBHOOK_URL` |

**Méthode de configuration :**

- Configurez les canaux correspondants dans `config.yaml`, sous `notification.channels`.
- Ou définissez les variables d'environnement correspondantes dans le fichier `.env` (priorité plus élevée).
- Les deux méthodes sont fusionnées automatiquement, les valeurs du fichier `.env` l'emportant sur celles de `config.yaml`.

**Deux outils :**

| Outil | Fonction | Exemple de formulation |
|------|------|---------|
| `get_notification_channels` | Détecte les canaux configurés et leur état | « Affiche la configuration des canaux de notification » |
| `send_notification` | Envoie un message à un canal précis ou à tous | « Envoie un message vers Feishu » |

**Flux d'utilisation typique :**

1. Consultez d'abord l'état des canaux : « Affiche les canaux de notification actuellement configurés ».
2. Une fois la disponibilité confirmée, envoyez : « Pousse le contenu suivant vers DingTalk : synthèse des tendances du jour... ».
3. Ou précisez plusieurs canaux : « Envoie vers Feishu et Telegram ».
4. Si aucun canal n'est précisé, l'envoi se fait vers tous les canaux configurés.

**Format des messages :**

- L'outil accepte un contenu de message au **format Markdown**.
- Il convertit automatiquement le format selon les exigences de chaque canal (texte brut pour Feishu, HTML pour Telegram, mrkdwn pour Slack, etc.).
- Aucune gestion manuelle des différences de format n'est nécessaire.

**Prise en charge de plusieurs comptes :**

- Séparez plusieurs URL / jetons par un `;` dans la valeur de configuration pour envoyer vers plusieurs comptes.
- Par exemple : `FEISHU_WEBHOOK_URL=url1;url2` envoie simultanément vers deux groupes Feishu.

---

## 💡 Astuces d'utilisation

### 1. Comment faire en sorte que l'IA affiche toutes les données au lieu de résumer automatiquement ?

**Contexte** : il arrive que l'IA résume automatiquement les données et n'affiche qu'une partie du contenu, même si l'outil a renvoyé l'ensemble des 50 éléments.

**Si l'IA résume malgré tout, vous pouvez** :

- **Méthode 1 - Demande explicite** : « Affiche toutes les actualités, sans résumer ».
- **Méthode 2 - Préciser le nombre** : « Affiche les 50 actualités ».
- **Méthode 3 - Remettre en question le comportement** : « Pourquoi n'en as-tu affiché que 15 ? Je veux tout voir ».
- **Méthode 4 - Préciser à l'avance** : « Interroge les actualités du jour, affiche tous les résultats en intégralité ».

**À noter** : l'IA peut tout de même adapter sa façon d'afficher en fonction du contexte.


### 2. Comment combiner plusieurs outils ?

**Exemple : analyse approfondie d'un sujet**

1. Recherchez d'abord : « Recherche les actualités sur « l'intelligence artificielle » ».
2. Analysez ensuite la tendance : « Analyse la tendance de popularité de « l'intelligence artificielle » ».
3. Terminez par l'analyse du sentiment : « Analyse le sentiment des actualités sur « l'intelligence artificielle » ».

**Exemple : suivre un événement**

1. Consultez les dernières actualités : « Interroge les actualités du jour sur « iPhone » ».
2. Recherchez l'historique : « Trouve les actualités historiques de la semaine dernière liées à « iPhone » ».
3. Trouvez des articles similaires : « Trouve les actualités similaires à « la conférence de présentation de l'iPhone » ».
