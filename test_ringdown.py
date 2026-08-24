"""
test_ringdown.py — walidacja ringdown_resonance() na syntetycznych danych
o znanej częstotliwości/tłumieniu, w realnych sekundach (świece 1h, tak
jak `t` jest budowane w backtest_finance.py: `t = ... * 3600`). Ten sam
wzorzec walidacji co w universal-state-analyzer/tests/test_ringdown.py,
TIMDR-Grid-Monitor/test_ringdown.py i analizator-gieldowy-v3/test_ringdown.py
(skąd ta funkcja jest portowana 1:1).
"""
import numpy as np
import pytest

from ringdown import ringdown_resonance

DT = 3600.0  # świece 1h, w sekundach - jak w backtest_finance.py


def _damped_oscillator(n, event_idx, f0, tau, amplitude=500.0, noise_sigma=0.0, seed=0):
    t = np.arange(n, dtype=float) * DT
    post = t[event_idx:] - t[event_idx]
    x = np.zeros(n)
    x[event_idx:] = amplitude * np.exp(-post / tau) * np.cos(2 * np.pi * f0 * post)
    if noise_sigma > 0:
        rng = np.random.default_rng(seed)
        x = x + rng.normal(0, noise_sigma, n)
    return t, x


def _monotonic_decay(n, event_idx, tau, amplitude=500.0, noise_sigma=0.0, seed=0):
    t = np.arange(n, dtype=float) * DT
    post = t[event_idx:] - t[event_idx]
    x = np.zeros(n)
    x[event_idx:] = amplitude * np.exp(-post / tau)
    if noise_sigma > 0:
        rng = np.random.default_rng(seed)
        x = x + rng.normal(0, noise_sigma, n)
    return t, x


def test_underdamped_recovers_known_frequency_and_damping():
    """Cena 'dzwoni' z powrotem do poziomu sprzed skoku - okres kołysania
    (w sekundach) i tłumienie odzyskane zgodnie z teorią."""
    n, event_idx = 400, 100
    period_hours = 6.0
    f0 = 1.0 / (period_hours * 3600.0)
    tau = 10.0 * 3600.0  # zanik w ~10h
    t, x = _damped_oscillator(n, event_idx, f0, tau, noise_sigma=5.0)
    res = ringdown_resonance(t, x, event_idx=event_idx, pre_event_window=event_idx)
    assert res["is_oscillatory"] is True
    assert res["frequency_hz"] == pytest.approx(f0, rel=0.08)
    zeta_theory = 1.0 / np.sqrt((2 * np.pi * f0 * tau) ** 2 + 1)
    assert res["damping_ratio"] == pytest.approx(zeta_theory, rel=0.3)


def test_overdamped_monotonic_decay_is_not_oscillatory():
    """Permanentne przecenienie/przewartościowanie - cena osiada na nowym
    poziomie bez odbicia. NIE jest to rezonans."""
    n, event_idx = 400, 100
    t, x = _monotonic_decay(n, event_idx, tau=8.0 * 3600.0, noise_sigma=5.0)
    res = ringdown_resonance(t, x, event_idx=event_idx, pre_event_window=event_idx)
    assert res["is_oscillatory"] is False


def test_bug_niefiltrowany_szum_dawal_falszywy_rezonans():
    """Regresja: bez progu szumu, sam szum w ogonie zanikłego sygnału
    generuje dziesiątki fałszywych przejść i błędne is_oscillatory=True."""
    n, event_idx = 400, 100
    t, x = _monotonic_decay(n, event_idx, tau=8.0 * 3600.0, noise_sigma=5.0)
    res_filtered = ringdown_resonance(t, x, event_idx=event_idx, pre_event_window=event_idx)
    res_unfiltered = ringdown_resonance(
        t, x, event_idx=event_idx, pre_event_window=event_idx, noise_floor_factor=0.0,
    )
    assert res_filtered["is_oscillatory"] is False
    assert res_unfiltered["n_crossings"] > 10


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_underdamped_frequency_stable_across_seeds(seed):
    n, event_idx = 400, 100
    f0 = 1.0 / (8.0 * 3600.0)
    t, x = _damped_oscillator(n, event_idx, f0, tau=12.0 * 3600.0, noise_sigma=5.0, seed=seed)
    res = ringdown_resonance(t, x, event_idx=event_idx, pre_event_window=event_idx)
    assert res["is_oscillatory"] is True
    assert res["frequency_hz"] == pytest.approx(f0, rel=0.1)


def test_too_short_window_returns_safe_default():
    t = np.arange(5, dtype=float) * DT
    x = np.array([60000.0, 60000.0, 60500.0, 60600.0, 60400.0])
    res = ringdown_resonance(t, x, event_idx=3, pre_event_window=3)
    assert res["is_oscillatory"] is False
    assert res["frequency_hz"] is None


def test_event_idx_out_of_range_raises():
    t = np.arange(10, dtype=float) * DT
    x = np.zeros(10)
    with pytest.raises(ValueError):
        ringdown_resonance(t, x, event_idx=99)


def test_event_idx_zero_no_pre_history_falls_back_to_unfiltered():
    n = 50
    t, x = _damped_oscillator(n, event_idx=0, f0=1.0 / (5 * 3600.0), tau=6 * 3600.0)
    res = ringdown_resonance(t, x, event_idx=0, pre_event_window=10)
    assert res["noise_floor"] == 0.0


def test_explicit_baseline_overrides_pre_event_mean():
    n, event_idx = 100, 30
    x = np.full(n, 60000.0)
    x[event_idx:] = 60500.0
    t = np.arange(n, dtype=float) * DT
    res = ringdown_resonance(t, x, event_idx=event_idx, baseline=60000.0, pre_event_window=event_idx)
    assert res["baseline"] == 60000.0
