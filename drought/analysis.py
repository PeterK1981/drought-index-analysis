"""Rasterprüfung, zeitliche Mittel und Klassifikation – ohne Plot-Zustand."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import convolve, generic_filter


DM_BREAKS = np.array([10., 20., 24., 28., 35., 55.])
DM_LABELS = ["arid", "semi-arid", "mediterran", "semi-humid", "humid",
             "sehr humid", "extrem humid"]


@dataclass
class Climate:
    precipitation: np.ndarray
    temperature: np.ndarray
    transform: object
    years: tuple

    @property
    def index(self):
        return de_martonne(self.precipitation, self.temperature)


def de_martonne(precipitation, temperature):
    p, t = np.broadcast_arrays(np.asarray(precipitation, float),
                               np.asarray(temperature, float))
    result = np.full(p.shape, np.nan)
    valid = np.isfinite(p) & np.isfinite(t) & (p >= 0) & (t > -10)
    np.divide(p, t + 10, out=result, where=valid)
    return result


def source_path(root, kind, year):
    root = Path(root)
    folder, legacy, remote = {
        "precipitation": ("Precipitation", f"RSMS_17_{year}_01.asc",
                          f"grids_germany_annual_precipitation_{year}17.asc"),
        "temperature": ("Temperature", f"TAMM_17_{year}_01.asc",
                        f"grids_germany_annual_air_temp_mean_{year}17.asc"),
    }[kind]
    candidates = [root / folder / remote, root / folder / legacy]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"Jahresraster fehlt: {candidates[0]}")


def read_grid(path):
    with rasterio.open(path) as src:
        if src.count != 1:
            raise ValueError(f"Genau ein Rasterband erwartet: {path.name}")
        if src.crs is not None and src.crs != rasterio.crs.CRS.from_epsg(31467):
            raise ValueError(f"EPSG:31467 erwartet: {path.name}")
        if src.transform.b or src.transform.d or src.transform.a <= 0 or src.transform.e >= 0:
            raise ValueError("Nur nordorientierte Raster werden unterstützt.")
        values = src.read(1, masked=True).astype(float).filled(np.nan)
        return values, src.transform


def load_climate(root, start, end):
    """Mittel ausschließlich dort, wo beide Größen in ALLEN Jahren vorliegen.

    ASCII-Dateien ohne CRS werden als dokumentiertes DWD-GK3-Raster gelesen.
    Form und Affintransformation müssen in allen Dateien exakt übereinstimmen.
    """
    if start > end:
        raise ValueError("Startjahr muss vor oder gleich Endjahr liegen.")
    p_sum = t_sum = valid_all = transform = None
    for year in range(start, end + 1):
        p, pt = read_grid(source_path(root, "precipitation", year))
        t, tt = read_grid(source_path(root, "temperature", year))
        if p.shape != t.shape or pt != tt:
            raise ValueError(f"Niederschlag und Temperatur sind {year} nicht deckungsgleich.")
        if transform is None:
            transform = pt
            p_sum, t_sum = np.zeros_like(p), np.zeros_like(t)
            valid_all = np.ones(p.shape, dtype=bool)
        if p.shape != p_sum.shape or pt != transform:
            raise ValueError(f"Rastergeometrie weicht im Jahr {year} ab.")
        t /= 10
        valid = np.isfinite(p) & np.isfinite(t) & (p >= 0)
        valid_all &= valid
        p_sum += np.where(valid, p, 0)
        t_sum += np.where(valid, t, 0)
    if not valid_all.any():
        raise ValueError("Keine Zelle hat vollständige Daten für diesen Zeitraum.")
    n = end - start + 1
    return Climate(np.where(valid_all, p_sum / n, np.nan),
                   np.where(valid_all, t_sum / n, np.nan), transform, (start, end))


def classify(index):
    index = np.asarray(index)
    return np.where(np.isfinite(index), np.searchsorted(DM_BREAKS, index, side="right"), -1)


def smooth_classes(classes, size=5, method="majority"):
    """Glättung nur zur Darstellung. NoData bleibt unverändert.

    Mehrheits-Gleichstände gehen an die niedrigere Klasse. Median verwendet
    bei gerader Anzahl gültiger Nachbarn den unteren mittleren Klassenwert.
    """
    if size < 1 or size % 2 == 0:
        raise ValueError("Glättungsgröße muss eine positive ungerade Zahl sein.")
    if method not in ("majority", "median", "none"):
        raise ValueError("Unbekannte Glättungsmethode.")
    classes = np.asarray(classes, dtype=int)
    if method == "none" or size == 1:
        return classes.copy()
    if method == "majority":
        kernel = np.ones((size, size), dtype=np.int32)
        counts = np.stack([convolve((classes == i).astype(np.int32), kernel,
                                    mode="reflect") for i in range(7)])
        result = counts.argmax(axis=0)
    else:
        def lower_median(values):
            values = np.sort(values[values >= 0])
            return values[(len(values) - 1) // 2] if len(values) else -1
        result = generic_filter(classes, lower_median, size=size, mode="reflect")
    return np.where(classes < 0, -1, result)


def quantile_breaks(values):
    finite = np.asarray(values)[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("Keine gültigen Werte für Quartile.")
    return np.quantile(finite, [.25, .5, .75])


def bivariate(climate, p_breaks, t_breaks):
    """Gleiche Werte bleiben zusammen; bei Bindungen können Klassen leer sein."""
    p, t = climate.precipitation, climate.temperature
    valid = np.isfinite(p) & np.isfinite(t)
    return np.where(valid, np.searchsorted(t_breaks, t, side="left") * 4
                    + np.searchsorted(p_breaks, p, side="left"), -1)
