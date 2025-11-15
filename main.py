# main.py
from utils.export import esporta_csv, esporta_csv_per_mese
from db.db_utils import inizializza_db, leggi_transazioni_da_db, leggi_transazioni_filtrate
from utils.helpers import pausa
from utils.crypto import ottieni_valore_btc_eur, euro_to_btc
from cli import (
    chiedi_saldo_iniziale,
    inserisci_transazione,
    elimina_transazione,
    modifica_transazione,
    mostra_transazioni_filtrate,
)

import csv
import os


def mostra_transazioni():
    transazioni = leggi_transazioni_da_db()
    print("\n📋 Transazioni registrate:")
    saldo = 0.0
    for t in transazioni:
        id_db, data, descrizione, categoria, sottocategoria, importo, controvalore_btc, valore_btc_eur = t
        btc_str = f"{controvalore_btc:.8f} BTC" if controvalore_btc else "?"
        btc_str_val = f"{valore_btc_eur:.2f} BTC" if valore_btc_eur else "?"
        print(
            f"🆔 {id_db} - {data} - {descrizione} - {categoria} - {sottocategoria}  - {importo:.2f} € - {btc_str} - {btc_str_val}")
        saldo += importo

    print(f"\n💰 Saldo totale attuale: {saldo:.2f} €")
    pausa()


def main():
    print("📂 Tracker Avviato")
    inizializza_db()
    chiedi_saldo_iniziale()

    while True:
        print("\n==============================")
        print("📋 Scegli un'opzione:")
        print("1. ➕ Inserisci una transazione")
        print("2. 🗑 Elimina transazione")
        print("3. ✏️ Modifica transazione")
        print("4. 💾 Esporta CSV")
        print("5. 📖 Mostra tutte le transazioni")
        print("6. 📅 Filtra per mese/anno")
        print("7. 📤 Esporta csv per mese")
        print("0. ❌ Esci")
        print("==============================")
        scelta = input("👉 Scelta: ").strip()

        if scelta == '1':
            inserisci_transazione()
        elif scelta == '2':
            elimina_transazione()
        elif scelta == '3':
            modifica_transazione()
        elif scelta == '4':
            esporta_csv()
        elif scelta == '5':
            mostra_transazioni()
        elif scelta == '6':
            mostra_transazioni_filtrate()
        elif scelta == '7':
            mese = input(
                "\n📅 Inserisci il mese da esportare (formato YYYY-MM) ").strip()
            if len(mese) != 7 or not mese[:4].isdigit() or mese[4] != '-' or not mese[5:].isdigit():
                print("⚠️ Formato mese non valido. Usa YYYY-MM.")
            else:
                esporta_csv_per_mese(mese)
                pausa()
        elif scelta == '0':
            conferma = input(
                "❓Sei sicuro di voler uscire? (s/n): ").lower()
            if conferma == 's':
                print("👋 Uscita dal programma.")
                break
            else:
                continue
        else:
            print("⚠️ Scelta non valida. Riprova.")


if __name__ == '__main__':
    main()
