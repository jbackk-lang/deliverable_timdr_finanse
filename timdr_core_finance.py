"""
timdr_core_finance.py — TIMDR-Finanse (rdzeń analizy przepływów rynkowych)
============================================================================
Ten sam szkielet co `timdr_core_earthquake.py` (fala, sygnał ciągły) i
`catalog_core.py` (rodzina detektorów anomalia/defekt/rezonans/skręt),
przeniesiony na dane rynkowe: S(t) = [price, volume, delta, spread, sigma].

WAŻNE ZASTRZEŻENIE UCZCIWOŚCI (przeczytaj przed użyciem):
Ten moduł jest zbudowany z danych OHLC + volume (świece), NIE z prawdziwego
orderbooka ani tick-by-tick order flow. To oznacza:

- `delta_proxy()` to PRZYBLIŻENIE presji kupna/sprzedaży
  (sign(close-open) * volume), NIE prawdziwa delta agresora z tick-data.
  Na słabo płynnych instrumentach / świecach z dużym knotem to przybliżenie
  może się mylić co do kierunku.
- `spread_proxy()` to zakres wewnątrz świecy ((high-low)/close), NIE
  prawdziwy spread bid/ask. Nie odzwierciedla mikrostruktury (depth,
  kolejka zleceń).

Jeśli zasilisz ten moduł prawdziwym orderbookiem / tick-data, podmień
`delta_proxy`/`spread_proxy` na realne wartości — reszta pipeline'u
(TRM/FLOW/TWIST/RHYTHM/anomalie/defekty/rezonans) działa identycznie na
dowolnym S(t), niezależnie od tego, czy komponenty są przybliżeniami.

DRUGIE, WAŻNIEJSZE ZASTRZEŻENIE: w przeciwieństwie do sejsmiki (Ertake) czy
pogody (Synoptyk), rynek NIE jest zjawiskiem fizycznym z ustalonym
mechanizmem — jest w dużej mierze efektywny i adwersarialny (arbitrażyści
zjadają łatwo wykrywalne wzorce). Test na katalogu globalnym trzęsień
(TIMDR-Earthquake-Core) pokazał r=0.04 (szum) dla trend_z bez prawdziwego
mechanizmu fizycznego (Omori-Utsu) w tle. Zakładaj, że sygnały z tego
modułu są SZUMEM, dopóki nie przejdą kauzalnego (bez lookahead) backtestu
przeciw twardemu null-modelowi (błądzenie losowe dla ceny, persystencja
zmienności dla sigma) NA REALNYCH DANYCH — patrz `backtest_finance.py`.
"""

import numpy as np

from ringdown import ringdown_resonance


class TIMDR_FinanceCore:
    def __init__(self, mad_scale=1.4826):
        self.mad_scale = mad_scale
        self._threshold_cache = {}  # (param_name, window_id) -> (mean,std,p10,p90)

    # ------------------------------------------------------------------
    # Komponenty S(t) z surowych świec OHLCV
    # ------------------------------------------------------------------
    @staticmethod
    def log_returns(close):
        close = np.asarray(close, float)
        if len(close) < 2:
            return np.array([])
        return np.diff(np.log(close))

    @staticmethod
    def realized_vol(close, window=6):
        """Zrealizowana zmienność: odchylenie std log-zwrotów w oknie
        `window` świec (nie w jednostkach czasu — jeśli świece mają luki,
        okno jest w liczbie świec, nie godzin; udokumentowane ograniczenie,
        tak jak rhythm() w catalog_core.py)."""
        close = np.asarray(close, float)
        n = len(close)
        if n < 2:
            return np.zeros(n)
        r = np.diff(np.log(close))
        r = np.concatenate([[0.0], r])
        out = np.zeros(n)
        for i in range(n):
            j0 = max(0, i - window + 1)
            seg = r[j0:i + 1]
            out[i] = np.std(seg) if len(seg) > 1 else 0.0
        return out

    @staticmethod
    def delta_proxy(open_, close):
        """PRZYBLIŻENIE presji kupna/sprzedaży z samych OHLC: kierunek
        świecy * wolumen. Zobacz zastrzeżenie w docstringu modułu — to NIE
        jest prawdziwa delta z order flow."""
        open_ = np.asarray(open_, float)
        close = np.asarray(close, float)
        return np.sign(close - open_)

    @staticmethod
    def spread_proxy(high, low, close):
        """PRZYBLIŻENIE spreadu: zakres świecy znormalizowany ceną
        zamknięcia. Zobacz zastrzeżenie w docstringu modułu."""
        high = np.asarray(high, float)
        low = np.asarray(low, float)
        close = np.asarray(close, float)
        with np.errstate(divide='ignore', invalid='ignore'):
            out = (high - low) / close
        return np.nan_to_num(out, nan=0.0)

    # ------------------------------------------------------------------
    # TRM — wygładzanie (mediana k-NN w czasie)
    # ------------------------------------------------------------------
    @staticmethod
    def trm(t, s, k=5):
        t = np.asarray(t, float)
        s = np.asarray(s, float)
        n = len(s)
        if n == 0:
            return np.array([])
        out = np.empty(n)
        half = k // 2
        for i in range(n):
            j0, j1 = max(0, i - half), min(n, i + half + 1)
            out[i] = np.median(s[j0:j1])
        return out

    # ------------------------------------------------------------------
    # FLOW — lokalny gradient WZGLĘDEM CZASU (LSQ), nie indeksu próbki
    # ------------------------------------------------------------------
    @staticmethod
    def flow(t, s, window=5):
        t = np.asarray(t, float)
        s = np.asarray(s, float)
        n = len(s)
        if n == 0:
            return np.array([])
        out = np.zeros(n)
        half = window // 2
        for i in range(n):
            j0, j1 = max(0, i - half), min(n, i + half + 1)
            tt, ss = t[j0:j1], s[j0:j1]
            if len(tt) < 2 or tt[-1] == tt[0]:
                continue
            A = np.column_stack([tt, np.ones_like(tt)])
            a, _ = np.linalg.lstsq(A, ss, rcond=None)[0]
            out[i] = a
        return out

    # ------------------------------------------------------------------
    # TWIST — nagła zmiana kierunku FLOW, różniczkowana wzgledem CZASU
    # (dokladnie ten sam blad co w timdr_core_earthquake.py Bug 1: liczenie
    # gradientu po indeksie zamiast po t daje falszywe alarmy na lukach w
    # danych - tu utrzymane poprawnie od poczatku)
    # ------------------------------------------------------------------
    @staticmethod
    def twist(flow_vals, t, threshold=0.4):
        flow_vals = np.asarray(flow_vals, float)
        t = np.asarray(t, float)
        n = len(flow_vals)
        if n < 3:
            return np.array([], dtype=int), np.array([])
        dg = np.gradient(flow_vals, t)  # WZGLEDEM CZASU, nie indeksu
        std = np.std(dg) if np.std(dg) > 0 else 1e-9
        thr = threshold * std
        idx = np.where(np.abs(dg) > thr)[0]
        return idx, dg

    # ------------------------------------------------------------------
    # ANOMALIA — próg adaptacyjny z podłogą (unika pułapki zero-inflation
    # z dokumentu timdr-signal-framework: p90-p10~=0 na "cichych" seriach
    # jak wolumen w martwych godzinach)
    # ------------------------------------------------------------------
    def anomalies(self, t, s, factor=3.0, floor_frac=0.05):
        s = np.asarray(s, float)
        n = len(s)
        if n == 0:
            return np.array([], dtype=int), np.array([]), 0.0
        med = np.median(s)
        mad = np.median(np.abs(s - med)) * self.mad_scale
        if mad == 0 or not np.isfinite(mad):
            std = np.std(s)
            # PODLOGA: jesli i std jest ~0 (seria faktycznie stala / prawie
            # zero-inflated), uzyj malej stalej zamiast dzielenia przez 0 -
            # dokladnie blad #2 z timdr_core_earthquake.py (MAD=0 na
            # skwantowanym sygnale dawal prog=0 -> kazda niezerowa reszta
            # = "anomalia")
            mad = std if std > 0 else max(abs(med) * floor_frac, 1e-9)
        z = (s - med) / mad
        idx = np.where(np.abs(z) > factor)[0]
        return idx, z, mad * factor

    # ------------------------------------------------------------------
    # DEFEKT — nagly skok miedzy kolejnymi odczytami, prog z lokalnego
    # rozrzutu (p90-p10), z ta sama podloga co anomalie() dla parametrow
    # zero-inflated (np. delta_proxy na plytkim rynku)
    # ------------------------------------------------------------------
    @staticmethod
    def defekt(s, factor=0.3, floor_frac=0.05):
        s = np.asarray(s, float)
        n = len(s)
        if n < 2:
            return np.array([], dtype=int), np.array([])
        diffs = np.diff(s)
        p10, p90 = np.percentile(s, 10), np.percentile(s, 90)
        spread = p90 - p10
        if spread <= 0 or not np.isfinite(spread):
            spread = max(abs(np.median(s)) * floor_frac, 1e-9)
        thr = factor * spread
        idx = np.where(np.abs(diffs) > thr)[0] + 1  # indeks NOWEJ probki
        return idx, diffs

    # ------------------------------------------------------------------
    # RHYTHM — autokorelacja na wartosci ZE ZNAKIEM (nie rektyfikowanej -
    # dokladnie ten sam blad co w catalog_core.py: |MAD-z| tworzy sztuczna
    # okresowosc z samej rektyfikacji dla pojedynczej cechy)
    # ------------------------------------------------------------------
    @staticmethod
    def rhythm(values, max_lag=48, power_thresh=0.4):
        E = np.asarray(values, float)
        n = len(E)
        if n < 2:
            return [], 0.0
        idx = np.arange(n, dtype=float)
        if n > 2:
            slope, intercept = np.polyfit(idx, E, 1)
            E = E - (slope * idx + intercept)
        else:
            E = E - np.mean(E)
        max_lag = min(max_lag, n - 1)
        ac = np.zeros(max_lag + 1)
        for lag in range(max_lag + 1):
            if lag == 0:
                ac[lag] = np.dot(E, E) / n
            else:
                overlap = n - lag
                if overlap <= 0:
                    break
                ac[lag] = np.dot(E[:-lag], E[lag:]) / overlap
        if ac[0] == 0:
            return [], 0.0
        ac /= ac[0]
        peaks = [(i, float(ac[i])) for i in range(1, len(ac) - 1)
                 if ac[i] > ac[i - 1] and ac[i] > ac[i + 1] and ac[i] >= power_thresh]
        if not peaks:
            return [], 0.0
        score = max(p for _, p in peaks)
        return [p for p, _ in peaks], score

    # ------------------------------------------------------------------
    # REZONANS — >=min_count parametrow flaguje anomalie() w tej samej
    # chwili -> silniejszy, bardziej wiarygodny sygnal niz pojedyncza
    # anomalia
    # ------------------------------------------------------------------
    @staticmethod
    def rezonans(anomaly_index_lists, n, min_count=3):
        counts = np.zeros(n, dtype=int)
        for idxs in anomaly_index_lists:
            counts[np.asarray(idxs, dtype=int)] += 1
        idx = np.where(counts >= min_count)[0]
        return idx, counts

    # ------------------------------------------------------------------
    # RINGDOWN — rezonans w SENSIE FIZYCZNYM (nie licznik koincydencji jak
    # rezonans() wyzej): czy powrot serii po zdarzeniu (np. z defekt()) do
    # poziomu odniesienia jest oscylacyjny czy monotoniczny. Patrz
    # ringdown.py po pelne uzasadnienie metody i wazne zastrzezenie o
    # braku testu predykcyjnego.
    # ------------------------------------------------------------------
    @staticmethod
    def ringdown_events(t, s, event_indices, pre_event_window=10, max_lookahead=None):
        """Woła ringdown_resonance() dla każdego indeksu w `event_indices`
        (np. defekt_idx z TIMDRFinanceFusion.analyze()). Grupuje SĄSIADUJĄCE
        indeksy w bloki i liczy ringdown od POCZĄTKU każdego bloku (kilka
        kolejnych barów tego samego skoku nie powinno dawać wielu
        nakładających się analiz tego samego zdarzenia). Pomija zdarzenia
        na indeksie 0 (brak historii przed nimi do oszacowania szumu).

        Zwraca listę dictów: {"event_idx": int, **ringdown_resonance(...)}.
        """
        idx_list = sorted(set(int(i) for i in event_indices))
        if not idx_list:
            return []
        blocks = [idx_list[0]]
        prev = idx_list[0]
        for i in idx_list[1:]:
            if i != prev + 1:
                blocks.append(i)
            prev = i
        results = []
        for event_idx in blocks:
            if event_idx == 0:
                continue
            res = ringdown_resonance(
                t, s, event_idx,
                pre_event_window=min(event_idx, pre_event_window),
                max_lookahead=max_lookahead,
            )
            results.append({"event_idx": event_idx, **res})
        return results


class TIMDRFinanceFusion:
    """Wysokopoziomowy pipeline: surowe OHLCV -> mapa ryzyka.
    Mirror stylu TIMDRCatalogFusion / TIMDR_EarthquakeCore."""

    def __init__(self):
        self.core = TIMDR_FinanceCore()

    def analyze(self, t, open_, high, low, close, volume,
                anomaly_factor=3.0, twist_threshold=0.4, defekt_factor=0.3,
                rezonans_min=3):
        core = self.core
        t = np.asarray(t, float)
        close = np.asarray(close, float)

        sigma = core.realized_vol(close, window=6)
        delta = core.delta_proxy(open_, close) * np.asarray(volume, float)
        spread = core.spread_proxy(high, low, close)

        sigma_s = core.trm(t, sigma, k=5)
        flow_sigma = core.flow(t, sigma_s, window=5)
        twist_idx, twist_strength = core.twist(flow_sigma, t, threshold=twist_threshold)

        an_price_idx, an_price_z, _ = core.anomalies(t, close, factor=anomaly_factor)
        an_vol_idx, an_vol_z, _ = core.anomalies(t, np.asarray(volume, float), factor=anomaly_factor)
        an_sigma_idx, an_sigma_z, _ = core.anomalies(t, sigma, factor=anomaly_factor)
        an_delta_idx, an_delta_z, _ = core.anomalies(t, delta, factor=anomaly_factor)

        defekt_idx, defekt_diffs = core.defekt(close, factor=defekt_factor)

        rez_idx, rez_counts = core.rezonans(
            [an_price_idx, an_vol_idx, an_sigma_idx, an_delta_idx],
            n=len(close), min_count=rezonans_min)

        periods, rhythm_score = core.rhythm(delta, max_lag=48, power_thresh=0.4)

        # Rezonans w sensie fizycznym po skokach ceny (patrz ringdown.py) -
        # dla kazdego bloku zdarzen z defekt(), czy powrot ceny w strone
        # poziomu sprzed skoku jest oscylacyjny (overreaction + korekta)
        # czy monotoniczny (trwala przecena). pre_event_window=20
        # dopasowane do typowego okna analiz w tym repo; max_lookahead=40
        # (2x to okno) zeby nie zlapac zupelnie innego, pozniejszego skoku
        # jako czesc tego samego "powrotu". Wartosci nieskalibrowane na
        # realnych danych - patrz Ograniczenia w README.md.
        close_ringdown = core.ringdown_events(
            t, close, defekt_idx, pre_event_window=20, max_lookahead=40,
        )

        return dict(
            sigma=sigma, delta=delta, spread=spread,
            flow_sigma=flow_sigma, twist_idx=twist_idx, twist_strength=twist_strength,
            anomaly_price_idx=an_price_idx, anomaly_volume_idx=an_vol_idx,
            anomaly_sigma_idx=an_sigma_idx, anomaly_delta_idx=an_delta_idx,
            defekt_idx=defekt_idx, rezonans_idx=rez_idx, rezonans_counts=rez_counts,
            rhythm_periods=periods, rhythm_score=rhythm_score,
            close_ringdown=close_ringdown,
        )
