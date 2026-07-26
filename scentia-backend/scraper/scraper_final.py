import asyncio
import random
import os
import time
from datetime import datetime
import json
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
]

CHECKPOINT_FILE = "fragrantica_data_from_scraper.csv"
SEMILLA_FILE = "perfume_catalog_links.csv"
LOG_ERRORES_FILE = "failed_urls.log"
LOG_SESIONES_FILE = "scraping_sessions.log"

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
    #context = await browser.new_context(
        #user_agent=random.choice(USER_AGENTS),
        #viewport={"width": 1280, "height": 800},
        #locale="en-US"
    #)
    #page = await context.new_page()


    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1280, "height": 800},
        locale="es-ES",  # O "es-MX" según prefieras
        extra_http_headers={
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
        }
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

def registrar_log_sesion(
    inicio_ts, total_pendientes, exitosos, fallidos, estado
):
    duracion_seg = round(time.time() - inicio_ts, 2)
    minutos, segundos = divmod(int(duracion_seg), 60)
    tiempo_formateado = (
        f"{minutos}m {segundos}s" if minutos > 0 else f"{duracion_seg}s"
    )

    fecha_inicio = datetime.fromtimestamp(inicio_ts).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    fecha_fin = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_linea = (
        f"[{fecha_fin}] SESIÓN | Estado: {estado} | Inicio: {fecha_inicio} | "
        f"Duración: {tiempo_formateado} | Pendientes: {total_pendientes} | "
        f"Exitosos: {exitosos} | Fallidos: {fallidos}\n"
    )

    with open(LOG_SESIONES_FILE, "a", encoding="utf-8") as f:
        f.write(log_linea)


def registrar_error_url(url, motivo):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_ERRORES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] URL: {url} | Error: {motivo}\n")


async def main():
    inicio_sesion = time.time()
    exitosos_count = 0
    fallidos_count = 0
    estado_sesion = "FINALIZADO_OK"

    # 1. Cargar semillas
    if os.path.exists(SEMILLA_FILE):
        df_semilla = pd.read_csv(SEMILLA_FILE)
        # Reemplazar el dominio en la columna de URLs
        df_semilla["perfume_url"] = df_semilla["perfume_url"].str.replace(
            "https://www.fragrantica.com", 
            "https://www.fragrantica.es", 
            regex=False
        )
        urls_objetivo = df_semilla["perfume_url"].tolist()
    else:
        print(f"⚠️ No se encontró {SEMILLA_FILE}, usando lista vacía.")
        urls_objetivo = []

    # 2. Filtrar URLs ya procesadas en checkpoints previos
    urls_procesadas = set()
    if os.path.exists(CHECKPOINT_FILE):
        try:
            df_existente = pd.read_csv(
                CHECKPOINT_FILE, sep="|", usecols=["url"]
            )
            urls_procesadas = set(df_existente["url"].tolist())
            print(
                f"📈 Checkpoint detectado. Omitiendo {len(urls_procesadas)} URLs previas."
            )
        except Exception as e:
            print(f"⚠️ No se pudo leer el checkpoint anterior: {e}")

    urls_pendientes = [
        url for url in urls_objetivo if url not in urls_procesadas
    ]

    # 🔀 MEZCLA ALEATORIA EN MEMORIA
    # Desordena la lista pendiente sin modificar la lista original ni el archivo semilla.
    random.shuffle(urls_pendientes)

    print(
        f"🚀 Quedan {len(urls_pendientes)} ítems pendientes. Lista ordenada aleatoriamente para esta sesión."
    )

    if not urls_pendientes:
        print("✨ Todos los ítems ya han sido procesados.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, ##### MODIFICAR SI OCURRE UN ERROR PARA DEBUG
            args=["--disable-blink-features=AutomationControlled"],
        )

        try:
            for index, url in enumerate(urls_pendientes, start=1):
                tiempo_item_inicio = time.time()
                data = None

                try:
                    data = await scrape_fragrantica_deep_raw(browser, url)
                except Exception as err:
                    motivo_err = f"Excepción de ejecución: {str(err)}"
                    registrar_error_url(url, motivo_err)
                    fallidos_count += 1
                    print(
                        f"❌ [{index}/{len(urls_pendientes)}] Error en {url}: {err}"
                    )

                if data:
                    df_row = pd.DataFrame([data])
                    header_needed = not os.path.exists(CHECKPOINT_FILE)

                    df_row.to_csv(
                        CHECKPOINT_FILE,
                        sep="|",
                        index=False,
                        mode="a",
                        header=header_needed,
                        encoding="utf-8",
                    )
                    exitosos_count += 1
                    duracion_item = round(
                        time.time() - tiempo_item_inicio, 2
                    )
                    print(
                        f"📦 [{index}/{len(urls_pendientes)}] Guardado ({duracion_item}s)."
                    )
                elif data is None and err is None:
                    # Cuando la función retorna None o dict vacío sin lanzar excepción
                    registrar_error_url(
                        url, "Sin datos retornados (retornó None)"
                    )
                    fallidos_count += 1
                    print(
                        f"⚠️ [{index}/{len(urls_pendientes)}] Sin datos en {url}."
                    )

                # Pausa de enfriamiento prudente entre páginas
                if index < len(urls_pendientes):
                    await asyncio.sleep(random.uniform(4.0, 8.0))

        except KeyboardInterrupt:
            estado_sesion = "INTERRUMPIDO_USUARIO"
            print("\n🛑 Interrupción detectada (Ctrl + C). Guardando logs...")
        except Exception as e_global:
            estado_sesion = f"CRASH: {str(e_global)}"
            print(f"\n💥 Error inesperado en la sesión: {e_global}")
        finally:
            await browser.close()
            registrar_log_sesion(
                inicio_ts=inicio_sesion,
                total_pendientes=len(urls_pendientes),
                exitosos=exitosos_count,
                fallidos=fallidos_count,
                estado=estado_sesion,
            )

    print(
        f"\n🎉 Sesión guardada. Exitosos: {exitosos_count} | Fallidos: {fallidos_count}"
    )


if __name__ == "__main__":
    asyncio.run(main())