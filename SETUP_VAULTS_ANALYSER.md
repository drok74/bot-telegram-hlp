# Configuration de Vaults Analyser

Pour obtenir la liste complète des déposants et votre position dans le vault, vous devez configurer un token API depuis vaults-analyser.com.

## Étapes pour obtenir le token :

1. **Créer un compte** sur https://vaults-analyser.com
2. **Vérifier votre email** (vérifiez votre boîte de réception)
3. **Générer un token API** dans votre profil/settings
4. **Configurer le token** dans votre environnement :

### Windows PowerShell :
```powershell
$env:VAULTS_ANALYSER_TOKEN="votre_token_ici"
```

### Windows CMD :
```cmd
set VAULTS_ANALYSER_TOKEN=votre_token_ici
```

### Linux/Mac :
```bash
export VAULTS_ANALYSER_TOKEN="votre_token_ici"
```

## Documentation API :
- Base URL: `https://vaults-analyser.com/pub_api/v1`
- Endpoint depositors: `GET /depositors/{vaultAddress}`
- Documentation complète: https://vaults-analyser.com/docs

## Rate Limiting :
- 60 requêtes par 60 secondes par adresse IP

Une fois le token configuré, le bot utilisera automatiquement vaults-analyser pour récupérer votre position complète, même si vous n'êtes pas dans le top 100 des déposants.

