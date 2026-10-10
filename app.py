

from werkzeug.utils import secure_filename
from utils.security import decrypt_master_key, encrypt_data, decrypt_data
from utils.helpers import normalizza_importo, formatta_importo, VALUTE_SUPPORTATE, get_exchange_rate
from models import User
from utils.import_manager import anteprima_importazione_csv, anteprima_importazione_blink_csv
from utils.export import (
    genera_stringa_backup_json,
    esporta_csv, esporta_csv_per_mese, esporta_csv_lightning,
    esporta_csv_per_mese_lightning, esporta_csv_onchain, esporta_csv_per_mese_onchain
)
from utils.crypto import ottieni_valore_btc_eur, euro_to_btc, _carica_storico_btc_eur, aggiorna_prezzo_bitcoin
from db.db_utils import (
    DB_PATH, inizializza_db, get_db_connection, get_user_by_id, aggiorna_valuta_utente_db, inizializza_db, salva_su_db, leggi_transazioni_da_db,
    elimina_transazione_da_db, modifica_transazione_db, get_transazioni_con_saldo,
    salva_su_db_lightning, leggi_transazioni_da_db_lightning, modifica_transazione_db_lightning,
    elimina_transazione_da_db_lightning, get_transazioni_con_saldo_lightning,
    leggi_transazioni_da_db_onchain, salva_su_db_onchain, leggi_transazioni_filtrate_onchain,
    elimina_transazione_da_db_onchain, modifica_transazione_db_onchain, get_transazioni_con_saldo_onchain,
    ripristino_database_completo, get_transazioni_con_saldo_onchain,
    get_spese_per_categoria_filtrate, get_entrate_per_sottocategoria, get_bilancio_periodo,
    pulisci_mese, registra_transazione_conto, get_transaction_drill_down

)

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
from flask import request, jsonify, redirect, url_for, flash, render_template
from flask_babel import Babel, _
from flask_babel import gettext as _
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
from bech32 import convertbits, bech32_encode, bech32_decode

# Carica subito le variabili d'ambiente dal file .env
load_dotenv()
# Logica di Progetto (i tuoi moduli)

# --- CONFIGURAZIONE COSTANTI ---
VERSIONE_APP = "0.1.2"

CATEGORIE = {
    'Entrate': [
        'Cedole O Dividendi', 'Interessi attivi', 'Stipendio', 'Rimborso capitale investito',
        'Regalo', 'Donazioni', 'Claim giochi online', 'Plusvalenze Investimenti', 'Altro'
    ],
    'Abitazione': [
        'Affitto/Mutuo', 'Bollette: Luce', 'Bollette: acqua', 'Bollette: Gas',
        'Bollette: Rifiuti', 'Manutenzione', 'Spese condominiali', 'Assicurazione casa', 'IMU'
    ],
    'Alimentari': [
        'Supermercato', 'Ristorante - Bar', 'Spesa online', 'Altro'
    ],
    'Trasporti': [
        'Carburante', 'Mezzi pubblici', 'Manutenzione auto / moto', 'Assicurazione auto',
        'Bollo auto', 'Taxi / Uber', 'Noleggi', 'Parcheggi / pedaggi', 'Altro'
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
        'Commissioni bancarie', 'Interessi passivi', 'Minusvalenze investimenti', 'Imposte di bollo / IVAFE',
        'Acquisto Titoli/Fondi (Giroconto)', 'Versamento Pensione (Giroconto)', 'Investimento Crypto', 'Prelievo Contante'
    ],
    'Tasse & Stato': [
        'IRPEF (Saldo/Acconto)', 'Capital Gain (Tassazione)', 'Multe', 'Altro'
    ],
    'Lavoro & Studio': [
        'Ufficio / Coworking', 'Formazione / Corsi', 'Materiali didattici', 'Trasporti lavoro', 'Pasti lavoro'
    ],
    'Famiglia': [
        'Spese scolastiche', 'Abbigliamento bambino', 'Salute bambino', 'Giocattoli',
        'Baby sitter / Asilo', 'Regali fatti', 'Altro'
    ],
    'Salute': [
        'Farmacia', 'Visita medica', 'Assicurazione Sanitaria', 'Altro'
    ],
    'Imprevisti': [
        'Riparazioni urgenti', 'Emergenze', 'Sostituzione tech'
    ]
}
LISTA_CATEGORIE_UNICHE = [
    _('Entrate'), _('Cedole O Dividendi'), _('Interessi attivi'), _(
        'Stipendio'), _('Rimborso capitale investito'),
    _('Regalo'), _('Donazioni'), _('Claim giochi online'), _(
        'Plusvalenze Investimenti'), _('Altro'),
    _('Abitazione'), _(
        'Affitto/Mutuo'), _('Bollette: Luce'), _('Bollette: acqua'), _('Bollette: Gas'),
    _('Bollette: Rifiuti'), _('Manutenzione'), _(
        'Spese condominiali'), _('Assicurazione casa'), _('IMU'),
    _('Alimentari'), _('Supermercato'), _(
        'Ristorante - Bar'), _('Spesa online'),
    _('Trasporti'), _('Carburante'), _('Mezzi pubblici'), _(
        'Manutenzione auto / moto'), _('Assicurazione auto'),
    _('Bollo auto'), _('Taxi / Uber'), _('Noleggi'), _('Parcheggi / pedaggi'),
    _('Spese Personali'), _(
        'Abbigliamento / Scarpe'), _('Igiene personale'), _('Parrucchiere / estetista'),
    _('Abbonamenti (Netflix, Spotify, ecc)'), _('Libri / Riviste'),
    _('Tempo Libero'), _(
        'Cinema / Teatro / Eventi'), _('Sport / Palestra'), _('Viaggi / Vacanze'),
    _('Hobby / Collezioni'), _('Giochi / App'),
    _('Patrimonio & Finanze'), _('Commissioni bancarie'), _(
        'Interessi passivi'), _('Minusvalenze investimenti'),
    _('Imposte di bollo / IVAFE'), _('Acquisto Titoli/Fondi (Giroconto)'), _(
        'Versamento Pensione (Giroconto)'),
    _('Investimento Crypto'), _('Prelievo Contante'),
    _('Tasse & Stato'), _(
        'IRPEF (Saldo/Acconto)'), _('Capital Gain (Tassazione)'), _('Multe'),
    _('Lavoro & Studio'), _(
        'Ufficio / Coworking'), _('Formazione / Corsi'), _('Materiali didattici'),
    _('Trasporti lavoro'), _('Pasti lavoro'),
    _('Famiglia'), _('Spese scolastiche'), _(
        'Abbigliamento bambino'), _('Salute bambino'), _('Giocattoli'),
    _('Baby sitter / Asilo'), _('Regali fatti'),
    _('Salute'), _('Farmacia'), _('Visita medica'), _('Assicurazione Sanitaria'),
    _('Imprevisti'), _('Riparazioni urgenti'), _(
        'Emergenze'), _('Sostituzione tech')
]

# --- INIZIALIZZAZIONE FLASK ---
app = Flask(__name__)
app.config['DB_PATH'] = DB_PATH
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-key-per-test')

app.jinja_env.filters['formatta_importo'] = formatta_importo

# Cookie & CSRF Settings
app.config['WTF_CSRF_ENABLED'] = True
csrf = CSRFProtect(app)

# Nota: Se riscontri problemi con il Login in locale (127.0.0.1),
# imposta SESSION_COOKIE_SECURE solo quando BEESY_ENV è 'production'
if os.environ.get('BEESY_ENV') == 'production':
    app.config["SESSION_COOKIE_SAMESITE"] = "None"
    app.config["SESSION_COOKIE_SECURE"] = True

# --- TRADUZIONI & BABEL ---


def get_locale():
    # return 'en'
    return request.accept_languages.best_match(['it', 'en', 'zh'])


babel = Babel(app, locale_selector=get_locale)


def traduci_voce(testo):
    # Traduzione dinamica usando Babel
    return _(testo)

# Unico Context Processor per iniettare le variabili nei Template HTML


@app.context_processor
def inject_global_vars():
    return dict(
        traduci=traduci_voce,
        CATEGORIE=CATEGORIE,
        versione_beesy=VERSIONE_APP,
        beesy_env=os.environ.get('BEESY_ENV', 'production')
    )


@app.after_request
def add_header(response):
    response.headers['ngrok-skip-browser-warning'] = 'true'
    return response

# --- INIZIALIZZAZIONE AUTOMATICA DATABASE ---


def setup_application():
    """Crea le cartelle necessarie e assicura la presenza di tutte le tabelle nel DB."""
    os.makedirs(os.path.join('static', 'img'), exist_ok=True)

    if not os.path.exists(DB_PATH):
        print("🟡 Database non trovato. Inizializzazione in corso...")
        inizializza_db()
        print("🟢 Database creato con successo!")
    else:
        print("🔵 Database esistente rilevato. Eseguo controllo aggiornamenti...")
        inizializza_db()


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
    aggiorna_prezzo_bitcoin()
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    # 1. Recupero valuta e simbolo dell'utente
    valuta_utente = getattr(current_user, 'default_currency', 'EUR') or 'EUR'
    simbolo_valuta = VALUTE_SUPPORTATE.get(valuta_utente, '€')

    # Tasso di cambio se la valuta non è EUR
    tasso_fiat = 1.0
    if valuta_utente != 'EUR':
        tasso_fiat = get_exchange_rate('EUR', valuta_utente) or 1.14

    # 2. Recupero dati dai vari wallet
    dati, banca_eur, contanti_eur, s_inv_eur, s_pen_eur, saldo_totale_eur_base, btc_da_eur = get_transazioni_con_saldo(
        current_user.id)
    dati_lightning, saldo_totale_satoshi, saldo_eur_lightning_base = get_transazioni_con_saldo_lightning(
        current_user.id)
    dati_onchain, saldo_totale_btc = get_transazioni_con_saldo_onchain(
        current_user.id)

    # 3. RECUPERO PREZZO BTC LIVE IN EUR
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT prezzo_eur FROM prezzi_btc ORDER BY data DESC LIMIT 1")
    prezzo_record = cursor.fetchone()
    prezzo_attuale_btc_eur = prezzo_record[0] if prezzo_record else 0.0
    conn.close()

    # Prezzo BTC convertito nella valuta utente (es. USD o EUR)
    prezzo_attuale_btc_utente = prezzo_attuale_btc_eur * tasso_fiat

    # 4. Conversioni FIAT nella valuta dell'utente (applicando il tasso di cambio)
    banca = banca_eur * tasso_fiat
    contanti = contanti_eur * tasso_fiat

    # Assicuriamo valore assoluto positivo per gli asset investiti
    s_inv = abs(s_inv_eur) * tasso_fiat
    s_pen = abs(s_pen_eur) * tasso_fiat

    # Subtotali patrimoniali
    liquidita_totale = banca + contanti
    patrimonio_investito = s_inv + s_pen

    # Saldo totale Fiat reale (Liquidità + Investimenti) nella valuta dell'utente
    saldo_totale_eur = liquidita_totale + patrimonio_investito

    # Wallet Crypto - Conversione Storica e Live
    saldo_eur_lightning = saldo_eur_lightning_base * tasso_fiat
    saldo_eur_onchain_base = sum(float(t['controvalore_eur'])
                                 for t in dati_onchain if t.get('controvalore_eur') is not None)
    saldo_eur_onchain = saldo_eur_onchain_base * tasso_fiat

    # 5. Valore ATTUALE LIVE dei wallet crypto nella valuta dell'utente
    valore_attuale_onchain = saldo_totale_btc * prezzo_attuale_btc_utente
    valore_attuale_lightning = (
        saldo_totale_satoshi / 100000000.0) * prezzo_attuale_btc_utente

    # Patrimonio totale NET WORTH (Fiat + Valore LIVE Crypto)
    net_worth_totale = saldo_totale_eur + \
        valore_attuale_lightning + valore_attuale_onchain

    # 6. Controvalore dinamico BTC per i fondi FIAT
    if prezzo_attuale_btc_utente > 0:
        controvalore_btc_reale = saldo_totale_eur / prezzo_attuale_btc_utente
    else:
        controvalore_btc_reale = 0.0

    # 7. Dati per il grafico
    labels_grafico = [
        _('Disponibilità (Banca/Contanti)'),
        _('Investimenti/Pensione'),
        _('Lightning'),
        _('On-chain')
    ]
    valori_grafico = [
        round(liquidita_totale, 2),
        round(patrimonio_investito, 2),
        round(valore_attuale_lightning, 2),
        round(valore_attuale_onchain, 2)
    ]

    extra_data = [
        f"{controvalore_btc_reale:.8f} BTC" if controvalore_btc_reale else "N/A",
        "N/A",
        f"{int(saldo_totale_satoshi)} SATS" if saldo_totale_satoshi else "N/A",
        f"{saldo_totale_btc:.8f} BTC" if saldo_totale_btc else "N/A"
    ]

    # 8. Rendimento Crypto (Valore LIVE Attuale - Costo Storico Salvato)
    rendimento_onchain = valore_attuale_onchain - saldo_eur_onchain
    percentuale_onchain = (
        rendimento_onchain / saldo_eur_onchain * 100) if saldo_eur_onchain > 0 else 0.0

    rendimento_lightning = valore_attuale_lightning - saldo_eur_lightning
    percentuale_lightning = (
        rendimento_lightning / saldo_eur_lightning * 100) if saldo_eur_lightning > 0 else 0.0

    # Totale combinato Bitcoin
    totale_btc_cumulativo = saldo_totale_btc + \
        (saldo_totale_satoshi / 100000000.0)

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
                           valore_attuale_lightning=valore_attuale_lightning,
                           saldo_eur_lightning=saldo_eur_lightning,
                           saldo_totale_btc=saldo_totale_btc,
                           valore_attuale_onchain=valore_attuale_onchain,
                           saldo_eur_onchain=saldo_eur_onchain,
                           net_worth_totale=net_worth_totale,
                           labels_grafico=labels_grafico,
                           valori_grafico=valori_grafico,
                           extra_data=extra_data,
                           rendimento_onchain=rendimento_onchain,
                           percentuale_onchain=percentuale_onchain,
                           rendimento_lightning=rendimento_lightning,
                           percentuale_lightning=percentuale_lightning,
                           simbolo_valuta=simbolo_valuta,
                           beesy_env=os.environ.get('BEESY_ENV', 'production'),
                           totale_btc_cumulativo=totale_btc_cumulativo
                           )


@app.route('/transazioni')
@login_required
def transazioni():
    user_id = current_user.id

    # 1. Recupero valuta e tasso di cambio dell'utente
    valuta_utente = getattr(current_user, 'default_currency', 'EUR') or 'EUR'
    tasso_fiat = 1.0
    if valuta_utente != 'EUR':
        tasso_fiat = get_exchange_rate('EUR', valuta_utente) or 1.14

    # 2. Recuperiamo i dati dal DB
    dati, banca_base, contanti_base, invest_base, pen_base, saldo_totale_eur_base, btc_eur = get_transazioni_con_saldo(
        user_id)

    # 3. Applichiamo la conversione con il tasso fiat dell'utente
    banca = banca_base * tasso_fiat
    contanti = contanti_base * tasso_fiat
    invest = abs(invest_base) * tasso_fiat
    pen = abs(pen_base) * tasso_fiat
    saldo_totale_eur = banca + contanti + invest + pen

    # Ordiniamo la lista 'dati' per data decrescente e id decrescente
    dati_ordinati = sorted(dati, key=lambda x: (
        x['data'], x['id']), reverse=True)

    return render_template(
        'transazioni.html',
        transazioni=dati_ordinati,
        banca=banca,
        contanti=contanti,
        saldo_investimenti=invest,
        saldo_pensione=pen,
        saldo_totale_eur=saldo_totale_eur,
        saldo_btc_da_eur=btc_eur
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

        # Valuta base dell'utente corrente (es. 'EUR', 'USD', 'GBP')
        valuta_utente = getattr(
            current_user, 'default_currency', 'EUR') or 'EUR'

        # Valuta della spesa (se non specificata, usa quella dell'utente)
        valuta_spesa = request.form.get('valuta', valuta_utente).upper()

        try:
            importo_normalizzato = normalizza_importo(request.form['importo'])
            if importo_normalizzato is None:
                flash(_("Importo non valido"), "error")
                return redirect(url_for('nuova_transazione'))

            # 1. Recuperiamo il valore assoluto inserito dall'utente (positivo)
            importo_assoluto = abs(float(importo_normalizzato))

            # 2. Assegniamo il segno in base alla Categoria:
            #    Entrate = POSITIVO (+), Spese/Uscite = NEGATIVO (-)
            if categoria.strip().lower() == 'entrate':
                importo_finale = importo_assoluto
            else:
                importo_finale = -importo_assoluto

            # 3. Calcolo Tasso di Cambio e Importo in Valuta Base
            if valuta_spesa == valuta_utente:
                tasso_cambio = 1.0
                importo_valuta_base = importo_finale
            else:
                # Se l'utente ha inserito un tasso manuale nella form lo usiamo,
                # altrimenti lo recuperiamo automaticamente dall'API
                tasso_form = request.form.get('tasso_cambio')
                if tasso_form and float(tasso_form) > 0:
                    tasso_cambio = float(tasso_form)
                else:
                    tasso_cambio = get_exchange_rate(
                        valuta_spesa, valuta_utente)

                # Convertiamo l'importo (con il suo segno) nella valuta base dell'utente
                importo_valuta_base = importo_finale * tasso_cambio

            # 4. Calcolo controvalore BTC mantenendo il segno dell'importo
            valore_btc_eur = ottieni_valore_btc_eur(data)
            controvalore_btc = euro_to_btc(
                importo_valuta_base, valore_btc_eur) if valore_btc_eur else None

            # 5. Salvataggio nel DB con gli importi col segno corretto
            registra_transazione_conto(
                current_user.id, data, descrizione, categoria, sottocategoria, importo_finale,
                controvalore_btc=controvalore_btc, valore_btc_eur=valore_btc_eur,
                conto=conto, note=note, valuta=valuta_spesa,
                importo_valuta_base=importo_valuta_base, tasso_cambio=tasso_cambio
            )

            return redirect(url_for('transazioni'))
        except ValueError:
            return "Importo non valido", 400

    # Se GET, mostra il form passando la valuta predefinita dell'utente
    valuta_default = getattr(current_user, 'default_currency', 'EUR') or 'EUR'
    return render_template(
        'nuova_transazione.html',
        valute=VALUTE_SUPPORTATE,
        valuta_default=valuta_default,
        transazione=[None, None, None, '', '', '', None, None],
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

    # Valuta base di preferenza dell'utente (default a EUR se non impostata)
    valuta_utente = getattr(current_user, 'default_currency', 'EUR') or 'EUR'

    # --- SE L'UTENTE PREME SALVA (POST) ---
    if request.method == 'POST':
        data = request.form['data']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        conto = request.form['conto'].strip().upper()
        note = request.form.get('note', '')

        # NUOVI CAMPI MULTI-VALUTA
        valuta = request.form.get('valuta', valuta_utente).upper()
        tasso_input = request.form.get('tasso_cambio', '').strip()

        importo_normalizzato = normalizza_importo(request.form['importo'])

        if "INVESTIMENTI" in conto:
            conto = "INVESTIMENTI"
        if "PENSIONE" in conto:
            conto = "PENSIONE"
        if importo_normalizzato is None:
            flash("Importo non valido", "error")
            return redirect(url_for('modifica_transazione_eur', id_transazione=id_transazione))

        # --- GESTIONE SEGNO CORRETTO PER IL DB ---
        # 1. Recuperiamo il valore assoluto inserito dall'utente
        valore_assoluto = abs(float(importo_normalizzato))

        # 2. Assegniamo il segno: Entrate = POSITIVO, Tutte le altre (Spese/Uscite) = NEGATIVO
        if categoria.strip().lower() == 'entrate':
            importo = valore_assoluto
        else:
            importo = -valore_assoluto

        vecchio_importo = t['importo']
        vecchia_data = t['data']

        # --- GESTIONE TASSO DI CAMBIO E CONVERSIONE IN VALUTA BASE UTENTE ---
        if valuta == valuta_utente:
            tasso_cambio = 1.0
            importo_valuta_base = importo
        else:
            if tasso_input:
                try:
                    tasso_cambio = float(tasso_input.replace(',', '.'))
                except ValueError:
                    tasso_cambio = get_exchange_rate(
                        valuta, valuta_utente, date_str=data) or 1.0
            else:
                tasso_cambio = get_exchange_rate(
                    valuta, valuta_utente, date_str=data) or 1.0

            # L'importo in valuta base conserva il segno originale
            importo_valuta_base = importo * tasso_cambio if tasso_cambio else importo

        # --- UNICA CONNESSIONE PER TUTTO ---
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            # 1. Calcolo BTC sul controvalore in valuta base
            valore_btc_eur = ottieni_valore_btc_eur(data)
            controvalore_btc = euro_to_btc(
                importo_valuta_base, valore_btc_eur) if valore_btc_eur else 0.0

            # 2. Aggiornamento della transazione PRINCIPALE
            cursor.execute("""
                UPDATE transazioni
                SET data=?, descrizione=?, categoria=?, sottocategoria=?,
                    importo=?, conto=?, note=?, valore_btc_eur=?, controvalore_btc=?,
                    valuta=?, importo_valuta_base=?, tasso_cambio=?
                WHERE id=? AND user_id=?
            """, (data, descrizione, categoria, sottocategoria,
                  importo, conto, note, valore_btc_eur, controvalore_btc,
                  valuta, importo_valuta_base, tasso_cambio,
                  id_transazione, current_user.id))

            # 3. LOGICA GEMELLA (PARTITA DOPPIA)
            # Cerchiamo la transazione gemella che aveva l'importo OPPOSTO al vecchio importo
            importo_da_cercare = -vecchio_importo
            cursor.execute("""
                SELECT id FROM transazioni
                WHERE user_id=? AND data=? AND abs(importo - ?) < 0.01 AND id != ?
            """, (current_user.id, vecchia_data, importo_da_cercare, id_transazione))

            gemella_row = cursor.fetchone()

            if gemella_row:
                id_gemella = gemella_row[0]
                # La gemella avrà SEMPRE l'importo opposto rispetto alla principale modificata
                importo_gemella = -importo
                importo_valuta_base_gemella = -importo_valuta_base
                controvalore_btc_gemella = -controvalore_btc

                cursor.execute("""
                    UPDATE transazioni
                    SET data=?, descrizione=?, importo=?, note=?,
                        valore_btc_eur=?, controvalore_btc=?,
                        valuta=?, importo_valuta_base=?, tasso_cambio=?
                    WHERE id=? AND user_id=?
                """, (data, descrizione, importo_gemella, note,
                      valore_btc_eur, controvalore_btc_gemella,
                      valuta, importo_valuta_base_gemella, tasso_cambio,
                      id_gemella, current_user.id))
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
        # Mostriamo il valore assoluto nell'input del form per l'utente
        "importo": abs(t["importo"]),
        "conto": t["conto"], "note": t.get("note", ""),
        "valuta": t.get("valuta", valuta_utente),
        "tasso_cambio": t.get("tasso_cambio", 1.0)
    }

    return render_template(
        'modifica_transazione.html',
        transazione=transazione_dict,
        valute=VALUTE_SUPPORTATE,
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
            successo = ripristino_database_completo(current_user.id, data)

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


@app.route('/transazioni_lightning')
@login_required
def transazioni_lightning():
    valuta_utente = getattr(current_user, 'default_currency', 'EUR') or 'EUR'

    # Gestione del simbolo valuta
    info_valuta = VALUTE_SUPPORTATE.get(valuta_utente, '$')
    simbolo_valuta = info_valuta.get('simbolo', '$') if isinstance(
        info_valuta, dict) else info_valuta

    transazioni = leggi_transazioni_da_db_lightning(current_user.id)
    saldo_totale_satoshi = sum(int(t.get('satoshi', 0) or 0)
                               for t in transazioni)

    # 1. Recupera l'ultimo prezzo BTC dal database di Beesy
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT prezzo_eur FROM prezzi_btc ORDER BY data DESC LIMIT 1")
    prezzo_record = cursor.fetchone()
    conn.close()

    prezzo_btc_eur_live = prezzo_record[0] if prezzo_record else 0

    # 2. Converte il prezzo BTC nella valuta dell'utente
    if valuta_utente == 'EUR':
        prezzo_btc_live = prezzo_btc_eur_live
    else:
        tasso_fiat = get_exchange_rate('EUR', valuta_utente) or 1.14
        prezzo_btc_live = prezzo_btc_eur_live * float(tasso_fiat)

    # 3. Calcolo del Controvalore LIVE per tutti i Satoshi
    totale_controvalore = (saldo_totale_satoshi /
                           100_000_000.0) * prezzo_btc_live

    return render_template(
        'transazioni_lightning.html',
        transazioni_lightning=transazioni,
        saldo_totale_satoshi=saldo_totale_satoshi,
        totale_controvalore=totale_controvalore,
        simbolo_valuta=simbolo_valuta,
        valuta_utente=valuta_utente
    )


@app.route('/nuova_transazione_lightning', methods=['GET', 'POST'])
@login_required
def nuova_transazione_lightning():
    valuta_utente = getattr(current_user, 'default_currency', 'EUR') or 'EUR'

    if request.method == 'POST':
        data = request.form['data']
        wallet = request.form['wallet']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        # -------------------------------------------------------------------
        # 🎯 >>> MODIFICA QUI (GESTIONE SEGNO IN BASE ALLA CATEGORIA) <<<
        # -------------------------------------------------------------------
        # 1. Prendiamo il valore assoluto inserito dall'utente (senza segno)
        satoshi_assoluti = abs(int(request.form.get('satoshi', 0)))

        # 2. Assegniamo il segno: Entrate = POSITIVO (+), Tutte le altre = NEGATIVO (-)
        if categoria.strip().lower() == 'entrate':
            sats_finali = satoshi_assoluti
        else:
            sats_finali = -satoshi_assoluti
        # -------------------------------------------------------------------
        try:
            # 1. Recupera il valore BTC in EUR per la data indicata
            valore_btc_eur = ottieni_valore_btc_eur(data)

            # Se per la data di oggi/scelta l'API storica fallisce, usiamo un fallback sul prezzo live
            if not valore_btc_eur or float(valore_btc_eur) == 0:
                # o la tua funzione per il prezzo attuale
                valore_btc_eur = ottieni_valore_btc_eur()

            valore_btc_eur = float(valore_btc_eur or 0)

            # 2. Conversione nella valuta dell'utente (es. USD)
            if valuta_utente == 'EUR':
                valore_btc_utente = valore_btc_eur
            else:
                # Recupera tasso EUR -> USD (o viceversa se la tua funzione richiede valuta_utente -> EUR)
                tasso_fiat = get_exchange_rate('EUR', valuta_utente)
                if not tasso_fiat or tasso_fiat == 1.0:
                    rate_inv = get_exchange_rate(valuta_utente, 'EUR')
                    tasso_fiat = (
                        1 / rate_inv) if (rate_inv and rate_inv > 0) else 1.14

                valore_btc_utente = valore_btc_eur * float(tasso_fiat)

            # 3. Calcolo controvalore in fiat mantenendo il segno dei satoshi finali
            # 🎯 Nota: Usiamo 'sats_finali' al posto del vecchio 'satoshi'
            controvalore_fiat = (
                sats_finali / 100_000_000.0) * valore_btc_utente

            # 4. Salvataggio nel DB
            salva_su_db_lightning(
                user_id=current_user.id,
                data=data,
                wallet=wallet,
                descrizione=descrizione,
                categoria=categoria,
                sottocategoria=sottocategoria,
                satoshi=sats_finali,
                controvalore_eur=controvalore_fiat,
                valore_btc_eur=valore_btc_utente
            )

            flash("Transazione Lightning salvata con successo", "success_lightning")
            return redirect(url_for('transazioni_lightning'))

        except Exception as e:
            flash(f"Errore durante il salvataggio: {e}", "lightning_error")
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
    """
    Gestisce la modifica di una transazione Lightning esistente.

    - GET: Recupera i dati della transazione dal DB e mostra il form precompilato.
    - POST: Riceve i dati aggiornati, ricalcola il prezzo storico/live di BTC 
      e il controvalore nella valuta preferita dell'utente (EUR, USD, ecc.), 
      salva le modifiche sul DB e reindirizza alla lista transazioni.
    """
    transazioni_lightning = leggi_transazioni_da_db_lightning(current_user.id)
    t = next(
        (tr for tr in transazioni_lightning if tr['id'] == id_transazione), None)

    if t is None:
        flash("Transazione non trovata", "error")
        return redirect(url_for('transazioni_lightning'))

    valuta_utente = getattr(current_user, 'default_currency', 'EUR') or 'EUR'

    if request.method == 'POST':
        data = request.form['data']
        wallet = request.form['wallet']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        satoshi_raw = request.form['satoshi']

        # 1. Pulizia e conversione in intero del valore assoluto
        satoshi_puliti = str(satoshi_raw).replace(',', '.').strip()
        satoshi_assoluti = abs(int(float(satoshi_puliti))
                               ) if satoshi_puliti else 0

        # 2. Normalizzazione del SEGNO per il DB (Entrate = +, Spese/Uscite = -)
        if categoria.strip().lower() == 'entrate':
            sats_finali = satoshi_assoluti
        else:
            sats_finali = -satoshi_assoluti

        # 3. Aggiorna i dati base della transazione nel DB
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
            id_transazione, 'satoshi', sats_finali, current_user.id)

        # 4. Recupera il valore storico di BTC in EUR per la data specificata
        valore_btc_eur = ottieni_valore_btc_eur(data)

        # Fallback se l'API storica fallisce o restituisce 0
        if not valore_btc_eur or float(valore_btc_eur) == 0:
            valore_btc_eur = ottieni_valore_btc_eur()

        if valore_btc_eur and float(valore_btc_eur) > 0:
            valore_btc_eur = float(valore_btc_eur)

            # Calcola il prezzo BTC nella valuta dell'utente
            if valuta_utente == 'EUR':
                valore_btc_utente = valore_btc_eur
            else:
                tasso_fiat = get_exchange_rate('EUR', valuta_utente)

                if not tasso_fiat or tasso_fiat == 1.0:
                    rate_inv = get_exchange_rate(
                        valuta_utente, 'EUR', date_str=data)
                    tasso_fiat = (
                        1.0 / rate_inv) if (rate_inv and rate_inv > 0) else 1.14

                valore_btc_utente = valore_btc_eur * float(tasso_fiat)

            # 5. Calcola il controvalore fiat MANTENENDO IL SEGNO
            controvalore_fiat = (
                sats_finali / 100_000_000.0) * valore_btc_utente

            # 6. Salva i calcoli aggiornati nel DB
            modifica_transazione_db_lightning(
                id_transazione, 'valore_btc_eur', valore_btc_utente, current_user.id)
            modifica_transazione_db_lightning(
                id_transazione, 'controvalore_eur', controvalore_fiat, current_user.id)

            flash("✅ Transazione Lightning aggiornata con successo", "success")
        else:
            flash("⚠️ Impossibile ottenere il valore BTC per la data selezionata. I campi calcolati non sono stati modificati.", "warning")

        return redirect(url_for('transazioni_lightning'))

    # --- SE RICHIESTA GET (Mostriamo sempre il valore assoluto nel form per la UX) ---
    t_form = dict(t)
    if 'satoshi' in t_form and t_form['satoshi'] is not None:
        t_form['satoshi'] = abs(t_form['satoshi'])

    return render_template(
        'modifica_transazione_lightning.html',
        transazione_lightning=t_form,
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
    valuta_utente = getattr(current_user, 'default_currency', 'EUR') or 'EUR'

    # Gestione del simbolo valuta
    info_valuta = VALUTE_SUPPORTATE.get(valuta_utente, '$')
    simbolo_valuta = info_valuta.get('simbolo', '$') if isinstance(
        info_valuta, dict) else info_valuta

    dati_onchain, saldo_totale_btc = get_transazioni_con_saldo_onchain(
        current_user.id)

    # 1. Recupera l'ultimo prezzo BTC dal database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT prezzo_eur FROM prezzi_btc ORDER BY data DESC LIMIT 1")
    prezzo_record = cursor.fetchone()
    conn.close()

    prezzo_btc_eur_live = prezzo_record[0] if prezzo_record else 0

    # 2. Converte il prezzo BTC nella valuta dell'utente
    if valuta_utente == 'EUR':
        prezzo_btc_live = prezzo_btc_eur_live
    else:
        tasso_fiat = get_exchange_rate('EUR', valuta_utente) or 1.14
        prezzo_btc_live = prezzo_btc_eur_live * float(tasso_fiat)

    # 3. Controvalore totale On-chain
    totale_controvalore = saldo_totale_btc * prezzo_btc_live

    return render_template(
        "transazioni_onchain.html",
        transazioni_onchain=dati_onchain,
        saldo_totale_btc=saldo_totale_btc,
        totale_controvalore=totale_controvalore,
        simbolo_valuta=simbolo_valuta,
        valuta_utente=valuta_utente
    )


@app.route('/nuova_transazione_onchain', methods=['GET', 'POST'])
@login_required
def nuova_transazione_onchain():
    valuta_utente = getattr(current_user, 'default_currency', 'EUR') or 'EUR'

    if request.method == 'POST':
        data = request.form['data']
        wallet = request.form['wallet']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        transactionID = request.form['transactionID']

        # 1. Normalizzazione e pulizia dell'input (conversione virgola in punto)
        importo_raw = str(request.form.get('importo_btc', '0')
                          ).replace(',', '.').strip()
        importo_assoluto = abs(float(importo_raw)) if importo_raw else 0.0

        fee_raw = str(request.form.get('fee', '0')).replace(',', '.').strip()
        fee = abs(float(fee_raw)) if fee_raw else 0.0

        # 2. Assegnazione del segno in base alla Categoria
        if categoria.strip().lower() == 'entrate':
            importo_btc_final = importo_assoluto
        else:
            importo_btc_final = -importo_assoluto

        try:
            valore_btc_eur = ottieni_valore_btc_eur(data)

            if valore_btc_eur:
                if valuta_utente == 'EUR':
                    valore_btc_utente = valore_btc_eur
                else:
                    tasso_fiat = get_exchange_rate(
                        valuta_utente, 'EUR', date_str=data) or 1.0
                    valore_btc_utente = valore_btc_eur * tasso_fiat

                # Calcolo del controvalore mantenendo il segno dell'importo
                controvalore_fiat = importo_btc_final * valore_btc_utente
            else:
                valore_btc_utente = None
                controvalore_fiat = None

            salva_su_db_onchain(
                user_id=current_user.id,
                data=data,
                wallet=wallet,
                descrizione=descrizione,
                categoria=categoria,
                sottocategoria=sottocategoria,
                transactionID=transactionID,
                importo_btc=importo_btc_final,
                fee=fee,
                controvalore_eur=controvalore_fiat,
                valore_btc_eur=valore_btc_utente
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
        transazione_onchain=placeholder_transazione,
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
    transazioni_onchain = leggi_transazioni_da_db_onchain(current_user.id)
    t = next(
        (tr for tr in transazioni_onchain if tr['id'] == id_transazione), None)

    if t is None:
        flash("Transazione non trovata", "error")
        return redirect(url_for('transazioni_onchain'))

    valuta_utente = getattr(current_user, 'default_currency', 'EUR') or 'EUR'

    if request.method == 'POST':
        data = request.form['data']
        wallet = request.form['wallet']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        transactionID = request.form['transactionID']

        # 1. Normalizzazione importi (gestione virgola + abs)
        importo_raw = str(request.form.get('importo_btc', '0')
                          ).replace(',', '.').strip()
        importo_assoluto = abs(float(importo_raw)) if importo_raw else 0.0

        fee_raw = str(request.form.get('fee', '0')).replace(',', '.').strip()
        fee = abs(float(fee_raw)) if fee_raw else 0.0

        # 2. Normalizzazione del SEGNO per il DB
        if categoria.strip().lower() == 'entrate':
            importo_btc_final = importo_assoluto
        else:
            importo_btc_final = -importo_assoluto

        # 3. Aggiornamento dati base nel DB
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
            id_transazione, 'importo_btc', importo_btc_final, current_user.id)
        modifica_transazione_db_onchain(
            id_transazione, 'fee', fee, current_user.id)

        # 4. Ricalcola e aggiorna BTC rispetto alla valuta utente
        valore_btc_eur = ottieni_valore_btc_eur(data)

        if valore_btc_eur and float(valore_btc_eur) > 0:
            valore_btc_eur = float(valore_btc_eur)

            if valuta_utente == 'EUR':
                valore_btc_utente = valore_btc_eur
            else:
                tasso_fiat = get_exchange_rate('EUR', valuta_utente)
                if not tasso_fiat or tasso_fiat == 1.0:
                    rate_inv = get_exchange_rate(
                        valuta_utente, 'EUR', date_str=data)
                    tasso_fiat = (
                        1.0 / rate_inv) if (rate_inv and rate_inv > 0) else 1.14

                valore_btc_utente = valore_btc_eur * float(tasso_fiat)

            # Controvalore FIAT con il segno corretto
            controvalore_fiat = importo_btc_final * valore_btc_utente

            modifica_transazione_db_onchain(
                id_transazione, 'valore_btc_eur', valore_btc_utente, current_user.id)
            modifica_transazione_db_onchain(
                id_transazione, 'controvalore_eur', controvalore_fiat, current_user.id)

            flash("✅ Transazione On-Chain aggiornata con successo", "success")
        else:
            flash("⚠️ Impossibile ottenere il valore BTC per la data selezionata. I campi calcolati non sono stati modificati.", "warning")

        return redirect(url_for('transazioni_onchain'))

    # --- SE RICHIESTA GET (Mostriamo l'importo positivo nel form per la UX) ---
    t_form = dict(t)
    if 'importo_btc' in t_form and t_form['importo_btc'] is not None:
        t_form['importo_btc'] = abs(t_form['importo_btc'])

    return render_template(
        'modifica_transazione_onchain.html',
        transazione_onchain=t_form,
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
    from flask_babel import gettext as _
    from db.db_utils import get_db_connection

    # 1. Normalizziamo SUBITO 'tipo' in MAIUSCOLO per evitare mismatch nelle query
    tipo = tipo.upper().strip()

    # Se l'utente ha una valuta impostata usiamo quella, altrimenti EUR di default
    user_currency = getattr(current_user, 'default_currency', 'EUR')

    info_valuta = VALUTE_SUPPORTATE.get(user_currency, '$')
    simbolo_valuta = info_valuta.get('simbolo', '$') if isinstance(
        info_valuta, dict) else info_valuta

    # Tasso di cambio FIAT (1.0 se EUR)
    tasso_fiat = 1.0
    if user_currency != 'EUR':
        tasso_fiat = float(get_exchange_rate('EUR', user_currency) or 1.14)

    # 1. Recuperiamo i dati corretti inviati dal metodo GET dell'HTML
    mese_selezionato = request.args.get('mese')
    anno_selezionato = request.args.get('anno')

    # 2. Logica di esclusione reciproca
    if mese_selezionato:
        mese_selezionato = mese_selezionato.strip()
        if not mese_selezionato:
            mese_selezionato = None
        else:
            anno_selezionato = None

    if anno_selezionato:
        anno_selezionato = anno_selezionato.strip()
        if not anno_selezionato:
            anno_selezionato = None
        else:
            mese_selezionato = None

    # Recupero dati grafici spese/entrate
    labels_spese, valori_spese = get_spese_per_categoria_filtrate(
        current_user.id, tipo, mese=mese_selezionato, anno=anno_selezionato)

    labels_entrate, valori_entrate = get_entrate_per_sottocategoria(
        current_user.id, tipo, mese=mese_selezionato, anno=anno_selezionato)

    tot_entrate, tot_spese = get_bilancio_periodo(
        current_user.id, tipo, mese=mese_selezionato, anno=anno_selezionato)

    # Conversione spese ed entrate nella valuta utente
    tot_entrate *= tasso_fiat
    tot_spese *= tasso_fiat
    valori_spese = [v * tasso_fiat for v in valori_spese]
    valori_entrate = [v * tasso_fiat for v in valori_entrate]

    delta = tot_entrate - tot_spese
    saving_rate = (delta / tot_entrate * 100) if tot_entrate > 0 else 0

    date_btc = []
    saldi_btc = []
    saldi_eur_btc = []
    tx_storiche = []

    rendimento = 0
    percentuale = 0
    valore_attuale_eur = 0
    saldo_asset = 0
    costo_storico_eur = 0

    if tipo in ['ONCHAIN', 'LIGHTNING']:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Prezzo BTC attuale in EUR
        cursor.execute(
            "SELECT prezzo_eur FROM prezzi_btc ORDER BY data DESC LIMIT 1")
        prezzo_record = cursor.fetchone()
        prezzo_attuale_btc_eur = prezzo_record[0] if prezzo_record else 0

        # Prezzo BTC convertito nella valuta utente
        prezzo_attuale_btc = prezzo_attuale_btc_eur * tasso_fiat

        # 2. Prezzi storici convertiti
        cursor.execute(
            "SELECT data, prezzo_eur FROM prezzi_btc ORDER BY data ASC")
        prezzi_rows = cursor.fetchall()
        prezzi_storici = {row['data']: (
            row['prezzo_eur'] * tasso_fiat) for row in prezzi_rows}

        filtro_btc = ""
        params_btc = [current_user.id]
        if mese_selezionato:
            filtro_btc = "AND SUBSTR(data, 1, 7) = ?"
            params_btc.append(mese_selezionato)
        elif anno_selezionato:
            filtro_btc = "AND SUBSTR(data, 1, 4) = ?"
            params_btc.append(anno_selezionato)

        if tipo == 'ONCHAIN':
            from db.db_utils import get_transazioni_con_saldo_onchain
            dummy_tx, saldo_asset = get_transazioni_con_saldo_onchain(
                current_user.id)

            cursor.execute(
                "SELECT SUM(controvalore_eur) FROM transazioni_onchain WHERE user_id = ?", (current_user.id,))
            res = cursor.fetchone()
            costo_storico_eur = (res[0] if res[0] else 0) * tasso_fiat
            valore_attuale_eur = saldo_asset * prezzo_attuale_btc

            # Query storiche ONCHAIN (convertendo sats/btc e considerando le fee)
            cursor.execute(f'''
                SELECT SUBSTR(data, 1, 10) as giorno,
                       SUM(
                           CASE 
                               WHEN LOWER(TRIM(categoria)) = 'entrate' THEN ABS(importo_btc) - ABS(COALESCE(fee, 0))
                               ELSE -ABS(importo_btc) - ABS(COALESCE(fee, 0))
                           END
                       ) as flusso
                FROM transazioni_onchain
                WHERE user_id = ? {filtro_btc}
                GROUP BY giorno ORDER BY giorno ASC
            ''', tuple(params_btc))
            tx_storiche = cursor.fetchall()

        elif tipo == 'LIGHTNING':
            from db.db_utils import get_transazioni_con_saldo_lightning
            dummy1, saldo_asset, dummy2 = get_transazioni_con_saldo_lightning(
                current_user.id)

            cursor.execute(
                "SELECT SUM(controvalore_eur) FROM transazioni_lightning WHERE user_id = ?", (current_user.id,))
            res = cursor.fetchone()
            costo_storico_eur = (res[0] if res[0] else 0) * tasso_fiat
            valore_attuale_eur = (
                saldo_asset / 100000000.0) * prezzo_attuale_btc

            cursor.execute(f'''
                SELECT SUBSTR(data, 1, 10) as giorno,
                       SUM(
                           CASE 
                               WHEN LOWER(TRIM(categoria)) = 'entrate' THEN ABS(satoshi) * 0.00000001
                               ELSE -ABS(satoshi) * 0.00000001
                           END
                       ) as flusso
                FROM transazioni_lightning
                WHERE user_id = ? {filtro_btc}
                GROUP BY giorno ORDER BY giorno ASC
            ''', tuple(params_btc))
            tx_storiche = cursor.fetchall()

        saldo_temporale_btc = 0.0
        for tx in tx_storiche:
            giorno = tx['giorno']
            flusso = tx['flusso']
            saldo_temporale_btc += flusso

            prezzo_quel_giorno = prezzi_storici.get(giorno, prezzo_attuale_btc)
            controvalore_fiat_storico = saldo_temporale_btc * prezzo_quel_giorno

            date_btc.append(str(giorno))
            saldi_btc.append(round(saldo_temporale_btc, 8))
            saldi_eur_btc.append(round(controvalore_fiat_storico, 2))

        rendimento = valore_attuale_eur - costo_storico_eur
        if costo_storico_eur > 0:
            percentuale = (rendimento / costo_storico_eur) * 100

        conn.close()

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

        costo_storico_eur = sum(
            float(asset['capitale_investito']) for asset in investimenti_fiat) * tasso_fiat
        valore_attuale_eur = sum(
            float(asset['valore_attuale']) for asset in investimenti_fiat) * tasso_fiat

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

        filtro_tempo_grafico = ""
        parametri_grafico = [current_user.id]

        if mese_selezionato:
            filtro_tempo_grafico = "AND SUBSTR(h.data_rilevazione, 1, 7) <= ?"
            parametri_grafico.append(mese_selezionato)
        elif anno_selezionato:
            filtro_tempo_grafico = "AND SUBSTR(h.data_rilevazione, 1, 4) <= ?"
            parametri_grafico.append(anno_selezionato)

        tutti_i_parametri = [current_user.id] + \
            [p for p in parametri_grafico[1:]] + parametri_grafico

        cursor.execute(f'''
            SELECT SUBSTR(h.data_rilevazione, 1, 10) as giorno, SUM(h.valore_rilevato) as totale
            FROM assets_history h
            JOIN assets_watch w ON h.asset_id = w.id
            WHERE w.user_id = ? {filtro_tempo_grafico} AND h.id IN (
                SELECT MAX(inner_h.id)
                FROM assets_history inner_h
                JOIN assets_watch inner_w ON inner_h.asset_id = inner_w.id
                WHERE inner_w.user_id = ? {filtro_tempo_grafico}
                AND SUBSTR(inner_h.data_rilevazione, 1, 10) = SUBSTR(h.data_rilevazione, 1, 10)
                GROUP BY inner_h.asset_id
            )
            GROUP BY giorno ORDER BY giorno ASC
        ''', tuple(tutti_i_parametri))

        dati_grafico_fiat = cursor.fetchall()

        date_fiat = [str(r['giorno']) for r in dati_grafico_fiat]
        valori_fiat = [float(r['totale']) *
                       tasso_fiat for r in dati_grafico_fiat]

        rendimento = valore_attuale_eur - costo_storico_eur
        if costo_storico_eur > 0:
            percentuale = (rendimento / costo_storico_eur) * 100

        conn.close()

    # Ora _() è rimasta una funzione valida per tutte le chiavi!
    titoli = {
        'EURO': _('Statistiche %(simbolo)s', simbolo=simbolo_valuta),
        'LIGHTNING': _('Statistiche Lightning (⚡)'),
        'ONCHAIN': _('Statistiche On-chain (₿)')
    }
    # === FORZATURA E VERIFICA PER ONCHAIN (CON FILTRI TEMPO) ===
    if tipo == 'ONCHAIN':
        conn = get_db_connection()
        cursor = conn.cursor()

        filtro_tempo = ""
        parametri = [current_user.id]

        if mese_selezionato:
            filtro_tempo = "AND SUBSTR(data, 1, 7) = ?"
            parametri.append(mese_selezionato)
        elif anno_selezionato:
            filtro_tempo = "AND SUBSTR(data, 1, 4) = ?"
            parametri.append(anno_selezionato)

        # Somma ENTRATE On-chain dal DB
        cursor.execute(f"""
            SELECT COALESCE(SUM(ABS(importo_btc)), 0.0) 
            FROM transazioni_onchain 
            WHERE user_id = ? AND LOWER(TRIM(categoria)) = 'entrate' {filtro_tempo}
        """, tuple(parametri))
        tot_entrate = float(cursor.fetchone()[0])

        # Somma USCITE On-chain
        cursor.execute(f"""
            SELECT COALESCE(SUM(ABS(importo_btc)), 0.0) 
            FROM transazioni_onchain 
            WHERE user_id = ? AND LOWER(TRIM(categoria)) != 'entrate' {filtro_tempo}
        """, tuple(parametri))
        tot_spese = float(cursor.fetchone()[0])

        # Somma FEE di rete
        cursor.execute(f"""
            SELECT COALESCE(SUM(ABS(fee)), 0.0) 
            FROM transazioni_onchain 
            WHERE user_id = ? {filtro_tempo}
        """, tuple(parametri))
        tot_fee = float(cursor.fetchone()[0])

        # Le uscite totali sono uscite + fee
        tot_spese += tot_fee
        conn.close()

    delta = tot_entrate - tot_spese
    savings_rate = (delta / tot_entrate * 100) if tot_entrate > 0 else 0

    return render_template('analytics.html',
                           labels_spese=labels_spese,
                           valori_spese=valori_spese,
                           labels_entrate=labels_entrate,
                           valori_entrate=valori_entrate,
                           tipo=tipo,
                           titolo_pagina=titoli.get(tipo, _("Statistiche")),
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
                           date_btc=date_btc,
                           saldi_btc=saldi_btc,
                           saldi_eur_btc=saldi_eur_btc,
                           simbolo_valuta=simbolo_valuta
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

        # 1. Aggiorniamo il valore attuale nella tabella principale per l'asset specifico
        cursor.execute('''
            UPDATE assets_watch
            SET valore_attuale = ?, data_aggiornamento = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        ''', (float(nuovo_valore), int(asset_id), current_user.id))

        # 2. Inseriamo UN SOLO record nello storico per QUESTO specifico asset
        # Usiamo CURRENT_TIMESTAMP di SQLite così la data della riga sarà il momento esatto del click
        cursor.execute('''
            INSERT INTO assets_history (asset_id, valore_rilevato, data_rilevazione)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (int(asset_id), float(nuovo_valore)))

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

    return render_template('importa_csv.html', tipo_import="BANCA")


@app.route('/importa_blink', methods=['GET', 'POST'])
@login_required
def importa_blink():
    if request.method == 'POST':
        if 'file_csv' not in request.files:
            flash("Nessun file selezionato", "danger")
            return redirect(request.url)

        file = request.files['file_csv']
        if file.filename == '' or not file.filename.endswith('.csv'):
            flash("Formato file non valido. Seleziona un file CSV.", "warning")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        try:
            # Data di partenza per ignorare lo storico vecchio
            DATA_START = "2026-08-01"

            dati_anteprima = anteprima_importazione_blink_csv(
                filepath, current_user.id, data_inizio_filtro=DATA_START)

            # Cancelliamo il file temporaneo
            if os.path.exists(filepath):
                os.remove(filepath)

            # Inviamo i dati all'anteprima passando conto_origine="BLINK"
            return render_template('importa_anteprima.html',
                                   transazioni=dati_anteprima,
                                   tutte_categorie=CATEGORIE,
                                   conto_origine="BLINK")

        except Exception as e:
            flash(f"Errore durante l'analisi del file Blink: {e}", "danger")
            return redirect(request.url)

    # Pagina iniziale con il form di upload
    return render_template('importa_csv.html', tipo_import='BLINK')


@app.route('/conferma_importazione', methods=['POST'])
@login_required
def conferma_importazione():
    # Definiamo conn all'inizio così che sia accessibile anche nel blocco 'finally'
    conn = None
    try:
        from db.db_utils import get_db_connection
        form_data = request.form
        indici = [k.split('_')[1]
                  for k in form_data.keys() if k.startswith('data_')]

        count = 0
        skip_count = 0

        # Apriamo la connessione principale
        conn = get_db_connection()
        cursor = conn.cursor()

        for i in indici:
            data = form_data.get(f'data_{i}')
            desc = form_data.get(f'desc_{i}')
            importo = float(form_data.get(f'importo_{i}'))
            categoria = form_data.get(f'cat_{i}')
            sottocategoria = form_data.get(f'sub_{i}')
            controvalore_btc = float(form_data.get(f'btc_{i}'))

            # --- SCUDO ANTI-DUPLICATO CORAZZATO ---
            # Sostituisce il vecchio blocco per intercettare i giroconti automatici
            if sottocategoria == "Prelievo Contante" or sottocategoria == "Trasferimento":
                cursor.execute('''
                    SELECT id FROM transazioni
                    WHERE user_id = ? AND data = ? AND abs(importo) = abs(?) 
                    AND (descrizione = ? OR descrizione LIKE '%Giroconto%' OR descrizione LIKE '%Prelievo%')
                ''', (current_user.id, data, importo, desc))
            else:
                # Per tutte le altre categorie (inclusi Interessi e Rimborsi) usiamo il controllo standard
                cursor.execute('''
                    SELECT id FROM transazioni
                    WHERE user_id = ? AND data = ? AND descrizione = ? AND importo = ?
                ''', (current_user.id, data, desc, importo))

            esiste_gia = cursor.fetchone()

            if esiste_gia:
                skip_count += 1
                print(
                    f"⚠️ Doppione rilevato e saltato: [{data}] {desc[:30]}... ({importo}€)")
                continue

            valore_spot = abs(
                importo / controvalore_btc) if controvalore_btc != 0 else 0

            # Per evitare conflitti di lock, committiamo e chiudiamo momentaneamente la connessione di controllo
            # prima di cedere il controllo alla funzione interna di registrazione
            cursor.close()
            conn.commit()
            conn.close()

            # 1. Recuperiamo il conto (BLINK o BANCA) inviato dalla form
            conto_selezionato = request.form.get('conto_origine', 'BANCA')
            registra_transazione_conto(
                user_id=current_user.id,
                data=data,
                descrizione=desc,
                categoria=categoria,
                sottocategoria=sottocategoria,
                importo=importo,
                conto=conto_selezionato,  # <-- QUI! Dinamico (BANCA o BLINK)
                controvalore_btc=controvalore_btc,
                valore_btc_eur=valore_spot
            )

            # Riapriamo subito la connessione per la prossima riga del ciclo o per i mapping
            conn = get_db_connection()
            cursor = conn.cursor()

            # 3. APPRENDIMENTO (Mapping categorie)
            if 'ricorda_mapping' in form_data:
                parola_chiave = desc.split()[0].upper()
                if len(parola_chiave) > 3:
                    conn.execute('''
                        INSERT OR REPLACE INTO mapping_categorie (parola_chiave, categoria, sottocategoria)
                        VALUES (?, ?, ?)
                    ''', (parola_chiave, categoria, sottocategoria))

            count += 1

        # Commit finale se tutto il ciclo si è concluso felicemente
        conn.commit()

        if skip_count > 0:
            flash(
                f"✅ Ottimo Den! Abbiamo importato {count} nuovi movimenti. Rilevati e bloccati {skip_count} duplicati.", "success")
        else:
            flash(
                f"✅ Ottimo Den! Abbiamo importato {count} movimenti con successo.", "success")

        return redirect(url_for('home'))

    except Exception as e:
        flash(f"❌ Errore durante il salvataggio: {e}", "danger")
        return redirect(url_for('importa_csv'))

    finally:
        # Il blocco finally si esegue SEMPRE, garantendo che Beesy non lasci mai file aperti nel limbo
        if conn:
            try:
                conn.close()
            except Exception:
                pass


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
            if ripristino_database_completo(current_user.id, data):
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


@app.route('/api/analytics/drill-down')
@login_required
def api_drill_down():
    categoria = request.args.get('categoria')
    anno = request.args.get('anno')
    mese = request.args.get('mese')
    tipo_movimento = request.args.get('tipo_movimento')

    valuta_pref = getattr(current_user, 'default_currency', 'EUR') or 'EUR'
    simbolo_pref = currency_symbol(valuta_pref)

    if not categoria:
        return jsonify({
            'euro': [],
            'lightning': [],
            'onchain': [],
            'valuta_utente': valuta_pref,
            'simbolo_valuta': simbolo_pref
        })

    categoria = categoria.strip()

    # Calcoliamo il tasso di cambio se la valuta è diversa da EUR
    tasso_cambio = 1.0
    if valuta_pref != 'EUR':
        tasso_cambio = get_exchange_rate('EUR', valuta_pref) or 1.0

    conn = get_db_connection()
    cursor = conn.cursor()

    # Condizione SQL per la categoria/sottocategoria
    if categoria.lower() == 'altro':
        condizione_cat = "(categoria = 'Altro' OR (sottocategoria = 'Altro' AND sottocategoria IS NOT NULL AND sottocategoria != ''))"
        params_base = [current_user.id]
    else:
        condizione_cat = "(categoria = ? OR (sottocategoria = ? AND sottocategoria IS NOT NULL AND sottocategoria != ''))"
        params_base = [current_user.id, categoria, categoria]

    # --- FILTRO SEGNO (Entrate > 0 / Spese < 0) ---
    if tipo_movimento == 'entrate':
        filtro_segno_fiat = "AND importo > 0"
        filtro_segno_ln = "AND satoshi > 0"
        filtro_segno_btc = "AND importo_btc > 0"
    elif tipo_movimento == 'spese':
        filtro_segno_fiat = "AND importo < 0"
        filtro_segno_ln = "AND satoshi < 0"
        filtro_segno_btc = "AND importo_btc < 0"
    else:
        filtro_segno_fiat = ""
        filtro_segno_ln = ""
        filtro_segno_btc = ""

    # --- 1. TRANSAZIONI FIAT (MULTIVALUTA CON CONVERSIONE) ---
    where_fiat = ["user_id = ?", condizione_cat]
    params_fiat = list(params_base)

    if mese:
        where_fiat.append("SUBSTR(data, 1, 7) = ?")
        params_fiat.append(mese)
    elif anno:
        where_fiat.append("SUBSTR(data, 1, 4) = ?")
        params_fiat.append(anno)

    query_fiat = f"""
        SELECT data, descrizione, importo, valuta
        FROM transazioni 
        WHERE {" AND ".join(where_fiat)} {filtro_segno_fiat}
        ORDER BY data DESC
    """
    cursor.execute(query_fiat, tuple(params_fiat))
    euro_rows = cursor.fetchall()

    # Convertiamo gli importi al volo in base alla valuta scelta dall'utente
    lista_euro_convertite = []
    for r in euro_rows:
        importo_originale = float(r['importo'])
        valuta_origine = r['valuta'] if 'valuta' in r.keys(
        ) and r['valuta'] else 'EUR'

        # Se la transazione è in EUR e l'utente vuole un'altra valuta (es. USD)
        if valuta_origine == 'EUR' and valuta_pref != 'EUR':
            importo_convertito = importo_originale * tasso_cambio
        elif valuta_origine != 'EUR' and valuta_pref == 'EUR':
            # Se la transazione è in altra valuta e l'utente vuole EUR, applichiamo il tasso inverso
            tasso_inv = get_exchange_rate(valuta_origine, 'EUR') or 1.0
            importo_convertito = importo_originale * tasso_inv
        else:
            importo_convertito = importo_originale

        lista_euro_convertite.append({
            'data': str(r['data']),
            'descrizione': r['descrizione'],
            'importo': round(importo_convertito, 2)
        })

    # --- 2. TRANSAZIONI LIGHTNING ---
    where_ln = ["user_id = ?", condizione_cat]
    params_ln = list(params_base)
    if mese:
        where_ln.append("SUBSTR(data, 1, 7) = ?")
        params_ln.append(mese)
    elif anno:
        where_ln.append("SUBSTR(data, 1, 4) = ?")
        params_ln.append(anno)

    query_ln = f"""
        SELECT data, descrizione, satoshi
        FROM transazioni_lightning 
        WHERE {" AND ".join(where_ln)} {filtro_segno_ln}
        ORDER BY data DESC
    """
    cursor.execute(query_ln, tuple(params_ln))
    ln_rows = cursor.fetchall()

    # --- 3. TRANSAZIONI BITCOIN ON-CHAIN ---
    where_btc = ["user_id = ?", condizione_cat]
    params_btc = list(params_base)
    if mese:
        where_btc.append("SUBSTR(data, 1, 7) = ?")
        params_btc.append(mese)
    elif anno:
        where_btc.append("SUBSTR(data, 1, 4) = ?")
        params_btc.append(anno)

    query_btc = f"""
        SELECT data, descrizione, importo_btc 
        FROM transazioni_onchain 
        WHERE {" AND ".join(where_btc)} {filtro_segno_btc}
        ORDER BY data DESC
    """
    cursor.execute(query_btc, tuple(params_btc))
    btc_rows = cursor.fetchall()

    conn.close()

    return jsonify({
        'euro': lista_euro_convertite,
        'lightning': [{'data': str(r['data']), 'descrizione': r['descrizione'], 'satoshi': r['satoshi']} for r in ln_rows],
        'onchain': [{'data': str(r['data']), 'descrizione': r['descrizione'], 'importo_btc': r['importo_btc']} for r in btc_rows],
        'valuta_utente': valuta_pref,
        'simbolo_valuta': simbolo_pref
    })


@app.route('/impostazioni', methods=['GET', 'POST'])
@login_required
def impostazioni():
    if request.method == 'POST':
        nuova_valuta = request.form.get('valuta')

        if nuova_valuta in VALUTE_SUPPORTATE:
            # 1. Salva la modifica su SQLite persistentemente
            aggiorna_valuta_utente_db(current_user.id, nuova_valuta)

            # 2. Aggiorna l'oggetto in sessione per la risposta immediata
            current_user.default_currency = nuova_valuta

            flash(_("Valuta predefinita aggiornata con successo!"), "success")
            return redirect(url_for('impostazioni'))

    return render_template('impostazioni.html', valute=VALUTE_SUPPORTATE)


@app.template_filter('currency_symbol')
def currency_symbol(code):
    info = VALUTE_SUPPORTATE.get(code)
    return info['simbolo'] if info else code


@app.template_filter('format_currency')
def format_currency_filter(importo, valuta=None):
    if valuta is None:
        valuta = getattr(current_user, 'default_currency', 'EUR')
    return formatta_importo(importo, valuta)


if __name__ == '__main__':
    # Registrazione blueprint auth
    try:
        from auth import auth_bp
        app.register_blueprint(auth_bp)
    except Exception as e:
        print(f"⚠️ Nota registrazione Auth: {e}")

    # Avvio del server Flask
    print("🚀 Avvio di Beesy in corso...")
    app.run(host='0.0.0.0', port=5000, debug=True)
