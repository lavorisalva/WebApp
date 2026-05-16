# SBTrading-Pro

Trading crypto con AI, trading manuale e portafoglio Web3

made with 💚 by SBGE Studio

## Deploy su Streamlit Cloud

1. **Crea un repository su GitHub** (es. `sbtrading-pro`)
2. **Carica i file:**
```bash
git init
git add .
git commit -m "SBTrading-Pro v1.0"
git remote add origin https://github.com/TUO_USERNAME/sbtrading-pro.git
git branch -M main
git push -u origin main
```
3. **Vai su** https://streamlit.io/cloud
4. **New app** → seleziona il repo → branch `main` → file `app.py` → **Deploy**
5. **Imposta i Secrets** in Settings → Secrets:
```toml
[config]
api_key = "sk-tua-chiave-api"
api_base_url = "https://opencode.ai/zen/v1"
binance_key = "tua-chiave-binance"
binance_secret = "tuo-segreto-binance"
```

## Note
- DB SQLite viene resettato a ogni deploy (effimero)
