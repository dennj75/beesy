import os
import re

def pulisci_po_definitivo(filepath):
    if not os.path.exists(filepath):
        print(f"⚠️ File non trovato: {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 1. Elimina drasticamente tutte le righe obsolete (#~)
    lines_pulite = [line for line in lines if not line.strip().startswith('#~')]
    content = "".join(lines_pulite).replace('\r\n', '\n')

    # 2. Separa i blocchi del file .po
    raw_blocks = re.split(r'\n\s*\n', content)
    
    header = ""
    entries = {}  # msgid -> dict

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        # Mantieni l'intestazione gettext
        if 'msgid ""' in block and 'msgstr ""' in block and not header:
            header = block
            continue

        # Estrai msgid e msgstr
        msgid_match = re.search(r'msgid\s+"((?:[^"\\]|\\.)*)"', block)
        msgstr_match = re.search(r'msgstr\s+"((?:[^"\\]|\\.)*)"', block)

        if msgid_match and msgstr_match:
            msgid = msgid_match.group(1)
            msgstr = msgstr_match.group(1)
            comments = [l for l in block.split('\n') if l.startswith('#')]

            if msgid not in entries:
                entries[msgid] = {
                    'comments': list(comments),
                    'msgstr': msgstr
                }
            else:
                # Unisci le righe di riferimento (#:) senza duplicarle
                for c in comments:
                    if c not in entries[msgid]['comments']:
                        entries[msgid]['comments'].append(c)
                # Se la voce esistente era vuota, prendi quella tradotta
                if not entries[msgid]['msgstr'] and msgstr:
                    entries[msgid]['msgstr'] = msgstr

    # 3. Ricostruisci il file .po pulito
    new_content = header + "\n\n" if header else ""
    for msgid, data in entries.items():
        if data['comments']:
            new_content += "\n".join(data['comments']) + "\n"
        new_content += f'msgid "{msgid}"\n'
        new_content += f'msgstr "{data["msgstr"]}"\n\n'

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"✨ File {filepath} ripulito al 100%!")

# Esegui la pulizia
pulisci_po_definitivo("translations/en/LC_MESSAGES/messages.po")
pulisci_po_definitivo("translations/zh/LC_MESSAGES/messages.po")