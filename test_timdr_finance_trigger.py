"""
test_timdr_finance_trigger.py — testy timdr_finance_trigger.py.

Ten plik NIE re-weryfikuje matematyki TIMDR_FinanceCore/TIMDRFinanceFusion
(41/41 testów już w test_timdr_core_finance.py/test_ringdown.py) - to nie
jest robota dispatchera. Dwa rodzaje testów:

1. test_resonance_wins_na_realnych_swiecach - JEDEN test integracyjny na
   prawdziwym TIMDRFinanceFusion (bez mockowania), na recznie skonstruowanych
   swiecach OHLCV, zeby dowiescie ze wpiecie (fusion.analyze() -> mapowanie
   na typ/lokalizacje) faktycznie dziala end-to-end.
2. Reszta testow wstrzykuje fałszywy `fusion` (prosty stub zwracajacy
   ustalony słownik, ta sama struktura co TIMDRFinanceFusion.analyze()) -
   testujemy WYLACZNIE logike priorytetow/mapowania dispatchera, nie
   ponownie cala arytmetyke rdzenia.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from timdr_finance_trigger import TIMDRFinanceTrigger, FinanceTriggerType


# ----------------------------------------------------------------------
# 1) Test integracyjny na realnych (recznie skonstruowanych) świecach
# ----------------------------------------------------------------------

def test_resonance_wins_na_realnych_swiecach():
    """
    12 świec 1h. Płaska cena/wolumen =100/10 wszędzie, JEDEN skok w idx=6:
    open=100, close=130 (świeca wzrostowa), volume=500.

    Recznie wyprowadzone (patrz analiza w PR/rozmowie, nie powtarzane tu w
    komentarzu ze wzgledu na dlugosc):
      - anomalies() na close: mad_raw=0 -> fallback std(close)=8.2916,
        z(idx6)=30/8.2916=3.618 > 3.0 -> anomalia PRICE w idx 6.
      - anomalies() na volume: mad_raw=0 -> fallback std(volume)=135.43,
        z(idx6)=449.167/135.43=3.317 > 3.0 -> anomalia VOLUME w idx 6.
      - delta_proxy = sign(close-open)*volume = 0 wszedzie oprocz idx6
        (sign=+1, delta=500). anomalies() na delta: fallback std=138.19,
        z(idx6)=458.333/138.19=3.317 > 3.0 -> anomalia DELTA w idx 6.
      - sigma (realized_vol, window=6) NIE przekracza progu 3.0 w idx6/7
        (z~0.67/1.41) -> SIGMA nie jest anomalna - nieistotne, bo mamy juz
        3 inne parametry naraz w tym samym idx = rezonans_min.
    => rezonans_idx=[6], rezonans_counts[6]=3 -> RESONANCE w lokalizacji 6,
    niezaleznie od tego, czy defekt()/twist() cokolwiek tam zglaszaja.
    """
    n = 12
    t = list(range(n))
    open_ = [100.0] * n
    close = [100.0] * n
    volume = [10.0] * n
    close[6] = 130.0
    volume[6] = 500.0
    # open[6] zostaje 100.0 -> swieca wzrostowa (sign=+1) w idx 6
    high = [max(open_[i], close[i]) for i in range(n)]
    low = [min(open_[i], close[i]) for i in range(n)]

    trigger = TIMDRFinanceTrigger()
    result = trigger.analyze(t, open_, high, low, close, volume)

    assert result.triggered is True
    assert result.trigger_type == FinanceTriggerType.RESONANCE
    assert result.location == 6
    assert "3" in result.message


# ----------------------------------------------------------------------
# 2) Testy priorytetow dispatchera z wstrzyknietym fusion (stub)
# ----------------------------------------------------------------------

class _FakeFusion:
    """Stub o tym samym kontrakcie co TIMDRFinanceFusion.analyze(): zwraca
    ustalony słownik niezależnie od danych wejściowych."""

    def __init__(self, result_dict):
        self._result = result_dict

    def analyze(self, *args, **kwargs):
        return self._result


def _empty_result(**overrides):
    base = dict(
        rezonans_idx=[], rezonans_counts=[0] * 20,
        twist_idx=[], twist_strength=[],
        defekt_idx=[],
        anomaly_price_idx=[], anomaly_volume_idx=[],
        anomaly_sigma_idx=[], anomaly_delta_idx=[],
    )
    base.update(overrides)
    return base


def _dummy_args():
    n = 5
    z = [0.0] * n
    return (list(range(n)), z, z, z, z, z)


def test_priorytet_resonance_nad_wszystkim():
    counts = [0] * 20
    counts[8] = 4
    fake = _FakeFusion(_empty_result(
        rezonans_idx=[8], rezonans_counts=counts,
        twist_idx=[3], defekt_idx=[5],
        anomaly_price_idx=[1],
    ))
    trigger = TIMDRFinanceTrigger(fusion=fake)
    result = trigger.analyze(*_dummy_args())
    assert result.trigger_type == FinanceTriggerType.RESONANCE
    assert result.location == 8
    assert "4" in result.message


def test_priorytet_structure_nad_defekt_i_scale():
    fake = _FakeFusion(_empty_result(
        twist_idx=[5], defekt_idx=[7],
        anomaly_price_idx=[1], anomaly_volume_idx=[2],
    ))
    trigger = TIMDRFinanceTrigger(fusion=fake)
    result = trigger.analyze(*_dummy_args())
    assert result.trigger_type == FinanceTriggerType.STRUCTURE
    assert result.location == 5


def test_priorytet_defekt_nad_scale():
    fake = _FakeFusion(_empty_result(
        defekt_idx=[9],
        anomaly_price_idx=[1], anomaly_delta_idx=[2],
    ))
    trigger = TIMDRFinanceTrigger(fusion=fake)
    result = trigger.analyze(*_dummy_args())
    assert result.trigger_type == FinanceTriggerType.DEFEKT
    assert result.location == 9


def test_scale_gdy_tylko_jeden_parametr_anomalny():
    fake = _FakeFusion(_empty_result(anomaly_volume_idx=[3]))
    trigger = TIMDRFinanceTrigger(fusion=fake)
    result = trigger.analyze(*_dummy_args())
    assert result.triggered is True
    assert result.trigger_type == FinanceTriggerType.SCALE
    assert result.location == 3


def test_scale_lokalizacja_to_najmniejszy_indeks_z_kilku_parametrow():
    """Kiedy różne parametry anomalne są w różnych indeksach (i żaden nie
    dociąga do rezonans_min), lokalizacja SCALE to najmniejszy z nich -
    najwczesniejszy sygnal, nie pierwszy sprawdzony parametr."""
    fake = _FakeFusion(_empty_result(
        anomaly_price_idx=[7], anomaly_volume_idx=[2], anomaly_sigma_idx=[4],
    ))
    trigger = TIMDRFinanceTrigger(fusion=fake)
    result = trigger.analyze(*_dummy_args())
    assert result.trigger_type == FinanceTriggerType.SCALE
    assert result.location == 2


def test_none_gdy_wszystko_puste():
    fake = _FakeFusion(_empty_result())
    trigger = TIMDRFinanceTrigger(fusion=fake)
    result = trigger.analyze(*_dummy_args())
    assert result.triggered is False
    assert result.trigger_type == FinanceTriggerType.NONE
    assert result.location is None


def test_get_last_zwraca_ostatni_wynik():
    fake = _FakeFusion(_empty_result(defekt_idx=[4]))
    trigger = TIMDRFinanceTrigger(fusion=fake)
    result = trigger.analyze(*_dummy_args())
    assert trigger.get_last() is result
