import requests
import json
import os
import sys
from datetime import datetime

# --- CONFIGURACIÓN ---
API_URL = "https://api.nvidia.partners/edge/product/search?page=1&limit=20&locale=es-es&category=GPU&manufacturer=NVIDIA"
ARCHIVO_ESTADO = "estado_nvidia.json"
WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')

# Filtros (Parte del nombre)
OBJETIVOS = ["5080", "5090", "4090", "4080"] 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://store.nvidia.com/",
    "Origin": "https://store.nvidia.com"
}

def cargar_estado():
    if not os.path.exists(ARCHIVO_ESTADO): return {}
    try:
        with open(ARCHIVO_ESTADO, 'r') as f: return json.load(f)
    except: return {}

def guardar_estado(data):
    with open(ARCHIVO_ESTADO, 'w') as f: json.dump(data, f)

def notificar_discord(titulo, url, precio, estado):
    if not WEBHOOK_URL: return
    print(f"🚨 ALERTA: {titulo} -> {estado}")
    
    # Color: Verde si hay stock, Amarillo si es 'COMING_SOON'
    color = 5763719 if estado == "IN_STOCK" else 16776960
    mensaje = "@everyone 🚨 **STOCK NVIDIA FE DETECTADO**" if estado == "IN_STOCK" else "📢 **Novedad en API Nvidia**"

    data = {
        "content": mensaje,
        "embeds": [{
            "title": titulo,
            "url": url,
            "description": f"**Estado:** {estado}\n**Precio:** {precio}",
            "color": color,
            "footer": {"text": "Monitor API NVIDIA - GitHub Actions"}
        }]
    }
    requests.post(WEBHOOK_URL, json=data)

def check_api():
    print(f"Consultando API Nvidia...")
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"Error API: {response.status_code}")
            return

        data = response.json()
        productos = data.get('searchedProducts', {}).get('productDetails', [])
        
        estado_antiguo = cargar_estado()
        estado_nuevo = {}
        hay_cambios = False

        for p in productos:
            nombre = p.get('productTitle', 'Desconocido')
            sku = p.get('productID', nombre) # ID único
            status_actual = p.get('status', 'UNKNOWN')
            url = p.get('productUrl', '')
            precio = p.get('productPrice', '???')

            # 1. Filtramos por nombre (Solo 4080/4090/5080/5090)
            if not any(obj in nombre for obj in OBJETIVOS):
                continue
            
            # Guardamos el estado actual para la próxima
            estado_nuevo[sku] = status_actual
            
            # 2. Lógica de Detección de CAMBIOS
            # Recuperamos cómo estaba antes este producto
            status_anterior = estado_antiguo.get(sku, "UNKNOWN")

            # AVISAR SI:
            # - El estado NO es OUT_OF_STOCK (es decir, hay stock o viene pronto)
            # - Y ADEMÁS el estado ha cambiado respecto a la última vez (para no spamear)
            if status_actual != "OUT_OF_STOCK" and status_actual != status_anterior:
                notificar_discord(nombre, url, precio, status_actual)
            
            if status_actual != status_anterior:
                hay_cambios = True
                print(f"Cambio detectado en {nombre}: {status_anterior} -> {status_actual}")

        # Guardamos la "foto" actual de la API para la próxima ejecución
        if hay_cambios or not estado_antiguo:
            guardar_estado(estado_nuevo)
        else:
            print("Sin cambios en el stock de Nvidia.")

    except Exception as e:
        print(f"Error script API: {e}")

if __name__ == "__main__":
    check_api()
