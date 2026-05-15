import streamlit as st
import pandas as pd
import sqlite3
import os
from brain import NexusBrain

st.set_page_config(page_title="Nexus-Trader Pro", layout="wide", initial_sidebar_state="expanded")

# ---- CSS ----
st.markdown("""
<style>
    .badge-open { background-color: #ffa726; color: #333; padding: 2px 10px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    .badge-win { background-color: #00c853; color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    .badge-loss { background-color: #ff1744; color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    .big-price { font-size: 2em; font-weight: bold; margin: 0; }
    .big-label { font-size: 0.9em; color: #888; margin: 0; }
</style>
""", unsafe_allow_html=True)

# ---- Login ----
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'app_password' not in st.session_state:
    st.session_state['app_password'] = "nexus2024"

if not st.session_state['logged_in']:
    st.markdown("<h1 style='text-align:center;margin-top:80px'>Nexus-Trader Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#888'>Accesso riservato</p>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        pwd = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Accedi", type="primary", use_container_width=True):
                if pwd == st.session_state['app_password']:
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Password errata")
        with col_b:
            if st.button("Reset Password", use_container_width=True):
                st.session_state['app_password'] = "nexus2024"
                st.success("Reset a nexus2024")
    st.stop()

# ---- Sidebar: Config manuale ----
st.sidebar.header("Configurazione")

okey = st.sidebar.text_input("Chiave API (Opencode/OpenAI)", type="password",
                              value=st.session_state.get('okey', ''),
                              help="Inserisci la tua chiave API")
st.session_state['okey'] = okey

api_url = st.sidebar.text_input("API Base URL", 
                                 value=st.session_state.get('api_url', 'https://opencode.ai/zen/v1'),
                                 help="Lascia per Opencode Zen")
st.session_state['api_url'] = api_url

bkey = st.sidebar.text_input("Chiave Binance (opzionale)", type="password",
                              value=st.session_state.get('bkey', ''))
st.session_state['bkey'] = bkey

bsec = st.sidebar.text_input("Segreto Binance (opzionale)", type="password",
                              value=st.session_state.get('bsec', ''))
st.session_state['bsec'] = bsec

brain = NexusBrain()
brain.set_config(okey, bkey, bsec, api_url if api_url else None)

# ---- Sidebar ----
st.sidebar.header("Configurazione")
st.sidebar.success("Configurazione caricata da secrets.toml")

if 'tiks' not in st.session_state:
    st.session_state['tiks'] = brain.get_tickers()
if 'mods' not in st.session_state:
    st.session_state['mods'] = []

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

mode = st.sidebar.radio("Modalita", ["Paper Trading", "Real Trading"])

# ---- COLONNE ----
col_left, col_right = st.columns([1, 1.5])

# ========================================================
# COLONNA SINISTRA
# ========================================================
with col_left:
    # --- Trading AI ---
    with st.container(border=True):
        st.subheader("Analisi AI")
        if st.button("Avvia Analisi AI", type="primary", use_container_width=True):
            if not okey:
                st.error("Chiave API mancante in secrets.toml!")
            elif not mod:
                st.error("Inserisci un modello valido!")
            else:
                with st.spinner(f"Analisi {sym}..."):
                    res, prc, rsi = brain.decide_trade(sym, mod)
                    if res['azione'] == "ERRORE":
                        st.error(res['ragionamento'])
                    else:
                        ca, cb = st.columns(2)
                        ca.metric("Prezzo", f"{prc:,.2f} $")
                        cb.metric("RSI", f"{rsi:.1f}")
                        emoji = {"COMPRA":" BUY", "VENDI":" SELL", "ATTENDI":" HOLD"}
                        st.subheader(f"{emoji.get(res['azione'],'')} {res['azione']}")
                        st.caption(res.get('ragionamento', ''))
                        if res['azione'] in ("COMPRA", "VENDI"):
                            st.info(f"SL: {res.get('stop_loss',0):,.2f} | TP: {res.get('take_profit',0):,.2f}")
                            if mode == "Real Trading":
                                with st.spinner("Ordine..."):
                                    o = brain.execute_real_order(sym, res['azione'])
                                    if o: st.success(f"Eseguito! ID: {o['id']}")
                                    else: st.error("Errore ordine")
                            if st.button("Conferma e registra"):
                                brain.save_trade(sym, mode, res, prc)
                                st.success("Trade registrato!")

    # --- Trading Manuale ---
    with st.container(border=True):
        st.subheader("Trading Manuale")
        ca, cs, ct = st.columns(3)
        amt = ca.number_input("Importo USDT", min_value=5.0, value=20.0, step=5.0, key="manual_amt")
        try:
            cp = brain.exchange.fetch_ticker(sym)['last']
            sl_d = round(cp * 0.95, 2); tp_d = round(cp * 1.05, 2)
        except:
            cp = 0.0; sl_d = 0.0; tp_d = 0.0
        sl_price = cs.number_input("Stop Loss", value=sl_d, step=1.0, key="manual_sl", format="%.2f")
        tp_price = ct.number_input("Take Profit", value=tp_d, step=1.0, key="manual_tp", format="%.2f")

        cb1, cb2 = st.columns(2)
        with cb1:
            if st.button("COMPRA", use_container_width=True, type="primary"):
                try: prc = brain.exchange.fetch_ticker(sym)['last']
                except: prc = 0
                td = {"azione":"COMPRA","stop_loss":sl_price,"take_profit":tp_price,"ragionamento":"Manuale"}
                if mode == "Real Trading":
                    with st.spinner("Ordine..."):
                        o = brain.execute_real_order(sym, "COMPRA", amt)
                        if o: st.success(f"Eseguito! ID: {o['id']}")
                        else: st.error("Errore")
                else:
                    brain.save_trade(sym, mode, td, prc or amt)
                    st.success(f"Acquisto registrato! SL={sl_price} TP={tp_price}")
        with cb2:
            if st.button("VENDI", use_container_width=True, type="secondary"):
                try: prc = brain.exchange.fetch_ticker(sym)['last']
                except: prc = 0
                td = {"azione":"VENDI","stop_loss":tp_price,"take_profit":sl_price,"ragionamento":"Manuale"}
                if mode == "Real Trading":
                    with st.spinner("Ordine..."):
                        o = brain.execute_real_order(sym, "VENDI", amt)
                        if o: st.success(f"Eseguito! ID: {o['id']}")
                        else: st.error("Errore")
                else:
                    brain.save_trade(sym, mode, td, prc or amt)
                    st.success(f"Vendita registrata! SL={tp_price} TP={sl_price}")

    # --- Wallet ---
    with st.container(border=True):
        st.subheader("Wallet Multi-Catena")
        wallet_addr = st.text_input("Indirizzo", placeholder="0x...", key="wallet_addr")
        chains = {"bitcoin":"BTC","ethereum":"ETH","bsc":"BNB","polygon":"MATIC","tron":"TRX","xrp":"XRP","dogecoin":"DOGE","base":"ETH","linea":"ETH"}
        chain = st.selectbox("Rete", list(chains.keys()), key="chain_select", format_func=lambda x: f"{chains[x]} - {x.capitalize()}")
        tokens = brain.get_common_tokens(chain)
        opts = {"": "Nativo (nessun token)"}; opts.update(tokens)
        if 'prev_chain' not in st.session_state or st.session_state['prev_chain'] != chain:
            st.session_state['prev_chain'] = chain
            st.session_state['sel_token'] = ""
            st.session_state['token_addr'] = ""
        sel_t = st.selectbox("Token", list(opts.keys()), format_func=lambda x: f"{x}" if x else "Nativo", key="sel_token")
        ca = opts.get(sel_t, "")
        if ca and st.session_state.get('token_addr') != ca:
            st.session_state['token_addr'] = ca
        st.text_input("Indirizzo contratto", key="token_addr", placeholder="0x... o vuoto per nativo")
        if st.button("Verifica Saldo", use_container_width=True):
            if wallet_addr:
                with st.spinner(f"Consultazione {chain}..."):
                    r = brain.get_wallet_balance(wallet_addr.strip(), chain, st.session_state.get('token_addr','').strip() or None)
                    if r:
                        bal, ticker, rate = r
                        st.metric(f"Saldo {sel_t or chains[chain]}", f"{bal:,} {ticker}")
                        if bal * rate > 0: st.caption(f"~ {bal*rate:,.2f} USD")
                    else:
                        st.error("Nessun dato. Verifica indirizzo o rete.")
            else:
                st.warning("Inserisci un indirizzo")

# ========================================================
# COLONNA DESTRA: Portafoglio Trades
# ========================================================
with col_right:
    if st.button("Aggiorna Portafoglio", use_container_width=True):
        brain.check_and_close_trades()
    brain.check_and_close_trades()

    try:
        conn = sqlite3.connect('nexus_memory.db')
        df = pd.read_sql_query("SELECT * FROM trades ORDER BY id DESC", conn)
        conn.close()
        if not df.empty:
            total = len(df)
            aperti = len(df[df['status'] == 'APERTO'])
            vinti = len(df[(df['status'] == 'CHIUSO') & (df['profit_perc'] > 0)])
            persi = len(df[(df['status'] == 'CHIUSO') & (df['profit_perc'] <= 0)])
            ma, mb, mc, md = st.columns(4)
            ma.metric("Totale", total)
            mb.metric("Aperti", aperti)
            mc.metric("Vinti", vinti, delta=f"+{vinti}")
            md.metric("Persi", persi, delta=f"-{persi}", delta_color="inverse")
            st.divider()
            for _, row in df.iterrows():
                az = row.get('azione','') or ''
                cor = "#00c853" if az == "COMPRA" else "#ff1744" if az == "VENDI" else "#888"
                arr = az if az in ("COMPRA","VENDI") else ""
                badge = row['status']
                if badge == 'APERTO': b = '<span class="badge-open">APERTO</span>'
                elif row['profit_perc'] > 0: b = f'<span class="badge-win">+{row["profit_perc"]:.1f}%</span>'
                else: b = f'<span class="badge-loss">{row["profit_perc"]:.1f}%</span>'
                with st.container(border=True):
                    cols = st.columns([2, 1.5, 1.5, 1.5, 1])
                    cols[0].markdown(f"**{row['symbol']}** {b}", unsafe_allow_html=True)
                    cols[1].markdown(f"<span style='color:{cor};font-weight:bold'>{arr}</span>", unsafe_allow_html=True)
                    cols[2].markdown(f"<span style='font-size:0.9em'>{row['timestamp'][:19]}</span>", unsafe_allow_html=True)
                    cols[3].markdown(f"<b>{row['entry_price']:,.2f}</b>", unsafe_allow_html=True)
                    if row['status'] == 'CHIUSO' and row['profit_perc']:
                        pc = "#00c853" if row['profit_perc'] > 0 else "#ff1744"
                        cols[4].markdown(f"<span style='color:{pc};font-weight:bold'>{row['profit_perc']:+.2f}%</span>", unsafe_allow_html=True)
        else:
            st.info("Nessun trade. Avvia analisi o fai un trade manuale!")
    except:
        st.info("In attesa del primo trade...")

st.divider()
st.caption("Nexus-Trader v3.1 Web - AI + Manuale + Wallet")
st.caption("Dati su SQLite (ephemeral sul cloud). Usa PostgreSQL per persistenza.")
