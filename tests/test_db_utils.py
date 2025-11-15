
# Aggiunge la cartella superiore (radice del progetto) al path


# test/test_db_utils.py

from db import db_utils  # Importato dopo che sys.path è stato modificato
import pytest
import sys
import os


@pytest.fixture(autouse=True)
def setup_db():
    db_utils.inizializza_db()
    yield
    if os.path.exists(db_utils.DB_PATH):
        os.remove(db_utils.DB_PATH)


def test_salva_e_leggi_transazione():
    # Salva una transazione
    db_utils.salva_su_db(
        "2025-10-15",
        "Test descrizione",
        "Entrate",
        "Stipendio",
        1000.00,
        0.025,
        40000.00
    )

    # Leggi le transazioni dal DB
    transazioni = db_utils.leggi_transazioni_da_db()

    assert len(transazioni) == 1

    t = transazioni[0]
    assert t[1] == "2025-10-15"
    assert t[2] == "Test descrizione"
    assert t[3] == "Entrate"
    assert t[4] == "Stipendio"
    assert t[5] == 1000.00
    assert t[6] == 0.025
    assert t[7] == 40000.00
