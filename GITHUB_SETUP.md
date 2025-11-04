# Instructions pour créer le dépôt GitHub

## 📋 Étapes pour publier sur GitHub

### 1. Créer le dépôt sur GitHub

1. Allez sur [github.com](https://github.com) et connectez-vous
2. Cliquez sur le bouton **"+"** en haut à droite → **"New repository"**
3. Remplissez les informations :
   - **Repository name** : `bot-telegram-hlp` (ou le nom de votre choix)
   - **Description** : `Bot Telegram interactif pour suivre la performance HLP d'Hyperliquid`
   - **Visibilité** : Choisissez Public ou Private
   - ⚠️ **NE COCHEZ PAS** "Initialize this repository with a README" (on a déjà un README)
4. Cliquez sur **"Create repository"**

### 2. Connecter votre dépôt local à GitHub

Après avoir créé le dépôt, GitHub vous donnera des commandes. Utilisez celles qui correspondent à votre situation :

**Si vous avez déjà des commits (notre cas) :**

```bash
git remote add origin https://github.com/VOTRE_USERNAME/bot-telegram-hlp.git
git branch -M main
git push -u origin main
```

Remplacez `VOTRE_USERNAME` par votre nom d'utilisateur GitHub.

### 3. Alternative : Utiliser SSH

Si vous préférez utiliser SSH :

```bash
git remote add origin git@github.com:VOTRE_USERNAME/bot-telegram-hlp.git
git branch -M main
git push -u origin main
```

### 4. Vérification

Après avoir poussé le code, allez sur votre dépôt GitHub. Vous devriez voir tous vos fichiers.

## 🔐 Sécurité

⚠️ **Important** : Le fichier `.gitignore` exclut automatiquement :
- `user_addresses.json` (données utilisateurs)
- Les fichiers `.env` (variables d'environnement)
- Les fichiers de cache Python

Cependant, si vous avez des tokens hardcodés dans le code, vous devriez :
1. Les retirer du code
2. Utiliser des variables d'environnement
3. Créer un fichier `.env.example` pour documenter les variables nécessaires

## 📝 Commandes utiles

### Ajouter des modifications
```bash
git add .
git commit -m "Description de vos modifications"
git push
```

### Voir l'état du dépôt
```bash
git status
```

### Voir l'historique
```bash
git log
```

