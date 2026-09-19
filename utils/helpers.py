import datetime
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
