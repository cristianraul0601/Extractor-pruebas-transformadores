import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import time

st.set_page_config(page_title="Extractor de Protocolos FAT - Transformadores", layout="wide")
st.title("⚡ Extractor de Protocolos de Transformadores a Excel")

api_key = st.sidebar.text_input("Ingresa tu Gemini API Key:", type="password")

st.markdown("### Sube tu protocolo de pruebas (PDF o Imagen)")
uploaded_file = st.file_uploader(
    "Selecciona el protocolo completo:", 
    type=["pdf", "png", "jpg", "jpeg"], 
    accept_multiple_files=False
)

def procesar_con_ia(file_bytes, mime_type, api_key):
    client = genai.Client(api_key=api_key)
    
    prompt = """
    Eres un ingeniero especialista en ensayos y protocolos FAT de transformadores de potencia.
    Analiza este documento completo y extrae de forma INDEPENDIENTE todas las tablas de pruebas presentes que correspondan a:
    
    1. Relación de Transformación (TTR) y Polaridad (Taps 1 al 27 o según corresponda, fases U, V, W, relación teórica, medida y error).
    2. Corriente de Excitación (Iu, Iv, Iw en cada Tap).
    3. Resistencia de Devanados en CC (AT por Taps y MT, fases, resistencia medida y desbalances).
    4. Resistencia de Aislamiento, Índice de Polarización (IP) e Índice de Absorción (IA).
    5. Factor de Potencia / Tangente Delta y Capacitancia (Devanados y Bushings).
    
    Reglas obligatorias de negocio:
    - CONVERSIÓN DE CORRIENTE: Si está en miliamperios (mA), divide entre 1000 para reportar en Amperios (A).
    - CONVERSIÓN DE RESISTENCIA: Si la resistencia de devanados está en miliohmios (mΩ), divide entre 1000 para reportar en Ohmios (Ω).
    - ORDEN DE TAPS: Siempre ordena de menor a mayor (Tap 1, 2, 3... hacia arriba).
    - NÚMEROS LIMPIOS: Quita el símbolo '%' de los porcentajes de error o desbalance.
    - Asigna un nombre claro y técnico a cada prueba en 'nombre_prueba'.
    
    Estructura JSON requerida:
    {
      "tablas": [
        {
          "nombre_prueba": "1. Relación de Transformación (TTR)",
          "columnas": ["Tap", "Tensión AT (kV)", "Tensión MT (kV)", "Relación Teórica", "Relación U-O", "Error U", "Relación V-O", "Error V", "Relación W-O", "Error W"],
          "filas": [
             [1, 127.017, 36.061, 3.522, 3.516, -0.19, 3.517, -0.16, 3.515, -0.21]
          ]
        },
        {
          "nombre_prueba": "2. Corriente de Excitación",
          "columnas": ["Tap", "I Fase U (A)", "I Fase V (A)", "I Fase W (A)"],
          "filas": [
             [1, 0.00223, 0.00219, 0.00221]
          ]
        },
        {
          "nombre_prueba": "3. Resistencia de Devanados (AT y MT)",
          "columnas": ["Tap / Fase", "R Medida (Ω)", "R Corregida 75°C (Ω)", "Desbalance"],
          "filas": [
             ["Tap 1 - U-V", 0.0452, 0.0541, 0.35]
          ]
        }
      ]
    }
    """
    
    modelos_a_probar = ['gemini-3.5-flash-lite', 'gemini-3.5-flash']
    last_error = None

    for model_name in modelos_a_probar:
        for _ in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                        prompt
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                resultado = json.loads(response.text)
                if isinstance(resultado, dict):
                    return resultado.get("tablas", [resultado])
                elif isinstance(resultado, list):
                    return resultado
                return []
            except Exception as e:
                last_error = e
                time.sleep(1.5)
                continue
    raise last_error

# Procesamiento y visualización
if uploaded_file and api_key:
    mime = "application/pdf" if uploaded_file.name.lower().endswith(".pdf") else "image/png"
    if uploaded_file.name.lower().endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
        
    with st.spinner("⚡ Analizando todo el protocolo y extrayendo cada prueba técnica..."):
        try:
            lista_tablas = procesar_con_ia(uploaded_file.getvalue(), mime, api_key)

            if not lista_tablas:
                st.warning("No se encontraron tablas de pruebas en el documento.")
            else:
                st.success(f"✓ ¡Se identificaron {len(lista_tablas)} tablas de pruebas!")
                st.markdown("### Selecciona la prueba que deseas copiar:")

                # Crear una pestaña por cada prueba encontrada en el protocolo
                titulos_tabs = [f"📋 {t.get('nombre_prueba', f'Prueba {i+1}')}" for i, t in enumerate(lista_tablas)]
                tabs = st.tabs(titulos_tabs)

                for idx, tab in enumerate(tabs):
                    with tab:
                        t = lista_tablas[idx]
                        cols = t.get("columnas", [])
                        filas = t.get("filas", [])
                        df = pd.DataFrame(filas, columns=cols)

                        st.subheader(t.get("nombre_prueba", f"Prueba {idx+1}"))
                        
                        # Cuadro de copiado directo listo para Excel
                        tsv_data = df.to_csv(sep="\t", index=False)
                        st.code(tsv_data, language="text")
                        st.caption("👆 Haz clic en el icono de **Copiar** arriba a la derecha de este recuadro y presiona `Ctrl + V` en tu Excel compartido.")

                        st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(f"Error procesando el protocolo: {e}")
elif not api_key:
    st.info("💡 Pega tu API Key de Gemini en la barra lateral para comenzar.")
