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
    Eres un ingeniero especialista en ensayos y protocolos FAT de transformadores de potencia (Megger TRAX, OMICRON CPC 100 / TESTRANO, Doble, Vanguard).
    Analiza este documento completo y extrae de forma INDEPENDIENTE todas las tablas de pruebas presentes que correspondan a:
    
    1. Relación de Transformación (TTR) y Polaridad:
       - Extrae Taps (orden ascendente), voltajes teóricos, relación medida y error porcentual por fase.
       
    2. Corriente de Excitación en Alta Tensión (Regla Universal para TRAX, OMICRON, Doble):
       - REGLA CRÍTICA DE SELECCIÓN: Extrae ÚNICAMENTE la prueba real de excitación realizada a alta tensión nominal de ensayo (~10 kV o 10000 V).
       - En formatos TRAX: Esta prueba aparece habitualmente bajo el encabezado 'Tangente delta - Prueba Manual' con notas/comentarios como 'MEDICION DE CORRIENTE DE EXCITACION AT' y comentarios de fase por Tap ('U-N TAP-1', 'V-N TAP-14', etc.).
       - En formatos OMICRON/Doble: Se titula 'Excitation Current', 'Corriente de Excitación' o similar a 10 kV.
       - REGLA DE EXCLUSIÓN: NUNCA tomes la columna secundaria 'I Exc' presente en las tablas de TTR (relación de transformación), ya que esa prueba se inyecta a baja tensión (50 V - 80 V) y produce corrientes auxiliares diminutas (~1 a 3 mA).
       - Consolida una sola tabla por cada Tap con columnas: ["Tap", "Tensión (kV)", "Fase U (A)", "Fase V (A)", "Fase W (A)", "Potencia P (W)"].
       - Si las fases vienen en filas separadas o en orden inverso (ej. Tap 27 al 1), consolídalas y ordénalas ascendentemente por Tap (Tap 1, 2, ...).
       - CONVERSIÓN: Divide los mA entre 1000 para reportar en Amperios (A).

    3. Resistencia de Devanados en CC:
       - Mediciones de AT por cada Tap medido (U-O, V-O, W-O o entre fases) y devanados de MT/BT.
       - CONVERSIÓN: Divide los mΩ entre 1000 para reportar en Ohmios (Ω).

    4. Resistencia de Aislamiento:
       - Valores de resistencia (MΩ/GΩ), corrientes de fuga (nA), índices IP e IA, y aislamiento de Núcleo-Armadura/Masa si están presentes.

    5. Factor de Potencia y Capacitancia de Devanados (10 kV):
       - Extrae obligatoriamente dos tablas independientes si ambas existen en el documento:
         a) "5a. Factor de Potencia y Capacitancia de Devanados (Antes de pruebas dieléctricas)"
         b) "5b. Factor de Potencia y Capacitancia de Devanados (Después de pruebas dieléctricas)"
       - CONDICIÓN DE TENSIÓN: Extrae los registros evaluados a tensión nominal de 10 kV (10000 V / 10 kV). Si el reporte incluye barridos a 2 kV y 10 kV, prioriza el escalón de 10 kV.
       - Incluye: Aislamiento (CH, CL, CT, CHL, CHT, CLT), Modo (UST/GST), Tensión (kV), %FP corregido a 20°C y Capacitancia (pF).

    6. Factor de Potencia y Capacitancia de Bushings C1 y C2 (Antes y Después a 10 kV):
       - Mediciones de bornes a 10 kV si están presentes.

    Reglas obligatorias de formato:
    - CONVERSIONES: Corrientes en Amperios (A), Resistencias de devanados en Ohmios (Ω).
    - ORDEN: Todos los Taps ordenados de menor a mayor.
    - NÚMEROS LIMPIOS: Quita el símbolo '%' de cualquier porcentaje (errores, FP, desbalances) para que en Excel sean números operables.
    - Asigna nombres técnicos claros en 'nombre_prueba'.

    Estructura JSON requerida:
    {
      "tablas": [
        {
          "nombre_prueba": "2. Corriente de Excitación - AT (10 kV)",
          "columnas": ["Tap", "Tensión (kV)", "Fase U-N (A)", "Fase V-N (A)", "Fase W-N (A)", "Potencia P (W)"],
          "filas": [
             [1, 10.0, 0.05850, 0.04155, 0.05904, 449.8],
             [14, 10.0, 0.07412, 0.05355, 0.07436, 562.8]
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

                titulos_tabs = [f"📋 {t.get('nombre_prueba', f'Prueba {i+1}')}" for i, t in enumerate(lista_tablas)]
                tabs = st.tabs(titulos_tabs)

                for idx, tab in enumerate(tabs):
                    with tab:
                        t = lista_tablas[idx]
                        cols = t.get("columnas", [])
                        filas = t.get("filas", [])
                        df = pd.DataFrame(filas, columns=cols)

                        st.subheader(t.get("nombre_prueba", f"Prueba {idx+1}"))
                        
                        tsv_data = df.to_csv(sep="\t", index=False)
                        st.code(tsv_data, language="text")
                        st.caption("👆 Haz clic en el icono de **Copiar** arriba a la derecha de este recuadro y presiona `Ctrl + V` en tu Excel compartido.")

                        st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(f"Error procesando el protocolo: {e}")
elif not api_key:
    st.info("💡 Pega tu API Key de Gemini en la barra lateral para comenzar.")
