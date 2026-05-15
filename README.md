# Come pubblicare Nexus-Trader Pro sul web (gratis)

## 1. Crea un account GitHub
Vai su github.com e registrati.

## 2. Crea un repository
- Clicca sul "+" in alto a destra → "New repository"
- Nome: nexus-trader-web
- Scegli "Public" o "Private"
- Clicca "Create repository"

## 3. Carica i file
```bash
git init
git add .
git commit -m "Nexus-Trader Web v3.1"
git remote add origin https://github.com/TUO_USERNAME/nexus-trader-web.git
git branch -M main
git push -u origin main
```

## 4. Streamlit Cloud
- Vai su https://streamlit.io/cloud
- Accedi con GitHub
- Clicca "New app"
- Seleziona il repository nexus-trader-web
- Branch: main
- File: app.py
- Clicca "Deploy"

## 5. Configura i Secrets
Dopo il deploy, vai su:
Settings → Secrets
Incolla questo (con le tue chiavi):

```toml
[config]
api_key = "sk-tua-chiave-api"
api_base_url = "https://opencode.ai/zen/v1"
binance_key = "tua-chiave-binance"
binance_secret = "tuo-segreto-binance"
login_password = "nexus2024"
```

## Attenzione
- Il database SQLite viene resettato a ogni deploy
- Per dati persistenti, connetti PostgreSQL (supabase.com gratis)
- Non caricare secrets.toml su GitHub (e' nel .gitignore)
