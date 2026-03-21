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
    get_spese_per_categoria_filtrate, get_entrate_per_sottocategoria, get_bilancio_periodo
)
from utils.crypto import ottieni_valore_btc_eur, euro_to_btc, _carica_storico_btc_eur
from utils.export import (
    genera_stringa_backup_json,
    esporta_csv, esporta_csv_per_mese, esporta_csv_lightning,
    esporta_csv_per_mese_lightning, esporta_csv_onchain, esporta_csv_per_mese_onchain

)
from models import User
from utils.helpers import normalizza_importo
from utils.security import decrypt_master_key, encrypt_data, decrypt_data

load_dotenv()

CATEGORIE = {
    'Entrate': ['Stipendio', 'Rimborso', 'Regalo', 'Donazioni', 'claim giochi online', 'Altro'],
    'Abitazione': ['Affitto/Mutuo', 'Bollette: Luce', 'Bollette: acqua', 'Bollette: Gas', 'Bollette: Rifiuti', 'Manutenzione', 'Spese condominiali', 'Assicurazione casa'],
    'Alimentari': ['Supermercato', 'Ristorante - Bar', 'Spesa online', 'Altro'],
    'Trasporti': ['Carburante', 'Mezzi pubblici', 'Manutenzione auto / moto', 'Assicurazione auto', 'Bollo auto', 'Taxi / Uber', 'Noleggi', 'Parcheggi / pedaggi', 'Altro'],
    'Spese Personali': ['Abbigliamento / Scarpe', 'Igiene personale', 'Parrucchiere / estetista', 'Abbonamenti personali (Netflix, Spotify, ecc)', 'Libri / Riviste'],
    'Tempo Libero & Intrattenimento': ['Cinema / Teatro / Eventi', 'Sport / Palestra', 'Viaggi / Vacanze', 'Hobby / Collezioni', 'Giochi / App a pagamento'],
    'Finanze & Banche': ['Commissioni bancarie', 'Interessi passivi', 'Prelievi / Depositi', 'Investimenti', 'Criptovalute', 'Giroconti'],
    'Lavoro & Studio': ['Spese di ufficio / coworking', 'Formazione / Corsi', 'Libri / Materiali didattici', 'Trasporti lavoro / studio', 'Pasti lavoro'],
    'Famiglia & Bambini': ['Spese scolastiche', 'Abbigliamento bambino', 'Salute bambino', 'Giocattoli', 'Baby sitter / Asilo', 'Altro'],
    'Salute': ['Farmacia', 'Visita medica', 'Altro']
}


app = Flask(__name__)

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


@app.route('/')
@login_required
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    dati, saldo_totale_eur, saldo_banca, saldo_contanti, saldo_btc_da_eur = get_transazioni_con_saldo(
        current_user.id)
    dati_lightning, saldo_totale_satoshi, saldo_eur_lightning = get_transazioni_con_saldo_lightning(
        current_user.id)
    dati_onchain, saldo_totale_btc = get_transazioni_con_saldo_onchain(
        current_user.id)

    # Calcola controvalore BTC per il tracker EUR
    saldo_btc_da_eur = sum(float(t["controvalore_btc"])
                           for t in dati if t["controvalore_btc"] is not None)

    # Calcola controvalore EUR per on-chain
    saldo_eur_onchain = sum(float(t['controvalore_eur'])
                            for t in dati_onchain if t['controvalore_eur'] is not None)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT SUM(importo) FROM transazioni WHERE user_id=? AND conto='BANCA'", (current_user.id,))
    saldo_banca = cursor.fetchone()[0] or 0

    cursor.execute(
        "SELECT SUM(importo) FROM transazioni WHERE user_id=? AND conto='CONTANTI'", (current_user.id,))
    saldo_contanti = cursor.fetchone()[0] or 0

    conn.close()

    saldo_totale_eur = saldo_banca + saldo_contanti

    # Prepariamo i dati per il grafico
    # Creiamo due liste, una per i nomi e una per i valori in Eur
    labels_grafico = ['Banca (EUR)', 'Contanti (EUR)',
                      'Lightning (EUR)', 'On-chain (EUR)']
    valori_grafico = [
        round(saldo_banca, 2),
        round(saldo_contanti, 2),
        round(saldo_eur_lightning, 2),
        round(saldo_eur_onchain, 2)
    ]
    # Valori extra per il tooltip
    extra_data = [
        f"{saldo_btc_da_eur:.8f} BTC" if saldo_btc_da_eur else "N/A",  # Per Banca
        # I contanti non hanno controvalore BTC
        f"{0.0:.8f} BTC" if saldo_contanti else "N/A",
        f"{int(saldo_totale_satoshi)} SATS".replace(
            ",", ".") if saldo_totale_satoshi else "N/A",  # Per Lightning
        f"{saldo_totale_btc:.8f} BTC" if saldo_totale_btc else "N/A"  # Per On-chain

    ]

    return render_template('index.html',
                           saldo_banca=saldo_banca,
                           saldo_contanti=saldo_contanti,
                           saldo_totale_eur=saldo_totale_eur,
                           saldo_btc_da_eur=saldo_btc_da_eur,
                           saldo_totale_satoshi=saldo_totale_satoshi,
                           saldo_eur_lightning=saldo_eur_lightning,
                           saldo_totale_btc=saldo_totale_btc,
                           saldo_eur_onchain=saldo_eur_onchain,
                           labels_grafico=labels_grafico,
                           valori_grafico=valori_grafico,
                           extra_data=extra_data
                           )


@app.route('/transazioni')
@login_required
def transazioni():
    user_id = current_user.id

    # Ora qui ricevi già i dizionari
    dati, saldo_totale, saldo_banca, saldo_contanti, saldo_btc_da_eur = get_transazioni_con_saldo(
        user_id)

    # Calcolo saldo BANCA / CONTANTI
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT SUM(importo) FROM transazioni WHERE user_id=? AND conto='BANCA'",
        (user_id,)
    )
    saldo_banca = cursor.fetchone()[0] or 0

    cursor.execute(
        "SELECT SUM(importo) FROM transazioni WHERE user_id=? AND conto='CONTANTI'",
        (user_id,)
    )
    saldo_contanti = cursor.fetchone()[0] or 0

    conn.close()

    saldo_totale_eur = saldo_banca + saldo_contanti

    return render_template(
        'transazioni.html',
        transazioni=dati,
        saldo_totale=saldo_totale,
        saldo_banca=saldo_banca,
        saldo_contanti=saldo_contanti,
        saldo_totale_eur=saldo_totale_eur
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
                valore_btc_eur=valore_btc_eur, conto=conto)

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
    # Leggi la transazione
    transazioni = leggi_transazioni_da_db(current_user.id)
    t = next((tr for tr in transazioni if tr["id"] == id_transazione), None)

    if t is None:
        flash("Transazione non trovata", "error")
        return redirect(url_for('transazioni'))

    if request.method == 'POST':
        data = request.form['data']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        conto = request.form['conto']
        importo_normalizzato = normalizza_importo(request.form['importo'])

        if importo_normalizzato is None:
            flash("Importo non valido", "error")
            return redirect(url_for('modifica_transazione_eur', id_transazione=id_transazione))

        importo = float(importo_normalizzato)

        # Aggiorna i campi base
        campi_da_modificare = {
            'data': data,
            'descrizione': descrizione,
            'categoria': categoria,
            'sottocategoria': sottocategoria,
            'importo': importo,
            'conto': conto
        }

        for campo, valore in campi_da_modificare.items():
            modifica_transazione_db(
                id_transazione, campo, valore, current_user.id)

        # --- Ricalcolo BTC ---------------------
        from datetime import datetime, date

        data_dt = datetime.strptime(data, "%Y-%m-%d").date()
        oggi = date.today()

        if data_dt > oggi:
            # Data futura → NON chiamare CoinGecko
            flash("⚠️ La data è futura: mantengo i valori BTC già presenti.", "info")

        else:
            valore_btc_eur = ottieni_valore_btc_eur(data)

            if valore_btc_eur is not None:
                controvalore_btc = euro_to_btc(importo, valore_btc_eur)
                modifica_transazione_db(
                    id_transazione, 'valore_btc_eur', valore_btc_eur, current_user.id)
                modifica_transazione_db(
                    id_transazione, 'controvalore_btc', controvalore_btc, current_user.id)
            else:
                flash(
                    "⚠️ Impossibile ottenere il valore BTC per la data selezionata.", "error")

        # Aggiorna tabella
        dati, saldo_totale, saldo_banca, saldo_contanti, saldo_btc_da_eur = get_transazioni_con_saldo(
            current_user.id)

        return render_template(
            'transazioni.html',
            transazioni=dati,
            saldo_totale=saldo_totale,
            saldo_banca=saldo_banca,
            saldo_contanti=saldo_contanti
        )

    # ----- GET -----
    transazione_dict = {
        "id": t["id"],
        "data": t["data"],
        "descrizione": t["descrizione"],
        "categoria": t["categoria"],
        "sottocategoria": t["sottocategoria"],
        "importo": t["importo"],
        "controvalore_btc": t.get("controvalore_btc"),
        "valore_btc_eur": t.get("valore_btc_eur"),
        "conto": t["conto"],
        "user_id": current_user.id
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
    # --- FLUSSO NOSTR ---
    if current_user.auth_type == 'nostr':
        firma_nostr = request.args.get(
            'signature') or request.args.get('result')

        if firma_nostr and len(str(firma_nostr)) > 60:
            # Per Nostr scarichiamo il JSON in chiaro (per ora)
            json_data = genera_stringa_backup_json(current_user.id)
            buffer = io.BytesIO(json_data.encode('utf-8'))
            buffer.seek(0)
            return send_file(
                buffer,
                as_attachment=True,
                download_name=f"beesy_backup_{current_user.username}.json",
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

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"beesy_backup_{current_user.username}.json.enc",
            mimetype="application/octet-stream"
        )
    return render_template('backup_confirm.html')


@app.route('/ripristino-protetto', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def ripristino_protetto():
    if request.method == 'POST':
        password_o_firma = request.form.get('password')
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
                # Per Nostr NON decriptiamo, leggiamo il JSON direttamente
                data = json.loads(raw_content)
            else:
                print("DEBUG: Utente Tradizionale - Decriptazione necessaria")
                # Recuperiamo la master key per utenti password
                m_key = decrypt_master_key(current_user, password_o_firma)
                if not m_key:
                    flash("Password errata!", "error")
                    return redirect(url_for('ripristino_protetto'))

                decrypted_json = decrypt_data(raw_content, m_key)
                if not decrypted_json:
                    print("DEBUG: Fallimento decrypt_data")
                    flash(
                        "Impossibile decriptare il file. Password o file errato.", "error")
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


def registra_transazione_conto(user_id, data, descrizione, categoria, sottocategoria, importo, conto, controvalore_btc=None, valore_btc_eur=None):
    """
    Gestisce automaticamente i trasferimenti BANCA ↔ CONTANTI.
    Ora accetta e passa i valori BTC.
    """

    # PRELIEVO (importo negativo dalla banca)
    if categoria == "Finanze & Banche" and sottocategoria == "Prelievi / Depositi" and importo < 0:
        # 1. Togli dalla banca
        salva_su_db(user_id, data, descrizione, categoria, sottocategoria, importo,
                    # Passa i valori BTC originali per la transazione madre (banca)
                    controvalore_btc, valore_btc_eur, conto="BANCA")

        # 2. Aggiungi ai contanti (la transazione di trasferimento è in EUR, quindi i campi BTC rimangono a None)
        salva_su_db(user_id, data,
                    "Trasferimento da banca a contanti",
                    "Finanze & Banche",
                    "Trasferimento",
                    abs(importo),
                    # I trasferimenti interni (contrari) non devono avere valori BTC
                    None, None,
                    conto="CONTANTI")
        return

    # DEPOSITO (importo positivo nei contanti → banca)
    if categoria == "Finanze & Banche" and sottocategoria == "Prelievi / Depositi" and importo > 0:
        # 1. Aggiungi alla banca
        salva_su_db(user_id, data, descrizione, categoria, sottocategoria, importo,
                    # Passa i valori BTC originali per la transazione madre (banca)
                    controvalore_btc, valore_btc_eur, conto="BANCA")

        # 2. Togli dai contanti
        salva_su_db(user_id, data,
                    "Trasferimento da contanti a banca",
                    "Finanze & Banche",
                    "Trasferimento",
                    -abs(importo),
                    # I trasferimenti interni (contrari) non devono avere valori BTC
                    None, None,
                    conto="CONTANTI")
        return

    # Altre transazioni normali
    # BANCA di default a meno che non arrivi conto="CONTANTI" dal form
    salva_su_db(user_id, data, descrizione, categoria,
                sottocategoria, importo,
                # ✅ Passa i valori BTC calcolati
                controvalore_btc, valore_btc_eur,
                conto=conto)


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
    mese_selezionato = request.args.get('mese')
    anno_selezionato = request.args.get('anno')

    # Se l'utente ha scelto un mese, ignoriamo l'anno (perché il mese include già l'anno es. 2026-01)
    if mese_selezionato:
        anno_selezionato = None
    # -----------------------
    # Se le stringhe sono vuote, trasformale in None
    if not mese_selezionato:
        mese_selezionato = None
    if not anno_selezionato:
        anno_selezionato = None

    # Usiamo la funzione che abbiamo progettato per db_utils
    # Dati spese (barre)
    labels_spese, valori_spese = get_spese_per_categoria_filtrate(
        current_user.id, tipo, mese=mese_selezionato, anno=anno_selezionato)

    labels_entrate, valori_entrate = get_entrate_per_sottocategoria(current_user.id,
                                                                    tipo,
                                                                    mese=mese_selezionato,
                                                                    anno=anno_selezionato)

    # Definiamo un titolo carino in base al tipo
    titoli = {
        'EURO': 'Statistiche Euro (€)',
        'LIGHTNING': 'Statistiche Lightning (⚡)',
        'ONCHAIN': 'Statistiche On-chain (₿)'
    }
    titolo_pagina = titoli.get(tipo, "Statistiche")

    tot_entrate, tot_spese = get_bilancio_periodo(
        current_user.id, tipo, mese=mese_selezionato, anno=anno_selezionato)
    delta = tot_entrate - tot_spese

    saving_rate = 0
    if tot_entrate > 0:
        saving_rate = (delta / tot_entrate) * 100

    return render_template('analytics.html',
                           labels_spese=labels_spese,
                           valori_spese=valori_spese,
                           labels_entrate=labels_entrate,
                           valori_entrate=valori_entrate,
                           tipo=tipo,
                           titolo_pagina=titolo_pagina,
                           mese_selezionato=mese_selezionato,
                           anno_selezionato=anno_selezionato,
                           tot_entrate=tot_entrate,
                           tot_spese=tot_spese,
                           delta=delta,
                           savings_rate=saving_rate
                           )


@app.route('/faq')
def faq():
    return render_template('faq.html')


@app.route('/backup-protetto<path:extra>')
@login_required
def catch_amber(extra):
    # Se Amber sputa la firma dopo l'URL, lo rimandiamo a quella pulita con la firma come parametro
    return redirect(url_for('backup_protetto', signature=extra))


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


if __name__ == '__main__':
    # register auth blueprint lazily to avoid circular import at module load
    try:
        from auth import auth_bp
        app.register_blueprint(auth_bp)
    except Exception:
        pass
    app.run(host='0.0.0.0', port=5000, debug=True)
