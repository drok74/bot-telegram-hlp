# Bot Telegram HLP Performance Tracker

Un bot Telegram interactif qui permet aux utilisateurs de suivre leur performance dans le vault HLP d'Hyperliquid. Chaque utilisateur peut enregistrer son adresse wallet et obtenir des rapports de performance à la demande.

## 🚀 Fonctionnalités

- **Menu interactif** : Navigation facile avec des boutons inline
- **Gestion d'adresses** : Chaque utilisateur peut enregistrer sa propre adresse wallet
- **Rapports de performance** : Obtenez votre rapport HLP à tout moment avec :
  - Valeur actuelle de votre position
  - PnL quotidien (24h)
  - PnL total depuis le dépôt initial
  - Métriques du vault global (TVL, performance 24h)

## 📋 Prérequis

- Python 3.8+
- Un token de bot Telegram (obtenez-le via [@BotFather](https://t.me/BotFather))
- Optionnel : Un token API vaults-analyser.com pour des données plus complètes

## 🔧 Installation

1. Clonez le repository :
```bash
git clone https://github.com/votre-username/bot-telegram-hlp.git
cd bot-telegram-hlp
```

2. Installez les dépendances :
```bash
pip install -r requirements.txt
```

3. Configurez les variables d'environnement :
```bash
# Windows PowerShell
$env:TELEGRAM_BOT_TOKEN="votre_token_telegram"
$env:VAULTS_ANALYSER_TOKEN="votre_token_vaults_analyser"  # Optionnel

# Linux/Mac
export TELEGRAM_BOT_TOKEN="votre_token_telegram"
export VAULTS_ANALYSER_TOKEN="votre_token_vaults_analyser"  # Optionnel
```

Ou modifiez directement les variables dans `hlp-notifier.py` (lignes 12 et 17).

## 🏃 Utilisation

Lancez le bot :
```bash
python hlp-notifier.py
```

Le bot démarrera et sera prêt à recevoir des commandes sur Telegram.

## 📱 Commandes disponibles

- `/start` - Affiche le menu principal
- `/help` - Affiche l'aide
- `/report` - Génère un rapport de performance (nécessite une adresse enregistrée)

## 🔒 Sécurité

⚠️ **Important** : Ne partagez jamais votre token Telegram publiquement. Utilisez des variables d'environnement pour les tokens sensibles en production.

## 📦 Déploiement 24/7

Pour faire tourner le bot 24/7, vous pouvez utiliser :

- **Railway** : [railway.app](https://railway.app) - Recommandé, plan gratuit disponible
- **Render** : [render.com](https://render.com) - Plan gratuit avec limitations
- **Fly.io** : [fly.io](https://fly.io) - Plan gratuit généreux
- **VPS** : Serveur dédié avec systemd ou PM2

### Exemple avec Railway

1. Créez un compte sur Railway
2. Créez un nouveau projet
3. Connectez votre repository GitHub
4. Configurez les variables d'environnement dans Railway
5. Ajoutez un fichier `Procfile` :
```
worker: python hlp-notifier.py
```

## 🛠️ Structure du projet

```
bot-telegram-hlp/
├── hlp-notifier.py          # Code principal du bot
├── requirements.txt          # Dépendances Python
├── user_addresses.json       # Stockage des adresses utilisateurs (généré automatiquement)
├── SETUP_VAULTS_ANALYSER.md  # Documentation pour vaults-analyser
└── README.md                 # Ce fichier
```

## 📊 API utilisées

- **Hyperliquid API** : Récupération des données du vault HLP
- **Vaults Analyser API** : Données complètes des déposants (optionnel)
- **Telegram Bot API** : Communication avec les utilisateurs

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

## 📝 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🙏 Remerciements

- [Hyperliquid](https://hyperliquid.xyz) pour l'API
- [Vaults Analyser](https://vaults-analyser.com) pour les données complémentaires
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) pour la bibliothèque Telegram

## 📞 Support

Pour toute question ou problème, ouvrez une issue sur GitHub.

