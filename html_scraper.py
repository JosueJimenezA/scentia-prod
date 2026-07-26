import asyncio
import random
import os
import shutil
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
]

CHECKPOINT_FILE = "fragrantica_TEST_checkpoint.csv"
USER_DATA_DIR = "./playwright_user_data"  # Directorio para persistir la sesión humana

async def scrape_fragrantica_perfume(context, url):
    """Procesa una URL usando el contexto persistente."""
    page = await context.new_page()
    
    try:
        print(f"🔎 Navegando en local a: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Damos unos segundos para que cargue todo el contenido dinámico
        await asyncio.sleep(5) 
        
        # Vaciamos el HTML real en un archivo local para inspeccionarlo
        html = await page.content()
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("💾 Archivo 'debug_page.html' guardado. ¡Revísalo para buscar las etiquetas!")

    except Exception as e:
        print(f"❌ Error durante el test de {url}: {e}")
        return None
    finally:
        await page.close()

async def main():
    urls_objetivo = [
        "https://www.fragrantica.com/perfume/Creed/Aventus-9828.html"
    ]
    
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("🗑️ Archivo de prueba anterior eliminado.")

    async with async_playwright() as p:
        print("🚀 Iniciando Navegador con Contexto Persistente Orgánico...")
        
        # Lanzamos usando un directorio de datos persistente en lugar de una sesión temporal vacía
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/Mexico_City",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox"
            ]
        )
        
        # Evasión de bandera nativa en ventanas nuevas
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)
        
        print("🚀 Iniciando Test Corto...")
        
        for url in urls_objetivo:
            data = await scrape_fragrantica_perfume(context, url)
            
            if data:
                df_row = pd.DataFrame([data])
                file_exists = os.path.exists(CHECKPOINT_FILE)
                df_row.to_csv(
                    CHECKPOINT_FILE, 
                    sep="|", 
                    index=False, 
                    mode='a', 
                    header=not file_exists, 
                    encoding="utf-8"
                )
        
        await context.close()
        
        # Opcional: Limpiar el perfil temporal generado al terminar si deseas pruebas limpias consecutivas
        if os.path.exists(USER_DATA_DIR):
            shutil.rmtree(USER_DATA_DIR)
        
    print(f"\n📊 Test finalizado. Revisa '{CHECKPOINT_FILE}'.")

if __name__ == "__main__":
    asyncio.run(main())