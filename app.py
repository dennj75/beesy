from db.db_utils import DB_PATH
from utils.crypto import _carica_storico_btc_eur
from db.db_utils import get_user_by_id
from flask_login import LoginManager, login_required, UserMixin
from flask import Flask, render_template, request, redirect, url_for, flash
from db.db_utils import get_transazioni_con_saldo_lightning, leggi_transazioni_da_db, salva_su_db, elimina_transazione_da_db, modifica_transazione_db, inizializza_db, salva_su_db_lightning, leggi_transazioni_da_db_lightning, modifica_transazione_db_lightning, elimina_transazione_da_db_lightning, leggi_transazioni_da_db_onchain, salva_su_db_onchain, leggi_transazioni_filtrate_onchain, elimina_transazione_da_db_onchain, modifica_transazione_db_onchain
from flask import send_file
from utils.export import esporta_csv, esporta_csv_per_mese, esporta_csv_lightning, esporta_csv_per_mese_lightning, esporta_csv_onchain, esporta_csv_per_mese_onchain
from utils.crypto import ottieni_valore_btc_eur, euro_to_btc
from utils.helpers import normalizza_importo
import json
import sqlite3
from flask_login import LoginManager, login_remembered, current_user
import os
import binascii
import hashlib
from flask import Flask, session, jsonify, request
from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
from bech32 import bech32_decode, convertbits
from btclib.ecc import ssa
from hashlib import sha256
import time
from datetime import datetime, date
from coincurve import PublicKey
from coincurve._libsecp256k1 import lib, ffi

inizializza_db()  # <<--- aggiungi questa riga
CATEGORIE = {
    'Entrate': ['Stipendio', 'Rimborso', 'Regalo', 'Donazioni', 'claim giochi online', 'Altro'],
    'Abitazione': ['Affitto/Mutuo', 'Bollette: Luce', 'Bollette: acqua', 'Bollette: Gas', 'Bollette: Rifiuti', 'Manutenzione', 'Spese condominiali', 'Assicurazione casa'],
    'Alimentari': ['Supermercato', 'Ristorante - Bar', 'Spesa online', 'Altro'],
    'Trasporti': ['Carburante', 'Mezzi pubblici', 'Manutenzione auto / moto', 'Assicurazione auto', 'Taxi / Uber', 'Noleggi', 'Parcheggi / pedaggi', 'Altro'],
    'Spese Personali': ['Abbigliamento / Scarpe', 'Igiene personale', 'Parrucchiere / estetista', 'Abbonamenti personali (Netflix, Spotify, ecc)', 'Libri / Riviste'],
    'Tempo Libero & Intrattenimento': ['Cinema / Teatro / Eventi', 'Sport / Palestra', 'Viaggi / Vacanze', 'Hobby / Collezioni', 'Giochi / App a pagamento'],
    'Finanze & Banche': ['Commissioni bancarie', 'Interessi passivi', 'Prelievi / Depositi', 'Investimenti', 'Criptovalute', 'Giroconti'],
    'Lavoro & Studio': ['Spese di ufficio / coworking', 'Formazione / Corsi', 'Libri / Materiali didattici', 'Trasporti lavoro / studio', 'Pasti lavoro'],
    'Famiglia & Bambini': ['Spese scolastiche', 'Abbigliamento bambino', 'Salute bambino', 'Giocattoli', 'Baby sitter / Asilo', 'Altro'],
    'Salute': ['Farmacia', 'Visita medica', 'Altro']
}


def get_transazioni_con_saldo_lightning(user_id):
    transazioni_lightning = leggi_transazioni_da_db_lightning(user_id)

    saldo_satoshi = sum(
        float(t['satoshi']) for t in transazioni_lightning
        if t['satoshi'] not in (None, "", "None")
    )

    saldo_eur_lightning = sum(
        float(t['controvalore_eur']) for t in transazioni_lightning
        if t['controvalore_eur'] not in (None, "", "None")
    )

    return transazioni_lightning, saldo_satoshi, saldo_eur_lightning


def get_transazioni_con_saldo(user_id):
    transazioni = leggi_transazioni_da_db(user_id)
    saldo_totale = sum(float(t["importo"])
                       for t in transazioni if t["importo"] is not None)
    saldo_banca = sum(t['importo']
                      for t in transazioni if t['conto'].lower() == 'banca')
    saldo_contanti = sum(t['importo']
                         for t in transazioni if t['conto'].lower() == 'contanti')
    return transazioni, saldo_totale, saldo_banca, saldo_contanti


def get_transazioni_con_saldo_onchain(user_id):
    transazioni = leggi_transazioni_da_db_onchain(user_id)
    saldo_totale_btc = sum(float(t['importo_btc'])
                           for t in transazioni if t['importo_btc'] is not None)
    return transazioni, saldo_totale_btc


def get_transazioni_con_saldo_satoshi_onchain(user_id):
    transazioni_onchain = leggi_transazioni_da_db_onchain(user_id)
    saldo_totale_btc = sum(float(t['importo_btc'])
                           for t in transazioni_onchain if t['importo_btc'] is not None)
    return transazioni_onchain, saldo_totale_btc


app = Flask(__name__)
# Chiave necessaria per i flash e da cambiare in produzione
app.secret_key = 'supersecretkey'


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


@app.post("/api/verify")
def verify_signature():
    body = request.json
    event = body["event"]
    npub_hex = body["npub"]

    print("=" * 60)
    print("INIZIO VERIFICA NOSTR")
    print("=" * 60)
    print(f"Evento ricevuto:\n{json.dumps(event, indent=2)}")

    # Verifica presenza challenge
    challenge = session.get("challenge")
    timestamp_challenge = session.get("challenge_timestamp")

    if not challenge:
        print("❌ ERRORE: Nessuna challenge in sessione")
        return {"ok": False, "error": "no challenge"}, 400

    # Verifica content == challenge
    if event["content"] != challenge:
        print(f"❌ ERRORE: Content mismatch")
        return {"ok": False, "error": "content mismatch"}, 400

    # Verifica timestamp (180 secondi di tolleranza)
    if abs(event["created_at"] - timestamp_challenge) > 180:
        print(f"❌ ERRORE: Timestamp fuori range")
        return {"ok": False, "error": "timestamp mismatch"}, 400

    # Verifica pubkey
    if event["pubkey"] != npub_hex:
        print(f"❌ ERRORE: Pubkey mismatch")
        return {"ok": False, "error": "pubkey mismatch"}, 400

    try:
        # ========================================
        # CALCOLO ID EVENTO SECONDO NIP-01
        # ========================================

        serialized_array = [
            0,
            event["pubkey"],
            event["created_at"],
            event["kind"],
            event["tags"],
            event["content"]
        ]

        serialized_str = json.dumps(
            serialized_array,
            separators=(',', ':'),
            ensure_ascii=False
        )

        print(f"\n📝 Stringa serializzata:")
        print(f"   {serialized_str[:150]}...")

        # Calcola SHA256
        event_id_bytes = sha256(serialized_str.encode('utf-8')).digest()
        calculated_id = event_id_bytes.hex()

        print(f"\n🔐 Verifica ID:")
        print(f"   Calcolato: {calculated_id}")
        print(f"   Ricevuto : {event['id']}")
        print(f"   Match: {'✅' if calculated_id == event['id'] else '❌'}")

        # ========================================
        # VERIFICA FIRMA SCHNORR (BIP340)
        # ========================================

        pubkey_xonly = bytes.fromhex(event["pubkey"])  # 32 bytes x-only
        sig_bytes = bytes.fromhex(event["sig"])        # 64 bytes signature

        print(f"\n🔏 Verifica firma Schnorr (BIP340)...")
        print(f"   Pubkey x-only: {len(pubkey_xonly)} bytes")
        print(f"   Signature: {len(sig_bytes)} bytes")
        print(f"   Message hash: {len(event_id_bytes)} bytes")

        # Crea contesto secp256k1
        ctx = lib.secp256k1_context_create(lib.SECP256K1_CONTEXT_NONE)

        # Crea struttura per pubkey x-only
        xonly_pubkey = ffi.new('secp256k1_xonly_pubkey *')

        # Parse della pubkey x-only (32 bytes)
        result = lib.secp256k1_xonly_pubkey_parse(
            ctx, xonly_pubkey, pubkey_xonly)

        if result != 1:
            print(f"   ❌ Impossibile parsare pubkey x-only")
            lib.secp256k1_context_destroy(ctx)
            return {"ok": False, "error": "invalid pubkey"}, 400

        print(f"   ✓ Pubkey x-only parsata correttamente")

        # Verifica firma Schnorr (BIP340)
        result = lib.secp256k1_schnorrsig_verify(
            ctx,
            sig_bytes,
            event_id_bytes,
            32,  # lunghezza messaggio (sempre 32 per SHA256)
            xonly_pubkey
        )

        # Pulisci il contesto
        lib.secp256k1_context_destroy(ctx)

        is_valid = (result == 1)

        if is_valid:
            print(f"   ✅ Firma Schnorr verificata!")
            print(f"\n✅ LOGIN RIUSCITO!")

            # Salva npub in sessione
            session["npub"] = npub_hex

            # IMPORTANTE: Usa Flask-Login per fare il login
            from flask_login import login_user
            from db.db_utils import get_user_by_npub, create_user_from_npub

            # Cerca l'utente nel DB tramite npub
            user_row = get_user_by_npub(npub_hex)

            # Se non esiste, crealo
            if not user_row:
                print(
                    f"   📝 Creazione nuovo utente per npub: {npub_hex[:16]}...")
                user_id = create_user_from_npub(npub_hex)
                user_row = get_user_by_npub(npub_hex)

            # Crea oggetto user e fai login
            user = SimpleUser(id=user_row[0], username=user_row[1])
            login_user(user, remember=True)

            print(f"   ✓ Login Flask completato per user_id={user_row[0]}")
            print("=" * 60)
            return {"ok": True}
        else:
            print(f"   ❌ Firma Schnorr non valida (result={result})")
            print(f"\n❌ FIRMA NON VALIDA")
            print("=" * 60)
            return {"ok": False, "error": "invalid signature"}, 401

    except Exception as e:
        print(f"\n❌ ECCEZIONE durante la verifica:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return {"ok": False, "error": f"verification failed: {str(e)}"}, 400


# LOGIN: inizializzazione minimale di Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


# Minimal user loader so `current_user` is available in templates
class SimpleUser(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    try:
        row = get_user_by_id(int(user_id))
    except Exception:
        return None
    if not row:
        return None
    return SimpleUser(id=row[0], username=row[1])


@app.route('/')
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    dati, saldo_totale_eur, saldo_banca, saldo_contanti = get_transazioni_con_saldo(
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

    return render_template('index.html',
                           saldo_banca=saldo_banca,
                           saldo_contanti=saldo_contanti,
                           saldo_totale_eur=saldo_totale_eur,
                           saldo_btc_da_eur=saldo_btc_da_eur,
                           saldo_totale_satoshi=saldo_totale_satoshi,
                           saldo_eur_lightning=saldo_eur_lightning,
                           saldo_totale_btc=saldo_totale_btc,
                           saldo_eur_onchain=saldo_eur_onchain
                           )


@app.route('/transazioni')
@login_required
def transazioni():
    user_id = current_user.id

    # Ora qui ricevi già i dizionari
    dati, saldo_totale, saldo_banca, saldo_contanti = get_transazioni_con_saldo(
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

    # Elimina la transazione
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM transazioni WHERE id=? AND user_id=?", (id_transazione, user_id))
    conn.commit()
    conn.close()

    # Ricarica le transazioni aggiornate
    dati, saldo_totale, saldo_banca, saldo_contanti = get_transazioni_con_saldo(
        user_id)

    # Saldi banca/contanti
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
        dati, saldo_totale, saldo_banca, saldo_contanti = get_transazioni_con_saldo(
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
    elimina_transazione_da_db_lightning(id_transazione, current_user.id)
    flash("Transazione eliminata con successo", "success")
    dati_Lightning, saldo_totale_satoshi, saldo_eur_lightning = get_transazioni_con_saldo_lightning(
        current_user.id)
    return render_template('transazioni_lightning.html',
                           transazioni_lightning=dati_Lightning,
                           saldo_totale_satoshi=saldo_totale_satoshi,
                           saldo_eur_lightning=saldo_eur_lightning)


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
    flash("Transazione eliminata con successo", "success")

    # 1. Ricalcolo dei dati aggiornati (usa i nomi che ricevi)
    # Assumendo che 'get_transazioni_con_saldo_satoshi_onchain' esista e sia corretta:
    transazioni_aggiornate, saldo_aggiornato = get_transazioni_con_saldo_satoshi_onchain(
        current_user.id)

    # 2. Passa le variabili al template con i NOMI CORRETTI
    return render_template(
        'transazioni_onchain.html',
        # <-- Nome corretto per la lista transazioni
        transazioni_onchain=transazioni_aggiornate,
        saldo_totale_btc=saldo_aggiornato         # <-- Nome corretto per il saldo
    )


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


if __name__ == '__main__':
    # register auth blueprint lazily to avoid circular import at module load
    try:
        from auth import auth_bp
        app.register_blueprint(auth_bp)
    except Exception:
        pass
    app.run(debug=True)
