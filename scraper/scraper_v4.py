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

CHECKPOINT_FILE = "fragrantica_raw_v4.csv"

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
    """Extrae de forma robusta e independiente cada distribución del DOM."""
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
        
        # Scroll controlado y progresivo hacia el fondo para activar la carga de componentes
        for _ in range(8):
            await page.evaluate("window.scrollBy(0, 500);")
            await asyncio.sleep(1.0)
            
        # SOLUCIÓN CRÍTICA REVIEWS: Esperar explícitamente a que el bloque de comentarios cargue en el DOM
        try:
            await page.wait_for_selector('div[itemprop="review"]', timeout=10000)
        except Exception:
            print("⏳ El contenedor de comentarios tarda en cargar, procediendo con el DOM disponible...")

        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
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
            # Campos corregidos:
            'vibe_reactions_raw_dist': None,
            'seasons_raw_dist': None,
            'time_of_day_raw_dist': None,
            'longevity_raw_dist': None,
            'sillage_raw_dist': None,
            'price_value_raw_dist': None,
            'gender_voted_raw_dist': None,
            'reviews_text_corpus': None
        }
        
        # --- [ Extracción Base e Índices ] ---
        title_h1 = soup.select_one('h1[itemprop="name"]')
        if title_h1:
            raw_record['name_raw'] = title_h1.text.strip()
            
        designer_tag = soup.select_one('p[itemprop="brand"] a span') or soup.select_one('p[itemprop="brand"]')
        raw_record['designer_raw'] = designer_tag.text.strip() if designer_tag else None
        
        rating_tag = soup.select_one('span[itemprop="ratingValue"]')
        raw_record['global_rating'] = rating_tag.text.strip() if rating_tag else None
        
        vote_count_tag = soup.select_one('span[itemprop="ratingCount"]')
        raw_record['global_rating_count'] = vote_count_tag.text.strip() if vote_count_tag else None

        accords_link = soup.select_one('a[href*="accords-search"]')
        if accords_link:
            raw_record['accords_query_string'] = accords_link['href'].split('?')[-1]
            
        perfumer_links = soup.select('a[href^="/noses/"]')
        if perfumer_links:
            raw_record['perfumers_raw'] = ", ".join(list(dict.fromkeys([p.text.strip() for p in perfumer_links])))

        # --- [ Pirámide Olfativa ] ---
        pyramid_container = soup.select_one('#pyramid')
        if pyramid_container:
            levels = {"max-w-md": 'top_notes_raw', "max-w-xl": 'heart_notes_raw', "max-w-2xl": 'base_notes_raw'}
            for class_size, record_key in levels.items():
                level_div = pyramid_container.select_one(f'div.{class_size}')
                if level_div:
                    notes_links = level_div.select('a.pyramid-note-link')
                    raw_record[record_key] = ", ".join([n.text.strip() for n in notes_links if n.text.strip()])

        # --- [ SOLUCIÓN A DISTRIBUCIONES: Extracción dirigida e independiente ] ---
        # Buscamos de forma semántica por los títulos h6/Headers de las tarjetas Tailwind
        all_cards = soup.select('div.tw-perf-card, div.tw-rating-card')
        
        for card in all_cards:
            header = card.select_one('h6, .tw-rating-card-header')
            if not header:
                continue
            header_text = header.text.lower()
            
            # Buscamos las filas de datos internas de esta tarjeta específica
            rows = card.select('div.space-y-2 > div, div.flex.items-center.gap-1\.5')
            dist_dict = {}
            for row in rows:
                label_tag = row.select_one('span[class*="text-zinc-600"], span[class*="text-zinc-300"]')
                value_tag = row.select_one('span.tabular-nums, div.text-right > span, span[class*="text-zinc-500"]')
                if label_tag and value_tag:
                    dist_dict[label_tag.text.strip().lower()] = value_tag.text.strip().lower()
            
            if not dist_dict:
                continue
                
            # Clasificamos los datos según el título de la tarjeta correspondiente
            if "rating" in header_text:
                raw_record['vibe_reactions_raw_dist'] = json.dumps(dist_dict)
            elif "when to wear" in header_text:
                # Separar Horarios (Day/Night) y Estaciones basándonos en las llaves del diccionario
                seasons_keys = ['winter', 'spring', 'summer', 'fall']
                seasons_sub = {k: v for k, v in dist_dict.items() if k in seasons_keys}
                tod_sub = {k: v for k, v in dist_dict.items() if k in ['day', 'night']}
                if seasons_sub: raw_record['seasons_raw_dist'] = json.dumps(seasons_sub)
                if tod_sub: raw_record['time_of_day_raw_dist'] = json.dumps(tod_sub)
            elif "longevity" in header_text:
                raw_record['longevity_raw_dist'] = json.dumps(dist_dict)
            elif "sillage" in header_text:
                raw_record['sillage_raw_dist'] = json.dumps(dist_dict)
            elif "price value" in header_text or "value" in header_text:
                raw_record['price_value_raw_dist'] = json.dumps(dist_dict)
            elif "gender" in header_text or "unisex" in header_text:
                raw_record['gender_voted_raw_dist'] = json.dumps(dist_dict)

        # --- [ SOLUCIÓN A REVIEWS: Captura del Corpus de Texto ] ---
        reviews_block = soup.select_one('#all-reviews') or soup.select_one('.review-tab-panels')
        if reviews_block:
            reviews_bodies = reviews_block.select('div[itemprop="reviewBody"]')
            # Tomamos una muestra controlada de las primeras 10 para evitar desbordamientos
            sample_reviews = reviews_bodies[:10]
            clean_reviews = [rb.text.strip().replace("\n", " ").replace("|", " ") for rb in sample_reviews if rb.text.strip()]
            if clean_reviews:
                raw_record['reviews_text_corpus'] = " [REVIEW_BREAK] ".join(clean_reviews)

        print(f"✅ Extracción Cruda Exitosa -> {raw_record['name_raw']}")
        return raw_record

    except Exception as e:
        print(f"❌ Error en el proceso de extracción: {e}")
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
        print("🗑️ Dataset antiguo removido.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, 
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