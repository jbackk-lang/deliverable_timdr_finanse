"""
backtest_finance_extended.py — dodatkowy test: "czy JAKAKOLWIEK wersja
predykcji kierunku/reversal w ogole tu dziala?" Odpowiedz na pytanie
uzytkownika wprost, ale UCZCIWIE: przeszukujemy siatke horyzontow/strategii,
ale wybor najlepszej kombinacji robimy WYLACZNIE na 1. polowie danych
(trening), a raportujemy WYNIK NA 2. POLOWIE (out-of-sample) - dokladnie
raz, bez dalszego wyboru. To chroni przed data-snoopingiem (gdyby zamiast
tego raportowac najlepszy wynik z calego zbioru, wygralby przypadek - im
wiecej kombinacji przetestujesz, tym wieksza szansa ze cos "zadziala" czysto
losowo).

Dwa niezalezne eksperymenty:

A) Siatka horyzont x strategia dla kierunku zwrotu (na podstawie FLOW ceny)
B) Anomaly-triggered mean reversion: po wykryciu anomalii (kauzalnie, tylko
   dane sprzed danego punktu), czy nastepuje average "oddanie" ruchu, czy
   kontynuacja? To jest jedyny test tutaj oparty na udokumentowanym w
   literaturze mikrostrukturalnym efekcie (overreaction / short-term mean
   reversion po duzych ruchach), a nie na "szukaniu wzorca az cos wyjdzie".
"""
import csv
import numpy as np
from timdr_core_finance import TIMDR_FinanceCore

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
n = len(close)

BURN_IN = 168

# ============================================================
# A) Siatka horyzont x strategia, wybor na 1. polowie, ocena na 2.
# ============================================================
print("=== A: siatka horyzont x strategia (kierunek zwrotu) ===")
print("Wybor najlepszej kombinacji WYLACZNIE na 1. polowie danych (trening),")
print("ocena WYLACZNIE na 2. polowie (out-of-sample, bez dalszego wyboru).\n")

HORIZONS = [1, 2, 3, 6, 12, 24]
idxs_all = np.arange(BURN_IN, n - max(HORIZONS), 1)
half = len(idxs_all) // 2
idxs_train = idxs_all[:half]
idxs_test = idxs_all[half:]

# flow ceny w kazdym punkcie D, liczony raz kauzalnie (okno 5 przed D)
flow_price = core.flow(t_h, close, window=5)  # UWAGA: to jest liczone na
# calej serii na raz, ale flow() w kazdym punkcie i uzywa TYLKO probek
# [i-2, i+2] wokol i (patrz kod: window=5, half=2) - a poniewaz i sam nie
# jest "przyszloscia" wzgledem samego siebie, i uzywamy flow[D] TYLKO do
# przewidywania D+horizon, jest to nadal kauzalne w sensie: informacja
# o przyszlych swiecach D+1..D+2 (polowa okna) WYCIEKA do flow[D]. Aby to
# byc w pelni kauzalnym, uzywamy WYLACZNIE polowicznego, wstecznego okna
# (patrz flow_price_causal ponizej) - dokladnie tak jak w backtest_finance.py
# (tam flow liczony byl na close[:i], czyli tylko dane sprzed i).
flow_price_causal = np.zeros(n)
for i in idxs_all:
    fp = core.flow(t_h[:i], close[:i], window=5)
    flow_price_causal[i] = fp[-1] if len(fp) else 0.0

results_train = {}
for H in HORIZONS:
    fwd_ret = np.array([np.log(close[min(i + H, n - 1)]) - np.log(close[i]) for i in idxs_train])
    real_dir = np.where(fwd_ret > 0, 1, -1)
    pred_mom = np.sign(flow_price_causal[idxs_train])
    pred_mom[pred_mom == 0] = 1
    acc_mom = np.mean(pred_mom == real_dir)
    acc_rev = np.mean(-pred_mom == real_dir)
    baseline = max(np.mean(real_dir == 1), np.mean(real_dir == -1))
    results_train[H] = dict(mom=acc_mom, rev=acc_rev, baseline=baseline)
    print(f"  H={H:>2}h  trafnosc momentum={acc_mom:.3f}  reversal={acc_rev:.3f}  "
          f"baseline={baseline:.3f}")

# najlepsza kombinacja NA TRENINGU (moze byc szumem - to normalne w takiej
# siatce; sedno testu jest w tym, co sie stanie na danych testowych)
best_H, best_strat, best_acc = None, None, -1
for H, r in results_train.items():
    if r['mom'] > best_acc:
        best_H, best_strat, best_acc = H, 'mom', r['mom']
    if r['rev'] > best_acc:
        best_H, best_strat, best_acc = H, 'rev', r['rev']

print(f"\nNajlepsza kombinacja na TRENINGU: H={best_H}h, strategia={best_strat}, "
      f"trafnosc treningowa={best_acc:.3f}")
print("(To jest wynik PO przeszukaniu 12 kombinacji (6 horyzontow x 2 strategie) -")
print(" nalezy sie spodziewac, ze czesc z nich 'wygra' czysto przypadkiem.")
print(" Prawdziwy test jest ponizej: ta SAMA, JUZ WYBRANA kombinacja, bez zadnej")
print(" dalszej optymalizacji, na danych ktorych nie widziala.)\n")

fwd_ret_test = np.array([np.log(close[min(i + best_H, n - 1)]) - np.log(close[i]) for i in idxs_test])
real_dir_test = np.where(fwd_ret_test > 0, 1, -1)
pred_test = np.sign(flow_price_causal[idxs_test])
pred_test[pred_test == 0] = 1
if best_strat == 'rev':
    pred_test = -pred_test
acc_test = np.mean(pred_test == real_dir_test)
baseline_test = max(np.mean(real_dir_test == 1), np.mean(real_dir_test == -1))
print(f"OUT-OF-SAMPLE (2. polowa, {len(idxs_test)} punktow): "
      f"trafnosc wybranej kombinacji = {acc_test:.3f}, baseline = {baseline_test:.3f}")
if acc_test > baseline_test + 0.03:
    print("-> Przewaga PRZETRWALA out-of-sample: warta dalszego, ostrozniejszego zbadania.")
else:
    print("-> Przewaga NIE przetrwala out-of-sample (typowy objaw przypadkowego trafienia")
    print("   podczas przeszukiwania siatki, tzw. data snooping) - trafnosc treningowa byla")
    print("   szumem, nie realnym sygnalem.")

# ============================================================
# B) Anomaly-triggered mean reversion (kauzalne wykrywanie anomalii)
# ============================================================
print("\n=== B: mean-reversion po anomaliach (kauzalne wykrywanie) ===")
print("Hipoteza z mikrostruktury rynku: po nietypowo duzym ruchu cena czesciowo")
print("'oddaje' ruch w kolejnych godzinach (overreaction / krotkoterminowa")
print("mean-reversion). To NIE jest przeszukiwanie az cos wyjdzie - to jeden,")
print("z gory postawiony test konkretnej, znanej w literaturze hipotezy.\n")

anomaly_events = []  # (idx, kierunek: +1/-1, z-score)
for i in range(BURN_IN, n):
    past = log_ret[:i]
    idx_a, z_a, thr_a = core.anomalies(t_h[:i], past, factor=3.0)
    if len(idx_a) and idx_a[-1] == i - 1:  # ostatnia swieca w oknie [:i] byla anomalia
        anomaly_events.append((i - 1, np.sign(past[-1]), z_a[-1]))

print(f"Wykryto kauzalnie {len(anomaly_events)} anomalii (burn-in={BURN_IN}h, wiec")
print(f"analizowane {n - BURN_IN} z {n} swiec).\n")

for H in [1, 3, 6]:
    fwd_after_up, fwd_after_down, fwd_unconditional = [], [], []
    for idx, direction, z in anomaly_events:
        if idx + H >= n:
            continue
        fwd = np.log(close[idx + H]) - np.log(close[idx])
        (fwd_after_up if direction > 0 else fwd_after_down).append(fwd)
    all_idxs = np.arange(BURN_IN, n - H)
    fwd_unconditional = [np.log(close[i + H]) - np.log(close[i]) for i in all_idxs]
    mu_up = np.mean(fwd_after_up) if fwd_after_up else float('nan')
    mu_down = np.mean(fwd_after_down) if fwd_after_down else float('nan')
    mu_all = np.mean(fwd_unconditional)
    print(f"  H={H}h:  po anomalii W GORE (n={len(fwd_after_up)}): "
          f"sredni fwd zwrot={mu_up:+.5f}  |  po anomalii W DOL (n={len(fwd_after_down)}): "
          f"sredni fwd zwrot={mu_down:+.5f}  |  bezwarunkowo: {mu_all:+.5f}")

print("\nInterpretacja: jesli 'po anomalii w gore' sredni przyszly zwrot jest WYRAZNIE")
print("bardziej UJEMNY niz bezwarunkowo (i symetrycznie: 'po anomalii w dol' wyrazniej")
print("DODATNI) - to slad mean-reversion. Jesli podobny do bezwarunkowego albo w ta sama")
print("strone co sam ruch - brak efektu / kontynuacja. Uwaga: n jest tu male (dziesiatki")
print("zdarzen), wiec to sygnal jakosciowy, NIE dowod statystyczny - potrzeba wiecej danych")
print("(dluzszy okres) zeby cokolwiek z tego uznac za wiarygodne.")
