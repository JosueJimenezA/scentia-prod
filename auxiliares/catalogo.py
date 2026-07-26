import asyncio
import random
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def human_scroll(page):
    """Simula un desplazamiento gradual y natural hacia abajo."""
    scroll_height = await page.evaluate("document.body.scrollHeight")
    current_position = 0
    
    while current_position < scroll_height:
        # Avanza entre 200 y 500 píxeles aleatoriamente
        step = random.randint(200, 500)
        current_position += step
        await page.evaluate(f"window.scrollTo(0, {current_position});")
        # Pausa corta simulando lectura/visión
        await asyncio.sleep(random.uniform(0.3, 0.8))
        # Actualizar altura por si hay carga perezosa (lazy loading)
        scroll_height = await page.evaluate("document.body.scrollHeight")

async def get_all_designers(page):
    """Fase 1: Obtiene la lista de URLs de diseñadores desde el índice."""
    url_indice = "https://www.fragrantica.com/designers/"
    print(f"🗂️ Cargando índice maestro de diseñadores: {url_indice}")
    
    await page.goto(url_indice, wait_until="domcontentloaded", timeout=60000)
    await asyncio.sleep(random.uniform(2.0, 4.0))  # Pausa inicial humana
    
    # Scroll progresivo para forzar renderizado de imágenes y componentes dinámicos
    await human_scroll(page)
    
    html = await page.content()
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extraer todos los enlaces que apuntan a marcas/diseñadores
    brand_links = soup.select("a[href*='/designers/']")
    
    designers_urls = []
    for a in brand_links:
        href = a.get('href', '')
        if href.startswith("/designers/") and href.endswith(".html") and href != "/designers/":
            full_url = f"https://www.fragrantica.com{href}" if not href.startswith("http") else href
            designers_urls.append(full_url)
            
    return list(dict.fromkeys(designers_urls))

async def main():
    archivo_urls_final = "perfume_catalog_links.csv"
    
    async with async_playwright() as p:
        # Configuración de navegador para reducir la huella de automatización
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="es-ES"
        )
        
        page = await context.new_page()
        
        try:
            # 1. Obtener la lista global de diseñadores
            lista_disenadores = await get_all_designers(page)
            print(f"✅ Se encontraron {len(lista_disenadores)} marcas/diseñadores.")
            
            urls_perfumes_totales = []
            
            # 2. Iterar sobre los diseñadores
            for i, url_disenador in enumerate(lista_disenadores, start=1):
                print(f"🚀 [{i}/{len(lista_disenadores)}] Procesando: {url_disenador}")
                
                try:
                    # Navegación a la marca
                    await page.goto(url_disenador, wait_until="domcontentloaded", timeout=45000)
                    
                    # Simular lectura inicial de la marca
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    
                    # Scroll humano para cargar todos los perfumes de la lista (#list-view)
                    await human_scroll(page)
                    
                    html = await page.content()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Basado en la imagen 2: extraer enlaces dentro de #list-view o con la clase 'prefumeHbox'
                    list_container = soup.select_one("#list-view")
                    if list_container:
                        links_perfumes = list_container.select("a[href*='/perfume/']")
                    else:
                        links_perfumes = soup.select("a[href*='/perfume/']")
                    
                    count_antes = len(urls_perfumes_totales)
                    for a in links_perfumes:
                        href = a.get('href', '')
                        if href.startswith("/perfume/"):
                            urls_perfumes_totales.append(f"https://www.fragrantica.com{href}")
                    
                    obtenidos = len(urls_perfumes_totales) - count_antes
                    print(f"   └── Encontrados {obtenidos} perfumes en esta marca.")
                    
                except Exception as e:
                    print(f"⚠️ Error procesando {url_disenador}: {e}")
                    continue
                
                # Pausa aleatoria entre solicitudes a distintas páginas de marcas
                espera = random.uniform(3.5, 7.0)
                print(f"⏳ Pausa de cortesía: {espera:.2f}s...")
                await asyncio.sleep(espera)
                
            # 3. Guardado en CSV
            urls_unicas_finales = list(dict.fromkeys(urls_perfumes_totales))
            df = pd.DataFrame(urls_unicas_finales, columns=["perfume_url"])
            df.to_csv(archivo_urls_final, index=False, encoding="utf-8")
            
            print(f"\n🎉 ¡Extracción completada! Se guardaron {len(df)} enlaces en '{archivo_urls_final}'.")
            
        finally:
            await context.close()
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())