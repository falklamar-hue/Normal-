#!/usr/bin/env python3
"""Overvåker AIS-posisjoner og sender e-postvarsel når kystvaktbåter nærmer seg oppdrettsanlegg."""

from __future__ import annotations

import argparse
import json
import math
import smtplib
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from urllib import error, request


@dataclass(frozen=True)
class Facility:
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Vessel:
    mmsi: str
    name: str
    latitude: float
    longitude: float
    vessel_type: str


@dataclass(frozen=True)
class Alert:
    facility: Facility
    vessel: Vessel
    distance_km: float


def load_config(config_path: Path) -> Dict:
    with config_path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    required = ["facilities", "email", "watch"]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Mangler obligatoriske felt i config: {', '.join(missing)}")

    return config


def parse_facilities(raw_facilities: Sequence[Dict]) -> List[Facility]:
    facilities: List[Facility] = []
    for item in raw_facilities:
        facilities.append(
            Facility(
                name=item["name"],
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
            )
        )
    return facilities


def fetch_vessels(endpoint: str, timeout_seconds: int = 10) -> List[Vessel]:
    """
    Leser AIS-data fra en HTTP-endepunkt.

    Endepunktet må returnere JSON på format:
    {
      "vessels": [
        {
          "mmsi": "257123000",
          "name": "KV Sortland",
          "lat": 63.123,
          "lon": 8.456,
          "type": "Coast Guard"
        }
      ]
    }
    """
    try:
        with request.urlopen(endpoint, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise RuntimeError(f"Klarte ikke hente AIS-data: {exc}") from exc

    vessels: List[Vessel] = []
    for item in payload.get("vessels", []):
        vessels.append(
            Vessel(
                mmsi=str(item["mmsi"]),
                name=item.get("name", "Ukjent"),
                latitude=float(item["lat"]),
                longitude=float(item["lon"]),
                vessel_type=item.get("type", "Unknown"),
            )
        )
    return vessels


def is_relevant_coast_guard(vessel: Vessel, watched_keywords: Iterable[str]) -> bool:
    haystack = f"{vessel.name} {vessel.vessel_type}".lower()
    return any(keyword.lower() in haystack for keyword in watched_keywords)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def find_alerts(
    facilities: Sequence[Facility],
    vessels: Sequence[Vessel],
    watched_keywords: Sequence[str],
    radius_km: float,
) -> List[Alert]:
    alerts: List[Alert] = []
    for vessel in vessels:
        if not is_relevant_coast_guard(vessel, watched_keywords):
            continue

        for facility in facilities:
            distance = haversine_km(
                facility.latitude,
                facility.longitude,
                vessel.latitude,
                vessel.longitude,
            )
            if distance <= radius_km:
                alerts.append(Alert(facility=facility, vessel=vessel, distance_km=distance))
    return alerts


def format_alert_email(alerts: Sequence[Alert]) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"Kystvaktvarsel ({timestamp})",
        "",
        f"Fant {len(alerts)} hendelser:",
        "",
    ]
    for alert in alerts:
        lines.append(
            f"- {alert.vessel.name} ({alert.vessel.mmsi}) er {alert.distance_km:.2f} km fra {alert.facility.name}"
        )
    return "\n".join(lines)


def send_email(email_config: Dict, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = email_config["from"]
    msg["To"] = email_config["to"]
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(email_config["smtp_host"], int(email_config["smtp_port"])) as server:
        if email_config.get("starttls", True):
            server.starttls(context=context)
        if email_config.get("username"):
            server.login(email_config["username"], email_config["password"])
        server.send_message(msg)


def build_alert_key(alert: Alert) -> str:
    return f"{alert.facility.name}|{alert.vessel.mmsi}"


def run_monitor(config: Dict, once: bool = False) -> None:
    facilities = parse_facilities(config["facilities"])
    email_config = config["email"]
    watch_config = config["watch"]

    radius_km = float(watch_config.get("radius_km", 5.0))
    interval_seconds = int(watch_config.get("interval_seconds", 300))
    cooldown_seconds = int(watch_config.get("cooldown_seconds", 1800))
    watched_keywords = watch_config.get("vessel_keywords", ["kystvakt", "coast guard", "kv "])
    endpoint = watch_config["ais_endpoint"]

    last_sent: Dict[str, float] = {}

    while True:
        vessels = fetch_vessels(endpoint)
        alerts = find_alerts(facilities, vessels, watched_keywords, radius_km)

        due_alerts: List[Alert] = []
        now = time.time()
        for alert in alerts:
            key = build_alert_key(alert)
            sent_at = last_sent.get(key, 0.0)
            if now - sent_at >= cooldown_seconds:
                due_alerts.append(alert)
                last_sent[key] = now

        if due_alerts:
            body = format_alert_email(due_alerts)
            subject = f"Kystvaktvarsel: {len(due_alerts)} hendelser"
            send_email(email_config, subject, body)
            print(body)
        else:
            print(f"[{datetime.now().isoformat()}] Ingen nye varsler")

        if once:
            return
        time.sleep(interval_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Varsler når kystvaktbåter nærmer seg oppdrettsanlegg")
    parser.add_argument("--config", default="config.example.json", help="Sti til JSON-konfig")
    parser.add_argument("--once", action="store_true", help="Kjør bare én sjekk")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))
    run_monitor(config, once=args.once)


if __name__ == "__main__":
    main()
