from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from collections import Counter
import pandas as pd

from app.database import get_db
from app.models import UserAIProfile, UserCollection
from app.services.inference_v2 import inference_engine_v2

router = APIRouter(
    prefix="/api/users",
    tags=["AI Profile"]
)


def recalculate_user_ai_profile(user_id: str, db: Session):
    """
    Analiza la colección privada ('owned') del usuario,
    construye las notas dominantes, realiza la inferencia vectorial,
    genera recomendaciones actualizadas y actualiza la base de datos.
    """
    # 1. Obtener la submuestra de la BD
    subsample = inference_engine_v2.get_user_fragrances_subsample(user_id, db)
    if not subsample:
        return None

    # 2. Conteo estadístico de notas, acordes y estaciones
    notes_counter = Counter()
    accords_counter = Counter()
    seasons_counter = Counter()
    collected_ids = []  # <--- Guardamos los IDs de las fragancias que ya tiene

    for frag, rating in subsample:
        if not frag:
            continue

        # Guardar ID para excluirlo en la recomendación
        collected_ids.append(str(frag.id))

        weight = float(rating) / 5.0 if rating else 1.0

        all_notes = (frag.top_notes or []) + (frag.heart_notes or []) + (frag.base_notes or [])
        for note in all_notes:
            notes_counter[note.strip().capitalize()] += 1 * weight

        for accord in (frag.accords or []):
            accords_counter[accord.strip().capitalize()] += 1 * weight

        if frag.seasons_dist and isinstance(frag.seasons_dist, dict):
            for season, val in frag.seasons_dist.items():
                try:
                    seasons_counter[season.capitalize()] += float(val) * weight
                except (ValueError, TypeError):
                    pass

    top_notes = [note for note, _ in notes_counter.most_common(5)]
    top_accords = [accord for accord, _ in accords_counter.most_common(5)]
    top_seasons = [season for season, _ in seasons_counter.most_common(3)]

    summary = (
        f"Perfil definido por notas de {', '.join(top_notes[:3])} "
        f"con acordes predominantes {', '.join(top_accords[:2])}."
    )

    # 3. Inferencia de ML Vectorial & Cluster
    ml_analysis = inference_engine_v2.analyze_user_vector_and_cluster(subsample)

    # 4. GENERAR RECOMENDACIONES CON EL NUEVO VECTOR
    recommendations = []
    if ml_analysis and "user_centroid" in ml_analysis:
        user_centroid = ml_analysis["user_centroid"]
        
        # Invocación a la función de inferencia
        recommendations = inference_engine_v2.generate_recommendations(
            user_centroid=user_centroid,
            collected_ids=collected_ids,
            top_k=8
        )

    # 5. Guardar / Actualizar en Base de Datos
    ai_profile = db.query(UserAIProfile).filter(UserAIProfile.user_id == user_id).first()
    if not ai_profile:
        ai_profile = UserAIProfile(user_id=user_id)
        db.add(ai_profile)

    ai_profile.dominant_notes = top_notes
    ai_profile.preferred_accords = top_accords
    ai_profile.preferred_seasons = top_seasons
    ai_profile.summary_text = summary

    # Guardar las recomendaciones en la columna correspondiente del perfil AI
    if hasattr(ai_profile, "recommended_fragrances"):
        ai_profile.recommended_fragrances = recommendations

    if hasattr(ai_profile, "predicted_label") and ml_analysis:
        ai_profile.predicted_label = ml_analysis.get("predicted_label")

    db.commit()
    db.refresh(ai_profile)
    
    return ai_profile


@router.get("/{user_id}/ai-profile")
def get_or_generate_ai_profile(user_id: str, db: Session = Depends(get_db)):
    """
    Obtiene el perfil IA del usuario, realiza inferencia de recomendaciones
    y devuelve la estructura exacta requerida por el Dashboard del Frontend.
    """
    profile = db.query(UserAIProfile).filter(UserAIProfile.user_id == user_id).first()

    if not profile:
        profile = recalculate_user_ai_profile(user_id, db)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Aún no hay suficiente información en la colección para generar un perfil olfativo."
            )

    # Inferencia en tiempo real para métricas y recomendaciones
    subsample = inference_engine_v2.get_user_fragrances_subsample(user_id, db)
    ml_analysis = inference_engine_v2.analyze_user_vector_and_cluster(subsample)

    recommendations = []
    cluster_info = {
        "label": "Firma Olfativa Personal",
        "description": "Basado en el análisis de distancias vectoriales en el espacio de notas."
    }
    metrics = {
        "total_owned": len(subsample) if subsample else 0,
        "avg_longevity_score": 0.8,
        "avg_sillage_score": 0.75
    }

    if ml_analysis:
        cluster_info["label"] = ml_analysis["predicted_label"]
        metrics = ml_analysis["metrics"]
        
        # Generar Recomendaciones Top K
        recommendations = inference_engine_v2.generate_recommendations(
            user_centroid=ml_analysis["user_centroid"],
            collected_ids=ml_analysis["collected_ids"],
            top_k=8
        )

    # Respuesta compatible al 100% con tu page.js de Next.js / React
    return {
        "status": "success",
        "user_id": str(profile.user_id),
        "dominant_notes": profile.dominant_notes or [],
        "preferred_accords": profile.preferred_accords or [],
        "preferred_seasons": profile.preferred_seasons or [],
        "summary_text": profile.summary_text,
        "last_updated": profile.updated_at if hasattr(profile, "updated_at") else None,
        "cluster_info": cluster_info,
        "metrics": metrics,
        "recommendations": recommendations
    }


@router.post("/{user_id}/ai-profile/recalculate")
def trigger_profile_recalculation(user_id: str, db: Session = Depends(get_db)):
    """Fuerza la re-evaluación del perfil y retorna la estructura de respuesta completa."""
    profile = recalculate_user_ai_profile(user_id, db)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay fragancias registradas en la colección para recalcular el perfil."
        )
    
    # Delegar la respuesta al getter principal para mantener un contrato JSON idéntico
    return get_or_generate_ai_profile(user_id=user_id, db=db)