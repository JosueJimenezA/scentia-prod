import json
import pandas as pd
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models import Fragrance
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models import Fragrance
from app.limpieza import (
    parse_notes_list_clean,
    separate_distributions_from_dict,
    parse_dict,
    safe_int,
    safe_float
)


def check_fragrance_exists(db: Session, query_text: str, target_url: str = None) -> Fragrance | None:
    """
    Verifica si una fragancia ya existe en la base de datos local
    revisando primero por la URL directa y luego por coincidencia de palabras clave.
    """
    # 1. Validación por URL si ya se conoce
    if target_url:
        existing_by_url = db.query(Fragrance).filter(
            Fragrance.fragrantica_url == target_url
        ).first()
        if existing_by_url:
            return existing_by_url

    # 2. Validación por términos clave del nombre
    terms = query_text.strip().split()
    if not terms:
        return None

    filters = []
    for term in terms:
        t_pattern = f"%{term}%"
        filters.append(
            or_(
                Fragrance.name.ilike(t_pattern),
                Fragrance.designer.ilike(t_pattern)
            )
        )

    # Coincidencia donde todos los términos de la consulta estén en el nombre o marca
    existing_by_name = db.query(Fragrance).filter(*filters).first()
    return existing_by_name


def parse_dist_json(val: Any) -> Dict:
    if pd.isna(val) or not str(val).strip():
        return {}
    try:
        return json.loads(val)
    except Exception:
        return {}

def parse_notes_list(val: Any) -> List[str]:
    if pd.isna(val) or not str(val).strip():
        return []
    return [note.strip() for note in str(val).split(',') if note.strip()]

def insert_single_fragrance_from_raw(db, raw_dict: dict) -> Fragrance:
    # 1. Separar distribuciones mediante la función centralizada
    longevity_dist, sillage_dist, gender_voted_dist, price_value_dist = separate_distributions_from_dict(raw_dict)

    # 2. Instanciar el modelo con los campos homogenizados
    new_fragrance = Fragrance(
        fragrantica_url=str(raw_dict['url']),
        bottle_image_url=str(raw_dict.get('bottle_image_url')) if pd.notna(raw_dict.get('bottle_image_url')) else None,
        name=str(raw_dict.get('name_raw', '')).strip() if pd.notna(raw_dict.get('name_raw')) else 'Sin Nombre',
        designer=str(raw_dict.get('designer_raw', '')).strip().title() if pd.notna(raw_dict.get('designer_raw')) else 'Desconocido',
        global_rating=safe_float(raw_dict.get('global_rating')),
        global_rating_count=safe_int(raw_dict.get('global_rating_count')),
        
        # Notas homogenizadas mediante el script centralizado
        top_notes=parse_notes_list_clean(raw_dict.get('top_notes_raw')),
        heart_notes=parse_notes_list_clean(raw_dict.get('heart_notes_raw')),
        base_notes=parse_notes_list_clean(raw_dict.get('base_notes_raw')),
        perfumers=parse_notes_list_clean(raw_dict.get('perfumers_raw')),
        
        # Distribuciones limpias
        seasons_dist=parse_dict(raw_dict.get('seasons_raw_dist')),
        time_of_day_dist=parse_dict(raw_dict.get('time_of_day_raw_dist')),
        longevity_dist=longevity_dist,
        sillage_dist=sillage_dist,
        price_value_dist=price_value_dist,
        gender_voted_dist=gender_voted_dist,
        
        reviews_corpus=str(raw_dict.get('reviews_text_corpus', '')) if pd.notna(raw_dict.get('reviews_text_corpus')) else ""
    )

    db.add(new_fragrance)
    db.commit()
    db.refresh(new_fragrance)
    return new_fragrance
