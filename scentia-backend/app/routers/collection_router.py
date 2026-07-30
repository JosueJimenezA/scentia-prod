from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json

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
    # Usamos alias para recibir directamente 'filterStyle', 'filterSeason' y 'filterTime' desde el frontend
    scent_type: Optional[str] = Query(None, alias="filterStyle", description="Filtro de estilo u olor: dulce, amaderado, etc."),
    season: Optional[str] = Query(None, alias="filterSeason", description="Estación: primavera, verano, otoño, invierno"),
    time_of_day: Optional[str] = Query(None, alias="filterTime", description="Horario: dia, noche"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtiene la colección del usuario con paginación y filtrado robusto mediante df_master e InferenceEngine."""
    
    # 1. Obtener la colección activa del usuario
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

    # 2. Filtrar eficientemente usando el DataFrame Maestro en memoria
    owned_ids = [str(frag.id) for frag, _ in user_fragrances]
    
    # Mapeo id -> rating de la colección para adjuntarlo a la respuesta
    ratings_map = {str(frag.id): rating for frag, rating in user_fragrances}

    df_sub = inference_engine_v2.df_master[
        inference_engine_v2.df_master["id_str"].isin(owned_ids)
    ].copy()

    # --- FILTRO 1: Estilo / Notas Olfativas / Perfil ---
    if scent_type and scent_type.strip():
        term = scent_type.strip().lower()
        # Busca coincidencia en las notas ponderadas o en la etiqueta del perfil olfativo
        mask_notes = df_sub["notes_corpus_weighted"].astype(str).str.contains(term, case=False, na=False)
        mask_label = df_sub["olfactory_profile_label"].astype(str).str.contains(term, case=False, na=False)
        df_sub = df_sub[mask_notes | mask_label]

    # --- FILTRO 2: Estación del Año ---
    if season and season.strip():
        target_season = season.strip().lower()
        # Evalúa primero sobre la mejor estación calculada por el pipeline
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

    # 4. Formateo del Output estructurado
    items = []
    for _, row in paginated_df.iterrows():
        p_id = str(row["perfume_id"])
        items.append({
            "id": p_id,
            "name": row.get("name_raw"),
            "designer": row.get("designer_raw"),
            "bottle_image_url": row.get("bottle_image_url"),
            "global_rating": float(row.get("global_rating")) if row.get("global_rating") else None,
            "user_rating": ratings_map.get(p_id),
            "olfactory_profile_label": row.get("olfactory_profile_label"),
            "best_season": row.get("best_season"),
            "day_ratio": row.get("day_ratio")
        })

    return {
        "page": page,
        "limit": limit,
        "total_items": total_items,
        "total_pages": total_pages,
        "items": items
    }