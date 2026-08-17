@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================================
echo TIMDR-Finanse -- pelny przebieg: testy + backtest + wykresy
echo ============================================================

where python >nul 2>nul
if errorlevel 1 (
    echo [BLAD] Nie znaleziono "python" w PATH. Zainstaluj Python 3.10+ z python.org
    echo        i zaznacz "Add python.exe to PATH" podczas instalacji.
    pause
    exit /b 1
)

echo.
echo [1/5] Tworze srodowisko wirtualne (.venv), jesli nie istnieje...
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo.
echo [2/5] Instaluje zaleznosci (numpy, matplotlib, scipy, pytest)...
python -m pip install --upgrade pip >nul
python -m pip install numpy matplotlib scipy pytest -q

echo.
echo [3/5] Uruchamiam testy jednostkowe...
python -m pytest test_timdr_core_finance.py -q
if errorlevel 1 (
    echo [UWAGA] Niektore testy nie przeszly -- wyniki ponizej moga byc niepewne.
)

echo.
echo [4/5] Uruchamiam kauzalny walk-forward backtest (backtest_finance.py)...
python backtest_finance.py > backtest_output.txt
type backtest_output.txt

echo.
echo [5/5] Generuje wykresy i dashboard.html...
python make_charts.py
python build_dashboard.py

echo.
echo ============================================================
echo Gotowe. Otwieram dashboard.html w przegladarce...
echo ============================================================
start "" "dashboard.html"

pause
