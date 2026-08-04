from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import numpy as np
import pandas as pd
from app.database import get_db
from app.models import User, Fragrance, UserCollection
from app.auth import get_current_user
from app.services.inference_v2 import inference_engine_v2

router = APIRouter(prefix="/api/v1/collection", tags=["Colección de Usuario"])

@router.get("/ids")
def get_user_collection_ids(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Devuelve la lista de IDs de fragancias en la colección del usuario para actualizar botones en UI."""
    items = db.query(UserCollection.fragrance_id).filter(UserCollection.user_id == current_user.id).all()
    return [item[0] for item in items]


@router.post("/toggle/{fragrance_id}")
def toggle_collection_item(
    fragrance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Agrega o remueve un perfume de la colección del usuario."""
    existing = db.query(UserCollection).filter(
        UserCollection.user_id == current_user.id,
        UserCollection.fragrance_id == fragrance_id
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"added": False, "message": "Removido de tu colección."}
    else:
        new_item = UserCollection(user_id=current_user.id, fragrance_id=fragrance_id)
        db.add(new_item)
        db.commit()
        return {"added": True, "message": "¡Agregado a tu colección!"}


@router.get("/")
def get_user_collection(
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=50),
    scent_type: Optional[str] = Query(None, alias="filterStyle", description="Filtro de estilo u olor: dulce, amaderado, etc."),
    season: Optional[str] = Query(None, alias="filterSeason", description="Estación: primavera, verano, otoño, invierno"),
    time_of_day: Optional[str] = Query(None, alias="filterTime", description="Horario: dia, noche"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtiene la colección del usuario combinando el filtrado analítico del DataFrame con los datos de BD SQL."""
    
    # 1. Obtener la colección activa del usuario desde SQL
    user_fragrances = (
        db.query(Fragrance, UserCollection.user_rating)
        .join(UserCollection, Fragrance.id == UserCollection.fragrance_id)
        .filter(UserCollection.user_id == current_user.id)
        .all()
    )

    if not user_fragrances:
        return {
            "page": page,
            "limit": limit,
            "total_items": 0,
            "total_pages": 1,
            "items": []
        }

    # Crear mapeos rápidos usando el objeto Fragrance de SQL
    owned_ids = [str(frag.id) for frag, _ in user_fragrances]
    ratings_map = {str(frag.id): rating for frag, rating in user_fragrances}
    frag_db_map = {str(frag.id): frag for frag, _ in user_fragrances}

    # 2. Filtrar sobre el DataFrame Maestro
    df_master = inference_engine_v2.df_master.copy()
    df_master["id_str"] = df_master["id_str"].astype(str)

    df_sub = df_master[df_master["id_str"].isin(owned_ids)].copy()

    # --- FILTRO 1: Estilo / Notas Olfativas / Perfil ---
    if scent_type and scent_type.strip():
        term = scent_type.strip().lower()
        mask_notes = df_sub["notes_corpus_weighted"].astype(str).str.contains(term, case=False, na=False)
        mask_label = df_sub["olfactory_profile_label"].astype(str).str.contains(term, case=False, na=False)
        df_sub = df_sub[mask_notes | mask_label]

    # --- FILTRO 2: Estación del Año ---
    if season and season.strip():
        target_season = season.strip().lower()
        if "best_season" in df_sub.columns:
            df_sub = df_sub[df_sub["best_season"].astype(str).str.lower() == target_season]

    # --- FILTRO 3: Momento del Día (Día vs Noche) ---
    if time_of_day and time_of_day.strip():
        tod_term = time_of_day.strip().lower()
        if "day_ratio" in df_sub.columns:
            if tod_term in ["dia", "día", "day"]:
                df_sub = df_sub[df_sub["day_ratio"] >= 0.5]
            elif tod_term in ["noche", "night"]:
                df_sub = df_sub[df_sub["day_ratio"] < 0.5]

    # 3. Paginación
    total_items = len(df_sub)
    total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1
    offset = (page - 1) * limit
    
    paginated_df = df_sub.iloc[offset : offset + limit]

    def ensure_list_of_strings(val):
        """Asegura devolver siempre una lista de strings sin romper cuando val es un numpy array o lista."""
        # 1. Si es None explícito
        if val is None:
            return []

        # 2. Si ya es una lista, tupla o numpy array, iteramos directo sobre sus elementos
        if isinstance(val, (list, tuple, np.ndarray)):
            return [str(n).strip() for n in val if n is not None and pd.notna(n) and str(n).strip()]

        # 3. Si es un escalar de Pandas que evalúa a NA/NaN
        if pd.isna(val):
            return []

        # 4. Si es string
        if isinstance(val, str) and val.strip():
            v_str = val.strip()
            # Caso en que sea una lista serializada como string '[a, b]'
            if v_str.startswith("[") and v_str.endswith("]"):
                try:
                    parsed = json.loads(v_str)
                    if isinstance(parsed, list):
                        return [str(n).strip() for n in parsed if n]
                except Exception:
                    pass
                try:
                    parsed = ast.literal_eval(v_str)
                    if isinstance(parsed, list):
                        return [str(n).strip() for n in parsed if n]
                except Exception:
                    pass
            # Texto plano separado por comas
            return [n.strip() for n in v_str.split(",") if n.strip()]

        return []

    # 4. Formateo del Output estructurado
    items = []
    for _, row in paginated_df.iterrows():
        p_id = str(row["id_str"])
        frag_db = frag_db_map.get(p_id)

        # Se leen las notas directamente del objeto SQL (Fragrance)
        top_val = frag_db.top_notes if frag_db else []
        heart_val = frag_db.heart_notes if frag_db else []
        base_val = frag_db.base_notes if frag_db else []

        items.append({
            "id": p_id,
            "name": frag_db.name if frag_db else row.get("name_raw"),
            "designer": frag_db.designer if frag_db else row.get("designer_raw"),
            "bottle_image_url": row.get("bottle_image_url") or (getattr(frag_db, "image_url", None) if frag_db else None),
            "global_rating": float(row.get("global_rating")) if row.get("global_rating") else None,
            "user_rating": ratings_map.get(p_id),
            "olfactory_profile_label": row.get("olfactory_profile_label"),
            "best_season": row.get("best_season"),
            "day_ratio": row.get("day_ratio"),
            
            # Notas inyectadas desde SQL en el formato exacto que espera React
            "top_notes": ensure_list_of_strings(top_val),
            "heart_notes": ensure_list_of_strings(heart_val),
            "base_notes": ensure_list_of_strings(base_val)
        })

    return {
        "page": page,
        "limit": limit,
        "total_items": total_items,
        "total_pages": total_pages,
        "items": items
    }