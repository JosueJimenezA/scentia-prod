import httpx
from fastapi import APIRouter

router = APIRouter(prefix="/diag", tags=["Weather Agent"])

@router.get("/debug-openmeteo")
async def debug_open_meteo():
    # Coordenadas de prueba (París)
    lat, lon = 48.8566, 2.3522
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max&timezone=auto"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            
            return {
                "status_code": response.status_code,
                "is_blocked": response.status_code in [403, 429],
                "response_headers": dict(response.headers),
                "response_body": response.json() if response.status_code == 200 else response.text
            }
    except Exception as e:
        return {
            "error_type": type(e).__name__,
            "error_detail": str(e)
        }