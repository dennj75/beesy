import pandas as pd
import sqlite3
import time
from datetime import datetime
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

            # Calcolo equivalenza BTC
            btc_equiv_raw = euro_to_btc(importo_pulito, prezzo_btc)

            # 🎯 FIX NOTAZIONE SCIENTIFICA: Formattazione forzata a 8 decimali (es. -0.00002848)
            if btc_equiv_raw is not None:
                btc_equiv = f"{btc_equiv_raw:.8f}"
            else:
                btc_equiv = "0.00000000"

            # --- CHIAMATA AL CERVELLO ---
            cat_indovinata, subcat_indovinata = indovina_categoria(
                descrizione, user_id)

            print(
                f"Riga {index+1}: [{data_iso}] {descrizione[:30]}... | {importo_pulito}€ | BTC: {btc_equiv} | -> {cat_indovinata}")

            transazioni_pulite.append({
                'data': data_iso,
                'descrizione': descrizione,
                'importo': importo_pulito,
                'prezzo_btc': prezzo_btc,
                'btc_equiv': btc_equiv,  # Ora passa sempre la stringa formattata a 8 decimali
                'categoria': cat_indovinata,
                'sottocategoria': subcat_indovinata
            })

    except Exception as e:
        print(f"🔥 Errore durante la lettura: {e}")

    return transazioni_pulite


def anteprima_importazione_blink_csv(percorso_file, user_id, data_inizio_filtro=None):
    transazioni_pulite = []
    try:
        # Leggiamo il CSV di Blink
        df = pd.read_csv(percorso_file, sep=',',
                         engine='python', encoding='utf-8')
        df.columns = df.columns.str.strip()  # Puliamo eventuali spazi nei nomi colonne

        for index, row in df.iterrows():
            # 1. Estrazione Data dal Timestamp Unix
            raw_ts = row.get('timestamp', None)
            if pd.notnull(raw_ts):
                try:
                    # Convertiamo i secondi Unix in data AAAA-MM-DD
                    data_iso = datetime.fromtimestamp(
                        int(raw_ts)).strftime('%Y-%m-%d')
                except Exception:
                    data_iso = "Data Errata"
            else:
                data_iso = "Data Errata"

            # 2. Filtro Data: Ignora transazioni antecedenti alla data di inizio impostata
            if data_inizio_filtro and data_iso != "Data Errata":
                if data_iso < data_inizio_filtro:
                    continue  # Salta lo storico vecchio!

            # 3. Calcolo dei Sats (Credit = Entrata [+], Debit = Uscita [-])
            credit = float(row.get('credit', 0) or 0)
            debit = float(row.get('debit', 0) or 0)

            if credit > 0:
                sats = credit
            elif debit > 0:
                sats = -debit  # Uscita (importo negativo)
            else:
                sats = 0.0

            if sats == 0:
                continue  # Salta righe a zero sats o fallite

            # Convertiamo i Sats in BTC decimali (es. 100 sats = 0.00000100 BTC)
            btc_equiv = sats / 100_000_000.0

            # 4. Recupero della Nota / Descrizione
            memo = str(row.get('lnMemo', '')).strip()
            if not memo or memo == 'nan':
                memo = str(row.get('memoFromPayer', '')).strip()
            if not memo or memo == 'nan':
                memo = "Transazione Blink Lightning"

            # 5. Calcolo Controvalore EUR (Spot del giorno)
            prezzo_btc_eur = ottieni_valore_btc_eur(
                data_iso) if data_iso != "Data Errata" else 0

            if prezzo_btc_eur and prezzo_btc_eur > 0:
                importo_eur = round(btc_equiv * prezzo_btc_eur, 2)
            else:
                importo_eur = 0.0

            # 6. Il motore indovina Categoria e Sottocategoria
            cat_indovinata, subcat_indovinata = indovina_categoria(
                memo, user_id)

            transazioni_pulite.append({
                'data': data_iso,
                'descrizione': memo,
                'importo': importo_eur,        # In € per Beesy
                'prezzo_btc': prezzo_btc_eur,  # Tasso BTC/EUR di quel giorno
                'btc_equiv': btc_equiv,        # Importo in BTC reali
                # Sats per visualizzazione comoda
                'sats': int(sats),
                'categoria': cat_indovinata,
                'sottocategoria': subcat_indovinata
            })

    except Exception as e:
        print(f"🔥 Errore durante la lettura del CSV di Blink: {e}")

    return transazioni_pulite
