from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.services.weather_agent import parse_user_query
from app.services.open_meteo import get_coordinates, get_weather_forecast
from app.services.inference_service import inference_engine  # Instancia Singleton de InferenceEngine
from app.database import get_db
from app.models import UserAIProfile, UserCollection  # Modelos SQLAlchemy
from app.auth import get_current_user  # Inyección opcional de usuario si existe token

router = APIRouter(prefix="/weather", tags=["Weather Agent"])


class QueryRequest(BaseModel):
    user_input: str


@router.post("/recommendation-search")
async def analyze_and_get_weather(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    current_user: Optional[any] = Depends(get_current_user)
):
    # 1. Extracción e inspección con el LLM + Guardrails
    parsed_intent = await parse_user_query(payload.user_input)

    if not parsed_intent.valid_query or not parsed_intent.location:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Consulta no válida o rechazada por seguridad: {parsed_intent.reasoning}"
        )

    try:
        # 2. Geocodificación (Obtener Lat/Lon)
        coords = await get_coordinates(parsed_intent.location)

        # 3. Consultar Open-Meteo con las coordenadas y fecha extraída
        weather = await get_weather_forecast(
            lat=coords["latitude"],
            lon=coords["longitude"],
            target_date=parsed_intent.target_date
        )

        target_forecast = weather["target_day_forecast"]

        # 4. Obtener perfil olfativo (centroide) y colección del usuario si está autenticado
        user_centroid = None
        collected_ids = []

        if current_user:
            # Obtener el perfil olfativo vectorial
            profile = db.query(UserAIProfile).filter(UserAIProfile.user_id == current_user.id).first()
            if profile and hasattr(profile, "user_centroid"):
                user_centroid = profile.user_centroid

            # Obtener IDs de la colección privada para excluirlos
            user_fragrances = db.query(UserCollection.fragrance_id).filter(UserCollection.user_id == current_user.id).all()
            collected_ids = [f.fragrance_id for f in user_fragrances]

        # 5. Inferencia vectorial combinando clima + perfil del usuario
        clustering_alternatives = inference_engine.get_weather_based_recommendations(
            weather_forecast=target_forecast,
            user_centroid=user_centroid,
            collected_ids=collected_ids,
            top_k=6
        )

        return {
            "success": True,
            "parsed_intent": parsed_intent,
            "location": coords,
            "forecast": target_forecast,
            "clustering_alternatives": clustering_alternatives
        }

    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el servidor: {str(e)}")