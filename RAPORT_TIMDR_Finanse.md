# TIMDR-Finanse — test na realnych danych rynkowych (BTC/USD i złoto)

**Pytanie:** czy sygnały z rodziny TIMDR (TRM/FLOW/TWIST/RHYTHM), które w
`TIMDR-Earthquake-Core` dają realną, policzalną przewagę w krótkoterminowej
prognozie aftershocków, przenoszą się na dane rynkowe? Sprawdzone na
prawdziwych, pobranych na żywo świecach 1h BTC/USD (Kraken) — nie na danych
syntetycznych, i **kauzalnie** (prognoza w chwili D używa wyłącznie danych
sprzed D).

Krótka odpowiedź: **w większości — nie, i to jest oczekiwany, uczciwy
wynik.** Rynki różnią się fundamentalnie od trzęsień ziemi i pogody: nie są
zjawiskiem fizycznym bez pamięci strategicznej, tylko areną, na której
tysiące uczestników aktywnie poluje na dokładnie ten typ wzorca, który
próbuje wykryć TIMDR — a im prostszy i bardziej znany wzorzec, tym szybciej
zostaje zarbitrażowany. Jedyne miejsce, gdzie test poniżej znajduje coś
realnego, to zjawisko już dobrze znane literaturze (klastrowanie
zmienności) — TIMDR go nie odkrywa, tylko potwierdza, że go nie psuje.

---

## Dane

720 świec 1h BTC/USD, Kraken (`api.kraken.com/0/public/OHLC`), 2026-07-18 —
2026-08-17 (30 dni), zakres ceny 62 452 – 66 808 USD. Zweryfikowane
wewnętrznie: idealnie równe odstępy 3600s między świecami, zero luk w danych.
Brak dostępu do prawdziwego order booku / danych tickowych — `delta_proxy`
(znak świecy × wolumen) i `spread_proxy` ((high-low)/close) to jawnie
zadeklarowane **przybliżenia**, nie prawdziwy order-flow ani bid/ask spread.

---

## Test 1: prognoza zmienności (kolejne 6h)

**Metoda:** walk-forward, 182 punkty (co 3h, po tygodniu rozgrzewki), w
każdym punkcie D porównanie trzech prognoz zrealizowanej zmienności w
kolejnych 6h: (a) naiwna persystencja — średnia zmienność z ostatnich 24h,
(b) długoterminowa średnia ze wszystkich danych sprzed D, (c) TIMDR
`flow_sigma` — kauzalny trend wygładzonej zmienności (`trm()` + `flow()`).

![Prognoza zmienności](chart_vol_forecast.png)

| Metoda | MAE | Korelacja z realną przyszłą zmiennością |
|---|---:|---:|
| Naiwna persystencja (24h) | 0.000947 | r = 0.381 |
| Długoterminowa średnia | 0.001062 | — |
| TIMDR `flow_sigma` | — | r = 0.019 |

**Out-of-sample** (współczynnik korekty α dobrany na 1. połowie danych,
testowany na 2. połowie): najlepsze dopasowane α = 0.00 — czyli optymalna
odpowiedź to "nie używaj korekty flow_sigma w ogóle". MAE persystencji na
danych out-of-sample: 0.000711, z korektą flow_sigma: identyczne 0.000711.
**Poprawa: +0,0%.**

**Wniosek:** klastrowanie zmienności (`persystencja: r=0.38`) to prawdziwe,
dobrze znane w literaturze zjawisko rynkowe (spokojne okresy mają tendencję
zostawać spokojne, burzliwe — burzliwe) i ten test je potwierdza na realnych
danych. Ale to **nie jest zasługa TIMDR** — to najprostszy możliwy baseline
(średnia z ostatnich 24h). Sam TIMDR `flow_sigma` (trend tej zmienności) nie
wnosi nic ponad tę prostą persystencję — korelacja praktycznie zerowa
(r=0.019), zero poprawy out-of-sample.

---

## Test 2: prognoza kierunku (kolejne 6h)

**Metoda:** ten sam walk-forward, 182 punktów. Sprawdzane: czy znak
`flow()` liczonego na cenie (`flow_price`) przewiduje znak zwrotu w
kolejnych 6h — testowane w obu kierunkach (kontynuacja trendu / mean-reversion).

| Strategia | Trafność |
|---|---:|
| FLOW → kontynuacja trendu | 0.473 |
| FLOW → odwrócenie (mean-reversion) | 0.527 |
| Baseline: zawsze "w górę" (bazowy odsetek wzrostów w próbie) | 0.544 |
| Rzut monetą | 0.500 |

**Wniosek:** żadna z dwóch wersji strategii FLOW nie bije nawet najprostszego
możliwego baseline'u ("zawsze obstawiaj kierunek, który w tej 30-dniowej
próbce był częstszy"). To dokładnie to, czego uczy hipoteza rynku
efektywnego: kierunek ceny w tak krótkim horyzoncie (6h) na płynnym rynku
jak BTC/USD jest, na dostępnych tu danych, praktycznie nieprzewidywalny z
prostego sygnału trendu. Uczciwie: to jeden miesiąc danych jednego
instrumentu — nie dowód, że *żadna* strategia kierunkowa nigdy nie działa,
tylko że **ta konkretna, prosta wersja TIMDR FLOW — nie.**

---

## Test 3: kontrole (anomalie i rytm)

### 3a. `anomalies()` — kontrola pozytywna

Na 720 świecach 1h, próg |MAD-z| > 3.0: **38 anomalii wykrytych**, w tym
poprawnie największe realne ruchy w próbce (np. +1,83% w t=61h, z=10,30;
-1,55% w t=236h, z=-8,73).

![Anomalie na cenie BTC/USD](chart_btc_anomalies.png)

Działa zgodnie z oczekiwaniem — jako **narzędzie opisowe** (wykrywanie
nietypowych ruchów, które już się wydarzyły) `anomalies()` sprawdza się na
danych rynkowych tak samo jak na katalogu sejsmicznym. To nie jest test
predykcyjny — anomalia jest wykrywana *w momencie*, w którym już nastąpiła,
nie zanim się wydarzy.

### 3b. `rhythm()` na wolumenie godzinowym — jedyne miejsce, gdzie
spodziewaliśmy się realnego sygnału

W przeciwieństwie do kierunku ceny, dobowy cykl aktywności traderów to
**prawdziwy, znany mechanizm** (nie efekt arbitrażowany do zera — nikt nie
może "zarbitrażować" faktu, że więcej ludzi handluje w ciągu dnia niż w
nocy). To jedyna hipoteza w tym teście, która nie zakłada bicia rynku
efektywnego.

Przy standardowym progu decyzyjnym (power_thresh=0.4) `rhythm()` **nie
zgłasza** cyklu dobowego: `score=0.000`, brak wykrytych okresów. Ale
diagnostyka bez progu pokazuje, że to nie jest zupełny brak sygnału:

| lag (h) | autokorelacja (wartości ze znakiem) |
|---:|---:|
| 1 | **0.540** (najsilniejsza) |
| 7 | 0.079 |
| 24 | **0.200** (realna, ale słaba) |
| 36 | -0.110 |
| 47 | 0.132 |

**Wniosek:** przy lag=24h autokorelacja wolumenu jest realna (0.20), ale
**zdecydowanie zdominowana** przez znacznie silniejszą autokorelację przy
lag=1h (0.54) — wolumen w danej godzinie jest znacznie bardziej podobny do
wolumenu godzinę wcześniej (krótkoterminowe klastrowanie aktywności) niż do
wolumenu dokładnie 24h wcześniej (cykl dobowy). Prawdopodobne wyjaśnienie:
BTC handlowany jest 24/7 na całym świecie, więc pojedynczy, wyraźny cykl
regionalny (np. godziny sesji NYSE czy Azji) jest rozmyty przez nakładające
się strefy czasowe innych rynków — inaczej niż na rynkach z jedną
dominującą sesją giełdową. `rhythm()` **działa poprawnie** — nie
halucynuje okresowości tam, gdzie jej nie ma (test na szumie białym w
`test_timdr_core_finance.py` to potwierdza) — ale na tej 30-dniowej próbce
nie potwierdza użytecznego, dominującego cyklu dobowego w wolumenie BTC.

---

## Dodatek: czy JAKAKOLWIEK predykcja może się tu udać?

Testy 1–2 sprawdzały jedną konkretną, prostą wersję FLOW na jednym horyzoncie
(6h). To rodzi uczciwe pytanie: czy przy innym horyzoncie albo innym
mechanizmie coś by jednak zadziałało? Sprawdzone w `backtest_finance_extended.py`
— **z zabezpieczeniem przed data-snoopingiem**: wybór najlepszej kombinacji
zrobiony wyłącznie na 1. połowie danych (trening), ocena wyłącznie na 2.
połowie (out-of-sample), bez żadnego dalszego wyboru. To ważne, bo im więcej
kombinacji się przeszuka, tym większa szansa, że coś "wygra" czysto losowo —
jedyny uczciwy test to sprawdzenie tej samej, już wybranej kombinacji na
danych, których nie widziała.

**A. Siatka horyzont × strategia (momentum vs reversal), 6 horyzontów (1–24h):**

| Horyzont | Momentum (trening) | Reversal (trening) | Baseline (trening) |
|---:|---:|---:|---:|
| 1h | 0.489 | 0.511 | 0.511 |
| 2h | 0.504 | 0.496 | 0.519 |
| 3h | 0.477 | 0.523 | 0.508 |
| 6h | 0.466 | 0.534 | 0.564 |
| 12h | 0.462 | **0.538** | 0.591 |
| 24h | 0.504 | 0.496 | 0.655 |

Najlepsza na treningu: reversal, H=12h (0.538). Ta sama kombinacja, bez
żadnej dalszej optymalizacji, na danych testowych (2. połowa, 264
nakładających się punktów): **trafność 0.583 vs baseline 0.500** — czyli
przewaga formalnie przetrwała out-of-sample.

Uczciwe zastrzeżenie, ważniejsze niż sam wynik: to **jeden** split na
**jednym** miesiącu **jednego** instrumentu, a okna 12h nakładają się co 1h
— 264 "punkty" testowe to w praktyce dużo mniej niezależnych zdarzeń (jeśli
cena spadała przez kilka dni z rzędu, dziesiątki nakładających się okien
12h dzielą w gruncie rzeczy tę samą informację: "był spadek"). Najbardziej
prawdopodobne wyjaśnienie tego wyniku: w 2. połowie próbki BTC był w
trendzie spadkowym (baseline treningowy 0.591 "w górę" kontra baseline
testowy 0.500) — strategia reversal wygrywa niemal automatycznie, gdy trend
się odwraca między treningiem a testem, bez potrzeby żadnego realnego
sygnału predykcyjnego. **To nie jest potwierdzona przewaga — to ciekawy
trop, który wymagałby powtórzenia na innych, niezależnych okresach i
instrumentach, zanim dałoby się mu zaufać.**

**B. Mean-reversion po anomaliach** (kauzalnie wykryte, 21 zdarzeń w 552
świecach po burn-inie) — test konkretnej, znanej w mikrostrukturze rynku
hipotezy ("po nietypowo dużym ruchu cena częściowo go oddaje"), a nie
przeszukiwanie aż coś wyjdzie:

| Horyzont po anomalii | Śr. zwrot po anomalii w górę (n=9) | Śr. zwrot po anomalii w dół (n=12) | Bezwarunkowo |
|---:|---:|---:|---:|
| 1h | +0.00108 | -0.00134 | -0.00003 |
| 3h | **-0.00156** | **+0.00150** | -0.00010 |
| 6h | **-0.00068** | **+0.00098** | -0.00019 |

Przy 1h widać kontynuację ruchu, ale przy 3h i 6h znak się odwraca —
kierunek zgodny z hipotezą reversion (po skoku w górę średni przyszły zwrot
robi się ujemny, po skoku w dół — dodatni). To jakościowo ciekawe, ale przy
n=9–12 zdarzeń te średnie mają ogromny błąd standardowy (rzędu wielkości
samego efektu) — **nie da się tego odróżnić od szumu przy tak małej
próbce**. Żeby to potwierdzić, trzeba więcej danych (dłuższy okres, więcej
zdarzeń), nie więcej przeszukiwania.

**Odpowiedź na pytanie "czy predykcja może się tu udać":** najbliżej
sensownego sygnału predykcyjnego w tym teście są te dwa wątki (reversal na
dłuższym horyzoncie, mean-reversion po anomaliach) — ale żaden z nich nie
jest w tej chwili **potwierdzony**, tylko **wart dalszego sprawdzenia** na
większej, niezależnej próbce. Uczciwie: to jest różnica między "coś tu może
być" a "to działa" — i ten test dostarcza tylko tego pierwszego, słabego
sygnału.

---

## Podsumowanie: na ile przewidywanie jest możliwe?

| Sygnał | Realna przewaga nad prostym baseline'em? | Dowód z tego testu |
|---|---|---|
| Persystencja zmienności (bez TIMDR — sam baseline) | **Tak** — r=0.38 z realną przyszłą zmiennością | 182 punkty walk-forward |
| TIMDR `flow_sigma` (korekta trendu zmienności) | **Nie** — r=0.02, +0,0% poprawy out-of-sample | to samo |
| TIMDR `flow` na cenie → kierunek zwrotu (6h, prosta wersja) | **Nie** — gorzej niż baseline "zawsze w górę" | 182 punkty walk-forward |
| `anomalies()` jako narzędzie opisowe | **Tak** — poprawnie wskazuje realne duże ruchy | 38/720 świec, kontrola pozytywna |
| `rhythm()` na wolumenie (cykl dobowy) | **Częściowo** — realny (0.20), ale słaby i zdominowany przez lag=1h | diagnostyka autokorelacji |
| `flow` reversal, H=12h (siatka horyzontów) | **Niepewne** — przetrwało 1 split out-of-sample, ale najpewniej artefakt jednego trendu w próbce | Dodatek A, wymaga replikacji |
| Mean-reversion po anomaliach | **Niepewne** — kierunek zgodny z hipotezą przy 3-6h, ale n za małe | Dodatek B, wymaga większej próbki |

To jest dokładnie to, czego uczy hipoteza rynku efektywnego, i dokładnie to,
co zapowiedziałem przed rozpoczęciem tego testu: rynki, w przeciwieństwie do
trzęsień ziemi, są kształtowane przez aktywnych uczestników, którzy
eliminują łatwo wykrywalne wzorce. **Sygnały TIMDR-Finanse trzeba
domyślnie traktować jak szum, dopóki rygorystyczny backtest nie udowodni
inaczej** — i w tym teście, na tym miesiącu danych BTC/USD, żaden z
predykcyjnych komponentów (`flow_sigma` jako korekta zmienności, `flow`
jako predyktor kierunku) tego dowodu nie dostarczył. Jedyne, co
"zadziałało", to znany z literatury efekt (klastrowanie zmienności),
niezależny od TIMDR, oraz opisowe (nie predykcyjne) działanie
`anomalies()`.

## Metodologia i uczciwość danych

- Dane: `api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60`, pobrane na
  żywo w trakcie tej analizy (2026-08-17). Zweryfikowane wewnętrznie
  (równe odstępy czasowe, brak luk) — jedno z pól odpowiedzi API
  (deklarowana liczba świec) nie zgadzało się z rzeczywistą liczbą wierszy,
  więc oparto się na weryfikacji niezależnej (spójność timestampów), a nie
  na samej deklaracji API.
- Wszystkie prognozy w testach 1 i 2 liczone **kauzalnie** — w chwili D
  używane są wyłącznie dane sprzed D (włącznie z progami adaptacyjnymi
  MAD i parametrami wygładzania), ocena zawsze na świecach, które w
  chwili prognozy jeszcze nie istniały.
- Współczynnik korekty α w teście 1 dobrany metodą out-of-sample (1. połowa
  danych do dopasowania, 2. połowa do oceny) — nie in-sample.
- Kod: `timdr_core_finance.py`, `backtest_finance.py`, `make_charts.py`,
  `test_timdr_core_finance.py` (24 testy jednostkowe, wszystkie przechodzą)
  — w załączonym archiwum wraz z surowymi danymi.

## Ograniczenia tego testu

- **Jeden miesiąc, jeden instrument.** 720 świec 1h to 30 dni — mało w
  porównaniu do horyzontów, w których zjawiska rynkowe (reżimy zmienności,
  sezonowość) się ujawniają. Wynik "brak przewagi kierunkowej" jest zgodny
  z oczekiwaniem teoretycznym (rynek efektywny), ale nie jest dowodem
  ostatecznym — inny miesiąc, inny reżim rynkowy (np. silny trend
  jednokierunkowy zamiast zakresu) mógłby dać inny wynik przypadkowo.
- **Brak danych order booku / tickowych.** `delta_proxy` i `spread_proxy`
  są przybliżeniami z samych świec OHLCV — prawdziwy order-flow (agresywne
  kupno vs sprzedaż wewnątrz świecy) mógłby zachowywać się inaczej niż
  jego proxy.
- **`rhythm()` liczy opóźnienie w jednostkach świec, nie czasu** — dla
  świec o stałym kroku 1h (jak tutaj) to nie jest problem, ale dla danych o
  nierównych odstępach (np. tickowych) byłoby to takie samo ograniczenie,
  jak w `catalog_core.py`.
- Test 1 i 2 mają nakładające się okna (krok 3h, horyzont 6h) — punkty
  walk-forward nie są w pełni niezależne statystycznie; nie zmienia to
  kierunku wniosków (brak korelacji zostaje brakiem korelacji), ale
  formalny test istotności wymagałby korekty na autokorelację.

---

## Drugi ośrodek finansowy: złoto (PAXG/USD) — czy wyniki się powtarzają?

Jeden instrument i jeden miesiąc to za mało, żeby cokolwiek uogólniać —
więc cały pipeline (dane, testy 1–3, dodatek A/B) powtórzono na **innej
klasie aktywów**: złocie, jako `PAXG/USD` (PAX Gold — token na Krakenie
wsparty 1:1 fizycznym złotem, 1 token = 1 uncja trojańska, cena śledzi
spot LBMA/COMEX). Bezpośredni dostęp do prawdziwych danych futures/spot
złota (COMEX, LBMA) nie był dostępny przez narzędzia tej sesji (blokady
robots.txt na Yahoo Finance/stooq, klucze API wymagane przez pozostałe
darmowe serwisy) — PAXG to najbliższy praktycznie dostępny, realny proxy:
inny mechanizm cenowy niż BTC (kotwiczony do metalu, nie czysto
spekulacyjny), ale wciąż handlowany 24/7 na rynku krypto, więc test
cyklu dobowego ma to samo ograniczenie co dla BTC.

**Dane:** 720 świec 1h, Kraken, 2026-07-18 – 2026-08-17 (ten sam okres co
BTC), zakres ceny 3986–4427 USD. Zweryfikowane wewnętrznie: 720/720
świec, idealnie równe odstępy 3600s, zero luk w osi czasu. **Zastrzeżenie
uczciwości danych:** dla 54 z 720 świec (7,5%, jeden ok. 55-godzinny
fragment w połowie okresu) źródło zwróciło tylko cenę zamknięcia, nie
pełny zakres high/low — dla tych świec open=high=low=close jako
przybliżenie. To nie wpływa na zwroty, zmienność ani wykrywanie
kierunku/anomalii (liczone z close), ale sztucznie zeruje `spread_proxy`
dla tych 54 godzin.

### Wyniki

| Test | BTC/USD | PAXG/USD (złoto) |
|---|---|---|
| Persystencja zmienności (r) | 0.381 | **0.446** |
| TIMDR flow_sigma (r) | 0.019 | 0.016 |
| Poprawa flow_sigma out-of-sample | +0,0% | +0,0% |
| Kierunek FLOW, 6h (momentum / reversal) | 0.473 / 0.527 | 0.445 / 0.555 |
| Baseline kierunku (6h) | 0.544 | 0.604 |
| anomalies() wykryte (|z|>3, /720) | 38 | 61 |
| rhythm() na wolumenie, lag=24h | 0.200 (realny, słaby) | 0.149 (słabszy) |
| Najsilniejszy lag autokorelacji wolumenu | 1h (0.540) | 48h (0.234) |

**Persystencja zmienności działa jeszcze lepiej na złocie** (r=0.45 vs
0.38) — spójne z tym, że klastrowanie zmienności to zjawisko ogólnorynkowe,
nie specyficzne dla krypto. `flow_sigma` nadal nic nie dodaje. Kierunek
(6h) nadal nieprzewidywalny prostym FLOW, w żadną stronę. `rhythm()` na
złocie jest jeszcze słabszy niż na BTC — najsilniejsza autokorelacja
wolumenu wypada przy lag=48h, nie przy 24h ani 1h — czyli nawet ten
częściowy "ślad" cyklu dobowego widoczny na BTC się tu nie powtarza.

### Kluczowy wynik: replikacja Dodatku A (siatka horyzont × strategia)

To jest najważniejszy test tej sekcji. Na BTC reversal H=12h formalnie
przetrwał jeden out-of-sample split (0.583 vs baseline 0.500) — z
zastrzeżeniem w raporcie, że to najpewniej artefakt jednego trendu w
próbce, **wymagający replikacji, zanim dałoby się mu zaufać**. Dokładnie
ta sama metoda (wybór na 1. połowie, ocena na 2.) na złocie:

| Horyzont | Momentum (trening) | Reversal (trening) | Baseline (trening) |
|---:|---:|---:|---:|
| 1h | 0.492 | 0.508 | 0.519 |
| 6h | 0.504 | 0.496 | 0.568 |
| 12h | **0.523** | 0.477 | 0.587 |
| 24h | 0.496 | 0.504 | 0.621 |

Najlepsza na treningu: **momentum** H=12h (nie reversal jak na BTC — już
tu widać niestabilność między instrumentami). Out-of-sample (2. połowa,
264 punkty): **trafność 0.527 vs baseline 0.606 — przewaga NIE
przetrwała.** To dokładnie potwierdza wcześniejsze zastrzeżenie: sygnał,
który "zadziałał" na BTC, nie replikuje się na złocie — najbardziej
prawdopodobne wyjaśnienie to, że BTC-owy wynik był artefaktem jednego
konkretnego trendu w tamtej próbce (data snooping), a nie realną,
przenaszalną przewagą.

### Dodatek B na złocie: mean-reversion po anomaliach

61 anomalii wykryto kauzalnie (vs 38 na BTC — złoto miało więcej dużych
ruchów w tym okresie, głównie przez silny trend wzrostowy w 3. tygodniu).
Wyniki mniej jednoznaczne niż na BTC:

| Horyzont po anomalii | Śr. zwrot po anomalii w górę (n=35-36) | Śr. zwrot po anomalii w dół (n=25) | Bezwarunkowo |
|---:|---:|---:|---:|
| 1h | -0.00040 | +0.00014 | +0.00015 |
| 3h | +0.00027 | +0.00016 | +0.00043 |
| 6h | +0.00088 | +0.00214 | +0.00086 |

Na złocie nie widać tego samego wzorca reversion co na BTC przy 3-6h —
po skoku w górę zwrot jest dodatni (kontynuacja, nie reversja), a po
skoku w dół też dodatni i silniejszy niż bezwarunkowo (co pasuje bardziej
do "odbicia po spadku" niż klasycznej symetrycznej mean-reversion). Przy
tak małych próbkach (n=25-36) to zbyt słabe, żeby cokolwiek z tego
wnioskować — ale wynik na pewno **nie potwierdza jednoznacznie** wzorca
znalezionego na BTC.

### Wniosek z replikacji

To jest dokładnie taki wynik, jakiego uczy metodologia: pojedynczy,
"ciekawy" sygnał znaleziony na jednym instrumencie (reversal H=12h na
BTC) **nie przetrwał testu na drugim, niezależnym instrumencie** — co jest
mocnym argumentem za tym, że był szumem/artefaktem, a nie realną
przewagą. Jedyne, co powtarza się konsekwentnie na obu rynkach: (1)
persystencja zmienności jako realny, użyteczny (ale nie-TIMDR-owy)
sygnał, (2) brak jakiejkolwiek przewagi kierunkowej z prostego FLOW, (3)
`anomalies()` poprawnie opisuje duże ruchy po fakcie, (4) `rhythm()` nie
znajduje wiarygodnego, silnego cyklu dobowego w żadnym z dwóch aktywów
24/7. To jest solidniejsza, bardziej wiarygodna podstawa do wniosków niż
wynik z jednego instrumentu.

Kod: `backtest_gold.py`, `backtest_gold_extended.py`, `make_charts_gold.py`
— identyczna logika co dla BTC, inne dane wejściowe
(`data/paxgusd_1h.csv`).
