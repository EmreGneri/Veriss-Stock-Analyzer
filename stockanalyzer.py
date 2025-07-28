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
import traceback

# Logging setup with better error handling
try:
    logging.basicConfig(
        filename="stock_analyzer.log",
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    print("✅ Logging initialized")
except Exception as e:
    print(f"⚠️ Could not initialize logging: {e}")
    # Continue without logging if it fails

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

class StockAnalyzer:
    def __init__(self):
        print("🔧 Initializing Stock Analyzer...")
        self.model = None
        self.model_loading = False
        self.model_loaded = False
        
        try:
            print("🎨 Setting up user interface...")
            self.setup_ui()
            print("✅ UI setup complete")
            
            print("🤖 Starting model loading...")
            self.load_model()
            print("✅ Initialization complete")
            
        except Exception as e:
            print(f"❌ Error during initialization: {e}")
            import traceback
            traceback.print_exc()
            raise

    def load_model(self):
        if self.model_loading:
            return
            
        self.model_loading = True
        
        def load_in_background():
           
                # Common model paths for development environment
                possible_paths = [
                    "models/orca-mini-3b-gguf2-q4_0.gguf",
                    "models/mistral-7b-openorca.Q4_0.gguf",
                    "models/nous-hermes-llama2-13b.Q4_0.gguf",
                    os.path.join(os.path.expanduser("~"), ".cache", "gpt4all", "orca-mini-3b-gguf2-q4_0.gguf"),
                    os.path.join(os.path.expanduser("~"), "Documents", "GPT4All", "orca-mini-3b-gguf2-q4_0.gguf"),
                ]
                
                model_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        model_path = path
                        break
                
                if not model_path:
                    print("⚠️ No local model found. AI analysis will be limited.")
                    self.window.after(0, lambda: self.update_status("⚠️ No AI Model", "#FFA502"))
                    self.model_loaded = False
                    return
                
                print(f"🔄 Loading model: {model_path}")
                self.window.after(0, lambda: self.update_status("🔄 Loading AI Model...", "#FFA502"))
                
                # Load with more conservative settings for stability
                self.model = GPT4All(
                    model_path, 
                    allow_download=False, 
                    device='cpu',
                )
                try:    
                    # Test the model with very simple prompt
                    print("🧪 Testing model...")
                    test_response = self.model.generate("Hi", max_tokens=3, temp=0.1)
                    print(f"✅ Model test successful: '{test_response.strip()}'")
                
                    self.model_loaded = True
                    self.window.after(0, lambda: self.update_status("✅ AI Model Ready!", "#00D084"))
                
                except Exception as e:
                    print(f"❌ Model loading error: {e}")
                    print("Full traceback:")
                    traceback.print_exc()
                    logging.error(f"Model loading error: {e}")
                    logging.error(traceback.format_exc())
                    self.model_loaded = False
                    self.model = None
                    self.window.after(0, lambda: self.update_status("❌ AI Model Error", "#FF4757"))
                finally:
                    self.model_loading = False

        threading.Thread(target=load_in_background, daemon=True).start()

    def setup_ui(self):
        try:
            print("🪟 Creating main window...")
            self.window = tk.Tk()
            self.window.title("🚀 Stock Analyzer - AI Powered")
            self.window.geometry("1400x800")
            self.window.configure(bg="#0F0F23")
            self.window.resizable(True, True)
            
            # Prevent window from closing unexpectedly
            self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            print("🎨 Setting up color scheme...")
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

            print("📦 Creating main container...")
            main_container = tk.Frame(self.window, bg=self.colors['bg_primary'])
            main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            print("📋 Creating header...")
            self.create_header(main_container)
            
            print("📊 Creating content frame...")
            content_frame = tk.Frame(main_container, bg=self.colors['bg_primary'])
            content_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))
            
            print("⬅️ Creating left panel...")
            self.create_left_panel(content_frame)
            
            print("➡️ Creating right panel...")
            self.create_right_panel(content_frame)
            
            print("✅ UI setup completed successfully")
            
        except Exception as e:
            print(f"❌ Error setting up UI: {e}")
            import traceback
            traceback.print_exc()
            raise

    def on_closing(self):
        """Handle window closing event properly"""
        try:
            print("🛑 Closing application...")
            # Clean up model if loaded
            if hasattr(self, 'model') and self.model:
                try:
                    # Try to properly close the model
                    del self.model
                    self.model = None
                    print("✅ Model cleaned up")
                except:
                    pass
            
            if hasattr(self, 'window'):
                self.window.quit()
                self.window.destroy()
        except Exception as e:
            print(f"Error during closing: {e}")
        finally:
            sys.exit(0)

    def create_header(self, parent):
        header_frame = tk.Frame(parent, bg=self.colors['bg_secondary'], height=80)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        header_frame.pack_propagate(False)
        
        title_frame = tk.Frame(header_frame, bg=self.colors['bg_secondary'])
        title_frame.pack(expand=True, fill=tk.BOTH)
        
        title_label = tk.Label(
            title_frame,
            text="🚀 Stock Analyzer",
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
        
        welcome_msg = f"""🎯 Welcome to Stock Analyzer!

✨ FEATURES:
• 🤖 Advanced AI-powered stock analysis
• 📊 Real-time investor portfolio tracking  
• 💼 Famous investor holdings monitoring
• 🌐 Live market data integration
• 📈 Interactive price charts

🚀 HOW TO USE:
1. Enter stock symbol (AAPL, GOOGL, TSLA, etc.)
2. Or enter famous investor name (Warren Buffett, Bill Gates, etc.)  
3. Click 'AI ANALYZE' for AI-powered investment advice
4. Use 'CHART' to visualize price trends
5. Check sample portfolio on the right panel →

💡 To use AI features, place a GPT4All model file in the 'models' folder
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
            messagebox.showwarning("No Selection", "Please select a stock from the portfolio!")
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
                print(f"❌ Error in analyze_stock: {e}")
                traceback.print_exc()
                logging.error(f"Error in analyze_stock: {e}")
                logging.error(traceback.format_exc())
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
            
            # Always try AI analysis first if model is available
            if self.model_loaded and self.model:
                try:
                    analysis = self.create_ai_analysis(symbol, stock_data, company_info)
                except Exception as ai_error:
                    print(f"❌ AI analysis failed, falling back to basic: {ai_error}")
                    analysis = "❌ AI analysis failed. Showing basic analysis:\n\n" + self.create_basic_analysis(symbol, stock_data, company_info)
            else:
                analysis = "⚠️ AI model not available. Showing basic analysis:\n\n" + self.create_basic_analysis(symbol, stock_data, company_info)
      
            self.window.after(0, lambda: self.display_stock_analysis(symbol, stock_data, company_info, analysis))
            
        except Exception as e:
            print(f"❌ Error analyzing single stock {symbol}: {e}")
            traceback.print_exc()
            logging.error(f"Error analyzing single stock {symbol}: {e}")
            logging.error(traceback.format_exc())
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
            print(f"❌ Error analyzing investor portfolio: {e}")
            traceback.print_exc()
            logging.error(f"Error analyzing investor portfolio: {e}")
            logging.error(traceback.format_exc())
            self.window.after(0, lambda: self.display_error(f"{investor_name} portfolio analysis failed: {str(e)}"))

    def create_basic_analysis(self, symbol, stock_data, company_info):
        """AI olmadan temel analiz"""
        current_price = stock_data["c"]
        previous_close = stock_data["pc"]
        daily_change = current_price - previous_close
        daily_change_percent = (daily_change / previous_close) * 100
        
        analysis = "📈 BASIC TECHNICAL ANALYSIS:\n"
        analysis += "-" * 30 + "\n\n"
        
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
        
        day_range = stock_data['h'] - stock_data['l']
        range_percent = (day_range / current_price) * 100
        
        analysis += f"\n📊 Volatility: {range_percent:.1f}% intraday range\n"
        if range_percent > 5:
            analysis += "High volatility - Risky for short term\n"
        elif range_percent > 2:
            analysis += "Moderate volatility - Normal trading\n"
        else:
            analysis += "Low volatility - Stable trading\n"
        
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
        
        # Shorter, more focused prompt to prevent crashes
        prompt = f"""YOU ARE A FINANCIAL ANALYST AI. GIVE A DETAILED ANALYSIS OF THE STOCK MARKET DATA BELOW. DONT USE TOO MUCH JARGON, BE CONCISE AND TO THE POINT.

Stock: {symbol}
Price: ${current_price:.2f}
Change: {daily_change_percent:+.1f}%
High: ${data['h']:.2f}
Low: ${data['l']:.2f}

Give a short analysis and recommendation (BUY/HOLD/SELL):"""

        try:
            if not self.model or not self.model_loaded:
                return self.create_basic_analysis(symbol, data, company_info)
            
            print(f"🤖 Starting AI analysis: {symbol}")
            logging.info(f"Starting AI analysis for {symbol}")
            
            # Use more conservative settings to prevent crashes
            response = self.model.generate(
                prompt, 
                max_tokens=200,  # Reduced from 400
                temp=0.1,        # Lower temperature for stability
                top_p=0.8,       # More conservative
                repeat_penalty=1.05,  # Reduced
                 # Single thread for stability
            )
            
            analysis = response.strip()
            if not analysis or len(analysis) < 10:
                logging.warning("AI response too short, falling back to basic analysis")
                return f"❌ AI response incomplete!\n\n{self.create_basic_analysis(symbol, data, company_info)}"
            
            print(f"✅ AI analysis completed: {len(analysis)} characters")
            logging.info(f"AI analysis completed successfully: {len(analysis)} characters")
            return analysis
            
        except Exception as e:
            print(f"❌ Error generating AI analysis: {e}")
            traceback.print_exc()
            logging.error(f"Error generating AI analysis: {e}")
            logging.error(traceback.format_exc())
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
            messagebox.showerror("Error", "Matplotlib library required for charts.\n\nInstall with: pip install matplotlib")
        except Exception as e:
            logging.error(f"Error creating chart: {e}")
            messagebox.showerror("Error", f"Could not create chart for {symbol}: {str(e)}")

    def run(self):
        try:
            print("🚀 Starting main application loop...")
            self.window.mainloop()
        except KeyboardInterrupt:
            print("\n🛑 Application interrupted by user")
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("👋 Application main loop ended")


if __name__ == "__main__":
    try:
        print("🚀 Starting Stock Analyzer...")
        print("📦 Checking dependencies...")
        
        # Check critical imports
        try:
            import tkinter as tk
            print("✅ Tkinter OK")
        except ImportError as e:
            print(f"❌ Tkinter missing: {e}")
            input("Press Enter to exit...")
            sys.exit(1)
            
        try:
            import yfinance as yf
            print("✅ YFinance OK")
        except ImportError as e:
            print(f"❌ YFinance missing. Install with: pip install yfinance")
            print(f"Error: {e}")
            input("Press Enter to exit...")
            sys.exit(1)
            
        try:
            from bs4 import BeautifulSoup
            print("✅ BeautifulSoup OK")
        except ImportError as e:
            print(f"❌ BeautifulSoup missing. Install with: pip install beautifulsoup4")
            print(f"Error: {e}")
            input("Press Enter to exit...")
            sys.exit(1)
            
        try:
            import requests
            print("✅ Requests OK")
        except ImportError as e:
            print(f"❌ Requests missing. Install with: pip install requests")
            print(f"Error: {e}")
            input("Press Enter to exit...")
            sys.exit(1)

        print("🚀 All dependencies OK, starting application...")
        
        app = StockAnalyzer()
        print("✅ Application initialized successfully")
        app.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Application stopped by user")
    except Exception as e:
        error_msg = f"❌ Critical error starting application: {e}"
        print(error_msg)
        print(f"Error type: {type(e).__name__}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        print("\n💡 Common solutions:")
        print("1. Make sure all dependencies are installed:")
        print("   pip install gpt4all yfinance beautifulsoup4 requests matplotlib")
        print("2. Check your Python version (3.7+ required)")
        print("3. Try running as administrator")
        print("4. Check if any antivirus is blocking the app")
        input("\nPress Enter to exit...")
    finally:
        print("👋 Application closed")
