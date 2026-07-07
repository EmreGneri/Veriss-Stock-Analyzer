import sys
import os


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ml"))

try:
    from gpt4all import GPT4All
    GPT4ALL_AVAILABLE = True
except ImportError:
    GPT4ALL_AVAILABLE = False
    print("[INFO] gpt4all not installed - LLM commentary disabled, ML signal still available")

try:
    from predict import get_ml_signal
    ML_AVAILABLE = True
except ImportError as e:
    ML_AVAILABLE = False
    print(f"[INFO] ML module unavailable: {e}")

import threading
import time
import logging
import traceback

import requests
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import yfinance as yf
from bs4 import BeautifulSoup

logging.basicConfig(
    filename="stock_analyzer.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


C = {
    "bg":            "#F4F7FA",  
    "panel":         "#FFFFFF",  
    "card":          "#FFFFFF",  
    "card_shadow":   "#DDE3EC",  
    "border":        "#E2E8F0",  
    "accent":        "#059669", 
    "accent_hover":  "#047857",  
    "accent_light":  "#D1FAE5",  
    "btn":           "#F1F5F9", 
    "btn_hover":     "#E2E8F0", 
    "text":          "#0F172A", 
    "text2":         "#334155",  
    "dim":           "#94A3B8",  
    "red":           "#EF4444",  
    "amber":         "#F59E0B",  

   
    "gain":          "#059669",  
    "loss":          "#DC2626",  
    "neutral":       "#D97706",  
}

FONT = "Segoe UI"
MONO = "Consolas"


def make_shadow_card(parent, bg=None, shadow=None, pad=3, **frame_kw):
    """Simulates a drop shadow by layering a slightly darker outer frame."""
    bg = bg or C["card"]
    shadow = shadow or C["card_shadow"]
    outer = tk.Frame(parent, bg=shadow, **frame_kw)
    inner = tk.Frame(outer, bg=bg)
    inner.pack(fill=tk.BOTH, expand=True, padx=(0, pad), pady=(0, pad))
    return outer, inner


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, bg, hover_bg, fg,
                 width=120, height=34, corner_radius=7,
                 font=(FONT, 10, "bold"), state="normal"):
        self.width = width
        self.height = height
        super().__init__(parent, width=width, height=height,
                         bg=parent["bg"], highlightthickness=0)
        self.command = command
        self.bg_normal = bg
        self.bg = bg
        self.hover_bg = hover_bg
        self.fg = fg
        self.text = text
        self.corner_radius = corner_radius
        self.font = font
        self.state = state

        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        self.draw()

    def draw(self):
        self.delete("all")
        w, h, r = self.width, self.height, self.corner_radius
        bg = C["border"] if self.state == "disabled" else self.bg
        fg = C["dim"]   if self.state == "disabled" else self.fg
        for coords, start in [
            ((0, 0, r*2, r*2), 90),
            ((w-r*2-1, 0, w-1, r*2), 0),
            ((0, h-r*2-1, r*2, h-1), 180),
            ((w-r*2-1, h-r*2-1, w-1, h-1), 270),
        ]:
            self.create_arc(coords, start=start, extent=90,
                            fill=bg, outline=bg, tags="bg")
        self.create_rectangle((r, 0, w-r, h), fill=bg, outline=bg, tags="bg")
        self.create_rectangle((0, r, w, h-r), fill=bg, outline=bg, tags="bg")
        self.create_text(w/2, h/2, text=self.text, fill=fg,
                         font=self.font, tags="lbl")

    def on_enter(self, event):
        if self.state == "normal":
            self.itemconfig("bg", fill=self.hover_bg, outline=self.hover_bg)

    def on_leave(self, event):
        if self.state == "normal":
            self.itemconfig("bg", fill=self.bg, outline=self.bg)

    def on_click(self, event):
        if self.state == "normal" and self.command:
            self.command()

    def config(self, **kwargs):
        if "state" in kwargs: self.state = kwargs["state"]
        if "text"  in kwargs: self.text  = kwargs["text"]
        if "bg"    in kwargs: self.bg    = kwargs["bg"]
        if "hover" in kwargs: self.hover_bg = kwargs["hover"]
        self.draw()

    def configure(self, **kwargs):
        self.config(**kwargs)


class StatusLight(tk.Canvas):
    """Small glowing LED status indicator."""
    def __init__(self, parent, size=10):
        super().__init__(parent, width=size, height=size,
                         bg=parent["bg"], highlightthickness=0)
        self.size = size
        self.color = C["dim"]
        self.draw()

    def draw(self):
        self.delete("all")
        s = self.size
        # Outer glow ring
        self.create_oval(0, 0, s, s, fill=self.color, outline="", stipple="gray50")
        # Inner solid dot
        m = s // 4
        self.create_oval(m, m, s-m, s-m, fill=self.color, outline="")

    def set_color(self, color):
        self.color = color
        self.draw()


class GridBackgroundCanvas(tk.Canvas):
    def __init__(self, parent, bg_color, grid_color, trend_color):
        super().__init__(parent, bg=bg_color, highlightthickness=0)
        self.bg_color = bg_color
        self.grid_color = grid_color
        self.trend_color = trend_color
        self.bind("<Configure>", self.draw_background)

    def draw_background(self, event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return

        
        grid_size = 48
        for x in range(0, w, grid_size):
            self.create_line(x, 0, x, h, fill=self.grid_color, width=1)
        for y in range(0, h, grid_size):
            self.create_line(0, y, w, y, fill=self.grid_color, width=1)

      
        points = [
            (0, h * 0.95),
            (w * 0.15, h * 0.88),
            (w * 0.30, h * 0.75),
            (w * 0.45, h * 0.80),
            (w * 0.60, h * 0.58),
            (w * 0.75, h * 0.62),
            (w * 0.90, h * 0.38),
            (w, h * 0.30)
        ]
        
        poly_points = [0, h]
        for p in points:
            poly_points.extend(p)
        poly_points.extend([w, h])
        
        self.create_polygon(poly_points, fill=self.trend_color, outline="")
        self.create_line(points, fill=self.grid_color, width=2, smooth=True)

        
        cx = w - 160
        cy = h - 160
        
        # Arcs
        self.create_arc(cx - 30, cy - 40, cx + 30, cy, start=0, extent=180, outline=self.grid_color, width=3, style=tk.ARC)
        self.create_arc(cx - 30, cy, cx + 30, cy + 40, start=180, extent=180, outline=self.grid_color, width=3, style=tk.ARC)
        # S middle line
        self.create_line(cx - 30, cy, cx + 30, cy, fill=self.grid_color, width=3)
        # S vertical bar
        self.create_line(cx, cy - 60, cx, cy + 60, fill=self.grid_color, width=3)


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
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
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
        tickers = []
        for link in stock_links:
            href = link.get("href", "")
            if "sym=" in href:
                ticker = href.split("sym=")[1].split("&")[0].strip().upper()
                if ticker and len(ticker) <= 6 and ticker not in tickers:
                    tickers.append(ticker)
        return tickers[:15]

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
        except Exception:
            data.append([ticker, "Error", "N/A", "N/A", "N/A"])
    return data


class StockAnalyzer:
    def __init__(self):
        print("[INFO] Initializing Stock Analyzer...")
        self.model = None
        self.model_loading = False
        self.model_loaded = False

        self.setup_ui()
        self.setup_tags()
        
        # Display the formatted initial text
        initial_text = (
            "STOCK ANALYSIS: Veriss Stock Analyzer\n"
            "===\n\n"
            "Enter a stock symbol (AAPL, MSFT, TSLA) or a famous investor\n"
            "name (Warren Buffett, Michael Burry) and press Analyze.\n\n"
            "The ML signal comes from a RandomForest model trained on\n"
            "5 years of daily price history. If a local LLM model is\n"
            "installed, a short commentary is added on top.\n\n"
            "First analysis of a new symbol trains a model and can take\n"
            "about a minute.\n\n"
            "Educational tool - not financial advice.\n"
        )
        self.insert_formatted_text(initial_text)
        
        self.load_model()
        print("[OK] Initialization complete")

    # ------------------------------------------------------------------ UI

    def setup_ui(self):
        self.window = tk.Tk()
        self.window.title("Veriss Stock Analyzer")
        self.window.geometry("1280x780")
        self.window.configure(bg=C["bg"])
        self.window.minsize(1000, 640)
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._apply_window_effects()

        self.bg_canvas = GridBackgroundCanvas(
            self.window, 
            bg_color=C["bg"], 
            grid_color="#EDF2F7", 
            trend_color="#F1F5F9"
        )
        self.bg_canvas.pack(fill=tk.BOTH, expand=True)

        root = tk.Frame(self.bg_canvas, bg=C["bg"])
        root.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        self._build_header(root)

        content = tk.Frame(root, bg=C["bg"])
        content.pack(fill=tk.BOTH, expand=True, pady=(16, 0))

        self._build_left_panel(content)
        self._build_right_panel(content)

    def _apply_window_effects(self):
        """Pencere saydamlığı + Windows 11 Mica dokusu. Desteklenmeyen
        sistemlerde sessizce atlanır, uygulama normal görünümde açılır."""
        try:
            self.window.attributes("-alpha", 0.97)
        except tk.TclError:
            pass
        try:
            import ctypes
            self.window.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.window.winfo_id())
          
            backdrop = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
        except Exception:
            pass

    def _build_header(self, parent):
        # Thin emerald accent bar at very top
        accent_bar = tk.Frame(parent, bg=C["accent"], height=3)
        accent_bar.pack(fill=tk.X)

        header = tk.Frame(parent, bg=C["panel"])
        header.pack(fill=tk.X)

        title_box = tk.Frame(header, bg=C["panel"])
        title_box.pack(side=tk.LEFT, padx=24, pady=14)

        tk.Label(title_box, text="Veriss", font=(FONT, 20, "bold"),
                 bg=C["panel"], fg=C["accent"]).pack(side=tk.LEFT)
        tk.Label(title_box, text="  Stock Analyzer", font=(FONT, 13),
                 bg=C["panel"], fg=C["dim"]).pack(side=tk.LEFT, pady=(5, 0))

        status_box = tk.Frame(header, bg=C["panel"])
        status_box.pack(side=tk.RIGHT, padx=24, pady=14)

        self.status_light = StatusLight(status_box, size=10)
        self.status_light.pack(side=tk.LEFT, padx=(0, 7))

        self.status_label = tk.Label(status_box, text="",
                                     font=(FONT, 9), bg=C["panel"], fg=C["dim"])
        self.status_label.pack(side=tk.LEFT)
        self.set_status("Starting...", C["dim"])

        # Thin separator line
        tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X)

    def _build_left_panel(self, parent):
        left = tk.Frame(parent, bg=C["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 14))

        # --- Search card (shadow-simulated) ---
        outer, inner_card = make_shadow_card(left, pad=2)
        outer.pack(fill=tk.X, pady=(0, 14))

        inner = tk.Frame(inner_card, bg=C["card"])
        inner.pack(fill=tk.X, padx=22, pady=18)

        tk.Label(inner, text="SYMBOL OR INVESTOR NAME",
                 font=(FONT, 8, "bold"), bg=C["card"], fg=C["dim"]).pack(anchor=tk.W)

        row = tk.Frame(inner, bg=C["card"])
        row.pack(fill=tk.X, pady=(10, 6))

        # Entry with smooth focus border
        entry_wrap = tk.Frame(row, bg=C["border"], highlightthickness=0)
        entry_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        entry_inner = tk.Frame(entry_wrap, bg=C["card"])
        entry_inner.pack(fill=tk.X, padx=1, pady=1)

        self.entry_symbol = tk.Entry(
            entry_inner, font=(FONT, 12), bg=C["card"], fg=C["text"],
            insertbackground=C["accent"], relief="flat", bd=0
        )
        self.entry_symbol.pack(fill=tk.X, padx=12, pady=9)
        self.entry_symbol.bind("<Return>", lambda e: self.analyze_stock())

        def on_focus_in(e):
            entry_wrap.config(bg=C["accent"])
        def on_focus_out(e):
            entry_wrap.config(bg=C["border"])
        self.entry_symbol.bind("<FocusIn>", on_focus_in)
        self.entry_symbol.bind("<FocusOut>", on_focus_out)

        self.btn_analyze = self._button(
            row, "Analyze", self.analyze_stock,
            bg=C["accent"], hover=C["accent_hover"], fg=C["panel"]
        )
        self.btn_analyze.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_plot = self._button(
            row, "Chart",
            lambda: self.plot_stock_price(self.entry_symbol.get().strip()),
            bg=C["btn"], hover=C["btn_hover"], fg=C["text2"]
        )
        self.btn_plot.pack(side=tk.LEFT)

        tk.Label(inner, text="e.g.  AAPL  ·  MSFT  ·  TSLA  ·  Warren Buffett  ·  Michael Burry",
                 font=(FONT, 8), bg=C["card"], fg=C["dim"]).pack(anchor=tk.W)

        # --- Analysis report card (shadow-simulated) ---
        outer2, results_card = make_shadow_card(left, pad=2)
        outer2.pack(fill=tk.BOTH, expand=True)

        # Header row with green left accent strip
        hdr = tk.Frame(results_card, bg=C["card"])
        hdr.pack(fill=tk.X, padx=0, pady=(0, 0))
        tk.Frame(hdr, bg=C["accent"], width=4).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text="Analysis Report", font=(FONT, 10, "bold"),
                 bg=C["card"], fg=C["text"]).pack(side=tk.LEFT, padx=14, pady=14)

        tk.Frame(results_card, bg=C["border"], height=1).pack(fill=tk.X)

        self.result_text = scrolledtext.ScrolledText(
            results_card, wrap=tk.WORD, font=(MONO, 10),
            bg=C["card"], fg=C["text2"], insertbackground=C["accent"],
            relief="flat", bd=0,
            selectbackground=C["accent_light"],
            selectforeground=C["text"],
            padx=18, pady=14,
        )
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 0))

    def _build_right_panel(self, parent):
        right = tk.Frame(parent, bg=C["bg"], width=384)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)

        outer, card = make_shadow_card(right, pad=2)
        outer.pack(fill=tk.BOTH, expand=True)

        # Header row with green accent strip
        hdr = tk.Frame(card, bg=C["card"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=C["accent"], width=4).pack(side=tk.LEFT, fill=tk.Y)
        hdr_inner = tk.Frame(hdr, bg=C["card"])
        hdr_inner.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=14, pady=14)

        tk.Label(hdr_inner, text="Sample Portfolio", font=(FONT, 10, "bold"),
                 bg=C["card"], fg=C["text"]).pack(side=tk.LEFT)

        self.btn_refresh = self._button(
            hdr_inner, "Refresh", self.refresh_buffett_data,
            bg=C["btn"], hover=C["btn_hover"], fg=C["text2"]
        )
        self.btn_refresh.pack(side=tk.RIGHT)

        tk.Frame(card, bg=C["border"], height=1).pack(fill=tk.X)

        table_frame = tk.Frame(card, bg=C["card"])
        table_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(10, 8))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Veriss.Treeview",
                        background=C["card"], foreground=C["text2"],
                        fieldbackground=C["card"], borderwidth=0,
                        rowheight=34, font=(FONT, 10))
        style.configure("Veriss.Treeview.Heading",
                        background=C["bg"], foreground=C["dim"],
                        borderwidth=0, font=(FONT, 8, "bold"),
                        relief="flat", padding=(4, 6))
        style.map("Veriss.Treeview",
                  background=[("selected", C["accent_light"])],
                  foreground=[("selected", C["accent"])])

        style.configure("Veriss.Vertical.TScrollbar",
                        troughcolor=C["bg"], background=C["border"],
                        bordercolor=C["bg"], arrowcolor=C["dim"],
                        arrowsize=10, gripcount=0)
        style.map("Veriss.Vertical.TScrollbar",
                  background=[("active", C["btn_hover"])])

        columns = ("Symbol", "Company", "Price", "P/E", "Cap")
        self.buffett_tree = ttk.Treeview(table_frame, columns=columns,
                                         show="headings", style="Veriss.Treeview")
        widths = {"Symbol": 52, "Company": 118, "Price": 66, "P/E": 42, "Cap": 62}
        for col in columns:
            self.buffett_tree.heading(col, text=col.upper())
            self.buffett_tree.column(col, anchor="center", width=widths.get(col, 60))

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical",
                                  style="Veriss.Vertical.TScrollbar",
                                  command=self.buffett_tree.yview)
        self.buffett_tree.configure(yscrollcommand=scrollbar.set)
        self.buffett_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Frame(card, bg=C["border"], height=1).pack(fill=tk.X)
        btn = self._button(card, "Analyze Selected",
                           self.analyze_selected_buffett_stock,
                           bg=C["accent"], hover=C["accent_hover"], fg=C["panel"])
        btn.pack(pady=14)

        self.load_buffett_data()

    def _button(self, parent, text, command, bg, hover, fg=None, padx=18, pady=8):
        fg = fg or C["text"]
        width = max(88, len(text) * 8 + 36)
        height = 34
        if text in ("Analyze Selected", "Analyze selected"):
            width = 168
        return RoundedButton(parent, text, command, bg=bg, hover_bg=hover,
                             fg=fg, width=width, height=height)

    def set_status(self, text, color):
        """Thread-safe durum güncellemesi - her thread'den çağrılabilir."""
        def apply():
            self.status_label.config(text=text, fg=C["text"])
            self.status_light.set_color(color)
        try:
            self.window.after(0, apply)
        except RuntimeError:
            pass  # pencere kapanırken gelen güncellemeleri yoksay

    def on_closing(self):
        try:
            if self.model is not None:
                self.model = None
            self.window.quit()
            self.window.destroy()
        except Exception as e:
            logging.error(f"Error during closing: {e}")

    def setup_tags(self):
        self.result_text.tag_configure(
            "title", font=(FONT, 14, "bold"), foreground=C["accent"],
            spacing1=12, spacing3=6)
        self.result_text.tag_configure(
            "header", font=(FONT, 10, "bold"), foreground=C["text"],
            spacing1=10, spacing3=3)
        self.result_text.tag_configure(
            "buy",  font=(MONO, 10, "bold"), foreground=C["gain"],
            background=C["accent_light"])
        self.result_text.tag_configure(
            "sell", font=(MONO, 10, "bold"), foreground=C["loss"],
            background="#FEE2E2")
        self.result_text.tag_configure(
            "hold", font=(MONO, 10, "bold"), foreground=C["neutral"],
            background="#FEF3C7")
        self.result_text.tag_configure("gain",    foreground=C["gain"])
        self.result_text.tag_configure("loss",    foreground=C["loss"])
        self.result_text.tag_configure("divider", foreground=C["border"])
        self.result_text.tag_configure("muted",   foreground=C["dim"])

    def insert_formatted_text(self, text):
        self.result_text.config(state="normal")
        self.result_text.delete(1.0, tk.END)

        for line in text.split("\n"):
            if line.startswith("STOCK ANALYSIS:") or line.startswith("PORTFOLIO:"):
                self.result_text.insert(tk.END, line + "\n", "title")

            elif line.strip() in {
                "COMPANY", "PRICE",
                "ML SIGNAL (RandomForest)", "TECHNICAL SUMMARY",
                "COMMENTARY (LLM)", "COMMENTARY", "ERROR"
            }:
                self.result_text.insert(tk.END, line + "\n", "header")

            elif line.startswith("---") or line.startswith("==="):
                self.result_text.insert(tk.END, "─" * 48 + "\n", "divider")

            else:
                for word in line.split(" "):
                    cw = word.strip().upper().rstrip(".,;:")
                    if cw in ("BUY",):
                        self.result_text.insert(tk.END, f" {word} ", "buy")
                        self.result_text.insert(tk.END, " ")
                    elif cw in ("SELL",):
                        self.result_text.insert(tk.END, f" {word} ", "sell")
                        self.result_text.insert(tk.END, " ")
                    elif cw in ("HOLD",):
                        self.result_text.insert(tk.END, f" {word} ", "hold")
                        self.result_text.insert(tk.END, " ")
                    elif "+" in word and any(c.isdigit() for c in word):
                        self.result_text.insert(tk.END, word + " ", "gain")
                    elif "-" in word and any(c.isdigit() for c in word) and ("%" in word or "$" in word):
                        self.result_text.insert(tk.END, word + " ", "loss")
                    else:
                        self.result_text.insert(tk.END, word + " ")
                self.result_text.insert(tk.END, "\n")

        self.result_text.config(state="disabled")

    # ----------------------------------------------------------- LLM model

    def load_model(self):
        if self.model_loading:
            return
        self.model_loading = True

        def load_in_background():
            try:
                if not GPT4ALL_AVAILABLE:
                    print("[INFO] GPT4All not installed; skipping LLM load.")
                    self.set_status("ML signal mode (no LLM)", C["dim"])
                    return

                import glob
                script_dir = os.path.dirname(os.path.abspath(__file__))
                candidates = sorted(glob.glob(os.path.join(script_dir, "models", "*.gguf")))
                candidates += [
                    os.path.join(os.path.expanduser("~"), ".cache", "gpt4all", "orca-mini-3b-gguf2-q4_0.gguf"),
                    os.path.join(os.path.expanduser("~"), "Documents", "GPT4All", "orca-mini-3b-gguf2-q4_0.gguf"),
                ]
                model_path = next((p for p in candidates if os.path.exists(p)), None)

                if not model_path:
                    print("[WARN] No local LLM model found.")
                    self.set_status("No LLM model - ML signal only", C["amber"])
                    return

                print(f"[INFO] Loading model: {model_path}")
                self.set_status("Loading LLM model...", C["amber"])

                try:
                    self.model = GPT4All(model_path, allow_download=False, device="gpu")
                    print("[OK] Model running on GPU")
                except Exception as gpu_error:
                    print(f"[INFO] GPU init failed ({gpu_error}); falling back to CPU")
                    self.model = GPT4All(model_path, allow_download=False, device="cpu")

                self.model.generate("Hi", max_tokens=2, temp=0.1)
                self.model_loaded = True
                print("[OK] LLM model ready")
                self.set_status("Model ready", C["accent"])

            except Exception as e:
                print(f"[ERROR] LLM load failed: {e}")
                logging.error(f"LLM load failed: {e}\n{traceback.format_exc()}")
                self.model = None
                self.model_loaded = False
                self.set_status("LLM unavailable - ML signal only", C["red"])
            finally:
                self.model_loading = False

        threading.Thread(target=load_in_background, daemon=True).start()

    # ------------------------------------------------------------ Portfolio

    def load_buffett_data(self):
        def load_data():
            try:
                self.set_status("Loading holdings...", C["amber"])
                holdings = get_buffett_top_holdings_data()

                def populate():
                    for item in self.buffett_tree.get_children():
                        self.buffett_tree.delete(item)
                    for row_values in holdings:
                        self.buffett_tree.insert("", tk.END, values=row_values)

                self.window.after(0, populate)
                self.set_status("Ready", C["accent"] if self.model_loaded else C["dim"])
            except Exception as e:
                logging.error(f"Holdings load failed: {e}")
                self.set_status("Holdings load failed", C["red"])

        threading.Thread(target=load_data, daemon=True).start()

    def refresh_buffett_data(self):
        self.btn_refresh.config(state="disabled", text="...")

        def refresh():
            try:
                self.load_buffett_data()
            finally:
                self.window.after(0, lambda: self.btn_refresh.config(state="normal", text="Refresh"))

        threading.Thread(target=refresh, daemon=True).start()

    def analyze_selected_buffett_stock(self):
        selection = self.buffett_tree.selection()
        if not selection:
            messagebox.showwarning("No selection", "Select a stock from the portfolio first.")
            return
        ticker = self.buffett_tree.item(selection[0])["values"][0]
        self.entry_symbol.delete(0, tk.END)
        self.entry_symbol.insert(0, ticker)
        self.analyze_stock()

    # -------------------------------------------------------------- Analysis

    def analyze_stock(self):
        symbol = self.entry_symbol.get().strip()
        if not symbol:
            messagebox.showwarning("Missing input", "Enter a stock symbol or investor name.")
            return

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "Analyzing... this can take a minute for a new symbol.\n")
        self.btn_analyze.config(state="disabled", text="Analyzing...")

        def analyze_in_background():
            try:
                investor_code = resolve_name_to_dataroma_code(symbol)
                if investor_code:
                    self.analyze_investor_portfolio(symbol, investor_code)
                else:
                    self.analyze_single_stock(symbol.upper())
            except Exception as e:
                logging.error(f"Error in analyze_stock: {e}\n{traceback.format_exc()}")
                self.window.after(0, lambda: self.display_error(f"Analysis failed: {e}"))
            finally:
                self.window.after(0, lambda: self.btn_analyze.config(state="normal", text="Analyze"))

        threading.Thread(target=analyze_in_background, daemon=True).start()

    def analyze_single_stock(self, symbol):
        stock_data = self.get_stock_data(symbol)
        if "error" in stock_data:
            self.window.after(0, lambda: self.display_error(
                f"Could not get data for {symbol}: {stock_data['error']}"))
            return

        company_info = self.get_company_info(symbol)

        # 1) ML sinyali (RandomForest)
        ml_section = self.create_ml_analysis(symbol)

        # 2) Üstüne LLM yorumu (varsa) ya da temel teknik özet
        if self.model_loaded and self.model:
            try:
                commentary = "COMMENTARY (LLM)\n" + "-" * 40 + "\n"
                commentary += self.create_ai_analysis(symbol, stock_data)
            except Exception as ai_error:
                logging.error(f"AI analysis failed: {ai_error}")
                commentary = self.create_basic_analysis(symbol, stock_data)
        else:
            commentary = self.create_basic_analysis(symbol, stock_data)

        analysis = ml_section + "\n" + commentary
        self.window.after(0, lambda: self.display_stock_analysis(
            symbol, stock_data, company_info, analysis))

    def analyze_investor_portfolio(self, investor_name, investor_code):
        tickers = get_dataroma_portfolio(investor_code)
        if not tickers:
            self.window.after(0, lambda: self.display_error(
                f"Portfolio not found for {investor_name}"))
            return

        lines = [f"PORTFOLIO: {investor_name.upper()}", "=" * 44, "",
                 f"{len(tickers)} holdings found", ""]

        for i, ticker in enumerate(tickers[:10], 1):
            try:
                stock_data = self.get_stock_data(ticker)
                if "error" not in stock_data:
                    change = ((stock_data["c"] - stock_data["pc"]) / stock_data["pc"]) * 100
                    lines.append(f"{i:2d}. {ticker:6s} ${stock_data['c']:>9.2f}  {change:+.1f}%")
                else:
                    lines.append(f"{i:2d}. {ticker:6s} data not available")
            except Exception:
                lines.append(f"{i:2d}. {ticker:6s} fetch error")

        lines += ["", "Type one of the symbols above and press Analyze",
                  "for a detailed ML + LLM analysis."]

        text = "\n".join(lines)
        self.window.after(0, lambda: self.display_portfolio_analysis(text))

    def create_ml_analysis(self, symbol):
        """ML sinyal bölümü. Model yoksa ilk çağrıda eğitilir (web ile aynı ml/ paketi)."""
        if not ML_AVAILABLE:
            return "ML SIGNAL\n" + "-" * 40 + "\nUnavailable (ml/ module not found)\n"
        try:
            s = get_ml_signal(symbol)
            header = f"ML SIGNAL ({s.get('model_name', 'ML')})\n" + "-" * 40 + "\n"
            out = header
            out += f"Signal: {s['signal']}   P(up in 5 days): {s['probability_up']:.1%}"
            if s.get("proba_baseline") is not None:
                out += f"   (model baseline: {s['proba_baseline']:.1%})"
            out += "\n"
            out += f"RSI(14): {s['rsi_14']:.1f}   SMA5/SMA20: {s['sma_ratio']:.3f}\n"
            out += f"Model test accuracy: {s['model_test_accuracy']:.1%}   F1: {s['model_test_f1']:.2f}\n"
            out += f"Data as of: {s['as_of']}\n"
            if s.get("explanation"):
                out += "\nWhy " + s["signal"] + "?\n"
                out += s["explanation"] + "\n"
            return out
        except Exception as e:
            logging.error(f"ML signal failed for {symbol}: {e}")
            return "ML SIGNAL\n" + "-" * 40 + f"\nCould not compute ({e})\n"

    def create_basic_analysis(self, symbol, stock_data):
        current_price = stock_data["c"]
        previous_close = stock_data["pc"]
        daily_change_percent = ((current_price - previous_close) / previous_close) * 100

        out = "TECHNICAL SUMMARY\n" + "-" * 40 + "\n"

        if daily_change_percent > 5:
            out += "Strong upward momentum (more than +5%)\n"
        elif daily_change_percent > 2:
            out += "Moderate upward trend (+2% to +5%)\n"
        elif daily_change_percent > 0:
            out += "Slight positive movement\n"
        elif daily_change_percent > -2:
            out += "Minor decline (less than -2%)\n"
        elif daily_change_percent > -5:
            out += "Moderate decline (-2% to -5%)\n"
        else:
            out += "Significant decline (more than -5%)\n"

        day_range = stock_data["h"] - stock_data["l"]
        range_percent = (day_range / current_price) * 100
        out += f"Intraday range: {range_percent:.1f}%"
        if range_percent > 5:
            out += " (high volatility)\n"
        elif range_percent > 2:
            out += " (moderate volatility)\n"
        else:
            out += " (low volatility)\n"

        return out

    def display_stock_analysis(self, symbol, stock_data, company_info, analysis):
        r = f"STOCK ANALYSIS: {symbol}\n"
        r += "===\n\n"

        r += "COMPANY\n" + "---\n"
        r += f"Name:     {company_info.get('name', 'Unknown')}\n"
        r += f"Sector:   {company_info.get('sector', 'Unknown')}\n"
        r += f"Industry: {company_info.get('industry', 'Unknown')}\n"
        r += f"Country:  {company_info.get('country', 'Unknown')}\n\n"

        daily_change = stock_data["c"] - stock_data["pc"]
        daily_change_percent = (daily_change / stock_data["pc"]) * 100

        r += "PRICE\n" + "---\n"
        r += f"Current:        ${stock_data['c']:.2f}\n"
        r += f"Previous close: ${stock_data['pc']:.2f}\n"
        r += f"Daily change:   {daily_change:+.2f} ({daily_change_percent:+.2f}%)\n"
        r += f"Day high/low:   ${stock_data['h']:.2f} / ${stock_data['l']:.2f}\n"
        if stock_data.get("v"):
            r += f"Volume:         {int(stock_data['v']):,}\n"
        market_cap = company_info.get("marketCap")
        if market_cap and market_cap >= 1e9:
            r += f"Market cap:     ${market_cap/1e9:.2f}B\n"
        elif market_cap and market_cap >= 1e6:
            r += f"Market cap:     ${market_cap/1e6:.2f}M\n"
        r += "\n"

        r += analysis + "\n"
        r += "---\n"
        r += f"Completed {time.strftime('%H:%M:%S')}. "
        r += "Use Chart for the last 30 days. Not financial advice.\n"

        self.insert_formatted_text(r)

    def display_portfolio_analysis(self, portfolio_text):
        self.insert_formatted_text(portfolio_text)

    def display_error(self, error_message):
        text = "ERROR\n" + "===\n\n"
        text += f"{error_message}\n\n"
        text += "Things to check:\n"
        text += "- Internet connection\n"
        text += "- Symbol spelling (e.g. AAPL, not Apple)\n"
        text += "- Yahoo Finance rate limit: wait a few minutes and retry\n"
        self.insert_formatted_text(text)

    # ------------------------------------------------------------- Data

    def get_stock_data(self, symbol):
        # ml/data.py'daki çok kaynaklı zincir: Yahoo -> Twelve Data + günlük önbellek
        try:
            from data import get_quote
            q = get_quote(symbol)
            return {"c": q["price"], "pc": q["previous_close"],
                    "h": q["high"], "l": q["low"], "v": q["volume"]}
        except Exception as e:
            logging.error(f"Error fetching stock data for {symbol}: {e}")
            return {"error": str(e)}

    def get_company_info(self, symbol):
        # fundamentals.py zinciri: Yahoo müsaitse Yahoo, değilse Finnhub
        try:
            from fundamentals import get_company_info as fetch_info
            info = fetch_info(symbol)
            return {
                "name": info["name"] or symbol,
                "industry": info["industry"],
                "sector": info["sector"],
                "country": info["country"],
                "marketCap": info["market_cap"] or 0,
            }
        except Exception as e:
            logging.error(f"Error fetching company info for {symbol}: {e}")
            return {"name": symbol, "industry": "Unknown", "sector": "Unknown",
                    "country": "Unknown", "marketCap": 0}

    def create_ai_analysis(self, symbol, data):
        current_price = data["c"]
        daily_change_percent = ((current_price - data["pc"]) / data["pc"]) * 100

        prompt = f"""You are a financial analyst. Write a short, plain-language analysis of this stock. Be concise, avoid jargon.

Stock: {symbol}
Price: ${current_price:.2f}
Change: {daily_change_percent:+.1f}%
High: ${data['h']:.2f}
Low: ${data['l']:.2f}

Short analysis and a one-word stance (BUY/HOLD/SELL):"""

        response = self.model.generate(
            prompt, max_tokens=200, temp=0.1, top_p=0.8, repeat_penalty=1.05,
        )
        analysis = response.strip()
        if len(analysis) < 10:
            raise ValueError("LLM response too short")
        return analysis + "\n"

    # ------------------------------------------------------------- Chart

    def plot_stock_price(self, symbol):
        if not symbol:
            messagebox.showwarning("Missing input", "Enter a stock symbol first.")
            return

        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates

            try:
                from data import fetch_history
                hist = fetch_history(symbol.upper(), period="1mo")
            except ImportError:
                hist = yf.Ticker(symbol.upper()).history(period="1mo")
            if hist.empty:
                messagebox.showerror("Error", f"No data found for {symbol}")
                return

            import matplotlib.ticker as mticker

            first_close = hist["Close"].iloc[0]
            last_close  = hist["Close"].iloc[-1]
            line_color  = C["gain"] if last_close >= first_close else C["loss"]

            fig, (ax, ax_vol) = plt.subplots(
                2, 1, figsize=(11, 6.5),
                gridspec_kw={"height_ratios": [3, 1], "hspace": 0.06}
            )
            fig.patch.set_facecolor(C["panel"])

            for a in (ax, ax_vol):
                a.set_facecolor(C["panel"])
                a.spines["top"].set_visible(False)
                a.spines["right"].set_visible(False)
                a.spines["left"].set_color(C["border"])
                a.spines["bottom"].set_color(C["border"])
                a.tick_params(colors=C["dim"], labelsize=9)
                a.grid(True, linestyle=":", alpha=0.5, color=C["border"])

            # Price area with subtle fill
            ax.plot(hist.index, hist["Close"],
                    linewidth=2.5, color=line_color, zorder=3)
            ax.fill_between(hist.index, hist["Close"],
                            alpha=0.08, color=line_color)

            ax.set_title(f"{symbol.upper()}  —  Last 30 Days",
                         fontsize=12, fontweight="bold",
                         color=C["text"], pad=14, loc="left")
            ax.set_ylabel("Price (USD)", color=C["dim"], fontsize=9)
            ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.0f"))
            ax.set_xticklabels([])

            # Volume subplot
            vol_color = [C["gain"] if c >= o else C["loss"]
                         for c, o in zip(hist["Close"], hist["Open"])]
            ax_vol.bar(hist.index, hist["Volume"],
                       color=vol_color, alpha=0.35, width=0.8)
            ax_vol.set_ylabel("Volume", color=C["dim"], fontsize=8)
            ax_vol.yaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
            ax_vol.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
            ax_vol.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
            plt.setp(ax_vol.get_xticklabels(), rotation=30, ha="right")

            # Current price annotation
            current_price = hist["Close"].iloc[-1]
            ax.annotate(
                f"${current_price:.2f}",
                xy=(hist.index[-1], current_price),
                xytext=(-60, 10), textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.4", fc=line_color,
                          ec="none", alpha=0.92),
                fontsize=10, fontweight="bold", color="#FFFFFF"
            )

            fig.tight_layout()
            plt.show()

        except Exception as e:
            logging.error(f"Error creating chart: {e}")
            messagebox.showerror("Error", f"Could not create chart for {symbol}: {e}")

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    try:
        print("[INFO] Starting Veriss Stock Analyzer...")
        app = StockAnalyzer()
        app.run()
    except KeyboardInterrupt:
        print("[INFO] Stopped by user")
    except Exception as e:
        print(f"[ERROR] Critical error: {e}")
        traceback.print_exc()
        logging.error(f"Critical error: {e}\n{traceback.format_exc()}")
        input("\nPress Enter to exit...")
    finally:
        print("[INFO] Application closed")
