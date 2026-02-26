# db_utils.py

import sqlite3
import os

DB_PATH = 'database.db'


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
            valore_btc_eur REAL,
            conto TEXT DEFAULT 'BANCA'
        )
    ''')

    try:
        cursor.execute(
            'ALTER TABLE transazioni ADD COLUMN user_id INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            "ALTER TABLE transazioni ADD COLUMN conto TEXT DEFAULT 'BANCA'")
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
    conn_users = sqlite3.connect(DB_PATH)

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

    # 1. Colonna per la Master Key criptata
    try:
        cursor_users.execute(
            'ALTER TABLE users ADD COLUMN encrypted_master_key TEXT')
    except sqlite3.OperationalError:
        pass  # La colonna esiste già

    # 2. Colonna per l'identità tecnica (Hex)
    try:
        cursor_users.execute('ALTER TABLE users ADD COLUMN pubkey TEXT')
        print("✅ Colonna pubkey aggiunta")
    except sqlite3.OperationalError:
        pass  # La colonna esiste già

    # Colonna per capire il tipo di login ('local' o 'nostr')
    try:
        cursor_users.execute(
            "ALTER TABLE users ADD COLUMN auth_type TEXT DEFAULT 'local'")
        print("✅ Colonna auth_type aggiunta")
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
    # Ottieni i nomi delle colonne (intestazioni)
    colonne = [desc[0] for desc in cursor.description]

    righe = cursor.fetchall()
    conn.close()
    # 💡 CONVERSIONE TUPLE -> DIZIONARI
    # Crea una lista di dizionari, dove le chiavi sono i nomi delle colonne
    dati_onchain = []
    for riga in righe:
        # zip combina le colonne con i valori della riga
        dizionario_transazione = dict(zip(colonne, riga))
        dati_onchain.append(dizionario_transazione)

    return dati_onchain  # Ora restituisce una lista di dizionari


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


def leggi_transazioni_da_db_onchain(user_id):
    """
    Legge le transazioni on-chain dal DB e le restituisce come lista di dizionari.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
    SELECT id, data, wallet, descrizione, categoria, sottocategoria,
           transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur
    FROM transazioni_onchain WHERE user_id = ? ORDER BY data ASC
    ''', (user_id,))

    # Ottiene i nomi delle colonne (intestazioni)
    colonne = [desc[0] for desc in cursor.description]

    # Ottiene le righe come lista di tuple
    righe_tuple = cursor.fetchall()

    conn.close()

    # 💡 Converte le tuple in dizionari
    dati_onchain = []
    for riga in righe_tuple:
        # Crea un dizionario mappando i nomi delle colonne ai valori della riga
        dizionario_transazione = dict(zip(colonne, riga))
        dati_onchain.append(dizionario_transazione)

    return dati_onchain


def leggi_transazioni_filtrate_onchain(filtro_data, user_id):
    """
    Legge le transazioni on-chain filtrate per data dal DB e le restituisce 
    come lista di dizionari.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = '''
        SELECT id, data, wallet, descrizione, categoria, sottocategoria, 
               transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur
        FROM transazioni_onchain
        WHERE user_id = ? AND data LIKE ?
        ORDER BY data ASC
    '''
    cursor.execute(query, (user_id, filtro_data + '%'))

    # Ottiene i nomi delle colonne (intestazioni)
    colonne = [desc[0] for desc in cursor.description]

    # Ottiene le righe come lista di tuple
    righe_tuple = cursor.fetchall()

    conn.close()

    # 💡 Converte le tuple in dizionari
    dati_filtrati = []
    for riga in righe_tuple:
        dizionario_transazione = dict(zip(colonne, riga))
        dati_filtrati.append(dizionario_transazione)

    return dati_filtrati


# --- SPOSTA QUESTE NEI TUOI UTILS ---

def get_transazioni_con_saldo(user_id):
    """Recupera transazioni Fiat e calcola i saldi (Banca, Contanti, Totale, BTC)."""
    transazioni = leggi_transazioni_da_db(user_id)

    saldo_banca = sum(t['importo']
                      for t in transazioni if t['conto'].upper() == 'BANCA')
    saldo_contanti = sum(t['importo']
                         for t in transazioni if t['conto'].upper() == 'CONTANTI')
    saldo_totale = saldo_banca + saldo_contanti

    # Calcola il controvalore BTC accumulato dalle spese EUR
    saldo_btc_da_eur = sum(float(t["controvalore_btc"]) for t in transazioni
                           if t.get("controvalore_btc") is not None)

    return transazioni, saldo_totale, saldo_banca, saldo_contanti, saldo_btc_da_eur


def get_transazioni_con_saldo_lightning(user_id):
    """Recupera transazioni Lightning e calcola i saldi."""
    transazioni = leggi_transazioni_da_db_lightning(user_id)

    saldo_satoshi = sum(float(t['satoshi'])
                        for t in transazioni if t.get('satoshi'))
    saldo_eur = sum(float(t['controvalore_eur'])
                    for t in transazioni if t.get('controvalore_eur'))

    return transazioni, saldo_satoshi, saldo_eur


def get_transazioni_con_saldo_onchain(user_id):
    """Recupera transazioni On-chain e calcola il saldo BTC."""
    transazioni = leggi_transazioni_da_db_onchain(user_id)
    saldo_btc = sum(float(t['importo_btc'])
                    for t in transazioni if t.get('importo_btc'))

    return transazioni, saldo_btc


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
    conn.row_factory = sqlite3.Row        # <<---- RITORNA DICTIONARY
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, data, wallet, descrizione, categoria, sottocategoria,
               satoshi, controvalore_eur, valore_btc_eur
        FROM transazioni_lightning
        WHERE user_id = ?
        ORDER BY data ASC
    """, (user_id,))

    righe = cursor.fetchall()
    conn.close()

    transazioni_ligtning = []
    for r in righe:
        d = dict(r)

        # 🎯 AGGIUNTO: Conversione dei campi numerici a float
        d['satoshi'] = float(d['satoshi']) if d['satoshi'] is not None else 0.0
        d['controvalore_eur'] = float(
            d['controvalore_eur']) if d['controvalore_eur'] is not None else None
        d['valore_btc_eur'] = float(
            d['valore_btc_eur']) if d['valore_btc_eur'] is not None else None

        # 🟢 CORREZIONE FONDAMENTALE: Aggiungi il dizionario elaborato alla lista
        transazioni_ligtning.append(d)
    return transazioni_ligtning


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
    # 🎯 AGGIUNTO: Ritorna oggetti Row (simili a dict)
    conn.row_factory = sqlite3.Row
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

    transazioni_lightning = []
    for r in righe:
        d = dict(r)

        # 🎯 AGGIUNTO: Conversione dei campi numerici a float
        d['satoshi'] = float(d['satoshi']) if d['satoshi'] is not None else 0.0
        d['controvalore_eur'] = float(
            d['controvalore_eur']) if d['controvalore_eur'] is not None else None
        d['valore_btc_eur'] = float(
            d['valore_btc_eur']) if d['valore_btc_eur'] is not None else None
        transazioni_lightning.append(d)
    return transazioni_lightning


def salva_su_db(user_id, data, descrizione, categoria, sottocategoria,
                importo, controvalore_btc, valore_btc_eur, conto):

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO transazioni (
            user_id,
            data,
            descrizione,
            categoria,
            sottocategoria,
            importo,
            controvalore_btc,
            valore_btc_eur,
            conto
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        data,
        descrizione,
        categoria,
        sottocategoria,
        float(importo),
        controvalore_btc,
        valore_btc_eur,
        conto
    ))

    conn.commit()
    conn.close()


def leggi_transazioni_da_db(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT 
            id, data, descrizione, categoria, sottocategoria, importo,
            controvalore_btc, valore_btc_eur, conto
        FROM transazioni 
        WHERE user_id = ? 
        ORDER BY data ASC''',
        (user_id,)
    )
    righe = cursor.fetchall()
    conn.close()

    transazioni = []
    for r in righe:
        importo = float(r[5]) if r[5] is not None else 0.0
        controvalore_btc = float(r[6]) if r[6] is not None else None
        valore_btc_eur = float(r[7]) if r[7] is not None else None
        transazioni.append({
            "id": r[0],
            "data": r[1],
            "descrizione": r[2],
            "categoria": r[3],
            "sottocategoria": r[4],
            "importo": importo,  # <-- Sintassi corretta Chiave: Valore
            "controvalore_btc": controvalore_btc,
            "valore_btc_eur": valore_btc_eur,
            "conto": r[8]
        })
    return transazioni


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
                        'importo', 'controvalore_btc', 'valore_btc_eur', 'conto'}
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
    # Ho aggiunto npub, pubkey e auth_type qui per farle combaciare con models.py
    cursor.execute('''
        SELECT id, username, email, password_hash, npub, 
               encrypted_master_key, pubkey, auth_type 
        FROM users WHERE username = ?
    ''', (username,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, email, password_hash, npub, 
               encrypted_master_key, pubkey, auth_type 
        FROM users WHERE id = ?
    ''', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_user_by_npub(npub_hex):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Cerchiamo l'esadecimale nella colonna pubkey (che ora è piena!)
    cursor.execute(
        "SELECT id, username, auth_type, npub FROM users WHERE pubkey = ?", (npub_hex,))
    row = cursor.fetchone()
    conn.close()
    return row


def create_user_from_npub(pubkey_hex, npub_bech32):
    """
    Crea un nuovo utente salvando:
    - username: l'esadecimale pulito (es. b1da9e19...)
    - pubkey: l'esadecimale pulito
    - npub: il formato Bech32 (es. npub1k8df...)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Usiamo l'esadecimale come username. È univoco e pulito.
    username = pubkey_hex

    cursor.execute('''
        INSERT INTO users (username, email, password_hash, npub, pubkey, auth_type) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        username,
        None,           # email
        'NO_PASSWORD',  # Password disabilitata per login Nostr
        npub_bech32,    # Formato npub1...
        pubkey_hex,     # Formato hex puro
        'nostr'         # Tipo di autenticazione
    ))

    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def salva_master_key_nel_db(user_id, encrypted_mk):
    """Salva la Master Key criptata nel record dell'utente corretto."""
    try:
        # Usa il percorso corretto del tuo db (database.db)
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        print(f"DEBUG DB: Tentativo di salvataggio MK per utente {user_id}...")

        cursor.execute(
            "UPDATE users SET encrypted_master_key = ? WHERE id = ?",
            (encrypted_mk, user_id)
        )

        conn.commit()
        righe_modificate = cursor.rowcount
        conn.close()

        if righe_modificate > 0:
            print(
                f"✅ DEBUG DB: Master Key salvata con successo per ID {user_id}!")
        else:
            print(
                f"❌ DEBUG DB: Nessun utente trovato con ID {user_id}. Salvataggio fallito.")

    except Exception as e:
        print(f"❌ DEBUG DB: Errore durante il salvataggio: {e}")


def update_user_password_hash(user_id, pw_hash):
    """Aggiorna l'hash della password di un utente nel DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Assumendo che la tabella utenti si chiami 'utenti' e la colonna 'password_hash'
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    import sqlite3
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def ripristina_database_completo(user_id, dati_json):
    """Svuota le tabelle dell'utente e inserisce i dati dal backup con debug migliorato."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Pulizia (Solo per l'utente specifico!)
        cursor.execute("DELETE FROM transazioni WHERE user_id = ?", (user_id,))
        cursor.execute(
            "DELETE FROM transazioni_lightning WHERE user_id = ?", (user_id,))
        cursor.execute(
            "DELETE FROM transazioni_onchain WHERE user_id = ?", (user_id,))

        # 2. Inserimento Euro (Proviamo sia 'euro' che 'transazioni' per compatibilità)
        transazioni_euro = dati_json.get(
            'euro') or dati_json.get('transazioni') or []
        print(
            f"DEBUG RIPRISTINO: Trovate {len(transazioni_euro)} transazioni Euro")

        for t in transazioni_euro:
            cursor.execute('''
                INSERT INTO transazioni (data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur, conto, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (t['data'], t['descrizione'], t['categoria'], t['sottocategoria'], t['importo'], t.get('controvalore_btc', 0), t.get('valore_btc_eur', 0), t.get('conto', 'BANCA'), user_id))

        # 3. Inserimento Lightning
        transazioni_ln = dati_json.get('lightning', [])
        print(
            f"DEBUG RIPRISTINO: Trovate {len(transazioni_ln)} transazioni Lightning")

        for t in transazioni_ln:
            cursor.execute('''
                INSERT INTO transazioni_lightning (data, wallet, descrizione, categoria, sottocategoria, satoshi, controvalore_eur, valore_btc_eur, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (t['data'], t['wallet'], t['descrizione'], t['categoria'], t['sottocategoria'], t['satoshi'], t.get('controvalore_eur', 0), t.get('valore_btc_eur', 0), user_id))

        # 4. Inserimento On-chain
        transazioni_on = dati_json.get('onchain', [])
        print(
            f"DEBUG RIPRISTINO: Trovate {len(transazioni_on)} transazioni Onchain")

        for t in transazioni_on:
            cursor.execute('''
                INSERT INTO transazioni_onchain (data, wallet, descrizione, categoria, sottocategoria, transactionID, importo_btc, fee, controvalore_eur, valore_btc_eur, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (t['data'], t['wallet'], t['descrizione'], t['categoria'], t['sottocategoria'], t.get('transactionID', ''), t['importo_btc'], t.get('fee', 0), t.get('controvalore_eur', 0), t.get('valore_btc_eur', 0), user_id))

        conn.commit()
        print("✅ RIPRISTINO DB: Operazione completata con successo!")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ ERRORE CRITICO RIPRISTINO DB: {e}")
        return False
    finally:
        conn.close()
