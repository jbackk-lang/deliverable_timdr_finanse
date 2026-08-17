"""
test_timdr_core_finance.py — testy jednostkowe TIMDR-Finanse

Konwencja jak w test_timdr_core_earthquake.py / test_catalog_core.py:
odpornosc na n=0/1/2, kontrola pulapki zero-inflation (MAD=0), kontrola
bledu rektyfikacji w rhythm(), kontrola liczenia gradientu wzgledem
CZASU (nie indeksu) na danych z luka.
"""
import numpy as np
import pytest
from timdr_core_finance import TIMDR_FinanceCore, TIMDRFinanceFusion

core = TIMDR_FinanceCore()


# ---------------------------------------------------------------
# Odpornosc na krotkie serie (n=0,1,2) - nie moze crashowac
# ---------------------------------------------------------------
@pytest.mark.parametrize("n", [0, 1, 2])
def test_trm_n_male(n):
    t = np.arange(n, dtype=float)
    s = np.arange(n, dtype=float)
    out = core.trm(t, s)
    assert len(out) == n


@pytest.mark.parametrize("n", [0, 1, 2])
def test_flow_n_male(n):
    t = np.arange(n, dtype=float)
    s = np.arange(n, dtype=float)
    out = core.flow(t, s)
    assert len(out) == n


@pytest.mark.parametrize("n", [0, 1, 2])
def test_twist_n_male(n):
    flow_vals = np.arange(n, dtype=float)
    t = np.arange(n, dtype=float)
    idx, dg = core.twist(flow_vals, t)
    assert len(idx) == 0  # za malo danych na sensowny twist


@pytest.mark.parametrize("n", [0, 1, 2])
def test_anomalies_n_male(n):
    t = np.arange(n, dtype=float)
    s = np.arange(n, dtype=float)
    idx, z, th = core.anomalies(t, s)
    assert len(z) == n


@pytest.mark.parametrize("n", [0, 1])
def test_defekt_n_male(n):
    s = np.arange(n, dtype=float)
    idx, diffs = core.defekt(s)
    assert len(idx) == 0


@pytest.mark.parametrize("n", [0, 1])
def test_rhythm_n_male(n):
    s = np.arange(n, dtype=float)
    periods, score = core.rhythm(s)
    assert periods == [] and score == 0.0


# ---------------------------------------------------------------
# anomalies(): pulapka zero-inflation / MAD=0 (Blad 2 z
# timdr_core_earthquake.py, przeniesiony na np. wolumen w martwych
# godzinach - same zera + jeden nietypowy odczyt)
# ---------------------------------------------------------------
def test_anomalies_zero_inflated_nie_wybucha():
    # 20 zer (martwy rynek) + jeden nietypowy, niewielki odczyt
    s = np.zeros(21)
    s[10] = 0.01
    idx, z, th = core.anomalies(np.arange(21, dtype=float), s, factor=3.0)
    # prog nie moze byc doslownie zero (inaczej kazdy niezerowy odczyt =
    # "anomalia" - dokladnie blad #2 z earthquake core)
    assert th > 0
    assert np.isfinite(z).all()


def test_anomalies_stala_seria_nie_crashuje():
    s = np.full(15, 5.0)
    idx, z, th = core.anomalies(np.arange(15, dtype=float), s)
    assert np.isfinite(z).all()
    assert len(idx) == 0  # stala seria - nic nie powinno byc anomalia


# ---------------------------------------------------------------
# twist(): gradient MUSI byc liczony wzgledem CZASU, nie indeksu -
# dokladnie Blad 1 z timdr_core_earthquake.py. Test: gladka fala z luka
# w rejestracji NIE powinna dawac falszywego alarmu na granicy luki.
# ---------------------------------------------------------------
def test_twist_brak_falszywego_alarmu_na_luce_czasowej():
    # gladki sinus, ale z 3-krotnie wieksza przerwa czasowa w polowie
    t1 = np.linspace(0, 5, 50)
    t2 = np.linspace(20, 25, 50)  # ta sama predkosc probkowania, duza przerwa
    t = np.concatenate([t1, t2])
    s = np.sin(t * 0.5)
    flow_vals = core.flow(t, s, window=5)
    idx, dg = core.twist(flow_vals, t, threshold=0.4)
    # punkt na granicy przerwy (okolice indeksu 49/50) nie powinien
    # dominowac - sila tam nie powinna byc rzedy wielkosci wieksza niz
    # typowa w reszcie sygnalu
    boundary = dg[47:52]
    typical = np.median(np.abs(dg[np.r_[0:40, 60:100]]))
    assert np.max(np.abs(boundary)) < 20 * max(typical, 1e-9)


# ---------------------------------------------------------------
# rhythm(): musi dzialac na wartosci ZE ZNAKIEM, nie rektyfikowanej -
# ten sam blad co w catalog_core.py (rektyfikacja tworzy sztuczna
# okresowosc). Test posrednio: szum bialy (bez okresowosci) nie
# powinien dawac wysokiego score.
# ---------------------------------------------------------------
def test_rhythm_szum_bialy_brak_okresowosci():
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 1, 500)
    periods, score = core.rhythm(noise, max_lag=48, power_thresh=0.4)
    assert score < 0.4


def test_rhythm_wykrywa_prawdziwa_periodycznosc():
    t = np.arange(500)
    signal = np.sin(2 * np.pi * t / 24)  # okres 24 (np. cykl sesyjny)
    periods, score = core.rhythm(signal, max_lag=48, power_thresh=0.4)
    assert score >= 0.4
    assert any(abs(p - 24) <= 1 for p in periods)


# ---------------------------------------------------------------
# defekt(): podloga na zero-inflated serii (np. delta_proxy na plytkim
# rynku - same zera + jeden skok)
# ---------------------------------------------------------------
def test_defekt_zero_inflated_ma_podloge():
    s = np.zeros(20)
    s[10] = 100.0  # jeden duzy skok
    idx, diffs = core.defekt(s, factor=0.3)
    assert len(idx) > 0  # skok 0->100 powinien byc wykryty
    assert 10 in idx or 11 in idx


# ---------------------------------------------------------------
# rezonans(): >=3 parametrow flagujacych ten sam punkt
# ---------------------------------------------------------------
def test_rezonans_wymaga_wielu_parametrow():
    n = 10
    a = [3]
    b = [3, 7]
    c = [3, 7]
    d = [7]
    idx, counts = core.rezonans([a, b, c, d], n=n, min_count=3)
    assert 3 in idx  # flagowany przez a,b,c = 3 parametry
    assert 7 in idx  # flagowany przez b,c,d = 3 parametry
    assert counts[3] == 3 and counts[7] == 3


# ---------------------------------------------------------------
# Pelny pipeline (TIMDRFinanceFusion.analyze) - integracyjny, nie
# crashuje na realistycznym ksztalcie danych OHLCV
# ---------------------------------------------------------------
def test_analyze_pelny_pipeline_nie_crashuje():
    rng = np.random.default_rng(1)
    n = 200
    t = np.arange(n, dtype=float) * 3600  # sekundy, co godzine
    close = 60000 + np.cumsum(rng.normal(0, 50, n))
    open_ = close - rng.normal(0, 20, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 10, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 10, n))
    volume = np.abs(rng.normal(20, 5, n))

    fusion = TIMDRFinanceFusion()
    result = fusion.analyze(t, open_, high, low, close, volume)
    assert 'twist_idx' in result
    assert 'rezonans_idx' in result
    assert np.isfinite(result['sigma']).all()


if __name__ == '__main__':
    import sys
    sys.exit(pytest.main([__file__, '-v']))
