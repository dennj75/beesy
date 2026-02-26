import sqlite3
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
# Puliamo le chiavi master così Beesy ne genererà di nuove con la firma fissa
cursor.execute(
    "UPDATE users SET encrypted_master_key = NULL WHERE auth_type = 'nostr'")
conn.commit()
conn.close()
print("✅ Database pronto per il nuovo inizio!")
