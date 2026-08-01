# scentia-backend/app/services/weather_agent.py
import os
import json
from datetime import datetime
from pydantic import BaseModel, Field
from openai import AsyncOpenAI, OpenAIError, AuthenticationError
from app.prompts.weather_prompts import SYSTEM_WEATHER_GUARDRAIL

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Modelos auxiliares opcionales para tipar los nuevos campos del JSON
class TimeFrame(BaseModel):
    target_date: str | None = Field(default=None, description="Fecha objetivo YYYY-MM-DD.")
    target_time: str | None = Field(default=None, description="Hora objetivo HH:MM:SS.")
    relative_offset_minutes: int | None = Field(default=None, description="Desfase en minutos desde el momento actual.")
    is_immediate: bool = Field(default=False, description="True si requiere clima actual / ahora.")


class ExtractedWeatherIntent(BaseModel):
    # --- ATRIBUTOS ORIGINALES (NO SE MODIFICAN NI ELIMINAN) ---
    valid_query: bool = Field(description="True si la entrada del usuario es una consulta válida de viaje/destino.")
    location: str | None = Field(default=None, description="Lugar o ciudad sobre la que se requiere el clima.")
    target_date: str | None = Field(default=None, description="Fecha objetivo en formato YYYY-MM-DD.")
    reasoning: str = Field(description="Explicación breve de la decisión.")

    # --- NUEVOS ATRIBUTOS OPCIONALES (RETROCOMPATIBLES) ---
    query_type: str | None = Field(default=None, description="Tipo de consulta (current_location, departure_soon, etc.)")
    origin_location: str | None = Field(default=None, description="Ciudad de origen si el usuario va a viajar.")
    time_frame: TimeFrame | None = Field(default=None, description="Información detallada del tiempo/hora.")
    inferred_user_needs: list[str] = Field(default_factory=list, description="Etiquetas de necesidades inferidas.")


async def parse_user_query(user_input: str) -> ExtractedWeatherIntent:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("La API Key de OpenAI no está configurada en las variables de entorno (.env).")

    # Inyectamos la fecha y HORA actual completa de referencia para calcular desfases
    current_now_iso = datetime.now().isoformat()
    system_prompt = SYSTEM_WEATHER_GUARDRAIL.format(
        current_datetime=datetime.now().isoformat()
    )

    clean_input = user_input.replace("<", "").replace(">", "")
    prompt_user = f"Analiza la siguiente entrada y responde con el objeto json requerido:\n<user_input>{clean_input}</user_input>"

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_user}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            timeout=10.0
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        # RETROCOMPATIBILIDAD CRÍTICA:
        # El nuevo prompt devuelve 'target_date' anidado dentro de 'time_frame'.
        # Si el nivel superior no lo trae, extraemos la fecha de 'time_frame' para no romper
        # el atributo principal 'target_date' que usan los otros componentes.
        if "target_date" not in data or data["target_date"] is None:
            if "time_frame" in data and isinstance(data["time_frame"], dict):
                data["target_date"] = data["time_frame"].get("target_date")

        return ExtractedWeatherIntent(**data)

    except AuthenticationError:
        raise ValueError("La API Key de OpenAI es inválida o ha expirado.")
    except OpenAIError as e:
        raise ValueError(f"Error al comunicar con el servicio de Inteligencia Artificial: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error procesando la solicitud del agente: {str(e)}")