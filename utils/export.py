# utils/export.py

import csv
import json
import os
from db.db_utils import leggi_transazioni_da_db, leggi_transazioni_filtrate, leggi_transazioni_da_db_lightning, leggi_transazioni_filtrate_lightning, leggi_transazioni_filtrate_onchain, leggi_transazioni_da_db_onchain
from datetime import datetime


def genera_stringa_backup_json(user_id=None):
    # Recuperiamo tutti i dati usando le funzioni esistenti
    dati = {
        "metadata": {
            "user_id": user_id,
            "data_backup": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "versione_beesy": "1.0"
        },
        "onchain": leggi_transazioni_da_db_onchain(user_id),
        "lightning": leggi_transazioni_da_db_lightning(user_id),
        "euro": leggi_transazioni_da_db(user_id),
    }

    # Restituiamo direttamente la stringa JSON invece di salvare un file
    return json.dumps(dati, ensure_ascii=False, indent=4)


def esporta_csv_onchain(nome_file='exports/transazioni_onchain.csv', user_id=None):
    # Crea la cartella exports se non esiste
    cartella_export = os.path.dirname(nome_file)
    os.makedirs(cartella_export, exist_ok=True)

    transazioni_onchain = leggi_transazioni_da_db_onchain(user_id)

    # 🎯 Inizio del blocco 'with'. Tutto ciò che segue è DENTRO.
    with open(nome_file, mode='w', newline='', encoding='utf-8') as file_csv:
        intestazioni = [
            'id', 'data', 'wallet', 'descrizione', 'categoria',
            'sottocategoria', 'transactionID', 'importo_btc', 'fee', 'controvalore_eur', 'valore_btc_eur'
        ]
        writer = csv.DictWriter(file_csv, fieldnames=intestazioni)
        writer.writeheader()

        saldo_totale_btc = 0.0

        # ⚠️ CICLO FOR: Deve essere indentato (dentro il with)
        for t in transazioni_onchain:
            # Scrittura di ogni transazione
            writer.writerow({
                'id': t['id'],
                'data': t['data'],
                'wallet': t['wallet'],
                'descrizione': t['descrizione'],
                'categoria': t['categoria'],
                'sottocategoria': t['sottocategoria'],
                'transactionID': t['transactionID'],
                'importo_btc': f'{t["importo_btc"]:.8f}',
                'fee': f'{t["fee"]:.8f}',
                'controvalore_eur': f'{t.get("controvalore_eur"):.2f}' if t.get('controvalore_eur') is not None else '',
                'valore_btc_eur': f'{t.get("valore_btc_eur"):.8f}' if t.get('valore_btc_eur') is not None else ''
            })
            saldo_totale_btc += t['importo_btc']

        # ⚠️ SCRITTURA TOTALE: Deve essere indentata (dentro il with e fuori dal for)
        # Ho corretto anche l'errore "fee is not defined" che si ripresenterebbe qui!
        writer.writerow({
            'id': '',
            'data': '',
            'wallet': '',
            'descrizione': '💰 Totale BTC',
            'categoria': '',
            'sottocategoria': '',
            'transactionID': '',
            'importo_btc': f'{saldo_totale_btc:.8f}',
            'fee': '',  # <-- Corretto: la variabile 't' non è disponibile qui
            'controvalore_eur': '',
            'valore_btc_eur': ''
        })

    # 🎯 Stampa finale: è ora al livello esterno (fuori dal with), ma non è critica.
    print(
        f"✅ File '{nome_file}' esportato correttamente con saldo totale di {saldo_totale_btc} satoshi.")


def esporta_csv_per_mese_onchain(mese, user_id=None):
    transazioni_onchain = leggi_transazioni_filtrate_onchain(mese, user_id)
    if not transazioni_onchain:
        print(f"⚠️ Nessuna transazione trovata per il mese {mese} ")
        return

    # Crea la cartella exports se non esistente
    cartella_export = 'exports'
    if not os.path.exists(cartella_export):
        os.makedirs(cartella_export)

    nome_file = os.path.join(
        cartella_export, f'transazioni_{mese}_onchain.csv')

    with open(nome_file, mode='w', newline='', encoding='utf-8') as file_csv:
        intestazioni = ['id', 'data', 'wallet', 'descrizione', 'categoria',
                        'sottocategoria', 'transactionID', 'importo_btc', 'fee', 'controvalore_eur', 'valore_btc_eur']
        writer = csv.DictWriter(file_csv, fieldnames=intestazioni)
        writer.writeheader()

        saldo_totale_btc = 0.0

        # ✅ CORREZIONE: Iteriamo sui dizionari 't'
        for t in transazioni_onchain:
            # Calcolo del controvalore_eur e valore_btc_eur per formattazione sicura
            controvalore_eur = t.get('controvalore_eur')
            valore_btc_eur = t.get('valore_btc_eur')

            writer.writerow({
                'id': t['id'],
                'data': t['data'],
                'wallet': t['wallet'],
                'descrizione': t['descrizione'],
                'categoria': t['categoria'],
                'sottocategoria': t['sottocategoria'],
                'transactionID': t['transactionID'],
                # ✅ CORREZIONE 1: Usa t['importo_btc'] per la riga singola
                'importo_btc': f'{t["importo_btc"]:.8f}',
                'fee': f'{t["fee"]:.8f}',
                'controvalore_eur': f'{controvalore_eur:.2f}' if controvalore_eur is not None else '',
                'valore_btc_eur': f'{valore_btc_eur:.8f}' if valore_btc_eur is not None else ''
            })
            # Aggiorna il saldo con l'importo della transazione
            saldo_totale_btc += t['importo_btc']

        # ⚠️ CORREZIONE 2: Riga Totale (non usare la variabile 'fee' che è indefinita qui)
        writer.writerow({
            'id': '',
            'data': '',
            'wallet': '',
            'descrizione': '💰 Totale BTC',
            'categoria': '',
            'sottocategoria': '',
            'transactionID': '',
            'importo_btc': f'{saldo_totale_btc:.8f}',
            'fee': '',  # Sostituito f'{fee:.8f}'
            'controvalore_eur': '',
            'valore_btc_eur': ''
        })

    print(f"\n✅ File '{nome_file}' esportato correttamente con il saldo.")


def esporta_csv_lightning(nome_file='exports/transazioni_lightning.csv', user_id=None):
    # Crea la cartella exports se non esiste
    cartella_export = os.path.dirname(nome_file)
    os.makedirs(cartella_export, exist_ok=True)

    # Assume che questa funzione restituisca una LISTA DI DIZIONARI, con i tipi numerici già convertiti a float/int
    transazioni_lightning = leggi_transazioni_da_db_lightning(user_id)

    with open(nome_file, mode='w', newline='', encoding='utf-8') as file_csv:
        intestazioni = [
            'id', 'data', 'wallet', 'descrizione', 'categoria',
            'sottocategoria', 'satoshi', 'controvalore_eur', 'valore_btc_eur'
        ]
        writer = csv.DictWriter(file_csv, fieldnames=intestazioni)
        writer.writeheader()

        saldo_satoshi = 0

        # 🎯 CORREZIONE DEL CICLO FOR: Iterazione sul dizionario
        for transazione in transazioni_lightning:

            # Estrazione dei valori per chiarezza e per la formattazione
            satoshi = transazione['satoshi']
            controvalore_eur = transazione['controvalore_eur']
            valore_btc_eur = transazione['valore_btc_eur']

            writer.writerow({
                'id': transazione['id'],
                'data': transazione['data'],
                'wallet': transazione['wallet'],
                'descrizione': transazione['descrizione'],
                'categoria': transazione['categoria'],
                'sottocategoria': transazione['sottocategoria'],

                # Assume che satoshi sia un int/float
                'satoshi': satoshi,

                # Assume che controvalore_eur e valore_btc_eur siano float o None
                'controvalore_eur': f'{controvalore_eur:.2f}' if controvalore_eur is not None else '',
                'valore_btc_eur': f'{valore_btc_eur:.8f}' if valore_btc_eur is not None else ''
            })

            # La somma è sicura se satoshi è un tipo numerico (int o float)
            saldo_satoshi += satoshi

        writer.writerow({
            'id': '',
            'data': '',
            'wallet': '',
            'descrizione': '💰 Totale (satoshi)',
            'categoria': '',
            'sottocategoria': '',
            'satoshi': saldo_satoshi,  # Scrive il saldo totale (come int)
            'controvalore_eur': '',
            'valore_btc_eur': ''
        })

    print(
        f"✅ File '{nome_file}' esportato correttamente con saldo totale di {saldo_satoshi} satoshi.")


def esporta_csv_per_mese_lightning(mese, user_id=None):
    transazioni_lightning = leggi_transazioni_filtrate_lightning(mese, user_id)
    if not transazioni_lightning:
        print(f"⚠️ Nessuna transazione trovata per il mese {mese} ")
        return

    # Crea la cartella exports se non esistente
    cartella_export = 'exports'
    if not os.path.exists(cartella_export):
        os.makedirs(cartella_export)

    nome_file = os.path.join(
        cartella_export, f'transazioni_{mese}_lightning.csv')

    with open(nome_file, mode='w', newline='', encoding='utf-8') as file_csv:
        intestazioni = ['id', 'data', 'wallet', 'descrizione', 'categoria',
                        'sottocategoria', 'satoshi', 'controvalore_eur', 'valore_btc_eur']
        writer = csv.DictWriter(file_csv, fieldnames=intestazioni)
        writer.writeheader()

        saldo_satoshi = 0.0
        for t in transazioni_lightning:  # 't' è ora il dizionario della transazione
            # Estrai i valori dal dizionario 't'
            controvalore_eur = t.get('controvalore_eur')
            valore_btc_eur = t.get('valore_btc_eur')
            satoshi = t.get('satoshi')
            writer.writerow({
                'id': t.get('id', ''),
                'data': t.get('data', ''),
                'wallet': t.get('wallet', ''),
                'descrizione': t.get('descrizione', ''),
                'categoria': t.get('categoria', ''),
                'sottocategoria': t.get('sottocategoria', ''),
                'satoshi': satoshi,
                'controvalore_eur': f'{controvalore_eur:.2f}' if controvalore_eur is not None else '',
                'valore_btc_eur': f'{valore_btc_eur:.8f}' if valore_btc_eur is not None else ''
            })
            if satoshi is not None:
                saldo_satoshi += satoshi

        writer.writerow({
            'id': '',
            'data': '',
            'wallet': '',
            'descrizione': '💰 Saldo totale',
            'categoria': '',
            'sottocategoria': '',
            'satoshi': saldo_satoshi,
            'controvalore_eur': '',
            'valore_btc_eur': ''
        })

    print(f"\n✅ File '{nome_file}' esportato correttamente con il saldo.")
    return nome_file  # <-- Restituisce il nome del file se tutto va bene


def esporta_csv(nome_file='exports/transazioni.csv', user_id=None):
    transazioni = leggi_transazioni_da_db(user_id)
    with open(nome_file, mode='w', newline='', encoding='utf-8') as file_csv:
        intestazioni = ['id', 'data', 'descrizione', 'categoria',
                        'sottocategoria', 'importo', 'controvalore_btc', 'valore_btc_eur', 'conto']
        writer = csv.DictWriter(file_csv, fieldnames=intestazioni)
        writer.writeheader()

        saldo = 0.0

        # 🎯 CORREZIONE: Iterare sull'elemento dizionario singolo
        for transazione in transazioni:

            # Poiché leggi_transazioni_da_db ora restituisce FLOAT,
            # possiamo accedere direttamente ai valori e formattarli/sommarli.
            importo = transazione["importo"]
            controvalore_btc = transazione["controvalore_btc"]
            valore_btc_eur = transazione["valore_btc_eur"]

            writer.writerow({
                'id': transazione["id"],
                'data': transazione["data"],
                'descrizione': transazione["descrizione"],
                'categoria': transazione["categoria"],
                'sottocategoria': transazione["sottocategoria"],

                # Non serve più float(), perché importo è già un FLOAT grazie a leggi_transazioni_da_db
                'importo': f'{importo:.2f}',

                'controvalore_btc': f'{controvalore_btc:.8f}' if controvalore_btc is not None else '',
                'valore_btc_eur': f'{valore_btc_eur:.2f}' if valore_btc_eur is not None else '',
                'conto': transazione["conto"]
            })

            # Non serve più float(), importo è già un FLOAT
            saldo += float(importo)

        # ... (Il resto della funzione, inclusa la scrittura del saldo, è corretto)
        writer.writerow({
            'id': '',
            'data': '',
            'descrizione': '💰 Saldo Totale',
            'categoria': '',
            'sottocategoria': '',
            'importo': f'{saldo:.2f}',
            'controvalore_btc': '',
            'valore_btc_eur': '',
            'conto': ''
        })

    print(f"\n✅ File '{nome_file}' esportato correttamente con il saldo.")


def esporta_csv_per_mese(mese, user_id=None):
    transazioni = leggi_transazioni_filtrate(mese, user_id)
    if not transazioni:
        print(f"⚠️ Nessuna transazione trovata per il mese {mese} ")
        return

    # Crea la cartella exports se non esistente
    cartella_export = 'exports'
    if not os.path.exists(cartella_export):
        os.makedirs(cartella_export)

    nome_file = os.path.join(
        cartella_export, f'transazioni_{mese}.csv')
    with open(nome_file, mode='w', newline='', encoding='utf-8') as file_csv:
        intestazioni = ['id', 'data', 'descrizione', 'categoria',
                        'sottocategoria', 'importo', 'controvalore_btc', 'valore_btc_eur']
        writer = csv.DictWriter(file_csv, fieldnames=intestazioni)
        writer.writeheader()

        saldo = 0.0
        for id_db, data, descrizione, categoria, sottocategoia, importo, controvalore_btc, valore_btc_eur in transazioni:
            writer.writerow({
                'id': id_db,
                'data': data,
                'descrizione': descrizione,
                'categoria': categoria,
                'sottocategoria': sottocategoia,
                'importo': f'{importo:.2f}',
                'controvalore_btc': f'{controvalore_btc:.8f}' if controvalore_btc else '',
                'valore_btc_eur': f'{valore_btc_eur:.2f}' if valore_btc_eur else ''
            })
            saldo += importo

        writer.writerow({
            'id': '',
            'data': '',
            'descrizione': '💰 Saldo totale',
            'categoria': '',
            'sottocategoria': '',
            'importo': f'{saldo:.2f}',
            'controvalore_btc': '',
            'valore_btc_eur': ''
        })

    print(f"\n✅ File '{nome_file}' esportato correttamente con il saldo.")
