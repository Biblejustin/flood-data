"""
Flood "signs" plot suite, mirroring the earthquake reference framework.
Inputs:  merged_floods_long.csv (built by the merge step)
Outputs: plots/01_*.png … plots/08_*.png
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator

# --------------------------------------------------------------------------
# CATALOG-COMPLETENESS REGIME CONSTANTS — single source of truth
# --------------------------------------------------------------------------
DFO_START          = pd.Timestamp('1985-01-01')   # DFO catalog begins
DFO_END_COMPLETE   = pd.Timestamp('2023-12-31')   # last fully-populated year in v0.9.0
EMDAT_MODERN       = pd.Timestamp('1988-01-01')   # CRED's documented methodology upgrade
EMDAT_CONSISTENT   = pd.Timestamp('2000-01-01')   # post-2000 reporting density
TODAY              = pd.Timestamp.today().normalize()

# "Great flood" thresholds (composite — used wherever earthquakes used M≥7)
DFO_SEV_GREAT      = 2.0                          # DFO Severity 2.0 = "Extreme"
EMDAT_DEATHS_GREAT = 1000                         # EM-DAT deaths threshold

# Composite great-flood counts become unreliable once either catalog is truncated
# or EM-DAT death tolls haven't stabilized. DFO v0.9.0 stops 2024-02 and EM-DAT
# death tallies typically finalize ~12-24 months after an event.
COMPOSITE_STABLE_END = pd.Timestamp('2023-12-31')

# Styling
COL_DFO     = '#1f77b4'    # blue
COL_EMDAT   = '#d62728'    # red
COL_GREAT   = '#2ca02c'    # green
COL_TREND   = '#444444'
COL_PARTIAL = '#999999'

plt.rcParams.update({
    'figure.dpi': 110,
    'savefig.dpi': 160,
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.titleweight': 'bold',
    'axes.grid': True,
    'grid.alpha': 0.25,
    'axes.spines.top': False,
    'axes.spines.right': False,
})

OUT = Path(__file__).parent / 'plots'
OUT.mkdir(exist_ok=True)

# --------------------------------------------------------------------------
# LOAD + SPLIT
# --------------------------------------------------------------------------
df = pd.read_csv(Path(__file__).parent / 'merged_floods_long.csv',
                 parse_dates=['start_date', 'end_date'])
df['year']  = df['start_date'].dt.year
df['month'] = df['start_date'].dt.month
df = df.dropna(subset=['start_date'])

dfo = df[df['source'] == 'DFO'].copy()
emd = df[df['source'] == 'EM-DAT'].copy()

# Composite "great flood" — deduped by match_group_id where available
def composite_great_floods(df):
    dfo_great = df[(df['source']=='DFO')   & (df['severity']  >= DFO_SEV_GREAT)]
    emd_great = df[(df['source']=='EM-DAT')& (df['deaths']    >= EMDAT_DEATHS_GREAT)]
    g = pd.concat([dfo_great, emd_great])
    # Dedupe: when a group has both sources, prefer EM-DAT (richer deaths data, longer span)
    g_with_grp = g.dropna(subset=['match_group_id']).copy()
    g_with_grp['_prio'] = (g_with_grp['source'] == 'EM-DAT').astype(int)
    g_with_grp = g_with_grp.sort_values('_prio', ascending=False).drop_duplicates('match_group_id')
    g_no_grp  = g[g['match_group_id'].isna()]
    out = pd.concat([g_with_grp.drop(columns='_prio'), g_no_grp]).sort_values('start_date')
    return out.reset_index(drop=True)

great = composite_great_floods(df)
print(f'Composite great floods: {len(great):,} ({great["year"].min()}–{great["year"].max()})')

# Helpers ------------------------------------------------------------------
def annualize(count, days_elapsed):
    return count * 365.25 / max(days_elapsed, 1)

def fit_line(years, vals):
    """Returns (slope_per_year, intercept, predicted) for plotting; ignores NaN."""
    mask = np.isfinite(years) & np.isfinite(vals)
    if mask.sum() < 3:
        return None
    s, i = np.polyfit(years[mask], vals[mask], 1)
    return s, i, s * years + i

def save(fig, name):
    p = OUT / name
    fig.tight_layout()
    fig.savefig(p, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'  wrote {p.name}')

# ==========================================================================
# PLOT 01 — Intensity vs. time scatter (2-panel: DFO severity + EM-DAT deaths)
# ==========================================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True)

# DFO severity panel
d = dfo.dropna(subset=['severity'])
ax1.scatter(d['start_date'], d['severity'], s=8, alpha=0.35, color=COL_DFO, label='DFO event')
great_dfo = d[d['severity'] >= DFO_SEV_GREAT]
ax1.scatter(great_dfo['start_date'], great_dfo['severity'], s=28, color=COL_GREAT,
            edgecolor='black', linewidth=0.4, label=f'Severity ≥ {DFO_SEV_GREAT} ("Extreme")', zorder=3)
ax1.axvline(DFO_START, ls='--', color='black', lw=0.8, alpha=0.6)
ax1.text(DFO_START, 2.05, ' DFO catalog start (1985)', fontsize=8, va='top', alpha=0.7)
ax1.set_ylabel('DFO Severity\n(1.0 Large · 1.5 V.Large · 2.0 Extreme)')
ax1.set_title('Plot 01 — Intensity vs. time (composite)')
ax1.set_yticks([1.0, 1.5, 2.0])
ax1.legend(loc='upper left', fontsize=8)

# EM-DAT deaths panel (log y)
e = emd.dropna(subset=['deaths'])
e = e[e['deaths'] > 0]
ax2.scatter(e['start_date'], e['deaths'], s=8, alpha=0.35, color=COL_EMDAT, label='EM-DAT event')
great_emd = e[e['deaths'] >= EMDAT_DEATHS_GREAT]
ax2.scatter(great_emd['start_date'], great_emd['deaths'], s=28, color=COL_GREAT,
            edgecolor='black', linewidth=0.4, label=f'Deaths ≥ {EMDAT_DEATHS_GREAT:,}', zorder=3)
ax2.axhline(EMDAT_DEATHS_GREAT, ls=':', color='gray', lw=0.7)
ax2.axvline(EMDAT_MODERN,     ls='--', color='black', lw=0.8, alpha=0.6)
ax2.axvline(EMDAT_CONSISTENT, ls='--', color='black', lw=0.6, alpha=0.4)
ax2.text(EMDAT_MODERN, 1e6, ' EM-DAT methodology upgrade (1988)', fontsize=8, va='top', alpha=0.7)
ax2.set_yscale('log')
ax2.set_ylabel('EM-DAT Total Deaths (log)')
ax2.set_xlabel('Year')
ax2.legend(loc='upper left', fontsize=8)
save(fig, '01_intensity_vs_time.png')

# ==========================================================================
# PLOT 02 — Yearly counts by intensity band, stacked (2-panel)
# ==========================================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True)

# DFO panel: bands 1.0, 1.5, 2.0
def stack_dfo(d):
    bands = [1.0, 1.5, 2.0]
    g = d.dropna(subset=['severity']).groupby([d['year'], 'severity']).size().unstack(fill_value=0)
    return g.reindex(columns=bands, fill_value=0)

stk = stack_dfo(dfo)
years = stk.index.values
bottom = np.zeros(len(years))
colors_dfo = ['#cfe2f3', '#6ba6d4', COL_DFO]
labels_dfo = ['Severity 1.0 (Large)', 'Severity 1.5 (Very Large)', 'Severity 2.0 (Extreme)']
for b, c, lab in zip([1.0, 1.5, 2.0], colors_dfo, labels_dfo):
    vals = stk[b].values
    ax1.bar(years, vals, bottom=bottom, color=c, label=lab, width=0.85)
    bottom += vals

# Hatched partial-year overlay for current incomplete year (2024 in DFO)
last_full = DFO_END_COMPLETE.year
partial_mask = years > last_full
if partial_mask.any():
    py = years[partial_mask]; pv = bottom[partial_mask]
    days_in_year = (pd.Timestamp(f'{int(py[0])}-12-31') - pd.Timestamp(f'{int(py[0])}-01-01')).days + 1
    days_so_far = (dfo['start_date'].max() - pd.Timestamp(f'{int(py[0])}-01-01')).days + 1
    proj = pv * days_in_year / max(days_so_far, 1)
    ax1.bar(py, proj - pv, bottom=pv, color='none', edgecolor=COL_PARTIAL,
            hatch='///', label=f'Annualized projection ({int(py[0])} partial)', width=0.85)

# Linear trend on full DFO stable era
total_per_year = stk.sum(axis=1)
fit_years = total_per_year.index.values
fit_mask = (fit_years >= DFO_START.year) & (fit_years <= DFO_END_COMPLETE.year)
fit = fit_line(fit_years[fit_mask].astype(float), total_per_year.values[fit_mask].astype(float))
if fit:
    s, i, _ = fit
    fy = fit_years[fit_mask]
    ax1.plot(fy, s*fy + i, color=COL_TREND, lw=2, ls='-',
             label=f'Linear trend 1985–{last_full}: {s:+.2f}/yr')
ax1.set_title('Plot 02 — Yearly flood counts by intensity band')
ax1.set_ylabel('DFO events per year')
ax1.legend(loc='upper left', fontsize=8, ncol=2)

# EM-DAT panel: deaths bands [0–10, 10–100, 100–1000, ≥1000]
def stack_emd(d):
    d2 = d.dropna(subset=['deaths']).copy()
    bins   = [-0.01, 10, 100, 1000, np.inf]
    labels = ['<10 deaths', '10–99', '100–999', '≥1,000']
    d2['band'] = pd.cut(d2['deaths'], bins=bins, labels=labels)
    return d2.groupby(['year', 'band'], observed=True).size().unstack(fill_value=0).reindex(columns=labels, fill_value=0)

stke = stack_emd(emd)
ye = stke.index.values
bottom = np.zeros(len(ye))
colors_emd = ['#fde0dc', '#f5a89e', '#d65f4d', COL_EMDAT]
for col, c in zip(stke.columns, colors_emd):
    vals = stke[col].values
    ax2.bar(ye, vals, bottom=bottom, color=c, label=str(col), width=0.85)
    bottom += vals

# Hatched partial-year overlay for current year (2026)
cur_year = TODAY.year
partial_mask_e = ye == cur_year
if partial_mask_e.any():
    pv = bottom[partial_mask_e]
    days_in_year = 366 if (cur_year % 4 == 0 and cur_year % 100 != 0) or cur_year % 400 == 0 else 365
    days_so_far = (TODAY - pd.Timestamp(f'{cur_year}-01-01')).days + 1
    proj = pv * days_in_year / days_so_far
    ax2.bar(ye[partial_mask_e], proj - pv, bottom=pv, color='none', edgecolor=COL_PARTIAL,
            hatch='///', label=f'Annualized projection ({cur_year} partial)', width=0.85)

# Linear trends — separate fits for "long" (1900+) and "modern" (1988+)
total_e = stke.sum(axis=1)
ye2 = total_e.index.values.astype(float)
for label, start, color in [('Trend 1900–today (full)', 1900, '#888'),
                            (f'Trend {EMDAT_MODERN.year}–{cur_year-1} (modern)', EMDAT_MODERN.year, COL_TREND)]:
    mask = (ye2 >= start) & (ye2 < cur_year)
    fit = fit_line(ye2[mask], total_e.values[mask].astype(float))
    if fit:
        s, i, _ = fit
        ax2.plot(ye2[mask], s*ye2[mask] + i, color=color, lw=2,
                 label=f'{label}: {s:+.2f}/yr')

ax2.set_ylabel('EM-DAT flood events per year')
ax2.set_xlabel('Year')
ax2.legend(loc='upper left', fontsize=8, ncol=2)
save(fig, '02_yearly_by_band.png')

# ==========================================================================
# PLOT 03 — Great-flood yearly counts with dual trend lines + 10-yr rolling + mean
# ==========================================================================
fig, ax = plt.subplots(figsize=(13, 5.5))
gy = great.groupby('year').size()
# Reindex over full range so empty years show as 0
full_yr = np.arange(int(great['year'].min()), cur_year + 1)
gy = gy.reindex(full_yr, fill_value=0)

# Color bars: fully stable (green), data-edge undercount zone (gray, hatched)
stable_end_yr = COMPOSITE_STABLE_END.year
colors = [COL_PARTIAL if y > stable_end_yr else COL_GREAT for y in gy.index]
hatches = ['///' if y > stable_end_yr else '' for y in gy.index]
for x, v, c, h in zip(gy.index, gy.values, colors, hatches):
    ax.bar(x, v, color=c, width=0.85, alpha=0.85, hatch=h, edgecolor='black' if h else 'none', linewidth=0.4)
ax.axvspan(stable_end_yr + 0.5, gy.index.max() + 0.5, color=COL_PARTIAL, alpha=0.10, zorder=0)
ax.text(stable_end_yr + 0.6, gy.values.max() * 0.95,
        f' Data-edge zone: DFO ends 2024-02; EM-DAT\n deaths still finalizing — likely undercount',
        fontsize=8, va='top', alpha=0.75, style='italic')

# 10-yr rolling mean (excluding data-edge zone)
gy_stable = gy.loc[gy.index <= stable_end_yr]
roll = gy_stable.rolling(10, center=True, min_periods=5).mean()
ax.plot(roll.index, roll.values, color='black', lw=2, label='10-yr rolling mean (stable era)')

# Long-span trend (1900 → stable_end_yr)
fy = gy.index.values.astype(float)
mask_long = (fy >= 1900) & (fy <= stable_end_yr)
f1 = fit_line(fy[mask_long], gy.values[mask_long].astype(float))
if f1:
    s, i, _ = f1
    ax.plot(fy[mask_long], s*fy[mask_long]+i, color='#888', lw=1.8, ls='--',
            label=f'Long-span trend 1900–{stable_end_yr}: {s:+.3f}/yr')

# Modern-era trend (1988 → stable_end_yr)
mask_mod = (fy >= EMDAT_MODERN.year) & (fy <= stable_end_yr)
f2 = fit_line(fy[mask_mod], gy.values[mask_mod].astype(float))
if f2:
    s, i, _ = f2
    ax.plot(fy[mask_mod], s*fy[mask_mod]+i, color=COL_TREND, lw=2,
            label=f'Modern trend {EMDAT_MODERN.year}–{stable_end_yr}: {s:+.3f}/yr')

# Long-run mean (stable era only)
mean_long = gy.loc[(gy.index >= 1900) & (gy.index <= stable_end_yr)].mean()
ax.axhline(mean_long, color='#cc6699', ls=':', lw=1.2,
           label=f'Long-run mean (1900–{stable_end_yr}): {mean_long:.1f}/yr')

ax.set_title('Plot 03 — "Great flood" yearly counts (Severity ≥ 2.0 OR deaths ≥ 1,000)')
ax.set_xlabel('Year'); ax.set_ylabel('Great floods per year')
ax.legend(loc='upper left', fontsize=8, ncol=2)
ax.xaxis.set_major_locator(MaxNLocator(15))
save(fig, '03_great_floods_yearly.png')

# ==========================================================================
# PLOT 04 — Great-flood trailing-12-month sliding window with ±1σ band
# ==========================================================================
fig, ax = plt.subplots(figsize=(13, 5.5))

# Daily timeline: 1 per event on its start_date, then trailing-365-day sum
daily = great.groupby(great['start_date'].dt.normalize()).size()
all_days = pd.date_range(great['start_date'].min().normalize(), TODAY, freq='D')
daily = daily.reindex(all_days, fill_value=0)
trail = daily.rolling('365D').sum()

# Only show post-1900 for cleanness
trail = trail[trail.index >= pd.Timestamp('1900-01-01')]

# Split into stable era and data-edge zone
stable_mask = trail.index <= COMPOSITE_STABLE_END
ax.plot(trail.index[stable_mask], trail.values[stable_mask], color=COL_GREAT, lw=1.1,
        label='Trailing-12mo count (stable era)')
ax.plot(trail.index[~stable_mask], trail.values[~stable_mask], color=COL_PARTIAL, lw=1.1, ls='-',
        label='Trailing-12mo count (data-edge — undercount)')
# Data-edge shading
ax.axvspan(COMPOSITE_STABLE_END, TODAY, color=COL_PARTIAL, alpha=0.12, zorder=0)
ax.text(COMPOSITE_STABLE_END, trail.values.max()*0.95,
        ' Data-edge zone\n DFO ends 2024-02;\n EM-DAT death tolls\n still finalizing',
        fontsize=8, va='top', ha='left', alpha=0.75, style='italic')

# ±1σ band — stable era only
stable_window = trail[(trail.index >= EMDAT_MODERN) & (trail.index <= COMPOSITE_STABLE_END)]
mu  = stable_window.mean()
sig = stable_window.std()
ax.axhline(mu,        color=COL_TREND, ls='-',  lw=1.1, label=f'Stable-era mean ({EMDAT_MODERN.year}–{COMPOSITE_STABLE_END.year}): {mu:.1f}')
ax.axhline(mu + sig,  color=COL_TREND, ls=':',  lw=0.9, label=f'±1σ ({sig:.1f})')
ax.axhline(mu - sig,  color=COL_TREND, ls=':',  lw=0.9)
ax.fill_between(trail.index, mu - sig, mu + sig, color=COL_TREND, alpha=0.06)

# Mark last-stable point AND today (separately, so reader sees both)
last_stable = trail.loc[:COMPOSITE_STABLE_END].iloc[-1]
last_stable_z = (last_stable - mu) / sig if sig > 0 else 0
ax.scatter([COMPOSITE_STABLE_END], [last_stable], s=70, color='black', zorder=5,
           label=f'Last fully-stable point ({COMPOSITE_STABLE_END.date()}): {last_stable:.0f} (z={last_stable_z:+.2f})')
cur_val = trail.iloc[-1]
ax.scatter([trail.index[-1]], [cur_val], s=70, color='gray', marker='s', zorder=5,
           label=f'Today (raw, undercount): {cur_val:.0f}')

ax.set_title('Plot 04 — "Great flood" trailing-12-month rolling count')
ax.set_xlabel('Date'); ax.set_ylabel('Great floods in trailing 365 days')
ax.legend(loc='upper left', fontsize=8)
save(fig, '04_trailing_12mo.png')

# ==========================================================================
# PLOT 05 — Decadal intensity (2-panel: peak T12mo + cumulative deaths)
# ==========================================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8))

# Panel 1: peak trailing-12mo per decade
trail_full = daily.rolling('365D').sum()
trail_full = trail_full[trail_full.index >= pd.Timestamp('1900-01-01')]
df_trail = trail_full.to_frame('t12')
df_trail['decade'] = (df_trail.index.year // 10) * 10
peak = df_trail.groupby('decade')['t12'].max()
mean_t = df_trail.groupby('decade')['t12'].mean()
# Mark partial decade
cur_decade = (cur_year // 10) * 10
colors = [COL_PARTIAL if d == cur_decade else COL_GREAT for d in peak.index]
ax1.bar(peak.index, peak.values, width=8, color=colors, alpha=0.85, label='Peak trailing-12mo')
ax1.plot(mean_t.index, mean_t.values, 'ko-', ms=6, lw=1.5, label='Mean trailing-12mo')
ax1.set_title('Plot 05a — Decadal peak intensity (great floods, trailing-12mo count)')
ax1.set_ylabel('Trailing-12mo count')
ax1.legend(loc='upper left', fontsize=8)
ax1.set_xticks(peak.index)
ax1.tick_params(axis='x', labelrotation=0)

# Panel 2: cumulative EM-DAT deaths per decade (impact-energy proxy)
emd_deaths = emd.dropna(subset=['deaths']).copy()
emd_deaths['decade'] = (emd_deaths['year'] // 10) * 10
dec_deaths = emd_deaths.groupby('decade')['deaths'].sum()
colors2 = [COL_PARTIAL if d == cur_decade else COL_EMDAT for d in dec_deaths.index]
ax2.bar(dec_deaths.index, dec_deaths.values, width=8, color=colors2, alpha=0.85)
ax2.set_yscale('log')
ax2.set_title('Plot 05b — Decadal cumulative flood deaths (EM-DAT, "impact energy")')
ax2.set_ylabel('Total deaths per decade (log)')
ax2.set_xlabel('Decade')
ax2.set_xticks(dec_deaths.index)
# annotate values
for x, v in zip(dec_deaths.index, dec_deaths.values):
    if v > 0:
        ax2.text(x, v*1.25, f'{int(v):,}', ha='center', fontsize=7, alpha=0.8)
save(fig, '05_decadal_intensity.png')

# ==========================================================================
# PLOT 06 — Great-flood timing (2-panel: cumulative + inter-event intervals)
# ==========================================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8))

gsort = great.sort_values('start_date').reset_index(drop=True)
gsort['idx'] = np.arange(1, len(gsort) + 1)

# Cumulative count
ax1.step(gsort['start_date'], gsort['idx'], color=COL_GREAT, lw=1.6, where='post', label='Cumulative great floods')

# Constant-rate reference: from stable era only (1988 → COMPOSITE_STABLE_END)
mod = gsort[(gsort['start_date'] >= EMDAT_MODERN) & (gsort['start_date'] <= COMPOSITE_STABLE_END)]
if len(mod) > 1:
    yrs = (mod['start_date'].max() - mod['start_date'].min()).days / 365.25
    rate = (len(mod) - 1) / yrs
    ref_start = gsort['start_date'].min()
    ref_x = pd.date_range(ref_start, TODAY, freq='YE')
    ref_y_start = gsort.loc[gsort['start_date'] <= ref_start, 'idx'].max() or 1
    ref_y = ref_y_start + rate * ((ref_x - ref_start).days / 365.25)
    ax1.plot(ref_x, ref_y, color=COL_TREND, ls='--', lw=1.2,
             label=f'Constant-rate ref ({rate:.1f}/yr from {EMDAT_MODERN.year}–{COMPOSITE_STABLE_END.year})')

# Post-hoc regime shading — illustrative only
regimes = [
    ('1900-01-01', '1930-12-31', '#fff7d6', 'Pre-instrumental sparse'),
    ('1988-01-01', '2010-12-31', '#dfead8', 'EM-DAT modern era'),
    ('2010-01-01', COMPOSITE_STABLE_END.strftime('%Y-%m-%d'), '#fbe1cf', 'Satellite-era'),
]
for s, e, c, _ in regimes:
    ax1.axvspan(pd.Timestamp(s), pd.Timestamp(e), color=c, alpha=0.4, zorder=0)
# Data-edge zone in slate gray on top of everything
ax1.axvspan(COMPOSITE_STABLE_END, TODAY, color=COL_PARTIAL, alpha=0.30, zorder=0)
ax1.text(0.01, 0.98, 'Regime shading is post-hoc, illustrative only.\nGray = data-edge undercount zone.',
         transform=ax1.transAxes, fontsize=8, va='top', style='italic', alpha=0.75)
ax1.set_title('Plot 06a — Cumulative great floods vs. constant-rate reference')
ax1.set_ylabel('Cumulative count')
ax1.legend(loc='upper left', fontsize=8)

# Inter-event intervals (days between consecutive great floods)
gsort['interval_days'] = gsort['start_date'].diff().dt.days
ints = gsort.dropna(subset=['interval_days'])
ax2.scatter(ints['start_date'], ints['interval_days'], s=10, alpha=0.4, color=COL_GREAT)
roll_int = ints.set_index('start_date')['interval_days'].rolling('1825D').mean()  # 5-yr rolling
ax2.plot(roll_int.index, roll_int.values, color='black', lw=2, label='5-yr rolling mean interval')
ax2.axhline(ints['interval_days'].median(), color=COL_TREND, ls=':',
            label=f'Median interval: {ints["interval_days"].median():.0f} d')
ax2.axvspan(COMPOSITE_STABLE_END, TODAY, color=COL_PARTIAL, alpha=0.30, zorder=0)
ax2.set_title('Plot 06b — Inter-event intervals between great floods (days)')
ax2.set_xlabel('Date'); ax2.set_ylabel('Days since previous great flood')
ax2.set_yscale('log')
ax2.legend(loc='upper left', fontsize=8)
save(fig, '06_great_flood_timing.png')

# ==========================================================================
# PLOT 07 — Frequency distributions (2-panel)
# ==========================================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

# DFO severity histogram (discrete bins)
sev_counts = dfo['severity'].value_counts().sort_index()
ax1.bar(sev_counts.index.astype(str), sev_counts.values, color=COL_DFO, width=0.6)
for x, v in zip(sev_counts.index.astype(str), sev_counts.values):
    ax1.text(x, v + 30, f'{int(v):,}', ha='center', fontsize=9)
ax1.set_title('Plot 07a — DFO severity frequency')
ax1.set_xlabel('DFO Severity'); ax1.set_ylabel('Event count')

# EM-DAT deaths log-log frequency (the Gutenberg-Richter analog)
de = emd.dropna(subset=['deaths'])
de = de[de['deaths'] > 0]
bins = np.logspace(0, np.log10(de['deaths'].max()), 25)
counts, edges = np.histogram(de['deaths'], bins=bins)
mids = (edges[:-1] * edges[1:]) ** 0.5
nonzero = counts > 0
ax2.loglog(mids[nonzero], counts[nonzero], 'o', color=COL_EMDAT, ms=7, label='EM-DAT events')
# Cumulative complementary distribution (N events with deaths ≥ X)
sorted_d = np.sort(de['deaths'].values)
ccdf_x = sorted_d
ccdf_y = len(sorted_d) - np.arange(len(sorted_d))
ax2.loglog(ccdf_x, ccdf_y, color=COL_EMDAT, alpha=0.4, lw=1, label='N(≥ deaths) cumulative')
ax2.axvline(EMDAT_DEATHS_GREAT, color='black', ls=':', lw=0.8,
            label=f'Great-flood threshold ({EMDAT_DEATHS_GREAT:,})')
ax2.set_title('Plot 07b — EM-DAT deaths frequency distribution')
ax2.set_xlabel('Total deaths (log)'); ax2.set_ylabel('Event count (log)')
ax2.legend(loc='lower left', fontsize=8)
save(fig, '07_frequency_distributions.png')

# ==========================================================================
# PLOT 08 — Monthly seasonality (flood-specific, not in earthquake suite)
# ==========================================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

# All-time monthly climatology, both sources
dfo_m = dfo.groupby('month').size()
emd_m = emd.groupby('month').size()
months = np.arange(1, 13)
month_lbls = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

w = 0.38
ax1.bar(months - w/2, dfo_m.reindex(months, fill_value=0).values, width=w,
        color=COL_DFO, label=f'DFO ({len(dfo):,} events, 1985+)')
ax1.bar(months + w/2, emd_m.reindex(months, fill_value=0).values, width=w,
        color=COL_EMDAT, label=f'EM-DAT ({len(emd):,} events, 1900+)')
ax1.set_xticks(months); ax1.set_xticklabels(month_lbls)
ax1.set_title('Plot 08a — Monthly seasonality (all-time)')
ax1.set_ylabel('Total events by start-month')
ax1.legend(loc='upper left', fontsize=8)

# By hemisphere — N vs S using latitude where available (EM-DAT)
e_geo = emd.dropna(subset=['latitude']).copy()
e_geo['hemi'] = np.where(e_geo['latitude'] >= 0, 'Northern', 'Southern')
hemi_m = e_geo.groupby(['hemi', 'month']).size().unstack(fill_value=0).reindex(columns=months, fill_value=0)
ax2.plot(months, hemi_m.loc['Northern'].values, 'o-', color='#1f77b4',
         label=f'Northern Hemisphere (n={(e_geo["hemi"]=="Northern").sum():,})')
ax2.plot(months, hemi_m.loc['Southern'].values, 'o-', color='#d62728',
         label=f'Southern Hemisphere (n={(e_geo["hemi"]=="Southern").sum():,})')
ax2.set_xticks(months); ax2.set_xticklabels(month_lbls)
ax2.set_title('Plot 08b — Seasonality by hemisphere (EM-DAT events with lat/lon)')
ax2.set_ylabel('Events by start-month')
ax2.legend(loc='upper left', fontsize=8)
save(fig, '08_seasonality.png')

# ==========================================================================
# SUMMARY
# ==========================================================================
print('\nDone. PNGs in', OUT)
for p in sorted(OUT.glob('*.png')):
    print(f'  {p.name}  ({p.stat().st_size//1024} KB)')

# Headline numbers — report both the last-fully-stable value AND today's raw value
last_stable_t12 = trail.loc[:COMPOSITE_STABLE_END].iloc[-1]
last_stable_z   = (last_stable_t12 - mu) / sig if sig > 0 else 0
cur_t12         = trail.iloc[-1]
cur_z           = (cur_t12 - mu) / sig if sig > 0 else 0

print(f'\nStable-era reference window: {EMDAT_MODERN.year}–{COMPOSITE_STABLE_END.year}')
print(f'  Stable-era mean great-floods/yr: {mu:.1f}  (σ {sig:.1f})')
print(f'  Long-run mean ({EMDAT_MODERN.year}–{COMPOSITE_STABLE_END.year}): see Plot 03')
print(f'\nLast-stable trailing-12mo ({COMPOSITE_STABLE_END.date()}): {last_stable_t12:.0f}  '
      f'(z = {last_stable_z:+.2f})')
print(f'Today raw trailing-12mo ({TODAY.date()}): {cur_t12:.0f}  '
      f'(z = {cur_z:+.2f}) — UNDERCOUNT: DFO truncated, EM-DAT deaths still finalizing')
