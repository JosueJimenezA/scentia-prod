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

CHECKPOINT_FILE = "fragrantica_raw_v3.csv"

async def scrape_fragrantica_perfume_raw(browser, url):
    """Extrae absolutamente todos los datos disponibles en formato crudo."""
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1280, "height": 800},
        locale="en-US"
    )
    page = await context.new_page()
    
    # Contenedor para almacenar respuestas de red interceptadas
    network_data = {}

    # Interceptor de llamadas de red (captura los JSON de votaciones de fimgs)
    async def handle_response(response):
        if "fimgs.net" in response.url or "c.fimgs.net" in response.url:
            if "itemId=" in response.url:
                try:
                    text_data = await response.text()
                    if text_data.strip().startswith("{") or text_data.strip().startswith("["):
                        network_data['api_json'] = json.loads(text_data)
                except Exception:
                    pass

    page.on("response", handle_response)

    try:
        print(f"🔎 Navegando a: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_selector("h1", timeout=15000)
        
        # Scroll controlado para asegurar la ejecución de requests asíncronos e iframes
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 500);")
            await asyncio.sleep(1.2)
            
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Inicializamos el diccionario con todas las variables crudas imaginables
        raw_record = {
            'url': url,
            'name': None,
            'designer': None,
            'declared_gender': None,
            'rating_value': None,
            'rating_count': None,
            'accords_raw': None,
            'top_notes': None,
            'heart_notes': None,
            'base_notes': None,
            # JSONs de distribución cruda para tu ingeniería de variables:
            'vibe_reactions_json': None,      # love, like, ok, dislike, hate
            'longevity_json': None,           # very weak -> eternal
            'sillage_json': None,             # intimate -> enormous
            'seasons_json': None,             # winter, spring, summer, fall
            'time_of_day_json': None,         # day, night
            'price_value_json': None,         # value ratings
            'gender_clinal_json': None,       # user voted gender spectrum
        }
        
        # 1. Metadatos del Perfume (Estructura de la cabecera)
        title_tag = soup.select_one('h1[itemprop="name"]') or soup.select_one("h1")
        if title_tag:
            raw_record['name'] = title_tag.text.strip()
            # Detectar género declarado en el título de la página
            if "for men" in title_tag.text.lower():
                raw_record['declared_gender'] = "men"
            elif "for women and men" in title_tag.text.lower() or "unisex" in title_tag.text.lower():
                raw_record['declared_gender'] = "unisex"
            elif "for women" in title_tag.text.lower():
                raw_record['declared_gender'] = "women"

        designer_tag = soup.select_one('p[itemprop="brand"] a span') or soup.select_one('p[itemprop="brand"]')
        raw_record['designer'] = designer_tag.text.strip() if designer_tag else None
        
        # 2. Ratings Globales Estándar
        rating_tag = soup.select_one('span[itemprop="ratingValue"]')
        raw_record['rating_value'] = rating_tag.text.strip() if rating_tag else None
        
        vote_count_tag = soup.select_one('span[itemprop="ratingCount"]')
        raw_record['rating_count'] = vote_count_tag.text.strip() if vote_count_tag else None

        # 3. Acordes Crudos (Lista completa tal como aparece en el gráfico de texto)
        accord_elements = soup.find_all(string=["fruity", "sweet", "woody", "leather", "citrus", "smoky", "musky", "fresh", "tropical", "mossy", "amber", "vanilla", "powdery", "iris", "aromatic", "spicy"])
        accords_clean = list(dict.fromkeys([acc.strip() for acc in accord_elements if len(acc.strip()) > 2]))
        raw_record['accords_raw'] = ", ".join(accords_clean)

        # 4. Pirámide Olfativa (Notas Crudas en Listas separadas)
        # Buscamos los contenedores de las notas por sus encabezados de texto nativos
        levels = {"Top Notes": 'top_notes', "Middle Notes": 'heart_notes', "Base Notes": 'base_notes'}
        for text_label, key in levels.items():
            header = soup.find(string=lambda t: t and text_label in t)
            if header:
                parent_div = header.find_parent("div")
                if parent_div:
                    # Encontrar todos los enlaces a notas dentro de este nivel de la pirámide
                    note_links = parent_div.find_next_sibling("div")
                    if note_links:
                        notes = [img['alt'].strip() for img in note_links.find_all("img") if img.get('alt')]
                        raw_record[key] = ", ".join(notes)

        # 5. Volcado de las Votaciones Numéricas desde el API de Red Interceptada
        if 'api_json' in network_data:
            api = network_data['api_json']
            
            # Guardamos las estructuras completas de votación en strings JSON limpios
            raw_record['vibe_reactions_json'] = json.dumps(api.get('vibe', {}))
            raw_record['longevity_json'] = json.dumps(api.get('longevity', {}))
            raw_record['sillage_json'] = json.dumps(api.get('sillage', {}))
            raw_record['seasons_json'] = json.dumps(api.get('seasons', {}))
            raw_record['time_of_day_json'] = json.dumps(api.get('tod', {}))
            raw_record['price_value_json'] = json.dumps(api.get('pricevalue', {}))
            raw_record['gender_clinal_json'] = json.dumps(api.get('gender', {}))
        else:
            print("⚠️ Advertencia: No se capturó el JSON de respuestas de red para este item. Intenta aumentar levemente los tiempos de espera.")

        print(f"✅ Extracción Cruda Exitosa -> {raw_record['name']}")
        return raw_record

    except Exception as e:
        print(f"❌ Error crítico procesando la URL: {e}")
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
        print("🗑️ Dataset antiguo eliminado.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, 
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        print("🚀 Iniciando Motor de Extracción para Data Science...")
        raw_dataset = []
        
        for url in urls_objetivo:
            data = await scrape_fragrantica_perfume_raw(browser, url)
            if data:
                raw_dataset.append(data)
                
        if raw_dataset:
            df = pd.DataFrame(raw_dataset)
            # Guardamos usando el separador '|' porque los strings de JSON contienen comas legítimas
            df.to_csv(CHECKPOINT_FILE, sep="|", index=False, encoding="utf-8")
            print(f"\n📊 Proceso terminado. Archivo crudo generado con {len(df)} registros en '{CHECKPOINT_FILE}'")
        else:
            print("❌ El proceso terminó sin recopilar registros.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())