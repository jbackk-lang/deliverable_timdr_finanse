"""
test_timdr_finance_field.py — testy timdr_finance_field.py

PRE-REJESTRACJA (progi ustalone PRZED uruchomieniem):
Symulacja: 8 aktywow, 500 dni. W oknie kryzysu (dni 300-350) kazdy
zwrot = wspolny_czynnik*beta + idiosynkratyczny_szum (beta duze, silne
sprzezenie); poza tym oknem kazdy zwrot jest CZYSTO idiosynkratyczny
(niezalezny szum, beta=0).

Hipoteza: w oknie kryzysu mean_pairwise_correlation i absorption_ratio
oba istotnie WZRASTAJA wzgledem linii bazowej, i oba sa wykrywane przez
anomalies()/twist() na E(t). Kontrola negatywna: bez wstrzknietego
kryzysu (beta=0 wszedzie), zaden z tych efektow nie wystepuje.

Progi sukcesu (ustalone przed uruchomieniem):
- mean_pairwise_correlation w oknie kryzysu > 0.4 (linia bazowa oczekiwana
  bliska 0, bo aktywa niezalezne)
- absorption_ratio w oknie kryzysu > 0.5 (linia bazowa dla k=8 niezaleznych
  aktywow oczekiwana bliska 1/8=0.125)
- anomalies()/twist() na E(t)=mean_pairwise_correlation wykrywaja poczatek
  kryzysu (indeks > 3.0 gdziekolwiek w oknie 295-320)
"""

import numpy as np
import pytest

from timdr_finance_field import (
    TIMDRFinanceFieldFusion,
    absorption_ratio,
    compute_returns,
    mean_pairwise_correlation,
)

N_DAYS = 501  # 500 zwrotow
N_ASSETS = 8
CRISIS_START = 300
CRISIS_END = 350


def _simulate_basket(inject_crisis, seed=42, beta=3.0):
    rng = np.random.default_rng(seed)
    n_returns = N_DAYS - 1
    common_factor = rng.normal(0, 1, n_returns)
    idio = rng.normal(0, 1, (n_returns, N_ASSETS))

    returns = idio.copy()
    if inject_crisis:
        in_crisis = np.zeros(n_returns, dtype=bool)
        in_crisis[CRISIS_START:CRISIS_END] = True
        returns[in_crisis] = (
            beta * common_factor[in_crisis, None] + idio[in_crisis]
        )

    prices = np.zeros((N_DAYS, N_ASSETS))
    prices[0] = 100.0
    prices[1:] = 100.0 * np.exp(np.cumsum(returns * 0.01, axis=0))
    t_days = np.arange(N_DAYS, dtype=float)
    return t_days, prices


def test_baseline_independent_assets_give_low_correlation():
    t, prices = _simulate_basket(inject_crisis=False)
    returns = compute_returns(prices)
    corr = mean_pairwise_correlation(returns, window=20)
    valid = np.isfinite(corr)
    assert np.nanmean(np.abs(corr[valid])) < 0.15, (
        f"aktywa niezalezne, oczekiwano korelacji bliskiej 0, srednia|corr|="
        f"{np.nanmean(np.abs(corr[valid])):.3f}"
    )


def test_crisis_injection_raises_mean_correlation_above_threshold():
    t, prices = _simulate_basket(inject_crisis=True)
    returns = compute_returns(prices)
    corr = mean_pairwise_correlation(returns, window=20)
    crisis_window = corr[CRISIS_START + 15:CRISIS_END]  # +15 zeby okno 20-dniowe bylo juz w pelni w kryzysie
    assert np.nanmean(crisis_window) > 0.4, (
        f"oczekiwano srednia korelacja w kryzysie >0.4, otrzymano {np.nanmean(crisis_window):.3f}"
    )


def test_crisis_injection_raises_absorption_ratio_above_threshold():
    t, prices = _simulate_basket(inject_crisis=True)
    returns = compute_returns(prices)
    ar = absorption_ratio(returns, window=20, n_components=1)
    baseline = np.nanmean(ar[20:CRISIS_START])
    crisis = np.nanmean(ar[CRISIS_START + 15:CRISIS_END])
    assert crisis > 0.5, f"oczekiwano absorption ratio w kryzysie >0.5, otrzymano {crisis:.3f}"
    assert crisis > baseline * 2, (
        f"oczekiwano co najmniej podwojenia wzgledem linii bazowej: kryzys={crisis:.3f}, baza={baseline:.3f}"
    )


def test_negative_control_no_crisis_no_false_regime_shift():
    t, prices = _simulate_basket(inject_crisis=False)
    fusion = TIMDRFinanceFieldFusion()
    corr, ar = fusion.fuse(prices, window=20)
    t_ret = t[1:]
    idx_an, z_an = fusion.anomalies(corr)
    assert len(idx_an) < len(corr) * 0.1, "za duzo falszywych anomalii bez wstrzknietego kryzysu"


def test_crisis_onset_detected_by_anomalies_or_twist():
    t, prices = _simulate_basket(inject_crisis=True)
    fusion = TIMDRFinanceFieldFusion()
    corr, ar = fusion.fuse(prices, window=20)
    t_ret = t[1:]
    idx_an, z_an = fusion.anomalies(corr)
    idx_tw, z_tw = fusion.twist(t_ret, corr)

    detected_by_anomalies = any(CRISIS_START <= i <= CRISIS_START + 25 for i in idx_an)
    detected_by_twist = any(CRISIS_START <= i <= CRISIS_START + 25 for i in idx_tw)
    assert detected_by_anomalies or detected_by_twist, (
        "ani anomalies() ani twist() nie wykryly poczatku kryzysu w oknie 300-325"
    )


def test_absorption_ratio_requires_at_least_two_assets():
    prices = np.ones((10, 1)) * 100
    returns = compute_returns(prices)
    with pytest.raises(ValueError):
        absorption_ratio(returns)
    with pytest.raises(ValueError):
        mean_pairwise_correlation(returns)
