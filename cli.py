# cli.py

import datetime
from utils.crypto import ottieni_valore_btc_eur, euro_to_btc
from utils.helpers import normalizza_importo, pausa, data_valida
from db.db_utils import (
    leggi_transazioni_da_db,
    elimina_transazione_da_db,
    modifica_transazione_db,
    saldo_iniziale_esistente,
    salva_su_db,
    leggi_transazioni_filtrate
)


def chiedi_saldo_iniziale():
    if saldo_iniziale_esistente():
        return

    print("💰 Vuoi inserire un saldo iniziale? (default 0.00)")
    risposta = input("👉 [s] Sì, [n] No: ").lower()

    if risposta == 's':
        while True:
            saldo = input(
                "Inserisci saldo Iniziale (es. 1000.00): ").replace(',', '.')
            try:
                saldo = f"{float(saldo):.2f}"
                break
            except ValueError:
                print("⚠️ Importo non valido. Riprova")
    else:
        saldo = "0.00"

    oggi = datetime.date.today().isoformat()
    valore_btc_eur = ottieni_valore_btc_eur(oggi)
    controvalore_btc = euro_to_btc(
        saldo, valore_btc_eur) if valore_btc_eur else None
    salva_su_db(oggi, 'Saldo Iniziale', 'Sistema',
                'Iniziale', saldo, controvalore_btc, valore_btc_eur)


def inserisci_transazione():
    print("➕ Inserisci una nuova transazione")
    while True:
        data = input("Data (AAAA-MM-GG): ")
        if data_valida(data):
            break
        else:
            print("⚠️ Data non valida. Riprova.")

    descrizione = input("Descrizione: ")

    # Macro categorie e sottocategorie predefinite
    categorie = {
        'Entrate': ['Stipendio', 'Rimborso', 'Regalo', 'Donazioni', 'Altro'],
        'Abitazione': ['Affitto/Mutuo', 'Bollette: Luce', 'Bollette: acqua', 'Bollette: Gas', 'Bollette: Rifiuti', 'Manutenzione', 'Spese condominiali', 'Assicurazione casa'],
        'Alimentari': ['Supermercato', 'Ristorante - Bar', 'Spesa online', 'Altro'],
        'Trasporti': ['Carburante', 'Mezzi pubblici', 'Manutenzione auto / moto', 'Assicurazione auto', 'Taxi / Uber', 'Noleggi', 'Parcheggi / pedaggi', 'Altro'],
        'Spese Personali': ['Abbigliamento / Scarpe', 'Igiene personale', 'Parrucchiere / estetista', 'Abbonamenti personali (Netflix, Spotify)', 'Libri / Riviste'],
        'Tempo Libero & Intrattenimento': ['Cinema / Teatro / Eventi', 'Sport / Palestra', 'Viaggi / Vacanze', 'Hobby / Collezioni', 'Giochi / App a pagamento'],
        'Finanze & Banche': ['Commissioni bancarie', 'Interessi passivi', 'Prelievi / Depositi', 'Investimenti', 'Criptovalute', 'Giroconti'],
        'Lavoro & Studio': ['Spese di ufficio / coworking', 'Formazione / Corsi', 'Libri / Materiali didattici', 'Trasporti lavoro / studio', 'Pasti lavoro'],
        'Famiglia & Bambini': ['Spese scolastiche', 'Abbigliamento bambino', 'Salute bambino', 'Giocattoli', 'Baby sitter / Asilo', ''],
        'Salute': ['Farmacia', 'Visita medica', 'Altro']
    }

    # 1. Scegli macro categoria
    print("\nMacro categorie disponibili:")
    macro_keys = list(categorie.keys())
    for i, cat in enumerate(macro_keys):
        print(f"[{i}] {cat}")

    while True:
        scelta_macro = input("👉 Scegli il numero della macro categoria: ")
        if scelta_macro.isdigit() and int(scelta_macro) in range(len(macro_keys)):
            categoria = macro_keys[int(scelta_macro)]
            break
        else:
            print("⚠️ Scelta non valida. Riprova.")

    # 2. Scegli sottocategoria
    sottocategorie = categorie[categoria]
    print("\nSottocategorie disponibili:")
    for i, sotto in enumerate(sottocategorie):
        print(f"[{i}] {sotto}")

    while True:
        scelta_sotto = input("👉 Scegli il numero della sottocategoria: ")
        if scelta_sotto.isdigit() and int(scelta_sotto) in range(len(sottocategorie)):
            # scegli la sottocategoria
            sottocategoria = sottocategorie[int(scelta_sotto)]
            break
        else:
            print("⚠️ Scelta non valida. Riprova.")

    importo = input("Importo (es. -50.00 per spesa, 1000.00 per entrata): ")

    while True:
        print("\nHai inserito:")
        print(f"📅 Data: {data}")
        print(f"📝 Descrizione: {descrizione}")
        print(f"🏷️ Categoria: {categoria}")
        print(f"💸 Importo: {importo}")
        print("\n✅ Confermi la transazione?")
        print("[s] Sì, conferma")
        print("[d] Modifica data")
        print("[e] Modifica descrizione")
        print("[c] Modifica categoria")
        print("[i] Modifica importo")
        print("[n] Reinserisci tutto")

        scelta = input("👉 scelta: ").lower()

        if scelta == 's':
            importo_norm = normalizza_importo(importo)
            if importo_norm is None:
                print("⚠️ Importo non valido. Riprova.")
                continue
            valore_btc_eur = ottieni_valore_btc_eur(data)
            controvalore_btc = euro_to_btc(
                importo, valore_btc_eur) if valore_btc_eur else None
            salva_su_db(data, descrizione, categoria, sottocategoria, importo_norm,
                        controvalore_btc, valore_btc_eur)
            print("✅ Transazione salvata.")
            break
        elif scelta == 'd':
            data = input("Nuova data (AAAA-MM-GG): ")
        elif scelta == 'e':
            descrizione = input("Nuova descrizione: ")
        elif scelta == 'c':
            print("\nCategorie disponibili:")
            for i, cat in enumerate(categorie):
                print(f"[{i}] {cat}")
            while True:
                scelta_cat = input("👉 Scegli il numero della categoria: ")
                if scelta_cat.isdigit() and int(scelta_cat) in range(len(categorie)):
                    categoria = list(categorie.keys())[int(scelta_cat)]
                    break
                else:
                    print("⚠️ Scelta non valida.")

            # 👇 Dopo la categoria, chiedi anche la nuova sottocategoria
            sottocategorie = categorie[categoria]
            print("\nSottocategorie disponibili:")
            for i, sotto in enumerate(sottocategorie):
                print(f"[{i}] {sotto}")

            while True:
                scelta_sotto = input(
                    "👉 Scegli il numero della sottocategoria: ")
                if scelta_sotto.isdigit() and int(scelta_sotto) in range(len(sottocategorie)):
                    sottocategoria = sottocategorie[int(scelta_sotto)]
                    break
                else:
                    print("⚠️ Scelta non valida.")


def modifica_transazione():
    print("\n✏️ Vuoi modificare una transazione?")
    scelta = input("👉 [s] Sì, [n] No: ").lower()
    if scelta != 's':
        return

    transazioni = leggi_transazioni_da_db()
    for idx, (id_db, data, desc, cat, sotto, imp, controvalore_btc, valore_btc) in enumerate(transazioni):
        print(f"[{idx}] {data} - {desc} - {cat} - {sotto} - {imp:.2f} € - {controvalore_btc} - {valore_btc} - (ID: {id_db})")

    try:
        indice = int(input("Numero della transazione da modificare: "))
        id_transazione = transazioni[indice][0]
        transazione_attuale = transazioni[indice]
        data_corrente = transazione_attuale[1]
        importo_corrente = transazione_attuale[4]

        print("\n🔁 Quale campo vuoi modificare?")
        print("[d] Data  [e] Descrizione  [c] Categoria [i] Importo")
        campo = input("👉 scelta: ").lower()

        if campo == 'd':
            nuovo_valore = input("Nuova data (AAAA-MM-GG): ")
            modifica_transazione_db(id_transazione, 'data', nuovo_valore)

            prezzo_btc = ottieni_valore_btc_eur(nuovo_valore)
            nuovo_btc = euro_to_btc(
                importo_corrente, prezzo_btc) if prezzo_btc else None
            modifica_transazione_db(
                id_transazione, 'controvalore_btc', nuovo_btc)

        elif campo == 'e':
            nuovo_valore = input("Nuova descrizione: ")
            modifica_transazione_db(
                id_transazione, 'descrizione', nuovo_valore)
        elif campo == 'c':
            categorie = {
                'Entrate': ['Stipendio', 'Rimborso', 'Regalo', 'Donazioni', 'Altro'],
                'Abitazione': ['Affitto/Mutuo', 'Bollette: Luce', 'Bollette: acqua', 'Bollette: Gas', 'Bollette: Rifiuti', 'Manutenzione', 'Spese condominiali', 'Assicurazione casa'],
                'Alimentari': ['Supermercato', 'Ristorante - Bar', 'Spesa online', 'Altro'],
                'Trasporti': ['Carburante', 'Mezzi pubblici', 'Manutenzione auto / moto', 'Assicurazione auto', 'Taxi / Uber', 'Noleggi', 'Parcheggi / pedaggi', 'Altro'],
                'Spese Personali': ['Abbigliamento / Scarpe', 'Igiene personale', 'Parrucchiere / estetista', 'Abbonamenti personali (Netflix, Spotify)', 'Libri / Riviste'],
                'Tempo Libero & Intrattenimento': ['Cinema / Teatro / Eventi', 'Sport / Palestra', 'Viaggi / Vacanze', 'Hobby / Collezioni', 'Giochi / App a pagamento'],
                'Finanze & Banche': ['Commissioni bancarie', 'Interessi passivi', 'Prelievi / Depositi', 'Investimenti', 'Criptovalute', 'Giroconti'],
                'Lavoro & Studio': ['Spese di ufficio / coworking', 'Formazione / Corsi', 'Libri / Materiali didattici', 'Trasporti lavoro / studio', 'Pasti lavoro'],
                'Famiglia & Bambini': ['Spese scolastiche', 'Abbigliamento bambino', 'Salute bambino', 'Giocattoli', 'Baby sitter / Asilo', ''],
                'Salute': ['Farmacia', 'Visita medica', 'Altro']
            }
            print("\nCategorie disponibili:")
            macro_keys = list(categorie.keys())
            for i, cat in enumerate(macro_keys):
                print(f"[{i}] {cat}")

            while True:
                scelta_cat = input("👉 Scegli il numero della categoria: ")
                if scelta_cat.isdigit() and int(scelta_cat) in range(len(macro_keys)):
                    nuova_categoria = macro_keys[int(scelta_cat)]
                    break
                else:
                    print("⚠️ Scelta non valida.")

            sottocategorie = categorie[nuova_categoria]
            print("\nSottocategorie disponibili:")
            for i, sotto in enumerate(sottocategorie):
                print(f"[{i}] {sotto}")
            while True:
                scelta_sotto = input("👉 Scegli sottocategoria: ")
                if scelta_sotto.isdigit() and int(scelta_sotto) in range(len(sottocategorie)):
                    nuova_sottocategoria = sottocategorie[int(scelta_sotto)]
                    break
                else:
                    print("⚠️ Scelta non valida.")

            modifica_transazione_db(
                id_transazione, 'categoria', nuova_categoria)
            modifica_transazione_db(
                id_transazione, 'sottocategoria', nuova_sottocategoria)
        elif campo == 'i':
            while True:
                nuovo_valore = input("Nuovo importo: ").replace(',', '.')
                try:
                    nuovo_valore = f"{float(nuovo_valore):.2f}"
                    break
                except ValueError:
                    print("⚠️ Importo non valido.")
            modifica_transazione_db(id_transazione, 'importo', nuovo_valore)

            prezzo_btc = ottieni_valore_btc_eur(data_corrente)
            nuovo_btc = euro_to_btc(
                nuovo_valore, prezzo_btc) if prezzo_btc else None
            modifica_transazione_db(
                id_transazione, 'controvalore_btc', nuovo_btc)
            modifica_transazione_db(
                id_transazione, 'valore_btc_eur', prezzo_btc)

        else:
            print("⚠️ Campo non valido.")
            return

        print("✅ Transazione modificata.")

    except Exception:
        print("⚠️ Errore: indice non valido.")


def elimina_transazione():
    print("\n🗑 Vuoi eliminare una transazione?")
    transazioni = leggi_transazioni_da_db()

    if not transazioni:
        print("⚠️ Nessuna transazione da eliminare.")
        return

    for idx, (id_db, data, descrizione, categoria, sottocategoria, importo, _, _) in enumerate(transazioni):
        print(
            f"[{idx}] {data} - {descrizione} - {categoria}/{sottocategoria} - {importo:.2f} € (ID: {id_db})")

    try:
        indice = int(
            input("\n👉 Inserisci il numero della transazione da eliminare: "))
        transazione = transazioni[indice]
        id_transazione = transazione[0]

        conferma = input(
            f"\n❗ Sei sicuro di voler eliminare la transazione '{transazione[2]}' del {transazione[1]}? (s/n): ").lower()
        if conferma == 's':
            elimina_transazione_da_db(id_transazione)
            print("✅ Transazione eliminata con successo.")
        else:
            print("⛔ Operazione annullata.")
    except (IndexError, ValueError):
        print("⚠️ Indice non valido.")


def mostra_transazioni_filtrate():
    filtro = input(
        "\n📅 Inserisci filtro data (es. 2025 per anno o 2025-09 per mese): ").strip()

    if not filtro:
        print("⚠️ Filtro non valido.")
        return

    transazioni = leggi_transazioni_filtrate(filtro)

    if not transazioni:
        print("❌ Nessuna transazione trovata per il filtro inserito.")
        return

    print(f"\n📋 Transazioni per il periodo: {filtro}")

    saldo = 0.0
    for id_db, data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur in transazioni:
        btc_str = f"{controvalore_btc:.8f} BTC" if controvalore_btc else "?"
        val_str = f"{valore_btc_eur:.2f} €" if valore_btc_eur else "?"
        print(
            f"🆔 {id_db} - {data} - {descrizione} - {categoria}/{sottocategoria} - {importo:.2f} €")
        saldo += importo

    print(
        f"\n💰 Saldo per il periodo {filtro}: {saldo:.2f} € - {btc_str} @ {val_str}")
    pausa()
