from flask import Flask, render_template, request, redirect, url_for, flash
from db.db_utils import get_transazioni_con_saldo_lightning, leggi_transazioni_da_db, salva_su_db, elimina_transazione_da_db, modifica_transazione_db, inizializza_db, salva_su_db_lightning, leggi_transazioni_da_db_lightning, modifica_transazione_db_lightning, elimina_transazione_da_db_lightning, leggi_transazioni_da_db_onchain, salva_su_db_onchain, leggi_transazioni_filtrate_onchain, elimina_transazione_da_db_onchain, modifica_transazione_db_onchain
from flask import send_file
from utils.export import esporta_csv, esporta_csv_per_mese, esporta_csv_lightning, esporta_csv_per_mese_lightning, esporta_csv_onchain, esporta_csv_per_mese_onchain
from utils.crypto import ottieni_valore_btc_eur, euro_to_btc
from utils.helpers import normalizza_importo
import json
import sqlite3

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


def get_transazioni_con_saldo_lightning():
    transazioni_lightning = leggi_transazioni_da_db_lightning()
    # t[6] è la colonna 'satoshi'
    saldo_satoshi = sum(float(t[6])
                        for t in transazioni_lightning if t[6] is not None)
    # t[7] è la colonna 'controvalore_eur'
    saldo_eur_lightning = sum(float(t[7])
                              for t in transazioni_lightning if t[7] is not None)
    # AGGIUNTO saldo_eur_lightning
    return transazioni_lightning, saldo_satoshi, saldo_eur_lightning


def get_transazioni_con_saldo():
    transazioni = leggi_transazioni_da_db()
    saldo = sum(float(t[5]) for t in transazioni if t[5] is not None)
    return transazioni, saldo


def get_transazioni_con_saldo_onchain():
    transazioni = leggi_transazioni_da_db_onchain()
    saldo_totale_btc = sum(float(t[7])
                           for t in transazioni if t[7] is not None)
    return transazioni, saldo_totale_btc


def get_transazioni_con_saldo_satoshi_onchain():
    transazioni_onchain = leggi_transazioni_da_db_onchain()
    saldo_totale_btc = sum(float(t[7])
                           for t in transazioni_onchain if t[7] is not None)
    return transazioni_onchain, saldo_totale_btc


app = Flask(__name__)
# Chiave necessaria per i flash e da cambiare in produzione
app.secret_key = 'supersecretkey'


@app.route('/')
def home():
    dati, saldo_totale = get_transazioni_con_saldo()
    # Ora riceviamo anche il saldo_eur_lightning dalla funzione aggiornata
    dati_lightning, saldo_totale_satoshi, saldo_eur_lightning = get_transazioni_con_saldo_lightning()
    # sarà la homepage
    return render_template('index.html',
                           saldo_totale=saldo_totale,
                           saldo_totale_satoshi=saldo_totale_satoshi,  # PASSATO ALLA TEMPLATE
                           saldo_eur_lightning=saldo_eur_lightning  # PASSATO ALLA TEMPLATE
                           )


@app.route('/transazioni')
def transazioni():
    dati, saldo_totale = get_transazioni_con_saldo()
    return render_template('transazioni.html', transazioni=dati, saldo_totale=saldo_totale)


@app.route('/nuova_transazione', methods=['GET', 'POST'])
def nuova_transazione():
    if request.method == 'POST':
        data = request.form['data']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form.get('sottocategoria', '')

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
            salva_su_db(data, descrizione, categoria, sottocategoria,
                        importo, controvalore_btc, valore_btc_eur)
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


@app.route('/elimina-transazione/<int:id_transazione>', methods=['POST'])
def elimina_transazione_web(id_transazione):
    elimina_transazione_da_db(id_transazione)
    flash("Transazione eliminata con successo", "success")
    dati, saldo_totale = get_transazioni_con_saldo()
    return render_template('transazioni.html', transazioni=dati, saldo_totale=saldo_totale)


@app.route('/modifica-transazione/<int:id_transazione>', methods=['GET', 'POST'])
def modifica_transazione_web(id_transazione):
    # Leggi tutte le transazioni e e cerca quella con id = id_transazione
    transazioni = leggi_transazioni_da_db()
    t = None
    for tr in transazioni:
        if tr[0] == id_transazione:
            t = tr
            break
    if t is None:
        flash("Transazione non trovata", "error")
        return redirect(url_for('transazioni'))

    if request.method == 'POST':
        data = request.form['data']
        descrizione = request.form['descrizione']
        categoria = request.form['categoria']
        sottocategoria = request.form['sottocategoria']
        importo_normalizzato = float(
            normalizza_importo(request.form['importo']))
        if importo_normalizzato is None:
            flash("Importo non valido", "error")
            return redirect(url_for('modifica_transazione_web', id_transazione=id_transazione))

        importo = float(importo_normalizzato)

        # chiama la funzione di modifica
        modifica_transazione_db(id_transazione, 'data', data)
        modifica_transazione_db(id_transazione, 'descrizione', descrizione)
        modifica_transazione_db(id_transazione, 'categoria', categoria)
        modifica_transazione_db(
            id_transazione, 'sottocategoria', sottocategoria)
        modifica_transazione_db(id_transazione, 'importo', importo)
        # Ricalcola e aggiorna BTC
        valore_btc_eur = ottieni_valore_btc_eur(data)

        if valore_btc_eur is not None:
            controvalore_btc = euro_to_btc(importo, valore_btc_eur)
            modifica_transazione_db(
                id_transazione, 'valore_btc_eur', valore_btc_eur)
            modifica_transazione_db(
                id_transazione, 'controvalore_btc', controvalore_btc)
        else:
            flash("⚠️ Impossibile ottenere il valore BTC per la data selezionata. Verifica la connessione o riprova più tardi.", "error")

        dati, saldo_totale = get_transazioni_con_saldo()
        return render_template('transazioni.html', transazioni=dati, saldo_totale=saldo_totale)
        # return redirect(url_for('transazioni'))

    # Se GET, mostra il form con i dati precompilati
    return render_template(
        'modifica_transazione.html',
        transazione=t,
        categorie=list(CATEGORIE.keys()),
        categorie_json=json.dumps(CATEGORIE)
    )


@app.route('/scarica-csv')
def scarica_csv():
    nome_file = 'exports/transazioni.csv'
    esporta_csv(nome_file)  # Genera il csv aggiornato
    return send_file(nome_file, as_attachment=True, download_name=f"transazioni.csv")


@app.route('/scarica-csv-mese', methods=['GET', 'POST'])
def scarica_csv_per_mese():
    if request.method == 'POST':
        mese = request.form['mese']  # esempio formato YYYY-MM
        if len(mese) != 7 or not mese[:4].isdigit() or mese[4] != '-' or not mese[5:].isdigit():
            flash("⚠️ Formato mese non valido. Usa YYYY-MM.", "error")
            return redirect(url_for('scarica_csv_per_mese'))

        nome_file = f'exports/transazioni_{mese}.csv'
        esporta_csv_per_mese(mese)  # Genera il csv aggiornato
        return send_file(nome_file, as_attachment=True, download_name=f"transazioni_{mese}.csv")

    return render_template('scarica_csv_per_mese.html')


@app.route('/transazioni_lightning')
def transazioni_lightning():

    # Questa funzione restituisce 3 valori (lista, saldo sats, saldo eur)
    dati_lightning, saldo_totale_satoshi, saldo_eur_lightning = get_transazioni_con_saldo_lightning()

    # *CAMBIARE 'index.html' con 'transazioni_lightning.html'*
    return render_template("transazioni_lightning.html",
                           transazioni_lightning=dati_lightning,
                           saldo_totale_satoshi=saldo_totale_satoshi,
                           saldo_eur_lightning=saldo_eur_lightning
                           )


@app.route('/nuova_transazione_lightning', methods=['GET', 'POST'])
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
def elimina_transazione_web_lightning(id_transazione):
    elimina_transazione_da_db_lightning(id_transazione)
    flash("Transazione eliminata con successo", "success")
    dati_Lightning, saldo_totale_satoshi, saldo_eur_lightning = get_transazioni_con_saldo_lightning()
    return render_template('transazioni_lightning.html',
                           transazioni_lightning=dati_Lightning,
                           saldo_totale_satoshi=saldo_totale_satoshi,
                           saldo_eur_lightning=saldo_eur_lightning)


@app.route('/modifica-transazione_lightning/<int:id_transazione>', methods=['GET', 'POST'])
def modifica_transazione_web_lightning(id_transazione):
    # Leggi tutte le transazioni e e cerca quella con id = id_transazione
    transazioni_lightning = leggi_transazioni_da_db_lightning()
    t = None
    for tr in transazioni_lightning:
        if tr[0] == id_transazione:
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
        modifica_transazione_db_lightning(id_transazione, 'data', data)
        modifica_transazione_db_lightning(id_transazione, 'wallet', wallet)
        modifica_transazione_db_lightning(
            id_transazione, 'descrizione', descrizione)
        modifica_transazione_db_lightning(
            id_transazione, 'categoria', categoria)
        modifica_transazione_db_lightning(
            id_transazione, 'sottocategoria', sottocategoria)
        modifica_transazione_db_lightning(id_transazione, 'satoshi', satoshi)
        # Ricalcola e aggiorna BTC
        valore_btc_eur = ottieni_valore_btc_eur(data)

        if valore_btc_eur is not None:
            # Calcola il controvalore in euro in base ai satoshi
            controvalore_eur = (int(satoshi) / 100_000_000) * valore_btc_eur

            # Aggiorna i campi corretti nel DB
            modifica_transazione_db_lightning(
                id_transazione, 'valore_btc_eur', valore_btc_eur)
            modifica_transazione_db_lightning(
                id_transazione, 'controvalore_eur', controvalore_eur)
        else:
            flash("⚠️ Impossibile ottenere il valore BTC per la data selezionata. Verifica la connessione o riprova più tardi.", "error")

        dati_lightning, saldo_totale_satoshi = get_transazioni_con_saldo_lightning()
        return render_template('transazioni_lightning.html', transazioni_lightning=dati_lightning, saldo_totale_satoshi=saldo_totale_satoshi)

    # Se GET, mostra il form con i dati precompilati
    return render_template(
        'modifica_transazione_lightning.html',
        transazione_lightning=t,
        categorie=list(CATEGORIE.keys()),
        categorie_json=json.dumps(CATEGORIE)
    )


@app.route('/scarica_csv_lightning')
def scarica_csv_lightning():
    nome_file = 'exports/transazioni_lightning.csv'
    esporta_csv_lightning(nome_file)  # Genera il csv aggiornato
    return send_file(nome_file, as_attachment=True, download_name=f"transazioni_lightning.csv")


@app.route('/scarica_csv_lightning_per_mese', methods=['GET', 'POST'])
def scarica_csv_per_mese_lightning():
    if request.method == 'POST':
        mese = request.form['mese']  # esempio formato YYYY-MM
        if len(mese) != 7 or not mese[:4].isdigit() or mese[4] != '-' or not mese[5:].isdigit():
            flash("⚠️ Formato mese non valido. Usa YYYY-MM.", "error")
            return redirect(url_for('scarica_csv_per_mese_lightning'))

        nome_file = f'exports/transazioni_{mese}_lightning.csv'
        esporta_csv_per_mese_lightning(mese)  # Genera il csv aggiornato
        return send_file(nome_file, as_attachment=True, download_name=f"transazioni_{mese}_lightning.csv")

    return render_template('scarica_csv_per_mese_lightning.html')


@app.route('/transazioni_onchain')
def transazioni_onchain():
    dati_onchain, saldo_totale_btc = get_transazioni_con_saldo_onchain()
    return render_template("transazioni_onchain.html", transazioni_onchain=dati_onchain, saldo_totale_btc=saldo_totale_btc)


@app.route('/nuova_transazione_onchain', methods=['GET', 'POST'])
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

    return render_template(
        'nuova_transazione_onchain.html',
        transazione_onchain=[None, '', '', '', '', '',
                             '', '', '', '', ''],  # placeholder vuoti
        categorie=list(CATEGORIE.keys()),
        categorie_json=json.dumps(CATEGORIE)
    )


@app.route('/elimina_transazione_onchain/<int:id_transazione>', methods=['POST'])
def elimina_transazione_web_onchain(id_transazione):
    elimina_transazione_da_db_onchain(id_transazione)
    flash("Transazione eliminata con successo", "success")
    dati_onchain, saldo_totale_satoshi_onchain = get_transazioni_con_saldo_satoshi_onchain()
    return render_template('transazioni_onchain.html', transazioni_lightning=dati_onchain, saldo_totale_satoshi=saldo_totale_satoshi_onchain)


@app.route('/modifica-transazione_onchain/<int:id_transazione>', methods=['GET', 'POST'])
def modifica_transazione_web_onchain(id_transazione):
    # Leggi tutte le transazioni e e cerca quella con id = id_transazione
    transazioni_onchain = leggi_transazioni_da_db_onchain()
    t = None
    for tr in transazioni_onchain:
        if tr[0] == id_transazione:
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
        modifica_transazione_db_onchain(id_transazione, 'data', data)
        modifica_transazione_db_onchain(id_transazione, 'wallet', wallet)
        modifica_transazione_db_onchain(
            id_transazione, 'descrizione', descrizione)
        modifica_transazione_db_onchain(
            id_transazione, 'categoria', categoria)
        modifica_transazione_db_onchain(
            id_transazione, 'sottocategoria', sottocategoria)
        modifica_transazione_db_onchain(
            id_transazione, 'transactionID', transactionID)
        modifica_transazione_db_onchain(
            id_transazione, 'importo_btc', importo_btc)
        modifica_transazione_db_onchain(id_transazione, 'fee', fee)
        # Ricalcola e aggiorna BTC
        valore_btc_eur = ottieni_valore_btc_eur(data)
        if valore_btc_eur:
            controvalore_eur = importo_btc * valore_btc_eur
            modifica_transazione_db_onchain(
                id_transazione, 'valore_btc_eur', valore_btc_eur)
            modifica_transazione_db_onchain(
                id_transazione, 'controvalore_eur', controvalore_eur)
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
def scarica_csv_onchain():
    nome_file = 'exports/transazioni_onchain.csv'
    esporta_csv_onchain(nome_file)  # Genera il csv aggiornato
    return send_file(nome_file, as_attachment=True, download_name=f"transazioni_onchain.csv")


@app.route('/scarica_csv_onchain_per_mese', methods=['GET', 'POST'])
def scarica_csv_per_mese_onchain():
    if request.method == 'POST':
        mese = request.form['mese']  # esempio formato YYYY-MM
        if len(mese) != 7 or not mese[:4].isdigit() or mese[4] != '-' or not mese[5:].isdigit():
            flash("⚠️ Formato mese non valido. Usa YYYY-MM.", "error")
            return redirect(url_for('scarica_csv_per_mese_onchain'))

        nome_file = f'exports/transazioni_{mese}_onchain.csv'
        esporta_csv_per_mese_lightning(mese)  # Genera il csv aggiornato
        return send_file(nome_file, as_attachment=True, download_name=f"transazioni_{mese}_onchain.csv")

    return render_template('scarica_csv_per_mese_onchain.html')


if __name__ == '__main__':
    app.run(debug=True)
