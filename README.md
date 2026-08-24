# TIMDR-Finanse

Sygnały TIMDR (TRM/FLOW/TWIST/RHYTHM + anomalie/defekt/rezonans), przeniesione
1:1 z earthquake/catalog_core, odpalone na realnych świecach 1h z dwóch
różnych rynków: BTC/USD i złoto (PAXG/USD, token 1:1 wsparty złotem, 30 dni
każdy). Sprawdzone kauzalnie (walk-forward, bez podglądania przyszłości), z
drugim instrumentem specjalnie po to, żeby sprawdzić, czy cokolwiek z BTC się
powtarza (spoiler: prawie nic).

Krótko: prawie nic z tego nie przewiduje ceny — i to jest spodziewany,
uczciwy wynik na rynku (w odróżnieniu od trzęsień ziemi, tu ktoś na
drugim końcu zjada każdy łatwy wzorzec).

## Pliki

- `timdr_core_finance.py` — sam rdzeń. `TIMDR_FinanceCore` (trm/flow/twist/
  anomalie/defekt/rhythm/rezonans/ringdown_events) + `TIMDRFinanceFusion`
  (pełny pipeline z surowych OHLCV). Uwaga na górze pliku: `delta_proxy`/
  `spread_proxy` to przybliżenia z samych świec, nie prawdziwy order flow
  — nie ma tu orderbooka.
- `ringdown.py` — `ringdown_resonance()`: rezonans w SENSIE FIZYCZNYM (nie
  licznik koincydencji jak `rezonans()` wyżej) — po skoku ceny (`defekt()`),
  czy powrót w stronę poziomu sprzed skoku jest oscylacyjny (overreaction
  + korekta) czy monotoniczny (trwała przecena). Wynik w `close_ringdown`
  zwracanym przez `TIMDRFinanceFusion.analyze()`. **Nieprzetestowane
  predykcyjnie w tym repo** — patrz "Wyniki, bez owijania w bawełnę" niżej.
- `test_timdr_core_finance.py` — 29 testów jednostkowych (w tym integracja
  `ringdown_events()`/`close_ringdown`).
- `test_ringdown.py` — 12 testów `ringdown_resonance()` (walidacja na
  syntetycznym tłumionym oscylatorze o znanej częstotliwości/tłumieniu —
  port 1:1 z `jbackk-lang/universal-state-analyzer`, `analizator-gieldowy-v3`
  i `TIMDR-Grid-Monitor`, gdzie ta sama funkcja jest już zweryfikowana i
  udokumentowana pełną historią znalezionych i naprawionych błędów).
  `pytest -q` (41/41 łącznie z powyższym).
- `backtest_finance.py` / `backtest_gold.py` — główny backtest (BTC / złoto):
  prognoza zmienności (6h), prognoza kierunku (6h), kontrole
  `anomalies()`/`rhythm()`. Identyczna logika, inne dane wejściowe.
- `backtest_finance_extended.py` / `backtest_gold_extended.py` — dodatkowy
  test "czy cokolwiek tu w ogóle działa": siatka horyzontów 1-24h z
  train/test splitem (żeby nie oszukać się przypadkiem) + mean-reversion
  po anomaliach.
- `make_charts.py` / `make_charts_gold.py` — po 2 PNG na instrument
  (cena+anomalie, prognoza zmienności).
- `build_dashboard.py` — skleja wszystkie PNG + tabele wyników (oba
  instrumenty) w `dashboard.html` (jeden plik, otwierasz w przeglądarce,
  nic nie trzeba instalować).
- `run.bat` — odpala to wszystko od zera (venv, pip install, testy,
  wszystkie backtesty, wykresy, dashboard) i sam otwiera dashboard.
  Podwójny klik, wymaga Pythona 3.10+ w PATH.
- `RAPORT_TIMDR_Finanse.md` — pełny raport z metodologią, tabelami,
  zastrzeżeniami — jak coś nie gra, tam jest szczegół.
- `dashboard.html`, `chart_*.png`, `backtest_*output*.txt` — gotowe wyniki
  z ostatniego przebiegu (nie musisz nic odpalać, żeby je zobaczyć).
- `data/btcusd_1h.csv`, `data/paxgusd_1h.csv` — po 720 świec 1h,
  2026-07-18 – 2026-08-17. Uwaga: w danych złota 54/720 świec ma tylko
  cenę zamknięcia (open=high=low=close jako przybliżenie) — nie wpływa na
  zwroty/zmienność/kierunek, zeruje tylko spread_proxy dla tych godzin.

## Wyniki, bez owijania w bawełnę

- Persystencja zmienności działa (r=0.38) — ale to zwykły baseline
  ("ostatnie 24h = prognoza"), nie zasługa TIMDR. `flow_sigma` (korekta
  TIMDR) nic nie dodaje — r=0.02, +0% poprawy out-of-sample.
- Prosty kierunek z FLOW na 6h — gorzej niż strategia "zawsze w górę".
  Rynek na tym horyzoncie nieprzewidywalny tym sygnałem.
- `anomalies()` łapie realne duże ruchy — ale jako opis tego, co się już
  stało, nie jako predykcję.
- `rhythm()` na wolumenie — słaby, realny cykl dobowy (0.20), całkowicie
  przykryty przez klastrowanie godzina-do-godziny (0.54). BTC handluje się
  24/7 na całym świecie, więc pojedynczy cykl dobowy się rozmywa.
- Dodatkowy test na BTC (siatka horyzontów + mean-reversion po anomaliach):
  reversal na 12h formalnie przetrwał jeden out-of-sample split (0.583 vs
  0.500) — WYGLĄDAŁO obiecująco, więc sprawdziłem to samo na złocie.
- **Replikacja na złocie: nie przetrwała.** Ta sama metoda na PAXG/USD
  wybrała inną strategię (momentum, nie reversal) i out-of-sample wyszło
  0.527 vs baseline 0.606 — gorzej niż baza. Czyli "sygnał" z BTC to był
  najpewniej zwykły przypadek (jeden trend w jednej próbce), nie coś
  realnego — dokładnie to, przed czym ostrzegałem sam siebie w
  poprzedniej wersji tego pliku. Mean-reversion po anomaliach na złocie
  też nie powtarza wzorca z BTC. Persystencja zmienności za to działa na
  obu (r=0.38 BTC, r=0.45 złoto) — jedyny sygnał, który się replikuje,
  i to jest baseline, nie coś od TIMDR.

Czyli: gotowej strategii tu nie ma, i drugi instrument to potwierdził —
"ciekawy trop" z BTC nie przeżył konfrontacji z niezależnymi danymi.

**Nowy sygnał, jeszcze nie przetestowany (`ringdown.py`):** dla skoków
ceny (`defekt()`) sprawdza, czy powrót jest oscylacyjny czy monotoniczny
(patrz opis w "Pliki"). Sama funkcja jest zweryfikowana numerycznie na
syntetykach (znana częstotliwość/tłumienie odzyskane poprawnie — te same
testy co w siostrzanych repo tego zestawu), ale NIE przeszła tu
kauzalnego backtestu jak reszta sygnałów w tym pliku — nie wiadomo, czy
"oscylacyjny ringdown" cokolwiek mówi o przyszłej cenie, czy jest tak
samo szumem jak reversal na 12h, który nie przetrwał replikacji na
złocie. Traktuj `close_ringdown` jako opisowy sygnał diagnostyczny (co
się stało po skoku), nie jako trop inwestycyjny, dopóki ktoś nie
przepuści go przez `backtest_finance_extended.py`-owy rygor.

## A ropa?

Pytanie: może to ropa kształtuje układ. Sprawdziłem, ale tylko częściowo —
godzinowych/dziennych danych ropy nie dało się technicznie ściągnąć w tej
sesji (Kraken ich nie ma, darmowe API wymagają płatnego klucza albo są
zablokowane, a rządowe archiwa USA — FRED/EIA — są za duże/za dziwnie
skompresowane dla narzędzia do pobierania stron). Udało się za to wyciągnąć
realne dane **miesięczne** z EIA (`chart_oil_context.png`,
`data/wti_monthly.csv`): ropa WTI skoczyła z 64,51 USD/bbl (luty 2026) do
102,13 USD/bbl (maj 2026, +58%), potem spadła do 80,46 USD/bbl (lipiec) —
czyli była podwyższona, ale już po szczycie, dokładnie gdy zaczynało się
nasze okno testowe na BTC/złocie. To ciekawa zbieżność w czasie z rajdem
złota, ale **nie jest to test kauzalny** jak reszta tego projektu — jeden
punkt na miesiąc to za mało, żeby policzyć cokolwiek na poziomie
godzinowym. Szczegóły i zastrzeżenia w `RAPORT_TIMDR_Finanse.md`. Jeśli
masz gdzieś dostęp do godzinowych/dziennych danych ropy z tego okresu, wrzuć
je, a przepuszczę je przez ten sam pipeline.

## Jak odpalić

Podwójny klik na `run.bat` (Windows). Zrobi wszystko sam: venv, zależności,
testy, oba backtesty, wykresy, dashboard — i otworzy dashboard w
przeglądarce na koniec.
