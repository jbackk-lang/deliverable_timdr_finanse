"""
make_chart_oil.py — kontekst makro: miesieczna cena ropy WTI (EIA), zeby
sprawdzic hipoteze "moze to ropa ksztaltuje uklad". UWAGA: to sa dane
MIESIECZNE (dzienne/godzinowe nie byly technicznie osiagalne w tej sesji -
patrz RAPORT), wiec to jest kontekst/tlo makro, NIE rygorystyczny test
kauzalny jak reszta projektu.
"""
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({
    'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': '#888888', 'axes.labelcolor': '#333333',
    'xtick.color': '#555555', 'ytick.color': '#555555',
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
})

COL_REAL = '#1a1a1a'
COL_SPIKE = '#c2410c'
COL_WINDOW = '#2b6cb0'

rows = list(csv.DictReader(open('data/wti_monthly.csv')))
months = [r['month'] for r in rows]
prices = np.array([float(r['price_usd_bbl']) for r in rows])
x = np.arange(len(months))

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(x, prices, color=COL_REAL, lw=1.6, marker='o', ms=3.5, zorder=2)

# podkresl skok wiosna 2026
spike_i0, spike_i1 = months.index('2026-02'), months.index('2026-05')
ax.axvspan(spike_i0, spike_i1, color=COL_SPIKE, alpha=0.12, zorder=1,
           label='Skok +58% (lut→maj 2026)')

# zaznacz okno testu BTC/zloto (2026-07-18 .. 2026-08-17 -> miesiace 07/08)
win_i = months.index('2026-07')
ax.axvspan(win_i - 0.5, win_i + 0.5, color=COL_WINDOW, alpha=0.15, zorder=1,
           label='Miesiąc testu BTC/złoto (lipiec 2026)')

tick_idx = list(range(0, len(months), 3))
ax.set_xticks(tick_idx)
ax.set_xticklabels([months[i] for i in tick_idx], rotation=45, ha='right', fontsize=8.5)
ax.set_ylabel('WTI, USD/baryłka (EIA, miesięczna średnia)')
ax.set_title('Ropa WTI, sierpień 2023 – lipiec 2026 — kontekst makro (dane miesięczne, nie godzinowe)', fontsize=11.5)
ax.legend(fontsize=8.5, loc='upper left')
fig.tight_layout()
fig.savefig('chart_oil_context.png', dpi=150)
print('saved chart_oil_context.png')
