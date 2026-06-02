from db.db_utils import get_db_connection
from flask import request, jsonify, redirect, url_for, flash, render_template
import os
import io
import json
import sqlite3
import binascii
import hashlib
import base64
import time
import traceback
from datetime import datetime, date
import secrets

# Flask & Estensioni
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_login import LoginManager, login_required, UserMixin, current_user, login_remembered
from flask_wtf.csrf import CSRFProtect
from flask import session

# Crittografia & Nostr
from coincurve import PublicKey
from coincurve._libsecp256k1 import lib, ffi
from btclib.ecc import ssa
from hashlib import sha256
from dotenv import load_dotenv
from bech32 import bech32_decode, convertbits, bech32_encode

# Logica di Progetto (i tuoi moduli)


from db.db_utils import (
    DB_PATH, get_user_by_id, inizializza_db, salva_su_db, leggi_transazioni_da_db,
    elimina_transazione_da_db, modifica_transazione_db, get_transazioni_con_saldo,
    salva_su_db_lightning, leggi_transazioni_da_db_lightning, modifica_transazione_db_lightning,
    elimina_transazione_da_db_lightning, get_transazioni_con_saldo_lightning,
    leggi_transazioni_da_db_onchain, salva_su_db_onchain, leggi_transazioni_filtrate_onchain,
    elimina_transazione_da_db_onchain, modifica_transazione_db_onchain, get_transazioni_con_saldo_onchain,
    ripristina_database_completo, get_transazioni_con_saldo_onchain,
    get_spese_per_categoria_filtrate, get_entrate_per_sottocategoria, get_bilancio_periodo, crea_tabella_prezzi_btc, crea_tabella_mapping
)
from utils.crypto import ottieni_valore_btc_eur, euro_to_btc, _carica_storico_btc_eur, aggiorna_prezzo_bitcoin
from utils.export import (
    genera_stringa_backup_json,
    esporta_csv, esporta_csv_per_mese, esporta_csv_lightning,
    esporta_csv_per_mese_lightning, esporta_csv_onchain, esporta_csv_per_mese_onchain
)
from utils.import_manager import anteprima_importazione_csv

from models import User
from utils.helpers import normalizza_importo
from utils.security import decrypt_master_key, encrypt_data, decrypt_data

from werkzeug.utils import secure_filename

load_dotenv()

CATEGORIE = {
    'Entrate': [
        'Cedole O Dividendi', 'Stipendio', 'Rimborso', 'Regalo', 'Donazioni',
        'Claim giochi online', 'Plusvalenze Investimenti', 'Altro'
    ],
    'Abitazione': [
        'Affitto/Mutuo', 'Bollette: Luce', 'Bollette: acqua',
        'Bollette: Gas', 'Bollette: Rifiuti', 'Manutenzione',
        'Spese condominiali', 'Assicurazione casa', 'IMU'
    ],
    'Alimentari': [
        'Supermercato', 'Ristorante - Bar', 'Spesa online', 'Altro'
    ],
    'Trasporti': [
        'Carburante', 'Mezzi pubblici', 'Manutenzione auto / moto',
        'Assicurazione auto', 'Bollo auto', 'Taxi / Uber',
        'Noleggi', 'Parcheggi / pedaggi', 'Altro'
    ],
    'Spese Personali': [
        'Abbigliamento / Scarpe', 'Igiene personale', 'Parrucchiere / estetista',
        'Abbonamenti (Netflix, Spotify, ecc)', 'Libri / Riviste'
    ],
    'Tempo Libero': [
        'Cinema / Teatro / Eventi', 'Sport / Palestra', 'Viaggi / Vacanze',
        'Hobby / Collezioni', 'Giochi / App'
    ],
    'Patrimonio & Finanze': [
        'Commissioni bancarie', 'Interessi passivi', 'Imposte di bollo / IVAFE',
        'Acquisto Titoli/Fondi (Giroconto)', 'Versamento Pensione (Giroconto)',
        'Investimento Crypto', 'Prelievo Contante'
    ],
    'Tasse & Stato': [
        'IRPEF (Saldo/Acconto)', 'Capital Gain (Tassazione)', 'Multe', 'Altro'
    ],
    'Lavoro & Studio': [
        'Ufficio / Coworking', 'Formazione / Corsi', 'Materiali didattici',
        'Trasporti lavoro', 'Pasti lavoro'
    ],
    'Famiglia': [
        'Spese scolastiche', 'Abbigliamento bambino', 'Salute bambino',
        'Giocattoli', 'Baby sitter / Asilo', 'Regali fatti', 'Altro'
    ],
    'Salute': [
        'Farmacia', 'Visita medica', 'Assicurazione Sanitaria', 'Altro'
    ],
    'Imprevisti': [
        'Riparazioni urgenti', 'Emergenze', 'Sostituzione tech'
    ]
}


app = Flask(__name__)


@app.after_request
def add_header(response):
    # Questo comando dice a ngrok di saltare la pagina di avviso
    response.headers['ngrok-skip-browser-warning'] = 'true'
    return response


# Prende la chiave dal file .env.
# Se non la trova, usa un valore di backup (solo per sviluppo!)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-key-per-test')

app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True

# Inizializziamo il modulo
csrf = CSRFProtect(app)

app.config['WTF_CSRF_ENABLED'] = True

# --- INIZIALIZZAZIONE AUTOMATICA (Plug & Play) ---


def setup_application():
    """Crea le cartelle necessarie e inizializza i database se non esistono."""
    # 1. Crea la cartella static/img se non esiste (per le icone)
    os.makedirs(os.path.join('static', 'img'), exist_ok=True)

    # 2. Controlla e inizializza i database
    if not os.path.exists(DB_PATH):
        print("🟡 Database non trovato. Inizializzazione in corso...")
        inizializza_db()
        print("🟢 Database creato con successo!")
    else:
        print("🔵 Database esistente rilevato.")


# Esegui il setup prima di far partire il server
with app.app_context():
    setup_application()


@app.route('/test-amber')
@app.route('/test-amber<path:extra>')
def test_amber(extra=None):
    # Passiamo 'extra' (che contiene la chiave o la firma) direttamente al template
    return render_template('test_amber.html', extra_data=extra)
# ----------------------------------------------------


@app.get("/api/challenge")
def get_challenge():
    challenge = binascii.hexlify(os.urandom(32)).decode()
    timestamp = int(time.time())
    session["challenge"] = challenge
    session["challenge_timestamp"] = timestamp
    return {"challenge": challenge, "timestamp": timestamp}


@app.route('/login_nostr')
def login_nostr():
    return render_template('login_nostr.html')


def npub_to_hex(npub):
    hrp, data = bech32_decode(npub)
    decoded = convertbits(data, 5, 8, False)
    return bytes(decoded).hex()


def hex_to_npub(hex_str):
    try:
        data = bytes.fromhex(hex_str)
        converted = convertbits(data, 8, 5)
        return bech32_encode("npub", converted)
    except Exception as e:
        print(f"Errore conversione HEX->NPUB: {e}")
        return hex_str


@app.post("/api/verify")
@csrf.exempt
def verify_signature():
    body = request.json
    event = body["event"]
    npub_hex = body["npub"]

    # --- AGGIUNTA PER COMPATIBILITÀ AMBER (MOBILE) ---
    if "id" not in event:
        serialized_array = [0, event["pubkey"], event["created_at"],
                            event["kind"], event["tags"], event["content"]]
        serialized_str = json.dumps(
            serialized_array, separators=(',', ':'), ensure_ascii=False)
        event["id"] = sha256(serialized_str.encode('utf-8')).hexdigest()
    # --------------------------------------------------

    # Verifica presenza challenge
    challenge = session.get("challenge")
    timestamp_challenge = session.get("challenge_timestamp")

    if not challenge:
        return {"ok": False, "error": "no challenge"}, 400

    if event["content"] != challenge:
        return {"ok": False, "error": "content mismatch"}, 400

    try:
        # --- VERIFICA FIRMA ---
        pubkey_xonly = bytes.fromhex(event["pubkey"])
        sig_bytes = bytes.fromhex(event["sig"])
        event_id_bytes = bytes.fromhex(event["id"])

        ctx = lib.secp256k1_context_create(lib.SECP256K1_CONTEXT_NONE)
        xonly_pubkey = ffi.new('secp256k1_xonly_pubkey *')

        parse_result = lib.secp256k1_xonly_pubkey_parse(
            ctx, xonly_pubkey, pubkey_xonly)
        if parse_result != 1:
            lib.secp256k1_context_destroy(ctx)
            return {"ok": False, "error": "invalid pubkey"}, 400

        result = lib.secp256k1_schnorrsig_verify(
            ctx, sig_bytes, event_id_bytes, 32, xonly_pubkey)
        lib.secp256k1_context_destroy(ctx)

        if result == 1:
            print(f"✅ Firma verificata per: {npub_hex[:10]}...")

            # --- GESTIONE UTENTE NEL DATABASE ---
            from flask_login import login_user
            from db.db_utils import get_user_by_npub, create_user_from_npub

            # 1. Cerca l'utente (nel DB pulito dopo bonifica)
            user_row = get_user_by_npub(npub_hex)

            # 2. Se non esiste, lo creiamo ora
            if not user_row:
                real_npub = hex_to_npub(npub_hex)
                print(f"📝 Nuovo utente rilevato, creazione in corso...")
                create_user_from_npub(npub_hex, real_npub)
                # Ricarica dopo creazione
                user_row = get_user_by_npub(npub_hex)

            # 3. Ora user_row NON può essere None. Facciamo il login.
            if user_row:
                # user_row[0] è l'ID, user_row[1] è lo username, user_row[3] è l'npub
                # Passiamo tutto a SimpleUser
                user = SimpleUser(
                    id=user_row[0], username=user_row[1], npub=user_row[3])
                login_user(user, remember=True)

                print(f"🚀 Login completato con successo!")
                return {"ok": True}
            else:
                return {"ok": False, "error": "Errore creazione database"}, 500

        else:
            print("❌ Firma non valida")
            return {"ok": False, "error": "invalid signature"}, 401

    except Exception as e:
        print(f"❌ Errore critico: {str(e)}")
        traceback.print_exc()
        return {"ok": False, "error": str(e)}, 400


# LOGIN: inizializzazione minimale di Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


# Minimal user loader so `current_user` is available in templates
class SimpleUser(UserMixin):
    def __init__(self, id, username, npub=None):
        self.id = id
        self.username = username
        self.npub = npub  # Aggiungiamo il campo npub


@login_manager.user_loader
def load_user(user_id):
    row = get_user_by_id(int(user_id))
    if not row:
        return None
    # Usiamo il metodo from_db_row che abbiamo aggiornato in auth.py
    # che ora include anche encrypted_master_key
    return User.from_db_row(row)

    crea_tabella_prezzi_btc()


@app.route('/')
@login_required
def home():
    aggiorna_prezzo_bitcoin()
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    # 1. Recupero dati dai vari wallet
    dati, banca, contanti, s_inv, s_pen, saldo_totale_eur, btc_da_eur = get_transazioni_con_saldo(
        current_user.id)
    dati_lightning, saldo_totale_satoshi, saldo_eur_lightning = get_transazioni_con_saldo_lightning(
        current_user.id)
    dati_onchain, saldo_totale_btc = get_transazioni_con_saldo_onchain(
        current_user.id)

    # 2. RECUPERO PREZZO BTC (SPOSTATO QUI PER EVITARE L'ERRORE)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT prezzo_eur FROM prezzi_btc ORDER BY data DESC LIMIT 1")
    prezzo_record = cursor.fetchone()
    prezzo_attuale_btc = prezzo_record[0] if prezzo_record else 0
    # Teniamo la connessione aperta un attimo per i calcoli successivi se serve, o chiudiamola dopo.

    # 3. Calcoli incrociati e Dashboard
    saldo_eur_onchain = sum(float(t['controvalore_eur'])
                            for t in dati_onchain if t.get('controvalore_eur') is not None)

    liquidita_totale = banca + contanti
    patrimonio_investito = s_inv + s_pen

    # Valore attuale dei wallet crypto
    valore_attuale_onchain = saldo_totale_btc * prezzo_attuale_btc
    valore_attuale_lightning_eur = (
        saldo_totale_satoshi / 100000000) * prezzo_attuale_btc

    # Patrimonio totale (Fiat + Valore attuale Crypto)
    net_worth_totale = saldo_totale_eur + \
        valore_attuale_lightning_eur + valore_attuale_onchain

    # 4. CALCOLO CONTROVALORE DINAMICO (Ora prezzo_attuale_btc esiste!)
    if prezzo_attuale_btc > 0:
        controvalore_btc_reale = saldo_totale_eur / prezzo_attuale_btc
    else:
        controvalore_btc_reale = 0.0

    # 5. Prepariamo i dati per il grafico e extra_data
    labels_grafico = [
        'Disponibilità (Banca/Contanti)', 'Investimenti/Pensione', 'Lightning', 'On-chain']
    valori_grafico = [
        round(liquidita_totale, 2),
        round(patrimonio_investito, 2),
        round(valore_attuale_lightning_eur, 2),
        round(valore_attuale_onchain, 2)
    ]

    extra_data = [
        f"{controvalore_btc_reale:.8f} BTC" if controvalore_btc_reale else "N/A",
        "N/A",
        f"{int(saldo_totale_satoshi)} SATS" if saldo_totale_satoshi else "N/A",
        f"{saldo_totale_btc:.8f} BTC" if saldo_totale_btc else "N/A"
    ]

    # --- LOGICA RENDIMENTO (USIAMO IL PREZZO GIÀ PRESO) ---
    rendimento_onchain = valore_attuale_onchain - saldo_eur_onchain
    percentuale_onchain = (
        rendimento_onchain / saldo_eur_onchain * 100) if saldo_eur_onchain > 0 else 0

    rendimento_lightning = valore_attuale_lightning_eur - saldo_eur_lightning
    percentuale_lightning = (
        rendimento_lightning / saldo_eur_lightning * 100) if saldo_eur_lightning > 0 else 0

    conn.close()

    return render_template('index.html',
                           banca=banca,
                           contanti=contanti,
                           s_inv=s_inv,
                           s_pen=s_pen,
                           liquidita_totale=liquidita_totale,
                           patrimonio_investito=patrimonio_investito,
                           saldo_totale_eur=saldo_totale_eur,
                           saldo_btc_da_eur=controvalore_btc_reale,
                           saldo_totale_satoshi=saldo_totale_satoshi,
                           saldo_eur_lightning=saldo_eur_lightning,
                           saldo_totale_btc=saldo_totale_btc,
                           saldo_eur_onchain=saldo_eur_onchain,
                           net_worth_totale=net_worth_totale,
                           labels_grafico=labels_grafico,
                           valori_grafico=valori_grafico,
                           extra_data=extra_data,
                           rendimento_onchain=rendimento_onchain,
                           percentuale_onchain=percentuale_onchain,
                           rendimento_lightning=rendimento_lightning,
                           percentuale_lightning=percentuale_lightning
                           )


@app.route('/transazioni')
@login_required
def transazioni():
    user_id = current_user.id

    # Recuperiamo TUTTO in un colpo solo dalla funzione che abbiamo appena sistemato
    dati, banca, contanti, invest, pen, saldo_totale_eur, btc_eur = get_transazioni_con_saldo(
        user_id)

    return render_template(
        'transazioni.html',
        transazioni=dati,
        banca=banca,
        contanti=contanti,
        saldo_investimenti=invest,
        saldo_pensione=pen,
        saldo_totale_eur=saldo_totale_eur,
        saldo_btc_da_eur=btc_eur  # Non dimentichiamoci i BTC!
    )


@app.route('/nuova_transazione', methods=['GET', 'POST'])
@login_required
def nuova_transazione():
    if request.method == 'POST':
        data = request.form['data']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form.get('sottocategoria', '')
        conto = request.form['conto']
        note = request.form.get('note', '')

        try:
            importo_normalizzato = float(
                normalizza_importo(request.form['importo']))
            if importo_normalizzato is None:
                flash("Importo non valido", "error")
                return redirect(url_for('nuova_transazione'))
            importo = float(importo_normalizzato)
            valore_btc_eur = ottieni_valore_btc_eur(data)
            controvalore_btc = euro_to_btc(
                importo, valore_btc_eur) if valore_btc_eur else None

        # Salviamo sia valore controvalore (btc) che BTC (€/BTC)
            registra_transazione_conto(
                current_user.id, data, descrizione, categoria, sottocategoria, importo, controvalore_btc=controvalore_btc,
                valore_btc_eur=valore_btc_eur, conto=conto, note=note)

            return redirect(url_for('transazioni'))
        except ValueError:
            return "Importo non valido", 400

    # Se GET, mostra il file
    return render_template(
        'nuova_transazione.html',
        transazione=[None, None, None, '', '',
                     '', None, None],  # valori placeholder
        categorie=list(CATEGORIE.keys()),
        categorie_json=json.dumps(CATEGORIE))


@app.route('/elimina_transazione/<int:id_transazione>', methods=['POST'])
@login_required
def elimina_transazione_eur(id_transazione):
    user_id = current_user.id

    # 1. Elimina la transazione (fai solo questo)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM transazioni WHERE id=? AND user_id=?", (id_transazione, user_id))
    conn.commit()
    conn.close()

    # 2. Messaggio per l'utente
    flash("Transazione eliminata con successo", "success")

    # 3. REINDIRIZZA alla pagina principale delle transazioni
    # Supponendo che la tua rotta per vedere le transazioni EUR si chiami 'home'
    # (quella che abbiamo sistemato prima con le 5 variabili)
    return redirect(url_for('transazioni'))


@app.route('/modifica-transazione/<int:id_transazione>', methods=['GET', 'POST'])
@login_required
def modifica_transazione_eur(id_transazione):
    # 1. Recupero la transazione per assicurarmi che esista
    transazioni = leggi_transazioni_da_db(current_user.id)
    t = next((tr for tr in transazioni if tr["id"] == id_transazione), None)

    if t is None:
        flash("Transazione non trovata", "error")
        return redirect(url_for('transazioni'))

    # --- SE L'UTENTE PREME SALVA (POST) ---
    if request.method == 'POST':
        data = request.form['data']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        conto = request.form['conto'].strip().upper()
        note = request.form.get('note', '')
        importo_normalizzato = normalizza_importo(request.form['importo'])

        if "INVESTIMENTI" in conto:
            conto = "INVESTIMENTI"
        if "PENSIONE" in conto:
            conto = "PENSIONE"
        if importo_normalizzato is None:
            flash("Importo non valido", "error")
            return redirect(url_for('modifica_transazione_eur', id_transazione=id_transazione))

        importo = float(importo_normalizzato)
        vecchio_importo = t['importo']
        vecchia_data = t['data']

        # --- UNICA CONNESSIONE PER TUTTO ---
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            # 1. Calcolo BTC (facciamolo prima di salvare)
            valore_btc_eur = ottieni_valore_btc_eur(data)
            controvalore_btc = euro_to_btc(
                importo, valore_btc_eur) if valore_btc_eur else 0.0

            # 2. Aggiornamento massivo della transazione PRINCIPALE
            cursor.execute("""
                UPDATE transazioni
                SET data=?, descrizione=?, categoria=?, sottocategoria=?,
                    importo=?, conto=?, note=?, valore_btc_eur=?, controvalore_btc=?
                WHERE id=? AND user_id=?
            """, (data, descrizione, categoria, sottocategoria,
                  importo, conto, note, valore_btc_eur, controvalore_btc,
                  id_transazione, current_user.id))

            # 3. LOGICA GEMELLA
            importo_da_cercare = -vecchio_importo
            cursor.execute("""
                SELECT id FROM transazioni
                WHERE user_id=? AND data=? AND abs(importo - ?) < 0.01 AND id != ?
            """, (current_user.id, vecchia_data, importo_da_cercare, id_transazione))

            gemella_row = cursor.fetchone()

            if gemella_row:
                id_gemella = gemella_row[0]
                # Aggiorniamo la gemella con l'importo OPPOSTO e i nuovi dati btc
                cursor.execute("""
                    UPDATE transazioni
                    SET data=?, descrizione=?, importo=?, note=?,
                        valore_btc_eur=?, controvalore_btc=?
                    WHERE id=? AND user_id=?
                """, (data, descrizione, -importo, note,
                      valore_btc_eur, -controvalore_btc, id_gemella, current_user.id))
                flash("Aggiornata anche la transazione gemella!", "info")

            conn.commit()
            flash("Transazione modificata con successo!", "success")

        except Exception as e:
            conn.rollback()
            flash(f"Errore durante l'aggiornamento: {e}", "error")
        finally:
            conn.close()

        return redirect(url_for('transazioni'))

    # --- SE L'UTENTE ENTRA NELLA PAGINA (GET) ---
    transazione_dict = {
        "id": t["id"], "data": t["data"], "descrizione": t["descrizione"],
        "categoria": t["categoria"], "sottocategoria": t["sottocategoria"],
        "importo": t["importo"], "conto": t["conto"], "note": t.get("note", "")
    }

    return render_template(
        'modifica_transazione.html',
        transazione=transazione_dict,
        categorie=list(CATEGORIE.keys()),
        categorie_json=json.dumps(CATEGORIE)

    )


@app.route('/backup-protetto', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def backup_protetto():
    # Generiamo il timestamp una volta sola per entrambi i flussi
    data_str = datetime.now().strftime("%Y%m%d_%H%M")

    # --- FLUSSO NOSTR ---
    if current_user.auth_type == 'nostr':
        firma_nostr = request.args.get(
            'signature') or request.args.get('result')

        if firma_nostr and len(str(firma_nostr)) > 60:
            # Per Nostr scarichiamo il JSON in chiaro (per ora)
            json_data = genera_stringa_backup_json(current_user.id)
            buffer = io.BytesIO(json_data.encode('utf-8'))
            buffer.seek(0)

            # Nome file uniforme anche per Nostr
            nome_file_nostr = f"beesy_backup_{current_user.username}_{data_str}.json"
            return send_file(
                buffer,
                as_attachment=True,
                download_name=nome_file_nostr,
                mimetype="application/json"
            )
        return render_template('backup_confirm.html')

    # --- FLUSSO TRADIZIONALE ---
    if request.method == 'POST':
        password = request.form.get('password')
        print(
            f"DEBUG: Tentativo backup tradizionale per {current_user.username}")

        # FORZIAMO la decriptazione via password ignorando il tipo utente
        # Assicurati che decrypt_master_key accetti questi due parametri
        try:
            m_key = decrypt_master_key(current_user, password)
        except Exception as e:
            print(f"ERRORE CRITICO DECRIPT: {e}")
            m_key = None

        if not m_key:
            print("DEBUG: La Master Key non è stata sbloccata.")
            flash("Password errata! Impossibile sbloccare la Master Key.", "error")
            return redirect(url_for('backup_protetto'))

        print("✅ Master Key sbloccata con successo!")
        json_data = genera_stringa_backup_json(current_user.id)
        json_criptato = encrypt_data(json_data, m_key)

        buffer = io.BytesIO(json_criptato.encode('utf-8'))
        buffer.seek(0)

        # Nome file uniforme con estensione .enc per i file criptati
        nome_file_enc = f"beesy_backup_{current_user.username}_{data_str}.json.enc"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=nome_file_enc,
            mimetype="application/octet-stream"
        )
    return render_template('backup_confirm.html')


@app.route('/ripristino-protetto', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def ripristino_protetto():
    if request.method == 'POST':
        password_o_firma = request.form.get('password')
        # AGGIUNGI QUESTO SOLO PER TEST:
        print(
            f"DEBUG: Password ricevuta lunga {len(password_o_firma)} caratteri")
        file = request.files.get('backup_file')

        if not file or not password_o_firma:
            flash("File e password/firma mancanti!", "error")
            return redirect(url_for('ripristino_protetto'))

        try:
            # 1. Leggiamo il contenuto del file
            raw_content = file.read().decode('utf-8')
            print(f"DEBUG: File letto, lunghezza: {len(raw_content)}")

            # 2. Gestione differenziata
            if current_user.auth_type == 'nostr':
                print("DEBUG: Utente Nostr - Caricamento diretto JSON")
                data = json.loads(raw_content)
            else:
                print(
                    "DEBUG: Utente Tradizionale - Controllo se il file è in chiaro o criptato")
                try:
                    # PROVA A LEGGERE DIRETTAMENTE (Se è il backup in chiaro di debug)
                    data = json.loads(raw_content)
                    print("DEBUG: File in chiaro rilevato, procedo senza decriptazione")
                except json.JSONDecodeError:
                    # SE FALLISCE, ALLORA PROVA A DECRIPTARLO (Procedura normale)
                    print("DEBUG: File criptato rilevato, avvio decriptazione")
                    m_key = decrypt_master_key(current_user, password_o_firma)
                    if not m_key:
                        flash("Password errata!", "error")
                        return redirect(url_for('ripristino_protetto'))

                    decrypted_json = decrypt_data(raw_content, m_key)
                    if not decrypted_json:
                        print("DEBUG: Fallimento decrypt_data")
                        flash("Impossibile decriptare il file.", "error")
                        return redirect(url_for('ripristino_protetto'))
                    data = json.loads(decrypted_json)

            # 3. Scrittura nel Database
            successo = ripristina_database_completo(current_user.id, data)

            if successo:
                print("✅ RIPRISTINO: Database aggiornato con successo!")
                flash("🔥 Cronologia ripristinata correttamente!", "success")
                return redirect(url_for('home'))
            else:
                print("❌ RIPRISTINO: Errore durante la scrittura delle tabelle")
                flash("Errore tecnico nel database.", "error")

        except json.JSONDecodeError:
            print("❌ ERRORE: Il file non è un JSON valido!")
            flash("Il file caricato non è valido o è corrotto.", "error")
        except Exception as e:
            print(f"❌ ERRORE CRITICO: {str(e)}")
            flash(f"Errore imprevisto: {str(e)}", "error")

    return render_template('ripristino_protetto.html')


@app.route('/scarica-csv')
@login_required
def scarica_csv():
    nome_file = 'exports/transazioni.csv'
    # Genera il csv aggiornato filtrato per utente
    esporta_csv(nome_file, user_id=current_user.id)
    return send_file(nome_file, as_attachment=True, download_name=f"transazioni.csv")


@app.route('/scarica-csv-mese', methods=['GET', 'POST'])
@login_required
def scarica_csv_per_mese():
    if request.method == 'POST':
        mese = request.form['mese']  # esempio formato YYYY-MM
        if len(mese) != 7 or not mese[:4].isdigit() or mese[4] != '-' or not mese[5:].isdigit():
            flash("⚠️ Formato mese non valido. Usa YYYY-MM.", "error")
            return redirect(url_for('scarica_csv_per_mese'))

        nome_file = f'exports/transazioni_{mese}.csv'
        # Genera il csv aggiornato filtrato per utente
        esporta_csv_per_mese(mese, user_id=current_user.id)
        return send_file(nome_file, as_attachment=True, download_name=f"transazioni_{mese}.csv")

    return render_template('scarica_csv_per_mese.html')


def registra_transazione_conto(user_id, data, descrizione, categoria, sottocategoria, importo, conto, controvalore_btc=None, valore_btc_eur=None, note=''):
    """
    Gestisce automaticamente i trasferimenti BANCA ↔ CONTANTI.
    Aggiornato con i nuovi nomi delle categorie.
    """
    # --- CASO 1: INVESTIMENTI (PAC o Versamenti grossi) ---
    if sottocategoria == "Acquisto Titoli/Fondi (Giroconto)":
        # 1. Togliamo i soldi dalla BANCA (Uscita reale)
        salva_su_db(user_id, data, descrizione, categoria, sottocategoria,
                    importo, controvalore_btc, valore_btc_eur, conto="BANCA", note=note)
        # 2. Li aggiungiamo al conto INVESTIMENTI (Aumento del fondo)
        salva_su_db(user_id, data, f"Caricamento: {descrizione}", categoria, sottocategoria, abs(
            importo), None, None, conto="INVESTIMENTI", note="Giroconto automatico")
        return

    # --- CASO 2: PENSIONE COMPLEMENTARE ---
    if sottocategoria == "Versamento Pensione (Giroconto)":
        # 1. Uscita dalla BANCA
        salva_su_db(user_id, data, descrizione, categoria,
                    sottocategoria, importo, None, None, conto="BANCA", note=note)
        # 2. Entrata nel conto PENSIONE
        salva_su_db(user_id, data, f"Versamento: {descrizione}", categoria, sottocategoria, abs(
            importo), None, None, conto="PENSIONE", note="Giroconto automatico")
        return

    # 3. PRELIEVO (Soldi che escono dalla BANCA per andare nei CONTANTI)
    # Usiamo i nuovi nomi: "Patrimonio & Finanze" e "Prelievo Contante"
    if categoria == "Patrimonio & Finanze" and sottocategoria == "Prelievo Contante" and importo < 0:
        # Nota: Qui potresti voler concatenare la nota dell'utente a quella automatica
        nota_giroconto = f"{note} (Giroconto)".strip()
        # Togli dalla banca (segna la spesa reale)
        salva_su_db(user_id, data, descrizione, categoria, sottocategoria, importo,
                    controvalore_btc, valore_btc_eur, conto="BANCA")

        # Aggiungi ai contanti (giroconto interno)
        salva_su_db(user_id, data,
                    "Giroconto: Prelievo da banca",
                    "Patrimonio & Finanze",
                    "Trasferimento",
                    abs(importo),
                    None, None,
                    conto="CONTANTI")
        return

    # 2. DEPOSITO (Soldi contanti che versi in BANCA)
    if categoria == "Patrimonio & Finanze" and sottocategoria == "Prelievo Contante" and importo > 0:
        # Aggiungi alla banca
        salva_su_db(user_id, data, descrizione, categoria, sottocategoria, importo,
                    controvalore_btc, valore_btc_eur, conto="BANCA")

        # Togli dai contanti
        salva_su_db(user_id, data,
                    "Giroconto: Versamento in banca",
                    "Patrimonio & Finanze",
                    "Trasferimento",
                    -abs(importo),
                    None, None,
                    conto="CONTANTI")
        return

    # Se non è un prelievo/deposito, salva normalmente sul conto selezionato
    salva_su_db(user_id, data, descrizione, categoria, sottocategoria, importo,
                controvalore_btc, valore_btc_eur, conto=conto, note=note)


@app.route('/transazioni_lightning')
@login_required
def transazioni_lightning():

    # Questa funzione restituisce 3 valori (lista, saldo sats, saldo eur)
    dati_lightning, saldo_totale_satoshi, saldo_eur_lightning = get_transazioni_con_saldo_lightning(
        current_user.id)

    # *CAMBIARE 'index.html' con 'transazioni_lightning.html'*
    return render_template("transazioni_lightning.html",
                           transazioni_lightning=dati_lightning,
                           saldo_totale_satoshi=saldo_totale_satoshi,
                           saldo_eur_lightning=saldo_eur_lightning
                           )


@app.route('/nuova_transazione_lightning', methods=['GET', 'POST'])
@login_required
def nuova_transazione_lightning():
    if request.method == 'POST':
        data = request.form['data']
        wallet = request.form['wallet']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        satoshi = int(request.form['satoshi'])

        try:
            valore_btc_eur = ottieni_valore_btc_eur(data)
            controvalore_eur = (satoshi / 100_000_000) * \
                valore_btc_eur if valore_btc_eur else None

            salva_su_db_lightning(
                user_id=current_user.id,
                data=data,
                wallet=wallet,
                descrizione=descrizione,
                categoria=categoria,
                sottocategoria=sottocategoria,
                satoshi=satoshi,
                controvalore_eur=controvalore_eur,
                valore_btc_eur=valore_btc_eur
            )

            flash("Transazione Lightning salvata con successo", "success")
            return redirect(url_for('transazioni_lightning'))

        except Exception as e:
            flash(f"Errore: {e}", "error")
            return redirect(url_for('nuova_transazione_lightning'))

    return render_template(
        'nuova_transazione_lightning.html',
        categorie=list(CATEGORIE.keys()),
        categorie_json=json.dumps(CATEGORIE)
    )


@app.route('/elimina_transazione_lightning/<int:id_transazione>', methods=['POST'])
@login_required
def elimina_transazione_web_lightning(id_transazione):
    # 1. Esegui l'eliminazione
    elimina_transazione_da_db_lightning(id_transazione, current_user.id)

    # 2. Manda il messaggio di conferma
    flash("Transazione eliminata con successo", "success")

    # 3. REINDIRIZZA alla rotta che elenca le transazioni
    # In questo modo 'get_transazioni_con_saldo_lightning' verrà chiamata
    # automaticamente dalla funzione 'transazioni_lightning'
    return redirect(url_for('transazioni_lightning'))


@app.route('/modifica-transazione_lightning/<int:id_transazione>', methods=['GET', 'POST'])
@login_required
def modifica_transazione_web_lightning(id_transazione):
    # Leggi tutte le transazioni e e cerca quella con id = id_transazione
    transazioni_lightning = leggi_transazioni_da_db_lightning(current_user.id)
    t = None
    for tr in transazioni_lightning:
        if tr['id'] == id_transazione:
            t = tr
            break
    if t is None:
        flash("Transazione non trovata", "error")
        return redirect(url_for('transazioni'))

    if request.method == 'POST':
        data = request.form['data']
        wallet = request.form['wallet']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        satoshi = request.form['satoshi']
        # chiama la funzione di modifica
        modifica_transazione_db_lightning(
            id_transazione, 'data', data, current_user.id)
        modifica_transazione_db_lightning(
            id_transazione, 'wallet', wallet, current_user.id)
        modifica_transazione_db_lightning(
            id_transazione, 'descrizione', descrizione, current_user.id)
        modifica_transazione_db_lightning(
            id_transazione, 'categoria', categoria, current_user.id)
        modifica_transazione_db_lightning(
            id_transazione, 'sottocategoria', sottocategoria, current_user.id)
        modifica_transazione_db_lightning(
            id_transazione, 'satoshi', satoshi, current_user.id)
        # Ricalcola e aggiorna BTC
        valore_btc_eur = ottieni_valore_btc_eur(data)

        if valore_btc_eur is not None:
            # Calcola il controvalore in euro in base ai satoshi
            controvalore_eur = (int(satoshi) / 100_000_000) * valore_btc_eur

            # Aggiorna i campi corretti nel DB
            modifica_transazione_db_lightning(
                id_transazione, 'valore_btc_eur', valore_btc_eur, current_user.id)
            modifica_transazione_db_lightning(
                id_transazione, 'controvalore_eur', controvalore_eur, current_user.id)
        else:
            flash("⚠️ Impossibile ottenere il valore BTC per la data selezionata. Verifica la connessione o riprova più tardi.", "error")

        dati_lightning, saldo_totale_satoshi, saldo_eur_lightning = get_transazioni_con_saldo_lightning(
            current_user.id)
        return render_template('transazioni_lightning.html',
                               transazioni_lightning=dati_lightning,
                               saldo_totale_satoshi=saldo_totale_satoshi,
                               saldo_eur_lightning=saldo_eur_lightning)

    # Se GET, mostra il form con i dati precompilati
    return render_template(
        'modifica_transazione_lightning.html',
        transazione_lightning=t,
        categorie=list(CATEGORIE.keys()),
        categorie_json=json.dumps(CATEGORIE)
    )


@app.route('/scarica_csv_lightning')
@login_required
def scarica_csv_lightning():
    nome_file = 'exports/transazioni_lightning.csv'
    # Genera il csv aggiornato filtrato per utente
    esporta_csv_lightning(nome_file, user_id=current_user.id)
    return send_file(nome_file, as_attachment=True, download_name=f"transazioni_lightning.csv")


@app.route('/scarica_csv_lightning_per_mese', methods=['GET', 'POST'])
@login_required
def scarica_csv_per_mese_lightning():
    if request.method == 'POST':
        mese = request.form['mese']  # esempio formato YYYY-MM
        if len(mese) != 7 or not mese[:4].isdigit() or mese[4] != '-' or not mese[5:].isdigit():
            flash("⚠️ Formato mese non valido. Usa YYYY-MM.", "error")
            return redirect(url_for('scarica_csv_per_mese_lightning'))

        nome_file_completo = esporta_csv_per_mese_lightning(
            mese, user_id=current_user.id)
        if nome_file_completo:
            # Se il nome del file è stato restituito, il file esiste.
            download_name = f"transazioni_{mese}_lightning.csv"
            return send_file(nome_file_completo, as_attachment=True, download_name=download_name)
        else:
            # Se è None, il file non è stato creato (es. dati mancanti)
            flash(
                f"⚠️ Nessuna transazione Lightning trovata per il mese {mese}.", "error_lightning")
            # Reindirizza l'utente alla pagina di download
            return redirect(url_for('scarica_csv_per_mese_lightning'))
    return render_template('scarica_csv_per_mese_lightning.html')


@app.route('/transazioni_onchain')
@login_required
def transazioni_onchain():
    dati_onchain, saldo_totale_btc = get_transazioni_con_saldo_onchain(
        current_user.id)
    return render_template("transazioni_onchain.html", transazioni_onchain=dati_onchain, saldo_totale_btc=saldo_totale_btc)


@app.route('/nuova_transazione_onchain', methods=['GET', 'POST'])
@login_required
def nuova_transazione_onchain():
    if request.method == 'POST':
        data = request.form['data']
        wallet = request.form['wallet']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        transactionID = request.form['transactionID']
        importo_btc = float(request.form['importo_btc'])
        fee = float(request.form['fee'])
        try:
            valore_btc_eur = ottieni_valore_btc_eur(data)
            controvalore_eur = importo_btc * valore_btc_eur
            valore_btc_eur if valore_btc_eur else None

            salva_su_db_onchain(
                user_id=current_user.id,
                data=data,
                wallet=wallet,
                descrizione=descrizione,
                categoria=categoria,
                sottocategoria=sottocategoria,
                transactionID=transactionID,
                importo_btc=importo_btc,
                fee=fee,
                controvalore_eur=controvalore_eur,
                valore_btc_eur=valore_btc_eur
            )

            flash("Transazione On-chain salvata con successo", "success")
            return redirect(url_for('transazioni_onchain'))

        except Exception as e:
            flash(f"Errore: {e}", "error")
            return redirect(url_for('nuova_transazione_onchain'))

    placeholder_transazione = {
        "id": None, "data": "", "wallet": "", "descrizione": "",
        "categoria": "", "sottocategoria": "", "transactionID": "",
        "importo_btc": 0.0, "fee": 0.0, "controvalore_eur": 0.0, "valore_btc_eur": 0.0
    }

    return render_template(
        'nuova_transazione_onchain.html',
        transazione_onchain=placeholder_transazione,  # Passa un dizionario
        categorie=list(CATEGORIE.keys()),
        categorie_json=json.dumps(CATEGORIE)
    )


# Nel tuo file app.py, funzione elimina_transazione_web_onchain

@app.route('/elimina_transazione_onchain/<int:id_transazione>', methods=['POST'])
@login_required
def elimina_transazione_web_onchain(id_transazione):
    # Aggiungi questa riga
    print(f"ID Utente Loggato (current_user.id): {current_user.id}")
    elimina_transazione_da_db_onchain(id_transazione, current_user.id)
    # 2. Manda il messaggio di conferma
    flash("Transazione eliminata con successo", "success")

    # 3. REINDIRIZZA alla rotta che elenca le transazioni
    # In questo modo 'get_transazioni_con_saldo_lightning' verrà chiamata
    # automaticamente dalla funzione 'transazioni_lightning'
    return redirect(url_for('transazioni_onchain'))


@app.route('/modifica-transazione_onchain/<int:id_transazione>', methods=['GET', 'POST'])
@login_required
def modifica_transazione_web_onchain(id_transazione):
    # Leggi tutte le transazioni e e cerca quella con id = id_transazione
    transazioni_onchain = leggi_transazioni_da_db_onchain(current_user.id)
    t = None
    for tr in transazioni_onchain:
        if tr['id'] == id_transazione:
            t = tr
            break
    if t is None:
        flash("Transazione non trovata", "error")
        return redirect(url_for('transazioni_onchain'))

    if request.method == 'POST':
        data = request.form['data']
        wallet = request.form['wallet']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        transactionID = request.form['transactionID']
        importo_btc = float(request.form['importo_btc'])
        fee = float(request.form['fee'])
        # chiama la funzione di modifica
        modifica_transazione_db_onchain(
            id_transazione, 'data', data, current_user.id)
        modifica_transazione_db_onchain(
            id_transazione, 'wallet', wallet, current_user.id)
        modifica_transazione_db_onchain(
            id_transazione, 'descrizione', descrizione, current_user.id)
        modifica_transazione_db_onchain(
            id_transazione, 'categoria', categoria, current_user.id)
        modifica_transazione_db_onchain(
            id_transazione, 'sottocategoria', sottocategoria, current_user.id)
        modifica_transazione_db_onchain(
            id_transazione, 'transactionID', transactionID, current_user.id)
        modifica_transazione_db_onchain(
            id_transazione, 'importo_btc', importo_btc, current_user.id)
        modifica_transazione_db_onchain(
            id_transazione, 'fee', fee, current_user.id)
        # Ricalcola e aggiorna BTC
        valore_btc_eur = ottieni_valore_btc_eur(data)
        if valore_btc_eur:
            controvalore_eur = importo_btc * valore_btc_eur
            modifica_transazione_db_onchain(
                id_transazione, 'valore_btc_eur', valore_btc_eur, current_user.id)
            modifica_transazione_db_onchain(
                id_transazione, 'controvalore_eur', controvalore_eur, current_user.id)
        else:
            flash("⚠️ Impossibile ottenere il valore BTC/EUR", "error")

        flash("✅ Transazione aggiornata con successo", "success")
        return redirect(url_for('transazioni_onchain'))

    # Se GET, mostra il form con i dati precompilati
    return render_template(
        'modifica_transazione_onchain.html',
        transazione_onchain=t,
        categorie=list(CATEGORIE.keys()),
        categorie_json=json.dumps(CATEGORIE)
    )


@app.route('/scarica_csv_onchain')
@login_required
def scarica_csv_onchain():
    nome_file = 'exports/transazioni_onchain.csv'
    # Genera il csv aggiornato filtrato per utente
    esporta_csv_onchain(nome_file, user_id=current_user.id)
    return send_file(nome_file, as_attachment=True, download_name=f"transazioni_onchain.csv")


@app.route('/scarica_csv_onchain_per_mese', methods=['GET', 'POST'])
@login_required
def scarica_csv_per_mese_onchain():
    if request.method == 'POST':
        mese = request.form['mese']  # esempio formato YYYY-MM
        if len(mese) != 7 or not mese[:4].isdigit() or mese[4] != '-' or not mese[5:].isdigit():
            flash("⚠️ Formato mese non valido. Usa YYYY-MM.", "error")
            return redirect(url_for('scarica_csv_per_mese_onchain'))

        nome_file = f'exports/transazioni_{mese}_onchain.csv'
        # Genera il csv aggiornato filtrato per utente
        esporta_csv_per_mese_onchain(mese, user_id=current_user.id)
        return send_file(nome_file, as_attachment=True, download_name=f"transazioni_{mese}_onchain.csv")

    return render_template('scarica_csv_per_mese_onchain.html')


@app.route('/analytics/<tipo>')
@login_required
def analytics(tipo):
    # Usiamo la connessione universale intelligente
    from db.db_utils import get_db_connection

    mese_selezionato = request.args.get('mese')
    anno_selezionato = request.args.get('anno')

    if mese_selezionato:
        anno_selezionato = None
    if not mese_selezionato:
        mese_selezionato = None
    if not anno_selezionato:
        anno_selezionato = None

    # 1. Recupero dati grafici e bilancio standard
    labels_spese, valori_spese = get_spese_per_categoria_filtrate(
        current_user.id, tipo, mese=mese_selezionato, anno=anno_selezionato)

    labels_entrate, valori_entrate = get_entrate_per_sottocategoria(
        current_user.id, tipo, mese=mese_selezionato, anno=anno_selezionato)

    tot_entrate, tot_spese = get_bilancio_periodo(
        current_user.id, tipo, mese=mese_selezionato, anno=anno_selezionato)

    delta = tot_entrate - tot_spese
    saving_rate = (delta / tot_entrate * 100) if tot_entrate > 0 else 0

    # Inizializziamo le variabili per i grafici Bitcoin (vuote di default per l'Euro)
    date_btc = []
    saldi_btc = []
    saldi_eur_btc = []

    # --- INIZIO LOGICA RENDIMENTO E GRAFICI UNIFICATA (BTC & SATS) ---
    rendimento = 0
    percentuale = 0
    valore_attuale_eur = 0
    saldo_asset = 0
    costo_storico_eur = 0

    if tipo in ['ONCHAIN', 'LIGHTNING']:
        conn = get_db_connection()  # <-- Connessione corretta e sicura!
        cursor = conn.cursor()

        # 1. Prendiamo l'ultimo prezzo BTC (serve per i calcoli veloci)
        cursor.execute(
            "SELECT prezzo_eur FROM prezzi_btc ORDER BY data DESC LIMIT 1")
        prezzo_record = cursor.fetchone()
        prezzo_attuale_btc = prezzo_record[0] if prezzo_record else 0

        # 2. Recuperiamo anche TUTTI i prezzi storici per generare la linea temporale del grafico
        cursor.execute(
            "SELECT data, prezzo_eur FROM prezzi_btc ORDER BY data ASC")
        prezzi_rows = cursor.fetchall()
        prezzi_storici = {row['data']: row['prezzo_eur']
                          for row in prezzi_rows}

        if tipo == 'ONCHAIN':
            from db.db_utils import get_transazioni_con_saldo_onchain
            _, saldo_asset = get_transazioni_con_saldo_onchain(current_user.id)

            cursor.execute(
                "SELECT SUM(controvalore_eur) FROM transazioni_onchain WHERE user_id = ?", (current_user.id,))
            res = cursor.fetchone()
            costo_storico_eur = res[0] if res[0] else 0
            valore_attuale_eur = saldo_asset * prezzo_attuale_btc

            # Query Storica Grafico On-chain (Sottraiamo le fee se registrate come costo positivo)
            cursor.execute('''
                SELECT SUBSTR(data, 1, 10) as giorno, 
                       SUM(importo_btc - IFNULL(fee, 0)) as flusso
                FROM transazioni_onchain 
                WHERE user_id = ? 
                GROUP BY giorno ORDER BY giorno ASC
            ''', (current_user.id,))
            tx_storiche = cursor.fetchall()

        elif tipo == 'LIGHTNING':
            from db.db_utils import get_transazioni_con_saldo_lightning
            _, saldo_asset, _ = get_transazioni_con_saldo_lightning(
                current_user.id)

            cursor.execute(
                "SELECT SUM(controvalore_eur) FROM transazioni_lightning WHERE user_id = ?", (current_user.id,))
            res = cursor.fetchone()
            costo_storico_eur = res[0] if res[0] else 0
            valore_attuale_eur = (saldo_asset / 100000000) * prezzo_attuale_btc

            # Query Storica Grafico Lightning (Convertiamo i satoshi in BTC fluttuanti)
            cursor.execute('''
                SELECT SUBSTR(data, 1, 10) as giorno, 
                       SUM(satoshi * 0.00000001) as flusso
                FROM transazioni_lightning 
                WHERE user_id = ? 
                GROUP BY giorno ORDER BY giorno ASC
            ''', (current_user.id,))
            tx_storiche = cursor.fetchall()

        # Calcoliamo il saldo progressivo temporale per il grafico Bitcoin
        saldo_temporale_btc = 0.0
        for tx in tx_storiche:
            giorno = tx['giorno']
            flusso = tx['flusso']
            saldo_temporale_btc += flusso

            # Troviamo il prezzo di quel giorno specifico nel DB, se manca usiamo l'ultimo noto
            prezzo_quel_giorno = prezzi_storici.get(giorno, prezzo_attuale_btc)
            controvalore_fiat_storico = saldo_temporale_btc * prezzo_quel_giorno

            date_btc.append(str(giorno))
            saldi_btc.append(round(saldo_temporale_btc, 8))
            saldi_eur_btc.append(round(controvalore_fiat_storico, 2))

        # Calcoli finali comuni del box rendimento
        rendimento = valore_attuale_eur - costo_storico_eur
        if costo_storico_eur > 0:
            percentuale = (rendimento / costo_storico_eur) * 100

        conn.close()

    # --- RECUPERO ASSET TRADIZIONALI (Solo per tipo EURO) ---
    investimenti_fiat = []
    cronologia_fiat = []
    date_fiat = []
    valori_fiat = []

    if tipo == 'EURO':
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM assets_watch WHERE user_id = ?", (current_user.id,))
        investimenti_fiat = cursor.fetchall()

        try:
            cursor.execute('''
                SELECT h.*, w.nome_asset
                FROM assets_history h
                JOIN assets_watch w ON h.asset_id = w.id
                WHERE w.user_id = ?
                ORDER BY h.data_rilevazione DESC
            ''', (current_user.id,))
            cronologia_fiat = cursor.fetchall()
        except Exception as e:
            print(f"Nota nel recupero cronologia: {e}")

        cursor.execute('''
            SELECT SUBSTR(data_rilevazione, 1, 10) as giorno, SUM(valore_rilevato) as totale
            FROM assets_history
            JOIN assets_watch w ON assets_history.asset_id = w.id
            WHERE w.user_id = ?
            GROUP BY giorno ORDER BY giorno ASC
        ''', (current_user.id,))
        dati_grafico_fiat = cursor.fetchall()

        date_fiat = [str(row['giorno']) for row in dati_grafico_fiat]
        valori_fiat = [float(row['totale']) for row in dati_grafico_fiat]

        conn.close()

    titoli = {
        'EURO': 'Statistiche Euro (€)',
        'LIGHTNING': 'Statistiche Lightning (⚡)',
        'ONCHAIN': 'Statistiche On-chain (₿)'
    }

    return render_template('analytics.html',
                           labels_spese=labels_spese,
                           valori_spese=valori_spese,
                           labels_entrate=labels_entrate,
                           valori_entrate=valori_entrate,
                           tipo=tipo,
                           titolo_pagina=titoli.get(tipo, "Statistiche"),
                           mese_selezionato=mese_selezionato,
                           anno_selezionato=anno_selezionato,
                           tot_entrate=tot_entrate,
                           tot_spese=tot_spese,
                           delta=delta,
                           savings_rate=saving_rate,
                           rendimento=rendimento,
                           percentuale=percentuale,
                           valore_attuale_eur=valore_attuale_eur,
                           costo_storico_eur=costo_storico_eur,
                           investimenti_fiat=investimenti_fiat,
                           cronologia_fiat=cronologia_fiat,
                           date_fiat=date_fiat,
                           valori_fiat=valori_fiat,
                           # --- NUOVI DATI PASSATI A JINJA PER I GRAFICI BITCOIN ---
                           date_btc=date_btc,
                           saldi_btc=saldi_btc,
                           saldi_eur_btc=saldi_eur_btc
                           )


@app.route('/add_asset', methods=['POST'])
@login_required
def add_asset():
    nome = request.form.get('nome_asset')
    investito = request.form.get('capitale_investito')
    attuale = request.form.get('valore_attuale')

    if nome and investito and attuale:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO assets_watch (user_id, nome_asset, capitale_investito, valore_attuale)
            VALUES (?, ?, ?, ?)
        ''', (current_user.id, nome, float(investito), float(attuale)))
        conn.commit()
        conn.close()

    return redirect(url_for('analytics', tipo='EURO'))


@app.route('/update_asset_value', methods=['POST'])
@login_required
def update_asset_value():
    asset_id = request.form.get('asset_id')
    nuovo_valore = request.form.get('nuovo_valore')

    if asset_id and nuovo_valore:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Inseriamo il nuovo record nello storico per non perdere il passato
        cursor.execute('''
            INSERT INTO assets_history (asset_id, valore_rilevato)
            VALUES (?, ?)
        ''', (int(asset_id), float(nuovo_valore)))

        # 2. Aggiorniamo comunque il 'valore_attuale' nella tabella principale per comodità di lettura veloce
        cursor.execute('''
            UPDATE assets_watch
            SET valore_attuale = ?, data_aggiornamento = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        ''', (float(nuovo_valore), int(asset_id), current_user.id))

        conn.commit()
        conn.close()

    return redirect(url_for('analytics', tipo='EURO'))


@app.route('/modifica_asset/<int:asset_id>', methods=['POST'])
@login_required
def modifica_asset(asset_id):
    from db.db_utils import get_db_connection

    nuovo_nome = request.form.get('nuovo_nome')

    if nuovo_nome:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Forziamo gli ID a intero per evitare brutte sorprese con SQLite
            int_asset_id = int(asset_id)
            int_user_id = int(current_user.id)

            print(
                f"DEBUG: Tentativo di modifica asset {int_asset_id} per utente {int_user_id} con nome: '{nuovo_nome.strip()}'")

            # Eseguiamo l'aggiornamento
            cursor.execute('''
                UPDATE assets_watch
                SET nome_asset = ?
                WHERE id = ? AND user_id = ?
            ''', (nuovo_nome.strip(), int_asset_id, int_user_id))

            # Verifichiamo quante righe sono state effettivamente modificate
            righe_modificate = cursor.rowcount
            print(f"DEBUG: Righe modificate nel DB: {righe_modificate}")

            conn.commit()
            conn.close()

            return redirect(url_for('analytics', tipo='EURO'))

        except Exception as e:
            print(f"Errore durante la modifica dell'asset: {e}")
            return "Si è verificato un errore", 500

    return redirect(url_for('analytics', tipo='EURO'))


@app.route('/elimina_cronologia/<int:history_id>/<tipo>', methods=['POST'])
@login_required
def elimina_cronologia(history_id, tipo):
    from db.db_utils import get_db_connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Eliminiamo la riga specifica dalla cronologia
        cursor.execute(
            'DELETE FROM assets_history WHERE id = ?', (history_id,))

        conn.commit()
        conn.close()
        print(f"❌ Riga cronologia {history_id} eliminata correttamente!")

    except Exception as e:
        print(f"Errore durante l'eliminazione della cronologia: {e}")

    return redirect(url_for('analytics', tipo=tipo))


@app.route('/faq')
def faq():
    return render_template('faq.html')


@app.route('/backup-protetto<path:extra>')
@login_required
def catch_amber(extra):
    # Se Amber sputa la firma dopo l'URL, lo rimandiamo a quella pulita con la firma come parametro
    return redirect(url_for('backup_protetto', signature=extra))


# Cartella temporanea per il caricamento
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@app.route('/importa_csv', methods=['GET', 'POST'])
@login_required
def importa_csv():
    if request.method == 'POST':
        if 'file_csv' not in request.files:
            flash("Nessun file selezionato", "danger")
            return redirect(request.url)

        file = request.files['file_csv']
        if file.filename == '':
            return redirect(request.url)

        if file and file.filename.endswith('.csv'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            try:
                # Chiamiamo il nostro "Cervello"
                dati_anteprima = anteprima_importazione_csv(
                    filepath, current_user.id)

                # 🔥 SICUREZZA: Cancelliamo il file subito dopo la lettura
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(
                        f"🗑️ File temporaneo {filename} eliminato per privacy.")

                # Nota: passiamo 'transazioni' e 'tutte_categorie' al template
                return render_template('importa_anteprima.html',
                                       transazioni=dati_anteprima,
                                       tutte_categorie=CATEGORIE)

            except Exception as e:
                flash(f"Errore durante l'analisi del file: {e}", "danger")
                return redirect(request.url)

    return render_template('importa_csv.html')


@app.route('/conferma_importazione', methods=['POST'])
@login_required
def conferma_importazione():
    try:
        form_data = request.form
        indici = [k.split('_')[1]
                  for k in form_data.keys() if k.startswith('data_')]

        count = 0
        for i in indici:
            data = form_data.get(f'data_{i}')
            desc = form_data.get(f'desc_{i}')
            importo = float(form_data.get(f'importo_{i}'))
            categoria = form_data.get(f'cat_{i}')
            sottocategoria = form_data.get(f'sub_{i}')

            # Recuperiamo il valore BTC calcolato nell'anteprima
            controvalore_btc = float(form_data.get(f'btc_{i}'))

            # Calcoliamo il prezzo spot (valore di 1 BTC quel giorno)
            valore_spot = abs(
                importo / controvalore_btc) if controvalore_btc != 0 else 0

            # 🔥 IL MOMENTO MAGICO: Chiamiamo il "Vigile Urbano"
            # Questa funzione da sola farà:
            # - Il salvataggio normale
            # - OPPURE lo sdoppiamento se vede "Prelievo Contante"
            registra_transazione_conto(
                user_id=current_user.id,
                data=data,
                descrizione=desc,
                categoria=categoria,
                sottocategoria=sottocategoria,
                importo=importo,
                conto="BANCA",  # Origine sempre banca per il CSV
                controvalore_btc=controvalore_btc,
                valore_btc_eur=valore_spot
            )

            # 3. APPRENDIMENTO (Questo lo teniamo qui perché riguarda l'importazione)
            if 'ricorda_mapping' in form_data:
                parola_chiave = desc.split()[0].upper()
                if len(parola_chiave) > 3:
                    # Usiamo una connessione rapida per il mapping
                    with sqlite3.connect('database.db') as conn:
                        conn.execute('''
                            INSERT OR REPLACE INTO mapping_categorie (parola_chiave, categoria, sottocategoria)
                            VALUES (?, ?, ?)
                        ''', (parola_chiave, categoria, sottocategoria))

            count += 1

        flash(
            f"✅ Ottimo Den! Abbiamo importato {count} movimenti con successo.", "success")
        return redirect(url_for('home'))

    except Exception as e:
        flash(f"❌ Errore durante il salvataggio: {e}", "danger")
        return redirect(url_for('importa_csv'))


# storage temporaneo in memoria
TEMP_BACKUPS = {}  # token -> raw_content

# storage temporaneo in memoria
TEMP_BACKUPS = {}  # token -> raw_content

# ATTENZIONE: Questa parte è un laboratorio aperto.
# Obiettivo: rendere il ripristino Nostr su mobile stabile come quello PC.
# Contattami su GitHub se hai idee!


@app.route('/carica-file-temporaneo', methods=['POST'])
@csrf.exempt
def carica_file_temporaneo():
    data = request.get_json()
    if data and 'backup_data' in data:
        session['temp_backup_data'] = data['backup_data']
        print(
            f"DEBUG: File salvato in sessione ({len(data['backup_data'])} caratteri)")
        return "OK", 200
    return "No data", 400


@app.route('/test_nostr_ripristino_protetto', methods=['GET', 'POST'])
@csrf.exempt
def test_nostr_ripristino_protetto():
    if request.args:
        print(f"DEBUG: Parametri ricevuti nell'URL: {request.args}")

    signature = (
        request.args.get("signature")
        or request.args.get("event")
        or request.args.get("result")
    )

    if signature:
        print(
            f"DEBUG: Amber è tornato! Signature (primi 10): {signature[:10]}...")
        raw_content = session.get('temp_backup_data')

        if not raw_content:
            print("DEBUG: ERRORE - File non trovato in sessione!")
            flash("Sessione scaduta o file perso. Riprova.", "error")
            return redirect(url_for('test_nostr_ripristino_protetto'))

        try:
            data = json.loads(raw_content)
            if ripristina_database_completo(current_user.id, data):
                session.pop('temp_backup_data', None)
                print("✅ RIPRISTINO MOBILE COMPLETATO!")
                flash("🔥 Ripristino con Amber riuscito!", "success")
                return redirect(url_for('home'))
        except Exception as e:
            print(f"DEBUG: Errore JSON o DB: {str(e)}")
            flash(f"Errore: {str(e)}", "error")

    return render_template('test_nostr_ripristino_protetto.html')

# FINE LABORATORIO.


@app.context_processor
def inject_dev_mode():
    # Troviamo la cartella dove gira il server
    base_dir = os.path.abspath(os.path.dirname(__file__))
    percorso_file = os.path.join(base_dir, '.dev_mode')

    # Controlliamo se esiste
    is_dev = os.path.exists(percorso_file)

    # STAMPA DI DIAGNOSTICA: Guarda cosa esce nel terminale nero!
    print(f"🔎 DEBUG BADGE: Sto cercando il file in: {percorso_file}")
    print(f"🔮 DEBUG BADGE: Il file esiste davvero? -> {is_dev}")

    return dict(is_dev_mode=is_dev)


if __name__ == '__main__':
    # register auth blueprint lazily to avoid circular import at module load
    try:
        from auth import auth_bp
        app.register_blueprint(auth_bp)
    except Exception:
        pass
    app.run(host='0.0.0.0', port=5000, debug=True)
