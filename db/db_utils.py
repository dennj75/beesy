# db_utils.py

import sqlite3
import os

DB_PATH = 'transazioni.db'


def inizializza_db():
    # Rimuove il vecchio DB per ricrearlo da zero con nuova struttura
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transazioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            descrizione TEXT NOT NULL,
            categoria TEXT NOT NULL,
            sottocategoria TEXT NOT NULL,
            importo REAL NOT NULL,
            controvalore_btc REAL,
            valore_btc_eur REAL
        )
    ''')

    # Tabella per Lightning Network
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transazioni_lightning(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            wallet TEXT NOT NULL,
            descrizione TEXT NOT NULL,
            categoria TEXT,
            sottocategoria TEXT,
            satoshi INTEGER,
            controvalore_eur REAL NOT NULL,
            valore_btc_eur REAL NOT NULL
        )
    ''')

    # Tabella per Bitcoin on-chain
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transazioni_onchain(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            wallet TEXT NOT NULL,
            descrizione TEXT NOT NULL,
            categoria TEXT,
            sottocategoria TEXT,
            transactionID TEXT NOT NULL,
            importo_btc REAL NOT NULL,
            fee REAL NOT NULL,
            controvalore_eur REAL NOT NULL,
            valore_btc_eur REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def salva_su_db_onchain(data, wallet, descrizione, categoria, sottocategoria, transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO transazioni_onchain(data, wallet, descrizione, categoria, sottocategoria, transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur)
    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data, wallet, descrizione, categoria, sottocategoria, transactionID, importo_btc, fee, float(controvalore_eur), float(valore_btc_eur)))
    conn.commit()
    conn.close()


def leggi_transazioni_da_db_onchain():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, data, wallet, descrizione, categoria, sottocategoria,
           transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur
    FROM transazioni_onchain
    ORDER BY data ASC''')
    righe = cursor.fetchall()
    conn.close()
    return righe


def elimina_transazione_da_db_onchain(id_transazione):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM transazioni_onchain WHERE id = ?', (id_transazione,))
    conn.commit()
    conn.close()


def modifica_transazione_db_onchain(id_transazione, campo, nuovo_valore):
    campi_consentiti = {'data', 'wallet', 'descrizione', 'categoria', 'sottocategoria',
                        'transactionID', 'importo_btc', 'fee', 'controvalore_eur', 'valore_btc_eur'}
    if campo not in campi_consentiti:
        raise ValueError("Campo non valido")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = f'UPDATE transazioni_onchain SET {campo} = ? WHERE id = ?'
    cursor.execute(query, (nuovo_valore, id_transazione))
    conn.commit()
    conn.close()


def leggi_transazioni_filtrate_onchain(filtro_data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = '''
        SELECT id, data, wallet, descrizione, categoria, sottocategoria, transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur
        FROM transazioni_onchain
        WHERE data LIKE ?
        ORDER BY data ASC
    '''
    cursor.execute(query, (filtro_data + '%',))
    righe = cursor.fetchall()
    conn.close()
    return righe


def get_transazioni_con_saldo_lightning():
    """
    Legge tutte le transazioni Lightning e calcola il saldo totale in satoshi.
    Ritorna: (lista_transazioni, saldo_totale_satoshi)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Legge tutte le transazioni
    cursor.execute('''
    SELECT id, data, wallet, descrizione, categoria, sottocategoria, satoshi, controvalore_eur, valore_btc_eur 
    FROM transazioni_lightning
    ORDER BY data ASC''')
    dati_lightning = cursor.fetchall()

    # Calcola il saldo totale sommando la colonna 'satoshi' (indice 6)
    cursor.execute('SELECT SUM(satoshi) FROM transazioni_lightning')
    saldo_totale_satoshi = cursor.fetchone()[0]

    conn.close()

    # Gestione del caso in cui non ci siano transazioni (SUM restituisce None)
    if saldo_totale_satoshi is None:
        saldo_totale_satoshi = 0

    # **IMPORTANTE: Restituisce DUE valori, risolvendo l'errore**
    return dati_lightning, saldo_totale_satoshi


def salva_su_db_lightning(data, wallet, descrizione, categoria, sottocategoria, satoshi, controvalore_eur, valore_btc_eur):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO transazioni_lightning(data, wallet, descrizione, categoria, sottocategoria, satoshi, controvalore_eur, valore_btc_eur)
    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data, wallet, descrizione, categoria, sottocategoria, satoshi, float(controvalore_eur), float(valore_btc_eur)))
    conn.commit()
    conn.close()


def leggi_transazioni_da_db_lightning():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, data, wallet, descrizione, categoria, sottocategoria, satoshi, controvalore_eur, valore_btc_eur FROM transazioni_lightning')
    righe = cursor.fetchall()
    conn.close()
    return righe


def elimina_transazione_da_db_lightning(id_transazione):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM transazioni_lightning WHERE id = ?', (id_transazione,))
    conn.commit()
    conn.close()


def modifica_transazione_db_lightning(id_transazione, campo, nuovo_valore):
    campi_consentiti = {'data', 'wallet', 'descrizione', 'categoria', 'sottocategoria',
                        'satoshi', 'controvalore_eur', 'valore_btc_eur'}
    if campo not in campi_consentiti:
        raise ValueError("Campo non valido")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = f'UPDATE transazioni_lightning SET {campo} = ? WHERE id = ?'
    cursor.execute(query, (nuovo_valore, id_transazione))
    conn.commit()
    conn.close()


def leggi_transazioni_filtrate_lightning(filtro_data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = '''
        SELECT id, data, wallet, descrizione, categoria, sottocategoria, satoshi, controvalore_eur, valore_btc_eur
        FROM transazioni_lightning
        WHERE data LIKE ?
        ORDER BY data ASC
    '''
    cursor.execute(query, (filtro_data + '%',))
    righe = cursor.fetchall()
    conn.close()
    return righe


def salva_su_db(data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO transazioni(data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur)
    VALUES(?, ?, ?, ?, ?, ?, ?)
    ''', (data, descrizione, categoria, sottocategoria, float(importo), controvalore_btc, valore_btc_eur))
    conn.commit()
    conn.close()


def leggi_transazioni_da_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur FROM transazioni')
    righe = cursor.fetchall()
    conn.close()
    return righe


def elimina_transazione_da_db(id_transazione):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM transazioni WHERE id = ?', (id_transazione,))
    conn.commit()
    conn.close()


def modifica_transazione_db(id_transazione, campo, nuovo_valore):
    campi_consentiti = {'data', 'descrizione', 'categoria', 'sottocategoria',
                        'importo', 'controvalore_btc', 'valore_btc_eur'}
    if campo not in campi_consentiti:
        raise ValueError("Campo non valido")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = f'UPDATE transazioni SET {campo} = ? WHERE id = ?'
    cursor.execute(query, (nuovo_valore, id_transazione))
    conn.commit()
    conn.close()


def saldo_iniziale_esistente():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM transazioni WHERE LOWER(descrizione) = 'saldo iniziale'")
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def leggi_transazioni_filtrate(filtro_data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = '''
        SELECT id, data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur
        FROM transazioni
        WHERE data LIKE ?
        ORDER BY data ASC
    '''
    cursor.execute(query, (filtro_data + '%',))
    righe = cursor.fetchall()
    conn.close()
    return righe
