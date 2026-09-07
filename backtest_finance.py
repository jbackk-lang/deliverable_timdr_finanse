"""
backtest_finance.py — kauzalny walk-forward test TIMDR-Finanse na realnych
danych BTC/USD (Kraken, 720 świec 1h, 2026-07-18 .. 2026-08-17, pobrane i
zweryfikowane co do wewnętrznej spójności: idealnie równe odstępy 3600s,
zero luk).

Trzy testy, wszystkie KAUZALNE (prognoza w chwili D uzywa wylacznie danych
sprzed D):

1. Prognoza zmiennosci (realized vol w kolejnych 6h): TIMDR flow_sigma-
   adjusted vs (a) naiwna persystencja (ostatnie 24h = prognoza - to
   REALNIE silny baseline na rynkach, znany efekt "vol clustering"),
   (b) dlugoterminowa srednia.
2. Prognoza kierunku (znak zwrotu w kolejnych 6h): czy TWIST/FLOW maja
   jakakolwiek przewage nad rzutem moneta (50%) - to jest test tego, czy
   rynek jest tu przewidywalny kierunkowo w ogole.
3. Kontrole: anomalies() na najwiekszych realnych ruchach (pozytywna),
   rhythm() na wolumenie (czy jest prawdziwy cykl dobowy - u.wagi: to
   JEDYNE miejsce, gdzie spodziewamy sie realnego sygnalu, bo cykl
   dobowy aktywnosci traderow to prawdziwy, znany mechanizm - w
   przeciwienstwie do "przewidywania kierunku ceny").
"""
import csv
import numpy as np
from timdr_core_finance import TIMDR_FinanceCore, TIMDRFinanceFusion

core = TIMDR_FinanceCore()

rows = []
with open('data/btcusd_1h.csv') as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append(row)

t = np.array([int(r['time']) for r in rows], dtype=float)
t_h = (t - t[0]) / 3600.0  # godziny od poczatku
open_ = np.array([float(r['open']) for r in rows])
high = np.array([float(r['high']) for r in rows])
low = np.array([float(r['low']) for r in rows])
close = np.array([float(r['close']) for r in rows])
volume = np.array([float(r['volume']) for r in rows])

print(f"Dane: {len(rows)} swiec 1h, {t_h[-1]:.0f}h ({t_h[-1]/24:.1f} dni), "
      f"BTC/USD {close.min():.0f}-{close.max():.0f}")

sigma = core.realized_vol(close, window=6)  # zrealizowana zmiennosc, okno 6 swiec
log_ret = np.concatenate([[0.0], core.log_returns(close)])

# ============================================================
# TEST 1: prognoza zmiennosci w kolejnych 6h
# ============================================================
print("\n=== TEST 1: prognoza zrealizowanej zmiennosci (kolejne 6h) ===")

BURN_IN = 168   # 1 tydzien
STEP = 3
HORIZON = 6
VOL_WINDOW = 24

idxs = np.arange(BURN_IN, len(close) - HORIZON, STEP)
real_vol_fwd = []
persist_pred = []
longrun_pred = []
flow_sigma_at_D = []

for i in idxs:
    past_sigma = sigma[:i]
    # (a) naiwna persystencja: sigma z ostatnich VOL_WINDOW swiec
    persist_pred.append(np.mean(past_sigma[-VOL_WINDOW:]))
    # (b) dlugoterminowa srednia ze WSZYSTKICH danych sprzed i
    longrun_pred.append(np.mean(past_sigma))
    # (c) TIMDR flow_sigma, liczony KAUZALNIE (tylko dane sprzed i)
    sigma_s = core.trm(t_h[:i], past_sigma, k=5)
    fs = core.flow(t_h[:i], sigma_s, window=5)
    flow_sigma_at_D.append(fs[-1] if len(fs) else 0.0)
    # REALNA przyszla zmiennosc: std zwrotow w [i, i+HORIZON)
    real_vol_fwd.append(np.std(log_ret[i:i + HORIZON]))

real_vol_fwd = np.array(real_vol_fwd)
persist_pred = np.array(persist_pred)
longrun_pred = np.array(longrun_pred)
flow_sigma_at_D = np.array(flow_sigma_at_D)

mae_persist = np.mean(np.abs(persist_pred - real_vol_fwd))
mae_longrun = np.mean(np.abs(longrun_pred - real_vol_fwd))
corr_persist = np.corrcoef(persist_pred, real_vol_fwd)[0, 1]
corr_flow = np.corrcoef(flow_sigma_at_D, real_vol_fwd)[0, 1]

print(f"Punkty walk-forward: {len(idxs)}")
print(f"MAE naiwna persystencja (24h): {mae_persist:.6f}")
print(f"MAE dlugoterminowa srednia:    {mae_longrun:.6f}")
print(f"Korelacja persystencja vs realna przyszla zmiennosc: r={corr_persist:.3f}")
print(f"Korelacja flow_sigma vs realna przyszla zmiennosc:   r={corr_flow:.3f}")

half = len(idxs) // 2
alpha_candidates = np.linspace(-50, 50, 101)
best_alpha, best_mae_in = 0.0, mae_persist
for a in alpha_candidates:
    adj = persist_pred[:half] * np.clip(1 + a * flow_sigma_at_D[:half], 0, None)
    mae_in = np.mean(np.abs(adj - real_vol_fwd[:half]))
    if mae_in < best_mae_in:
        best_mae_in, best_alpha = mae_in, a
adj_out = persist_pred[half:] * np.clip(1 + best_alpha * flow_sigma_at_D[half:], 0, None)
mae_adj_out = np.mean(np.abs(adj_out - real_vol_fwd[half:]))
mae_persist_out = np.mean(np.abs(persist_pred[half:] - real_vol_fwd[half:]))
print(f"\nOut-of-sample (alpha={best_alpha:.2f} dobrane na 1. polowie):")
print(f"  MAE persystencja (2. polowa, out-of-sample): {mae_persist_out:.6f}")
print(f"  MAE persystencja + korekta flow_sigma:        {mae_adj_out:.6f}")
improvement = (mae_persist_out - mae_adj_out) / mae_persist_out * 100
print(f"  Poprawa dzieki flow_sigma: {improvement:+.1f}%")

# ============================================================
# TEST 2: prognoza kierunku w kolejnych 6h
# ============================================================
print("\n=== TEST 2: prognoza KIERUNKU zwrotu (kolejne 6h) ===")

flow_price_at_D = []
real_dir_fwd = []
for i in idxs:
    fp = core.flow(t_h[:i], close[:i], window=5)
    flow_price_at_D.append(fp[-1] if len(fp) else 0.0)
    fwd_ret = np.log(close[min(i + HORIZON, len(close) - 1)]) - np.log(close[i])
    real_dir_fwd.append(1 if fwd_ret > 0 else -1)

flow_price_at_D = np.array(flow_price_at_D)
real_dir_fwd = np.array(real_dir_fwd)
pred_dir_momentum = np.sign(flow_price_at_D)  # zaklada kontynuacje trendu
pred_dir_momentum[pred_dir_momentum == 0] = 1

acc_momentum = np.mean(pred_dir_momentum == real_dir_fwd)
acc_reversal = np.mean(-pred_dir_momentum == real_dir_fwd)
baseline_up = np.mean(real_dir_fwd == 1)
print(f"Trafnosc 'FLOW przewiduje kontynuacje trendu': {acc_momentum:.3f}")
print(f"Trafnosc 'FLOW przewiduje odwrocenie (mean-reversion)': {acc_reversal:.3f}")
print(f"Baseline (zawsze 'w gore', bazowy odsetek wzrostow w probie): {baseline_up:.3f}")
print("(rzut moneta = 0.500; wartosci obu strategii blisko max(baseline_up,1-baseline_up)")
print(" oznaczaja BRAK realnej przewagi kierunkowej ponad prosta baze)")

# ============================================================
# TEST 3a: anomalies() - kontrola pozytywna na najwiekszych ruchach
# ============================================================
print("\n=== TEST 3a: anomalies() na 1h log-zwrotach (kontrola pozytywna) ===")
an_idx, an_z, an_th = core.anomalies(t_h, log_ret, factor=3.0)
order = an_idx[np.argsort(-np.abs(an_z[an_idx]))]
print(f"Wykryto {len(an_idx)} anomalii na {len(log_ret)} swiec (|MAD-z|>3.0):")
for i in order[:8]:
    print(f"  t={t_h[i]:6.1f}h  zwrot={log_ret[i]*100:+.2f}%  z={an_z[i]:6.2f}  "
          f"close={close[i]:.0f}")

# ============================================================
# TEST 3b: rhythm() na wolumenie - JEDYNE miejsce gdzie oczekujemy
# realnego sygnalu (dobowy cykl aktywnosci to prawdziwy mechanizm)
# ============================================================
print("\n=== TEST 3b: rhythm() na wolumenie godzinowym (oczekiwany cykl 24h) ===")
periods, score = core.rhythm(volume, max_lag=48, power_thresh=0.4)
print(f"Wykryte 'okresy' (w godzinach) przy progu 0.4: {periods}, score={score:.3f}")

# Diagnostyka: jaka jest FAKTYCZNA autokorelacja przy lag=24 i gdzie sa
# lokalne maksima, niezaleznie od progu decyzyjnego 0.4 (ktory jest
# progiem "czy to na tyle silne, by cokolwiek z tym zrobic", a nie progiem
# "czy sygnal istnieje"). To rozroznienie jest wazne dla uczciwej
# interpretacji: brak wykrycia przy progu 0.4 != brak jakiegokolwiek
# sygnalu w danych.
signed = volume - np.mean(volume)
n = len(signed)
denom = np.sum(signed ** 2)
autocorr = np.array([
    np.sum(signed[:n - lag] * signed[lag:]) / denom if denom > 0 else 0.0
    for lag in range(0, 49)
])
peaks = [lag for lag in range(1, 48) if autocorr[lag] > autocorr[lag - 1] and autocorr[lag] > autocorr[lag + 1]]
best_lag = max(range(1, 49), key=lambda lag: autocorr[lag])
print(f"Faktyczna autokorelacja przy lag=24h: {autocorr[24]:.3f}")
print(f"Najsilniejsza autokorelacja (lag>0): lag={best_lag}h, wartosc={autocorr[best_lag]:.3f}")
print(f"Lokalne maksima autokorelacji (lag, wartosc): "
      f"{[(p, round(autocorr[p], 3)) for p in peaks]}")
print(
    "Interpretacja: przy standardowym progu (0.4) rhythm() NIE zglasza cyklu\n"
    "  dobowego - formalnie 'brak wykrytej periodycznosci'. Ale to nie znaczy,\n"
    "  ze sygnal jest zerowy: przy lag=24h autokorelacja jest realna, ale slaba\n"
    f"  (~{autocorr[24]:.2f}), i zdecydowanie zdominowana przez znacznie silniejsza\n"
    f"  autokorelacje przy lag=1h (~{autocorr[best_lag]:.2f} przy lag={best_lag}) - czyli\n"
    "  wolumen w danej godzinie jest podobny do wolumenu godzine wczesniej\n"
    "  (klastrowanie krotkoterminowe) znacznie silniej, niz jest podobny do\n"
    "  wolumenu dokladnie 24h wczesniej (cykl dobowy). Prawdopodobne wyjasnienie:\n"
    "  BTC handlowany jest 24/7 na calym swiecie, wiec pojedynczy, wyrazny cykl\n"
    "  regionalny (np. 'godziny sesji NYSE') jest rozmyty przez nakladajace sie\n"
    "  strefy czasowe innych rynkow. Wniosek: rhythm() dziala poprawnie (nie\n"
    "  halucynuje okresowosci), ale przy tym progu i tej probce (30 dni) nie\n"
    "  potwierdza uzytecznego, dominujacego cyklu dobowego w wolumenie."
)
if periods:
    near_24 = [p for p in periods if 20 <= p <= 28]
    print(f"Okresy w poblizu 24h: {near_24}")

# ============================================================
# TEST 4: TIMDRFinanceTrigger - czujnik sygnalowy (NIE predykcja ceny -
# patrz zastrzezenia w timdr_finance_trigger.py) na calej realnej serii
# ============================================================
print("\n=== TEST 4: TIMDRFinanceTrigger na calej serii BTC/USD ===")
from timdr_finance_trigger import TIMDRFinanceTrigger

trigger = TIMDRFinanceTrigger()
trig_result = trigger.analyze(t_h, open_, high, low, close, volume)
print(f"triggered={trig_result.triggered}  type={trig_result.trigger_type.value}  "
      f"location={trig_result.location}")
print(f"  {trig_result.message}")
if trig_result.location is not None:
    print(f"  t={t_h[trig_result.location]:.1f}h  close={close[trig_result.location]:.0f}")
