import os
import time
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURACIÓN ---
URL_BUSQUEDA = "https://www.ldlc.com/es-es/informatica/piezas-de-informatica/tarjeta-grafica/c4684/+fv121-126519,126520,126567+fv1766-16762.html"
ARCHIVO_DATOS = "vistos_ldlc.json"
WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')

# Marcas que NO queremos (Añade más si salen otras)
MARCAS_IGNORAR = ["asus", "msi", "gigabyte", "zotac", "pny", "gainward", "palit", "inno3d", "kfa2"]

def cargar_vistos():
    if not os.path.exists(ARCHIVO_DATOS): return []
    try:
        with open(ARCHIVO_DATOS, 'r') as f: return json.load(f)
    except: return []

def guardar_vistos(lista):
    with open(ARCHIVO_DATOS, 'w') as f: json.dump(lista, f)

def notificar_discord(producto):
    if not WEBHOOK_URL: return
    
    # Si es Founders (o parece serlo), ponemos alerta roja y mention
    es_founder = "founder" in producto['nombre'].lower() or "nvidia" in producto['nombre'].lower()
    
    color = 15548997 if es_founder else 5763719 # Rojo si es FE, Verde si es otra
    mensaje = "@everyone 🚨 **FOUNDERS EDITION DETECTADA**" if es_founder else "📢 **Stock detectado en LDLC**"

    data = {
        "content": mensaje,
        "embeds": [{
            "title": producto['nombre'],
            "url": producto['link'],
            "description": f"Precio: {producto['precio']}\nEstado: {producto['stock']}",
            "color": color,
            "thumbnail": {"url": producto['img']}
        }]
    }
    requests.post(WEBHOOK_URL, json=data)

def check_ldlc():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    print("Iniciando navegador...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        print(f"Cargando lista: {URL_BUSQUEDA}")
        driver.get(URL_BUSQUEDA)
        
        # Esperamos a que cargue la lista de productos (clase .listing-product o .pdt-item)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".listing-product, .pdt-item"))
        )

        # Buscamos los bloques de productos
        items = driver.find_elements(By.CSS_SELECTOR, ".listing-product, .pdt-item")
        print(f"Elementos encontrados en la web: {len(items)}")

        productos_encontrados = []
        
        for item in items:
            try:
                # Extraer Título
                title_el = item.find_element(By.CSS_SELECTOR, ".title-3, .pdt-info h3")
                nombre = title_el.text.strip()
                link = title_el.find_element(By.TAG_NAME, "a").get_attribute("href")
                
                # Extraer Precio (si existe)
                try:
                    precio = item.find_element(By.CSS_SELECTOR, ".price, .price-row").text.strip()
                except:
                    precio = "Precio no disponible"

                # Extraer Imagen (opcional)
                try:
                    img = item.find_element(By.CSS_SELECTOR, "img").get_attribute("src")
                except:
                    img = ""

                # --- FILTRO INTELIGENTE ---
                # 1. Comprobamos si es una de las marcas que NO queremos
                nombre_lower = nombre.lower()
                es_marca_terceros = any(marca in nombre_lower for marca in MARCAS_IGNORAR)
                
                # Queremos notificar SI:
                # - NO es una marca de terceros (es decir, es probable que sea NVIDIA pura)
                # - O dice explícitamente "Founders"
                # - O dice "NVIDIA" al principio sin otras marcas
                
                # Si tú quieres ver TODO lo que salga en esa URL, quita este 'if'.
                # Pero si solo quieres Founders, esto ayuda a filtrar basura.
                if not es_marca_terceros or "founder" in nombre_lower:
                    
                    # Chequeo de Stock: A veces LDLC muestra productos agotados en la lista
                    # Buscamos si hay botón "Añadir a la cesta" o NO pone "Agotado/Rupture"
                    texto_item = item.text.lower()
                    
                    # Si no pone 'rupture' (francés) o 'agotado' (español), asumimos stock
                    if "rupture" not in texto_item and "agotado" not in texto_item:
                        stock_status = "En Stock (Probable)"
                        
                        productos_encontrados.append({
                            'id': link.split('/')[-1], # ID basado en URL
                            'nombre': nombre,
                            'link': link,
                            'precio': precio,
                            'stock': stock_status,
                            'img': img
                        })
            except Exception as e:
                print(f"Error parseando un item: {e}")
                continue

        # Lógica de notificación (igual que antes)
        vistos_antiguos = cargar_vistos()
        vistos_nuevos = [p['id'] for p in productos_encontrados]
        nuevos_detectados = False

        print(f"Productos válidos (filtrados): {len(productos_encontrados)}")

        for prod in productos_encontrados:
            if prod['id'] not in vistos_antiguos:
                print(f"NUEVO MATCH: {prod['nombre']}")
                notificar_discord(prod)
                nuevos_detectados = True
        
        # Solo actualizamos si encontramos algo o si la lista estaba vacía
        if nuevos_detectados or (not vistos_antiguos and vistos_nuevos):
             guardar_vistos(vistos_nuevos)

    except Exception as e:
        print(f"Error general en Selenium: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    check_ldlc()