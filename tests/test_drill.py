import sqlite3


def test_drill_down_avanzato(categoria_selezionata, anno=None, mese=None):
    conn = sqlite3.connect('database_dev.db')
    cursor = conn.cursor()

    filtro_data = ""
    parametri = [categoria_selezionata]

    if anno and mese:
        filtro_data = " AND data LIKE ?"
        parametri.append(f"{anno}-{mese}%")
        print(
            f"\n--- 🔍 DRILL-DOWN: '{categoria_selezionata}' | Periodo: {mese}/{anno} ---")
    elif anno:
        filtro_data = " AND data LIKE ?"
        parametri.append(f"{anno}%")
        print(
            f"\n--- 🔍 DRILL-DOWN: '{categoria_selezionata}' | Periodo: Anno {anno} ---")
    else:
        print(
            f"\n--- 🔍 DRILL-DOWN: '{categoria_selezionata}' | Periodo: Tutto lo storico ---")

    parametri_tupla = tuple(parametri)

    # 1. Tabella Euro
    print("\n[Tabella EURO]")
    try:
        query_euro = f"SELECT data, descrizione, importo FROM transazioni WHERE categoria = ?{filtro_data} ORDER BY data DESC"
        cursor.execute(query_euro, parametri_tupla)
        euro_trans = cursor.fetchall()
        if not euro_trans:
            print("  Nessuna transazione trovata in questa categoria.")
        for t in euro_trans:
            print(
                f"  📅 {t[0]} | 📝 {t[1]} | 💰 {t[2]} {{ current_user.default_currency | currency_symbol }}")
    except sqlite3.OperationalError as e:
        print(f"  ❌ Errore lettura tabella transazioni: {e}")

    # 2. Tabella Bitcoin Onchain
    print("\n[Tabella BITCOIN ONCHAIN]")
    try:
        query_onchain = f"SELECT data, descrizione, importo_btc FROM transazioni_onchain WHERE categoria = ?{filtro_data} ORDER BY data DESC"
        cursor.execute(query_onchain, parametri_tupla)
        onchain_trans = cursor.fetchall()
        if not onchain_trans:
            print("  Nessuna transazione trovata in questa categoria.")
        for t in onchain_trans:
            print(f"  📅 {t[0]} | 📝 {t[1]} | ₿ {t[2]} BTC")
    except sqlite3.OperationalError as e:
        print(f"  ❌ Errore lettura tabella transazioni_onchain: {e}")

    # 3. Tabella Lightning
    print("\n[Tabella LIGHTNING]")
    try:
        query_lightning = f"SELECT data, descrizione, satoshi FROM transazioni_lightning WHERE categoria = ?{filtro_data} ORDER BY data DESC"
        cursor.execute(query_lightning, parametri_tupla)
        ln_trans = cursor.fetchall()
        if not ln_trans:
            print("  Nessuna transazione trovata in questa categoria.")
        for t in ln_trans:
            print(f"  📅 {t[0]} | 📝 {t[1]} | ⚡ {t[2]} sat")
    except sqlite3.OperationalError as e:
        print(f"  ❌ Errore lettura tabella transazioni_lightning: {e}")

    conn.close()
    print("\n--------------------------------------------------")


# Lanciamo il test (puoi cambiare i parametri per testare i messaggi di vuoto!)
test_drill_down_avanzato(
    categoria_selezionata='Alimentari', anno='2026', mese='02')
