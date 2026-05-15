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
    def __init__(self, db_path='nexus_memory.db', exchange_name='bybit', proxy=None):
        self.db_path = db_path
        self._init_db()
        exchange_map = {
            'bybit': ccxt.bybit,
            'binance': ccxt.binance,
            'kucoin': ccxt.kucoin,
            'mexc': ccxt.mexc,
        }
        if hasattr(ccxt, 'binanceus'):
            exchange_map['binanceus'] = ccxt.binanceus
        
        self.exchange_name = exchange_name
        exchange_class = exchange_map.get(exchange_name)
        if not exchange_class:
            exchange_class = ccxt.bybit
            self.exchange_name = 'bybit'
        
        kwargs = {'enableRateLimit': True}
        if proxy:
            kwargs['httpsProxy'] = proxy
        
        # Prova exchange in ordine senza parametri extra
        self.exchange = None
        for ex_name, ex_class in [('bybit', ccxt.bybit), ('binance', ccxt.binance)]:
            try:
                ex = ex_class()
                ex.load_markets()
                self.exchange = ex
                self.exchange_name = ex_name
                if proxy:
                    ex.httpsProxy = proxy
                break
            except:
                continue
        if not self.exchange:
            # Fallback minimale
            self.exchange = ccxt.bybit()
            self.exchange_name = 'bybit'
        self.client = None

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME, symbol TEXT, mode TEXT, azione TEXT,
                entry_price REAL, stop_loss REAL, take_profit REAL,
                reasoning TEXT, profit_perc REAL DEFAULT 0, status TEXT DEFAULT 'APERTO')''')
            try:
                conn.execute("ALTER TABLE trades ADD COLUMN azione TEXT")
            except:
                pass

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

    def get_tickers(self):
        try:
            self.exchange.load_markets()
            tiks = [m for m in self.exchange.markets if m.endswith('/USDT') and 'UP/' not in m and 'DOWN/' not in m]
            return sorted(tiks)
        except Exception as e:
            print(f"Ticker error {self.exchange_name}: {e}")
            return ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    def get_available_models(self):
        if not self.client:
            return []
        try:
            models = self.client.models.list()
            return sorted([m.id for m in models])
        except:
            return []

    @staticmethod
    def get_common_tokens(chain):
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
        stack = []
        for i, ch in enumerate(text):
            if ch == '{':
                stack.append(i)
            elif ch == '}':
                if stack:
                    start = stack.pop()
                    if not stack:
                        try:
                            return json.loads(text[start:i+1])
                        except:
                            continue
        return None

    def decide_trade(self, symbol, model_id):
        if not self.client:
            return {"azione": "ERRORE", "ragionamento": "Chiave API mancante"}, 0, 0
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
            df = pd.DataFrame(ohlcv, columns=['t', 'o', 'h', 'l', 'c', 'v'])
            rsi = ta.momentum.rsi(df['c'], window=14).iloc[-1]
        except Exception as e:
            return {"azione": "ERRORE", "ragionamento": f"Errore {self.exchange_name}: {str(e)}"}, 0, 0

        news = " | ".join(get_latest_crypto_news()[:5])
        prompt = f"""Dati: {symbol} a {price}$, RSI {rsi:.2f}. News: {news}.
Rispondi con JSON: {{"azione":"COMPRA","stop_loss":{price*0.95:.2f},"take_profit":{price*1.05:.2f},"ragionamento":"..."}}"""

        try:
            response = self.client.chat.completions.create(
                model=model_id, messages=[{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=2000
            )
            msg = response.choices[0].message
            raw = msg.content or getattr(msg, 'reasoning_content', '') or ''
            clean = re.sub(r'```json|```|`', '', raw).strip()
            parsed = self._extract_json(clean)
            if parsed:
                return parsed, price, rsi
            return {"azione": "ERRORE", "ragionamento": f"Risposta: {raw[:150]}"}, price, rsi
        except Exception as e:
            return {"azione": "ERRORE", "ragionamento": str(e)}, price, rsi

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

    def save_trade(self, symbol, mode, data, price):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('INSERT INTO trades (timestamp, symbol, mode, azione, entry_price, stop_loss, take_profit, reasoning, status) VALUES (?,?,?,?,?,?,?,?,?)',
                         (datetime.datetime.now(), symbol, mode, data.get('azione', 'ATTENDI'), price,
                          data.get('stop_loss', 0), data.get('take_profit', 0), data['ragionamento'], 'APERTO'))

    def check_and_close_trades(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            trades = cursor.execute("SELECT * FROM trades WHERE status = 'APERTO'").fetchall()
            for t in trades:
                try:
                    ticker = self.exchange.fetch_ticker(t['symbol'])
                    curr = ticker['last']
                    cl = False
                    if t['stop_loss'] > 0 and curr <= t['stop_loss']: cl = True
                    if t['take_profit'] > 0 and curr >= t['take_profit']: cl = True
                    if cl:
                        p = ((curr - t['entry_price']) / t['entry_price']) * 100
                        if t['mode'] == "Real Trading":
                            try:
                                base_currency = t['symbol'].split('/')[0]
                                balance = self.exchange.fetch_balance()
                                qty = balance['free'].get(base_currency, 0)
                                if qty > 0:
                                    self.exchange.create_market_order(t['symbol'], 'sell', qty)
                            except: pass
                        conn.execute("UPDATE trades SET status='CHIUSO', profit_perc=? WHERE id=?", (round(p, 2), t['id']))
                        conn.commit()
                except: continue

    def get_wallet_balance(self, address, chain="ethereum", token_address=None):
        if not address:
            return None
        try:
            if chain in ("ethereum", "bsc", "polygon", "base", "linea"):
                rpc_map = {
                    "ethereum": "https://eth.llamarpc.com", "bsc": "https://bsc.publicnode.com",
                    "polygon": "https://polygon-rpc.com", "base": "https://mainnet.base.org",
                    "linea": "https://rpc.linea.build",
                }
                rpc = rpc_map[chain]
                if token_address:
                    data = "0x70a08231" + address[2:].zfill(64)
                    r = requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_call","params":[{"to":token_address,"data":data},"latest"],"id":1}, timeout=10)
                    if r.status_code == 200:
                        bal = int(r.json().get("result","0x0"), 16)
                        return round(bal/1e6, 2), "USDC", 1.0
                r = requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_getBalance","params":[address,"latest"],"id":1}, timeout=10)
                if r.status_code == 200:
                    wei = int(r.json().get("result","0x0"), 16)
                    ticker_map = {"ethereum":"ETH","bsc":"BNB","polygon":"MATIC","base":"ETH","linea":"ETH"}
                    price_map = {"ethereum":1800,"bsc":600,"polygon":0.50,"base":1800,"linea":1800}
                    return round(wei/1e18, 6), ticker_map.get(chain,"ETH"), price_map.get(chain, 1800)
            elif chain == "bitcoin":
                r = requests.get(f"https://blockchain.info/balance?active={address}", timeout=10)
                if r.status_code == 200:
                    sat = r.json().get(address, {}).get("final_balance", 0)
                    return round(sat/1e8, 8), "BTC", 67000
            elif chain == "tron":
                r = requests.get(f"https://api.trongrid.io/v1/accounts/{address}", timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("data"):
                        bal = data["data"][0].get("balance", 0)
                        return round(bal/1e6, 2), "TRX", 0.12
            elif chain == "xrp":
                r = requests.get(f"https://data.ripple.com/v2/accounts/{address}/balances", timeout=10)
                if r.status_code == 200:
                    for b in r.json().get("balances", []):
                        if b.get("currency") == "XRP":
                            return round(float(b["value"]), 2), "XRP", 0.50
            elif chain == "dogecoin":
                r = requests.get(f"https://dogechain.info/api/v1/address/balance/{address}", timeout=10)
                if r.status_code == 200:
                    bal = r.json().get("balance", 0)
                    return round(float(bal), 2), "DOGE", 0.15
        except:
            pass
        return None
