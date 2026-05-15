import requests
import re

def get_latest_crypto_news():
    try:
        res = requests.get("https://cointelegraph.com/rss", timeout=10)
        if res.status_code == 200:
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', res.text)
            if not titles: titles = re.findall(r'<title>(.*?)</title>', res.text)
            return titles[1:11] if len(titles) > 1 else ["Nessuna notizia trovata."]
    except: pass
    return ["Servizio news non raggiungibile."]
