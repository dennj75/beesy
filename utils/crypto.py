# utils/crypto.py
import requests
from datetime import datetime
from typing import Optional

_valori_cache = {}
_storico_btc = None   # cache unica dello storico


def _carica_storico_btc_eur():
    """Carica tutta la storia BTC/EUR da CoinGecko una sola volta."""
    global _storico_btc

    if _storico_btc is not None:
        return

    print("Caricamento dati storici BTC da CoinGecko...")
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=eur&days=max"
    risposta = requests.get(url)

    if risposta.status_code != 200:
        print("Errore CoinGecko storico:", risposta.status_code)
        _storico_btc = []
        return

    dati = risposta.json()
    # "prices" → lista di [timestamp_ms, valore_eur]
    _storico_btc = dati.get("prices", [])


def ottieni_valore_btc_eur(data: str, fallback_oggi=True) -> Optional[float]:
    from datetime import datetime, date
    import requests

    if data in _valori_cache:
        return _valori_cache[data]

    try:
        data_obj = datetime.strptime(data, '%Y-%m-%d')
        data_api = data_obj.strftime('%d-%m-%Y')
        url = f"https://api.coingecko.com/api/v3/coins/bitcoin/history?date={data_api}&localization=false"
        response = requests.get(url)

        if response.status_code == 200:
            dati = response.json()
            valore = dati["market_data"]["current_price"]["eur"]
            valore = round(valore, 2)
            _valori_cache[data] = valore
            return valore
        else:
            print(f"Errore API storico: {response.status_code}")

            # ✅ Se richiesto, prendi il valore attuale di oggi
            if fallback_oggi:
                url_oggi = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur"
                r = requests.get(url_oggi)
                if r.status_code == 200:
                    valore = r.json()["bitcoin"]["eur"]
                    valore = round(valore, 2)
                    _valori_cache[data] = valore
                    print(f"Valore BTC corrente preso come fallback: {valore}")
                    return valore

            return None
    except Exception as e:
        print(f"Errore recupero BTC per {data}: {e}")
        return None


def euro_to_btc(importo, valore_btc_eur):
    try:
        if importo is None or valore_btc_eur is None:
            return None
        return round(float(importo) / float(valore_btc_eur), 8)
    except (ValueError, ZeroDivisionError, TypeError):
        return None
