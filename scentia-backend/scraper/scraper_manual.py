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

CHECKPOINT_FILE = "fragrantica_raw_data_science_dataset.csv"

async def scrape_fragrantica_deep_raw(browser, url):
    """Abre el navegador en modo interactivo para asegurar la carga completa del DOM."""
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1280, "height": 800},
        locale="en-US"
    )
    page = await context.new_page()
    
    try:
        print(f"🔎 Navegando a: {url}")
        await page.goto(url, wait_until="commit", timeout=45000)
        
        print("\n" + "═"*50)
        print("🛑 SCRIPT PAUSADO EN MODO INTERACTIVO")
        print("1. Por favor, haz scroll lento por toda la página de Chromium.")
        print("2. Asegúrate de detenerte en los gráficos de Performance y Demographics.")
        print("3. En la ventana flotante 'Playwright Inspector', haz clic en RESUME (el botón de Play verde/azul) para extraer.")
        print("═"*50 + "\n")
        
        # Pausa interactiva humana para garantizar renderizado total
        await page.pause()
        
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
            'vibe_reactions_raw_dist': None,
            'seasons_raw_dist': None,
            'time_of_day_raw_dist': None,
            'longevity_raw_dist': None,
            'sillage_raw_dist': None,
            'price_value_raw_dist': None,
            'gender_voted_raw_dist': None,
            'reviews_text_corpus': None
        }
        
        # --- [ Extracción Base ] ---
        title_h1 = soup.select_one('h1[itemprop="name"]')
        if title_h1: raw_record['name_raw'] = title_h1.text.strip()
            
        designer_tag = soup.select_one('p[itemprop="brand"] a span') or soup.select_one('p[itemprop="brand"]')
        raw_record['designer_raw'] = designer_tag.text.strip() if designer_tag else None
        
        rating_tag = soup.select_one('span[itemprop="ratingValue"]')
        raw_record['global_rating'] = rating_tag.text.strip() if rating_tag else None
        
        vote_count_tag = soup.select_one('span[itemprop="ratingCount"]')
        raw_record['global_rating_count'] = vote_count_tag.text.strip() if vote_count_tag else None

        accords_link = soup.select_one('a[href*="accords-search"]')
        if accords_link: raw_record['accords_query_string'] = accords_link['href'].split('?')[-1]
            
        perfumer_links = soup.select('a[href^="/noses/"]')
        if perfumer_links: raw_record['perfumers_raw'] = ", ".join(list(dict.fromkeys([p.text.strip() for p in perfumer_links])))

        # --- [ Pirámide Olfativa ] ---
        pyramid_container = soup.select_one('#pyramid')
        if pyramid_container:
            levels = {"max-w-md": 'top_notes_raw', "max-w-xl": 'heart_notes_raw', "max-w-2xl": 'base_notes_raw'}
            for class_size, record_key in levels.items():
                level_div = pyramid_container.select_one(f'div.{class_size}')
                if level_div:
                    notes_links = level_div.select('a.pyramid-note-link')
                    raw_record[record_key] = ", ".join([n.text.strip() for n in notes_links if n.text.strip()])

        # --- [ SOLUCIÓN DEFINITIVA A LAS MÉTRICAS: Clasificación por contenido de llaves ] ---
        # Buscamos de forma general todos los contenedores flexibles que contienen filas de votación
        all_blocks = soup.select('div.tw-perf-card, div.tw-rating-card, div[id="performance"], div[id="demographics"], div.p-4, div.p-2')
        
        for block in all_blocks:
            rows = block.select(r'div.space-y-2 > div, div.flex.items-center.gap-1\.5, div.flex.items-center.gap-2')
            if not rows:
                continue
                
            dist_dict = {}
            for row in rows:
                label_tag = row.select_one('span[class*="text-zinc-600"], span[class*="text-zinc-300"], span[class*="text-zinc-500"]')
                value_tag = row.select_one('span.tabular-nums, div.text-right > span, span[class*="font-semibold"]')
                if label_tag and value_tag:
                    lbl = label_tag.text.strip().lower()
                    val = value_tag.text.strip().lower()
                    if lbl and val and lbl != "no vote":
                        dist_dict[lbl] = val
            
            if not dist_dict:
                continue
            
            # Clasificamos de manera robusta mapeando el contenido de las llaves del diccionario generado
            keys = list(dist_dict.keys())
            
            if 'love' in keys or 'hate' in keys:
                raw_record['vibe_reactions_raw_dist'] = json.dumps(dist_dict)
            elif 'very weak' in keys or 'long lasting' in keys:
                raw_record['longevity_raw_dist'] = json.dumps(dist_dict)
            elif 'intimate' in keys or 'enormous' in keys:
                raw_record['sillage_raw_dist'] = json.dumps(dist_dict)
            elif 'way overpriced' in keys or 'great value' in keys:
                raw_record['price_value_raw_dist'] = json.dumps(dist_dict)
            elif 'more male' in keys or 'more female' in keys:
                raw_record['gender_voted_raw_dist'] = json.dumps(dist_dict)
            elif 'winter' in keys or 'summer' in keys:
                # Separar estaciones de horarios del día si se encuentran juntos
                seasons_keys = ['winter', 'spring', 'summer', 'fall']
                seasons_sub = {k: v for k, v in dist_dict.items() if k in seasons_keys}
                tod_sub = {k: v for k, v in dist_dict.items() if k in ['day', 'night']}
                if seasons_sub: raw_record['seasons_raw_dist'] = json.dumps(seasons_sub)
                if tod_sub: raw_record['time_of_day_raw_dist'] = json.dumps(tod_sub)

        # --- [ Corpus de Reseñas ] ---
        reviews_block = soup.select_one('#all-reviews') or soup.select_one('.review-tab-panels') or soup.select_one('div.review-tab-panels')
        if reviews_block:
            reviews_bodies = reviews_block.select('div[itemprop="reviewBody"]')
            sample_reviews = reviews_bodies[:10]
            clean_reviews = [rb.text.strip().replace("\n", " ").replace("|", " ") for rb in sample_reviews if rb.text.strip()]
            if clean_reviews: 
                raw_record['reviews_text_corpus'] = " [REVIEW_BREAK] ".join(clean_reviews)

        print(f"✅ Extracción Cruda Exitosa -> {raw_record['name_raw']}")
        return raw_record

    except Exception as e:
        print(f"❌ Error en la interacción manual: {e}")
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
            df.to_csv(CHECKPOINT_FILE, sep="|", index=False, encoding="utf-8")
            print(f"\n📊 Extracción finalizada. Dataset guardado de forma segura en: '{CHECKPOINT_FILE}'")
        else:
            print("❌ No se pudieron procesar las fuentes.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())