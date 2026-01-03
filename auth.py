from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, UserMixin, current_user
from db.db_utils import crea_utente, get_user_by_username, get_user_by_id, update_user_password_hash
from app import app, login_manager
import re
import sqlite3

auth_bp = Blueprint('auth', __name__)


class User(UserMixin):
    def __init__(self, id, username, email, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash

    @staticmethod
    def from_db_row(row):
        if not row:
            return None
        return User(id=row[0], username=row[1], email=row[2], password_hash=row[3])


# Impostazione della lunghezza minima per la password
MIN_PASSWORD_LENGTH = 12

# NUOVA FUNZIONE: Controlla se la password rispetta i requisiti attuali


def check_password_complexity(password):
    """Verifica se la password rispetta i requisiti minimi di complessità."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f'La password è troppo corta (minimo {MIN_PASSWORD_LENGTH} caratteri).'

    # Controllo Maiuscola
    if not re.search(r'[A-Z]', password):
        return False, 'La password deve contenere almeno una lettera maiuscola.'

    # Controllo Numero
    if not re.search(r'[0-9]', password):
        return False, 'La password deve contenere almeno un numero.'

    # Controllo Carattere Speciale
    # Usiamo lo stesso set di caratteri speciali della funzione register
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, 'La password deve contenere almeno un carattere speciale (!@#$%^&*...).'

    return True, None


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        # Utilizziamo la nuova funzione per la validazione della password
        is_valid, error_msg = check_password_complexity(password)
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(url_for('auth.register'))
        if not username or not password:
            flash('Username e password richiesti', 'error')
            return redirect(url_for('auth.register'))

        # 1. Controllo Lunghezza Minima
        if len(password) < MIN_PASSWORD_LENGTH:
            flash(
                f'La password deve essere lunga almeno {MIN_PASSWORD_LENGTH} caratteri', 'error')
            return redirect(url_for('auth.register'))
        # 2. INIZIO MODIFICA: Controlli di Complessità (Regex)
        # Controllo per almeno una lettera MAIUSCOLA
        if not re.search(r'[A-Z]', password):
            flash('La password deve contenere almeno una lettera maiuscola', 'error')
            return redirect(url_for('auth.register'))
        # Controllo per almeno un NUMERO
        if not re.search(r'[0-9]', password):
            flash('La password deve contenere almeno un numero', 'error')
            return redirect(url_for('auth.register'))
        # Controllo per almeno un CARATTERE SPECIALE
        # Ho incluso un set comune di caratteri speciali (punteggiatura, simboli, ecc.)
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            flash(
                'La password deve contenere almeno un carattere speciale (!@#$%^&*...).', 'error')
            return redirect(url_for('auth.register'))
        # check existing
        existing = get_user_by_username(username)
        if existing:
            flash('Username già presente', 'error')
            return redirect(url_for('auth.register'))
        pw_hash = generate_password_hash(password)
        user_id = crea_utente(username, email, pw_hash)
        user = User(user_id, username, email, pw_hash)
        login_user(user)
        flash('Registrazione completata', 'success')
        return redirect(url_for('home'))
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        row = get_user_by_username(username)

        # 1. Username non trovato
        if not row:
            flash('Credenziali non valide', 'error')
            return redirect(url_for('auth.login'))

        user = User.from_db_row(row)

        # 2. Password errata
        if not check_password_hash(user.password_hash, password):
            flash('Credenziali non valide', 'error')
            return redirect(url_for('auth.login'))

        # 3. Verifica complessità (Password corretta ma è debole?)
        is_complex, _ = check_password_complexity(password)

        if not is_complex:
            # ************ MODIFICA CHIAVE QUI ************

            # Autenticazione OK, ma password debole -> FORZA RESET
            # Memorizza l'ID utente nella sessione
            session['force_reset_user_id'] = user.id

            flash('La tua vecchia password non rispetta i nuovi standard di sicurezza. Devi impostare una nuova password per procedere.', 'error')

            # Reindirizza alla rotta di reset forzato
            return redirect(url_for('auth.force_password_reset'))

            # **********************************************

        # 4. Login standard (Password corretta E complessa)
        login_user(user)
        flash('Login effettuato', 'success')
        return redirect(url_for('home'))

    return render_template('login.html')

# NUOVA ROTTA: Gestisce la reimpostazione forzata della password


@auth_bp.route('/force-reset', methods=['GET', 'POST'])
def force_password_reset():
    user_id_to_reset = session.get('force_reset_user_id')

    if not user_id_to_reset:
        # Se l'ID utente non è nella sessione, reindirizza al login
        flash('Accesso negato. Esegui prima il login.', 'error')
        return redirect(url_for('auth.login'))

    user_row = get_user_by_id(user_id_to_reset)

    # Assumiamo che l'utente esista ancora, altrimenti torniamo al login
    if not user_row:
        session.pop('force_reset_user_id', None)
        flash('Errore utente non trovato.', 'error')
        return redirect(url_for('auth.login'))

    user = User.from_db_row(user_row)

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or new_password != confirm_password:
            flash('Le password non corrispondono o sono vuote.', 'error')
            return render_template('force_password_reset.html', username=user.username)

        # Riconvalida la complessità della NUOVA password
        is_valid, error_msg = check_password_complexity(new_password)

        if not is_valid:
            flash(error_msg, 'error')
            return render_template('force_password_reset.html', username=user.username)

        # Hash e aggiornamento nel database
        pw_hash = generate_password_hash(new_password)

        # CHIAMA LA FUNZIONE DI UTILITÀ DEL DB
        try:
            update_user_password_hash(user.id, pw_hash)
        except Exception:
            flash(
                'Errore interno durante l\'aggiornamento della password. Riprova.', 'error')
            # Assicurati che questo return sia presente
            return render_template('force_password_reset.html', username=user.username)

        # Successo: fai il login e pulisci la sessione
        session.pop('force_reset_user_id', None)
        login_user(user)
        # Leggermente più esplicito
        flash('Password aggiornata con successo! Accesso effettuato. Benvenuto.', 'success')
        # L'utente viene reindirizzato alla home e dovrebbe essere loggato
        return redirect(url_for('home'))

    # Se GET, mostra il form di reset
    return render_template('force_password_reset.html', username=user.username)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout effettuato', 'success')
    return redirect(url_for('home'))


@auth_bp.route('/elimina_utente/<int:user_id>', methods=['POST'])
def elimina_utente(user_id):
    # Il resto del codice rimane uguale
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    logout_user() # Ti consiglio di aggiungerlo così pulisce la sessione
    flash("Utente eliminato correttamente", "success")
    return redirect(url_for('home'))
