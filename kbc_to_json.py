#!/usr/bin/env python3
"""
Telecharge la page flat.php de KBC ESOP et la convertit en JSON
consommable par le fournisseur de cours "JSON" de Portfolio Performance.

L'URL est lue dans la variable d'environnement KBC_URL (jamais en dur,
pour ne pas la commiter par accident).

Usage local :
    export KBC_URL='https://option.esop.kbc.be/flat.php?enc=...'
    python3 kbc_to_json.py quotes/bestof-eunl-2026-03-31.json

Aucune dependance externe : uniquement la bibliotheque standard.
"""

import json
import os
import pathlib
import re
import sys
import urllib.request

TIMEOUT = 30
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# "2026-08-25 00:00,12.73"  ->  date, valeur
LINE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2})(?:[ T]\d{2}:\d{2}(?::\d{2})?)?\s*[,;]\s*"
    r"(-?\d+(?:[.,]\d+)?)\s*$"
)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
    text = raw.decode("utf-8", errors="replace")
    if "error.php" in resp.geturl() or "went wrong" in text:
        raise RuntimeError("KBC a renvoye une page d'erreur : token invalide ou expire.")
    return text


def parse(text: str) -> list[dict]:
    # tolere un eventuel habillage HTML autour des lignes
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)

    rows: dict[str, float] = {}
    for line in text.splitlines():
        m = LINE.match(line)
        if m:
            rows[m.group(1)] = float(m.group(2).replace(",", "."))

    if not rows:
        raise RuntimeError(
            "aucune ligne date,valeur reconnue. La page a-t-elle change de format ?"
        )
    return [{"date": d, "close": rows[d]} for d in sorted(rows)]


def main() -> int:
    url = os.environ.get("KBC_URL")
    if not url:
        print("ECHEC : variable d'environnement KBC_URL absente.", file=sys.stderr)
        return 2

    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "quotes.json")
    quotes = parse(fetch(url))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(quotes, indent=1), encoding="utf-8")

    print(f"OK  {len(quotes)} cours  ({quotes[0]['date']} -> {quotes[-1]['date']})")
    print(f"    dernier : {quotes[-1]['close']}  ->  {out}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ECHEC : {exc}", file=sys.stderr)
        sys.exit(1)
