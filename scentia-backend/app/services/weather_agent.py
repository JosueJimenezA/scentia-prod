# scentia-backend/app/services/weather_agent.py
import os
import json
from pydantic import BaseModel, Field
from openai import AsyncOpenAI, OpenAIError, AuthenticationError
from app.prompts.weather_prompts import SYSTEM_WEATHER_GUARDRAIL

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class ExtractedWeatherIntent(BaseModel):
    valid_query: bool = Field(description="True si la entrada del usuario es una consulta válida de viaje/destino.")
    location: str | None = Field(default=None, description="Lugar o ciudad mencionada.")
    target_date: str | None = Field(default=None, description="Fecha objetivo en formato YYYY-MM-DD.")
    reasoning: str = Field(description="Explicación breve de la decisión.")

async def parse_user_query(user_input: str) -> ExtractedWeatherIntent:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("La API Key de OpenAI no está configurada en las variables de entorno (.env).")

    clean_input = user_input.replace("<", "").replace(">", "")
    prompt_user = f"Analiza la siguiente entrada y responde con el objeto json requerido:\n<user_input>{clean_input}</user_input>"

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_WEATHER_GUARDRAIL},
                {"role": "user", "content": prompt_user}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            timeout=10.0
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        return ExtractedWeatherIntent(**data)

    except AuthenticationError:
        raise ValueError("La API Key de OpenAI es inválida o ha expirado.")
    except OpenAIError as e:
        raise ValueError(f"Error al comunicar con el servicio de Inteligencia Artificial: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error procesando la solicitud del agente: {str(e)}")