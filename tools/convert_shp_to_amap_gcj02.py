#!/usr/bin/env python3
"""Convert WGS84/OSM shapefile coordinates to AMap/GCJ-02 using AMap Web API.

The script reads every .shp file in an input directory, calls the AMap
coordinate conversion API for unique coordinates, and writes converted
shapefiles to a separate output directory. It never overwrites the source
directory unless explicitly pointed there with a non-empty suffix.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests
import shapefile


AMAP_CONVERT_URL = "https://restapi.amap.com/v3/assistant/coordinate/convert"
MAX_AMAP_BATCH_SIZE = 40
SIDECARS_TO_COPY = (".prj", ".cpg")

Coord = Tuple[float, float]
Cache = Dict[str, List[float]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert SHP coordinates to AMap/GCJ-02 with AMap coordinate conversion API."
    )
    parser.add_argument(
        "--input-dir",
        default="dxc_traffic_shp",
        help="Directory containing source OSM/WGS84 shapefiles. Default: dxc_traffic_shp",
    )
    parser.add_argument(
        "--output-dir",
        default="dxc_traffic_amap_shp",
        help="Directory for converted shapefiles. Default: dxc_traffic_amap_shp",
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("AMAP_KEY", ""),
        help="AMap Web service key. Can also be provided with AMAP_KEY env var.",
    )
    parser.add_argument(
        "--coordsys",
        default="gps",
        choices=("gps", "mapbar", "baidu"),
        help="Source coordinate system expected by AMap API. OSM/WGS84 should use gps.",
    )
    parser.add_argument(
        "--suffix",
        default="",
        help="Optional suffix appended to output file stems, for example _gcj02.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively process .shp files under input-dir.",
    )
    parser.add_argument(
        "--encoding",
        default=None,
        help="DBF encoding. If omitted, pyshp tries to infer/use default encoding.",
    )
    parser.add_argument(
        "--request-precision",
        type=int,
        default=6,
        help="Decimal precision sent to AMap API and used for cache keys. Default: 6.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=MAX_AMAP_BATCH_SIZE,
        help="Coordinates per API call. AMap maximum is 40. Default: 40.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.08,
        help="Sleep seconds between API calls. Default: 0.08.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout seconds. Default: 20.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retry count for each API batch. Default: 3.",
    )
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        help="Ignore HTTP_PROXY/HTTPS_PROXY environment variables when calling AMap API.",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="Explicit proxy URL for AMap API requests, for example http://127.0.0.1:7890.",
    )
    parser.add_argument(
        "--cache-file",
        default=None,
        help="JSON cache file. Default: <output-dir>/.amap_coord_cache_<coordsys>.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only scan shapefiles and report counts; do not call API or write output.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output shapefile set.",
    )
    return parser.parse_args()


def discover_shapefiles(input_dir: Path, recursive: bool) -> List[Path]:
    pattern = "**/*.shp" if recursive else "*.shp"
    return sorted(input_dir.glob(pattern))


def coord_key(lon: float, lat: float, precision: int) -> str:
    return f"{lon:.{precision}f},{lat:.{precision}f}"


def load_cache(path: Path) -> Cache:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    cache: Cache = {}
    for key, value in raw.items():
        if (
            isinstance(value, list)
            and len(value) == 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            cache[key] = [float(value[0]), float(value[1])]
    return cache


def save_cache(path: Path, cache: Cache) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
    tmp_path.replace(path)


def read_shapefile(path: Path, encoding: Optional[str]) -> shapefile.Reader:
    if encoding:
        return shapefile.Reader(str(path), encoding=encoding)
    return shapefile.Reader(str(path))


def iter_shape_points(reader: shapefile.Reader) -> Iterable[Coord]:
    for shape in reader.iterShapes():
        for lon, lat in shape.points:
            yield float(lon), float(lat)


def collect_unique_coords(shp_paths: Sequence[Path], encoding: Optional[str], precision: int) -> Dict[str, Coord]:
    coords: Dict[str, Coord] = {}
    for shp_path in shp_paths:
        reader = read_shapefile(shp_path, encoding)
        try:
            for lon, lat in iter_shape_points(reader):
                key = coord_key(lon, lat, precision)
                coords.setdefault(key, (round(lon, precision), round(lat, precision)))
        finally:
            reader.close()
    return coords


def chunked(items: Sequence[Tuple[str, Coord]], size: int) -> Iterable[Sequence[Tuple[str, Coord]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def create_http_session(args: argparse.Namespace) -> requests.Session:
    session = requests.Session()

    if args.no_proxy and args.proxy:
        raise ValueError("--no-proxy and --proxy cannot be used together")

    if args.no_proxy:
        session.trust_env = False
        session.proxies = {}
        print("[network] proxy disabled; ignoring HTTP_PROXY/HTTPS_PROXY environment variables")
    elif args.proxy:
        session.trust_env = False
        session.proxies = {
            "http": args.proxy,
            "https": args.proxy,
        }
        print(f"[network] using explicit proxy: {args.proxy}")

    return session


def request_amap_batch(
    session: requests.Session,
    batch: Sequence[Tuple[str, Coord]],
    key: str,
    coordsys: str,
    timeout: float,
    retries: int,
) -> List[Coord]:
    locations = "|".join(f"{lon:.6f},{lat:.6f}" for _, (lon, lat) in batch)
    params = {
        "locations": locations,
        "coordsys": coordsys,
        "output": "json",
        "key": key,
    }

    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(AMAP_CONVERT_URL, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "1":
                info = data.get("info") or data.get("errmsg") or "unknown error"
                infocode = data.get("infocode") or data.get("errcode") or "unknown code"
                raise RuntimeError(f"AMap API failed: {info} ({infocode})")

            converted_text = data.get("locations", "")
            converted = []
            for item in converted_text.split(";"):
                if not item:
                    continue
                lon_text, lat_text = item.split(",", 1)
                converted.append((float(lon_text), float(lat_text)))

            if len(converted) != len(batch):
                raise RuntimeError(
                    f"AMap API returned {len(converted)} coordinates for {len(batch)} inputs"
                )
            return converted
        except requests.exceptions.ProxyError as exc:
            last_error = RuntimeError(
                "Proxy connection failed while requesting AMap API. "
                "If you do not need a proxy, rerun with --no-proxy. "
                "If you need a proxy, pass --proxy http://host:port or fix HTTP_PROXY/HTTPS_PROXY.\n"
                f"Original error: {exc}"
            )
            if attempt < retries:
                time.sleep(min(2.0, 0.4 * attempt))
        except Exception as exc:  # noqa: BLE001 - surface API and HTTP errors uniformly.
            last_error = exc
            if attempt < retries:
                time.sleep(min(2.0, 0.4 * attempt))

    assert last_error is not None
    raise last_error


def convert_missing_coords(
    missing: Sequence[Tuple[str, Coord]],
    cache: Cache,
    cache_file: Path,
    args: argparse.Namespace,
) -> None:
    session = create_http_session(args)
    total = len(missing)
    processed = 0
    batch_size = min(max(1, args.batch_size), MAX_AMAP_BATCH_SIZE)

    for batch in chunked(missing, batch_size):
        converted = request_amap_batch(
            session=session,
            batch=batch,
            key=args.key,
            coordsys=args.coordsys,
            timeout=args.timeout,
            retries=args.retries,
        )
        for (source_key, _), (lon, lat) in zip(batch, converted):
            cache[source_key] = [lon, lat]

        processed += len(batch)
        print(f"[convert] {processed}/{total} coordinates converted")
        save_cache(cache_file, cache)
        if args.sleep > 0:
            time.sleep(args.sleep)


def convert_shape(shape: shapefile.Shape, cache: Cache, precision: int) -> shapefile.Shape:
    if shape.shapeType == shapefile.NULL:
        return shape

    converted_shape = shapefile.Shape(shape.shapeType)
    converted_shape.points = [
        tuple(cache[coord_key(float(lon), float(lat), precision)])
        for lon, lat in shape.points
    ]
    if converted_shape.points:
        xs = [point[0] for point in converted_shape.points]
        ys = [point[1] for point in converted_shape.points]
        converted_shape.bbox = [min(xs), min(ys), max(xs), max(ys)]
    converted_shape.parts = list(getattr(shape, "parts", []))

    if hasattr(shape, "partTypes"):
        converted_shape.partTypes = list(shape.partTypes)
    if hasattr(shape, "z"):
        converted_shape.z = list(shape.z)
    if hasattr(shape, "m"):
        converted_shape.m = list(shape.m)

    return converted_shape


def output_base_for(shp_path: Path, input_dir: Path, output_dir: Path, suffix: str) -> Path:
    rel = shp_path.relative_to(input_dir)
    out_parent = output_dir / rel.parent
    return out_parent / f"{shp_path.stem}{suffix}"


def remove_existing_shapefile_set(out_base: Path) -> None:
    for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".shp.xml"):
        path = out_base.with_suffix(ext)
        if path.exists():
            path.unlink()


def copy_sidecars(src_base: Path, out_base: Path) -> None:
    for ext in SIDECARS_TO_COPY:
        src = src_base.with_suffix(ext)
        if src.exists():
            out_base.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out_base.with_suffix(ext))


def write_converted_shapefile(
    shp_path: Path,
    input_dir: Path,
    output_dir: Path,
    cache: Cache,
    args: argparse.Namespace,
) -> None:
    out_base = output_base_for(shp_path, input_dir, output_dir, args.suffix)
    out_shp = out_base.with_suffix(".shp")

    if shp_path.resolve() == out_shp.resolve():
        raise RuntimeError("Refusing to overwrite source shapefile. Use a different output-dir or suffix.")
    if out_shp.exists() and not args.force:
        raise RuntimeError(f"Output exists: {out_shp}. Use --force to overwrite.")
    if out_shp.exists() and args.force:
        remove_existing_shapefile_set(out_base)

    reader = read_shapefile(shp_path, args.encoding)
    writer_kwargs = {"shapeType": reader.shapeType}
    if args.encoding:
        writer_kwargs["encoding"] = args.encoding

    out_base.parent.mkdir(parents=True, exist_ok=True)
    writer = shapefile.Writer(str(out_base), **writer_kwargs)
    writer.autoBalance = 1

    try:
        for field in reader.fields[1:]:
            writer.field(*field)

        for shape_record in reader.iterShapeRecords():
            writer.shape(convert_shape(shape_record.shape, cache, args.request_precision))
            writer.record(*shape_record.record)
    finally:
        writer.close()
        reader.close()

    copy_sidecars(shp_path.with_suffix(""), out_base)
    print(f"[write] {out_shp}")


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    cache_file = Path(args.cache_file).resolve() if args.cache_file else (
        output_dir / f".amap_coord_cache_{args.coordsys}.json"
    )

    if args.batch_size > MAX_AMAP_BATCH_SIZE:
        print(f"[warn] AMap supports at most {MAX_AMAP_BATCH_SIZE} coordinates per request; clamping batch size.")
        args.batch_size = MAX_AMAP_BATCH_SIZE

    if not input_dir.exists():
        print(f"[error] input directory not found: {input_dir}", file=sys.stderr)
        return 2

    shp_paths = discover_shapefiles(input_dir, args.recursive)
    if not shp_paths:
        print(f"[error] no .shp files found in {input_dir}", file=sys.stderr)
        return 2

    unique_coords = collect_unique_coords(shp_paths, args.encoding, args.request_precision)
    print(f"[scan] shapefiles: {len(shp_paths)}")
    print(f"[scan] unique coordinates: {len(unique_coords)}")
    print(f"[scan] output directory: {output_dir}")

    if args.dry_run:
        print("[dry-run] no API requests were sent and no files were written")
        return 0

    if not args.key:
        print("[error] AMap key is required. Pass --key or set AMAP_KEY.", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    cache = load_cache(cache_file)
    missing = [(key, coord) for key, coord in unique_coords.items() if key not in cache]
    print(f"[cache] cached coordinates: {len(cache)}")
    print(f"[cache] missing coordinates: {len(missing)}")

    if missing:
        convert_missing_coords(missing, cache, cache_file, args)
    else:
        print("[cache] all coordinates already converted")

    for shp_path in shp_paths:
        write_converted_shapefile(shp_path, input_dir, output_dir, cache, args)

    save_cache(cache_file, cache)
    print("[done] conversion complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
