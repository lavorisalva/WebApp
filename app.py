import streamlit as st
import pandas as pd
import sqlite3
import os
import json
import subprocess
from brain import NexusBrain

st.set_page_config(page_title="SBTrading-Pro", page_icon="logo.svg", layout="wide", initial_sidebar_state="expanded")
K_FILE = ".keys"
STATE_FILE = ".state"

def save_state(**kw):
    try:
        s = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                s = json.load(f)
        s.update(kw)
        with open(STATE_FILE, "w") as f:
            json.dump(s, f)
    except:
        pass

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}

# Auto-login from saved state
saved_state = load_state()
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = saved_state.get('auto_logged_in', False)
    st.session_state['user_id'] = saved_state.get('user_id', 0)
    st.session_state['username'] = saved_state.get('username', '')
    st.session_state['login_mode'] = "login"

if not st.session_state['logged_in']:
    col_logo, col_logo2, col_logo3 = st.columns([1, 2, 1])
    with col_logo2:
        st.image("logo.svg", width=100)
        st.markdown("<h1 style='text-align:center'>SBTrading-Pro</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#888;font-size:0.8em'>made with 💚 by SBGE Studio</p>", unsafe_allow_html=True)
    brain_login = NexusBrain()
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        mode = st.session_state.get('login_mode', 'login')
        if mode == "login":
            st.markdown("<p style='text-align:center;color:#888'>Accedi con username e password</p>", unsafe_allow_html=True)
            u = st.text_input("Username", placeholder="username", key="login_user")
            p = st.text_input("Password", type="password", placeholder="password", key="login_pass")
            if st.button("Accedi", type="primary", use_container_width=True):
                uid = brain_login.login_user(u, p)
                if uid:
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = uid
                    st.session_state['username'] = u
                    save_state(auto_logged_in=True, user_id=uid, username=u)
                    st.rerun()
                else:
                    st.error("Username o password errati")
            st.divider()
            if st.button("Accedi come Guest (trades legacy)", use_container_width=True):
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = 0
                st.session_state['username'] = "Guest"
                save_state(auto_logged_in=True, user_id=0, username="Guest")
                st.rerun()
            if st.button("Registrati", use_container_width=True):
                st.session_state['login_mode'] = "register"
                st.rerun()
        else:
            st.markdown("<p style='text-align:center;color:#888'>Crea un nuovo account</p>", unsafe_allow_html=True)
            u = st.text_input("Nuovo username", placeholder="username", key="reg_user")
            p = st.text_input("Nuova password", type="password", placeholder="min 4 caratteri", key="reg_pass")
            p2 = st.text_input("Conferma password", type="password", placeholder="conferma", key="reg_pass2")
            if st.button("Crea Account", type="primary", use_container_width=True):
                if len(u) < 3: st.error("Username minimo 3 caratteri")
                elif len(p) < 4: st.error("Password minimo 4 caratteri")
                elif p != p2: st.error("Le password non coincidono")
                elif brain_login.register_user(u, p):
                    st.success("Account creato! Ora accedi.")
                    st.session_state['login_mode'] = "login"
                    st.rerun()
                else:
                    st.error("Username gia' esistente")
            if st.button("Torna al login", use_container_width=True):
                st.session_state['login_mode'] = "login"
                st.rerun()
    st.stop()

# ---- CSS migliorato ----
st.markdown("""
<style>
    .buy-btn { background-color: #00c853; color: white; padding: 10px 25px; border-radius: 8px; font-weight: bold; }
    .sell-btn { background-color: #ff1744; color: white; padding: 10px 25px; border-radius: 8px; font-weight: bold; }
    .badge-open { background-color: #ffa726; color: #333; padding: 2px 10px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    .badge-win { background-color: #00c853; color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    .badge-loss { background-color: #ff1744; color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    .big-price { font-size: 2em; font-weight: bold; margin: 0; }
    .big-label { font-size: 0.9em; color: #888; margin: 0; }

</style>
""", unsafe_allow_html=True)

def load_k():
    # Lettura da Streamlit Cloud secrets (se disponibile)
    try:
        sec = st.secrets.get("config", {})
        if sec.get("api_key"):
            return [sec.get("api_key",""), sec.get("binance_key",""), sec.get("binance_secret",""),
                    sec.get("api_base_url","https://opencode.ai/zen/v1"), "", "", ""]
    except:
        pass
    # Fallback locale: file .keys
    if os.path.exists(K_FILE):
        lines = open(K_FILE, "r").read().splitlines()
        return (lines + ["","","","","","",""])[:7]
    return ["","","","","","",""]

def format_trade(row):
    status = row['status']
    pnl = row.get('profit_perc', 0)
    if status == 'APERTO':
        badge = '<span class="badge-open">APERTO</span>'
    elif pnl > 0:
        badge = f'<span class="badge-win">+{pnl:.1f}%</span>'
    else:
        badge = f'<span class="badge-loss">{pnl:.1f}%</span>'
    return badge

st.title("SBTrading-Pro")
st.caption("Trading crypto con AI · Trading manuale · Portafoglio Web3  —  made with 💚 by SBGE Studio")

# ---- Sidebar ----
st.sidebar.image("logo.svg", width=40)
st.sidebar.markdown("**SBTrading-Pro** <span style='color:#888;font-size:0.7em'>by SBGE Studio</span>", unsafe_allow_html=True)
st.sidebar.divider()

st.sidebar.header("Configurazione")
c_ai, c_bk, c_bs, c_url, c_proxy, c_tg_tok, c_tg_chat = load_k()

okey = st.sidebar.text_input("Chiave API", value=c_ai, type="password",
                              help="Opencode Zen / OpenAI / provider compatibile")
default_url = "https://opencode.ai/zen/v1" if c_ai and c_ai.startswith("sk-") else ""
api_url = st.sidebar.text_input("API Base URL", value=c_url or default_url,
                                 help="Default OpenAI. Opencode Zen: https://opencode.ai/zen/v1")
bkey = st.sidebar.text_input("Chiave Binance", value=c_bk)
bsec = st.sidebar.text_input("Segreto Binance", value=c_bs, type="password")

tg_token_saved = st.session_state.get('_tg_token', '')
tg_chat_saved = st.session_state.get('_tg_chat', '')
proxy_saved = st.session_state.get('_proxy', '')

if st.sidebar.button("Salva Config"):
    _p = st.session_state.get('proxy_url', c_proxy) or ''
    _t = st.session_state.get('tg_token', c_tg_tok) or ''
    _c = st.session_state.get('tg_chat', c_tg_chat) or ''
    with open(K_FILE, "w") as f:
        f.write(f"{okey}\n{bkey}\n{bsec}\n{api_url}\n{_p}\n{_t}\n{_c}")
    st.sidebar.success("Configurazione salvata!")

brain = NexusBrain()
brain.set_config(okey, bkey, bsec, api_url if api_url else None)
if c_proxy:
    brain.set_proxy(c_proxy)
if c_tg_tok and c_tg_chat:
    brain.set_telegram(c_tg_tok, c_tg_chat)

# Proxy
with st.sidebar.expander("Proxy"):
    proxy_url = st.text_input("Proxy URL", value=c_proxy, placeholder="http://user:pass@ip:port", key="proxy_url")
    if st.button("Applica Proxy", use_container_width=True):
        brain.set_proxy(proxy_url.strip() if proxy_url else None)
        _s = open(K_FILE, "w")
        _s.write(f"{okey}\n{bkey}\n{bsec}\n{api_url}\n{proxy_url.strip() if proxy_url else ''}\n{c_tg_tok}\n{c_tg_chat}")
        _s.close()
        st.success("Proxy configurato e salvato!")

# Telegram
with st.sidebar.expander("Telegram"):
    tg_token = st.text_input("Bot Token", value=c_tg_tok, type="password", placeholder="123:ABC...", key="tg_token")
    tg_chat = st.text_input("Chat ID", value=c_tg_chat, placeholder="-100123456789", key="tg_chat")
    if st.button("Salva Telegram", use_container_width=True):
        _tt = tg_token.strip() if tg_token else ''
        _tc = tg_chat.strip() if tg_chat else ''
        _pp = st.session_state.get('proxy_url', c_proxy) or ''
        brain.set_telegram(_tt or None, _tc or None)
        _s = open(K_FILE, "w")
        _s.write(f"{okey}\n{bkey}\n{bsec}\n{api_url}\n{_pp}\n{_tt}\n{_tc}")
        _s.close()
        st.success("Telegram configurato e salvato!")
        if _tt and _tc:
            brain.send_telegram("✅ <b>SBTrading-Pro</b> connesso!")

mode = st.sidebar.radio("Modalita", ["Paper Trading", "Real Trading"])
daemon_running = load_state().get('daemon_running', False)
if 'auto_exec' not in st.session_state:
    st.session_state['auto_exec'] = False
if daemon_running:
    st.session_state['auto_exec'] = True
st.sidebar.checkbox("Esecuzione automatica AI", key="auto_exec",
                    help="Se attivo, esegue e registra automaticamente i trade analizzati dall'AI")
auto_exec = daemon_running or st.session_state['auto_exec']

# Info utente
st.sidebar.divider()
st.sidebar.markdown(f"👤 <b>{st.session_state.get('username','')}</b>", unsafe_allow_html=True)

# Portafoglio virtuale (Paper Trading)
uid = st.session_state['user_id']
bal = brain.get_portfolio_balance(uid) if uid else 0
if mode == "Paper Trading" and uid:
    st.sidebar.metric("Portafoglio Virtuale", f"${bal:,.2f}")
    with st.sidebar.expander("Gestione Portafoglio"):
        new_bal = st.number_input("Nuovo saldo iniziale", min_value=100, max_value=1000000, value=1000, step=100)
        if st.button("Imposta Saldo"):
            brain.init_portfolio(uid, new_bal)
            st.success(f"Saldo impostato a ${new_bal}")
            st.rerun()

if st.sidebar.button("Logout"):
    save_state(auto_logged_in=False)
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = 0
    st.session_state['username'] = ""
    st.rerun()

# ---- Inizializzazione stati ----
for key, default in [('mods', []), ('ai_res', None), ('ai_prc', 0), ('ai_rsi', 50)]:
    if key not in st.session_state:
        st.session_state[key] = default
if 'tiks' not in st.session_state:
    st.session_state['tiks'] = brain.get_tickers()

# ---- Sidebar: Coppia e Modello ----
sym = st.sidebar.selectbox("Coppia", st.session_state.get('tiks', ["BTC/USDT"]), key="sym_select")

if st.sidebar.button("Aggiorna Modelli"):
    with st.sidebar:
        with st.spinner("Recupero modelli..."):
            found = brain.get_available_models()
            if found:
                st.session_state['mods'] = found
                st.success(f"{len(found)} modelli trovati!")
                st.rerun()
            else:
                st.error("Nessun modello trovato. Inserisci manualmente.")

custom_model = st.sidebar.text_input("Modello (override)", placeholder="lascia vuoto per usare lista")
mods_list = st.session_state.get('mods', [])
if custom_model:
    mod = custom_model
elif mods_list:
    mod = st.sidebar.selectbox("Modello disponibile", mods_list, key="mod_select")
else:
    mod = st.sidebar.text_input("Modello", value="big-pickle", key="mod_manual")

# Bot Daemon (background trading) — solo in locale
is_cloud = not os.path.exists(K_FILE)
if not is_cloud:
    st.sidebar.divider()
    if daemon_running:
        st.sidebar.success("🤖 Bot Daemon ATTIVO (background)")
        if st.sidebar.button("Ferma Bot", type="secondary"):
            save_state(daemon_running=False)
            st.rerun()
    else:
        if st.sidebar.button("Avvia Bot (background)", type="primary"):
            save_state(daemon_running=True, user_id=uid, username=st.session_state['username'],
                      api_key=okey, model=mod, proxy=c_proxy,
                      tg_token=c_tg_tok, tg_chat=c_tg_chat)
            python = r"C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe"
            log = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "daemon.log"), "w")
            subprocess.Popen([python, "bot_daemon.py"], cwd=os.path.dirname(os.path.abspath(__file__)),
                            stdout=log, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
            st.success("Bot avviato in background!")
            st.rerun()

# ---- TAB ORGANIZZATIVI ----
TAB_TRADING, TAB_PORTFOLIO, TAB_WALLET = st.tabs(["Trading", "Portafoglio", "Wallet"])

# ========================================================
# TAB 1: Trading (AI + Manuale)
# ========================================================
with TAB_TRADING:
    col_left, col_right = st.columns([1, 1])
    with col_left:
        with st.container(border=True):
            st.subheader("Analisi Automatica AI")
            if st.button("Avvia Analisi AI", type="primary", use_container_width=True):
                if not okey:
                    st.error("Inserisci la chiave API!")
                elif not mod:
                    st.error("Inserisci un modello valido!")
                else:
                    with st.spinner(f"Analisi {sym} in corso..."):
                        res, prc, rsi = brain.decide_trade(sym, mod)
                        st.session_state['ai_res'] = res
                        st.session_state['ai_prc'] = prc
                        st.session_state['ai_rsi'] = rsi
                    st.rerun()
            if st.session_state.get('ai_res'):
                res = st.session_state['ai_res']
                prc = st.session_state['ai_prc']
                rsi = st.session_state['ai_rsi']
                if res['azione'] == "ERRORE":
                    st.error(res['ragionamento'])
                    del st.session_state['ai_res']
                else:
                    col_a, col_b = st.columns(2)
                    col_a.metric("Prezzo", f"{prc:,.2f} $")
                    col_b.metric("RSI", f"{rsi:.1f}")
                    az = res['azione']
                    emoji = {"COMPRA":" BUY", "VENDI":" SELL", "ATTENDI":" HOLD"}
                    st.subheader(f"{emoji.get(az, '')} {az}")
                    st.caption(res.get('ragionamento', ''))
                    if az in ("COMPRA", "VENDI"):
                        st.info(f"SL: {res.get('stop_loss',0):,.2f} | TP: {res.get('take_profit',0):,.2f}")
                        if mode == "Real Trading":
                            with st.spinner("Ordine in esecuzione..."):
                                order = brain.execute_real_order(sym, az)
                                if order:
                                    st.success(f"Ordine eseguito! ID: {order['id']}")
                                else:
                                    st.error("Errore ordine reale.")
                        trade_amt = max(10, int(bal * 0.1)) if mode == "Paper Trading" and uid else 20
                        if auto_exec:
                            brain.save_trade(sym, mode, res, prc, mod, st.session_state['user_id'], trade_amt)
                            del st.session_state['ai_res']
                            st.success(f"Trade eseguito automaticamente! (${trade_amt})")
                            st.rerun()
                        else:
                            col_conf1, col_conf2 = st.columns(2)
                            with col_conf1:
                                if st.button("Conferma e registra", use_container_width=True, type="primary"):
                                    brain.save_trade(sym, mode, res, prc, mod, st.session_state['user_id'], trade_amt)
                                    del st.session_state['ai_res']
                                    st.success("Trade registrato!")
                                    st.rerun()
                            with col_conf2:
                                if st.button("Annulla", use_container_width=True):
                                    del st.session_state['ai_res']
                                    st.rerun()
                    else:
                        st.info("Nessuna azione consigliata.")
                        if auto_exec:
                            del st.session_state['ai_res']
                            st.rerun()
                        elif st.button("OK", use_container_width=True):
                            del st.session_state['ai_res']
                            st.rerun()
    with col_right:
        with st.container(border=True):
            st.subheader("Trading Manuale")
            col_amt, col_sl, col_tp = st.columns(3)
            amt = col_amt.number_input("Importo (USDT)", min_value=5.0, max_value=100000.0, value=20.0, step=5.0, key="manual_amt")
            try:
                curr_price = brain.exchange.fetch_ticker(sym)['last']
                sl_default = float(round(curr_price * 0.95, 2))
                tp_default = float(round(curr_price * 1.05, 2))
            except:
                curr_price = 0.0; sl_default = 0.0; tp_default = 0.0
            sl_price = col_sl.number_input("SL (USDT)", min_value=0.0, value=sl_default, step=1.0, key="manual_sl", format="%.2f")
            tp_price = col_tp.number_input("TP (USDT)", min_value=0.0, value=tp_default, step=1.0, key="manual_tp", format="%.2f")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("COMPRA", use_container_width=True, type="primary"):
                    try: current_price = brain.exchange.fetch_ticker(sym)['last']
                    except: current_price = 0
                    trade_data = {"azione":"COMPRA","stop_loss":sl_price,"take_profit":tp_price,"ragionamento":"Manuale"}
                    if mode == "Real Trading" and bkey:
                        with st.spinner("Ordine in corso..."):
                            o = brain.execute_real_order(sym, "COMPRA", amt)
                            if o: st.success(f"Acquisto eseguito! ID: {o['id']}")
                            else: st.error("Errore ordine.")
                    else:
                        brain.save_trade(sym, mode, trade_data, current_price or amt, mod, st.session_state['user_id'], amt)
                        st.success(f"Acquisto manuale registrato! (${amt})")
            with col_b2:
                if st.button("VENDI", use_container_width=True, type="secondary"):
                    try: current_price = brain.exchange.fetch_ticker(sym)['last']
                    except: current_price = 0
                    trade_data = {"azione":"VENDI","stop_loss":tp_price,"take_profit":sl_price,"ragionamento":"Manuale"}
                    if mode == "Real Trading" and bkey:
                        with st.spinner("Ordine in corso..."):
                            o = brain.execute_real_order(sym, "VENDI", amt)
                            if o: st.success(f"Vendita eseguita! ID: {o['id']}")
                            else: st.error("Errore ordine.")
                    else:
                        brain.save_trade(sym, mode, trade_data, current_price or amt, mod, st.session_state['user_id'], amt)
                        st.success(f"Vendita manuale registrata! (${amt})")

# ========================================================
# TAB 2: Portafoglio Trades
# ========================================================
with TAB_PORTFOLIO:
    uid = st.session_state['user_id']
    if st.button("Aggiorna Portafoglio", use_container_width=True):
        brain.check_and_close_trades(mod, uid)
    brain.check_and_close_trades(mod, uid)
    try:
        conn = sqlite3.connect('nexus_memory.db')
        df = pd.read_sql_query("SELECT * FROM trades WHERE user_id=? ORDER BY id DESC", conn, params=(uid,))
        conn.close()
        if not df.empty:
            total = len(df); aperti = len(df[df['status'] == 'APERTO'])
            chiusi_vinti = len(df[(df['status'] == 'CHIUSO') & (df['profit_perc'] > 0)])
            chiusi_persi = len(df[(df['status'] == 'CHIUSO') & (df['profit_perc'] <= 0)])
            met_a, met_b, met_c, met_d = st.columns(4)
            met_a.metric("Totale Trades", total)
            met_b.metric("Aperti", aperti, delta_color="off")
            met_c.metric("Vinti", chiusi_vinti, delta=f"+{chiusi_vinti}")
            met_d.metric("Persi", chiusi_persi, delta=f"-{chiusi_persi}", delta_color="inverse")
            st.divider()
            for _, row in df.iterrows():
                badge = format_trade(row)
                reason = row.get('reasoning', '') or ''
                close_reason = reason.split("Chiuso:")[-1].strip() if "Chiuso:" in reason else ""
                azione = row.get('azione', '') or ''
                color = "#00c853" if azione == "COMPRA" else "#ff1744" if azione == "VENDI" else "#888"
                arrow = azione if azione in ("COMPRA","VENDI") else ""
                with st.container(border=True):
                    cols = st.columns([2, 1.2, 1.5, 1.5, 1.2])
                    cols[0].markdown(f"**{row['symbol']}** {badge}", unsafe_allow_html=True)
                    cols[1].markdown(f"<span style='color:{color};font-weight:bold'>{arrow}</span>", unsafe_allow_html=True)
                    cols[2].markdown(f"<span style='font-size:0.85em'>{row['timestamp'][:19]}</span>", unsafe_allow_html=True)
                    cols[3].markdown(f"<span class='big-label'>Entry</span><br><b>{row['entry_price']:,.2f}</b>", unsafe_allow_html=True)
                    if row['status'] == 'CHIUSO' and row['profit_perc']:
                        pnl_color = "#00c853" if row['profit_perc'] > 0 else "#ff1744"
                        h = f"<span style='color:{pnl_color};font-weight:bold'>{row['profit_perc']:+.2f}%</span>"
                        if close_reason: h += f"<br><span style='font-size:0.65em;color:#aaa'>{close_reason}</span>"
                        cols[4].markdown(h, unsafe_allow_html=True)
        else:
            st.info("Nessun trade ancora. Avvia un'analisi AI o esegui un trade manuale!")
    except:
        st.info("In attesa del primo trade...")

# ========================================================
# TAB 3: Wallet Multi-Catena
# ========================================================
with TAB_WALLET:
    col_w1, col_w2 = st.columns([1, 1])
    with col_w1:
        st.subheader("Portafoglio Multi-Catena")
        st.caption("Leggi saldo nativo o token ERC-20")
        wallet_addr = st.text_input("Indirizzo wallet", placeholder="0x...", key="wallet_addr")
        chains_dispo = {
            "bitcoin": "BTC", "ethereum": "ETH", "bsc": "BNB",
            "polygon": "MATIC", "tron": "TRX", "xrp": "XRP",
            "dogecoin": "DOGE", "base": "ETH", "linea": "ETH"
        }
        chain = st.selectbox("Rete", list(chains_dispo.keys()), key="chain_select",
                             format_func=lambda x: f"{chains_dispo[x]} - {x.capitalize()}")
        common_tokens = brain.get_common_tokens(chain)
        token_opts = {"": "Nativo (nessun token)"}
        token_opts.update(common_tokens)
        if 'prev_chain' not in st.session_state or st.session_state['prev_chain'] != chain:
            st.session_state['prev_chain'] = chain
            st.session_state['sel_token'] = ""
            st.session_state['token_addr'] = ""
        selected_token = st.selectbox("Token", list(token_opts.keys()),
                                      format_func=lambda x: f"{x} - {token_opts[x][:6]}..." if x and token_opts.get(x) else (x if x else "Nativo"),
                                      key="sel_token")
        contract_addr = token_opts.get(selected_token, "")
        if contract_addr:
            st.session_state['token_addr'] = contract_addr
        elif st.session_state.get('token_addr', '') and st.session_state['token_addr'] != '':
            st.session_state['token_addr'] = ""
        token_addr = st.text_input("Indirizzo contratto", key="token_addr",
                                    placeholder="0x... o lascia vuoto per saldo nativo")
        token_addr_value = ""
        if token_addr and token_addr.startswith("0x"):
            token_addr_value = token_addr.strip()
        if st.button("Verifica Saldo", use_container_width=True):
            if wallet_addr:
                with st.spinner(f"Consultazione {chain}..."):
                    result = brain.get_wallet_balance(wallet_addr.strip(), chain, token_addr_value or None)
                    if result:
                        bal, ticker, usd_rate = result; usd_val = bal * usd_rate
                        label_token = selected_token or chains_dispo.get(chain, "")
                        st.metric(f"Saldo {label_token}", f"{bal:,} {ticker}")
                        if usd_val > 0: st.caption(f"~ {usd_val:,.2f} USD")
                    else: st.error("Nessun dato. Verifica indirizzo o rete.")
            else: st.warning("Inserisci un indirizzo")
    with col_w2:
        st.subheader("Saldo Exchange (Binance)")
        st.caption("Leggi il saldo dal tuo account Binance collegato")
        if bkey and bsec:
            if st.button("Aggiorna Saldo Exchange", use_container_width=True):
                with st.spinner("Recupero saldo Binance..."):
                    ex_bal = brain.get_exchange_balance()
                    if isinstance(ex_bal, dict):
                        for token, amt in sorted(ex_bal.items(), key=lambda x: x[1], reverse=True):
                            if amt > 0:
                                st.metric(token, f"{amt:.6f}".rstrip('0').rstrip('.') if amt < 1000 else f"{amt:,.2f}")
                    elif isinstance(ex_bal, str):
                        st.error(ex_bal)
                    else:
                        st.error("Inserisci le credenziali Binance nella sidebar.")
        else:
            st.info("Inserisci Chiave Binance e Segreto nella sidebar per vedere il saldo.")

st.divider()
st.caption("SBTrading-Pro · made with 💚 by SBGE Studio")
