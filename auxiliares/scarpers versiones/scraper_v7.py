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

CHECKPOINT_FILE = "fragrantica_raw_v7.csv"

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
    """Extrae de forma robusta e independiente cada distribución del DOM usando clics dinámicos."""
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1280, "height": 800},
        locale="en-US"
    )
    page = await context.new_page()
    
    try:
        print(f"🔎 Navegando automáticamente a: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_selector("h1", timeout=15000)
        
        # 1. Scroll humano inicial para despertar componentes asíncronos superiores
        await human_scroll(page)
        
        # Guardamos el primer estado del HTML para extraer las métricas estables
        html_initial = await page.content()
        soup = BeautifulSoup(html_initial, 'html.parser')
        
        raw_record = {
            'url': url,
            'bottle_image_url': None,
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

        bottle_img = soup.select_one('img[itemprop="image"]')
        if bottle_img and bottle_img.get('src'):
            raw_record['bottle_image_url'] = bottle_img['src'].strip()
            
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

        # --- [ SOLUCIÓN INTEGRADA: Distribuciones Estables del Historial ] ---
        # Bloques basados en Componentes de Reacciones y Estaciones (.tw-rating-card)
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
            raw_record['longevity_raw_dist'] = extract_dom_distribution(perf_section)
            raw_record['sillage_raw_dist'] = extract_dom_distribution(perf_section)
            
        demo_section = soup.select_one('#demographics')
        if demo_section:
            raw_record['gender_voted_raw_dist'] = extract_dom_distribution(demo_section)
            raw_record['price_value_raw_dist'] = extract_dom_distribution(demo_section)

        # --- [ SOLUCIÓN DE REVIEWS: Evento Click Automatizado ] ---
        print("🖱️ Ejecutando clic en el enlace de reseñas para forzar la carga...")
        try:
            # Localizamos el selector exacto que se muestra en tu captura de DevTools
            reviews_trigger = page.locator('a[href="#all-reviews"]')
            if await reviews_trigger.count() > 0:
                # Forzamos el click virtual
                await reviews_trigger.click(force=True)
                # Damos un margen de tiempo para que se complete el renderizado dinámico en el DOM
                await page.wait_for_selector('div[itemprop="review"]', timeout=8000)
                await asyncio.sleep(1.5)
                
                # Volvemos a capturar el HTML actualizado con los comentarios inyectados
                html_updated = await page.content()
                soup_updated = BeautifulSoup(html_updated, 'html.parser')
                
                reviews_block = soup_updated.select_one('#all-reviews') or soup_updated.select_one('.review-tab-panels')
                if reviews_block:
                    reviews_bodies = reviews_block.select('div[itemprop="reviewBody"]')
                    sample_reviews = reviews_bodies[:10] # Muestra significativa
                    clean_reviews = [rb.text.strip().replace("\n", " ").replace("|", " ") for rb in sample_reviews if rb.text.strip()]
                    if clean_reviews: 
                        raw_record['reviews_text_corpus'] = " [REVIEW_BREAK] ".join(clean_reviews)
                        print(f"💬 Reseñas integradas con éxito ({len(clean_reviews)} procesadas).")
        except Exception as e:
            print(f"⏳ No se pudo completar el trigger de comentarios: {e}, guardando métricas base.")

        print(f"✅ Extracción Consolidada Exitosa -> {raw_record['name_raw']}")
        return raw_record

    except Exception as e:
        print(f"❌ Error automático en {url}: {e}")
        return None
    finally:
        await page.close()
        await context.close()

async def main():
    SEMILLA_FILE = "perfume_catalog_links.csv"
    
    if os.path.exists(SEMILLA_FILE):
        df_semilla = pd.read_csv(SEMILLA_FILE)
        urls_objetivo = df_semilla["perfume_url"].tolist()
        
        # Par obtener solo una prueba
        # urls_objetivo = df_semilla["perfume_url"].head(5).tolist()
    else:
        # Fallback por si acaso el archivo no existe
        print(f"⚠️ No se encontró {SEMILLA_FILE}, usando lista vacía.")
        urls_objetivo = []
    
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