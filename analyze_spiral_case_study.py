"""
analyze_spiral_case_study.py — studium przypadku: czy trajektoria
flow_sigma vs przyszla zmiennosc (Test 1) uklada sie w "spirale w czasie"
(hipoteza zgloszona podczas przegladu dashboardu)? Patrz sekcja
"Studium przypadku" w RAPORT_TIMDR_Finanse.md.

Trzy testy:
A) Dlugosc trajektorii (ciaglosc w czasie) vs 3000 losowych permutacji
   tych samych punktow - model-free test "czy kolejnosc czasowa cokolwiek
   zmienia".
B) Cross-korelacja flow_sigma vs przyszla zmiennosc przy przesunieciach
   -20..+20 krokow (wliczajac NIEKAUZALNE przesuniecia, dla pelnego obrazu).
C) To samo, ale ograniczone do przesuniec KAUZALNYCH, z walidacja
   out-of-sample (1. polowa trening, 2. polowa test) - jedyna wersja, ktora
   mialaby jakiekolwiek znaczenie predykcyjne.
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

core = TIMDR_FinanceCore()
rows = []
with open('data/btcusd_1h.csv') as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append(row)

t = np.array([int(r['time']) for r in rows], dtype=float)
t_h = (t - t[0]) / 3600.0
close = np.array([float(r['close']) for r in rows])
log_ret = np.concatenate([[0.0], core.log_returns(close)])
sigma = core.realized_vol(close, window=6)

BURN_IN, STEP, HORIZON = 168, 3, 6
idxs = np.arange(BURN_IN, len(close) - HORIZON, STEP)
real_vol_fwd, flow_sigma_at_D = [], []
for i in idxs:
    past_sigma = sigma[:i]
    sigma_s = core.trm(t_h[:i], past_sigma, k=5)
    fs = core.flow(t_h[:i], sigma_s, window=5)
    flow_sigma_at_D.append(fs[-1] if len(fs) else 0.0)
    real_vol_fwd.append(np.std(log_ret[i:i + HORIZON]))

x = np.array(flow_sigma_at_D)
y = np.array(real_vol_fwd)
n = len(x)
half = n // 2

# ============================================================
# TEST A: dlugosc trajektorii (ciaglosc w czasie)
# ============================================================
def path_length(xv, yv):
    return np.sum(np.hypot(np.diff(xv), np.diff(yv)))

true_len = path_length(x, y)
rng = np.random.default_rng(3)
perm_lens = np.array([path_length(x[rng.permutation(n)], y) for _ in range(3000)])
pctl_len = np.mean(perm_lens < true_len) * 100

print("=== TEST A: dlugosc trajektorii (ciaglosc w czasie) ===")
print(f"Prawdziwa chronologia: dlugosc toru = {true_len:.6f}")
print(f"3000 losowych permutacji: srednia={perm_lens.mean():.6f}, std={perm_lens.std():.6f}")
print(f"Prawdziwy wynik na percentylu {pctl_len:.1f} "
      f"(0=najgladszy ze wszystkich, 50=typowy, 100=najbardziej chaotyczny)")
print("-> Trajektoria JEST gladsza niz losowa (realny efekt) - ale patrz")
print("   TEST C nizej, dlaczego to nie oznacza uzytecznego sygnalu.")

# ============================================================
# TEST B: najlepszy lag ze WSZYSTKICH przesuniec (wliczajac niekauzalne)
# ============================================================
def lagged_pairs(xv, yv, lag, lo, hi):
    xs, ys = [], []
    for i in range(lo, hi):
        j = i + lag
        if 0 <= j < len(xv):
            xs.append(xv[j]); ys.append(yv[i])
    return np.array(xs), np.array(ys)

print("\n=== TEST B: najlepszy lag ze WSZYSTKICH przesuniec (-20..+20) ===")
best_r, best_lag = 0.0, 0
for lag in range(-20, 21):
    xs, ys = lagged_pairs(x, y, lag, 0, n)
    if len(xs) < 10:
        continue
    r = np.corrcoef(xs, ys)[0, 1]
    if abs(r) > abs(best_r):
        best_r, best_lag = r, lag
causal = "KAUZALNY" if best_lag <= 0 else "NIEKAUZALNY (look-ahead!)"
print(f"Najlepszy |r| ze wszystkich 41 przesuniec: r={best_r:.3f} przy "
      f"lag={best_lag} krokow ({best_lag*3}h) -- {causal}")

# ============================================================
# TEST C: najlepszy KAUZALNY lag, zwalidowany out-of-sample
# ============================================================
print("\n=== TEST C: najlepszy KAUZALNY lag, walidacja out-of-sample ===")
best_r_train, best_lag_c = 0.0, 0
for lag in range(-20, 1):
    xs, ys = lagged_pairs(x, y, lag, 0, half)
    r = np.corrcoef(xs, ys)[0, 1]
    if abs(r) > abs(best_r_train):
        best_r_train, best_lag_c = r, lag
xs_test, ys_test = lagged_pairs(x, y, best_lag_c, half, n)
r_test = np.corrcoef(xs_test, ys_test)[0, 1]
print(f"Najlepszy kauzalny lag na TRENINGU: lag={best_lag_c} ({best_lag_c*3}h), "
      f"r_train={best_r_train:.3f}")
print(f"Ten sam lag na TEScie (out-of-sample): r_test={r_test:.3f}")
if abs(r_test) < abs(best_r_train) * 0.5:
    print("-> Sygnal w duzej mierze ZNIKA out-of-sample (typowy objaw")
    print("   data-snoopingu, jak reversal H=12h w Dodatku A).")

# ============================================================
# Wykres: prawdziwa chronologia vs jedna losowa permutacja (do Testu A)
# ============================================================
rng2 = np.random.default_rng(7)
shuffled = rng2.permutation(np.arange(n))

fig, axes = plt.subplots(1, 2, figsize=(11, 5.2))
cmap = plt.cm.viridis

for ax, order, title in [
    (axes[0], np.arange(n), 'PRAWDZIWA chronologia\n(dokładnie te same 182 punkty)'),
    (axes[1], shuffled, 'JEDNA losowa permutacja\n(te same punkty, przetasowana kolejność)'),
]:
    xs, ys = x[order], y[order]
    ax.plot(xs, ys, '-', color='#c7c7c7', lw=0.7, zorder=1)
    sc = ax.scatter(xs, ys, c=np.arange(n), cmap=cmap, s=18, zorder=2)
    ax.set_title(title, fontsize=10.5)
    ax.set_xlabel('flow_sigma')
    ax.set_ylabel('rzeczywista zmienność (6h fwd)')

cbar = fig.colorbar(sc, ax=axes, orientation='horizontal', fraction=0.05, pad=0.12, aspect=40)
cbar.set_label('kolejność w czasie (ciemny=wcześniej, jasny=później)', fontsize=9)
fig.suptitle(
    'Czy trajektoria "spirala się"? Prawdziwa kolejność vs losowe przetasowanie tych samych punktów\n'
    f'(Test A: prawdziwy tor na percentylu {pctl_len:.1f} rozkładu losowego — realnie gładszy, ale patrz Test C)',
    fontsize=10.5, y=1.02)
fig.savefig('chart_flow_sigma_trajectory.png', dpi=150, bbox_inches='tight')
print('\nsaved chart_flow_sigma_trajectory.png')
