"""Peter Kellers dunkle Karten und ursprüngliche Farbpaletten."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, to_rgb
from matplotlib.patches import Patch
import numpy as np

from .analysis import DM_BREAKS, DM_LABELS, bivariate, classify, smooth_classes

BACKGROUND = "#122635"
DM_COLORS = ["#f4efe8", "#e9d9c3", "#e76f51", "#a7c957", "#6a994e", "#386641", "#1b4332"]


def bivariate_palette():
    bg, temp, prec, white = map(lambda c: np.array(to_rgb(c)),
                               ["#1B3648", "#C9782A", "#1FA7A1", "#D2CBC0"])
    colors = []
    for i in range(4):
        for j in range(4):
            wt, wp = i / 3, j / 3
            base = (1 - wt - wp) * bg + wt * temp + wp * prec
            colors.append(np.clip(wt * wp * white + (1 - wt * wp) * base, 0, 1))
    return ListedColormap(colors)


def draw(climate, destination, kind, p_breaks, t_breaks, reference_label,
         smoothing="majority", size=5, dpi=140):
    """Feste Bildgröße erlaubt identische Frames für die Animation."""
    rows, cols = climate.precipitation.shape
    tr = climate.transform
    extent = [tr.c, tr.c + cols * tr.a, tr.f + rows * tr.e, tr.f]
    x, y = tr.c + (np.arange(cols) + .5) * tr.a, tr.f + (np.arange(rows) + .5) * tr.e
    dm = smooth_classes(classify(climate.index), size, smoothing)
    fig = plt.figure(figsize=(8.8, 10.4), facecolor=BACKGROUND)
    ax = fig.add_axes([.17, .075, .81, .81], facecolor=BACKGROUND)
    ax.set_axis_off()
    is_dm = kind == "demartonne"
    cmap = ListedColormap(DM_COLORS) if is_dm else bivariate_palette()
    values = dm if is_dm else bivariate(climate, p_breaks, t_breaks)
    ax.imshow(np.ma.masked_less(values, 0), extent=extent, origin="upper",
              cmap=cmap, vmin=0, vmax=6 if is_dm else 15, interpolation="nearest")
    if kind != "bivariate":
        # Die Linien grenzen geglättete Klassen ab, keine interpolierten Isolinien.
        ax.contour(x, y, np.ma.masked_less(dm, 0), levels=np.arange(.5, 6, 1),
                   colors="#163126" if is_dm else ["#3a312b", "#2f2a26", "#43352c"],
                   linewidths=[.25, .5, .75, 1, 1.25, 1.5], alpha=.9)
    start, end = climate.years
    title = "De-Martonne-Index für Deutschland" if is_dm else "Bivariate Klimakarte für Deutschland"
    subtitle = f"{start}–{end} · Index aus den Periodenmitteln" if is_dm else f"{start}–{end} · mittlere Jahrestemperatur und Jahresniederschlag"
    fig.text(.5, .965, title, ha="center", color="white", fontsize=17)
    fig.text(.5, .938, subtitle, ha="center", color="white", fontsize=10)
    if is_dm:
        ranges = ["< 10", "10–<20", "20–<24", "24–<28", "28–<35", "35–<55", "≥ 55"]
        legend = fig.legend(handles=[Patch(color=c, label=f"{name}  ({r})")
                            for c, name, r in zip(DM_COLORS, DM_LABELS, ranges)],
                            title="dMI-Klassen", loc="lower left", bbox_to_anchor=(.015, .09),
                            facecolor=BACKGROUND, edgecolor="#e6ddd2", fontsize=8, title_fontsize=9)
        plt.setp(legend.get_texts(), color="white")
        legend.get_title().set_color("white")
    else:
        inset = fig.add_axes([.055, .70, .20, .17], facecolor=BACKGROUND)
        inset.imshow(np.arange(16).reshape(4, 4), cmap=cmap, origin="lower", vmin=0, vmax=15)
        inset.set_xticks(range(4), ["Q1", "Q2", "Q3", "Q4"])
        inset.set_yticks(range(4), ["Q1", "Q2", "Q3", "Q4"])
        inset.tick_params(colors="white", labelsize=7, length=0)
        inset.set_xlabel("Niederschlag →", color="white", fontsize=8)
        inset.set_ylabel("Temperatur →", color="white", fontsize=8)
        for spine in inset.spines.values():
            spine.set_color("#cfcfcf")
        ptext = " / ".join(f"{v:.0f}" for v in p_breaks)
        ttext = " / ".join(f"{v:.1f}" for v in t_breaks)
        fig.text(.025, .655, "Q1: niedrige · Q4: hohe Werte\n"
                 f"Quartilgrenzen {reference_label}:\nT: {ttext} °C\nP: {ptext} mm/Jahr",
                 color="white", fontsize=7, va="top", linespacing=1.5)
        if kind == "contours":
            fig.text(.025, .545, "Konturen: dMI-Klassengrenzen\n10 / 20 / 24 / 28 / 35 / 55",
                     color="white", fontsize=7, va="top", linespacing=1.5)
    smoothing_text = "unglättet" if smoothing == "none" or size == 1 else f"{size} × {size} Zellen, " + {"majority": "Mehrheitsfilter", "median": "Medianfilter"}[smoothing]
    fig.text(.025, .045, f"dMI = P / (T + 10) · Klassendarstellung: {smoothing_text}", color="white", fontsize=7)
    fig.text(.025, .022, "Abb.: Dr. Peter Keller · Daten: DWD Climate Data Center (CC BY 4.0) · eigene Berechnung und Darstellung",
             color="white", fontsize=6.5)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=dpi, facecolor=BACKGROUND)
    plt.close(fig)
