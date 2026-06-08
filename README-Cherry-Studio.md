# TrendRadar × Cherry Studio - Guide de déploiement 🍒

> **Public visé** : utilisateurs sans aucune base en programmation
> **Client** : Cherry Studio (client GUI gratuit et open source)

---

## 📥 Étape 1 : télécharger Cherry Studio

### Utilisateurs Windows

Téléchargez depuis le site officiel : https://cherry-ai.com/
Ou téléchargez directement : [Cherry-Studio-Windows.exe](https://github.com/kangfenmao/cherry-studio/releases/latest)

### Utilisateurs Mac

Téléchargez depuis le site officiel : https://cherry-ai.com/
Ou téléchargez directement : [Cherry-Studio-Mac.dmg](https://github.com/kangfenmao/cherry-studio/releases/latest)


---

## 📦 Étape 2 : récupérer le code du projet

Pourquoi faut-il récupérer le code du projet ?

La fonction d'analyse par IA a besoin de lire les données d'actualités présentes dans le projet pour fonctionner. Que vous utilisiez GitHub Actions ou un déploiement Docker, les données générées par le robot d'exploration sont enregistrées dans le répertoire `output` du projet. Il faut donc récupérer l'intégralité du code du projet (avec ses fichiers de données) avant de configurer le serveur MCP.

Selon votre niveau technique, vous pouvez choisir l'une des méthodes suivantes :

### Méthode 1 : Git Clone (recommandée aux utilisateurs techniques)

Si vous êtes à l'aise avec Git, utilisez les commandes suivantes pour cloner le projet :

```bash
git clone https://github.com/votre-nom-utilisateur/votre-nom-de-projet.git
cd votre-nom-de-projet
```

**Avantage** :

- Une seule commande suffit pour mettre à jour les données locales à tout moment (`git pull`).

### Méthode 2 : télécharger directement l'archive ZIP (recommandée aux débutants)


1. **Ouvrez la page GitHub du projet**

   - Lien du projet : `https://github.com/votre-nom-utilisateur/votre-nom-de-projet`

2. **Téléchargez l'archive**

   - Cliquez sur le bouton vert « Code »
   - Choisissez « Download ZIP »
   - Ou ouvrez directement : `https://github.com/votre-nom-utilisateur/votre-nom-de-projet/archive/refs/heads/master.zip`


**À noter** :

- La procédure est un peu plus fastidieuse : pour les mises à jour ultérieures, il faut répéter les étapes ci-dessus puis écraser les données locales (répertoire `output`).

---

## 🚀 Étape 3 : déployer le serveur MCP en un clic

### Utilisateurs Windows

1. **Double-cliquez** sur le fichier `setup-windows.bat` du dossier du projet ; en cas de problème, lancez plutôt `setup-windows-en.bat`.
2. **Attendez la fin de l'installation.**
3. **Notez les informations de configuration affichées** (chemin de la commande et arguments).

### Utilisateurs Mac

1. **Ouvrez le Terminal** (recherchez « Terminal » dans le Launchpad).
2. **Glissez-déposez** le fichier `setup-mac.sh` du dossier du projet dans la fenêtre du Terminal.
3. **Appuyez sur Entrée.**
4. **Notez les informations de configuration affichées.**

---

## 🔧 Étape 4 : configurer Cherry Studio

### 1. Ouvrir les paramètres

Lancez Cherry Studio, puis cliquez sur le bouton ⚙️ **Paramètres** en haut à droite.

### 2. Ajouter un serveur MCP

Dans la page des paramètres, trouvez : **MCP** → cliquez sur **Ajouter**.

### 3. Renseigner la configuration (important !)

Remplissez les champs avec les informations affichées par le script d'installation précédent.

### 4. Enregistrer et activer

- Cliquez sur le bouton **Enregistrer**.
- Assurez-vous que l'interrupteur du serveur MCP, dans la liste, est en position **activée** ✅.

---

## ✅ Étape 5 : vérifier que tout fonctionne

### 1. Tester la connexion

Dans la zone de dialogue de Cherry Studio, saisissez :

```
Récupère pour moi les actualités les plus récentes
```

Ou essayez d'autres commandes de test :

```
Recherche les actualités des 3 derniers jours sur « l'intelligence artificielle »
Trouve les articles de janvier 2025 relatifs à « Tesla »
Analyse la tendance de popularité de « iPhone »
```

**Astuce** : quand vous dites « les 3 derniers jours », l'IA calcule automatiquement la plage de dates et lance la recherche.

### 2. Signes de réussite

Si la configuration est réussie, l'IA va :

- ✅ appeler les outils de TrendRadar ;
- ✅ renvoyer de vraies données d'actualités ;
- ✅ afficher les informations telles que la plateforme, le titre, le classement, etc.


---

## 🎯 Configuration avancée

### Mode HTTP (optionnel)

Si vous avez besoin d'un accès à distance ou d'un partage entre plusieurs clients, vous pouvez utiliser le mode HTTP :

#### Windows

Double-cliquez sur `start-http.bat`.

#### Mac

```bash
./start-http.sh
```

Configurez ensuite Cherry Studio ainsi :

```
Type : streamableHttp
URL : http://localhost:3333/mcp
```
