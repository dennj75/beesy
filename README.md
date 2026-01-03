# ₿eesy - Bitcoin Expense Tracker 🐝⚡

> **"Your Node, Your Rules. Your Data, Your Privacy."**

[![GitHub license](https://img.shields.io/github/license/dennj75/bitcoin-expense-tracker?style=flat-square)](LICENSE)
[![GitHub stars](https://imgpl.io/github/stars/dennj75/bitcoin-expense-tracker?style=flat-square)](https://github.com/dennj75/bitcoin-expense-tracker/stargazers)

---

## ⚠️ IMPORTANT DISCLAIMER (READ BEFORE USE)
This project is an **EXPERIMENTAL EDUCATIONAL LABORATORY**.
- **NOT** production-ready software.
- **DO NOT** entrust critical financial data to this system without external backups.
- The author is **NOT** responsible for any data loss or security vulnerabilities.
- **PRIVACY:** By running this software locally, your data stays in your SQLite database (`.db`). You are solely responsible for its custody.

---

## 🌟 Unique Features

- 📱 **Nostr Mobile Auth:** Experimental login via **Amber (Nostr Signer)** on smartphones using the `intent` protocol.
- 🖥 **Nostr PC Login** - Decentralized authentication using NIP-07 (ALBY, nos2x extension):
    - Sign in with your existing Nostr identity.
    - Schnorr signature verification (BIP340).
    - No password needed.

- 🔐 **Self-Sovereign:** No central server. Install it on your PC, Raspberry Pi, or Umbrel node.
- ⚡ **Lightning Ready:** Separate management for on-chain and off-chain transactions with Satoshi precision.
- 💱 **Historical Conversion:** Automatic BTC/EUR price retrieval via CoinGecko API.

### 🔧 Auto-Configuration
- No SQL knowledge required! ₿eesy features a **Plug & Play** system: 
On the first run, the application automatically detects if the database is missing and creates it for you, including all necessary tables for EUR, Lightning, and On-chain transactions.

---

### 🛠️ TechStack

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Backend** | Flask (Python) | Server-side logic & API management |
| **Database** | SQLite | Local-first, private data storage |
| **API** | CoinGecko | Real-time & historical BTC prices |
| **Frontend** | HTML, CSS, JS (Vanilla) | Clean, responsive user interface |
| **Auth (Desktop)** | Flask-Login + NIP-07 | Traditional or extension-based login |
| **Auth (Mobile)** | **Amber (Nostr Signer)** | Password-less login via Android Intents |
| **Cryptography** | `coincurve` | BIP340/Schnorr signature verification |

## 🚀 Quick Start (Self-Hosted)

### 1. Prerequisites
- Python 3.9+
- Active internet connection (for BTC price APIs).

### 2. Setup
```bash
git clone [https://github.com/your-username/EE.git](https://github.com/your-username/EE.git)
cd EE
python -m venv .venv
source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
python app.py

```
App will be available at http://localhost:5000.

## 🧪 "Nostr" & Mobile Laboratory

⚡ Nostr Authentication: The Magic of Amber
₿eesy leverages the power of the Nostr protocol to provide a secure, password-less experience.

Desktop: Use any NIP-07 browser extension (like nos2x or Alby).

Mobile (Amber): On Android, ₿eesy triggers an Android Intent. Amber pops up, you approve the signature, and you are logged in. Your private key never touches our code.

## 🛠️ Roadmap & Contributions

- [ ] Multi-currency support (beyond EUR).
- [ ] Encrypted database export backup.
- [ ] Dashboard with advanced charts (Chart.js).

Building in public 🚀 | Stay humble, stack sats ⚡

## 🇮🇹 Versione Italiana

₿eesy è un laboratorio educativo per tracciare le spese in Euro e visualizzarle in Bitcoin.

Perché usarlo?
- Privacy Totale: I dati restano nel tuo database locale SQLite.

- Bitcoin-First: Gestione corretta di prelievi bancomat, transazioni On-chain e Lightning.

- Login Nostr: Sperimenta il futuro dell'autenticazione decentralizzata.

⚠️ Disclaimer: Questo è un progetto sperimentale. Usalo a tuo rischio e mantieni sempre dei backup dei file .db.

## 🛠️ Roadmap & Contributi
- [ ] Supporto Multi-Valuta (oltre EUR).

- [ ] Export Backup cifrato del database.

- [ ] Dashboard con grafici avanzati (Chart.js).



Stay humble, stack sats. ₿eesy!