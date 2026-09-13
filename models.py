# models.py
from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, id, username, email, password_hash, encrypted_master_key=None, npub=None, pubkey=None, auth_type='local', default_currency='EUR'):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.encrypted_master_key = encrypted_master_key
        self.npub = npub
        self.pubkey = pubkey
        self.auth_type = auth_type
        self.default_currency = default_currency

    @staticmethod
    def from_db_row(row):
        if not row:
            return None

        # Supporto sia per sqlite3.Row (accesso per nome colonna) sia per tupla classica (accesso per indice)
        if hasattr(row, 'keys'):
            return User(
                id=row['id'],
                username=row['username'],
                email=row['email'],
                password_hash=row['password_hash'],
                npub=row['npub'] if 'npub' in row.keys() else None,
                encrypted_master_key=row['encrypted_master_key'] if 'encrypted_master_key' in row.keys() else None,
                pubkey=row['pubkey'] if 'pubkey' in row.keys() else None,
                auth_type=row['auth_type'] if 'auth_type' in row.keys() else 'local',
                default_currency=row['default_currency'] if 'default_currency' in row.keys() else 'EUR'
            )

        # Gestione tramite indici numerici (se la riga è una tupla standard)
        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            password_hash=row[3],
            npub=row[4] if len(row) > 4 else None,
            encrypted_master_key=row[5] if len(row) > 5 else None,
            pubkey=row[6] if len(row) > 6 else None,
            auth_type=row[7] if len(row) > 7 else 'local',
            default_currency=row[8] if len(row) > 8 and row[8] else 'EUR'
        )