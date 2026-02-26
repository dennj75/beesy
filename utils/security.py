import hashlib
import os
import base64
from base64 import b64decode, b64encode
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# 1. TRASFORMA LA PASSWORD IN UNA CHIAVE PER IL "CASSETTO"


def get_key_from_password(password, username):
    """Genera una chiave deterministica usando password e username (come salt)"""
    salt = username.encode().ljust(16, b'\x00')[
        :16]  # Usiamo lo username come salt per ora
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

# 2. GENERA UNA MASTER KEY CASUALE (Quella che useremo per i JSON)


def generate_master_key():
    return Fernet.generate_key().decode()

# 3. CRIPTA LA MASTER KEY (Prima di salvarla nel DB)


def encrypt_master_key(master_key, password, username):
    """Protegge la master key prima di salvarla nel Database."""
    key = get_key_from_password(password, username)
    f = Fernet(key)
    return f.encrypt(master_key.encode()).decode()

# 4. DECRIPTA LA MASTER KEY (Quando serve per il backup)


def genera_chiave_da_nostr(firma_hex):
    """
    Trasforma la firma di Nostr in una chiave crittografica a 32 byte.
    Usiamo SHA-256 per assicurarci che la lunghezza sia sempre corretta.
    """
    # Trasformiamo la firma in un hash per avere una lunghezza fissa (32 byte)
    chiave = hashlib.sha256(firma_hex.encode()).digest()
    return b64encode(chiave)  # Restituiamo in base64 per compatibilità


def decrypt_master_key(user, password_o_firma):
    from cryptography.fernet import Fernet
    import base64
    import os
    from db.db_utils import salva_master_key_nel_db

    # Controlliamo se quello che ci è arrivato è una firma Nostr (lunga) o una password (corta)
    is_firma = password_o_firma and len(str(password_o_firma)) > 60

    # 1. DETERMINIAMO LA CHIAVE DI PROTEZIONE
    if is_firma:
        # Se abbiamo una firma, la usiamo per derivare la chiave (Flusso Nostr dinamico)
        chiave_protezione = genera_chiave_da_nostr(password_o_firma)
        print(f"DEBUG: Uso FIRMA Nostr per {user.username}")
    elif user.auth_type == 'nostr':
        # Se è un utente Nostr ma NON abbiamo la firma (es. backup automatico), usiamo l'username fisso
        chiave_protezione = genera_chiave_da_nostr(user.username)
        print(f"DEBUG: Uso USERNAME fisso per utente Nostr {user.username}")
    else:
        # Utente tradizionale: usiamo la password
        chiave_protezione = get_key_from_password(
            password_o_firma, user.username)
        print(f"DEBUG: Uso PASSWORD per utente tradizionale {user.username}")

    # 2. GENERAZIONE SE ASSENTE (Invariato)
    if not user.encrypted_master_key:
        nuova_mk = base64.urlsafe_b64encode(os.urandom(32)).decode()
        f = Fernet(chiave_protezione)
        encrypted_mk = f.encrypt(nuova_mk.encode()).decode()
        salva_master_key_nel_db(user.id, encrypted_mk)
        return nuova_mk

    # 3. DECRIPTAZIONE
    f = Fernet(chiave_protezione)
    try:
        decrypted_mk = f.decrypt(user.encrypted_master_key.encode()).decode()
        return decrypted_mk
    except Exception as e:
        print(f"DEBUG: Errore decriptazione: {e}")
        return None


def encrypt_data(data_string: str, master_key: str):
    """Cripta il contenuto del file JSON usando la Master Key."""
    return Fernet(master_key.encode()).encrypt(data_string.encode()).decode()


def decrypt_data(encrypt_data: str, master_key: str):
    """Decripta il contenuto del file JSON di backup usando la Master Key."""
    try:
        f = Fernet(master_key.encode())
        return f.decrypt(encrypt_data.encode()).decode()
    except Exception as e:
        print(f"Errore durante la decriptazione dei dati: {e}")
        return None
