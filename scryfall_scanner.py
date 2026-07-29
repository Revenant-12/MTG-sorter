import requests
import re
import urllib.parse
from PIL import Image
import io
import os

SCRYFALL_BASE_URL = "https://api.scryfall.com"
HEADERS = {"User-Agent": "MTGSorterApp/1.0 (https://github.com/Revenant-12/MTG-sorter)"}

COLOR_MAP = {
    "W": "White",
    "U": "Blue",
    "B": "Black",
    "R": "Red",
    "G": "Green"
}

CATEGORY_LIST = [
    "Land", "Legendary Creature", "Creature", "Instant", "Sorcery",
    "Legendary Enchantment", "Enchantment", "Planeswalker",
    "Legendary Artifact", "Artifact Equipment", "Artifact Vehicle",
    "Artifact Creature", "Artifact Treasure", "Artifact"
]

def map_colors(colors_list):
    if not colors_list:
        return "Colorless"
    mapped = [COLOR_MAP.get(c, c) for c in colors_list if c in COLOR_MAP]
    if not mapped:
        return "Colorless"
    if len(mapped) == 1:
        return mapped[0]
    return "/".join(mapped)

def map_category(type_line):
    if not type_line:
        return "Creature"
    
    tl = type_line.lower()
    
    # Specific artifact categories
    if "artifact creature" in tl:
        return "Artifact Creature"
    if "artifact" in tl and "equipment" in tl:
        return "Artifact Equipment"
    if "artifact" in tl and "vehicle" in tl:
        return "Artifact Vehicle"
    if "artifact" in tl and "treasure" in tl:
        return "Artifact Treasure"
    if "legendary artifact" in tl:
        return "Legendary Artifact"
    if "artifact" in tl:
        return "Artifact"
        
    # Legendary categories
    if "legendary creature" in tl:
        return "Legendary Creature"
    if "legendary enchantment" in tl:
        return "Legendary Enchantment"
        
    # Standard categories
    if "planeswalker" in tl:
        return "Planeswalker"
    if "creature" in tl:
        return "Creature"
    if "land" in tl:
        return "Land"
    if "instant" in tl:
        return "Instant"
    if "sorcery" in tl:
        return "Sorcery"
    if "enchantment" in tl:
        return "Enchantment"
        
    return "Creature"

def parse_subtypes(type_line):
    if not type_line or "—" not in type_line:
        return ""
    parts = type_line.split("—")
    if len(parts) > 1:
        return parts[1].strip()
    return ""

def parse_scryfall_card(card_data):
    """
    Transforms raw Scryfall API response into application card dictionary format.
    """
    if not card_data or card_data.get("object") == "error":
        return None

    # Handle multi-faced cards (e.g. Transformers / DFCs)
    if "card_faces" in card_data and "image_uris" not in card_data:
        face = card_data["card_faces"][0]
        colors = face.get("colors", card_data.get("colors", []))
        type_line = face.get("type_line", "")
        mana_cost = face.get("mana_cost", "")
        power = face.get("power")
        toughness = face.get("toughness")
        ability = face.get("oracle_text", "")
        image_url = face.get("image_uris", {}).get("normal", "")
        loyalty = face.get("loyalty")
    else:
        colors = card_data.get("colors", [])
        type_line = card_data.get("type_line", "")
        mana_cost = card_data.get("mana_cost", "")
        power = card_data.get("power")
        toughness = card_data.get("toughness")
        ability = card_data.get("oracle_text", "")
        image_url = card_data.get("image_uris", {}).get("normal", "")
        loyalty = card_data.get("loyalty")

    # Power / Toughness
    pt_str = ""
    if power is not None and toughness is not None:
        pt_str = f"{power}/{toughness}"

    # Loyalty
    loyalty_val = None
    if loyalty is not None:
        try:
            loyalty_val = int(loyalty)
        except Exception:
            loyalty_val = str(loyalty)

    return {
        "name": card_data.get("name", ""),
        "color": map_colors(colors),
        "quantity": 1,
        "card_category": map_category(type_line),
        "mana_cost": mana_cost,
        "power_toughness": pt_str,
        "subtypes": parse_subtypes(type_line),
        "keywords": ", ".join(card_data.get("keywords", [])) if card_data.get("keywords") else "",
        "ability": ability,
        "loyalty": loyalty_val,
        "set_code": card_data.get("set", "").upper(),
        "collector_number": str(card_data.get("collector_number", "")),
        "collection_id": None
    }

def fetch_card_by_name(name):
    """
    Queries Scryfall by card name (fuzzy search).
    """
    if not name or not name.strip():
        return None
    url = f"{SCRYFALL_BASE_URL}/cards/named?fuzzy={urllib.parse.quote(name.strip())}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            return parse_scryfall_card(resp.json())
    except Exception as e:
        print(f"Scryfall query error: {e}")
    return None

def fetch_card_by_set_collector(set_code, collector_number):
    """
    Queries Scryfall by exact Set Code & Collector Number.
    """
    if not set_code or not collector_number:
        return None
    s_code = set_code.strip().lower()
    c_num = str(collector_number).strip().lower()
    url = f"{SCRYFALL_BASE_URL}/cards/{urllib.parse.quote(s_code)}/{urllib.parse.quote(c_num)}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            return parse_scryfall_card(resp.json())
    except Exception as e:
        print(f"Scryfall query error: {e}")
    return None

def fetch_card_printings(card_name):
    """
    Fetches all printings (sets and collector numbers) for a given card name from Scryfall API.
    Returns a list of dicts: [{'label': ..., 'set_code': ..., 'collector_number': ..., 'card_data': ...}]
    """
    if not card_name or not card_name.strip():
        return []
    
    clean_name = card_name.strip()
    encoded = urllib.parse.quote(clean_name)
    url = f"{SCRYFALL_BASE_URL}/cards/search?q=%21%22{encoded}%22+include%3Aextras&unique=prints"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            printings = []
            for item in data:
                set_code = item.get("set", "").upper()
                collector_num = str(item.get("collector_number", ""))
                set_name = item.get("set_name", "")
                parsed = parse_scryfall_card(item)
                label = f"{set_code} - #{collector_num} ({set_name})"
                printings.append({
                    "label": label,
                    "set_code": set_code,
                    "collector_number": collector_num,
                    "set_name": set_name,
                    "card_data": parsed
                })
            return printings
    except Exception as e:
        print(f"Error fetching printings: {e}")
    return []

def autocomplete_card_name(query):
    """
    Fetches card name suggestions from Scryfall API.
    """
    if not query or len(query.strip()) < 2:
        return []
    url = f"{SCRYFALL_BASE_URL}/cards/autocomplete?q={urllib.parse.quote(query.strip())}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=3)
        if resp.status_code == 200:
            return resp.json().get("data", [])
    except Exception:
        pass
    return []

def scan_card_image(image_bytes):
    """
    Uses OCR to extract text from an uploaded or camera-captured card image,
    then attempts to query Scryfall with detected card names/set codes.
    Returns (extracted_card_dict, raw_detected_text)
    """
    extracted_text = ""
    try:
        import pytesseract
        image = Image.open(io.BytesIO(image_bytes))
        extracted_text = pytesseract.image_to_string(image)
    except Exception:
        try:
            import easyocr
            import numpy as np
            reader = easyocr.Reader(['en'], gpu=False)
            image_np = np.array(Image.open(io.BytesIO(image_bytes)))
            results = reader.readtext(image_np, detail=0)
            extracted_text = "\n".join(results)
        except Exception as e:
            extracted_text = f"OCR Error: {e}"

    if not extracted_text:
        return None, "No text detected."

    lines = [line.strip() for line in extracted_text.splitlines() if len(line.strip()) > 2]
    
    for line in lines[:5]:
        clean_line = re.sub(r'[^a-zA-Z0-9\s,\'-]', '', line)
        if len(clean_line) >= 3:
            card = fetch_card_by_name(clean_line)
            if card:
                return card, extracted_text

    return None, extracted_text
