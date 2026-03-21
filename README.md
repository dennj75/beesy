# <strong style="color: #f39c12">₿eesy</strong> - Bitcoin Expense Tracker 🐝⚡

> **"Your Node, Your Rules. Your Data, Your Privacy."**

[![GitHub license](https://img.shields.io/github/license/dennj75/beesy?style=flat-square)](LICENSE)
[![GitHub stars](https://imgpl.io/github/stars/dennj75/beesy?style=flat-square)](https://github.com/dennj75/beesy/stargazers)

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
- ⚡ **Lightning Ready:** Separate management for on-chain and off-chain transactions with Satoshi precision.
- 💱 **Historical Conversion:** Automatic BTC/EUR price retrieval via CoinGecko API.
- 🔐 **Self-Sovereign:** No central server. Install it on your PC, Raspberry Pi, or Umbrel node.
- 📊 **Advanced Analytics:** Real-time visual dashboards for spending and income habits powered by **Chart.js**.
- 📉 **Savings Rate Tracker:** Automatic calculation of your financial efficiency (Saving vs Spending) to help you reach **FIRE** or economic independence.

## 🛡️ Military-Grade Backup System:

- Encrypted Exports: Export your entire history into a .json.enc file.

- AES-256-GCM: Traditional accounts use high-standard encryption derived from your password.

- Self-Sovereign Recovery: Restore your data on any device (PC or Mobile) simply by uploading your backup file.

### 🔧 Plug & Play Auto-Configuration

- No SQL knowledge required! <strong style="color: #f39c12">₿eesy</strong> features a **Plug & Play** system:
  On the first run, the application automatically detects if the database is missing and creates it for you, including all necessary tables for BTC On-chain, Lightning, and EUR transactions.

---

### 🛠️ TechStack

| Component          | Technology                   | Role                                                   |
| :----------------- | :--------------------------- | :----------------------------------------------------- |
| **Backend**        | Flask (Python)               | Server-side logic & API management                     |
| **Frontend**       | HTML, CSS, JS (Vanilla)      | Clean, responsive user interface                       |
| **Data Viz**       | **Chart.js**                 | Interactive bar and doughnut charts for analytics      |
| **Security**       | AES-256-GCM                  | Industry-standard encryption for backups               |
| **Database**       | SQLite                       | Local-first, private data storage                      |
| **API**            | CoinGecko                    | Real-time & historical BTC prices                      |
| **Frontend**       | HTML, CSS, JS (Vanilla)      | Clean, responsive user interface                       |
| **Auth (Desktop)** | Flask-Login + NIP-07         | Traditional or extension-based login                   |
| **Auth (Mobile)**  | **Amber (Nostr Signer)**     | Password-less login via Android Intents                |
| **Cryptography**   | `coincurve` & `pycryptodome` | BIP340/Schnorr signature verification & AES encryption |

## 🚀 Quick Start (Self-Hosted)

### 1. Prerequisites

- Python 3.9+
- Active internet connection (for BTC price APIs).

### 2. Setup

```bash
git clone [https://github.com/dennj75/beesy.git](https://github.com/dennj75/beesy.git)
cd beesy

Create and activate the virtual environment
python -m venv .venv
# Su Windows:
.venv\Scripts\activate
# Su Linux/Mac:
source .venv/bin/activate

Install dependencies and launch
pip install -r requirements.txt
python app.py

```

Access <strong style="color: #f39c12">₿eesy</strong> at http://localhost:5000.

## 🧪 "Nostr" & Mobile Laboratory

⚡ Nostr Authentication: The Magic of Amber
<strong style="color: #f39c12">₿eesy</strong> leverages the power of the Nostr protocol to provide a secure, password-less experience.

Desktop: Use any NIP-07 browser extension (like nos2x or Alby).

Mobile (Amber): On Android, <strong style="color: #f39c12">₿eesy</strong> triggers an Android Intent. Amber pops up, you approve the signature, and you are logged in. Your private key never touches our code.

## 🔏 The "Privacy-First" Laboratory

🛡️ Backup & Restore (New!)
We implemented a robust backup system to ensure you never lose your data:

- Traditional Users: Your backup is encrypted using a Master Key derived from your password. Even if someone steals your backup file, they cannot read it without your Beesy password.
- Nostr Users: Quick JSON export/import for seamless identity portability.
  -Mobile Ready: Restore your history directly from your smartphone browser with 100% success rate on traditional accounts.

## 🛠️ Roadmap & Contributions

- [x] Encrypted database export/backup. (Done! 🎉)
- [x] Advanced Dashboard: Real-time charts for spending habits (Chart.js). 📊
- [x] PDF Reporting system (Browser-based export). 📄
- [ ] Multi-currency support: Beyond EUR (USD, CHF, etc.).
- [ ] Detailed transaction history view within the Analytics page.
- [ ] Mobile Nostr Restore: Refined integration with Nostr Signer apps.
      
## 💜 Connect on Nostr

Se vuoi seguire lo sviluppo o metterti in contatto in modo decentralizzato:

- **Developer (@Dennj75):** [dennj75@nostr.red](https://primal.net/p/npub1lejpu7ms5j6y7srv32ndxw4m9j5vp7tgdjpsxw32h3r2y7zpqtdsdumyk0) 
  - `npub1lejpu7ms5j6y7srv32ndxw4m9j5vp7tgdjpsxw32h3r2y7zpqtdsdumyk0`
- **Beesy Project:** [beesy@nostrcheck.me](https://primal.net/p/npub1k8dfux202k788vm955rn4wrckvavuxxr3202wlpsa2h97d4tlkrsp57qcv)
  - `npub1k8dfux202k788vm955rn4wrckvavuxxr3202wlpsa2h97d4tlkrsp57qcv`

---

## 🇮🇹 Versione Italiana

<strong style="color: #f39c12">₿eesy</strong> è un tracker di spese "Bitcoin-first" progettato per la privacy totale.
<strong style="color: #f39c12">₿eesy</strong> è un tracker di spese "Bitcoin-first" progettato per la privacy totale.

- **Analytics Avanzate:** Grafici interattivi per monitorare entrate, uscite e tasso di risparmio.
- **Backup Cifrato:** Esporta i tuoi dati in formato AES-256 sicuro.
- **Senza Password:** Prova il login Nostr tramite estensioni browser o Amber su Android.

- **Ripristino Mobile:** Funzionante al 100% per account tradizionali.

- **Senza Password:** Prova il login Nostr tramite estensioni browser o Amber su Android.

---

| <strong style="color: #f39c12">₿eesy</strong> | Building in public 🚀 | Stay humble, stack sats ⚡
