#!/usr/bin/env python3
"""
Telecharge une ou plusieurs pages flat.php de KBC ESOP et les convertit en
fichiers JSON consommables par le fournisseur de cours "JSON" de
Portfolio Performance.

Les URL sont lues dans la variable d'environnement KBC_URLS, une par ligne,
au format  nom=url  :

    KBC_URLS="bestof-eunl-2026-03-31=https://option.esop.kbc.be/flat.php?enc=AAA
    top-warrant-2025-06-30=https://warrant.esop.kbc.be/flat.php?enc=BBB"

Chaque produit produit <dossier>/<nom>.json .
Les lignes vides et celles commencant par # sont ignorees.

Usage :
    export KBC_URLS='...'
    python3 kbc_to_json.py quotes

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

# noms de fichiers autorises (pas de / ni de .. : on ecrit ou on veut ecrire)
SLUG = re.compile(r"^[A-Za-z0-9._-]+$")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
        final = resp.geturl()
    text = raw.decode("utf-8", errors="replace")
    if "error.php" in final or "went wrong" in text:
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


def read_products() -> list[tuple[str, str]]:
    """Lit KBC_URLS (multi-produits) ou retombe sur KBC_URL (mono-produit)."""
    blob = os.environ.get("KBC_URLS", "").strip()

    if not blob:
        legacy = os.environ.get("KBC_URL", "").strip()
        if legacy:
            return [("quotes", legacy)]
        raise RuntimeError("ni KBC_URLS ni KBC_URL ne sont definies.")

    products: list[tuple[str, str]] = []
    seen: set[str] = set()

    for lineno, line in enumerate(blob.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RuntimeError(f"ligne {lineno} : format attendu  nom=url")

        name, url = line.split("=", 1)
        name, url = name.strip(), url.strip()

        if not SLUG.match(name):
            raise RuntimeError(
                f"ligne {lineno} : nom {name!r} invalide "
                "(lettres, chiffres, point, tiret et underscore uniquement)"
            )
        if not url.startswith("https://"):
            raise RuntimeError(f"ligne {lineno} : l'URL doit commencer par https://")
        if name in seen:
            raise RuntimeError(f"ligne {lineno} : nom {name!r} en double")

        seen.add(name)
        products.append((name, url))

    if not products:
        raise RuntimeError("KBC_URLS est definie mais ne contient aucun produit.")
    return products


def main() -> int:
    outdir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "quotes")
    products = read_products()
    outdir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for name, url in products:
        try:
            quotes = parse(fetch(url))
        except Exception as exc:  # noqa: BLE001
            print(f"KO   {name} : {exc}", file=sys.stderr)
            failures += 1
            continue

        target = outdir / f"{name}.json"
        target.write_text(json.dumps(quotes, indent=1), encoding="utf-8")
        print(
            f"OK   {name} : {len(quotes)} cours "
            f"({quotes[0]['date']} -> {quotes[-1]['date']}), "
            f"dernier {quotes[-1]['close']}  ->  {target}"
        )

    if failures:
        print(f"\n{failures} produit(s) en echec sur {len(products)}.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ECHEC : {exc}", file=sys.stderr)
        sys.exit(2)
