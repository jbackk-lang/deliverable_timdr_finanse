"""
test_selfbaseline_recovery.py -- czy anomalies()/defekt() (self-baseline,
liczone z tego samego okna co oceniane) falszywie flaguja NOWE, normalne
probki po ustaniu anomalii, tylko dlatego ze stare anomalne probki wciaz
siedza w oknie referencyjnym? Ten sam test co w siostrzanych repo
TIMDR-Crypto-Graph (test_recovery.py) i universal-state-analyzer
(test_selfbaseline_recovery.py).

ZNALEZIONY I NAPRAWIONY PRZY TYM TESCIE (nie hipotetyczny, zmierzony):
defekt() liczyl prog z rozrzutu (p90-p10) POZIOMOW ceny (s), nie z rozrzutu
SAMYCH ROZNIC dzien-do-dnia. Dla trendujacego random walk (ceny akcji/
walut) to dokladnie ten sam blad, ktory juz raz znaleziono i naprawiono w
bliznaczym module analizator-gieldowy-v3/timdr_core_finance.py::defect() -
ale poprawka nigdy nie zostala przeniesiona do TEJ (klasowej) wersji.
Zmierzone PRZED poprawka: 16.3% falszywych flag na CALKOWICIE CZYSTYM
random walk (bez zadnej anomalii!), w trybie strumieniowym (trailing
window W=30, 10 ziaren) - niemal identyczne do ~20% udokumentowanych w
gieldowy-v3 dla tego samego bledu. Naprawiono: spread liczony z diffs, i
(druga, rownie wazna polowa poprawki - pierwsza proba z samym diffs BEZ
podniesienia progu dala 49.4%, GORZEJ niz przed) domyslny factor
podniesiony 0.3 -> 3.0, jak w juz naprawionym gieldowy-v3. Po obu razem:
0.0% falszywych flag na czystym random walk.
"""
import numpy as np
from timdr_core_finance import TIMDR_FinanceCore

core = TIMDR_FinanceCore()
W = 30  # rozmiar trailing window symulujacy typowe uzycie strumieniowe


def _make_series(rng, n_pre=60, n_anom=3, n_post=20, jump=50.0):
    """Random walk z ciagla kontynuacja PRZED i PO anomalii (bez sztucznego
    dodatkowego skoku przy przejsciu - anomalia to jedyne odstepstwo)."""
    pre = 100 + np.cumsum(rng.normal(0, 0.3, n_pre))
    level = pre[-1]
    spike = np.full(n_anom, level + jump)
    post = level + np.cumsum(rng.normal(0, 0.3, n_post))
    return np.concatenate([pre, spike, post]), n_pre + n_anom


def test_defekt_zero_falszywych_flag_na_czystym_random_walk():
    """Regresja na znaleziony bug: BEZ zadnej anomalii, defekt() w trybie
    strumieniowym (W=30) nie powinien flagowac prawie nic - normalny szum
    dzien-do-dnia random walk to NIE jest defekt."""
    for seed in range(10):
        rng = np.random.default_rng(seed)
        price = 100 + np.cumsum(rng.normal(0, 0.3, 300))
        flags = sum(
            1
            for i in range(W, len(price))
            if (len(price[i - W:i + 1]) - 1) in core.defekt(price[i - W:i + 1])[0]
        )
        rate = flags / (len(price) - W)
        assert rate < 0.05, (
            f"seed={seed}: defekt() falszywie flaguje {rate*100:.1f}% czystych "
            f"probek random walk - powrocil blad rozrzutu-z-poziomow"
        )


def test_defekt_recovers_po_anomalii_bez_falszywych_flag():
    """Anomalia (skok +50) konczy sie, random walk wraca do normalnego
    zachowania (kontynuacja od poziomu SPRZED anomalii) - kolejne normalne
    probki NIE powinny byc flagowane jako defekt tylko dlatego, ze skok
    wciaz siedzi w oknie referencyjnym."""
    for seed in range(5):
        rng = np.random.default_rng(seed)
        full, event_end = _make_series(rng)
        flagged_after = [
            i for i in range(event_end + 2, event_end + 15)
            if (len(full[max(0, i - W):i + 1]) - 1)
            in core.defekt(full[max(0, i - W):i + 1])[0]
        ]
        assert flagged_after == [], (
            f"seed={seed}: defekt() wciaz flaguje normalne probki po evencie "
            f"w krokach {flagged_after}"
        )


def test_anomalies_recovers_immediately_gdy_anomalia_to_mniejszosc_okna():
    """anomalies() (MAD-z, self-baseline) - ten sam test co w
    universal-state-analyzer: anomalia mniejszosciowa w oknie (10%) nie
    powinna zostawiac sladu na kolejnych normalnych probkach, dzieki
    odpornosci mediany/MAD na mniejszosciowe wartosci odstajace."""
    for seed in range(5):
        rng = np.random.default_rng(seed)
        full, event_end = _make_series(rng, n_anom=3)
        for i in range(event_end, event_end + 5):
            window = full[max(0, i - W):i + 1]
            t_window = np.arange(len(window))
            idx, z, _ = core.anomalies(t_window, window, factor=3.0)
            last = len(window) - 1
            # kryterium to sama funkcja anomalies() (factor=3.0) - nie
            # dowolny osobny prog na z: normalny random walk ma z natury
            # nieco szerszy rozklad |z| niz N(0,1) (widziane empirycznie do
            # ~2.96 na 5 ziarnach), wiec liczy sie realne "czy flaguje", nie
            # arbitralna, ciasniejsza granica
            assert last not in idx, (
                f"seed={seed}, i={i}: anomalies() falszywie flaguje probke "
                f"tuz po evencie (z={z[-1]:.2f})"
            )
