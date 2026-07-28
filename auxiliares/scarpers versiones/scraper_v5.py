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

CHECKPOINT_FILE = "fragrantica_raw_v5.csv"

def extract_dom_distribution(container, selector_rows="div.mt-3.space-y-2 > div, div.flex.justify-evenly.gap-2 > div"):
    """Función auxiliar para mapear textos y conteos crudos de los gráficos de Tailwind."""
    distribution = {}
    if not container:
        return None
    rows = container.select(selector_rows)
    for row in rows:
        # Busca etiquetas de texto descriptivas de la izquierda o inferiores
        label_tag = row.select_one('span[class*="text-zinc-600"], span[class*="text-zinc-500"]')
        # Busca los valores numéricos crudos formateados con clases tabulares
        value_tag = row.select_one('span.tabular-nums, div.text-right > span')
        
        if label_tag and value_tag:
            lbl = label_tag.text.strip().lower()
            val = value_tag.text.strip().lower()
            if lbl and val:
                distribution[lbl] = val
    return json.dumps(distribution) if distribution else None

async def scrape_fragrantica_deep_raw(browser, url):
    """Extrae todo el espectro de información en formato crudo del DOM."""
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1280, "height": 800},
        locale="en-US"
    )
    page = await context.new_page()
    
    try:
        print(f"🔎 Navegando y renderizando DOM completo: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_selector("h1", timeout=15000)
        
        # Scroll lento por secciones para forzar el renderizado completo de las reviews asíncronas
        for _ in range(6):
            await page.evaluate("window.scrollBy(0, 600);")
            await asyncio.sleep(1.5)
            
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Inicialización del registro definitivo
        raw_record = {
            'url': url,
            'name_raw': None,
            'designer_raw': None,
            'global_rating': None,
            'global_rating_count': None,
            'accords_query_string': None,
            'perfumers_raw': None,
            'top_notes_raw': None,
            'heart_notes_raw': None,
            'base_notes_raw': None,
            # Variables de distribución capturadas directamente del DOM moderno de Tailwind:
            'vibe_reactions_raw_dist': None,  # love, like, ok, dislike, hate
            'seasons_raw_dist': None,          # winter, spring, summer, fall
            'time_of_day_raw_dist': None,      # day, night
            'longevity_raw_dist': None,         # very weak, weak, moderate...
            'sillage_raw_dist': None,           # intimate, moderate, strong...
            'price_value_raw_dist': None,       # way overpriced, good value...
            'gender_voted_raw_dist': None,      # female, more female, unisex...
            # NLP: Lista cruda de las primeras reseñas principales de la página
            'reviews_text_corpus': None
        }
        
        # 1. Identificación e Identidad Base
        title_h1 = soup.select_one('h1[itemprop="name"]')
        if title_h1:
            raw_record['name_raw'] = title_h1.text.strip()
            
        designer_tag = soup.select_one('p[itemprop="brand"] a span') or soup.select_one('p[itemprop="brand"]')
        raw_record['designer_raw'] = designer_tag.text.strip() if designer_tag else None
        
        # 2. Índices Globales de Popularidad
        rating_tag = soup.select_one('span[itemprop="ratingValue"]')
        raw_record['global_rating'] = rating_tag.text.strip() if rating_tag else None
        
        vote_count_tag = soup.select_one('span[itemprop="ratingCount"]')
        raw_record['global_rating_count'] = vote_count_tag.text.strip() if vote_count_tag else None

        # 3. Métricas de Estructura Comercial (Query string de Acordes y Narices)
        accords_link = soup.select_one('a[href*="accords-search"]')
        if accords_link:
            raw_record['accords_query_string'] = accords_link['href'].split('?')[-1]
            
        perfumer_links = soup.select('a[href^="/noses/"]')
        if perfumer_links:
            raw_record['perfumers_raw'] = ", ".join(list(dict.fromkeys([p.text.strip() for p in perfumer_links])))

        # 4. Extracción de Notas mediante niveles jerárquicos de la Pirámide Olfativa
        pyramid_container = soup.select_one('#pyramid')
        if pyramid_container:
            levels = {
                "max-w-md": 'top_notes_raw',
                "max-w-xl": 'heart_notes_raw',
                "max-w-2xl": 'base_notes_raw'
            }
            for class_size, record_key in levels.items():
                level_div = pyramid_container.select_one(f'div.{class_size}')
                if level_div:
                    notes_links = level_div.select('a.pyramid-note-link')
                    notes_extracted = [n.text.strip() for n in notes_links if n.text.strip()]
                    raw_record[record_key] = ", ".join(notes_extracted)

        # 5. Mapeo de Distribuciones en Crudo usando bloques de Clases y Selectores de ID
        # Bloques basados en Componentes de Reacciones / Estaciones
        cards = soup.select('.tw-rating-card')
        for card in cards:
            header = card.select_one('.tw-rating-card-header')
            if header:
                header_text = header.text.lower()
                if "rating" in header_text:
                    raw_record['vibe_reactions_raw_dist'] = extract_dom_distribution(card)
                elif "when to wear" in header_text:
                    raw_record['seasons_raw_dist'] = extract_dom_distribution(card)
                    raw_record['time_of_day_raw_dist'] = extract_dom_distribution(card)

        # Bloques de Rendimiento y Atributos (Performance & Demographics)
        perf_section = soup.select_one('#performance')
        if perf_section:
            # Separar Longevidad y Estela buscando por patrones de palabras clave en las filas
            raw_record['longevity_json_backup'] = extract_dom_distribution(perf_section)
            
        demo_section = soup.select_one('#demographics')
        if demo_section:
            # Captura las distribuciones de Demografía (Género de usuarios y relación Precio-Valor)
            raw_record['gender_voted_raw_dist'] = extract_dom_distribution(demo_section)
            raw_record['price_value_raw_dist'] = extract_dom_distribution(demo_section)

        # 6. Extracción de Reseñas Completas para Corpus de Texto (Data Text Mining)
        reviews_block = soup.select_one('#all-reviews')
        if reviews_block:
            reviews_bodies = reviews_block.select('div[itemprop="reviewBody"]')
            clean_reviews = [rb.text.strip().replace("\n", " ") for rb in reviews_bodies if rb.text.strip()]
            # Guardamos los textos separados por un delimitador interno especial para tokenizar después
            raw_record['reviews_text_corpus'] = " [REVIEW_BREAK] ".join(clean_reviews)

        print(f"✅ Procesamiento Crudo Exitoso -> {raw_record['name_raw']}")
        return raw_record

    except Exception as e:
        print(f"❌ Error en el proceso de extracción: {e}")
        return None
    finally:
        await page.close()
        await context.close()

async def main():
    urls_objetivo = [
        "https://www.fragrantica.es/perfume/Narciso-Rodriguez/Narciso-Rodriguez-For-Her-Musc-Nude-88936.html",
        "https://www.fragrantica.com/perfume/Dior/Sauvage-31861.html"
    ]
    
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("🗑️ Dataset antiguo removido.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, 
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        print("🚀 Lanzando Extractor Masivo Consolidado...")
        dataset = []
        
        for url in urls_objetivo:
            data = await scrape_fragrantica_deep_raw(browser, url)
            if data:
                dataset.append(data)
                
        if dataset:
            df = pd.DataFrame(dataset)
            # Guardamos usando un separador de tubería '|' para que los textos de reviews y JSONs no rompan las columnas
            df.to_csv(CHECKPOINT_FILE, sep="|", index=False, encoding="utf-8")
            print(f"\n📊 Extracción finalizada. Dataset guardado de forma segura en: '{CHECKPOINT_FILE}'")
        else:
            print("❌ No se pudieron procesar las fuentes.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())