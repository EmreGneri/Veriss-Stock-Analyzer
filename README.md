# Veriss Stock Analyzer

Veriss Stock Analyzer is a desktop app that helps you analyze stock data and see what top investors like Warren Buffett are holding. It's simple, clean, and powered by a local AI model (GPT4All).

## What it does

- Shows real-time stock data like price, change, volume, and more
- Uses a local GPT4All model to give simple investment advice (Buy, Hold, or Sell)
- Lets you explore famous investors’ portfolios from Dataroma
- Plots 30-day stock price charts
- Runs on a modern desktop interface built with Tkinter

## Getting started

### 1. Clone the project

```
git clone https://github.com/EmreGneri/Veriss-Stock-Analyzer.git
cd Veriss-Stock-Analyzer
```

### 2. Install the required libraries

```
pip install -r requirements.txt
```

### 3. Add a GPT4All model

- Download a .gguf model from: https://gpt4all.io
  - Suggested models:
    - mistral-7b-openorca.Q4_0.gguf
    - orca-mini-3b-gguf2-q4_0.gguf

- Create a folder named `models` in the project root
- Put your downloaded .gguf file inside that folder

### 4. Run the application

```
python stockanalyzer.py
```

## Example inputs

- Stock symbols: AAPL, MSFT, TSLA
- Investor names: Warren Buffett, Bill Gates, Michael Burry

## Folder structure

```
Veriss-Stock-Analyzer/
├── stockanalyzer.py
├── requirements.txt
├── README.md
└── models/
    └── mistral-7b-openorca.Q4_0.gguf
```

## Notes

- The app can work without a model file, but AI analysis will be disabled
- The AI model runs locally – no internet needed for analysis
- You can package this into a Windows executable using tools like PyInstaller

## License

MIT – Free to use, modify, and share.
