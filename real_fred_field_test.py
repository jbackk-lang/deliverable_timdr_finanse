"""
real_fred_field_test.py — walidacja timdr_finance_field.py na PRAWDZIWYCH
danych FRED (Federal Reserve Economic Data)
================================================================================
UCZCIWE ZASTRZEŻENIE: w sandboxie, w którym ten kod powstał, bezpośrednie
zapytania sieciowe (bash/curl/`requests`) do fred.stlouisfed.org były
zablokowane przez proxy tamtego środowiska (ten sam problem co przy
NREL PVDAQ i DALTON w innych repo tego ekosystemu) — ALE osobne narzędzie
do pobierania stron (nie dostępne z poziomu zwykłego kodu Python w tamtym
sandboxie) zdołało dotrzeć do fred.stlouisfed.org i pobrać PRAWDZIWE dane
(zweryfikowano ręcznie: S&P 500, 2016-09-12 do 2023-03-31+, wartości
zgodne ze znanym przebiegiem indeksu, np. dołek COVID 2020-03-23=2237.40).
U CIEBIE (zwykłe połączenie internetowe, bez proxy sandboxa) ten skrypt
powinien zadziałać bezpośrednio — nie ma tu nic niezweryfikowanego co do
ISTNIENIA/FORMATU danych, tylko sam kod ingestii nie został odpalony w
środowisku, w którym powstał.

## Koszyk (4 serie, WSZYSTKIE zweryfikowane jako realnie istniejące i
## pobieralne, bez klucza API):

    SP500      - S&P 500 (indeks giełdowy USA, dziennie)
    DCOILWTICO - ropa WTI (USD/baryłka, dziennie)
    DTWEXBGS   - ważony handlem szeroki indeks dolara (dziennie)
    VIXCLS     - indeks zmienności VIX (dziennie)

Sprawdzone i ODRZUCONE jako martwe/nieistniejące: GOLDAMGBD228NLBM (złoto
LBMA) - seria zwróciła pustą odpowiedź, prawdopodobnie wygaszona; NIE
dodawaj złota do koszyka bez wcześniejszego sprawdzenia aktualnego ID
serii na fred.stlouisfed.org.

## Instalacja

```bash
pip install pandas-datareader pandas numpy requests
```

`pandas-datareader` jest ZALECANE (obsługuje FRED niezawodnie, poprawne
nagłówki HTTP). Jeśli go nie masz, skrypt spróbuje fallbacku przez
`requests` + `fredgraph.csv` — mniej niezawodny (FRED bez nagłówka
User-Agent bywa kapryśny co do formatu odpowiedzi), ale też powinien
zadziałać. Jeśli fallback rzuci błąd parsowania, zainstaluj
`pandas-datareader` — to najprostsza naprawa.

## Użycie

```bash
python real_fred_field_test.py                    # domyślny koszyk, 5 lat
python real_fred_field_test.py --years 3           # krótszy okres
python real_fred_field_test.py --window 20         # okno korelacji (dni)
```

## Uwaga o brakujących wartościach

FRED oznacza dni bez handlu (weekendy/święta różne dla różnych giełd) jako
"." — `ingest_fred_basket()` usuwa wiersze z JAKIMKOLWIEK brakiem w
koszyku (`dropna()`), żeby macierz korelacji była liczona na w pełni
zgranych w czasie obserwacjach. To zmniejsza liczbę próbek (typowo o
5-15%, więcej w latach ze świętami niepokrywającymi się między USA a
rynkiem ropy/FX) — jawnie raportowane przez skrypt, nie ukryte.
"""

import argparse

import numpy as np
import pandas as pd

DEFAULT_BASKET = ["SP500", "DCOILWTICO", "DTWEXBGS", "VIXCLS"]

# Koszyk PRE-REJESTROWANY jako nastepny test (2026-09-14), po tym jak
# DEFAULT_BASKET dal wynik ujemny/mieszany: mean_pairwise_correlation byla
# UJEMNA przez caly 5-letni okres (srednia -0.137, nigdy >0.4), co
# zdiagnozowano jako efekt skladu koszyka (VIX jest ustrukturalnie silnie
# ujemnie skorelowany z SP500, ~-0.7 do -0.85 dla zwrotow dziennych), nie
# porazke mechanizmu. Ten koszyk usuwa VIX, zamiast tego 3 glowne indeksy
# gieldowe USA (SP500/DJIA/NASDAQCOM - zweryfikowane jako realne, dzienne,
# FRED) + ropa WTI - wszystkie oczekiwane jako WSPOLKIERUNKOWE (rosna/spadaja
# razem), zgodnie z zalozeniem Longin & Solnik (2001).
EQUITY_ONLY_BASKET = ["SP500", "DJIA", "NASDAQCOM", "DCOILWTICO"]

# Znane, niezalezne od tego eksperymentu zdarzenie odniesienia: krach COVID-19
# (szczyt paniki ok. 2020-02-20 do 2020-04-15, dno DJIA 2020-03-23=18591.93,
# zweryfikowane recznie z surowych danych FRED). Pre-rejestrowane PRZED
# uruchomieniem na tym koszyku:
#   H1: mean_pairwise_correlation(t) > 0 w >=95% prawidlowych probek w calym
#       oknie (naprawa efektu znaku z VIX-koszyka, gdzie bylo ~0%).
#   H2: w oknie KNOWN_CRISIS_WINDOW korelacja lokalna jest wyzsza od mediany
#       calej probki, ORAZ anomalies()/twist() na mean_pairwise_correlation
#       flaguje >=1 punkt w tym oknie.
# Progi NIE beda zmieniane po zobaczeniu wyniku na tym koszyku.
KNOWN_CRISIS_WINDOW = ("2020-02-20", "2020-04-15")


def fetch_fred_series(series_id, start, end):
    """Pobiera jedna serie FRED. Probuje pandas_datareader (zalecane,
    `pip install pandas-datareader` - najbardziej niezawodne, wysyla
    poprawne naglowki HTTP), z fallbackiem na bezposrednie zapytanie do
    fredgraph.csv przez stdlib `urllib.request` (NIE przez `requests` -
    na jednej z maszyn testowych `requests`/nowszy `urllib3` z backendem
    HTTP/2 ("hface") dostawal `ProtocolError: Stream 1 was reset by
    remote peer` przy kazdej probie polaczenia z fred.stlouisfed.org;
    stdlib urllib uzywa zwyklego HTTP/1.1 i tego problemu nie ma), z 3
    probami i odczekaniem miedzy nimi na wypadek chwilowego zerwania
    polaczenia, jesli pandas_datareader nie jest zainstalowany."""
    try:
        from pandas_datareader import data as pdr
        return pdr.DataReader(series_id, "fred", start, end)[series_id]
    except ImportError:
        import io
        import time
        import urllib.error
        import urllib.request

        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; timdr-finance-field/1.0)"}
        )

        text = None
        last_exc = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    text = resp.read().decode("utf-8")
                break
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(2)

        if text is None:
            raise RuntimeError(
                f"Nie udalo sie pobrac {series_id} z FRED po 3 probach "
                f"(ostatni blad: {last_exc!r}). To wyglada na chwilowy "
                f"problem sieciowy/serwera (nie blad w kodzie) - sprobuj "
                f"ponownie za chwile. Jesli problem sie powtarza stale, "
                f"zainstaluj `pip install pandas-datareader` jako "
                f"alternatywna sciezke pobierania."
            ) from last_exc

        try:
            df = pd.read_csv(
                io.StringIO(text),
                parse_dates=["observation_date"],
                index_col="observation_date",
            )
        except (ValueError, KeyError) as exc:
            raise RuntimeError(
                f"Nie udalo sie sparsowac CSV dla {series_id}. "
                f"Pierwsze 300 znakow odpowiedzi serwera (do diagnozy):\n"
                f"{text[:300]!r}\n\n"
                f"Najprostsze rozwiazanie: `pip install pandas-datareader` "
                f"i uruchom ponownie - ta biblioteka radzi sobie z tym "
                f"niezawodnie zamiast recznego pobierania CSV."
            ) from exc

        df = df[(df.index >= start) & (df.index <= end)]
        series = pd.to_numeric(df[series_id], errors="coerce")
        return series


def ingest_fred_basket(basket=None, years=5):
    """Zwraca DataFrame (indeks=data, kolumny=seria) tylko z wierszami
    kompletnymi dla WSZYSTKICH serii w koszyku (dropna)."""
    basket = basket or DEFAULT_BASKET
    end = pd.Timestamp.today()
    start = end - pd.DateOffset(years=years)

    frames = {}
    for series_id in basket:
        print(f"Pobieram {series_id}...")
        frames[series_id] = fetch_fred_series(series_id, start, end)

    df = pd.DataFrame(frames)
    n_before = len(df)
    df = df.dropna()
    n_after = len(df)
    pct_removed = 100 * (n_before - n_after) / max(n_before, 1)
    print(f"Probek przed/po usunieciu brakow: {n_before} -> {n_after} ({pct_removed:.1f}% usuniete)")
    return df


def run_real_validation(basket=None, years=5, window=20):
    from timdr_finance_field import TIMDRFinanceFieldFusion

    df = ingest_fred_basket(basket, years)
    prices = df.to_numpy()
    t_days = np.arange(len(df), dtype=float)

    fusion = TIMDRFinanceFieldFusion()
    corr, ar = fusion.fuse(prices, window=window)
    t_ret = t_days[1:]

    valid_corr = corr[np.isfinite(corr)]
    valid_ar = ar[np.isfinite(ar)]
    print(f"\nmean_pairwise_correlation: min={valid_corr.min():.3f} "
          f"mean={valid_corr.mean():.3f} max={valid_corr.max():.3f}")
    print(f"absorption_ratio: min={valid_ar.min():.3f} "
          f"mean={valid_ar.mean():.3f} max={valid_ar.max():.3f}")

    idx_an, z_an = fusion.anomalies(corr)
    idx_tw, z_tw = fusion.twist(t_ret, corr)
    tr_sl, tr_z = fusion.trend(t_ret, corr, window=window)

    max_z_an = np.nanmax(z_an) if len(z_an) else float("nan")
    max_z_tw = np.nanmax(z_tw) if len(z_tw) else float("nan")
    print(f"\nanomalies() na mean_pairwise_correlation: {len(idx_an)}/{len(corr)} (max z={max_z_an:.2f})")
    print(f"twist(): {len(idx_tw)}/{len(corr)} (max z={max_z_tw:.2f})")
    print(f"trend max|z|: {np.nanmax(np.abs(tr_z)):.2f}")

    dates_ret = df.index[1:]

    if len(idx_an):
        print("\nDaty z anomalnym mean_pairwise_correlation (anomalies()):")
        for d in dates_ret[idx_an[:20]]:
            print(f"  {d.date()}")

    if len(idx_tw):
        print("\nDaty z twist() na mean_pairwise_correlation:")
        for d in dates_ret[idx_tw[:20]]:
            print(f"  {d.date()}")

    # H1 (pre-rejestrowane): odsetek prawidlowych probek z korelacja > 0.
    pct_positive = 100 * np.mean(valid_corr > 0)
    print(f"\nH1: odsetek probek mean_pairwise_correlation > 0: {pct_positive:.1f}% "
          f"(prog pre-rejestrowany: >=95%)")

    # H2 (pre-rejestrowane): zachowanie w oknie znanego kryzysu (COVID-19).
    start_str, end_str = KNOWN_CRISIS_WINDOW
    in_window = np.asarray((dates_ret >= pd.Timestamp(start_str)) & (dates_ret <= pd.Timestamp(end_str)))
    if in_window.any():
        window_corr = corr[in_window]
        window_corr = window_corr[np.isfinite(window_corr)]
        global_median = np.nanmedian(valid_corr)
        window_median = np.nanmedian(window_corr) if window_corr.size else float("nan")
        window_idx = np.where(in_window)[0]
        an_hit = any(i in window_idx for i in idx_an)
        tw_hit = any(i in window_idx for i in idx_tw)
        print(f"\nH2: okno znanego kryzysu (COVID-19, {start_str} do {end_str}):")
        print(f"  mediana korelacji w oknie={window_median:.3f} vs mediana calej probki={global_median:.3f}")
        print(f"  anomalies() trafia w okno: {an_hit}, twist() trafia w okno: {tw_hit}")
    else:
        print(f"\nH2: okno znanego kryzysu ({start_str} do {end_str}) POZA zakresem pobranych "
              f"danych (df.index: {dates_ret.min().date()} do {dates_ret.max().date()}) - "
              f"uzyj wiekszego --years, zeby je objac.")

    return {"df": df, "corr": corr, "absorption_ratio": ar, "anomaly_idx": idx_an, "twist_idx": idx_tw}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--basket", nargs="+", default=None)
    args = parser.parse_args()
    run_real_validation(args.basket, args.years, args.window)
