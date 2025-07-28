import sys
import os
from gpt4all import GPT4All
import requests
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import threading
import yfinance as yf
from bs4 import BeautifulSoup
import time
import logging

# EXE için özel yol ayarları
def get_base_path():
    """EXE ve normal çalıştırma için uygun base path döndür"""
    if getattr(sys, 'frozen', False):
        # PyInstaller ile derlenmiş .exe dosyası
        return os.path.dirname(sys.executable)
    else:
        # Normal Python scripti
        return os.path.dirname(os.path.abspath(__file__))

def get_temp_path():
    """Geçici dosyalar için güvenli path"""
    if getattr(sys, 'frozen', False):
        # EXE modunda sistem temp klasörünü kullan
        return os.path.join(os.environ.get('TEMP', os.path.expanduser('~')), 'VerissStockAnalyzer')
    else:
        return os.path.join(get_base_path(), 'temp')

# Log dosyası için güvenli yol
log_path = os.path.join(get_temp_path(), "stock_analyzer.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def resolve_name_to_dataroma_code(name):
    name = name.strip().lower()
    name_map = {
        "warren buffett": "BRK",
        "bill gates": "GFT",
        "bill ackman": "psc",
        "charlie munger": "DJCO",
        "michael burry": "SAM",
        "ray dalio": "BRIDGE",
        "joel greenblatt": "GOTHAM",
        "tiger global": "TGM",
        "jeff bezos": "AMZN",
        "david einhorn": "GLRE",
        "seth klarman": "BAUPOST",
        "leon cooperman": "oa",
        "carl icahn": "ic",
        "david tepper": "AM",
        "bill miller": "LMM",
        "chuck akre": "AC",
        "mohnish pabrai": "PI",
        "guy spier": "aq",
        "li lu": "HC",
        "prem watsa": "FFH",
        "francis chou": "ca",
        "thomas russo": "GR",
        "mason hawkins": "LLPFX",
        "chase coleman": "TGM",
        "lee ainslie": "mc",
        "daniel loeb": "tp",
        "david abrams": "abc",
        "bruce berkowitz": "fairx",
        "glenn greenberg": "CCM",
        "pat dorsey": "DA",
        "christopher davis": "DAV",
        "john rogers": "CAAPX",
        "bill nygren": "oaklx",
        "dodge cox": "DODGX",
        "third avenue": "TA",
        "first eagle": "FE",
    }
    return name_map.get(name)

def get_dataroma_portfolio(investor_code):
    if not investor_code:
        return []

    url = f"https://www.dataroma.com/m/holdings.php?m={investor_code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,/;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        logging.debug(f"Fetching portfolio for: {investor_code}")
        time.sleep(2)
        session = requests.Session()
        session.headers.update(headers)
        response = session.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        stock_links = soup.find_all("a", href=lambda x: x and "/m/stock.php?sym=" in str(x))
        if stock_links:
            tickers = []
            for link in stock_links:
                href = link.get("href", "")
                if "sym=" in href:
                    ticker = href.split("sym=")[1]
                    if "&" in ticker:
                        ticker = ticker.split("&")[0]
                    ticker = ticker.strip().upper()
                    if ticker and len(ticker) <= 6 and ticker not in tickers:
                        tickers.append(ticker)
            return tickers[:15]
        return []

    except Exception as e:
        logging.error(f"Error scraping Dataroma: {e}")
        return []

def get_buffett_top_holdings_data():
    tickers = get_dataroma_portfolio("BRK") or [
        "AAPL", "AXP", "BAC", "KO", "CVX", "OXY", "MCO", "KHC", "CB", "DVA", "V", "AMZN"
    ]
    data = []
    for ticker in tickers[:15]:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            hist = stock.history(period="2d")
            price = info.get("currentPrice", hist["Close"].iloc[-1] if not hist.empty else None)
            price_str = f"${price:.2f}" if price else "N/A"
            pe_ratio = info.get("trailingPE", info.get("forwardPE"))
            pe_str = f"{pe_ratio:.2f}" if pe_ratio and pe_ratio > 0 else "N/A"
            market_cap = info.get("marketCap")
            cap_str = f"${market_cap/1e9:.2f}B" if market_cap and market_cap >= 1e9 else "N/A"
            company_name = info.get("shortName", ticker)[:20]
            data.append([ticker, company_name, price_str, pe_str, cap_str])
        except Exception as e:
            data.append([ticker, "Error", "N/A", "N/A", "N/A"])
    return data

class ModernStockAnalyzer:
    def __init__(self):
        self.base_path = get_base_path()
        self.temp_path = get_temp_path()
        os.makedirs(self.temp_path, exist_ok=True)
        
        self.setup_model_path()
        self.model = None
        self.model_loading = False
        self.setup_modern_ui()
        self.load_model()

    def setup_model_path(self):
        """EXE uyumlu model yolu belirleme"""
        possible_paths = [
            # EXE ile aynı klasördeki models klasörü
            os.path.join(self.base_path, "models", "orca-mini-3b-gguf2-q4_0.gguf"),
            os.path.join(self.base_path, "models", "mistral-7b-openorca.Q4_0.gguf"),
            os.path.join(self.base_path, "models", "nous-hermes-llama2-13b.Q4_0.gguf"),
            
            # EXE ile aynı klasör
            os.path.join(self.base_path, "orca-mini-3b-gguf2-q4_0.gguf"),
            os.path.join(self.base_path, "mistral-7b-openorca.Q4_0.gguf"),
            os.path.join(self.base_path, "nous-hermes-llama2-13b.Q4_0.gguf"),
            
            # Kullanıcı belgeler klasörü
            os.path.join(os.path.expanduser("~"), "Documents", "VerissModels", "orca-mini-3b-gguf2-q4_0.gguf"),
            os.path.join(os.path.expanduser("~"), "Documents", "VerissModels", "mistral-7b-openorca.Q4_0.gguf"),
            
            # GPT4All varsayılan konumlar
            os.path.join(os.path.expanduser("~"), ".cache", "gpt4all", "orca-mini-3b-gguf2-q4_0.gguf"),
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "nomic.ai", "GPT4All", "orca-mini-3b-gguf2-q4_0.gguf"),
            
            # Original path (development)
            r"C:\Users\lenovo\build\gpt4all\gpt4all-bindings\python\orca-mini-3b-gguf2-q4_0.gguf",
        ]
        
        self.model_path = None
        for path in possible_paths:
            if os.path.exists(path):
                self.model_path = path
                print(f"✅ Model found: {path}")
                logging.info(f"Model found: {path}")
                return
        
        print("❌ Model file not found!")
        logging.warning("No model file found in any of the expected locations")

    def load_model(self):
        if self.model_loading:
            return
            
        self.model_loading = True
        
        def load_in_background():
            try:
                if not self.model_path:
                    self.window.after(0, lambda: self.handle_model_not_found())
                    return
                
                print(f"🔄 Loading model: {self.model_path}")
                logging.info(f"Starting model load: {self.model_path}")
                self.window.after(0, lambda: self.update_status("🔄 Loading AI Model...", "#FFA502"))
                
                # Model yükleme denemeleri
                try:
                    # İlk deneme: Doğrudan path ile
                    self.model = GPT4All(self.model_path, allow_download=False, device='cpu')
                    logging.info("Model loaded successfully with direct path")
                except Exception as e1:
                    print(f"First attempt failed: {e1}")
                    logging.warning(f"First load attempt failed: {e1}")
                    try:
                        # İkinci deneme: Model adı ve klasör ile
                        model_name = os.path.basename(self.model_path)
                        model_dir = os.path.dirname(self.model_path)
                        self.model = GPT4All(model_name, model_path=model_dir, allow_download=False, device='cpu')
                        logging.info("Model loaded successfully with name and directory")
                    except Exception as e2:
                        print(f"Second attempt failed: {e2}")
                        logging.warning(f"Second load attempt failed: {e2}")
                        try:
                            # Üçüncü deneme: Temp klasöre kopyala ve yükle
                            temp_model_path = os.path.join(self.temp_path, os.path.basename(self.model_path))
                            if not os.path.exists(temp_model_path):
                                import shutil
                                print("Copying model to temp directory...")
                                shutil.copy2(self.model_path, temp_model_path)
                            
                            self.model = GPT4All(temp_model_path, allow_download=False, device='cpu')
                            logging.info("Model loaded successfully from temp directory")
                        except Exception as e3:
                            print(f"Third attempt failed: {e3}")
                            logging.error(f"All model load attempts failed: {e3}")
                            raise e3
                
                # Model test
                print("🧪 Testing model...")
                test_response = self.model.generate("Test", max_tokens=5, temp=0.1)
                print(f"✅ Model test successful: {test_response}")
                logging.info(f"Model test successful: {test_response}")
                
                self.window.after(0, lambda: self.update_status("✅ AI Model Ready!", "#00D084"))
                self.window.after(0, lambda: self.show_model_ready_message())
                
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Model loading error: {error_msg}")
                logging.error(f"Model loading error: {error_msg}")
                self.window.after(0, lambda: self.update_status("❌ AI Model Error", "#FF4757"))
                self.window.after(0, lambda: self.show_model_error(error_msg))
            finally:
                self.model_loading = False

        threading.Thread(target=load_in_background, daemon=True).start()

    def handle_model_not_found(self):
        self.update_status("❌ Model Not Found", "#FF4757")
        
        # EXE için özel yönergeler
        exe_path = self.base_path if getattr(sys, 'frozen', False) else "script directory"
        
        msg = f"""🤖 GPT4All Model Required!

Model file not found. For EXE version, please follow these steps:

1️⃣ Download a model from https://gpt4all.io/index.html
2️⃣ Create a 'models' folder next to the EXE file
3️⃣ Place the .gguf file in the models folder

📁 Recommended locations:
• {exe_path}\\models\\model_name.gguf
• {os.path.expanduser('~')}\\Documents\\VerissModels\\model_name.gguf

🔥 Popular models:
• mistral-7b-openorca.Q4_0.gguf (7GB) - RECOMMENDED
• orca-mini-3b-gguf2-q4_0.gguf (2GB) - Faster
• nous-hermes-llama2-13b.Q4_0.gguf (7GB) - Advanced

⚡ The app will work without a model but AI analysis won't be available!
📊 Basic stock data and portfolio tracking still works perfectly!"""
        
        messagebox.showinfo("AI Model Required", msg)

    def show_model_error(self, error_msg):
        msg = f"""🚫 AI Model Loading Error!

Error: {error_msg}

🔧 EXE-specific solutions:
1️⃣ Make sure the model file is in 'models' folder next to EXE
2️⃣ Check file permissions (right-click → Properties → Security)
3️⃣ Run EXE as Administrator
4️⃣ Disable antivirus temporarily during first run
5️⃣ Try a different model file
6️⃣ Make sure path has no special characters

📁 Expected structure:
YourApp.exe
└── models/
    └── model_name.gguf

💡 Basic analysis is still available without the model!"""
        
        messagebox.showerror("Model Error", msg)

    def show_model_ready_message(self):
        current_text = self.result_text.get(1.0, tk.END)
        if "🤖 AI Status:" in current_text:
            lines = current_text.split('\n')
            for i, line in enumerate(lines):
                if "🤖 AI Status:" in line:
                    lines[i] = "🤖 AI Status: ✅ Model ready - You can now use AI analysis!"
                    break
            
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(1.0, '\n'.join(lines))

    def setup_modern_ui(self):
        self.window = tk.Tk()
        self.window.title("🚀 Veriss Stock Analyzer - AI Powered (EXE Version)")
        self.window.geometry("1400x800")
        self.window.configure(bg="#0F0F23")
        self.window.resizable(True, True)
        
        self.colors = {
            'bg_primary': '#0F0F23',
            'bg_secondary': '#1A1A3E',
            'bg_card': '#242450',
            'accent': '#00D084',
            'accent_hover': '#00B86B',
            'text_primary': '#FFFFFF',
            'text_secondary': '#A0A0A0',
            'danger': '#FF4757',
            'warning': '#FFA502',
            'info': '#3742FA'
        }
        
        # İkon yükleme - EXE uyumlu
        try:
            icon_path = os.path.join(self.base_path, "icon.ico")
            if os.path.exists(icon_path):
                self.window.iconbitmap(default=icon_path)
        except:
            pass

        main_container = tk.Frame(self.window, bg=self.colors['bg_primary'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.create_header(main_container)
        
        content_frame = tk.Frame(main_container, bg=self.colors['bg_primary'])
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))
        
        self.create_left_panel(content_frame)
        self.create_right_panel(content_frame)

    def create_header(self, parent):
        header_frame = tk.Frame(parent, bg=self.colors['bg_secondary'], height=80)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        header_frame.pack_propagate(False)
        
        title_frame = tk.Frame(header_frame, bg=self.colors['bg_secondary'])
        title_frame.pack(expand=True, fill=tk.BOTH)
        
        # EXE version indicator
        exe_indicator = " (EXE)" if getattr(sys, 'frozen', False) else " (DEV)"
        
        title_label = tk.Label(
            title_frame,
            text=f"🚀 Veriss Stock Analyzer{exe_indicator}",
            font=("Segoe UI", 24, "bold"),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary']
        )
        title_label.pack(side=tk.LEFT, padx=20, pady=20)
        
        subtitle_label = tk.Label(
            title_frame,
            text="🤖 Powered by GPT4All AI • 📊 Real-time Data • 💼 Professional Analysis",
            font=("Segoe UI", 10),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_secondary']
        )
        subtitle_label.pack(side=tk.LEFT, padx=(0, 20), pady=(30, 10))
        
        self.status_frame = tk.Frame(header_frame, bg=self.colors['bg_secondary'])
        self.status_frame.pack(side=tk.RIGHT, padx=20, pady=20)
        
        self.status_label = tk.Label(
            self.status_frame,
            text="🔄 Loading AI Model...",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors['bg_secondary'],
            fg=self.colors['warning']
        )
        self.status_label.pack()

    def create_left_panel(self, parent):
        left_panel = tk.Frame(parent, bg=self.colors['bg_primary'])
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 20))
        
        input_card = tk.Frame(left_panel, bg=self.colors['bg_card'], relief="flat", bd=0)
        input_card.pack(fill=tk.X, pady=(0, 20))
        
        input_header = tk.Frame(input_card, bg=self.colors['bg_card'])
        input_header.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        tk.Label(
            input_header,
            text="📊 AI Stock Analysis",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors['bg_card'],
            fg=self.colors['text_primary']
        ).pack(side=tk.LEFT)
        
        input_area = tk.Frame(input_card, bg=self.colors['bg_card'])
        input_area.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        tk.Label(
            input_area,
            text="Enter Stock Symbol or Investor Name:",
            font=("Segoe UI", 12),
            bg=self.colors['bg_card'],
            fg=self.colors['text_secondary']
        ).pack(anchor=tk.W, pady=(0, 8))
        
        input_frame = tk.Frame(input_area, bg=self.colors['bg_card'])
        input_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.entry_symbol = tk.Entry(
            input_frame,
            font=("Segoe UI", 14),
            bg=self.colors['bg_primary'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['accent'],
            relief="flat",
            bd=0,
            width=40
        )
        self.entry_symbol.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=12)
        self.entry_symbol.bind("<Return>", lambda e: self.analyze_stock())
        
        button_frame = tk.Frame(input_frame, bg=self.colors['bg_card'])
        button_frame.pack(side=tk.RIGHT)
        
        self.btn_analyze = tk.Button(
            button_frame,
            text="🤖 AI ANALYZE",
            command=self.analyze_stock,
            font=("Segoe UI", 12, "bold"),
            bg=self.colors['accent'],
            fg="white",
            relief="flat",
            bd=0,
            padx=25,
            pady=12,
            cursor="hand2"
        )
        self.btn_analyze.pack(side=tk.LEFT, padx=(0, 10))
        
        self.btn_plot = tk.Button(
            button_frame,
            text="📈 CHART",
            command=lambda: self.plot_stock_price(self.entry_symbol.get().strip()),
            font=("Segoe UI", 10, "bold"),
            bg=self.colors['info'],
            fg="white",
            relief="flat",
            bd=0,
            padx=20,
            pady=12,
            cursor="hand2"
        )
        self.btn_plot.pack(side=tk.LEFT)
        
        examples_label = tk.Label(
            input_area,
            text="💡 Examples: AAPL, TSLA, MSFT, Warren Buffett, Bill Gates, Ray Dalio",
            font=("Segoe UI", 9),
            bg=self.colors['bg_card'],
            fg=self.colors['text_secondary']
        )
        examples_label.pack(anchor=tk.W)
        
        results_card = tk.Frame(left_panel, bg=self.colors['bg_card'], relief="flat", bd=0)
        results_card.pack(fill=tk.BOTH, expand=True)
        
        results_header = tk.Frame(results_card, bg=self.colors['bg_card'])
        results_header.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        tk.Label(
            results_header,
            text="🤖 AI Analysis Results",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors['bg_card'],
            fg=self.colors['text_primary']
        ).pack(side=tk.LEFT)
        
        results_frame = tk.Frame(results_card, bg=self.colors['bg_card'])
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.result_text = scrolledtext.ScrolledText(
            results_frame,
            wrap=tk.WORD,
            font=("Cascadia Code", 10),
            bg=self.colors['bg_primary'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['accent'],
            relief="flat",
            bd=0,
            selectbackground=self.colors['accent'],
            selectforeground="white"
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        
        # EXE version için özel welcome mesajı
        version_info = "EXE Version" if getattr(sys, 'frozen', False) else "Development Version"
        model_status = f"Model Path: {self.model_path}" if self.model_path else "Model: Not Found"
        
        welcome_msg = f"""🎯 Welcome to Veriss Stock Analyzer! ({version_info})

✨ FEATURES:
• 🤖 Advanced AI-powered stock analysis
• 📊 Real-time investor portfolio tracking  
• 💼 Berkshire Hathaway holdings monitoring
• 🌐 Live market data integration
• 📈 Interactive price charts

🚀 HOW TO USE:
1. Enter stock symbol (AAPL, GOOGL, TSLA, etc.)
2. Or enter famous investor name (Warren Buffett, Bill Gates, etc.)  
3. Click 'AI ANALYZE' for AI-powered investment advice
4. Use 'CHART' to visualize price trends
5. Check Buffett's holdings on the right panel →

🤖 AI Status: {model_status}
⚡ Pro Tip: Try "Warren Buffett" for full portfolio analysis!

{'─' * 80}
"""
        self.result_text.insert(tk.END, welcome_msg)

    def create_right_panel(self, parent):
        right_panel = tk.Frame(parent, bg=self.colors['bg_primary'], width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)
        
        holdings_card = tk.Frame(right_panel, bg=self.colors['bg_card'], relief="flat", bd=0)
        holdings_card.pack(fill=tk.BOTH, expand=True)
        
        holdings_header = tk.Frame(holdings_card, bg=self.colors['bg_card'])
        holdings_header.pack(fill=tk.X, padx=20, pady=(20, 15))
        
        tk.Label(
            holdings_header,
            text="💼 Sample Portfolio",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors['bg_card'],
            fg=self.colors['text_primary']
        ).pack(side=tk.LEFT)
        
        self.btn_refresh = tk.Button(
            holdings_header,
            text="🔄",
            command=self.refresh_buffett_data,
            font=("Segoe UI", 12),
            bg=self.colors['accent'],
            fg="white",
            relief="flat",
            bd=0,
            width=3,
            height=1,
            cursor="hand2"
        )
        self.btn_refresh.pack(side=tk.RIGHT)
        
        table_frame = tk.Frame(holdings_card, bg=self.colors['bg_card'])
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Modern.Treeview",
                       background=self.colors['bg_primary'],
                       foreground=self.colors['text_primary'],
                       fieldbackground=self.colors['bg_primary'],
                       borderwidth=0,
                       font=("Segoe UI", 10))
        style.configure("Modern.Treeview.Heading",
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['text_primary'],
                       font=("Segoe UI", 10, "bold"))
        
        columns = ("Symbol", "Company", "Price", "P/E", "Cap")
        self.buffett_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style="Modern.Treeview"
        )
        
        column_widths = {"Symbol": 60, "Company": 120, "Price": 70, "P/E": 50, "Cap": 70}
        for col in columns:
            self.buffett_tree.heading(col, text=col)
            self.buffett_tree.column(col, anchor="center", width=column_widths.get(col, 80))
       
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.buffett_tree.yview)
        self.buffett_tree.configure(yscrollcommand=scrollbar.set)
        
        self.buffett_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.btn_analyze_buffett = tk.Button(
            holdings_card,
            text="🎯 Analyze Selected Stock",
            command=self.analyze_selected_buffett_stock,
            font=("Segoe UI", 11, "bold"),
            bg=self.colors['info'],
            fg="white",
            relief="flat",
            bd=0,
            padx=20,
            pady=12,
            cursor="hand2"
        )
        self.btn_analyze_buffett.pack(pady=(0, 20))
        
        self.load_buffett_data()

    def update_status(self, text, color):
        self.status_label.config(text=text, fg=color)

    def load_buffett_data(self):
        def load_data():
            try:
                self.window.after(0, lambda: self.update_status("🔄 Loading Holdings...", self.colors['warning']))
                holdings = get_buffett_top_holdings_data()

                def clear_and_populate():
                    for item in self.buffett_tree.get_children():
                        self.buffett_tree.delete(item)
                    for row in holdings:
                        self.buffett_tree.insert("", tk.END, values=row)

                self.window.after(0, clear_and_populate)
                self.window.after(0, lambda: self.update_status("✅ Holdings Loaded", self.colors['accent']))
            except Exception as e:
                self.window.after(0, lambda: self.update_status("❌ Loading Failed", self.colors['danger']))

        threading.Thread(target=load_data, daemon=True).start()

    def refresh_buffett_data(self):
        self.btn_refresh.config(state="disabled", text="⏳")
        
        def refresh():
            try:
                self.load_buffett_data()
                time.sleep(2)
                self.window.after(0, lambda: self.btn_refresh.config(state="normal", text="🔄"))
            except:
                self.window.after(0, lambda: self.btn_refresh.config(state="normal", text="🔄"))

        threading.Thread(target=refresh, daemon=True).start()

    def analyze_selected_buffett_stock(self):
        selection = self.buffett_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a stock from Buffett's portfolio!")
            return
        item = self.buffett_tree.item(selection[0])
        ticker = item["values"][0]
        self.entry_symbol.delete(0, tk.END)
        self.entry_symbol.insert(0, ticker)
        self.analyze_stock()

    def analyze_stock(self):
        symbol = self.entry_symbol.get().strip()
        if not symbol:
            messagebox.showwarning("Warning", "Please enter a stock symbol or investor name!")
            return
        
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "🔄 Analyzing... Please wait...\n")
        self.result_text.update()
        
        self.btn_analyze.config(state="disabled", text="⏳ ANALYZING...")
        
        def analyze_in_background():
            try:
                investor_code = resolve_name_to_dataroma_code(symbol)
                
                if investor_code:
                    self.analyze_investor_portfolio(symbol, investor_code)
                else:
                    self.analyze_single_stock(symbol.upper())
                    
            except Exception as e:
                logging.error(f"Error in analyze_stock: {e}")
                self.window.after(0, lambda: self.display_error(f"Analysis failed: {str(e)}"))
            finally:
                self.window.after(0, lambda: self.btn_analyze.config(state="normal", text="🤖 AI ANALYZE"))
        
        threading.Thread(target=analyze_in_background, daemon=True).start()

    def analyze_single_stock(self, symbol):
        try:
            stock_data = self.get_stock_data(symbol)
            if "error" in stock_data:
                self.window.after(0, lambda: self.display_error(f"Could not get data for {symbol}: {stock_data['error']}"))
                return
                
            company_info = self.get_company_info(symbol)
            
            if self.model:
                analysis = self.create_ai_analysis(symbol, stock_data, company_info)
            else:
                analysis = "⚠️ AI model not loaded. Showing basic data only.\n\n" + self.create_basic_analysis(symbol, stock_data, company_info)
      
            self.window.after(0, lambda: self.display_stock_analysis(symbol, stock_data, company_info, analysis))
            
        except Exception as e:
            logging.error(f"Error analyzing single stock {symbol}: {e}")
            self.window.after(0, lambda: self.display_error(f"{symbol} analysis failed: {str(e)}"))

    def analyze_investor_portfolio(self, investor_name, investor_code):
        try:
            tickers = get_dataroma_portfolio(investor_code)
            if not tickers:
                self.window.after(0, lambda: self.display_error(f"Portfolio not found for {investor_name}"))
                return
            
            portfolio_text = f"📊 PORTFOLIO ANALYSIS: {investor_name.upper()}\n"
            portfolio_text += "=" * 60 + "\n\n"
            portfolio_text += f"Found {len(tickers)} holdings:\n\n"
            
            for i, ticker in enumerate(tickers[:10], 1): 
                try:
                    stock_data = self.get_stock_data(ticker)
                    if "error" not in stock_data:
                        change = ((stock_data['c'] - stock_data['pc']) / stock_data['pc']) * 100
                        portfolio_text += f"{i:2d}. {ticker:5s} - ${stock_data['c']:.2f} ({change:+.1f}%)\n"
                    else:
                        portfolio_text += f"{i:2d}. {ticker:5s} - Data not available\n"
                except:
                    portfolio_text += f"{i:2d}. {ticker:5s} - Data fetch error\n"
            
            portfolio_text += f"\n💡 This portfolio belongs to the famous investor {investor_name}.\n"
            portfolio_text += "Click on one of the stocks above for detailed AI analysis."
            
            self.window.after(0, lambda: self.display_portfolio_analysis(portfolio_text))
            
        except Exception as e:
            logging.error(f"Error analyzing investor portfolio: {e}")
            self.window.after(0, lambda: self.display_error(f"{investor_name} portfolio analysis failed: {str(e)}"))

    def create_basic_analysis(self, symbol, stock_data, company_info):
        """AI olmadan temel analiz"""
        current_price = stock_data["c"]
        previous_close = stock_data["pc"]
        daily_change = current_price - previous_close
        daily_change_percent = (daily_change / previous_close) * 100
        
        analysis = "📈 BASIC TECHNICAL ANALYSIS:\n"
        analysis += "-" * 30 + "\n\n"
        
        # Fiyat analizi
        if daily_change_percent > 5:
            analysis += "🟢 Strong upward momentum (+5% or more)\n"
        elif daily_change_percent > 2:
            analysis += "🟡 Moderate upward trend (+2% to +5%)\n"
        elif daily_change_percent > 0:
            analysis += "🟢 Slight positive movement\n"
        elif daily_change_percent > -2:
            analysis += "🟡 Minor decline (less than -2%)\n"
        elif daily_change_percent > -5:
            analysis += "🟠 Moderate decline (-2% to -5%)\n"
        else:
            analysis += "🔴 Significant decline (more than -5%)\n"
        
        # Volatilite analizi
        day_range = stock_data['h'] - stock_data['l']
        range_percent = (day_range / current_price) * 100
        
        analysis += f"\n📊 Volatility: {range_percent:.1f}% intraday range\n"
        if range_percent > 5:
            analysis += "High volatility - Risky for short term\n"
        elif range_percent > 2:
            analysis += "Moderate volatility - Normal trading\n"
        else:
            analysis += "Low volatility - Stable trading\n"
        
        # Basit öneri
        analysis += "\n💡 BASIC RECOMMENDATION:\n"
        if daily_change_percent > 3:
            analysis += "⚠️ Consider taking profits if you own shares\n"
        elif daily_change_percent < -3:
            analysis += "🔍 May be a buying opportunity if fundamentals are strong\n"
        else:
            analysis += "📊 Normal trading - Monitor for trends\n"
        
        analysis += "\n⚠️ Note: This is basic technical analysis only.\n"
        analysis += "For detailed AI-powered fundamental analysis, please load an AI model."
        
        return analysis

    def display_stock_analysis(self, symbol, stock_data, company_info, analysis):
        self.result_text.delete(1.0, tk.END)
        
        result = f"🎯 STOCK ANALYSIS: {symbol}\n"
        result += "=" * 50 + "\n\n"
        
        result += f"📋 COMPANY INFORMATION:\n"
        result += f"Name: {company_info.get('name', 'Unknown')}\n"
        result += f"Sector: {company_info.get('sector', 'Unknown')}\n"
        result += f"Industry: {company_info.get('industry', 'Unknown')}\n"
        result += f"Country: {company_info.get('country', 'Unknown')}\n\n"
        
        result += f"💰 PRICE DATA:\n"
        result += f"Current Price: ${stock_data['c']:.2f}\n"
        result += f"Previous Close: ${stock_data['pc']:.2f}\n"
        daily_change = stock_data['c'] - stock_data['pc']
        daily_change_percent = (daily_change / stock_data['pc']) * 100
        result += f"Daily Change: ${daily_change:.2f} ({daily_change_percent:+.2f}%)\n"
        result += f"Day High: ${stock_data['h']:.2f}\n"
        result += f"Day Low: ${stock_data['l']:.2f}\n\n"
        
        if company_info.get('marketCap'):
            market_cap = company_info['marketCap']
            if market_cap >= 1e9:
                result += f"Market Cap: ${market_cap/1e9:.2f}B\n\n"
            elif market_cap >= 1e6:
                result += f"Market Cap: ${market_cap/1e6:.2f}M\n\n"
        
        result += f"🤖 ANALYSIS:\n"
        result += "=" * 30 + "\n"
        result += analysis + "\n\n"
        
        result += f"⚡ Analysis completed: {time.strftime('%H:%M:%S')}\n"
        result += "📈 Use CHART button to see price trends!"
        
        self.result_text.insert(tk.END, result)

    def display_portfolio_analysis(self, portfolio_text):
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, portfolio_text)

    def display_error(self, error_message):
        self.result_text.delete(1.0, tk.END)
        error_text = f"❌ ERROR\n"
        error_text += "=" * 30 + "\n\n"
        error_text += f"{error_message}\n\n"
        error_text += "💡 TROUBLESHOOTING:\n"
        error_text += "• Check your internet connection\n"
        error_text += "• Verify the stock symbol is correct\n"
        error_text += "• Try a different symbol\n"
        error_text += "• Wait a moment and try again\n"
        
        if getattr(sys, 'frozen', False):
            error_text += "\n🔧 EXE-specific tips:\n"
            error_text += "• Run as Administrator\n"
            error_text += "• Check Windows Firewall settings\n"
            error_text += "• Temporarily disable antivirus\n"
        
        self.result_text.insert(tk.END, error_text)

    def get_stock_data(self, symbol):
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="2d")
            if hist.empty:
                return {"error": "Data not available"}
            return {
                "c": hist["Close"].iloc[-1],
                "pc": hist["Close"].iloc[-2] if len(hist) > 1 else hist["Close"].iloc[-1],
                "h": hist["High"].iloc[-1],
                "l": hist["Low"].iloc[-1],
            }
        except Exception as e:
            logging.error(f"Error fetching stock data for {symbol}: {e}")
            return {"error": str(e)}

    def get_company_info(self, symbol):
        try:
            stock = yf.Ticker(symbol)
            info = stock.info or {}
            return {
                "name": info.get("shortName", info.get("longName", symbol)),
                "industry": info.get("industry", "Unknown"),
                "sector": info.get("sector", "Unknown"),
                "country": info.get("country", "Unknown"),
                "marketCap": info.get("marketCap", 0),
            }
        except Exception as e:
            logging.error(f"Error fetching company info for {symbol}: {e}")
            return {
                "name": symbol,
                "industry": "Unknown",
                "sector": "Unknown",
                "country": "Unknown",
                "marketCap": 0,
            }

    def create_ai_analysis(self, symbol, data, company_info):
        current_price = data["c"]
        previous_close = data["pc"]
        daily_change = current_price - previous_close
        daily_change_percent = (daily_change / previous_close) * 100
        
        prompt = f"""You are a professional financial advisor. Based on the following stock data, provide a brief and clear analysis and give a simple investment recommendation: BUY, HOLD, or SELL. Briefly explain your reasoning, using only the given price data.

Symbol: {symbol}
{f"Company: {company_info.get('name', '')}" if company_info.get('name') else ""}
Current Price: ${current_price:.2f}
Yesterday Price: ${previous_close:.2f}
Today's Change: ${daily_change:.2f} ({daily_change_percent:+.2f}%)
Day High: ${data['h']:.2f}
Day Low: ${data['l']:.2f}

Provide analysis in English:"""

        try:
            if not self.model:
                return self.create_basic_analysis(symbol, data, company_info)
            
            print(f"🤖 Starting AI analysis: {symbol}")
            logging.info(f"Starting AI analysis for {symbol}")
            
            response = self.model.generate(
                prompt, 
                max_tokens=400, 
                temp=0.3,
                top_p=0.9,
                repeat_penalty=1.1
            )
            
            analysis = response.strip()
            if not analysis or len(analysis) < 20:
                logging.warning("AI response too short, falling back to basic analysis")
                return f"❌ AI response too short!\n\n{self.create_basic_analysis(symbol, data, company_info)}"
            
            print(f"✅ AI analysis completed: {len(analysis)} characters")
            logging.info(f"AI analysis completed successfully: {len(analysis)} characters")
            return analysis
            
        except Exception as e:
            logging.error(f"Error generating AI analysis: {e}")
            return f"❌ AI Analysis Error: {str(e)}\n\n{self.create_basic_analysis(symbol, data, company_info)}"

    def plot_stock_price(self, symbol):
        if not symbol:
            messagebox.showwarning("Warning", "Enter a stock symbol first!")
            return
        
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            plt.style.use('dark_background')
            
            stock = yf.Ticker(symbol.upper())
            hist = stock.history(period="1mo")
            
            if hist.empty:
                messagebox.showerror("Error", f"No data found for {symbol}")
                return
            
            fig, ax = plt.subplots(figsize=(12, 7))
            
            ax.plot(hist.index, hist['Close'], linewidth=3, color='#00D084', alpha=0.8, label='Close Price')
            ax.fill_between(hist.index, hist['Close'], alpha=0.2, color='#00D084')
            
            ax2 = ax.twinx()
            ax2.bar(hist.index, hist['Volume'], alpha=0.3, color='#3742FA', label='Volume')
            ax2.set_ylabel('Volume', color='#3742FA')
            
            ax.set_title(f'{symbol.upper()} Stock Price & Volume - Last 30 Days', 
                        fontsize=16, fontweight='bold', pad=20, color='white')
            ax.set_xlabel('Date', fontsize=12, color='white')
            ax.set_ylabel('Price ($)', fontsize=12, color='white')
            ax.grid(True, alpha=0.3, linestyle='--')
            
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.WeekdayLocator())
            plt.xticks(rotation=45)
            
            current_price = hist['Close'].iloc[-1]
            ax.annotate(f'${current_price:.2f}', 
                       xy=(hist.index[-1], current_price),
                       xytext=(10, 10), textcoords='offset points',
                       bbox=dict(boxstyle='round,pad=0.3', fc='#00D084', alpha=0.8),
                       fontsize=12, fontweight='bold', color='white')
            
            plt.tight_layout()
            plt.show()
            
        except ImportError:
            messagebox.showerror("Error", "Matplotlib library required for charts.\n\nFor EXE version, charts may not be available.\nBasic analysis is still fully functional!")
        except Exception as e:
            logging.error(f"Error creating chart: {e}")
            messagebox.showerror("Error", f"Could not create chart for {symbol}: {str(e)}")

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    try:
        print("🚀 Starting Veriss Stock Analyzer...")
        print(f"Running mode: {'EXE' if getattr(sys, 'frozen', False) else 'Development'}")
        print(f"Base path: {get_base_path()}")
        print(f"Temp path: {get_temp_path()}")
        
        app = ModernStockAnalyzer()
        app.run()
    except Exception as e:
        error_msg = f"❌ Could not start application: {e}"
        print(error_msg)
        logging.error(error_msg)
        
        # EXE modunda hata dialog'u göster
        if getattr(sys, 'frozen', False):
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("Startup Error", f"Application failed to start:\n\n{e}\n\nCheck the log file for details.")
            except:
                pass
        
        input("Press Enter to exit...")