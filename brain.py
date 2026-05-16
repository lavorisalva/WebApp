import sqlite3
import pandas as pd
import ta
import ccxt
import requests
import datetime
import json
import re
from openai import OpenAI
from news_fetcher import get_latest_crypto_news

class NexusBrain:
    SYMBOL_TO_CG = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple",
                     "ADA": "cardano", "DOGE": "dogecoin", "DOT": "polkadot", "MATIC": "matic-network",
                     "SHIB": "shiba-inu", "AVAX": "avalanche-2", "LINK": "chainlink", "UNI": "uniswap",
                     "ATOM": "cosmos", "XLM": "stellar", "VET": "vechain", "FIL": "filecoin",
                     "ALGO": "algorand", "MANA": "decentraland", "SAND": "the-sandbox", "APE": "apecoin",
                     "NEAR": "near", "APT": "aptos", "ARB": "arbitrum", "OP": "optimism",
                     "AAVE": "aave", "CRV": "curve-dao-token", "SNX": "synthetix-network-token",
                     "COMP": "compound-governance-token", "MKR": "maker", "YFI": "yearn-finance",
                     "AXS": "axie-infinity", "CHZ": "chiliz", "FTM": "fantom", "EGLD": "elrond-erd-2",
                     "ICP": "internet-computer", "HNT": "helium", "NEO": "neo", "KSM": "kusama",
                     "LTC": "litecoin", "BCH": "bitcoin-cash", "EOS": "eos", "TRX": "tron",
                     "XMR": "monero", "DASH": "dash", "ETC": "ethereum-classic", "ZEC": "zcash"}
    COINGECKO_IDS = {"ethereum":"ethereum","bsc":"binancecoin","polygon":"matic-network",
                     "base":"ethereum","linea":"ethereum","bitcoin":"bitcoin",
                     "tron":"tron","xrp":"ripple","dogecoine":"dogecoin"}
    CG_PLATFORMS = {"ethereum":"ethereum","bsc":"binance-smart-chain","polygon":"polygon-pos"}
    RPC_MAP = {
        "ethereum": ["https://eth.llamarpc.com", "https://rpc.ankr.com/eth"],
        "bsc": ["https://bsc.publicnode.com", "https://rpc.ankr.com/bsc"],
        "polygon": ["https://polygon-rpc.com", "https://rpc.ankr.com/polygon"],
        "base": ["https://mainnet.base.org", "https://base-rpc.publicnode.com"],
        "linea": ["https://rpc.linea.build", "https://linea-rpc.publicnode.com"],
    }

    def __init__(self, db_path='nexus_memory.db'):
        self.db_path = db_path
        self._init_db()
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.client = None
        self.w3 = None
        self.proxy_url = None
        self.tg_token = None
        self.tg_chat_id = None
        self._price_cache = {}

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME, symbol TEXT, mode TEXT, azione TEXT,
                entry_price REAL, stop_loss REAL, take_profit REAL,
                reasoning TEXT, profit_perc REAL DEFAULT 0, status TEXT DEFAULT 'APERTO')''')
            conn.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE, password TEXT, created_at DATETIME)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS portfolio (
                user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 1000, created_at DATETIME)''')
            for col, typ in [("azione","TEXT"),("entry_time","TEXT"),
                             ("highest_price","REAL DEFAULT 0"),("last_ai_check","TEXT"),
                             ("ai_check_count","INTEGER DEFAULT 0"),("model_used","TEXT"),
                             ("user_id","INTEGER DEFAULT 0"),("amount_usdt","REAL DEFAULT 20")]:
                try:
                    conn.execute(f"ALTER TABLE trades ADD COLUMN {col} {typ}")
                except:
                    pass

    def _rpc_call(self, chain, method, params):
        for rpc in self.RPC_MAP.get(chain, []):
            try:
                r = requests.post(rpc, json={"jsonrpc":"2.0","method":method,"params":params,"id":1}, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    if 'result' in data:
                        return data['result']
            except:
                continue
        return None

    def _cg_symbol(self, symbol):
        base = symbol.split('/')[0]
        return self.SYMBOL_TO_CG.get(base, base.lower())

    def _bn_symbol(self, symbol):
        return symbol.replace('/', '')

    def _fetch_coin_price(self, symbol):
        try:
            return self.exchange.fetch_ticker(symbol)['last']
        except:
            pass
        bn_pair = self._bn_symbol(symbol)
        sources = [
            f"https://api.binance.com/api/v3/ticker/price?symbol={bn_pair}",
            f"https://api.binance.us/api/v3/ticker/price?symbol={bn_pair}",
            f"https://api1.binance.com/api/v3/ticker/price?symbol={bn_pair}",
        ]
        for url in sources:
            try:
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    return float(r.json()['price'])
            except:
                pass
        try:
            cg_id = self._cg_symbol(symbol)
            r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=usd", timeout=5)
            if r.status_code == 200:
                return r.json().get(cg_id, {}).get('usd', 0)
        except:
            pass
        return 0

    def _fetch_coin_ohlcv(self, symbol):
        try:
            return self.exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        except:
            pass
        bn_pair = self._bn_symbol(symbol)
        klines_sources = [
            f"https://api.binance.com/api/v3/klines?symbol={bn_pair}&interval=1h&limit=50",
            f"https://api1.binance.com/api/v3/klines?symbol={bn_pair}&interval=1h&limit=50",
            f"https://api.binance.us/api/v3/klines?symbol={bn_pair}&interval=1h&limit=50",
        ]
        for url in klines_sources:
            try:
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    return [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in r.json()]
            except:
                pass
        return []

    def _fetch_price(self, coin_id):
        if coin_id in self._price_cache:
            return self._price_cache[coin_id]
        try:
            r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd", timeout=8)
            if r.status_code == 200:
                price = r.json().get(coin_id, {}).get('usd', 0)
                if price:
                    self._price_cache[coin_id] = price
                    return price
        except:
            pass
        return 0

    def _fetch_token_price(self, chain, contract):
        plat = self.CG_PLATFORMS.get(chain)
        if not plat or contract in self._price_cache:
            return self._price_cache.get(contract, 0)
        try:
            r = requests.get(f"https://api.coingecko.com/api/v3/simple/token_price/{plat}?contract_addresses={contract}&vs_currencies=usd", timeout=8)
            if r.status_code == 200:
                price = r.json().get(contract.lower(), {}).get('usd', 0)
                if price:
                    self._price_cache[contract] = price
                    return price
        except:
            pass
        return 0

    def _read_token_decimals(self, chain, contract):
        data = self._rpc_call(chain, "eth_call", [{"to": contract, "data": "0x313ce567"}, "latest"])
        if data and data != '0x':
            return int(data, 16)
        return 18

    def set_config(self, api_key, bk=None, bs=None, base_url=None):
        if api_key:
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = OpenAI(**kwargs)
        else:
            self.client = None
        if bk and bs: 
            self.exchange.apiKey = bk.strip()
            self.exchange.secret = bs.strip()

    def set_proxy(self, proxy_url):
        self.proxy_url = proxy_url
        if proxy_url:
            self.exchange.proxies = {'http': proxy_url, 'https': proxy_url}
        else:
            self.exchange.proxies = {}

    def set_telegram(self, token, chat_id):
        self.tg_token = token
        self.tg_chat_id = chat_id

    def send_telegram(self, message):
        if not self.tg_token or not self.tg_chat_id:
            return
        try:
            requests.get(f"https://api.telegram.org/bot{self.tg_token}/sendMessage",
                         params={"chat_id": self.tg_chat_id, "text": message, "parse_mode": "HTML"},
                         timeout=8, proxies=self.exchange.proxies if self.exchange.proxies else None)
        except:
            pass

    def register_user(self, username, password):
        with sqlite3.connect(self.db_path) as conn:
            try:
                cur = conn.execute("INSERT INTO users (username, password, created_at) VALUES (?,?,?)",
                                   (username, password, datetime.datetime.now()))
                uid = cur.lastrowid
                conn.execute("INSERT OR IGNORE INTO portfolio (user_id, balance, created_at) VALUES (?,?,?)",
                            (uid, 1000, datetime.datetime.now()))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def login_user(self, username, password):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT id FROM users WHERE username=? AND password=?",
                               (username, password)).fetchone()
            if row:
                return row[0]
            # Crea utente admin se primo accesso
            if not conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
                conn.execute("INSERT INTO users (username, password, created_at) VALUES (?,?,?)",
                             ("admin", "admin", datetime.datetime.now()))
                conn.commit()
                if username == "admin" and password == "admin":
                    return 1
            return None

    def get_tickers(self):
        try:
            self.exchange.load_markets()
            tiks = [m for m in self.exchange.markets if m.endswith('/USDT') and 'UP/' not in m and 'DOWN/' not in m]
            return sorted(tiks)
        except:
            return ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    def get_available_models(self):
        if not self.client:
            return []
        try:
            models = self.client.models.list()
            return sorted([m.id for m in models])
        except Exception as e:
            print(f"DEBUG: Errore recupero modelli: {e}")
            return []

    @staticmethod
    def get_common_tokens(chain):
        """Indirizzi contratti dei token piu comuni per ogni rete"""
        tokens = {
            "ethereum": {
                "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
                "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
                "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
                "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            },
            "bsc": {
                "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
                "USDT": "0x55d398326f99059fF775485246999027B3197955",
                "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
                "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
            },
            "polygon": {
                "USDC": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
                "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
                "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
                "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
                "LINK": "0x53E0bca35eC356BD5ddDFebbD1Fc0fD03FaBad39",
                "SG": "0x79375C41d88F839f551457145066096C5C8944Bc",
            },
            "base": {
                "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "USDT": "0xfde4C96cC8596E55a777F4bD8F6e7E5FbF8b1F8",
                "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
                "AERO": "0x940181a94A35A4569E4529A3CDfB74e38FD98635",
                "WETH": "0x4200000000000000000000000000000000000006",
            },
            "linea": {
                "USDC": "0x176211869cA2b568f2A7D4EE941E073a821EE1ff",
                "USDT": "0xA219439258ca9da29E9Cc4cE5596924745e12B93",
                "DAI": "0x4AF15ec2A0BD43Db75dd04E62FAA3B8EF36b00d5",
                "WETH": "0xe5D7C2a44FfDDf6b295A15c148167daaAf5Cf34f",
                "WBTC": "0x3aAB2285ddcDdaD8edf438C1bAB47e1a9D05a9b4",
            },
        }
        return tokens.get(chain, {})

    def _extract_json(self, text):
        """Estrae il primo oggetto JSON valido da un testo, gestendo {} annidati"""
        stack = []
        for i, ch in enumerate(text):
            if ch == '{':
                stack.append(i)
            elif ch == '}':
                if stack:
                    start = stack.pop()
                    if not stack:  # Trovato l'oggetto JSON più esterno
                        try:
                            return json.loads(text[start:i+1])
                        except:
                            continue
        return None

    def decide_trade(self, symbol, model_id):
        if not self.client:
            return {"azione": "ERRORE", "ragionamento": "Chiave API mancante"}, 0, 0
        price = self._fetch_coin_price(symbol)
        if price == 0:
            return {"azione": "ERRORE", "ragionamento": "Prezzo non disponibile"}, 0, 0
        ohlcv = self._fetch_coin_ohlcv(symbol)
        try:
            df = pd.DataFrame(ohlcv, columns=['t', 'o', 'h', 'l', 'c', 'v'])
            rsi = float(ta.momentum.rsi(df['c'], window=14).iloc[-1])
        except:
            rsi = 50

        news = " | ".join(get_latest_crypto_news()[:5])
        prompt = f"""Dati: {symbol} a {price}$, RSI {rsi:.2f}. News: {news}.
Rispondi con JSON: {{"azione":"COMPRA","stop_loss":{price*0.95:.2f},"take_profit":{price*1.05:.2f},"ragionamento":"..."}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            msg = response.choices[0].message
            raw = msg.content or getattr(msg, 'reasoning_content', '') or ''
            print(f"DEBUG AI: {raw[:300]}")
            
            clean = re.sub(r'```json|```|`', '', raw).strip()
            parsed = self._extract_json(clean)
            if parsed:
                return parsed, price, rsi
            return {"azione": "ERRORE", "ragionamento": f"Risposta: {raw[:150]}"}, price, rsi
        except Exception as e:
            err = str(e)
            if "Connection" in err or "connect" in err or "timeout" in err:
                try:
                    base = str(self.client.base_url).rstrip('/')
                    if not base.endswith('/v1'):
                        base = self.client._base_url or "https://opencode.ai/zen/v1"
                    url = f"{base}/chat/completions"
                    ak = self.client.api_key or self.client._api_key or ""
                    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {ak}"}
                    payload = {"model": model_id, "messages": [{"role": "user", "content": prompt}],
                               "temperature": 0.1, "max_tokens": 2000}
                    proxies = self.exchange.proxies if self.exchange.proxies else None
                    r = requests.post(url, json=payload, headers=headers, timeout=30, proxies=proxies)
                    if r.status_code == 200:
                        data = r.json()
                        msg = data['choices'][0]['message']
                        raw = msg.get('content', '') or msg.get('reasoning_content', '') or ''
                        clean = re.sub(r'```json|```|`', '', raw).strip()
                        parsed = self._extract_json(clean)
                        if parsed:
                            return parsed, price, rsi
                        return {"azione": "ERRORE", "ragionamento": f"Risposta: {raw[:150]}"}, price, rsi
                    return {"azione": "ERRORE", "ragionamento": f"HTTP {r.status_code}"}, price, rsi
                except Exception as e2:
                    return {"azione": "ERRORE", "ragionamento": f"Connessione API fallita: {str(e2)}"}, price, rsi
            return {"azione": "ERRORE", "ragionamento": err}, price, rsi

    def execute_real_order(self, symbol, action, amount_usdt=20):
        try:
            side = 'buy' if action == "COMPRA" else 'sell'
            ticker = self.exchange.fetch_ticker(symbol)
            amount = amount_usdt / ticker['last']
            order = self.exchange.create_market_order(symbol, side, amount)
            return order
        except Exception as e:
            print(f"Errore esecuzione ordine: {e}")
            return None

    def save_trade(self, symbol, mode, data, price, model_used="", user_id=0, amount_usdt=20):
        now = datetime.datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''INSERT INTO trades
                (timestamp, symbol, mode, azione, entry_price, stop_loss, take_profit,
                 reasoning, status, entry_time, highest_price, last_ai_check, ai_check_count, model_used, user_id, amount_usdt)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (now, symbol, mode, data.get('azione', 'ATTENDI'), price,
                 data.get('stop_loss', 0), data.get('take_profit', 0),
                 data['ragionamento'], 'APERTO', now, price, now, 0, model_used, user_id, amount_usdt))
            if mode == "Paper Trading":
                conn.execute("INSERT OR IGNORE INTO portfolio (user_id, balance, created_at) VALUES (?,?,?)",
                            (user_id, 1000, now))
                conn.execute("UPDATE portfolio SET balance = balance - ? WHERE user_id=?", (amount_usdt, user_id))
                conn.commit()
        emoji = {"COMPRA":"🔴","VENDI":"🔵","ATTENDI":"⚪"}
        self.send_telegram(f"{emoji.get(data.get('azione',''),'')} <b>{symbol}</b>\n"
                           f"Azione: {data.get('azione','')}\nEntry: ${price:.2f}\n"
                           f"Importo: ${amount_usdt:.0f}\n"
                           f"SL: ${data.get('stop_loss',0):.2f} | TP: ${data.get('take_profit',0):.2f}")

    # ---- EXIT STRATEGY ----
    TRAILING_STOP = 0.015
    MAX_HOURS = 24
    AI_RECHECK_HOURS = 1
    MAX_AI_CHECKS = 6

    def _close_and_update(self, conn, trade, current_price, reason):
        pnl = ((current_price - trade['entry_price']) / trade['entry_price']) * 100
        old_reason = trade['reasoning'] or ''
        new_reason = f"{old_reason} | Chiuso: {reason}"
        highest = max(trade['highest_price'] or trade['entry_price'], current_price)
        conn.execute(
            "UPDATE trades SET status='CHIUSO', profit_perc=?, reasoning=?, highest_price=? WHERE id=?",
            (round(pnl, 2), new_reason, highest, trade['id'])
        )
        conn.commit()
        if trade['mode'] == "Paper Trading":
            amt = trade.get('amount_usdt', 20) or 20
            credit = amt + (amt * pnl / 100)
            with sqlite3.connect(self.db_path) as conn2:
                conn2.execute("INSERT OR IGNORE INTO portfolio (user_id, balance, created_at) VALUES (?,?,?)",
                            (trade.get('user_id', 0), 1000, datetime.datetime.now()))
                conn2.execute("UPDATE portfolio SET balance = balance + ? WHERE user_id=?",
                            (round(credit, 2), trade.get('user_id', 0)))
                conn2.commit()
        print(f"[TRADE] {trade['symbol']} CHIUSO ({reason}) | P&L: {pnl:+.2f}%")
        pnl_emoji = "🟢" if pnl > 0 else "🔴"
        self.send_telegram(f"{pnl_emoji} <b>{trade['symbol']} CHIUSO</b>\n"
                           f"Motivo: {reason}\nP&L: {pnl:+.2f}%\n"
                           f"Entry: ${trade['entry_price']:.2f} | Uscita: ${current_price:.2f}")

    def _ai_recheck(self, trade, current_price, model):
        rsi = 50
        try:
            ohlcv = self._fetch_coin_ohlcv(trade['symbol'])
            if ohlcv:
                df = pd.DataFrame(ohlcv, columns=['t', 'o', 'h', 'l', 'c', 'v'])
                rsi = float(ta.momentum.rsi(df['c'], window=14).iloc[-1])
        except:
            pass
        entry = trade['entry_price']
        profit = ((current_price - entry) / entry) * 100
        hours = 0
        try:
            et = trade['entry_time'] or trade['timestamp']
            hours = (datetime.datetime.now() - datetime.datetime.fromisoformat(et.replace('Z', ''))).total_seconds() / 3600
        except:
            pass
        news = " | ".join(get_latest_crypto_news()[:3])
        prompt = f"""Posizione APERTA: {trade['symbol']}
Entry: ${entry:.2f}, Prezzo: ${current_price:.2f}, P&L: {profit:+.2f}%
RSI: {rsi:.1f}, Ore aperta: {hours:.1f}
Az. originale: {trade['azione']}
News: {news}

Regola: se la posizione e' in profitto, sei portato a CHIUDERE. Meglio un piccolo profitto sicuro che aspettare e rischiare.
Rispondi SOLO con JSON:
- Se mantenere (solo se hai certezza che salira' ancora): {{"decisione":"HOLD", "motivo":"..."}}
- Se chiudere: {{"decisione":"CHIUDI", "motivo":"..."}}"""
        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            raw = resp.choices[0].message.content or ''
            clean = re.sub(r'```json|```|`', '', raw).strip()
            parsed = self._extract_json(clean)
            if parsed and parsed.get('decisione') in ('HOLD', 'CHIUDI'):
                print(f"[AI] {trade['symbol']} rianalisi: {parsed['decisione']} — {parsed.get('motivo','')}")
                return parsed['decisione']
        except Exception as e:
            print(f"[AI] Errore rianalisi {trade['symbol']}: {e}")
        return 'HOLD'

    def check_and_close_trades(self, default_model="big-pickle", user_id=0):
        now = datetime.datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            trades = cursor.execute("SELECT * FROM trades WHERE status = 'APERTO' AND user_id=?", (user_id,)).fetchall()
            for t in trades:
                curr = self._fetch_coin_price(t['symbol'])
                if curr == 0:
                    continue
                entry_price = t['entry_price']
                highest = max(t['highest_price'] or entry_price, curr)
                # 1. Trailing stop (solo se in profitto)
                if highest > entry_price * 1.01:
                    trailing_price = highest * (1 - self.TRAILING_STOP)
                    if curr <= trailing_price:
                        self._close_and_update(conn, t, curr, "Trailing Stop")
                        continue
                # 2. Hard SL / TP
                if t['stop_loss'] > 0 and curr <= t['stop_loss']:
                    self._close_and_update(conn, t, curr, "Stop Loss")
                    continue
                if t['take_profit'] > 0 and curr >= t['take_profit']:
                    self._close_and_update(conn, t, curr, "Take Profit")
                    continue
                # 3. Max duration
                entry_time_str = t['entry_time'] or t['timestamp']
                if entry_time_str:
                    try:
                        entry_time = datetime.datetime.fromisoformat(entry_time_str.replace('Z', ''))
                        hours_open = (now - entry_time).total_seconds() / 3600
                        if hours_open >= self.MAX_HOURS:
                            self._close_and_update(conn, t, curr, "Max Duration")
                            continue
                    except:
                        pass
                # 4. Update highest price
                conn.execute("UPDATE trades SET highest_price=? WHERE id=?", (highest, t['id']))
                # 5. AI Re-analysis
                last_check_str = t['last_ai_check']
                check_count = t['ai_check_count'] or 0
                should_recheck = (not last_check_str) or \
                    ((now - datetime.datetime.fromisoformat(last_check_str.replace('Z', ''))).total_seconds() / 3600 >= self.AI_RECHECK_HOURS)
                if should_recheck and check_count < self.MAX_AI_CHECKS:
                    model = t['model_used'] or default_model
                    if self.client and model:
                        decision = self._ai_recheck(t, curr, model)
                    else:
                        decision = 'HOLD'
                    if decision == "CHIUDI":
                        self._close_and_update(conn, t, curr, "AI Decision")
                        continue
                    conn.execute(
                        "UPDATE trades SET last_ai_check=?, ai_check_count=? WHERE id=?",
                        (now.isoformat(), check_count + 1, t['id'])
                    )
                    conn.commit()
            conn.commit()

    def get_trades_by_user(self, user_id=0):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM trades WHERE user_id=? OR user_id=0 ORDER BY id DESC", (user_id,)).fetchall()
            return rows

    def get_portfolio_balance(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT balance FROM portfolio WHERE user_id=?", (user_id,)).fetchone()
            if row:
                return row[0]
            conn.execute("INSERT INTO portfolio (user_id, balance, created_at) VALUES (?,?,?)",
                        (user_id, 1000, datetime.datetime.now()))
            conn.commit()
            return 1000.0

    def init_portfolio(self, user_id, amount):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO portfolio (user_id, balance, created_at) VALUES (?,?,?)",
                        (user_id, amount, datetime.datetime.now()))
            conn.commit()

    def get_exchange_balance(self):
        if not self.exchange.apiKey or not self.exchange.secret:
            return None
        try:
            self.exchange.load_markets()
            bal = self.exchange.fetch_balance()
            non_zero = {k: v for k, v in bal['total'].items() if v and v > 0}
            return non_zero
        except Exception as e:
            err = str(e)
            print(f"Errore fetch balance: {err}")
            return f"Errore: {err}"

    def get_wallet_balance(self, address, chain="ethereum", token_address=None):
        if not address:
            return None
        try:
            TICKERS = {"ethereum":"ETH","bsc":"BNB","polygon":"MATIC","base":"ETH","linea":"ETH","bitcoin":"BTC","tron":"TRX","xrp":"XRP","dogecoin":"DOGE"}
            ticker = TICKERS.get(chain, "ETH")
            if chain in ("ethereum", "bsc", "polygon", "base", "linea"):
                if token_address:
                    decimals = self._read_token_decimals(chain, token_address)
                    data = "0x70a08231" + address[2:].zfill(64)
                    result = self._rpc_call(chain, "eth_call", [{"to": token_address, "data": data}, "latest"])
                    if result and result != '0x':
                        bal = int(result, 16) / (10 ** decimals)
                        cg_id = self.COINGECKO_IDS.get(chain, "ethereum")
                        if cg_id in ("ethereum",):
                            usd_rate = self._fetch_token_price(chain, token_address) or 0
                        else:
                            usd_rate = self._fetch_price(cg_id) or 0
                        if not usd_rate:
                            usd_rate = 0
                        return round(bal, 4), ticker, usd_rate
                    return None
                result = self._rpc_call(chain, "eth_getBalance", [address, "latest"])
                if result and result != '0x':
                    wei = int(result, 16)
                    cg_id = self.COINGECKO_IDS.get(chain, "ethereum")
                    usd_rate = self._fetch_price(cg_id)
                    return round(wei/1e18, 6), ticker, usd_rate or 0
            elif chain == "bitcoin":
                r = requests.get(f"https://blockchain.info/balance?active={address}", timeout=8)
                if r.status_code == 200:
                    sat = r.json().get(address, {}).get("final_balance", 0)
                    usd_rate = self._fetch_price("bitcoin")
                    return round(sat/1e8, 8), "BTC", usd_rate or 0
            elif chain == "tron":
                r = requests.get(f"https://api.trongrid.io/v1/accounts/{address}", timeout=8)
                if r.status_code == 200:
                    d = r.json().get("data")
                    if d:
                        bal = d[0].get("balance", 0) / 1e6
                        usd_rate = self._fetch_price("tron")
                        return round(bal, 2), "TRX", usd_rate or 0
            elif chain == "xrp":
                r = requests.get(f"https://data.ripple.com/v2/accounts/{address}/balances", timeout=8)
                if r.status_code == 200:
                    for b in r.json().get("balances", []):
                        if b.get("currency") == "XRP":
                            usd_rate = self._fetch_price("ripple")
                            return round(float(b["value"]), 2), "XRP", usd_rate or 0
            elif chain == "dogecoin":
                r = requests.get(f"https://dogechain.info/api/v1/address/balance/{address}", timeout=8)
                if r.status_code == 200:
                    bal = r.json().get("balance", 0)
                    usd_rate = self._fetch_price("dogecoin")
                    return round(float(bal), 2), "DOGE", usd_rate or 0
        except Exception as e:
            print(f"Wallet error {chain}: {e}")
        return None

