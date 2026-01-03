import datetime
from db.db_utils import leggi_transazioni_da_db


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
