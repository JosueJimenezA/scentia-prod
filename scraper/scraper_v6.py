import asyncio
import random
import os
import json
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
]

CHECKPOINT_FILE = "fragrantica_raw_data_science_dataset.csv"

async def human_scroll(page):
    """Simula un scroll orgánico usando la rueda del ratón virtual."""
    # Posicionamos el mouse en el centro de la pantalla
    await page.mouse.move(640, 400)
    
    # Hacemos scrolls variables imitando la lectura humana
    for _ in range(12):
        # Desplazamientos hacia abajo pequeños y asimétricos
        steps = random.randint(3, 6)
        for _ in range(steps):
            pixels = random.randint(80, 150)
            await page.mouse.wheel(0, pixels)
            await asyncio.sleep(random.uniform(0.05, 0.15))
        
        # Pausa aleatoria simulando que el usuario se detiene a leer o ver un gráfico
        await asyncio.sleep(random.uniform(0.8, 1.8))

async def scrape_fragrantica_deep_raw(browser, url):
    """Extrae todo el espectro de datos imitando interacción humana real."""
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1280, "height": 800},
        locale="en-US"
    )
    page = await context.new_page()
    
    try:
        print(f"🔎 Navegando automáticamente a: {url}")
        # Entramos esperando que cargue la estructura base
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_selector("h1", timeout=15000)
        
        # Ejecutamos el scroll humano para gatillar las peticiones asíncronas de forma orgánica
        await human_scroll(page)
        
        # Espera dinámica dirigida a las reseñas
        try:
            await page.wait_for_selector('div[itemprop="review"]', timeout=12000)
            # Un pequeño respiro final para asegurar el volcado al DOM
            await asyncio.sleep(2.0)
        except Exception:
            print("⏳ Los comentarios tardaron más de lo habitual, capturando DOM disponible...")

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

        # --- [ Distribuciones de Votos Avanzados ] ---
        all_blocks = soup.select('div.tw-perf-card, div.tw-rating-card, div[id="performance"], div[id="demographics"], div.p-4, div.p-2, div.p-5')
        
        for block in all_blocks:
            rows = block.select(r'div.space-y-2 > div, div.flex.items-center.gap-1\.5, div.flex.items-center.gap-2')
            if not rows: continue
                
            dist_dict = {}
            for row in rows:
                label_tag = row.select_one('span[class*="text-zinc-600"], span[class*="text-zinc-300"], span[class*="text-zinc-500"]')
                value_tag = row.select_one('span.tabular-nums, div.text-right > span, span[class*="font-semibold"]')
                if label_tag and value_tag:
                    lbl = label_tag.text.strip().lower()
                    val = value_tag.text.strip().lower()
                    if lbl and val and lbl != "no vote":
                        dist_dict[lbl] = val
            
            if not dist_dict: continue
            
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

        print(f"✅ Extracción Exitosa Automática -> {raw_record['name_raw']}")
        return raw_record

    except Exception as e:
        print(f"❌ Error automático en {url}: {e}")
        return None
    finally:
        await page.close()
        await context.close()

async def main():
    urls_objetivo = [
        "https://www.fragrantica.com/perfume/Creed/Aventus-9828.html",
        "https://www.fragrantica.com/perfume/Dior/Sauvage-31861.html"
    ]
    
    file_exists = os.path.exists(CHECKPOINT_FILE)
    if not file_exists:
        print("📊 Iniciando un nuevo dataset crudo.")
    else:
        print("📈 Dataset detectado. Ejecutando en Modo Append.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, # Mantenlo en False inicialmente para observar el scroll fluido automático
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        print(f"🚀 Iniciando extracción masiva de {len(urls_objetivo)} ítems...")
        
        for index, url in enumerate(urls_objetivo, start=1):
            data = await scrape_fragrantica_deep_raw(browser, url)
            
            if data:
                df_row = pd.DataFrame([data])
                df_row.to_csv(
                    CHECKPOINT_FILE, 
                    sep="|", 
                    index=False, 
                    mode='a', 
                    header=not os.path.exists(CHECKPOINT_FILE), 
                    encoding="utf-8"
                )
                print(f"📦 [{index}/{len(urls_objetivo)}] Guardado en CSV.")
            
            if index < len(urls_objetivo):
                # Pausa de enfriamiento prudente entre perfumes (4 a 8 segundos)
                await asyncio.sleep(random.uniform(4.0, 8.0))
                
        await browser.close()
    print(f"\n🎉 ¡Proceso automático finalizado! Dataset consolidado en '{CHECKPOINT_FILE}'")

if __name__ == "__main__":
    asyncio.run(main())