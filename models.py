# models.py
from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, id, username, email, password_hash, encrypted_master_key=None, npub=None, pubkey=None, auth_type='local'):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.encrypted_master_key = encrypted_master_key
        self.npub = npub
        self.pubkey = pubkey
        self.auth_type = auth_type

    @staticmethod
    def from_db_row(row):
        if not row:
            return None

        # Questa struttura impedisce l'IndexError controllando la lunghezza della riga
        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            password_hash=row[3],
            npub=row[4] if len(row) > 4 else None,
            encrypted_master_key=row[5] if len(row) > 5 else None,
            pubkey=row[6] if len(row) > 6 else None,
            auth_type=row[7] if len(row) > 7 else 'local'
        )
