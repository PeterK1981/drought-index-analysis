"""Download, Karten, gleitende Zeitfenster und GIF über die Kommandozeile."""

import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .analysis import load_climate, quantile_breaks, source_path
from .download import download
from .plots import draw


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("download", "render"):
        cmd = sub.add_parser(command)
        cmd.add_argument("--data-dir", type=Path, default=Path("data"))
        cmd.add_argument("--start", type=int, default=1996)
        cmd.add_argument("--end", type=int, default=2025)
    render = sub.choices["render"]
    render.add_argument("--output-dir", type=Path, default=Path("outputs"))
    render.add_argument("--window", type=int, help="Gleitende Fenster in Jahren; sonst Gesamtzeitraum")
    render.add_argument("--quartiles", choices=["reference", "window"], default="reference",
                        help="Feste Grenzen des Gesamtzeitraums oder separate Grenzen je Fenster")
    render.add_argument("--smoothing", choices=["majority", "median", "none"], default="majority")
    render.add_argument("--smooth-size", type=int, default=5)
    render.add_argument("--kind", nargs="+", choices=["demartonne", "bivariate", "contours"],
                        default=["demartonne", "bivariate", "contours"])
    render.add_argument("--format", choices=["png", "svg", "pdf"], default="png")
    render.add_argument("--dpi", type=int, default=140)
    render.add_argument("--gif", action="store_true", help="Zusätzliche Animation der De-Martonne-Karten")
    render.add_argument("--frame-ms", type=int, default=1000)
    return p


def render(args):
    if args.start > args.end:
        raise ValueError("Startjahr muss vor oder gleich Endjahr liegen.")
    span = args.end - args.start + 1
    window = span if args.window is None else args.window
    if window < 1 or window > span:
        raise ValueError("Fenster muss zwischen 1 und der Anzahl Jahre liegen.")
    if args.dpi < 1 or args.frame_ms < 1 or args.smooth_size < 1 or args.smooth_size % 2 == 0:
        raise ValueError("DPI und Frame-Dauer müssen positiv, Filtergröße positiv und ungerade sein.")
    if args.gif and (args.format != "png" or "demartonne" not in args.kind):
        raise ValueError("GIF benötigt PNG-Ausgabe und die Kartenart demartonne.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reference = load_climate(args.data_dir, args.start, args.end)
    ref_p = quantile_breaks(reference.precipitation)
    ref_t = quantile_breaks(reference.temperature)
    frames, results = [], []
    for start in range(args.start, args.end - window + 2):
        end = start + window - 1
        climate = reference if window == span else load_climate(args.data_dir, start, end)
        if args.quartiles == "reference":
            pb, tb = ref_p, ref_t
            label = f"{args.start}–{args.end} (fest)"
        else:
            pb, tb = quantile_breaks(climate.precipitation), quantile_breaks(climate.temperature)
            label = f"{start}–{end} (je Fenster)"
        for kind in dict.fromkeys(args.kind):
            path = args.output_dir / f"{kind}_{start}_{end}.{args.format}"
            draw(climate, path, kind, pb, tb, label, args.smoothing, args.smooth_size, args.dpi)
            if kind == "demartonne":
                frames.append(path)
        results.append({"start": start, "end": end,
                        "valid_cells": int(np.isfinite(climate.index).sum()),
                        "precipitation_quartiles_mm": pb.tolist(),
                        "temperature_quartiles_celsius": tb.tolist()})
        print(f"Karten fertig: {start}–{end}", flush=True)
    if args.gif:
        images = []
        try:
            for path in frames:
                with Image.open(path) as image:
                    images.append(image.convert("RGB"))
            images[0].save(args.output_dir / "demartonne.gif", save_all=True, append_images=images[1:],
                           duration=args.frame_ms, loop=0, optimize=False)
        finally:
            for image in images:
                image.close()
    sources = []
    for year in range(args.start, args.end + 1):
        for kind in ("precipitation", "temperature"):
            path = source_path(args.data_dir, kind, year)
            sources.append({"year": year, "variable": kind, "filename": path.name,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {"software": {name: version(name) for name in ["numpy", "scipy", "rasterio", "matplotlib", "Pillow"]},
                "period": [args.start, args.end], "window": window,
                "quartiles": args.quartiles, "smoothing": args.smoothing,
                "smooth_size": args.smooth_size, "dpi": args.dpi, "format": args.format,
                "maps": list(dict.fromkeys(args.kind)), "windows": results, "sources": sources}
    (args.output_dir / "run.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        if args.command == "download":
            download(args.data_dir, args.start, args.end)
        else:
            render(args)
    except (ValueError, OSError) as error:
        p.exit(1, f"Fehler: {error}\n")
