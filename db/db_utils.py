# db/db_utils.py

import sqlite3
import os

DB_PATH = 'database.db'

COLONNE_TRANSAZIONI = [
    "id", "data", "descrizione", "categoria", "sottocategoria",
    "importo", "controvalore_btc", "valore_btc_eur", "conto", "user_id", "note"
]


def get_db_connection():
    # 'database.db' deve essere il nome esatto del tuo file
    db_path = 'database.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


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
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # 1. Creazione tabella con TUTTE le colonne aggiornate
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
            conto TEXT DEFAULT 'BANCA',
            user_id INTEGER DEFAULT 1,
            note TEXT DEFAULT '',  -- <--- AGGIUNTA QUI!
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # 2. "Paracadute" per i database vecchi
    # Se il database esiste già ma mancano le colonne, le aggiungiamo qui
    colonne_extra = [
        ('user_id', 'INTEGER DEFAULT 1'),
        ('conto', "TEXT DEFAULT 'BANCA'"),
        ('note', "TEXT DEFAULT ''")
    ]

    for nome_col, tipo in colonne_extra:
        try:
            cursor.execute(
                f'ALTER TABLE transazioni ADD COLUMN {nome_col} {tipo}')
        except sqlite3.OperationalError:
            pass  # La colonna esiste già, tutto ok!

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
            valore_btc_eur REAL NOT NULL,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
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
            valore_btc_eur REAL NOT NULL,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )  
    ''')
    try:
        cursor.execute(
            'ALTER TABLE transazioni_onchain ADD COLUMN user_id INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass

    # Tabella per utenti (auth) - USO LO STESSO CURSORE DI PRIMA
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Aggiunta colonne extra per utenti
    colonne_users = [
        ('npub', 'TEXT'),
        ('encrypted_master_key', 'TEXT'),
        ('pubkey', 'TEXT'),
        ('auth_type', "TEXT DEFAULT 'local'")
    ]

    for nome_col, tipo in colonne_users:
        try:
            cursor.execute(f'ALTER TABLE users ADD COLUMN {nome_col} {tipo}')
        except sqlite3.OperationalError:
            pass

    # Tabella per tenere d'occhio gli asset (es. fondi pensione, azioni, ETF)
    cursor.execute('''        
        CREATE TABLE IF NOT EXISTS assets_watch(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            nome_asset TEXT NOT NULL,       -- Es: "Fondo Pensione", "Poste Italiane"
            tipo_asset TEXT DEFAULT 'FIAT', -- Per distinguerli dalle crypto
            capitale_investito REAL,        -- Quanto hai messo il 31/03
            valore_attuale REAL,            -- Il valore aggiornato oggi
            data_aggiornamento DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Tabella per il "cervello" delle categorie
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mapping_categorie (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parola_chiave TEXT NOT NULL,
            categoria TEXT,
            sottocategoria TEXT,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )        
    ''')

    # ALLA FINE DI TUTTO: Un solo commit e una sola chiusura
    conn.commit()
    conn.close()
    print("🐝 Beesy: Database inizializzato e pronto!")


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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Leggiamo TUTTE le transazioni EUR (Banca, Contanti, Investimenti, Pensione)
    # Assicurati che la query non escluda i nuovi conti!
    cursor.execute("""
        SELECT * FROM transazioni 
        WHERE user_id = ? 
        AND UPPER(conto) IN ('BANCA', 'CONTANTI', 'INVESTIMENTI', 'PENSIONE')
        ORDER BY data DESC, id DESC
    """, (user_id,))

    rows = cursor.fetchall()
    transazioni = [dict(row) for row in rows]

    # Inizializziamo i saldi
    banca = 0.0
    contanti = 0.0
    saldo_investimenti = 0.0
    saldo_pensione = 0.0
    saldo_btc_da_eur = 0.0

    for t in transazioni:
        importo = t['importo'] or 0.0
        conto = t['conto'].upper() if t['conto'] else ""

        # Sommiamo nei cassetti giusti
        if conto == 'BANCA':
            banca += importo
        elif conto == 'CONTANTI':
            contanti += importo
        elif conto == 'INVESTIMENTI':
            saldo_investimenti += importo
        elif conto == 'PENSIONE':
            saldo_pensione += importo

        if t.get('controvalore_btc'):
            saldo_btc_da_eur += float(t['controvalore_btc'])

    saldo_totale_eur = banca + contanti + \
        saldo_investimenti + saldo_pensione

    conn.close()

    return transazioni, banca, contanti, saldo_investimenti, saldo_pensione, saldo_totale_eur, saldo_btc_da_eur


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
                importo, controvalore_btc, valore_btc_eur, conto='BANCA', note=''):

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
            conto,
            note
                
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        data,
        descrizione,
        categoria,
        sottocategoria,
        float(importo),
        controvalore_btc,
        valore_btc_eur,
        conto,
        note
    ))

    conn.commit()
    conn.close()


def leggi_transazioni_da_db(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT 
            id, data, descrizione, categoria, sottocategoria, importo,
            controvalore_btc, valore_btc_eur, conto, note
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
            "conto": r[8],
            "note": r[9]

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
                        'importo', 'controvalore_btc', 'valore_btc_eur', 'conto', 'note'}
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
        SELECT id, data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur, conto, note 
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
                INSERT INTO transazioni (
                    data, descrizione, categoria, sottocategoria, 
                    importo, controvalore_btc, valore_btc_eur, conto, note, user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                t['data'],
                t['descrizione'],
                t['categoria'],
                t['sottocategoria'],
                t['importo'],
                t.get('controvalore_btc', 0),
                t.get('valore_btc_eur', 0),
                t.get('conto', 'BANCA'),
                t.get('note', ''),  # <--- Recupera la nota o mette vuoto
                user_id
            ))
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


def get_spese_per_categoria_filtrate(user_id, tipo_conto, mese=None, anno=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Identifichiamo tabella e colonne giuste
    if tipo_conto == 'LIGHTNING':
        tabella = "transazioni_lightning"
        colonna_valore = "satoshi"
        filtro_uscite = ""  # Di solito su LN/Onchain registri solo uscite, quindi nessun filtro < 0
    elif tipo_conto == 'ONCHAIN':
        tabella = "transazioni_onchain"
        colonna_valore = "importo_btc"
        filtro_uscite = ""
    else:
        tabella = "transazioni"
        colonna_valore = "importo"
        # Per l'Euro vogliamo solo le uscite vere, escludendo i saldi iniziali positivi
        filtro_uscite = f"AND {colonna_valore} < 0"

    filtro_tempo = ""
    parametri = [user_id]
    if mese:
        filtro_tempo = "AND DATA LIKE ?"
        parametri.append(F"{mese}%")  # Es. "2024-06%"
    elif anno:
        filtro_tempo = "AND DATA LIKE ?"
        parametri.append(F"{anno}%")

    # 2. Costruiamo la query dinamica usando {colonna_valore} OVUNQUE
    query = f"""
        SELECT categoria, ABS(SUM({colonna_valore})) as totale 
        FROM {tabella} 
        WHERE user_id=? 
        AND categoria != 'Entrate' 
        {filtro_tempo} 
        {filtro_uscite}
        GROUP BY categoria
        ORDER BY totale DESC
    """

    cursor.execute(query, parametri)
    righe = cursor.fetchall()
    conn.close()

    # 3. Restituiamo i dati (con 8 decimali per On-chain, 2 per gli altri)
    labels_spese = [r[0] for r in righe]
    valori_spese = [round(r[1], 8) if tipo_conto ==
                    'ONCHAIN' else round(r[1], 2) for r in righe]

    return labels_spese, valori_spese


def get_entrate_per_sottocategoria(user_id, tipo_conto, mese=None, anno=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Identifichiamo tabella e colonne giuste
    if tipo_conto == 'LIGHTNING':
        tabella = "transazioni_lightning"
        colonna_valore = "satoshi"
    elif tipo_conto == 'ONCHAIN':
        tabella = "transazioni_onchain"
        colonna_valore = "importo_btc"
    else:
        tabella = "transazioni"
        colonna_valore = "importo"

    filtro_tempo = ""
    parametri = [user_id]
    if mese:
        filtro_tempo = "AND DATA LIKE ?"
        parametri.append(F"{mese}%")  # Es. "2024-06%"
    elif anno:
        filtro_tempo = "AND DATA LIKE ?"
        parametri.append(F"{anno}%")

    # Qui filtriamo solo le entrate (importo > 0) e raggruppiamo per sottocategoria
    # Usiamo ABS() per essere sicuri di sommare valori positivi (o perchè le entrate potrebbero essere negativesegnate diversamente), ma il filtro > 0 garantisce che siano entrate
    query = f"""
        SELECT sottocategoria, ABS(SUM({colonna_valore})) as totale 
        FROM {tabella} 
        WHERE user_id=? 
        AND categoria = 'Entrate' 
        AND {colonna_valore} > 0
        {filtro_tempo}
        GROUP BY sottocategoria
        ORDER BY totale DESC
    """

    cursor.execute(query, parametri)
    righe = cursor.fetchall()
    conn.close()
    print(
        f"DEBUG ENTRATE: Trovate {len(righe)} righe per utente {user_id} in {tipo_conto}")

    # Sostituisci sottocategoria vuota con "Generale"
    labels_entrate = [r[0] if r[0] else "Generale" for r in righe]
    valori_entrate = [round(r[1], 8) if tipo_conto ==
                      'ONCHAIN' else round(r[1], 2) for r in righe]

    return labels_entrate, valori_entrate


def get_bilancio_periodo(user_id, tipo_conto, mese=None, anno=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Scegliamo la tabella e la colonna
    if tipo_conto == 'LIGHTNING':
        tabella, colonna = "transazioni_lightning", "satoshi"
    elif tipo_conto == 'ONCHAIN':
        tabella, colonna = "transazioni_onchain", "importo_btc"
    else:
        tabella, colonna = "transazioni", "importo"

    filtro_tempo = ""
    parametri = [user_id]
    if mese:
        filtro_tempo = "AND data LIKE ?"
        parametri.append(f"{mese}%")
    elif anno:
        filtro_tempo = "AND data LIKE ?"
        parametri.append(f"{anno}%")

    # 1. Calcoliamo le Entrate
    query_entrate = f"SELECT SUM({colonna}) FROM {tabella} WHERE user_id=? AND categoria LIKE 'Entrate' {filtro_tempo}"
    cursor.execute(query_entrate, parametri)
    totale_entrate = cursor.fetchone()[0] or 0

    # 2. Calcoliamo le Spese (tutto ciò che NON è Entrate)
    query_spese = f"SELECT SUM({colonna}) FROM {tabella} WHERE user_id=? AND categoria NOT LIKE 'Entrate' {filtro_tempo}"
    cursor.execute(query_spese, parametri)
    totale_spese = cursor.fetchone()[0] or 0

    conn.close()

    # Restituiamo i valori assoluti per facilità di calcolo
    return abs(totale_entrate), abs(totale_spese)


def crea_tabella_prezzi_btc():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prezzi_btc (
            data TEXT PRIMARY KEY,
            prezzo_eur REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Tabella prezzi_btc RE-INIZIALIZZATA con successo.")


def crea_tabella_mapping():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mapping_categorie (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parola_chiave TEXT NOT NULL UNIQUE,
            categoria TEXT NOT NULL,
            sottocategoria TEXT NOT NULL
        )
    ''')
    # Aggiungiamo qualche esempio iniziale per testare
    esempi = [
        ('VODAFONE', 'Spese Personali', 'Abbonamenti (Netflix, Spotify, ecc)'),
        ('SEVEN PUB', 'Alimentari', 'Ristorante - Bar'),
        ('STIPENDIO', 'Entrate', 'Stipendio'),
        ('ENI', 'Trasporti', 'Carburante'),
        ('ALI', 'Alimentari', 'Supermercato')
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO mapping_categorie (parola_chiave, categoria, sottocategoria)
        VALUES (?, ?, ?)
    ''', esempi)

    conn.commit()
    conn.close()
    print("🧠 Tabella Mapping pronta con i primi esempi!")
