# db_utils.py

import sqlite3
import os

DB_PATH = 'transazioni.db'


def verifica_ownership_transazione(id_transazione, user_id, tabella):
    """
    Verifica che la transazione appartiene a user_id nella tabella specificata.
    Ritorna True se l'utente è il proprietario, False altrimenti.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f'SELECT user_id FROM {tabella} WHERE id = ?', (id_transazione,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    return row[0] == user_id


def inizializza_db():
    # Crea il DB se non esiste e crea le tabelle mancanti.
    # ATTENZIONE: non cancellare automaticamente il DB esistente per evitare perdita dati.
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
    try:
        cursor.execute(
            'ALTER TABLE transazioni ADD COLUMN user_id INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass

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
    try:
        cursor.execute(
            'ALTER TABLE transazioni_lightning ADD COLUMN user_id INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass

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
    try:
        cursor.execute(
            'ALTER TABLE transazioni_onchain ADD COLUMN user_id INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

    # Tabella per utenti (auth)
    conn_users = sqlite3.connect('database.db')
    cursor_users = conn_users.cursor()
    cursor_users.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL
        )
    ''')
    try:
        cursor_users.execute('ALTER TABLE users ADD COLUMN npub TEXT')
    except sqlite3.OperationalError:
        pass  # La colonna esiste già

    conn_users.commit()
    conn_users.close()


def salva_su_db_onchain(user_id, data, wallet, descrizione, categoria, sottocategoria, transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO transazioni_onchain(user_id, data, wallet, descrizione, categoria, sottocategoria, transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur)
    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data, wallet, descrizione, categoria, sottocategoria, transactionID, importo_btc, fee, float(controvalore_eur), float(valore_btc_eur)))
    conn.commit()
    conn.close()


def leggi_transazioni_da_db_onchain(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, data, wallet, descrizione, categoria, sottocategoria,
           transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur
    FROM transazioni_onchain WHERE user_id = ? ORDER BY data ASC
    ''', (user_id,))
    righe = cursor.fetchall()
    conn.close()
    return righe


def elimina_transazione_da_db_onchain(id_transazione, user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if not verifica_ownership_transazione(id_transazione, user_id, 'transazioni_onchain'):
        conn.close()
        raise PermissionError(
            f"Non hai il permesso di eliminare questa transazione")
    cursor.execute(
        'DELETE FROM transazioni_onchain WHERE id = ?', (id_transazione,))
    conn.commit()
    conn.close()


def modifica_transazione_db_onchain(id_transazione, campo, nuovo_valore, user_id):
    campi_consentiti = {'data', 'wallet', 'descrizione', 'categoria', 'sottocategoria',
                        'transactionID', 'importo_btc', 'fee', 'controvalore_eur', 'valore_btc_eur'}
    if campo not in campi_consentiti:
        raise ValueError("Campo non valido")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if not verifica_ownership_transazione(id_transazione, user_id, 'transazioni_onchain'):
        conn.close()
        raise PermissionError(
            f"Non hai il permesso di modificare questa transazione")
    query = f'UPDATE transazioni_onchain SET {campo} = ? WHERE id = ?'
    cursor.execute(query, (nuovo_valore, id_transazione))
    conn.commit()
    conn.close()


def leggi_transazioni_filtrate_onchain(filtro_data, user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = '''
        SELECT id, data, wallet, descrizione, categoria, sottocategoria, transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur
        FROM transazioni_onchain
        WHERE user_id = ? AND data LIKE ?
        ORDER BY data ASC
    '''
    cursor.execute(query, (user_id, filtro_data + '%'))
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


def salva_su_db_lightning(user_id, data, wallet, descrizione, categoria, sottocategoria, satoshi, controvalore_eur, valore_btc_eur):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO transazioni_lightning(user_id, data, wallet, descrizione, categoria, sottocategoria, satoshi, controvalore_eur, valore_btc_eur)
    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data, wallet, descrizione, categoria, sottocategoria, satoshi, float(controvalore_eur), float(valore_btc_eur)))
    conn.commit()
    conn.close()


def leggi_transazioni_da_db_lightning(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, data, wallet, descrizione, categoria, sottocategoria, satoshi, controvalore_eur, valore_btc_eur FROM transazioni_lightning WHERE user_id = ? ORDER BY data ASC', (
            user_id,)
    )
    righe = cursor.fetchall()
    conn.close()
    return righe


def elimina_transazione_da_db_lightning(id_transazione, user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if not verifica_ownership_transazione(id_transazione, user_id, 'transazioni_lightning'):
        conn.close()
        raise PermissionError(
            f"Non hai il permesso di eliminare questa transazione")
    cursor.execute(
        'DELETE FROM transazioni_lightning WHERE id = ?', (id_transazione,))
    conn.commit()
    conn.close()


def modifica_transazione_db_lightning(id_transazione, campo, nuovo_valore, user_id):
    campi_consentiti = {'data', 'wallet', 'descrizione', 'categoria', 'sottocategoria',
                        'satoshi', 'controvalore_eur', 'valore_btc_eur'}
    if campo not in campi_consentiti:
        raise ValueError("Campo non valido")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if not verifica_ownership_transazione(id_transazione, user_id, 'transazioni_lightning'):
        conn.close()
        raise PermissionError(
            f"Non hai il permesso di modificare questa transazione")
    query = f'UPDATE transazioni_lightning SET {campo} = ? WHERE id = ?'
    cursor.execute(query, (nuovo_valore, id_transazione))
    conn.commit()
    conn.close()


def leggi_transazioni_filtrate_lightning(filtro_data, user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = '''
        SELECT id, data, wallet, descrizione, categoria, sottocategoria, satoshi, controvalore_eur, valore_btc_eur
        FROM transazioni_lightning
        WHERE user_id = ? AND data LIKE ?
        ORDER BY data ASC
    '''
    cursor.execute(query, (user_id, filtro_data + '%'))
    righe = cursor.fetchall()
    conn.close()
    return righe


def salva_su_db(user_id, data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO transazioni(user_id, data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur)
    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data, descrizione, categoria, sottocategoria, float(importo), controvalore_btc, valore_btc_eur))
    conn.commit()
    conn.close()


def leggi_transazioni_da_db(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur FROM transazioni WHERE user_id = ? ORDER BY data ASC',
        (user_id,)  # ← TUPLA FUORI dalla query, come parametro di execute()
    )
    righe = cursor.fetchall()
    conn.close()
    return righe


def elimina_transazione_da_db(id_transazione, user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if not verifica_ownership_transazione(id_transazione, user_id, 'transazioni'):
        conn.close()
        raise PermissionError(
            f"Non hai il permesso di eliminare questa transazione")
    cursor.execute('DELETE FROM transazioni WHERE id = ?', (id_transazione,))
    conn.commit()
    conn.close()


def modifica_transazione_db(id_transazione, campo, nuovo_valore, user_id):
    campi_consentiti = {'data', 'descrizione', 'categoria', 'sottocategoria',
                        'importo', 'controvalore_btc', 'valore_btc_eur'}
    if campo not in campi_consentiti:
        raise ValueError("Campo non valido")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if not verifica_ownership_transazione(id_transazione, user_id, 'transazioni'):
        conn.close()
        raise PermissionError(
            f"Non hai il permesso di modificare questa transazione")
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


def leggi_transazioni_filtrate(filtro_data, user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = '''
        SELECT id, data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur
        FROM transazioni
        WHERE user_id = ? AND data LIKE ?
        ORDER BY data ASC
    '''
    cursor.execute(query, (user_id, filtro_data + '%'))
    righe = cursor.fetchall()
    conn.close()
    return righe

# Funzioni utenti


def crea_utente(username, email, password_hash):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO users(username, email, password_hash)
    VALUES(?, ?, ?)
    ''', (username, email, password_hash))
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def get_user_by_username(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, username, email, password_hash FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, username, email, password_hash FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_user_by_npub(npub):
    """Trova un utente tramite il suo npub"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username FROM users WHERE npub = ?', (npub,))
    user = cursor.fetchone()
    conn.close()
    return user


def create_user_from_npub(npub):
    """Crea un nuovo utente dal npub"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    username = f"nostr_{npub[:8]}"
    cursor.execute(
        'INSERT INTO users (username, email, password_hash, npub) VALUES (?, ?, ?, ?)',
        (username, None, '', npub)  # email=None, password_hash='', npub=valore
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id
