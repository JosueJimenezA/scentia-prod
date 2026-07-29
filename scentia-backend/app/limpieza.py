import json
import ast
import re
import pandas as pd
import unicodedata

# Conjuntos léxicos para desacoplar las distribuciones JSON del scraper
SEASONS_KEYS = {"invierno", "primaverda", "verano", "otoño","oto\u00f1o"}
TIME_OF_DAY_KEYS = {"noche", "dia","d\u00eda"}
LONGEVITY_KEYS = {"escasa", "débil", "dÉbil", "d\u00e9bil", "duradera", "muy duradera"} 
SILLAGE_KEYS = {"suave", "pesada", "enorme"}
GENDER_KEYS = {"femenino", "unisex femenino", "unisex", "unisex masculino", "masculino"}
PRICE_KEYS = {
    "extremadamente costoso", "ligeramente costoso", 
    "precio moderado", "buen precio", "excelente precio"
}

def clean_note_text(note: str) -> str:
    """Estandariza una nota a minúsculas, elimina caracteres especiales y limpia espacios."""
    if not note:
        return ""
    note = str(note).lower().strip()

    # Normaliza Unicode: separa los caracteres de sus tildes (ej. 'á' -> 'a' + '´')
    note = unicodedata.normalize('NFD', note)
    # Elimina los símbolos de tildes (categoría Mn: Nonspacing Mark)
    note = re.sub(r'[\u0300-\u036f]', '', note)
    
    # Reemplaza la 'ñ' por 'n' si es necesario
    note = note.replace('ñ', 'n')
    
    # Ahora sí podemos limpiar caracteres no alfanuméricos de forma segura
    note = re.sub(r'[^a-z0-9\s_]', '', note)
    return note.strip()

def parse_notes_list_clean(val) -> list:
    """Parsea y homogeniza cadenas o listas de notas."""
    if pd.isna(val) or not str(val).strip():
        return []
    val_str = str(val).strip()
    
    # Si viene en formato lista de Python "['lemon', 'rose']"
    if val_str.startswith('[') and val_str.endswith(']'):
        try:
            parsed = ast.literal_eval(val_str)
            if isinstance(parsed, list):
                return [clean_note_text(n) for n in parsed if clean_note_text(n)]
        except Exception:
            pass
            
    # Si viene como string separado por comas / barras
    raw_notes = re.split(r'[,|/]', re.sub(r"[\[\]'\"']", "", val_str))
    return [clean_note_text(n) for n in raw_notes if clean_note_text(n)]

def parse_dict(val):
    """Convierte de forma segura cadenas JSON o reprs de diccionarios a dicts de Python."""
    if pd.isna(val) or val is None:
        return {}
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(val)
        except Exception:
            return {}

def separate_distributions_from_dict(row_data):
    """
    Separa las distribuciones combinadas o ambiguas del scraper 
    (longevidad vs estela, género vs precio). Funciona tanto con dicts como con pd.Series.
    """
    get_val = row_data.get if isinstance(row_data, dict) else row_data.get

    seasons_day_dict = parse_dict(get_val('seasons_raw_dist') or get_val('time_of_day_raw_dist'))
    long_sill_dict = parse_dict(get_val('longevity_raw_dist') or get_val('sillage_raw_dist'))
    gen_price_dict = parse_dict(get_val('price_value_raw_dist') or get_val('gender_voted_raw_dist'))

    seasons_clean = {}
    time_of_day_clean = {}
    
    for k, v in seasons_day_dict.items():
        k_lower = str(k).lower().strip()
        if k_lower in SEASONS_KEYS:
            seasons_clean[k_lower] = v
        elif k_lower in TIME_OF_DAY_KEYS:
            time_of_day_clean[k_lower] = v

    longevity_clean = {}
    sillage_clean = {}
    
    for k, v in long_sill_dict.items():
        k_lower = str(k).lower().strip()
        if k_lower in LONGEVITY_KEYS or k_lower == "moderada":
            longevity_clean[k_lower] = v
        if k_lower in SILLAGE_KEYS or k_lower == "moderada":
            sillage_clean[k_lower] = v

    gender_clean = {}
    price_clean = {}
    
    for k, v in gen_price_dict.items():
        k_lower = str(k).lower().strip()
        if k_lower in GENDER_KEYS:
            gender_clean[k_lower] = v
        elif k_lower in PRICE_KEYS:
            price_clean[k_lower] = v

    return seasons_clean, time_of_day_clean, longevity_clean, sillage_clean, gender_clean, price_clean

def safe_int(val, default=0):
    if pd.isna(val): 
        return default
    try:
        clean_str = str(val).replace(',', '').replace('.', '').strip()
        return int(clean_str)
    except (ValueError, TypeError):
        return default

def safe_float(val, default=None):
    if pd.isna(val): 
        return default
    try:
        clean_str = str(val).replace(',', '.').strip()
        return float(clean_str)
    except (ValueError, TypeError):
        return default