import json
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.prompts.main_prompt import PerfumeAgentRequest, PerfumeAgentResponse, ChatMessage
from app.services.main_agent import transcribe_audio_stream, process_perfume_chat

router = APIRouter(prefix="/perfumes", tags=["Perfume Agent"])

@router.post("/chat/text", response_model=PerfumeAgentResponse)
async def chat_text(payload: PerfumeAgentRequest):
    if not payload.user_input.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    try:
        return await process_perfume_chat(
            user_message=payload.user_input,
            history=payload.history
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/chat/audio", response_model=PerfumeAgentResponse)
async def chat_audio(
    file: UploadFile = File(...),
    history_json: str = Form(default="[]")
):
    try:
        history_raw = json.loads(history_json)
        history = [ChatMessage(**msg) for msg in history_raw]

        # 1. Transcribir audio directamente en RAM
        transcription = await transcribe_audio_stream(file)

        if not transcription.strip():
            raise HTTPException(status_code=400, detail="No se pudo interpretar el audio.")

        # 2. Procesar con Function Calling
        return await process_perfume_chat(
            user_message=transcription,
            history=history,
            transcription=transcription
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))