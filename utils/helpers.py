import datetime
import requests
from db.db_utils import leggi_transazioni_da_db

# Dizionario unico per tutta l'applicazione Beesy
VALUTE_SUPPORTATE = {
    'EUR': {'simbolo': '€', 'nome': 'Euro'},
    'USD': {'simbolo': '$', 'nome': 'Dollaro Statunitense'},
    'CHF': {'simbolo': 'CHF', 'nome': 'Franco Svizzero'},
    'GBP': {'simbolo': '£', 'nome': 'Sterlina Britannica'},
    'JPY': {'simbolo': '¥', 'nome': 'Yen Giapponese'},
    'CNY': {'simbolo': '¥', 'nome': 'Yuan Cinese'},
    'ALL': {'simbolo': 'Lek', 'nome': 'Lek Albanese'},
    'CAD': {'simbolo': 'CA$', 'nome': 'Dollaro Canadese'},
    'AUD': {'simbolo': 'A$', 'nome': 'Dollaro Australiano'},
    'BRL': {'simbolo': 'R$', 'nome': 'Real Brasiliano'},
    'INR': {'simbolo': '₹', 'nome': 'Rupia Indiana'},
    'SEK': {'simbolo': 'kr', 'nome': 'Corona Svedese'},
    'AED': {'simbolo': 'AED', 'nome': 'Dirham EAE'},
    'BTC': {'simbolo': '₿', 'nome': 'Bitcoin'},
    'SAT': {'simbolo': 'sat', 'nome': 'Satoshi'},
}


def normalizza_importo(valore):
    try:
        return f"{float(valore.replace(',', '.')):.2f}"
    except ValueError:
        return None


def pausa():
    input("\n🔙 Premi INVIO per continuare...")


def data_valida(data_str):
    try:
        datetime.datetime.strptime(data_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def formatta_importo(importo, valuta='EUR'):
    # Recupera il simbolo dal dizionario centrale (fallback sul codice valuta)
    info_valuta = VALUTE_SUPPORTATE.get(valuta)
    simbolo = info_valuta['simbolo'] if info_valuta else valuta

    # Se la valuta è Satoshi o Bitcoin, gestiamo i decimali appropriati
    if valuta == 'SAT':
        return f"{int(importo)} {simbolo}"
    elif valuta == 'BTC':
        return f"{importo:.8f} {simbolo}"

    return f"{importo:.2f} {simbolo}"


def get_exchange_rate(from_currency, to_currency, date_str=None):
    """
    Restituisce il tasso di cambio tra due valute con timeout ultra-rapido
    e protezione totale contro i blocchi di rete.
    """
    if not from_currency or not to_currency or from_currency == to_currency:
        return 1.0

    try:
        # API gratuita della Banca Centrale Europea (Frankfurter)
        url = f"https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}"
        # Timeout abbassato a 2 secondi per evitare qualsiasi blocco del server
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            data = response.json()
            return float(data['rates'].get(to_currency, 1.0))
    except Exception as e:
        # Stampiamo l'errore senza bloccare l'esecuzione
        print(
            f"⚠️ API cambio non disponibile ({from_currency} -> {to_currency}), uso fallback: {e}")

    # Fallback immediato: se la rete fallisce, l'app non si blocca e usa 1.0
    return 1.0
