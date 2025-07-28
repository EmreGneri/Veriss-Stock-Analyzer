# 🚀 Veriss Stock Analyzer

**AI-Powered Stock Analysis Desktop App**

A modern GUI application that allows users to analyze stocks, track investor portfolios (like Warren Buffett), and get investment recommendations using an embedded local LLM (GPT4All).

## ✨ Features

- 📈 Real-time stock data from Yahoo Finance
- 🤖 Local AI-based investment analysis using GPT4All
- 💼 Analyze famous investor portfolios from Dataroma
- 📊 Interactive stock price chart (last 30 days)
- 🖥️ Beautiful modern interface with Tkinter

---

## 🔧 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/EmreGneri/Veriss-Stock-Analyzer.git
cd Veriss-Stock-Analyzer
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Download GPT4All Model

- Visit: https://gpt4all.io/index.html
- Download a `.gguf` model (e.g., `mistral-7b-openorca.Q4_0.gguf` or `orca-mini-3b-gguf2-q4_0.gguf`)
- Place the model file inside a folder named `models/` next to the `.py` file

### 4. Run the App

```bash
python stockanalyzer.py
```

---

## 💡 Example Inputs

- Stock symbols: `AAPL`, `MSFT`, `TSLA`
- Investor names: `Warren Buffett`, `Bill Gates`, `Ray Dalio`

---

## 📁 Folder Structure

```
Veriss-Stock-Analyzer/
├── stockanalyzer.py
├── requirements.txt
├── README.md
└── models/
    └── mistral-7b-openorca.Q4_0.gguf  # or any other GPT4All model
```

---

## ❗ Notes

- AI model is optional: if no `.gguf` is found, app falls back to basic analysis
- No data is sent online; LLM runs locally
- Windows `.exe` support via PyInstaller is possible

---

## 📜 License

MIT License – free to use, modify, and distribute.
