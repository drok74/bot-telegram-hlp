# Configuration Railway

## Variables d'environnement requises

Dans votre projet Railway, allez dans **Variables** et ajoutez :

### Obligatoire :
- `TELEGRAM_BOT_TOKEN` : Votre token Telegram (obtenez-le via @BotFather)

### Optionnel :
- `VAULTS_ANALYSER_TOKEN` : Votre token vaults-analyser (si vous en avez un)

## Configuration

1. **Connectez votre repo GitHub** à Railway
2. **Ajoutez les variables d'environnement** dans l'onglet Variables
3. **Start Command** : `python hlp-notifier.py` (ou créez un Procfile)
4. **Déployez** : Railway détectera automatiquement Python et installera les dépendances

## Procfile (optionnel)

Créez un fichier `Procfile` à la racine avec :
```
worker: python hlp-notifier.py
```

## Test local

Pour tester localement avant de déployer :

```powershell
# Windows PowerShell
$env:TELEGRAM_BOT_TOKEN="votre_token_telegram"
python hlp-notifier.py
```

