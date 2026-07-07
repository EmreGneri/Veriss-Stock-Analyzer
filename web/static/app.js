"use strict";

const $ = (id) => document.getElementById(id);
let chart = null;
let currentSymbol = null;

/* ---------------- Status ---------------- */

async function checkHealth() {
  const dot = $("status-dot");
  const text = $("status-text");
  try {
    const r = await fetch("/api/health");
    const h = await r.json();
    if (h.ml_available && h.llm_model_present) {
      dot.className = "dot ok";
      text.textContent = "ML + LLM Ready";
    } else if (h.ml_available) {
      dot.className = "dot ok";
      text.textContent = "ML Ready (No LLM Model)";
    } else {
      dot.className = "dot warn";
      text.textContent = "Basic Mode";
    }
  } catch {
    dot.className = "dot err";
    text.textContent = "API Unreachable";
  }
}

/* ---------------- Helpers ---------------- */

function fmtNum(n) {
  return n == null ? "N/A" : n.toLocaleString("en-US");
}

function fmtPct(n) {
  if (n == null) return "N/A";
  const cls = n >= 0 ? "pos" : "neg";
  const icon = n >= 0 ? "▲" : "▼";
  return `<span class="${cls}">${icon} ${n >= 0 ? "+" : ""}${n.toFixed(2)}%</span>`;
}

function fmtCap(cap) {
  if (!cap) return "N/A";
  if (cap >= 1e9) return `$${(cap / 1e9).toFixed(2)}B`;
  if (cap >= 1e6) return `$${(cap / 1e6).toFixed(2)}M`;
  return `$${fmtNum(cap)}`;
}

function esc(s) {
  const div = document.createElement("div");
  div.textContent = String(s);
  return div.innerHTML;
}

function showLoading(msg) {
  $("results-body").innerHTML = `
    <div class="skeleton">
      <div class="skeleton-block">
        <div class="skeleton-line w40"></div>
        <div class="skeleton-line w90"></div>
        <div class="skeleton-line w70"></div>
      </div>
      <div class="skeleton-block">
        <div class="skeleton-line tall"></div>
        <div class="skeleton-line w70"></div>
        <div class="skeleton-line w40"></div>
      </div>
      <div class="skeleton-block">
        <div class="skeleton-line w40"></div>
        <div class="skeleton-line w90"></div>
        <div class="skeleton-line w90"></div>
        <div class="skeleton-line w70"></div>
      </div>
      <p class="skeleton-note">${esc(msg)}</p>
    </div>`;
}

function showError(msg) {
  $("results-body").innerHTML = `
    <div class="error-box">
      <strong>Analysis Error</strong>
      ${esc(msg)}
      <br><br>
      Please check the symbol spelling, verify your connection, or wait a few minutes if Yahoo Finance is rate-limiting requests.
    </div>`;
}

/* ---------------- Analyze ---------------- */

async function analyze() {
  const query = $("query").value.trim();
  if (!query) return;

  const btn = $("btn-analyze");
  btn.disabled = true;
  btn.textContent = "Analyzing...";
  showLoading("Analyzing... first run for a new symbol trains a model (about a minute).");
  $("chart-card").hidden = true;

  try {
    const useLlm = $("use-llm").checked;
    const r = await fetch(`/api/analyze/${encodeURIComponent(query)}?llm=${useLlm}`);
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const data = await r.json();
    if (data.type === "portfolio") {
      renderPortfolio(data);
    } else {
      renderStock(data);
      loadChart(data.symbol, "1mo");
    }
  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Analyze";
  }
}

function renderStock(d) {
  const p = d.price;
  const c = d.company;
  let html = "";

  // Company Section
  html += `<div class="result-section">
    <div class="result-section-title">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px; height:14px; color:var(--primary);"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><line x1="9" y1="22" x2="9" y2="16"></line><line x1="15" y1="22" x2="15" y2="16"></line><line x1="9" y1="16" x2="15" y2="16"></line><path d="M9 6h6"></path><path d="M9 10h6"></path></svg>
      <span>Company Profile</span>
    </div>
    <div class="info-grid">
      <div class="info-item">
        <span class="info-label">Name</span>
        <span class="info-value">${esc(c.name)}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Sector</span>
        <span class="info-value">${esc(c.sector)}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Industry</span>
        <span class="info-value">${esc(c.industry)}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Country</span>
        <span class="info-value">${esc(c.country)}</span>
      </div>
    </div>
  </div>`;

  // Price Section
  html += `<div class="result-section">
    <div class="result-section-title">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px; height:14px; color:var(--primary);"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><path d="M9.5 10.5h5a2.5 2.5 0 0 1 0 5h-5a2.5 2.5 0 0 1 0-5z"></path></svg>
      <span>Market Price</span>
    </div>
    <div class="price-showcase">
      <span class="price-main">$${p.price.toFixed(2)}</span>
      <span class="price-diff">${fmtPct(p.change_pct)}</span>
    </div>
    <div class="info-grid">
      <div class="info-item">
        <span class="info-label">Daily Change</span>
        <span class="info-value ${p.change >= 0 ? "pos" : "neg"}">${p.change >= 0 ? "+" : ""}$${p.change.toFixed(2)}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Prev Close</span>
        <span class="info-value">$${p.previous_close.toFixed(2)}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Day Range</span>
        <span class="info-value">$${p.low.toFixed(2)} - $${p.high.toFixed(2)}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Volume</span>
        <span class="info-value">${fmtNum(p.volume)}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Market Cap</span>
        <span class="info-value">${fmtCap(c.market_cap)}</span>
      </div>
    </div>
  </div>`;

  // ML Signal Section
  const s = d.ml_signal;
  html += `<div class="result-section">
    <div class="result-section-title">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px; height:14px; color:var(--primary);"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
      <span>ML Analytics (${esc((s && s.model_name) || "ML")})</span>
    </div>`;
  
  if (!s) {
    html += `<p class="dim">ML analysis model is currently unavailable.</p>`;
  } else if (s.error) {
    html += `<p class="dim">Analysis failed: ${esc(s.error)}</p>`;
  } else {
    const cls = s.signal === "BUY" ? "buy" : s.signal === "SELL" ? "sell" : "hold";
    const probPct = (s.probability_up * 100).toFixed(1);
    html += `
      <div class="signal-row">
        <span class="signal-badge ${cls}">${esc(s.signal)}</span>
        <div class="confidence-container">
          <div class="confidence-header">
            <span>Trend Confidence Indicator</span>
            <span class="confidence-value">${probPct}% P(Up)</span>
          </div>
          <div class="confidence-track">
            <div class="confidence-bar ${cls}" style="transform: scaleX(${s.probability_up.toFixed(3)})"></div>
          </div>
        </div>
      </div>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">RSI (14)</span>
          <span class="info-value">${s.rsi_14.toFixed(1)}</span>
        </div>
        <div class="info-item">
          <span class="info-label">SMA5 / SMA20</span>
          <span class="info-value">${s.sma_ratio.toFixed(3)}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Model Accuracy</span>
          <span class="info-value">${(s.model_test_accuracy * 100).toFixed(1)}% <span class="dim" style="font-size: 11px; font-weight: normal;">(F1 ${s.model_test_f1.toFixed(2)})</span></span>
        </div>
        <div class="info-item">
          <span class="info-label">Updated As Of</span>
          <span class="info-value dim" style="font-size: 13px;">${esc(s.as_of)}</span>
        </div>
      </div>`;
    if (s.explanation) {
      html += `
      <div class="ml-explanation">
        <div class="ml-explanation-title">Why ${esc(s.signal)}?</div>
        <p>${esc(s.explanation)}</p>
      </div>`;
    }
  }
  html += `</div>`;

  // LLM Commentary Section
  if (d.commentary) {
    html += `<div class="result-section">
      <div class="result-section-title">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px; height:14px; color:var(--primary);"><path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m11.314 11.314l.707.707M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"></path></svg>
        <span>AI Market Commentary</span>
      </div>
      <div class="commentary-text">
        <p>${esc(d.commentary)}</p>
      </div>
    </div>`;
  }

  html += `<p class="dim" style="font-size:12px; margin-top: 14px; text-align: center;">Educational tool — not financial advice.</p>`;
  $("results-body").innerHTML = html;
}

function renderPortfolio(d) {
  let rows = d.holdings.map((h) => {
    const price = h.price == null ? `<span class="dim">N/A</span>` : `$${h.price.toFixed(2)}`;
    const chg = h.change_pct == null ? `<span class="dim">–</span>` : fmtPct(h.change_pct);
    return `<tr onclick="quickAnalyze('${esc(h.symbol)}')">
      <td style="font-weight: 600; color: var(--text);">${esc(h.symbol)}</td>
      <td class="num">${price}</td>
      <td class="num">${chg}</td>
    </tr>`;
  }).join("");

  $("results-body").innerHTML = `
    <div class="result-section">
      <div class="result-section-title">Portfolio Holdings — ${esc(d.investor)}</div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th class="num">Price</th>
              <th class="num">Change</th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
      </div>
      <p class="dim" style="margin-top:14px; font-size:12px; text-align: center;">
        Click any row to run a machine learning analysis on that stock.
      </p>
    </div>`;
}

function quickAnalyze(symbol) {
  $("query").value = symbol;
  analyze();
}

/* ---------------- Chart ---------------- */

async function loadChart(symbol, period) {
  try {
    const r = await fetch(`/api/history/${encodeURIComponent(symbol)}?period=${period}`);
    if (!r.ok) return;
    const d = await r.json();

    currentSymbol = symbol;
    $("chart-card").hidden = false;
    $("chart-title").textContent = `${symbol} — Price History`;

    document.querySelectorAll("#period-btns button").forEach((b) =>
      b.classList.toggle("active", b.dataset.period === period));

    const css = getComputedStyle(document.documentElement);
    const primary = css.getPropertyValue("--primary").trim() || "#38bdf8";
    const dim = css.getPropertyValue("--dim").trim() || "#9ca3af";
    const border = css.getPropertyValue("--border").trim() || "rgba(255, 255, 255, 0.08)";

    if (chart) chart.destroy();
    chart = new Chart($("chart"), {
      type: "line",
      data: {
        labels: d.dates,
        datasets: [{
          data: d.close,
          borderColor: primary,
          backgroundColor: primary + "15",
          fill: true,
          tension: 0.25,
          pointRadius: 0,
          borderWidth: 2,
        }],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: dim, maxTicksLimit: 8 }, grid: { color: border } },
          y: { ticks: { color: dim, callback: (v) => "$" + v }, grid: { color: border } },
        },
        interaction: { intersect: false, mode: "index" },
      },
    });
  } catch {
    /* grafik kritik değil; sessizce geç */
  }
}

/* ---------------- Sample Portfolio ---------------- */

async function loadSamplePortfolio() {
  const tbody = document.querySelector("#portfolio-table tbody");
  tbody.innerHTML = `<tr><td colspan="5" class="dim">Loading...</td></tr>`;
  try {
    const r = await fetch("/api/sample-portfolio");
    const d = await r.json();
    tbody.innerHTML = d.holdings.map((h) => `
      <tr onclick="quickAnalyze('${esc(h.symbol)}')">
        <td style="font-weight: 600; color: var(--text);">${esc(h.symbol)}</td>
        <td>${esc(h.name)}</td>
        <td class="num">${h.price == null ? "N/A" : "$" + h.price.toFixed(2)}</td>
        <td class="num">${h.pe == null ? "N/A" : h.pe.toFixed(1)}</td>
        <td class="num">${h.market_cap_b == null ? "N/A" : "$" + h.market_cap_b + "B"}</td>
      </tr>`).join("");
  } catch {
    tbody.innerHTML = `<tr><td colspan="5" class="dim">Could not load (rate limit?). Try Refresh.</td></tr>`;
  }
}

/* ---------------- Wire up ---------------- */

$("btn-analyze").addEventListener("click", analyze);
$("query").addEventListener("keydown", (e) => { if (e.key === "Enter") analyze(); });
$("btn-refresh").addEventListener("click", loadSamplePortfolio);
document.querySelectorAll("#period-btns button").forEach((b) =>
  b.addEventListener("click", () => currentSymbol && loadChart(currentSymbol, b.dataset.period)));

// Setup event listeners for hint tag pills
document.querySelectorAll(".hint-tag").forEach((t) => {
  t.addEventListener("click", () => {
    $("query").value = t.dataset.query;
    analyze();
  });
});

/* ---------------- Welcome market pulse ---------------- */

async function initWelcomePulse() {
  const canvas = $("welcome-pulse-chart");
  if (!canvas || typeof Chart === "undefined") return;
  try {
    const r = await fetch("/api/history/AAPL?period=3mo");
    if (!r.ok) throw new Error();
    const d = await r.json();

    const css = getComputedStyle(document.documentElement);
    const primary = css.getPropertyValue("--primary").trim() || "#10b981";

    new Chart(canvas, {
      type: "line",
      data: {
        labels: d.dates,
        datasets: [{
          data: d.close,
          borderColor: primary,
          backgroundColor: primary + "18",
          fill: true,
          tension: 0.3,
          pointRadius: 0,
          pointHitRadius: 12,
          borderWidth: 2,
        }],
      },
      options: {
        animation: { duration: 1400, easing: "easeOutQuart" },
        plugins: {
          legend: { display: false },
          tooltip: {
            intersect: false,
            mode: "index",
            displayColors: false,
            callbacks: { label: (ctx) => "$" + ctx.parsed.y.toFixed(2) },
          },
        },
        scales: { x: { display: false }, y: { display: false } },
        interaction: { intersect: false, mode: "index" },
        maintainAspectRatio: false,
      },
    });

    const first = d.close[0];
    const last = d.close[d.close.length - 1];
    const chg = ((last - first) / first) * 100;
    const label = $("welcome-pulse-label");
    if (label) {
      label.innerHTML =
        `${esc(d.symbol)} — last 3 months — $${last.toFixed(2)} ` +
        `<span class="${chg >= 0 ? "pos" : "neg"}">${chg >= 0 ? "+" : ""}${chg.toFixed(1)}%</span>`;
    }
  } catch {
    const box = $("welcome-pulse");
    if (box) box.hidden = true;
  }
}

checkHealth();
loadSamplePortfolio();
initWelcomePulse();
