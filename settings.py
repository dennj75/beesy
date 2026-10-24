from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_babel import _
from db.db_utils import DB_PATH
from utils.helpers import VALUTE_SUPPORTATE
import sqlite3

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/impostazioni', methods=['GET', 'POST'])
@login_required
def impostazioni():
    if request.method == 'POST':
        nuova_valuta = request.form.get('valuta')

        if nuova_valuta in VALUTE_SUPPORTATE:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET default_currency = ? 
                WHERE id = ?
            """, (nuova_valuta, current_user.id))
            conn.commit()
            conn.close()

            current_user.default_currency = nuova_valuta

            flash(_("Valuta predefinita aggiornata con successo!"), "success")
            return redirect(url_for('settings.impostazioni'))

    # AGGIUNGI QUI valute=VALUTE_SUPPORTATE
    return render_template('impostazioni.html', valute=VALUTE_SUPPORTATE)
