import pandas as pd
import sqlite3
import time
from utils.crypto import ottieni_valore_btc_eur, euro_to_btc


def indovina_categoria(descrizione, user_id):
    descrizione_upper = descrizione.upper()

    # 🛠️ FIX 1: Usa il nome corretto del tuo DB (beesy.db)
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT parola_chiave, categoria, sottocategoria FROM mapping_categorie")
        mappings = cursor.fetchall()
    except:
        mappings = []  # Se la tabella non esiste ancora
    conn.close()

    for parola, cat, subcat in mappings:
        # Usiamo .upper() anche sulla parola chiave per sicurezza
        if parola.upper() in descrizione_upper:
            return cat, subcat

    return "Da Classificare", "Altro"


def anteprima_importazione_csv(percorso_file, user_id):
    transazioni_pulite = []
    try:
        df = pd.read_csv(percorso_file, sep=',',
                         engine='python', encoding='utf-8')

        print(f"--- Diagnosi File ---")
        print(f"Colonne trovate: {list(df.columns)}")
        print(f"----------------------\n")

        for index, row in df.iterrows():
            row.index = row.index.str.strip()

            data_raw = str(row.get('Data', 'N/A'))
            operazione = str(row.get('Operazione', 'N/A'))
            dettagli = str(row.get('Dettagli', ''))
            importo_raw = str(row.get('Importo', '0'))

            descrizione = f"{operazione} {dettagli}".strip()

            try:
                data_iso = pd.to_datetime(
                    data_raw, dayfirst=True).strftime('%Y-%m-%d')
            except:
                data_iso = "Data Errata"

            try:
                importo_pulito = float(
                    importo_raw.replace('.', '').replace(',', '.'))
            except:
                importo_pulito = 0.0

            prezzo_btc = ottieni_valore_btc_eur(
                data_iso) if data_iso != "Data Errata" else None
            btc_equiv = euro_to_btc(importo_pulito, prezzo_btc)

            # --- CHIAMATA AL CERVELLO ---
            cat_indovinata, subcat_indovinata = indovina_categoria(descrizione, user_id)

            # 🛠️ FIX 2: Aggiungiamo la categoria nel print per vederla nel terminale!
            print(
                f"Riga {index+1}: [{data_iso}] {descrizione[:30]}... | {importo_pulito}€ | BTC: {btc_equiv} | -> {cat_indovinata}")

            transazioni_pulite.append({
                'data': data_iso,
                'descrizione': descrizione,
                'importo': importo_pulito,
                'prezzo_btc': prezzo_btc,
                'btc_equiv': btc_equiv,
                'categoria': cat_indovinata,
                'sottocategoria': subcat_indovinata
            })

    except Exception as e:
        print(f"🔥 Errore durante la lettura: {e}")

    return transazioni_pulite
