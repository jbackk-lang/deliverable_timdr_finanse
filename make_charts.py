"""
make_charts.py — wykresy do raportu TIMDR-Finanse. Styl i paleta spójne
z wykresami TIMDR-Earthquake-Core (make_charts.py w tamtym repo).
"""
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from timdr_core_finance import TIMDR_FinanceCore

plt.rcParams.update({
    'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': '#888888', 'axes.labelcolor': '#333333',
    'xtick.color': '#555555', 'ytick.color': '#555555',
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
})

COL_REAL = '#1a1a1a'
COL_ANOM_UP = '#2b6cb0'
COL_ANOM_DOWN = '#c2410c'
COL_NAIVE = '#9ca3af'
COL_FLOW = '#7c3aed'

core = TIMDR_FinanceCore()

rows = []
with open('data/btcusd_1h.csv') as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append(row)

t = np.array([int(r['time']) for r in rows], dtype=float)
t_h = (t - t[0]) / 3600.0
open_ = np.array([float(r['open']) for r in rows])
high = np.array([float(r['high']) for r in rows])
low = np.array([float(r['low']) for r in rows])
close = np.array([float(r['close']) for r in rows])
volume = np.array([float(r['volume']) for r in rows])
log_ret = np.concatenate([[0.0], core.log_returns(close)])

# ---------------------------------------------------------------
# Chart 1: cena BTC/USD (30 dni) + anomalie z anomalies() na 1h zwrotach
# (kontrola pozytywna: anomalies() dziala tak samo na rynkach jak na
# katalogu sejsmicznym - wykrywa realne, duze ruchy)
# ---------------------------------------------------------------
an_idx, an_z, an_th = core.anomalies(t_h, log_ret, factor=3.0)
up = an_idx[log_ret[an_idx] > 0]
down = an_idx[log_ret[an_idx] < 0]

fig, ax = plt.subplots(figsize=(9.5, 5.5))
ax.plot(t_h / 24.0, close, color=COL_REAL, lw=1.0, label='BTC/USD, świece 1h (Kraken)', zorder=2)
ax.scatter(t_h[up] / 24.0, close[up], color=COL_ANOM_UP, s=45, zorder=3, marker='^',
           label=f'anomalies(): skok w górę >3×MAD (n={len(up)})')
ax.scatter(t_h[down] / 24.0, close[down], color=COL_ANOM_DOWN, s=45, zorder=3, marker='v',
           label=f'anomalies(): skok w dół >3×MAD (n={len(down)})')
ax.set_xlabel('Dni od 2026-07-18')
ax.set_ylabel('Cena BTC/USD')
ax.set_title('BTC/USD, 30 dni (720 świec 1h) — anomalie 1h-zwrotów wykryte przez TIMDR anomalies()', fontsize=12)
ax.legend(fontsize=8.5, loc='upper left')
fig.tight_layout()
fig.savefig('chart_btc_anomalies.png', dpi=150)
print('saved chart_btc_anomalies.png')

# ---------------------------------------------------------------
# Chart 2: prognoza zmiennosci (out-of-sample) - persystencja vs realna
# przyszla zmiennosc, plus flow_sigma pokazany jako brak dodatkowej
# wartosci (r=0.019, patrz raport)
# ---------------------------------------------------------------
BURN_IN, STEP, HORIZON, VOL_WINDOW = 168, 3, 6, 24
sigma = core.realized_vol(close, window=6)
idxs = np.arange(BURN_IN, len(close) - HORIZON, STEP)
real_vol_fwd, persist_pred, flow_sigma_at_D = [], [], []
for i in idxs:
    past_sigma = sigma[:i]
    persist_pred.append(np.mean(past_sigma[-VOL_WINDOW:]))
    sigma_s = core.trm(t_h[:i], past_sigma, k=5)
    fs = core.flow(t_h[:i], sigma_s, window=5)
    flow_sigma_at_D.append(fs[-1] if len(fs) else 0.0)
    real_vol_fwd.append(np.std(log_ret[i:i + HORIZON]))
real_vol_fwd = np.array(real_vol_fwd)
persist_pred = np.array(persist_pred)
flow_sigma_at_D = np.array(flow_sigma_at_D)
r_persist = np.corrcoef(persist_pred, real_vol_fwd)[0, 1]
r_flow = np.corrcoef(flow_sigma_at_D, real_vol_fwd)[0, 1]

fig, axes = plt.subplots(1, 2, figsize=(10.5, 5))
axes[0].scatter(persist_pred, real_vol_fwd, s=14, color=COL_NAIVE, alpha=0.6, zorder=2)
lims = [0, max(persist_pred.max(), real_vol_fwd.max()) * 1.05]
axes[0].plot(lims, lims, color=COL_REAL, lw=1, ls='--', zorder=1, label='y=x (prognoza idealna)')
axes[0].set_xlim(lims); axes[0].set_ylim(lims)
axes[0].set_xlabel('Prognoza: persystencja zmienności (24h)')
axes[0].set_ylabel('Rzeczywista zmienność, kolejne 6h')
axes[0].set_title(f'Persystencja zmienności\nr={r_persist:.2f} (realny, użyteczny sygnał)', fontsize=10.5)
axes[0].legend(fontsize=8)

axes[1].scatter(flow_sigma_at_D, real_vol_fwd, s=14, color=COL_FLOW, alpha=0.6, zorder=2)
axes[1].set_xlabel('TIMDR flow_sigma (trend zmienności)')
axes[1].set_ylabel('Rzeczywista zmienność, kolejne 6h')
axes[1].set_title(f'TIMDR flow_sigma\nr={r_flow:.2f} (brak dodatkowej wartości)', fontsize=10.5)

fig.suptitle('Prognoza zmienności BTC/USD (kauzalny walk-forward, 182 punkty) — co działa, co nie', fontsize=12)
fig.tight_layout()
fig.savefig('chart_vol_forecast.png', dpi=150)
print('saved chart_vol_forecast.png')
