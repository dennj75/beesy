import sqlite3
import os

# Percorso relativo al DB dal file migrazione_user_id.py
DB_PATH = os.path.join(os.path.dirname(__file__), 'transazioni.db')
# sostituisci 'transazioni.db' con il nome reale del tuo file DB

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Esempio: imposta tutte le transazioni con user_id = 1
user_id_da_usare = 1
cursor.execute("UPDATE transazioni_onchain SET user_id = ?",
               (user_id_da_usare,))

conn.commit()
conn.close()
print(f"Tutte le transazioni aggiornate con user_id = {user_id_da_usare}")
