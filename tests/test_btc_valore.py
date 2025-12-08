# modifica questo percorso se serve
from utils.crypto import ottieni_valore_btc_eur

# Usa una data passata
data_test = "2025-01-01"
valore = ottieni_valore_btc_eur(data_test)
print(f"Valore BTC/EUR il {data_test}: {valore}")
