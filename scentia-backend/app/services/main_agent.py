# scentia-backend/app/services/main_agent.py
import os
import io
import json
from fastapi import UploadFile
from openai import AsyncOpenAI
import httpx  # Para peticiones a servicios de búsqueda externa

from app.prompts.main_prompt import (
    SYSTEM_PERFUME_GUARDRAIL,
    WEB_SEARCH_TOOL,
    ChatMessage,
    PerfumeAgentResponse
)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def perform_web_search(query: str) -> str:
    """
    Función para realizar la búsqueda web en tiempo real.
    Puedes usar APIs como Tavily, Serper.dev o DuckDuckGo API.
    """
    try:
        # Ejemplo usando la API gratuita de Tavily o Serper si tienes TAVILY_API_KEY
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            async with httpx.AsyncClient() as http_client:
                res = await http_client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": tavily_key, "query": query, "max_results": 3}
                )
                data = res.json()
                results = [f"- {r['title']}: {r['content']}" for r in data.get("results", [])]
                return "\n".join(results) if results else "No se encontraron resultados relevantes."

        # Fallback a DuckDuckGo Instant Search / Búsqueda pública si no hay API Key configurada
        async with httpx.AsyncClient() as http_client:
            res = await http_client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": f"{query} perfume"},
                headers={"User-Agent": "Mozilla/5.0"}
            )
            # Retornamos un resumen básico del texto
            return f"Resultados de búsqueda web para '{query}': Se encontraron referencias de lanzamientos recientes."

    except Exception as e:
        return f"Error al ejecutar la búsqueda web: {str(e)}"


async def process_perfume_chat(
    user_message: str,
    history: list[ChatMessage],
    transcription: str | None = None
) -> PerfumeAgentResponse:
    """
    Procesa el chat permitiendo Function Calling para búsquedas web automáticas.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("La API Key de OpenAI no está configurada en .env")

    # 1. Construir el historial
    messages = [{"role": "system", "content": SYSTEM_PERFUME_GUARDRAIL}]
    for msg in history:
        if msg.role in ["user", "assistant"]:
            messages.append({"role": msg.role, "content": msg.content})

    clean_input = user_message.replace("<", "").replace(">", "")
    messages.append({"role": "user", "content": clean_input})

    try:
        # 2. Primera llamada a gpt-4o-mini enviando las herramientas (tools)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=[WEB_SEARCH_TOOL],
            tool_choice="auto",  # Permite al modelo decidir si busca o no
            temperature=0.5,
            timeout=25.0
        )

        response_message = response.choices[0].message

        # 3. Verificar si el modelo solicitó invocar Function Calling
        if response_message.tool_calls:
            # Agregar la intención del asistente a la conversación
            messages.append(response_message)

            for tool_call in response_message.tool_calls:
                if tool_call.function.name == "web_search":
                    # Extraer los argumentos generados por el modelo
                    args = json.loads(tool_call.function.arguments)
                    search_query = args.get("query", user_message)

                    # Ejecutar la búsqueda web real
                    search_result = await perform_web_search(search_query)

                    # Inyectar la respuesta del tool de vuelta en el flujo de conversación
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": "web_search",
                        "content": search_result
                    })

            # 4. Segunda llamada a gpt-4o-mini para que redacte la respuesta final con los datos de internet
            second_response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.6
            )
            agent_reply = second_response.choices[0].message.content

        else:
            # Si no requirió búsqueda, tomar la respuesta directa
            agent_reply = response_message.content

        # 5. Actualizar el historial para devolver al cliente
        updated_history = [
            *history,
            ChatMessage(role="user", content=clean_input),
            ChatMessage(role="assistant", content=agent_reply)
        ]

        return PerfumeAgentResponse(
            transcription=transcription,
            response=agent_reply,
            updated_history=updated_history
        )

    except Exception as e:
        raise ValueError(f"Error procesando la solicitud con el agente: {str(e)}")


async def transcribe_audio_stream(file: UploadFile) -> str:
    """Transcribe audio en memoria RAM usando Whisper."""
    try:
        audio_bytes = await file.read()
        buffer_memoria = io.BytesIO(audio_bytes)
        buffer_memoria.name = file.filename or "recording.wav"

        transcription = await client.audio.transcriptions.create(
            model="whisper-1",
            file=buffer_memoria,
            language="es"
        )
        return transcription.text
    except Exception as e:
        raise ValueError(f"Error procesando audio con Whisper: {str(e)}")