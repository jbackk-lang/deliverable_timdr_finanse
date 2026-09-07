# ============================================
# TIMDR Finance Trigger Module
# ============================================
#
# ROLA: czujnik sygnałowy integralności serii rynkowej — NIE model, NIE
# strategia inwestycyjna. Zobacz zastrzeżenia w timdr_core_finance.py i
# README.md: ten pipeline (TRM/FLOW/TWIST/RHYTHM + anomalie/defekt/rezonans)
# NIE jest zwalidowanym predyktorem ceny (backtest na BTC i złocie pokazał,
# że "ciekawe" sygnały nie replikują się między instrumentami). Ten plik nie
# liczy własnej statystyki i nie próbuje przewidywać przyszłości — jedyna
# jego robota: zapytać już przetestowany TIMDRFinanceFusion.analyze()
# (41/41 testów w timdr_core_finance.py/ringdown.py) i powiedzieć, KTÓRY typ
# zdarzenia sygnałowego odpalił się w danych i GDZIE.
#
# Priorytet: RESONANCE (>=rezonans_min niezależnych parametrów [cena/
# wolumen/sigma/delta] anomalnych naraz — najsilniejszy, najbardziej
# ugruntowany dowód, ta sama zasada koincydencji co w catalog_core.py) >
# STRUCTURE (twist — załamanie kierunku trendu zmienności) > DEFEKT
# (pojedynczy nagły skok ceny między sąsiadującymi świecami) > SCALE
# (pojedynczy parametr statystycznie odstający wg anomalies()) > NONE.
# Silniejszy/łączny dowód wygrywa niezależnie od tego, co pojawiło się
# chronologicznie pierwsze w danych — ta sama zasada co w
# TIMDR-Security-Module i TIMDR-Aviation-Diagnostics.

from enum import Enum

from timdr_core_finance import TIMDRFinanceFusion


class FinanceTriggerType(Enum):
    RESONANCE = "resonance"
    STRUCTURE = "structure_twist"
    DEFEKT = "defekt"
    SCALE = "scale_anomaly"
    NONE = "none"


class FinanceTriggerResult:
    def __init__(self, triggered=False, trigger_type=FinanceTriggerType.NONE,
                 location=None, message=""):
        self.triggered = triggered
        self.trigger_type = trigger_type
        self.location = location
        self.message = message

    def as_dict(self):
        return {
            "triggered": self.triggered,
            "type": self.trigger_type.value,
            "location": self.location,
            "message": self.message,
        }


class TIMDRFinanceTrigger:
    """
    Dispatcher nad TIMDRFinanceFusion. `fusion` można wstrzyknąć (np. w
    testach) — domyślnie tworzy prawdziwy TIMDRFinanceFusion(). Progi
    (anomaly_factor, twist_threshold, defekt_factor, rezonans_min) to te
    same punkty startowe do dostrojenia co w reszcie ekosystemu, nie
    wartości uniwersalne.
    """

    def __init__(self, anomaly_factor=3.0, twist_threshold=0.4,
                 defekt_factor=0.3, rezonans_min=3, fusion=None):
        self.fusion = fusion if fusion is not None else TIMDRFinanceFusion()
        self.anomaly_factor = anomaly_factor
        self.twist_threshold = twist_threshold
        self.defekt_factor = defekt_factor
        self.rezonans_min = rezonans_min
        self.last_result = FinanceTriggerResult()

    def analyze(self, t, open_, high, low, close, volume):
        r = self.fusion.analyze(
            t, open_, high, low, close, volume,
            anomaly_factor=self.anomaly_factor,
            twist_threshold=self.twist_threshold,
            defekt_factor=self.defekt_factor,
            rezonans_min=self.rezonans_min,
        )

        if len(r["rezonans_idx"]):
            loc = int(r["rezonans_idx"][0])
            count = int(r["rezonans_counts"][loc])
            return self._set_result(
                True, FinanceTriggerType.RESONANCE, loc,
                f"{count} niezależnych parametrów anomalnych naraz."
            )

        if len(r["twist_idx"]):
            loc = int(r["twist_idx"][0])
            return self._set_result(
                True, FinanceTriggerType.STRUCTURE, loc,
                "Załamanie trendu zmienności (twist na flow_sigma)."
            )

        if len(r["defekt_idx"]):
            loc = int(r["defekt_idx"][0])
            return self._set_result(
                True, FinanceTriggerType.DEFEKT, loc,
                "Nagły skok ceny między sąsiadującymi świecami."
            )

        single = sorted(set(
            list(r["anomaly_price_idx"]) + list(r["anomaly_volume_idx"]) +
            list(r["anomaly_sigma_idx"]) + list(r["anomaly_delta_idx"])
        ))
        if single:
            return self._set_result(
                True, FinanceTriggerType.SCALE, int(single[0]),
                "Pojedynczy parametr statystycznie odstający."
            )

        return self._set_result(
            False, FinanceTriggerType.NONE, None,
            "Brak wykrytego zdarzenia sygnałowego."
        )

    def _set_result(self, triggered, trigger_type, location, message):
        self.last_result = FinanceTriggerResult(triggered, trigger_type, location, message)
        return self.last_result

    def get_last(self):
        return self.last_result
