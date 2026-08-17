@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================================
echo TIMDR-Finanse -- pelny przebieg: testy + backtesty (BTC+zloto) + wykresy
echo ============================================================

where python >nul 2>nul
if errorlevel 1 (
    echo [BLAD] Nie znaleziono "python" w PATH. Zainstaluj Python 3.10+ z python.org
    echo        i zaznacz "Add python.exe to PATH" podczas instalacji.
    pause
    exit /b 1
)

echo.
echo [1/8] Tworze srodowisko wirtualne (.venv), jesli nie istnieje...
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo.
echo [2/8] Instaluje zaleznosci (numpy, matplotlib, scipy, pytest)...
python -m pip install --upgrade pip >nul
python -m pip install numpy matplotlib scipy pytest -q

echo.
echo [3/8] Uruchamiam testy jednostkowe...
python -m pytest test_timdr_core_finance.py -q
if errorlevel 1 (
    echo [UWAGA] Niektore testy nie przeszly -- wyniki ponizej moga byc niepewne.
)

echo.
echo [4/8] Backtest BTC/USD (backtest_finance.py)...
python backtest_finance.py > backtest_output.txt
type backtest_output.txt

echo.
echo [5/8] Dodatkowy test predykcji na BTC (backtest_finance_extended.py)...
python backtest_finance_extended.py > backtest_extended_output.txt
type backtest_extended_output.txt

echo.
echo [6/8] Backtest zlota / PAXG-USD (backtest_gold.py) -- replikacja na innym rynku...
python backtest_gold.py > backtest_gold_output.txt
type backtest_gold_output.txt

echo.
echo [7/8] Dodatkowy test predykcji na zlocie (backtest_gold_extended.py)...
python backtest_gold_extended.py > backtest_gold_extended_output.txt
type backtest_gold_extended_output.txt

echo.
echo [8/8] Generuje wykresy (oba instrumenty + kontekst ropy + studium przypadku) i dashboard.html...
python make_charts.py
python make_charts_gold.py
python make_chart_oil.py
python analyze_spiral_case_study.py > spiral_case_study_output.txt
type spiral_case_study_output.txt
python build_dashboard.py

echo.
echo ============================================================
echo Gotowe. Otwieram dashboard.html w przegladarce...
echo ============================================================
start "" "dashboard.html"

pause
