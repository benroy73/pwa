#!/usr/bin/env python3
"""Check whether a power outage is affecting a given location.

Queries two utilities that serve the Seattle area:
  SCL  Seattle City Light   https://scl.datacapable.com
  PSE  Puget Sound Energy   https://www.pse.com/outage/outage-map

Usage:
    ./outage-check.py 47.7580026,-122.2665609
    ./outage-check.py --all

Exit codes:
    0  no active outage affects the location
    10 the location is inside an active outage polygon
    2  no outage found, but at least one feed was unreachable (result partial)
    1  an error occurred (bad input, or every feed failed)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

SCL_URL = "https://utilisocial.io/datacapable/v2/p/scl/map/events"
PSE_URL = "https://www.pse.com/api/sitecore/OutageMap/AnonymoussMapListView"
USER_AGENT = "outage-check/2.0"
TIMEOUT = 20

EXIT_CLEAR = 0
EXIT_ERROR = 1
EXIT_PARTIAL = 2
EXIT_OUTAGE = 10

try:
    from zoneinfo import ZoneInfo

    PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
except Exception:  # pragma: no cover - no tzdata available
    # Fall back to the machine's local zone. PSE timestamps carry no zone and
    # are always Pacific, so on a non-Pacific machine without tzdata they will
    # be offset.
    PACIFIC_TZ = datetime.now().astimezone().tzinfo


class FeedError(Exception):
    """A provider's feed could not be fetched or parsed."""


# --------------------------------------------------------------------------
# Input parsing
# --------------------------------------------------------------------------


def parse_point(tokens: list[str]) -> tuple[float, float]:
    """Parse "lat,lon", "lat, lon" or "lat" "lon" into floats."""
    joined = " ".join(tokens).replace(",", " ")
    parts = joined.split()
    if len(parts) != 2:
        raise ValueError(f"expected coordinates as 'lat,lon', got {' '.join(tokens)!r}")
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        raise ValueError(f"coordinates must be numbers, got {' '.join(tokens)!r}")
    if not -90 <= lat <= 90:
        raise ValueError(f"latitude {lat} is out of range")
    if not -180 <= lon <= 180:
        raise ValueError(f"longitude {lon} is out of range")
    return lat, lon


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------


def fetch_json(url: str):
    """Fetch and decode JSON. A local file path may be given instead of a URL."""
    try:
        if not url.startswith(("http://", "https://")):
            with open(url, "r", encoding="utf-8") as fh:
                return json.load(fh)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise FeedError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise FeedError(f"could not reach {url} ({exc.reason})") from exc
    except json.JSONDecodeError as exc:
        raise FeedError(f"invalid JSON from {url} ({exc})") from exc
    except OSError as exc:
        raise FeedError(str(exc)) from exc


# --------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------


def epoch_ms_to_dt(ms) -> datetime | None:
    if ms in (None, 0, ""):
        return None
    try:
        dt = datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None
    return dt.astimezone(PACIFIC_TZ)


def pse_time_to_dt(value, now: datetime) -> datetime | None:
    """Parse PSE's "09/16 07:52 PM" stamps, which carry no year and no zone.

    The year is inferred by choosing whichever of last/this/next year places the
    timestamp closest to now, which handles the December/January rollover in
    both directions.
    """
    if not value or not str(value).strip():
        return None
    text = str(value).strip()
    if text.upper() in {"TBD", "N/A", "UNKNOWN", "-"}:
        return None
    # Parse with an explicit year for each candidate. Parsing "%m/%d" with no
    # year is deprecated (Python 3.13+) and cannot represent Feb 29 at all.
    best = None
    for year in (now.year - 1, now.year, now.year + 1):
        try:
            cand = datetime.strptime(f"{year} {text}", "%Y %m/%d %I:%M %p")
        except ValueError:  # malformed text, or Feb 29 in a non-leap year
            continue
        cand = cand.replace(tzinfo=PACIFIC_TZ)
        if best is None or abs(cand - now) < abs(best - now):
            best = cand
    return best


def to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Providers -> normalized events
#
# A normalized event is a dict with these keys:
#   provider id title kind status cause customers area start etr updated
#   rings center raw
# --------------------------------------------------------------------------


def load_scl(url: str, now: datetime) -> list[dict]:
    data = fetch_json(url)
    if not isinstance(data, list):
        raise FeedError("SCL: expected a JSON array of events")

    events = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # SCL draws each event as a set of small disjoint circles, one per
        # affected device, all inside a single `rings` array. They are treated
        # as a union, not as ArcGIS outer-ring/hole pairs.
        rings = []
        for ring in ((item.get("polygons") or {}).get("rings") or []):
            pts = [
                [float(p[0]), float(p[1])]
                for p in ring
                if isinstance(p, (list, tuple)) and len(p) >= 2
            ]
            if len(pts) >= 3:
                rings.append(pts)

        planned = str(item.get("type") or "").upper() == "PLANNED_OUTAGE"
        area = ", ".join(x for x in (item.get("city"), item.get("state")) if x)
        lat, lon = item.get("latitude"), item.get("longitude")

        events.append(
            {
                "provider": "SCL",
                "id": str(item.get("identifier") or item.get("id") or "unknown"),
                "title": item.get("title") or "Outage",
                "kind": "planned" if planned else "unplanned",
                "status": item.get("status"),
                "cause": item.get("cause"),
                "customers": to_int(item.get("numPeople")),
                "area": area or None,
                "start": epoch_ms_to_dt(item.get("startTime")),
                "etr": epoch_ms_to_dt(item.get("etrTime")),
                "updated": epoch_ms_to_dt(item.get("lastUpdatedTime")),
                "rings": rings,
                "center": (float(lat), float(lon)) if lat and lon else None,
                "raw": item,
            }
        )
    return events


def load_pse(url: str, now: datetime) -> list[dict]:
    data = fetch_json(url)
    if not isinstance(data, dict) or "PseMap" not in data:
        raise FeedError("PSE: expected an object with a PseMap array")

    events = []
    for item in data.get("PseMap") or []:
        if not isinstance(item, dict):
            continue
        provider_block = item.get("DataProvider") or {}
        poi = provider_block.get("PointOfInterest") or {}

        # Attributes is a list of {Name, Value} pairs rather than fixed fields.
        attrs = {}
        for attr in provider_block.get("Attributes") or []:
            name = (attr.get("Name") or "").strip()
            if name:
                attrs[name.lower()] = attr.get("Value")

        # PSE gives one flat ring of {Latitude, Longitude} objects.
        ring = []
        for pt in item.get("Polygon") or []:
            try:
                ring.append([float(pt["Longitude"]), float(pt["Latitude"])])
            except (KeyError, TypeError, ValueError):
                continue
        rings = [ring] if len(ring) >= 3 else []

        filter_type = str(poi.get("FilterType") or "")
        if "PSPS" in filter_type.upper():
            kind = "psps"
            title = "Public Safety Power Shutoff"
        elif poi.get("PlannedOutage"):
            kind = "planned"
            title = "Planned Outage"
        else:
            kind = "unplanned"
            title = "Outage"

        lat, lon = poi.get("Latitude"), poi.get("Longitude")
        try:
            center = (float(lat), float(lon)) if lat and lon else None
        except (TypeError, ValueError):
            center = None

        events.append(
            {
                "provider": "PSE",
                "id": str(attrs.get("outage id") or poi.get("Id") or "unknown"),
                "title": title,
                "kind": kind,
                "status": attrs.get("status"),
                "cause": attrs.get("cause"),
                "customers": to_int(attrs.get("customers impacted")),
                "area": poi.get("Title") or None,
                "start": pse_time_to_dt(attrs.get("start time"), now),
                "etr": pse_time_to_dt(attrs.get("est. restoration time"), now),
                "updated": pse_time_to_dt(attrs.get("last update"), now),
                "rings": rings,
                "center": center,
                "raw": item,
            }
        )
    return events


PROVIDERS = {
    "scl": {"label": "Seattle City Light", "default_url": SCL_URL, "loader": load_scl},
    "pse": {"label": "Puget Sound Energy", "default_url": PSE_URL, "loader": load_pse},
}


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


def ring_contains(ring: list[list[float]], lon: float, lat: float) -> bool:
    """Standard even-odd ray cast, in raw lon/lat space."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_int = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_int:
                inside = not inside
        j = i
    return inside


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.7613  # mean earth radius, miles
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def event_contains(event: dict, lat: float, lon: float) -> bool:
    if event["rings"]:
        return any(ring_contains(r, lon, lat) for r in event["rings"])
    center = event.get("center")
    if not center:
        return False
    return haversine_mi(lat, lon, center[0], center[1]) <= 0.05


def _project(lat: float, lon: float, lat0: float) -> tuple[float, float]:
    """Equirectangular projection to miles, accurate enough over a few miles."""
    return (lon * 69.172 * cos(radians(lat0)), lat * 69.055)


def _point_segment_mi(px, py, ax, ay, bx, by) -> float:
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx * vx + vy * vy
    t = 0.0 if denom == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    dx, dy = px - (ax + t * vx), py - (ay + t * vy)
    return sqrt(dx * dx + dy * dy)


def distance_to_event_mi(event: dict, lat: float, lon: float) -> float | None:
    """Shortest distance from the point to the event's boundary, in miles."""
    px, py = _project(lat, lon, lat)
    best = None
    for ring in event["rings"]:
        n = len(ring)
        for i in range(n):
            ax, ay = _project(ring[i][1], ring[i][0], lat)
            nxt = ring[(i + 1) % n]
            bx, by = _project(nxt[1], nxt[0], lat)
            d = _point_segment_mi(px, py, ax, ay, bx, by)
            if best is None or d < best:
                best = d
    if best is not None:
        return best
    center = event.get("center")
    return haversine_mi(lat, lon, center[0], center[1]) if center else None


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------


def fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "unknown"
    stamp = dt.strftime("%a %b %d, %Y at %I:%M %p").replace(" 0", " ")
    return f"{stamp} {dt.strftime('%Z')}".strip()


def fmt_delta(delta: timedelta) -> str:
    secs = int(abs(delta).total_seconds())
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    bits = []
    if days:
        bits.append(f"{days}d")
    if hours:
        bits.append(f"{hours}h")
    if mins and not days:
        bits.append(f"{mins}m")
    return " ".join(bits) or "less than a minute"


def relative(dt: datetime, now: datetime) -> str:
    delta = dt - now
    return f"in {fmt_delta(delta)}" if delta.total_seconds() > 0 else f"{fmt_delta(delta)} ago"


KIND_LABEL = {
    "planned": "planned outage",
    "unplanned": "unplanned outage",
    "psps": "public safety power shutoff",
}


def describe(event: dict, now: datetime, distance_mi: float | None = None) -> str:
    lines = [
        f"  [{event['provider']}] #{event['id']} — "
        f"{event['title']} ({KIND_LABEL.get(event['kind'], event['kind'])})"
    ]

    def row(label, value):
        if value:
            lines.append(f"    {label:<15}{value}")

    row("Status:", event["status"])
    row("Cause:", event["cause"])
    if event["customers"] is not None:
        row("Customers out:", f"{event['customers']:,}")
    row("Area:", event["area"])
    if event["start"]:
        row("Started:", f"{fmt_dt(event['start'])}  ({relative(event['start'], now)})")
    if event["etr"]:
        etr_note = relative(event["etr"], now)
        if event["etr"] < now:
            etr_note += ", estimate has passed"
        row("Est. restored:", f"{fmt_dt(event['etr'])}  ({etr_note})")
    else:
        row("Est. restored:", "not yet estimated")
    if event["updated"]:
        row("Last update:", f"{fmt_dt(event['updated'])}  ({relative(event['updated'], now)})")
    if distance_mi is not None:
        row("Distance:", f"{distance_mi:.2f} mi from your location")
    return "\n".join(lines)


def jsonable(event: dict, include_raw: bool, distance_mi: float | None = None) -> dict:
    out = {
        k: (v.isoformat() if isinstance(v, datetime) else v)
        for k, v in event.items()
        if k != "raw"
    }
    if distance_mi is not None:
        out["distanceMiles"] = round(distance_mi, 3)
    if include_raw:
        out["raw"] = event["raw"]
    return out


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check Seattle City Light and Puget Sound Energy outages "
        "affecting a location.",
        epilog="Exit status: 0 = clear, 10 = outage affecting location, "
        "2 = clear but a feed was unreachable, 1 = error.",
    )
    parser.add_argument(
        "coords", nargs="*", help="location as 'lat,lon' (e.g. 47.774140,-122.276985)"
    )
    parser.add_argument(
        "--provider",
        choices=["both", "scl", "pse"],
        default="both",
        help="which utility to query (default: both)",
    )
    parser.add_argument(
        "--nearby",
        type=float,
        default=0.5,
        metavar="MILES",
        help="also report outages within this distance (default: 0.5; 0 disables)",
    )
    parser.add_argument("--all", action="store_true", help="list every active event")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument(
        "--raw", action="store_true", help="include each feed's raw record in --json output"
    )
    parser.add_argument("--scl-source", default=SCL_URL, help=argparse.SUPPRESS)
    parser.add_argument("--pse-source", default=PSE_URL, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if not args.coords and not args.all:
        parser.error("provide coordinates as 'lat,lon', or use --all")

    try:
        point = parse_point(args.coords) if args.coords else None
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    now = datetime.now(PACIFIC_TZ)
    wanted = ["scl", "pse"] if args.provider == "both" else [args.provider]
    overrides = {"scl": args.scl_source, "pse": args.pse_source}

    events: list[dict] = []
    counts: dict[str, int] = {}
    failures: list[tuple[str, str]] = []
    for key in wanted:
        spec = PROVIDERS[key]
        try:
            loaded = spec["loader"](overrides[key], now)
        except FeedError as exc:
            failures.append((key.upper(), str(exc)))
            continue
        counts[key.upper()] = len(loaded)
        events.extend(loaded)

    for name, reason in failures:
        print(f"warning: {name} feed unavailable: {reason}", file=sys.stderr)
    if failures and not counts:
        print("error: no outage feed could be reached", file=sys.stderr)
        return EXIT_ERROR

    tally = ", ".join(f"{name}: {n} active" for name, n in sorted(counts.items()))

    # --all with no coordinates: just dump the list.
    if point is None:
        if args.json:
            print(
                json.dumps(
                    {
                        "checked": now.isoformat(),
                        "counts": counts,
                        "unavailable": [n for n, _ in failures],
                        "events": [jsonable(e, args.raw) for e in events],
                    },
                    indent=2,
                )
            )
        else:
            print(f"{fmt_dt(now)}  ({tally})\n")
            for ev in sorted(events, key=lambda e: (e["start"] or now), reverse=True):
                print(describe(ev, now))
                print()
        return EXIT_PARTIAL if failures else EXIT_CLEAR

    lat, lon = point
    affecting, nearby = [], []
    for ev in events:
        if event_contains(ev, lat, lon):
            affecting.append((ev, 0.0))
            continue
        dist = distance_to_event_mi(ev, lat, lon)
        if args.nearby > 0 and dist is not None and dist <= args.nearby:
            nearby.append((ev, dist))
    affecting.sort(key=lambda pair: (pair[0]["start"] or now))
    nearby.sort(key=lambda pair: pair[1])

    if args.json:
        print(
            json.dumps(
                {
                    "location": {"latitude": lat, "longitude": lon},
                    "checked": now.isoformat(),
                    "counts": counts,
                    "unavailable": [n for n, _ in failures],
                    "affected": bool(affecting),
                    "outages": [jsonable(ev, args.raw) for ev, _ in affecting],
                    "nearby": [jsonable(ev, args.raw, d) for ev, d in nearby],
                },
                indent=2,
            )
        )
    else:
        print(f"Location: {lat:.6f}, {lon:.6f}")
        print(f"Checked:  {fmt_dt(now)}  ({tally or 'no feeds available'})")
        print()

        if affecting:
            word = "outage" if len(affecting) == 1 else "outages"
            print(f"AFFECTED — your location is inside {len(affecting)} active {word}:")
            print()
            for ev, _ in affecting:
                print(describe(ev, now))
                print()
        else:
            checked = " or ".join(n for n in sorted(counts)) or "any feed"
            print(f"No active {checked} outage covers this location.")
            print()

        if nearby:
            print(f"Nearby (within {args.nearby:g} mi, not covering your location):")
            print()
            for ev, dist in nearby:
                print(describe(ev, now, distance_mi=dist))
                print()

        if args.all:
            print("All active events:")
            print()
            for ev in sorted(events, key=lambda e: (e["start"] or now), reverse=True):
                print(describe(ev, now, distance_mi=distance_to_event_mi(ev, lat, lon)))
                print()

    if affecting:
        return EXIT_OUTAGE
    return EXIT_PARTIAL if failures else EXIT_CLEAR


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        # e.g. piping into `head`; silence the interpreter's shutdown warning.
        try:
            sys.stdout.close()
        finally:
            sys.exit(141)