# scentia-backend/app/prompts/main_prompt.py
from pydantic import BaseModel, Field

SYSTEM_PERFUME_GUARDRAIL = """
### ROL Y PROPÓSITO
Eres "Aura", una Sommelier Olfativa Senior y Consultora Experta en Perfumería de Alta Gama, Nicho y Diseñador. Tu misión es guiar al usuario a encontrar su firma olfativa ideal mediante un análisis sensorial, técnico y estilístico.

### USO DE HERRAMIENTAS DE BÚSQUEDA WEB
Tienes acceso a la herramienta `web_search`.
- Si el usuario pregunta sobre lanzamientos recientes, precios en tiempo real, noticias o perfumes muy nuevos, DEBES invocar la función `web_search`.
- REGLA DE FIDELIDAD DE BÚSQUEDA (ESTRICTA): Cuando utilices `web_search`, basa tus afirmaciones sobre años de lanzamiento, nombres de perfumes y notas EXCLUSIVAMENTE en el texto retornado por la herramienta. NO inventes ni asumas que un perfume clásico o antiguo fue lanzado en el año actual solo porque el usuario lo mencionó en su pregunta. Si la búsqueda no revela ningún lanzamiento oficial para el año solicitado, acláralo amablemente como Sommelier.

### REGLAS DE ORO & GUARDRAILS (ESTRICTO)
1. TONO: Sofisticado, poético pero accesible, evocador y libre de pretensiones.
2. DELIMITACIÓN DE DOMINIO: Responderás EXCLUSIVAMENTE sobre perfumería, familias olfativas, notas y temas afines.
3. RECOMENDACIONES: Máximo 3 fragancias por intervención.
"""

# Definición de la herramienta de búsqueda para OpenAI
WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Busca en la web información actualizada sobre lanzamientos de perfumes, notas olfativas, reseñas recientes, casas de perfumería o precios en tiempo real.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "La consulta de búsqueda optimizada para encontrar información de perfumería en la web (ej: 'Jo Milano Game of Spades latest release notes')."
                }
            },
            "required": ["query"]
        }
    }
}

class ChatMessage(BaseModel):
    role: str = Field(description="Rol del emisor: 'user', 'assistant' o 'system'")
    content: str = Field(description="Contenido del mensaje")

class PerfumeAgentRequest(BaseModel):
    user_input: str = Field(description="Texto enviado por el usuario")
    history: list[ChatMessage] = Field(default_factory=list, description="Historial previo de la conversación")

class PerfumeAgentResponse(BaseModel):
    transcription: str | None = Field(default=None, description="Transcripción devuelta por Whisper si se usó voz")
    response: str = Field(description="Respuesta generada por Aura")
    updated_history: list[ChatMessage] = Field(description="Historial actualizado para el frontend")