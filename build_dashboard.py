"""
build_dashboard.py — generuje samodzielny dashboard.html (jeden plik,
wszystko wbudowane) z wynikami TIMDR-Finanse: wykresy jako base64, tabele
wyników, uczciwe wnioski. Uruchamiane przez run.bat po backteście.
"""
import base64
import pathlib

def img_b64(path):
    return base64.b64encode(pathlib.Path(path).read_bytes()).decode('ascii')

anom_b64 = img_b64('chart_btc_anomalies.png')
vol_b64 = img_b64('chart_vol_forecast.png')

HTML = f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TIMDR-Finanse — wyniki testu na realnych danych BTC/USD</title>
<style>
  :root {{
    --ink: #1a1a1a; --sub: #555; --muted: #9ca3af;
    --good: #2b6cb0; --bad: #c2410c; --bg: #fafafa; --card: #ffffff;
    --border: #e5e7eb;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0 0 60px 0; background: var(--bg); color: var(--ink);
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    line-height: 1.55;
  }}
  header {{
    background: var(--ink); color: #fff; padding: 36px 24px 28px;
  }}
  header h1 {{ margin: 0 0 6px; font-size: 1.6rem; }}
  header p {{ margin: 0; color: #d4d4d4; max-width: 900px; font-size: 0.95rem; }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 0 24px; }}
  .verdict {{
    background: #fff7ed; border: 1px solid #fed7aa; border-radius: 10px;
    padding: 18px 22px; margin: 28px 0; font-size: 0.98rem;
  }}
  .verdict b {{ color: var(--bad); }}
  section {{ margin: 38px 0; }}
  h2 {{ font-size: 1.2rem; border-bottom: 2px solid var(--border); padding-bottom: 8px; }}
  .card {{
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 18px 22px; margin: 14px 0;
  }}
  img {{ max-width: 100%; border-radius: 6px; display: block; margin: 10px auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; margin: 10px 0; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--sub); font-weight: 600; background: #f3f4f6; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .tag {{ display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }}
  .tag.yes {{ background: #dbeafe; color: #1e40af; }}
  .tag.no {{ background: #fee2e2; color: #991b1b; }}
  .tag.partial {{ background: #fef3c7; color: #92400e; }}
  footer {{ text-align: center; color: var(--muted); font-size: 0.82rem; margin-top: 50px; }}
  code {{ background: #f3f4f6; padding: 1px 6px; border-radius: 4px; font-size: 0.88em; }}
</style>
</head>
<body>

<header>
  <div class="wrap">
    <h1>TIMDR-Finanse — test na realnych danych BTC/USD</h1>
    <p>Kauzalny walk-forward backtest sygnałów TRM/FLOW/TWIST/RHYTHM na 720 świecach
    1h BTC/USD (Kraken, 2026-07-18 – 2026-08-17), oceniony wobec uczciwych baseline'ów
    (persystencja zmienności, rzut monetą / baza rynkowa). Kod i dane w załączonym
    archiwum.</p>
  </div>
</header>

<div class="wrap">

  <div class="verdict">
    <b>Krótka odpowiedź: w większości — nie.</b> Rynki, w przeciwieństwie do trzęsień
    ziemi czy pogody, są adwersarialne — aktywni uczestnicy arbitrażują łatwo
    wykrywalne wzorce. Jedyny "działający" sygnał (persystencja zmienności) to znany
    efekt niezależny od TIMDR; komponenty predykcyjne TIMDR (<code>flow_sigma</code>,
    <code>flow</code> jako predyktor kierunku) nie biją prostych baseline'ów w tym teście.
  </div>

  <section>
    <h2>Podsumowanie wyników</h2>
    <div class="card">
      <table>
        <tr><th>Sygnał</th><th>Realna przewaga nad baseline'em?</th><th>Dowód</th></tr>
        <tr><td>Persystencja zmienności (baseline, bez TIMDR)</td><td><span class="tag yes">TAK</span> r=0.38</td><td>182 pkt walk-forward</td></tr>
        <tr><td>TIMDR <code>flow_sigma</code> (korekta trendu zmienności)</td><td><span class="tag no">NIE</span> r=0.02, +0,0% out-of-sample</td><td>to samo</td></tr>
        <tr><td>TIMDR <code>flow</code> na cenie → kierunek zwrotu</td><td><span class="tag no">NIE</span> gorzej niż "zawsze w górę"</td><td>182 pkt walk-forward</td></tr>
        <tr><td><code>anomalies()</code> jako narzędzie opisowe</td><td><span class="tag yes">TAK</span> poprawnie wskazuje duże ruchy</td><td>38/720 świec, kontrola pozytywna</td></tr>
        <tr><td><code>rhythm()</code> na wolumenie (cykl dobowy)</td><td><span class="tag partial">CZĘŚCIOWO</span> realny (0.20), ale słaby i zdominowany przez lag=1h (0.54)</td><td>diagnostyka autokorelacji</td></tr>
      </table>
    </div>
  </section>

  <section>
    <h2>Test 1 — prognoza zmienności (kolejne 6h)</h2>
    <div class="card">
      <img src="data:image/png;base64,{vol_b64}" alt="Prognoza zmienności BTC/USD">
      <table>
        <tr><th>Metoda</th><th class="num">MAE</th><th class="num">Korelacja r</th></tr>
        <tr><td>Naiwna persystencja (24h)</td><td class="num">0.000947</td><td class="num">0.381</td></tr>
        <tr><td>Długoterminowa średnia</td><td class="num">0.001062</td><td class="num">—</td></tr>
        <tr><td>TIMDR flow_sigma</td><td class="num">—</td><td class="num">0.019</td></tr>
      </table>
      <p>Out-of-sample: MAE persystencji = 0.000711, + korekta flow_sigma = 0.000711
      (poprawa <b>+0,0%</b>, najlepsze dopasowane α=0 na danych treningowych — czyli
      "nie używaj flow_sigma wcale").</p>
    </div>
  </section>

  <section>
    <h2>Test 2 — prognoza kierunku (kolejne 6h)</h2>
    <div class="card">
      <table>
        <tr><th>Strategia</th><th class="num">Trafność</th></tr>
        <tr><td>FLOW → kontynuacja trendu</td><td class="num">0.473</td></tr>
        <tr><td>FLOW → odwrócenie (mean-reversion)</td><td class="num">0.527</td></tr>
        <tr><td>Baseline "zawsze w górę"</td><td class="num">0.544</td></tr>
        <tr><td>Rzut monetą</td><td class="num">0.500</td></tr>
      </table>
      <p>Żadna wersja FLOW nie bije nawet najprostszego baseline'u. Zgodne z
      hipotezą rynku efektywnego dla tak krótkiego horyzontu.</p>
    </div>
  </section>

  <section>
    <h2>Test 3 — kontrole: anomalie i rytm</h2>
    <div class="card">
      <img src="data:image/png;base64,{anom_b64}" alt="Anomalie na cenie BTC/USD">
      <p><b>3a. anomalies()</b> — 38 anomalii wykryte na 720 świecach (|MAD-z|&gt;3.0),
      poprawnie oznaczone jako największe realne ruchy w próbce. Działa jako narzędzie
      <i>opisowe</i> (co się już wydarzyło), nie predykcyjne.</p>
      <table>
        <tr><th>Lag (h)</th><th class="num">Autokorelacja wolumenu</th></tr>
        <tr><td>1 (najsilniejsza)</td><td class="num">0.540</td></tr>
        <tr><td>7</td><td class="num">0.079</td></tr>
        <tr><td>24 (cykl dobowy)</td><td class="num">0.200</td></tr>
        <tr><td>36</td><td class="num">-0.110</td></tr>
        <tr><td>47</td><td class="num">0.132</td></tr>
      </table>
      <p><b>3b. rhythm()</b> — przy standardowym progu (0.4) nie zgłasza cyklu 24h
      (score=0.000). Diagnostyka pokazuje realną, ale słabą autokorelację przy lag=24h
      (0.20), zdominowaną przez znacznie silniejsze krótkoterminowe klastrowanie
      wolumenu (lag=1h, 0.54). Prawdopodobne wyjaśnienie: BTC handlowany 24/7 na całym
      świecie rozmywa pojedynczy regionalny cykl dobowy.</p>
    </div>
  </section>

  <section>
    <h2>Metodologia</h2>
    <div class="card">
      <p>Dane: <code>api.kraken.com/0/public/OHLC?pair=XBTUSD&amp;interval=60</code>,
      pobrane na żywo, zweryfikowane wewnętrznie (równe odstępy 3600s, zero luk).
      Wszystkie prognozy liczone <b>kauzalnie</b> — w chwili D wyłącznie dane sprzed D.
      Współczynnik korekty w Teście 1 dobrany metodą out-of-sample (1. połowa danych
      do dopasowania, 2. połowa do oceny). 24 testy jednostkowe, wszystkie przechodzą
      (<code>test_timdr_core_finance.py</code>).</p>
      <p>Ograniczenia: jeden miesiąc, jeden instrument; brak danych order booku/tickowych
      (delta/spread to udokumentowane przybliżenia z OHLCV); nakładające się okna
      walk-forward (nie w pełni niezależne statystycznie). Pełny opis w
      <code>RAPORT_TIMDR_Finanse.md</code>.</p>
    </div>
  </section>

</div>

<footer>TIMDR-Finanse · wygenerowano lokalnie przez build_dashboard.py · dane: Kraken (BTC/USD)</footer>

</body>
</html>
"""

with open('dashboard.html', 'w', encoding='utf-8') as f:
    f.write(HTML)
print('saved dashboard.html')
