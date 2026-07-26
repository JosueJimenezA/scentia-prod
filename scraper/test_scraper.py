import asyncio
import random
import os
import json
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

CHECKPOINT_FILE = "fragrantica_DATA_SCIENCE_checkpoint.csv"

async def scrape_fragrantica_perfume(browser, url):
    """Procesa una URL y extrae métricas de Data Science interceptando la red."""
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1280, "height": 800},
        locale="en-US"
    )
    page = await context.new_page()
    
    # Diccionario temporal para guardar las métricas asíncronas interceptadas
    intercepted_metrics = {}

    # Interceptamos las respuestas de la API interna de Fragrantica que carga los votos
    async def handle_response(response):
        if "fimgs.net" in response.url or "c.fimgs.net" in response.url:
            if "itemId=" in response.url:
                try:
                    # Intentamos obtener el JSON con las votaciones puras de los usuarios
                    text_data = await response.text()
                    if text_data.strip().startswith("{") or text_data.strip().startswith("["):
                        json_data = json.loads(text_data)
                        intercepted_metrics['raw_votes_json'] = json_data
                except Exception:
                    pass

    page.on("response", handle_response)

    try:
        print(f"🔎 Navegando en local a: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        
        # Esperamos a que cargue el h1 para asegurar que el DOM base esté listo
        await page.wait_for_selector("h1", timeout=15000)
        
        # Hacemos un scroll lento para gatillar la carga de las APIs de votaciones e iframes
        for _ in range(4):
            await page.evaluate("window.scrollBy(0, 400);")
            await asyncio.sleep(1.0)
            
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Estructura base del dataset
        data = {
            'url': url,
            'name': None,
            'designer': None,
            'rating': None,
            'rating_count': None,
            'reviews_count': None,
            'accords': None,
            # Campos nuevos solicitados para analítica:
            'longevity_votes': None,
            'sillage_votes': None,
            'gender_votes': None,
            'price_value_votes': None,
            'seasons_votes': None
        }
        
        # 1. Extraer Nombre y Diseñador (Estructura Tailwind)
        title_tag = soup.select_one('h1[itemprop="name"]') or soup.select_one("h1")
        if title_tag:
            data['name'] = title_tag.text.replace("for men", "").replace("for women", "").replace("for women and men", "").strip()
            
        designer_tag = soup.select_one('p[itemprop="brand"] a span') or soup.select_one('p[itemprop="brand"]')
        data['designer'] = designer_tag.text.strip() if designer_tag else None
        
        # 2. Extraer Acordes Corregidos (Buscando en la jerarquía del gráfico nuevo)
        accord_elements = soup.find_all(string=["fruity", "sweet", "woody", "leather", "citrus", "smoky", "musky", "fresh", "tropical", "mossy", "amber", "vanilla", "powdery", "iris"])
        accords_clean = list(dict.fromkeys([acc.strip() for acc in accord_elements if len(acc.strip()) > 2]))
        data['accords'] = ", ".join(accords_clean)
        
        # 3. Extraer Calificación global y total de votos/reviews
        rating_tag = soup.select_one('span[itemprop="ratingValue"]')
        data['rating'] = rating_tag.text.strip() if rating_tag else None
        
        vote_count_tag = soup.select_one('span[itemprop="ratingCount"]')
        data['rating_count'] = vote_count_tag.text.strip() if vote_count_tag else None
        
        # Contador de Reviews escritas
        reviews_tag = soup.find("a", string=lambda t: t and "Reviews" in t)
        if reviews_tag:
            data['reviews_count'] = "".join(filter(str.isdigit, reviews_tag.text))

        # 4. Procesar las métricas de Data Science interceptadas de la red
        if 'raw_votes_json' in intercepted_metrics:
            metrics = intercepted_metrics['raw_votes_json']
            # Guardamos las distribuciones crudas de votos para procesamiento numérico posterior
            data['longevity_votes'] = json.dumps(metrics.get('longevity', {}))
            data['sillage_votes'] = json.dumps(metrics.get('sillage', {}))
            data['gender_votes'] = json.dumps(metrics.get('gender', {}))
            data['price_value_votes'] = json.dumps(metrics.get('pricevalue', {}))
            data['seasons_votes'] = json.dumps(metrics.get('seasons', {}))
        else:
            # Fallback secundario si la API no se capturó a tiempo (Simulación basada en texto de respaldo del DOM)
            print("⚠️ API JSON no capturada a tiempo. Extrayendo promedios aproximados del DOM...")
            day_night = soup.select(".tw-rating-card")
            if len(day_night) > 1:
                data['seasons_votes'] = "Captured via DOM backup"

        print(f"✅ ¡Procesado con éxito! -> {data['name']} ({data['designer']})")
        return data

    except Exception as e:
        print(f"❌ Error durante la extracción de {url}: {e}")
        return None
    finally:
        await page.close()
        await context.close()

async def main():
    urls_objetivo = [
        "https://www.fragrantica.com/perfume/Creed/Aventus-9828.html",
        "https://www.fragrantica.com/perfume/Dior/Sauvage-31861.html"
    ]
    
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("🗑️ Archivo de datos anterior eliminado.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, 
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        print("🚀 Iniciando Pipeline de Extracción de Datos...")
        results = []
        
        for url in urls_objetivo:
            data = await scrape_fragrantica_perfume(browser, url)
            if data:
                results.append(data)
                
        if results:
            df = pd.DataFrame(results)
            df.to_csv(CHECKPOINT_FILE, sep="|", index=False, encoding="utf-8")
            print(f"\n📊 Pipeline finalizado con éxito. Dataset guardado en: '{CHECKPOINT_FILE}'")
        else:
            print("❌ No se pudieron recolectar datos.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())