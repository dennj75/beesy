# EE - Bitcoin & Euro Expense Tracker

A personal finance tracker built specifically for Bitcoiners. Track your expenses in EUR while automatically calculating Bitcoin (BTC) equivalents, including Lightning Network and on-chain transactions.

## 🌟 Why EE?

Most expense trackers treat Bitcoin as just another "crypto asset". EE is different:

- **Native Lightning Network support** - Track your Lightning transactions separately
- **On-chain transaction tracking** - Full support for regular Bitcoin transactions
- **Automatic BTC/EUR conversion** - Uses historical BTC prices for accurate tracking
- **Privacy-first** - Your data stays local, SQLite database on your machine
- **Open Source** - Built in public, contributions welcome

## ✨ Features

- 📊 **Multi-currency tracking**: EUR, Bitcoin (on-chain), Lightning Network (satoshis)
- 🏷️ **Detailed categorization**: 10+ categories with custom subcategories
- 💱 **Automatic BTC conversion**: Fetches historical BTC prices via CoinGecko API
- 📈 **Balance tracking**: Real-time balance in EUR, BTC, and satoshis
- 📤 **CSV Export**: Export transactions by month or all-time
- 🌐 **Web Interface**: Clean Flask-based UI (plus CLI for power users)
- 🔐 **Local-first**: Your financial data never leaves your computer

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- pip

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/EE.git
cd EE
```

2. Create virtual environment:

```bash
python -m venv .venv
```

3. Activate virtual environment:

- Windows: `.venv\Scripts\activate`
- Linux/Mac: `source .venv/bin/activate`

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Run the web app:

```bash
python app.py
```

6. Open browser at `http://127.0.0.1:5000`

### CLI Usage

For command-line interface:

```bash
python main.py
```

## 📸 Screenshots

_Coming soon - adding screenshots of the web interface_

## 🗂️ Project Structure

```
EE/
├── app.py              # Flask web application
├── main.py             # CLI interface
├── cli.py              # CLI utilities
├── requirements.txt    # Python dependencies
├── db/                 # Database utilities
│   └── db_utils.py    # DB functions
├── utils/             # Helper modules
│   ├── crypto.py      # BTC price fetching & conversion
│   ├── export.py      # CSV export functions
│   └── helpers.py     # General utilities
├── templates/         # HTML templates
└── static/           # CSS, JS, images
```

## 🛠️ Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLite
- **API**: CoinGecko (BTC prices)
- **Frontend**: HTML, CSS, JavaScript (Vanilla)

## 📝 Usage Examples

### Adding a Transaction (Web)

1. Navigate to "Nuova Transazione"
2. Select date, category, amount in EUR
3. Automatic BTC conversion happens based on historical price

### Adding Lightning Transaction

1. Go to "Transazioni Lightning"
2. Enter amount in satoshis
3. System calculates EUR equivalent

### Exporting Data

- Export all transactions: `/scarica-csv`
- Export by month: `/scarica-csv-mese` (format: YYYY-MM)

## 🎯 Roadmap

- [ ] Multi-user support with authentication
- [ ] Cloud deployment option
- [ ] Mobile-responsive design improvements
- [ ] Tax report generation for crypto transactions
- [ ] Budget planning & forecasting
- [ ] Recurring transaction support
- [ ] Charts & analytics dashboard
- [ ] Integration with wallet APIs (auto-import)

## 🤝 Contributing

This is a learning project built in public! Contributions, issues, and feature requests are welcome.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- CoinGecko API for BTC price data
- Flask framework
- The Bitcoin community

## 📧 Contact

Building in public - follow the journey!

---

**Note**: This is an early-stage project. Use at your own risk. Always backup your `transazioni.db` file regularly.
