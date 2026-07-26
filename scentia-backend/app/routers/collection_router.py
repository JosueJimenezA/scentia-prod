from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from app.database import get_db
from app.models import User, Fragrance, UserCollection
from app.auth import get_current_user

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
    scent_type: Optional[str] = Query(None, description="Filtro de estilo: dulce, amaderado, limpio, etc."),
    season: Optional[str] = Query(None, description="Estación: primavera, verano, otoño, invierno"),
    time_of_day: Optional[str] = Query(None, description="Horario: dia, noche"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtiene la colección del usuario con paginación de 15 en 15 y filtros dinámicos."""
    query = db.query(Fragrance).join(UserCollection).filter(UserCollection.user_id == current_user.id)

    # Filtrado por Estilo / Notas
    if scent_type and scent_type.strip():
        st = f"%{scent_type.strip()}%"
        query = query.filter(
            (Fragrance.top_notes.any(st)) | 
            (Fragrance.heart_notes.any(st)) | 
            (Fragrance.base_notes.any(st))
        )

    # Obtener todos los candidatos para aplicar filtros sobre JSON de distribuciones si es necesario
    all_items = query.all()
    filtered_items = []

    for item in all_items:
        keep = True
        
        # Filtro por Estación (analizando el JSON seasons_dist extraído del scraper)
        if season and item.seasons_dist:
            # Convierte llaves a minúsculas
            s_dist = {str(k).lower(): str(v).lower() for k, v in item.seasons_dist.items()}
            if season.lower() not in s_dist and not any(season.lower() in k for k in s_dist.keys()):
                keep = False

        # Filtro por Día/Noche
        if time_of_day and item.time_of_day_dist:
            t_dist = {str(k).lower(): str(v).lower() for k, v in item.time_of_day_dist.items()}
            if time_of_day.lower() not in t_dist and not any(time_of_day.lower() in k for k in t_dist.keys()):
                keep = False

        if keep:
            filtered_items.append(item)

    # Paginación manual de 15 en 15
    total_items = len(filtered_items)
    total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1
    offset = (page - 1) * limit
    paginated_items = filtered_items[offset : offset + limit]

    return {
        "page": page,
        "limit": limit,
        "total_items": total_items,
        "total_pages": total_pages,
        "items": paginated_items
    }