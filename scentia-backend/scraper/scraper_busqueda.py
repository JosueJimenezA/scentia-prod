import asyncio
import random
import os
import time
import argparse
from datetime import datetime
import json
import pandas as pd
from playwright.async_api import async_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
]

SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__)) # .../scentia-backend/scraper
BACKEND_DIR = os.path.abspath(os.path.join(SCRAPER_DIR, "..")) # .../scentia-backend
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, "..")) # .../raíz_proyecto

# Rutas absolutas
CHECKPOINT_FILE = os.path.join(PROJECT_ROOT, "data", "fragrantica_data_from_scraper.csv")
SEMILLA_FILE = os.path.join(PROJECT_ROOT, "data", "perfume_catalog_links.csv")
LOG_ERRORES_FILE = os.path.join(SCRAPER_DIR, "failed_urls.log")
LOG_SESIONES_FILE = os.path.join(SCRAPER_DIR, "scraping_sessions.log")

# Ajusta el número de pestañas concurrentes según tu CPU/Ancho de banda (3 a 5 es ideal)
CONCURRENCY_LIMIT = 3


async def extract_dom_distribution_native(card_locator):
    """Extrae directamente del DOM usando Playwright (sin BeautifulSoup)."""
    try:
        rows = await card_locator.locator("div.mt-3.space-y-2 > div, div.flex.justify-evenly.gap-2 > div").all()
        distribution = {}
        for row in rows:
            label_loc = row.locator('span[class*="text-zinc-600"], span[class*="text-zinc-500"]')
            val_loc = row.locator('span.tabular-nums, div.text-right > span')
            
            if await label_loc.count() > 0 and await val_loc.count() > 0:
                lbl = (await label_loc.first.text_content()).strip().lower()
                val = (await val_loc.first.text_content()).strip().lower()
                if lbl and val:
                    distribution[lbl] = val
        return json.dumps(distribution) if distribution else None
    except Exception:
        return None


async def scrape_fragrantica_deep_raw(browser, url, semaphore):
    async with semaphore:
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="es-ES",
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"}
        )
        page = await context.new_page()

        # 1. Bloquear recursos pesados para acelerar la carga (imágenes, fuentes, hojas de estilo)
        await page.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,css,woff,woff2}", 
            lambda route: route.abort()
        )

        try:
            print(f"🔎 Navegando a: {url}")
            # domcontentloaded es rápido y suficiente para cargar la estructura base
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector("h1", timeout=10000)

            # 2. Scroll rápido y dirigido
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(0.5)

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

            # Extracción Directa con Selectores de Playwright
            h1 = page.locator('h1[itemprop="name"]')
            if await h1.count() > 0:
                raw_record['name_raw'] = (await h1.first.text_content()).strip()

            bottle = page.locator('img[itemprop="image"]')
            if await bottle.count() > 0:
                raw_record['bottle_image_url'] = await bottle.first.get_attribute('src')

            designer = page.locator('p[itemprop="brand"] a span, p[itemprop="brand"]')
            if await designer.count() > 0:
                raw_record['designer_raw'] = (await designer.first.text_content()).strip()

            rating = page.locator('span[itemprop="ratingValue"]')
            if await rating.count() > 0:
                raw_record['global_rating'] = (await rating.first.text_content()).strip()

            vote_count = page.locator('span[itemprop="ratingCount"]')
            if await vote_count.count() > 0:
                raw_record['global_rating_count'] = (await vote_count.first.text_content()).strip()

            accords = page.locator('a[href*="accords-search"]')
            if await accords.count() > 0:
                href = await accords.first.get_attribute('href')
                if href and '?' in href:
                    raw_record['accords_query_string'] = href.split('?')[-1]

            perfumers = page.locator('a[href^="/noses/"]')
            if await perfumers.count() > 0:
                names = [await p.text_content() for p in await perfumers.all()]
                raw_record['perfumers_raw'] = ", ".join(list(dict.fromkeys([n.strip() for n in names])))

            # Pirámide Olfativa
            pyramid = page.locator('#pyramid')
            if await pyramid.count() > 0:
                levels = {"max-w-md": 'top_notes_raw', "max-w-xl": 'heart_notes_raw', "max-w-2xl": 'base_notes_raw'}
                for class_size, record_key in levels.items():
                    notes = pyramid.locator(f'div.{class_size} a.pyramid-note-link')
                    if await notes.count() > 0:
                        note_texts = [await n.text_content() for n in await notes.all()]
                        raw_record[record_key] = ", ".join([n.strip() for n in note_texts if n.strip()])

            # Tarjetas y Distribuciones
            cards = await page.locator('.tw-rating-card').all()
            for card in cards:
                header = card.locator('.tw-rating-card-header')
                if await header.count() > 0:
                    text = (await header.first.text_content()).lower()
                    if "rating" in text:
                        raw_record['vibe_reactions_raw_dist'] = await extract_dom_distribution_native(card)
                    elif "when to wear" in text:
                        dist = await extract_dom_distribution_native(card)
                        raw_record['seasons_raw_dist'] = dist
                        raw_record['time_of_day_raw_dist'] = dist

            perf_section = page.locator('#performance')
            if await perf_section.count() > 0:
                dist = await extract_dom_distribution_native(perf_section)
                raw_record['longevity_raw_dist'] = dist
                raw_record['sillage_raw_dist'] = dist

            demo_section = page.locator('#demographics')
            if await demo_section.count() > 0:
                dist = await extract_dom_distribution_native(demo_section)
                raw_record['gender_voted_raw_dist'] = dist
                raw_record['price_value_raw_dist'] = dist

            # Clic dinámico a comentarios
            reviews_trigger = page.locator('a[href="#all-reviews"]')
            if await reviews_trigger.count() > 0:
                try:
                    await reviews_trigger.first.click(force=True, timeout=2000)
                    await page.wait_for_selector('div[itemprop="reviewBody"]', timeout=4000)
                    
                    reviews = page.locator('#all-reviews div[itemprop="reviewBody"], .review-tab-panels div[itemprop="reviewBody"]')
                    reviews_list = await reviews.all()
                    sample_reviews = reviews_list[:10]
                    
                    clean_reviews = []
                    for r in sample_reviews:
                        txt = (await r.text_content()).strip().replace("\n", " ").replace("|", " ")
                        if txt: clean_reviews.append(txt)
                        
                    if clean_reviews:
                        raw_record['reviews_text_corpus'] = " [REVIEW_BREAK] ".join(clean_reviews)
                except Exception:
                    pass  # Continuar si la sección de reseñas no responde a tiempo

            print(f"✅ Extracción Exitosa -> {raw_record['name_raw']}")
            return raw_record

        except Exception as e:
            print(f"❌ Error en {url}: {e}")
            return None
        finally:
            await page.close()
            await context.close()


def registrar_log_sesion(inicio_ts, total_pendientes, exitosos, fallidos, estado):
    duracion_seg = round(time.time() - inicio_ts, 2)
    minutos, segundos = divmod(int(duracion_seg), 60)
    tiempo_formateado = f"{minutos}m {segundos}s" if minutos > 0 else f"{duracion_seg}s"
    fecha_inicio = datetime.fromtimestamp(inicio_ts).strftime("%Y-%m-%d %H:%M:%S")
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
    # --- PARSEO DE ARGUMENTOS PARA MODO SINGLE-URL ---
    parser = argparse.ArgumentParser(description="Scraper de Fragrantica")
    parser.add_argument("--single-url", type=str, help="Procesar una única URL individual desde el backend")
    args, _ = parser.parse_known_args()

    inicio_sesion = time.time()
    exitosos_count = 0
    fallidos_count = 0
    estado_sesion = "FINALIZADO_OK"

    # Determinar si se ejecuta en modo URL individual o modo archivo por lotes
    if args.single_url:
        single_target = args.single_url.replace("https://www.fragrantica.com", "https://www.fragrantica.es")
        urls_pendientes = [single_target]
        print(f"🎯 Modo URL Individual activado para: {single_target}")
    else:
        if os.path.exists(SEMILLA_FILE):
            df_semilla = pd.read_csv(SEMILLA_FILE)
            df_semilla["perfume_url"] = df_semilla["perfume_url"].str.replace(
                "https://www.fragrantica.com", "https://www.fragrantica.es", regex=False
            )
            urls_objetivo = df_semilla["perfume_url"].tolist()
        else:
            urls_objetivo = []

        urls_procesadas = set()
        if os.path.exists(CHECKPOINT_FILE):
            try:
                df_existente = pd.read_csv(CHECKPOINT_FILE, sep="|", usecols=["url"])
                urls_procesadas = set(df_existente["url"].tolist())
                print(f"📈 Checkpoint detectado. Omitiendo {len(urls_procesadas)} URLs previas.")
            except Exception as e:
                print(f"⚠️ No se pudo leer el checkpoint anterior: {e}")

        urls_pendientes = [url for url in urls_objetivo if url not in urls_procesadas]
        random.shuffle(urls_pendientes)

        print(f"🚀 Quedan {len(urls_pendientes)} ítems pendientes. Procesando con concurrencia max={CONCURRENCY_LIMIT}.")

    if not urls_pendientes:
        print("✨ Todos los ítems ya han sido procesados o no hay URLs objetivo.")
        return

    semaphore = asyncio.Semaphore(1 if args.single_url else CONCURRENCY_LIMIT)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        try:
            for index, url in enumerate(urls_pendientes, start=1):
                tiempo_item_inicio = time.time()
                data = await scrape_fragrantica_deep_raw(browser, url, semaphore)

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
                    duracion_item = round(time.time() - tiempo_item_inicio, 2)
                    print(f"📦 [{index}/{len(urls_pendientes)}] Guardado en {duracion_item}s.")
                else:
                    registrar_error_url(url, "Sin datos retornados o fallo")
                    fallidos_count += 1

                if not args.single_url:
                    await asyncio.sleep(random.uniform(1.0, 2.5))

        except KeyboardInterrupt:
            estado_sesion = "INTERRUMPIDO_USUARIO"
            print("\n🛑 Interrupción detectada. Guardando logs...")
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

    print(f"\n🎉 Sesión guardada. Exitosos: {exitosos_count} | Fallidos: {fallidos_count}")


if __name__ == "__main__":
    asyncio.run(main())