"""
timdr_finance_field.py — TIMDR Finanse jako POLE (nie pojedynczy instrument)
================================================================================
Odpowiedź na pytanie: "czy nowe podejście by coś zmieniło? z mapowaniem
pola". Reszta tego repo (`timdr_core_finance.py`) analizuje KAŻDY instrument
NIEZALEŻNIE (BTC osobno, złoto osobno) — replikacja sygnału reversal z BTC
na złocie NIE powtórzyła się (patrz README, "Wyniki, bez owijania w
bawełnę"), co jest testem, czy ten sam KSZTAŁT WAHANIA ceny generalizuje
się między aktywami.

Ten moduł stawia INNY zakład: nie "czy kształt fali się powtarza", tylko
"czy SPRZĘŻENIE między aktywami niesie sygnał" — koszyk aktywów jako
POLE, nie N niezależnych szeregów. To dokładnie ten sam zabieg, co
`Synoptyk-v3` (pogoda jako pole na siatce geograficznej, nie niezależne
stacje) i `TIMDR-Quantum-Lattice` (agregatowy stan całej siatki, nie
pojedynczy kanał 1D) — trzeci taki przypadek w tym ekosystemie.

## Dwa sygnały polowe, oba z literatury (nie wymyślone na potrzeby TIMDR)

1. `mean_pairwise_correlation()` — średnia korelacja parami w oknie
   kroczącym. Korelacje między aktywami SYSTEMATYCZNIE rosną w okresach
   stresu rynkowego/kryzysu ("korelacje idą do 1 w bessie") —
   udokumentowane empirycznie: Longin & Solnik (2001), "Extreme
   Correlation of International Equity Markets", Journal of Finance.

2. `absorption_ratio()` — udział wariancji koszyka wyjaśniany przez
   pierwsze `n_components` głównych składowych (PCA) macierzy kowariancji
   zwrotów. Wysoki absorption ratio = rynek "ciasno sprzężony"/kruchy
   (mało niezależnych źródeł ryzyka) — Kritzman, Li, Page, Rigobon
   (2011), "Principal Components as a Measure of Systemic Risk", Journal
   of Portfolio Management: rosnący AR wyprzedzał w ich danych duże
   spadki (m.in. 2007-2008).

Oba sygnały (nie wymieszane bez etykiety — dwa osobne, porównywalne
kanały) są następnie podawane do STANDARDOWEGO operatora TIMDR
(twist/trend/anomalies/rhythm/fusion_score) — ten sam kształt API co w
`TIMDR-Battery-Predict`/`TIMDR-Solar-PV`/`TIMDR-Mold-Risk` — ale tu
wejściem jest jedna wielkość AGREGATOWA opisująca CAŁY koszyk, nie cena
pojedynczego instrumentu.

## Uczciwe ograniczenia (nie ukryte)

- To NIE jest predykcja kierunku/ceny — to detektor ZMIANY REŻIMU
  sprzężenia (fragmentacja <-> synchronizacja rynku), zjawisko INNEGO
  RODZAJU niż to, co testował już ten repo (kształt fali na jednym
  instrumencie). Nie ma tu twierdzenia, że to naprawia porażkę reversal
  na BTC/złocie — to jest osobna, niezależna hipoteza.
- Wymaga koszyka >=4-5 aktywów i wystarczająco długiej historii (macierz
  korelacji z 2 aktywami to jedna liczba, nie pole) — dane testowe w tym
  repo (BTC/złoto, 30 dni, 720 świec 1h) są ZA MAŁE do tego modułu; ten
  moduł jest zaprojektowany pod dane DZIENNE, wieloletnie (patrz
  `real_fred_field_test.py`).
- `absorption_ratio()` z małym koszykiem (<5 aktywów) jest niestabilny/
  szumowy — pierwsza główna składowa z 2-3 szeregów wyjaśnia dużo
  wariancji niemal zawsze, niezależnie od realnego sprzężenia; sam
  moduł NIE ostrzega o tym w runtime (brak walidacji minimalnej
  liczebności koszyka) — świadomie udokumentowane tu jako obowiązek
  użytkownika API, nie zabezpieczone w kodzie (żeby nie dodawać
  niejawnych progów bez testu).
- Test na SYNTETYCZNYCH danych (ten plik) używa wstrzykniętego,
  jednoznacznego reżimu kryzysu (wspólny czynnik ryzyka włączany/
  wyłączany skokowo) — realne reżimy korelacji zmieniają się płynniej;
  to jest kontrola pozytywna sprawdzająca POPRAWNOŚĆ MECHANIZMU, nie
  kalibrację progów pod realny rynek.
"""

import numpy as np


def compute_returns(prices):
    """prices: macierz (n_dni, n_aktywow). Zwraca log-zwroty (n_dni-1, n_aktywow)."""
    prices = np.asarray(prices, float)
    return np.diff(np.log(prices), axis=0)


def mean_pairwise_correlation(returns, window=20):
    """Srednia korelacja parami (poza diagonala) w oknie kroczacym `window`
    dni. Zwraca tablice dlugosci n_dni (NaN dla pierwszych window-1 probek,
    oraz dla kazdego okna zawierajacego niefinitowy - NaN/inf - zwrot).
    returns: (n_dni, n_aktywow).

    Uwaga (2026-09-14, real_fred_field_test.py): niefinitowy zwrot moze
    powstac nie tylko z brakow danych, ale i z REALNEGO zdarzenia - np.
    cena ropy WTI (DCOILWTICO) na FRED byla UJEMNA 2020-04-20 (historyczny,
    udokumentowany dzien zalamania rynku kontraktow terminowych na rope w
    trakcie COVID-19), co daje log(cena<=0)=NaN w compute_returns() dla
    zwrotow po obu stronach tej daty. Okna kroczace obejmujace taki zwrot
    sa tu celowo pomijane (NaN w wyniku), a nie ukrywane/interpolowane -
    korelacja/PCA na sztucznie \"naprawionej\" cenie bylaby nieuczciwa."""
    returns = np.asarray(returns, float)
    n, k = returns.shape
    if k < 2:
        raise ValueError("mean_pairwise_correlation wymaga >=2 aktywow w koszyku")
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        window_data = returns[i - window + 1:i + 1]
        if not np.all(np.isfinite(window_data)):
            continue
        corr = np.corrcoef(window_data, rowvar=False)
        mask = ~np.eye(k, dtype=bool)
        out[i] = np.nanmean(corr[mask])
    return out


def absorption_ratio(returns, window=20, n_components=1):
    """Udzial wariancji wyjasniany przez pierwsze n_components skladowych
    PCA macierzy kowariancji zwrotow w oknie kroczacym `window` dni
    (Kritzman i in. 2011). Zwraca tablice dlugosci n_dni (NaN dla
    pierwszych window-1 probek, oraz dla kazdego okna zawierajacego
    niefinitowy zwrot - patrz uwaga w mean_pairwise_correlation() o
    ujemnej cenie ropy WTI 2020-04-20)."""
    returns = np.asarray(returns, float)
    n, k = returns.shape
    if k < 2:
        raise ValueError("absorption_ratio wymaga >=2 aktywow w koszyku")
    n_components = min(n_components, k)
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        window_data = returns[i - window + 1:i + 1]
        if not np.all(np.isfinite(window_data)):
            continue
        cov = np.cov(window_data, rowvar=False)
        eigvals = np.linalg.eigvalsh(cov)
        eigvals = np.sort(eigvals)[::-1]
        total = np.sum(eigvals)
        if total <= 0:
            out[i] = np.nan
            continue
        out[i] = np.sum(eigvals[:n_components]) / total
    return out


class TIMDRFinanceFieldFusion:
    """Operator TIMDR na sygnale POLOWYM (agregat koszyka aktywow), nie na
    cenie pojedynczego instrumentu. Ten sam ksztalt API co
    TIMDRBatteryFusion/TIMDRSolarFusion/TIMDRMoldFusion."""

    def __init__(self, mad_scale=1.4826):
        self.mad_scale = mad_scale

    def _mad_z(self, x):
        x = np.asarray(x, float)
        if x.size == 0:
            return np.zeros_like(x)
        med = np.nanmedian(x)
        mad = np.nanmedian(np.abs(x - med)) * self.mad_scale
        if not np.isfinite(mad) or mad == 0:
            span = np.nanmax(x) - np.nanmin(x)
            if not np.isfinite(span) or span == 0:
                return np.zeros_like(x)
            return (x - med) / (span / 4.0)
        return (x - med) / mad

    def fuse(self, prices, window=20, n_components=1):
        """prices: (n_dni, n_aktywow). Zwraca (E, aux) gdzie E=mean_pairwise_
        correlation (glowny sygnal, dobrze udokumentowany w literaturze) i
        aux=absorption_ratio (drugi, niezalezny sygnal polowy)."""
        returns = compute_returns(prices)
        corr = mean_pairwise_correlation(returns, window=window)
        ar = absorption_ratio(returns, window=window, n_components=n_components)
        return corr, ar

    def twist(self, t, E):
        t = np.asarray(t, float)
        E = np.asarray(E, float)
        if len(t) < 3:
            return np.array([], int), np.zeros_like(E)
        dE = np.gradient(E, t)
        ddE = np.gradient(dE, t)
        z = np.abs(self._mad_z(ddE))
        idx = np.where(z > 3.5)[0]
        return idx, z

    def trend(self, t, E, window=20):
        t = np.asarray(t, float)
        E = np.asarray(E, float)
        n = len(t)
        slopes = np.full(n, np.nan)
        if n < 2:
            return slopes, np.full(n, np.nan)
        for i in range(n):
            j0 = max(0, i - window + 1)
            tt = t[j0:i + 1]
            ee = E[j0:i + 1]
            valid = np.isfinite(ee)
            if valid.sum() < 2:
                continue
            A = np.column_stack([tt[valid], np.ones(valid.sum())])
            a, b = np.linalg.lstsq(A, ee[valid], rcond=None)[0]
            slopes[i] = a
        z = self._mad_z(slopes)
        return slopes, z

    def anomalies(self, E):
        E = np.asarray(E, float)
        if E.size == 0:
            return np.array([], int), np.zeros_like(E)
        z = np.abs(self._mad_z(E))
        idx = np.where(z > 3.0)[0]
        return idx, z

    def fusion_score(self, twist_z, trend_z, anomaly_z):
        def safe_max(x):
            x = np.asarray(x, float)
            x = x[np.isfinite(x)]
            return float(np.max(x)) if x.size else 0.0

        return float(0.4 * safe_max(twist_z) + 0.35 * safe_max(trend_z) + 0.25 * safe_max(anomaly_z))
