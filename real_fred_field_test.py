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
pip install pandas-datareader pandas numpy
```

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


def fetch_fred_series(series_id, start, end):
    """Pobiera jedna serie FRED. Probuje pandas_datareader (standardowa
    biblioteka), z fallbackiem na bezposrednie zapytanie do
    fredgraph.csv, jesli pandas_datareader nie jest zainstalowany."""
    try:
        from pandas_datareader import data as pdr
        return pdr.DataReader(series_id, "fred", start, end)[series_id]
    except ImportError:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        df = pd.read_csv(url, parse_dates=["DATE"], index_col="DATE")
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
    print(f"Probek przed/po usunieciu brakow: {n_before} -> {n_after} "
          f"({100*(n_before-n_after)/max(n_before,1):.1f}% usuniete)")
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

    print(f"\nanomalies() na mean_pairwise_correlation: {len(idx_an)}/{len(corr)} "
          f"(max z={np.nanmax(z_an) if len(z_an) else float('nan'):.2f})")
    print(f"twist(): {len(idx_tw)}/{len(corr)} (max z={np.nanmax(z_tw) if len(z_tw) else float('nan'):.2f})")
    print(f"trend max|z|: {np.nanmax(np.abs(tr_z)):.2f}")

    if len(idx_an):
        print("\nDaty z anomalnym mean_pairwise_correlation (indeksy w koszyku dropna, nie kalendarzowe):")
        dates = df.index[1:][idx_an[:20]]
        for d in dates:
            print(f"  {d.date()}")

    return {"df": df, "corr": corr, "absorption_ratio": ar, "anomaly_idx": idx_an}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--basket", nargs="+", default=None)
    args = parser.parse_args()
    run_real_validation(args.basket, args.years, args.window)
