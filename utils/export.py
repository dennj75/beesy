import csv
import os
from db.db_utils import leggi_transazioni_da_db, leggi_transazioni_filtrate, leggi_transazioni_da_db_lightning, leggi_transazioni_filtrate_lightning, leggi_transazioni_filtrate_onchain, leggi_transazioni_da_db_onchain


def esporta_csv_onchain(nome_file='exports/transazioni_onchain.csv'):
    # Crea la cartella exports se non esiste
    cartella_export = os.path.dirname(nome_file)
    os.makedirs(cartella_export, exist_ok=True)

    transazioni_onchain = leggi_transazioni_da_db_onchain()

    with open(nome_file, mode='w', newline='', encoding='utf-8') as file_csv:
        intestazioni = [
            'id', 'data', 'wallet', 'descrizione', 'categoria',
            'sottocategoria', 'transactionID', 'importo_btc', 'fee', 'controvalore_eur', 'valore_btc_eur'
        ]
        writer = csv.DictWriter(file_csv, fieldnames=intestazioni)
        writer.writeheader()

        saldo_totale_btc = 0.0
        for id_db, data, wallet, descrizione, categoria, sottocategoria, transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur in transazioni_onchain:
            writer.writerow({
                'id': id_db,
                'data': data,
                'wallet': wallet,
                'descrizione': descrizione,
                'categoria': categoria,
                'sottocategoria': sottocategoria,
                'transactionID': transactionID,
                'importo_btc': f'{importo_btc:.8f}',
                'fee': f'{fee:.8f}',
                'controvalore_eur': f'{controvalore_eur:.2f}' if controvalore_eur else '',
                'valore_btc_eur': f'{valore_btc_eur:.8f}' if valore_btc_eur else ''
            })
            saldo_totale_btc += importo_btc

        writer.writerow({
            'id': '',
            'data': '',
            'wallet': '',
            'descrizione': '💰 Totale BTC',
            'categoria': '',
            'sottocategoria': '',
            'transactionID': '',
            'importo_btc': f'{saldo_totale_btc:.8f}',
            'fee': f'{fee:.8f}',
            'controvalore_eur': '',
            'valore_btc_eur': ''
        })

    print(
        f"✅ File '{nome_file}' esportato correttamente con saldo totale di {saldo_totale_btc} satoshi.")


def esporta_csv_per_mese_onchain(mese):
    transazioni_onchain = leggi_transazioni_filtrate_onchain(mese)
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
        for id_db, data, wallet, descrizione, categoria, sottocategoia, transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur in transazioni_onchain:
            writer.writerow({
                'id': id_db,
                'data': data,
                'wallet': wallet,
                'descrizione': descrizione,
                'categoria': categoria,
                'sottocategoria': sottocategoia,
                'transactionID': transactionID,
                'importo_btc': f'{saldo_totale_btc:.8f}',
                'fee': f'{fee:.8f}',
                'controvalore_eur': f'{controvalore_eur:.2f}' if controvalore_eur else '',
                'valore_btc_eur': f'{valore_btc_eur:.8f}' if valore_btc_eur else ''
            })
            saldo_totale_btc += importo_btc

        writer.writerow({
            'id': '',
            'data': '',
            'wallet': '',
            'descrizione': '💰 Totale BTC',
            'categoria': '',
            'sottocategoria': '',
            'transactionID': '',
            'importo_btc': f'{saldo_totale_btc:.8f}',
            'fee': f'{fee:.8f}',
            'controvalore_eur': '',
            'valore_btc_eur': ''
        })

    print(f"\n✅ File '{nome_file}' esportato correttamente con il saldo.")


def esporta_csv_lightning(nome_file='exports/transazioni_lightning.csv'):
    # Crea la cartella exports se non esiste
    cartella_export = os.path.dirname(nome_file)
    os.makedirs(cartella_export, exist_ok=True)

    transazioni_lightning = leggi_transazioni_da_db_lightning()

    with open(nome_file, mode='w', newline='', encoding='utf-8') as file_csv:
        intestazioni = [
            'id', 'data', 'wallet', 'descrizione', 'categoria',
            'sottocategoria', 'satoshi', 'controvalore_eur', 'valore_btc_eur'
        ]
        writer = csv.DictWriter(file_csv, fieldnames=intestazioni)
        writer.writeheader()

        saldo_satoshi = 0
        for id_db, data, wallet, descrizione, categoria, sottocategoria, satoshi, controvalore_eur, valore_btc_eur in transazioni_lightning:
            writer.writerow({
                'id': id_db,
                'data': data,
                'wallet': wallet,
                'descrizione': descrizione,
                'categoria': categoria,
                'sottocategoria': sottocategoria,
                'satoshi': satoshi,
                'controvalore_eur': f'{controvalore_eur:.2f}' if controvalore_eur else '',
                'valore_btc_eur': f'{valore_btc_eur:.8f}' if valore_btc_eur else ''
            })
            saldo_satoshi += satoshi

        writer.writerow({
            'id': '',
            'data': '',
            'wallet': '',
            'descrizione': '💰 Totale (satoshi)',
            'categoria': '',
            'sottocategoria': '',
            'satoshi': saldo_satoshi,
            'controvalore_eur': '',
            'valore_btc_eur': ''
        })

    print(
        f"✅ File '{nome_file}' esportato correttamente con saldo totale di {saldo_satoshi} satoshi.")


def esporta_csv_per_mese_lightning(mese):
    transazioni_lightning = leggi_transazioni_filtrate_lightning(mese)
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
        for id_db, data, wallet, descrizione, categoria, sottocategoia, satoshi, controvalore_eur, valore_btc_eur in transazioni_lightning:
            writer.writerow({
                'id': id_db,
                'data': data,
                'wallet': wallet,
                'descrizione': descrizione,
                'categoria': categoria,
                'sottocategoria': sottocategoia,
                'satoshi': satoshi,
                'controvalore_eur': f'{controvalore_eur:.2f}' if controvalore_eur else '',
                'valore_btc_eur': f'{valore_btc_eur:.8f}' if valore_btc_eur else ''
            })
            saldo_satoshi += satoshi

        writer.writerow({
            'id': '',
            'data': '',
            'wallet': '',
            'descrizione': '💰 Saldo totale',
            'categoria': '',
            'sottocategoria': '',
            'satoshi': '',
            'controvalore_eur': '',
            'valore_btc_eur': ''
        })

    print(f"\n✅ File '{nome_file}' esportato correttamente con il saldo.")


def esporta_csv(nome_file='exports/transazioni.csv'):
    transazioni = leggi_transazioni_da_db()
    with open(nome_file, mode='w', newline='', encoding='utf-8') as file_csv:
        intestazioni = ['id', 'data', 'descrizione', 'categoria',
                        'sottocategoria', 'importo', 'controvalore_btc', 'valore_btc_eur']
        writer = csv.DictWriter(file_csv, fieldnames=intestazioni)
        writer.writeheader()

        saldo = 0.0
        for id_db, data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur in transazioni:
            writer.writerow({
                'id': id_db,
                'data': data,
                'descrizione': descrizione,
                'categoria': categoria,
                'sottocategoria': sottocategoria,
                'importo': f'{importo:.2f}',
                'controvalore_btc': f'{controvalore_btc:.8f}' if controvalore_btc else '',
                'valore_btc_eur': f'{valore_btc_eur:.2f}' if valore_btc_eur else ''
            })
            saldo += importo

        writer.writerow({
            'id': '',
            'data': '',
            'descrizione': '💰 Saldo Totale',
            'categoria': '',
            'sottocategoria': '',
            'importo': f'{saldo:.2f}',
            'controvalore_btc': '',
            'valore_btc_eur': ''
        })

    print(f"\n✅ File '{nome_file}' esportato correttamente con il saldo.")


def esporta_csv_per_mese(mese):
    transazioni = leggi_transazioni_filtrate(mese)
    if not transazioni:
        print(f"⚠️ Nessuna transazione trovata per il mese {mese} ")
        return

    # Crea la cartella exports se non esistente
    cartella_export = 'exports'
    if not os.path.exists(cartella_export):
        os.makedirs(cartella_export)

    nome_file = os.path.join(
        cartella_export, f'transazioni_{mese}_lightning.csv')
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
