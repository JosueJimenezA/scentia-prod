import sys
import os
import subprocess
import urllib.parse
import asyncio
import re
import pandas as pd
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from pydantic import BaseModel
from playwright.async_api import async_playwright

from app.database import get_db
from app.models import Fragrance
from app.utils import insert_single_fragrance_from_raw, check_fragrance_exists

router = APIRouter(prefix="/api/v1/fragrances", tags=["Catálogo de Perfumes"])

class ScrapeRequest(BaseModel):
    query: str


# -----------------------------------------------------------------------
# FUNCIÓN AUXILIAR DE BÚSQUEDA EN EL DOM DE FRAGRANTICA
# -----------------------------------------------------------------------
async def test_search_fragrantica_exact_dom(query_text: str) -> Optional[str]:
    """
    Navega al buscador nativo de Fragrantica mediante Playwright y extrae
    la URL exacta del primer resultado en el grid principal en < 2s.
    """
    encoded_query = urllib.parse.quote(query_text.lower())
    search_url = f"https://www.fragrantica.es/buscar/?query={encoded_query}"
    print(f"🔎 Navegando a la URL de búsqueda: {search_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            locale="es-ES"
        )
        page = await context.new_page()

        try:
            # domcontentloaded no espera analíticas en segundo plano (evita timeouts)
            await page.goto(search_url, wait_until="domcontentloaded", timeout=12000)
            
            # Selector exacto del grid principal descubierto en la inspección de DOM
            grid_selector = 'div.ais-StateResults div.grid a[href*="/perfume/"]'
            
            await page.wait_for_selector(grid_selector, timeout=7000)
            first_card = page.locator(grid_selector).first
            
            if await first_card.count() > 0:
                href = await first_card.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        href = f"https://www.fragrantica.es{href}"
                    
                    clean_url = href.replace("https://www.fragrantica.com", "https://www.fragrantica.es")
                    print(f"🎯 URL obtenida del DOM: {clean_url}")
                    await browser.close()
                    return clean_url

            await browser.close()
            return None

        except Exception as e:
            print(f"❌ Error durante la búsqueda en DOM: {e}")
            await browser.close()
            return None


# -----------------------------------------------------------------------
# ENDPOINTS DEL ROUTER
# -----------------------------------------------------------------------

async def search_fragrantica_url_playwright(query_text: str) -> Optional[str]:
    """
    Utiliza Playwright para buscar en Google de forma segura y extraer 
    el enlace directo de Fragrantica en español o inglés.
    """
    search_query = f"{query_text} site:fragrantica.es/perfume/ OR site:fragrantica.com/perfume/"
    google_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            print(f"🔎 Buscando enlace en Google para: '{query_text}'...")
            await page.goto(google_url, wait_until="domcontentloaded", timeout=15000)
            
            # Buscar selectores de enlaces de resultados en Google
            links = await page.locator('a[href*="fragrantica."]').all()
            
            for link_locator in links:
                href = await link_locator.get_attribute("href")
                if href and ("/perfume/" in href or "/perfumes/" in href):
                    # Limpiar parámetros de Google (/url?q=...)
                    if "/url?q=" in href:
                        href = href.split("/url?q=")[1].split("&")[0]
                    
                    # Convertir dominio a fragrantica.es si viene en .com
                    clean_url = href.replace("https://www.fragrantica.com", "https://www.fragrantica.es")
                    print(f"🎯 URL de Fragrantica encontrada: {clean_url}")
                    await browser.close()
                    return clean_url

        except Exception as e:
            print(f"❌ Error al buscar enlace en Google con Playwright: {e}")
        finally:
            if not page.is_closed():
                await page.close()
            await browser.close()

    return None


@router.get("/search")
def search_fragrances(
    q: Optional[str] = Query(None, description="Término de búsqueda"),
    limit: int = 10,
    db: Session = Depends(get_db)
):
    if not q or not q.strip():
        return {"found": True, "count": 0, "items": []}

    search_term = f"%{q.strip()}%"
    results = db.query(Fragrance).filter(
        or_(
            Fragrance.name.ilike(search_term),
            Fragrance.designer.ilike(search_term),
            Fragrance.top_notes.any(search_term),
            Fragrance.heart_notes.any(search_term),
            Fragrance.base_notes.any(search_term)
        )
    ).limit(limit).all()

    if len(results) > 0:
        return {
            "found": True,
            "is_scraped": False,
            "count": len(results),
            "items": results
        }
    
    return {
        "found": False,
        "query": q,
        "message": f"No se encontraron resultados para '{q}' en la base local.",
        "items": []
    }


@router.post("/scrape-and-add")
async def scrape_and_add_fragrance(
    payload: ScrapeRequest,
    db: Session = Depends(get_db)
):
    query = payload.query.strip()
    
    # PASO 1: Validación previa por texto en BD local (para ahorrar peticiones web)
    existing_by_text = check_fragrance_exists(db, query_text=query)
    if existing_by_text:
        return {
            "found": True,
            "is_scraped": False,
            "message": "La fragancia ya existía en el catálogo local.",
            "items": [existing_by_text]
        }

    # PASO 2: Navegar con Playwright al buscador de Fragrantica para obtener la URL del DOM
    target_url = await test_search_fragrantica_exact_dom(query)
    if not target_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ningún resultado en Fragrantica para '{query}'."
        )

    # PASO 3: Validación por URL exacta obtenida
    existing_by_url = db.query(Fragrance).filter(Fragrance.fragrantica_url == target_url).first()
    if existing_by_url:
        return {
            "found": True,
            "is_scraped": False,
            "message": "La fragancia ya existía en la base de datos.",
            "items": [existing_by_url]
        }

    # PASO 4: Si no existe la URL, extraer con scraper_busqueda.py e insertar

    ROUTER_DIR = os.path.dirname(os.path.abspath(__file__)) # .../scentia-backend/app/routers
    BACKEND_DIR = os.path.abspath(os.path.join(ROUTER_DIR, "../..")) # .../scentia-backend
    PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, "..")) # .../raíz_proyecto

    scraper_path = os.path.join(BACKEND_DIR, "scraper", "scraper_busqueda.py")
    csv_path = os.path.join(PROJECT_ROOT, "data", "fragrantica_data_from_scraper.csv")

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, scraper_path, "--single-url", target_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=BACKEND_DIR # Ejecuta el subproceso desde scentia-backend
        )
        
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=40.0)

        if proc.returncode != 0:
            print(f"❌ Error en subproceso del scraper:\n{stderr.decode()}")
            raise HTTPException(status_code=500, detail="Fallo al ejecutar el proceso de extracción.")

        if not os.path.exists(csv_path):
            raise HTTPException(status_code=500, detail="El archivo CSV de salida no existe.")

        df = pd.read_csv(csv_path, sep='|')
        matching_rows = df[df['url'] == target_url]
        
        if matching_rows.empty:
            raise HTTPException(status_code=500, detail="El scraper finalizó pero no guardó la URL esperada.")

        last_row_dict = matching_rows.iloc[-1].to_dict()
        new_fragrance = insert_single_fragrance_from_raw(db, last_row_dict)

        return {
            "found": True,
            "is_scraped": True,
            "message": "¡Perfume extraído e importado exitosamente!",
            "items": [new_fragrance]
        }

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="El tiempo de respuesta del scraper excedió el límite.")