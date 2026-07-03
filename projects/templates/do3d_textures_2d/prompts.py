"""Prompty do ekstrakcji płaskich tekstur 2D i prostych zdjęć z tekstem z fotografii produktów."""

from __future__ import annotations

from typing import Literal

OutputMode = Literal["texture", "print_flat"]

MODE_LABELS: dict[OutputMode, str] = {
    "texture": "czysta tekstura (bez tekstu)",
    "print_flat": "zdjęcie z tekstem (proste, bez skosu)",
}

BASE_TEXTURE_PROMPT = """\
You are a print-industry material reference specialist. You receive a product \
photography image of a printed product.

Task: produce ONE flat 2D material texture swatch suitable as a Material reference \
for e-commerce product pipelines (Nano Banana / Magnific).

Rules:
- Show ONLY the paper, cardboard, or coated stock surface finish visible on the product.
- REMOVE completely: all typography, logos, illustrations, barcodes, product silhouette, \
binding hardware, eyelets, die-cut edges, background scene, hands, and props.
- Frame: square macro crop; even diffuse studio lighting; neutral white balance.
- The result must look like a photographed paper or cardstock sample swatch — NOT a product shot.
- Match the material from the reference (matte, gloss, kraft, soft-touch, UV spot sheen on \
stock only) — do NOT invent a different substrate.
- No text, no logos, no product shape in the output.\
"""

BASE_PRINT_FLAT_PROMPT = """\
You are a print prepress and product photography specialist. You receive a product \
photography image of a printed product.

Task: produce ONE flat, front-facing product photo that keeps the printed content \
(text, logos, graphics) from the reference — but fully corrected to a straight, \
undistorted view.

Rules:
- KEEP the same printed content as in the reference (wording, layout, colors, logos) — \
do NOT invent new copy or replace text.
- Geometry: orthogonal front view; zero perspective; no keystone; no curved or warped text; \
all baselines perfectly horizontal and vertical; as if photographed flat on a copy stand or scanned.
- The printed surface must look planar — no folds, bends, spine curl, or 3D product shape.
- Remove background scene, hands, props, shadows from staging; use neutral even studio lighting.
- Text must be sharp, readable, and not italicized or skewed by camera angle.
- Match paper stock, ink colors, and finish (matte, gloss, UV spot) from the reference.
- Crop tightly to the printable area; square or near-square framing acceptable.\
"""

# Dodatek per typ materiału — tryb texture.
TEXTURE_ADDON: dict[str, str] = {
    "pudelka": (
        "Substrate: packaging cardboard or kraft carton. Extract outer box surface texture "
        "(matte or semi-gloss coat). Ignore flap folds and print."
    ),
    "ulotki": (
        "Substrate: coated offset or digital print paper for flyers. Extract base paper "
        "texture; if spot UV is present, keep only the paper stock matte areas, not the gloss pattern."
    ),
    "druki-samokopiujace": (
        "Substrate: carbonless (NCR) copy paper. Extract smooth office paper tooth; "
        "ignore ruled lines and header print."
    ),
    "teczki": (
        "Substrate: presentation folder cardstock with lamination. Extract cover lamination "
        "finish (matte, gloss, or soft-touch)."
    ),
    "katalogi": (
        "Substrate: bound catalog cover paper or PUR soft-touch laminate. Extract cover "
        "stock texture only; ignore spine binding."
    ),
    "metki": (
        "Substrate: hangtag or label cardstock. Extract uncoated or coated tag paper texture."
    ),
    "zawieszki": (
        "Substrate: hotel door hanger cardstock. Extract coated cardstock texture; ignore die-cut hole."
    ),
    "arkusze-plano": (
        "Substrate: large-format plano print paper. Extract smooth or lightly textured sheet stock."
    ),
    "podkladki": (
        "Substrate: absorbent placemat or board stock. Extract fibrous paperboard texture."
    ),
    "etui": (
        "Substrate: card sleeve or small packaging cardstock. Extract sleeve paper texture."
    ),
    "default": (
        "Substrate: printed product paper or cardstock. Extract the dominant printable surface finish."
    ),
}

# Dodatek per typ materiału — tryb print_flat.
PRINT_FLAT_ADDON: dict[str, str] = {
    "pudelka": (
        "Product: flat unfolded box panel or lid face. Show one printed panel only; "
        "straighten any perspective from the reference photo."
    ),
    "ulotki": (
        "Product: single flyer sheet, flat. Keep headline and body text readable; "
        "correct any camera tilt or trapezoid distortion."
    ),
    "druki-samokopiujace": (
        "Product: flat NCR form sheet. Keep form fields and header text; "
        "straighten ruled lines to perfect horizontal."
    ),
    "teczki": (
        "Product: folder front cover only, flat. Keep cover print; remove folder depth and spine angle."
    ),
    "katalogi": (
        "Product: catalog front cover only, flat. Keep cover artwork and title; "
        "no spine, no page thickness visible."
    ),
    "metki": (
        "Product: flat hangtag face. Keep tag print; ignore hole or string; straighten tag edges."
    ),
    "zawieszki": (
        "Product: flat door hanger face. Keep printed message; straighten die-cut outline to front view."
    ),
    "arkusze-plano": (
        "Product: flat plano sheet. Keep printed layout; correct any sheet curl or perspective."
    ),
    "podkladki": (
        "Product: flat placemat face. Keep printed design; remove table or scene context."
    ),
    "etui": (
        "Product: flat card sleeve face. Keep sleeve print; straighten to front orthogonal view."
    ),
    "default": (
        "Product: dominant printable face from the reference. Keep all visible print; "
        "correct perspective to a flat document-style photo."
    ),
}


def slug_from_filename(filename: str) -> str:
    """np. 738-teczki-a4-klasyczne-1.jpg -> teczki-a4-klasyczne"""
    stem = filename.rsplit(".", 1)[0]
    parts = stem.split("-", 1)
    if len(parts) < 2:
        return stem
    rest = parts[1]
    if rest.rsplit("-", 1)[-1].isdigit():
        rest = rest.rsplit("-", 1)[0]
    return rest


def category_key(slug: str) -> str:
    for key in TEXTURE_ADDON:
        if key == "default":
            continue
        if key in slug:
            return key
    return "default"


def build_prompt(filename: str, mode: OutputMode = "texture") -> str:
    slug = slug_from_filename(filename)
    cat = category_key(slug)
    if mode == "texture":
        return f"{BASE_TEXTURE_PROMPT}\n\n{TEXTURE_ADDON[cat]}"
    return f"{BASE_PRINT_FLAT_PROMPT}\n\n{PRINT_FLAT_ADDON[cat]}"


def output_name(filename: str, mode: OutputMode) -> str:
    stem = filename.rsplit(".", 1)[0]
    prefix = "texture" if mode == "texture" else "print_flat"
    return f"{prefix}_{stem}.jpg"


def build_modes(filename: str) -> dict[OutputMode, dict[str, str]]:
    """Dwa warianty wyjścia na jedną referencję wejściową."""
    return {
        mode: {
            "label": MODE_LABELS[mode],
            "prompt": build_prompt(filename, mode),
            "output_name": output_name(filename, mode),
        }
        for mode in ("texture", "print_flat")
    }


def product_id_from_filename(filename: str) -> str:
    return filename.split("-", 1)[0]
