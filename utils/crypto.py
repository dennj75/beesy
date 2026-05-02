# utils/crypto.py
import requests
import sqlite3
from datetime import datetime
from typing import Optional
from db.db_utils import DB_PATH, get_db_connection

# _valori_cache = {}
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

def aggiorna_prezzo_bitcoin():
    try:
        # 1. Chiediamo il prezzo a CoinGecko
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur"
        response = requests.get(url)
        data = response.json()
        
        prezzo_eur = data['bitcoin']['eur']
        data_attuale = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 2. Salviamolo nel Database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO prezzi_btc (data, prezzo_eur) VALUES (?, ?)",
            (data_attuale, prezzo_eur)
        )
        conn.commit()
        conn.close()
        
        print(f"✅ Prezzo aggiornato: {prezzo_eur} €")
        return prezzo_eur
    except Exception as e:
        print(f"❌ Errore aggiornamento prezzo: {e}")
        return None

def ottieni_valore_btc_eur(data: str) -> Optional[float]:
    """Cerca il prezzo nel DB locale. Se manca, lo scarica e lo salva."""
    print(f"DEBUG: Cerco prezzo per la data: {data}")  # <-- AGGIUNGI QUESTO
    # 1. Prova a leggere dal Database locale
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT prezzo_eur FROM prezzi_btc WHERE data = ?", (data,))
    risultato = cursor.fetchone()

    if risultato:
        conn.close()
        print(f"DEBUG: Trovato nel DB: {risultato[0]}")  # <-- AGGIUNGI QUESTO
        return risultato[0]  # Trovato in memoria!

    # 2. Se NON è nel DB, andiamo su CoinGecko
    try:
        data_obj = datetime.strptime(data, '%Y-%m-%d')
        data_api = data_obj.strftime('%d-%m-%Y')
        url = f"https://api.coingecko.com/api/v3/coins/bitcoin/history?date={data_api}&localization=false"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            dati = response.json()
            valore = dati["market_data"]["current_price"]["eur"]
            valore = round(float(valore), 2)

            # 3. SALVIAMO nel DB per la prossima volta (Cache persistente)
            cursor.execute(
                "INSERT OR REPLACE INTO prezzi_btc (data, prezzo_eur) VALUES (?, ?)", (data, valore))
            conn.commit()
            print(
                f"☁️ Scaricato e salvato prezzo BTC per il {data}: {valore}€")

            conn.close()
            print(f"DEBUG: Scaricato da API: {valore}")  # <-- AGGIUNGI QUESTO
            return valore
        else:
            print(f"❌ Errore API CoinGecko: {response.status_code}")
            conn.close()
            return None

    except Exception as e:
        print(f"🔥 Errore recupero/salvataggio BTC per {data}: {e}")
        conn.close()
        # <-- AGGIUNGI QUESTO
        print(f"DEBUG: Errore API Status: {response.status_code}")
        return None


def euro_to_btc(importo, valore_btc_eur):
    try:
        if importo is None or valore_btc_eur is None:
            return None
        return round(float(importo) / float(valore_btc_eur), 8)
    except (ValueError, ZeroDivisionError, TypeError):
        return None

