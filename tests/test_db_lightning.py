from db.db_utils import salva_su_db_lightning, leggi_transazioni_da_db_lightning

salva_su_db_lightning(
    "2025-10-18",
    "Phoenix Wallet",
    "Pagamento pizza",
    "Cibo",
    "Ristorante",
    2000,       # satoshi
    0.60,       # controvalore in EUR
    33333       # EUR per 1 BTC
)

transazioni = leggi_transazioni_da_db_lightning()
for t in transazioni:
    print(t)
