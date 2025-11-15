# utils/crypto.py

import requests
from datetime import datetime
from typing import Optional

# 🔁 Cache in memoria (dizionario con data come chiave)
_valori_cache = {}


def ottieni_valore_btc_eur(data: str) -> Optional[float]:
    """
    Recupera il valore del BTC in EUR per una data specifica, con cache.

    Parametri:
    - data (str): La data in formato 'YYYY-MM-DD'.

    Ritorna:
    - float: Il valore del BTC in EUR per la data specificata.
    - None: Se non è possibile recuperarlo.
    """

    # ✅ Se abbiamo già il valore in cache, lo restituiamo subito
    if data in _valori_cache:
        return _valori_cache[data]

    try:
        # Converti la data nel formato richiesto dall'API (DD-MM-YYYY)
        data_obj = datetime.strptime(data, '%Y-%m-%d')
        data_api = data_obj.strftime('%d-%m-%Y')

        # Chiamata all'API di CoinGecko
        url = f"https://api.coingecko.com/api/v3/coins/bitcoin/history?date={data_api}&localization=false"
        response = requests.get(url)

        if response.status_code == 200:
            dati = response.json()
            valore = dati["market_data"]["current_price"]["eur"]
            valore = round(valore, 2)

            # ✅ Salva in cache
            _valori_cache[data] = valore
            return valore
        else:
            print(f"Errore API: {response.status_code}")
            return None
    except Exception as e:
        print(f"Errore nel recupero del valore BTC per la data {data}: {e}")
        return None


def euro_to_btc(importo, valore_btc_eur):
    try:
        if importo is None or valore_btc_eur is None:
            return None
        return round(float(importo) / float(valore_btc_eur), 8)
    except (ValueError, ZeroDivisionError, TypeError):
        return None
