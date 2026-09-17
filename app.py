import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import io
import json
import time

st.set_page_config(page_title="Extractor de Protocolos FAT - Transformadores", layout="wide")
st.title("⚡ Extractor de Protocolos de Transformadores a Excel")

api_key = st.secrets.get("GEMINI_API_KEY") or st.sidebar.text_input("Ingresa tu Gemini API Key:", type="password")

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
       - EXTRAE TODAS LAS PRUEBAS DE TTR PRESENTES: Si el reporte contiene mediciones entre diferentes devanados (por ejemplo, AT vs MT y AT vs BT/Terciario), genera una tabla independiente para cada una.
       - Asigna títulos diferenciados: ej. "1a. TTR - AT vs MT" y "1b. TTR - AT vs BT".
       - CONSOLIDACIÓN TRIFÁSICA OBLIGATORIA: Cada fila debe ser un Tap con las columnas: ["Tap", "Tensión AT (V)", "Relación Teórica", "Rel. Medida U", "Error U", "Rel. Medida V", "Error V", "Rel. Medida W", "Error W"].
       - En las pruebas completas (como AT-BT en páginas 11 a 13 del TRAX), extrae minuciosamente todos los Taps del 1 al 27 sin omitir ninguno.
       - Elimina el símbolo '%'.
       
    2. Corriente de Excitación en Alta Tensión (Universal para TRAX, OMICRON, Doble):
       - REGLA DE SELECCIÓN: Extrae ÚNICAMENTE la prueba real de excitación realizada a alta tensión nominal de ensayo (~10 kV o 10000 V).
       - En TRAX: Viene como 'Tangente delta - Prueba Manual' con notas 'MEDICION DE CORRIENTE DE EXCITACION AT' y comentarios de fase por Tap ('U-N TAP-1', 'V-N TAP-27', etc.).
       - REGLA CRÍTICA DE FASES INVERSAS: Observa minuciosamente todas las filas de la prueba. Algunas fases (frecuentemente V-N) se ensayan en orden descendente, por lo que el registro de TAP-27 puede aparecer al inicio de la fase (ej: 'V-N TAP-27' con ~70 mA). NO dejes celdas vacías ni 'None'; empareja cada Tap con su valor correspondiente.
       - REGLA DE EXCLUSIÓN: NUNCA tomes la columna 'I Exc' de las tablas de TTR (esa es a 50-80 V con valores de ~1-3 mA).
       - Consolida una sola tabla por cada Tap con columnas: ["Tap", "Tensión (kV)", "Fase U-N (A)", "Fase V-N (A)", "Fase W-N (A)", "Potencia P (W)"].
       - CONVERSIÓN: Convierte estrictamente los mA a Amperios (A) dividiendo entre 1000.
       - Ordena siempre las filas en orden ascendente por Tap (Tap 1, 2, ...).

    3. Resistencia de Devanados en CC:
       - Extrae tanto el devanado de Alta Tensión (AT por Taps) como los devanados de Media Tensión (MT) y Baja Tensión / Terciario (BT) presentes en el documento.
       - Si vienen en secciones separadas, consolídalas en una sola tabla o en tablas contiguas: ["Devanado / Conexión", "Tap", "Corriente (A)", "R Medida (Ω)", "Desviación (%)"].
       - CONVERSIÓN: Divide los mΩ entre 1000 para reportar en Ohmios (Ω).

    4. Resistencia de Aislamiento:
       - Valores de resistencia (MΩ/GΩ), corrientes de fuga (nA), índices IP e IA, y aislamiento de Núcleo-Armadura/Masa si están presentes.

    5. Factor de Potencia y Capacitancia de Devanados (10 kV):
       - Extrae tablas independientes si existen ambas:
         a) "5a. Factor de Potencia y Capacitancia de Devanados (Antes de pruebas dieléctricas)"
         b) "5b. Factor de Potencia y Capacitancia de Devanados (Después de pruebas dieléctricas)"
       - CONDICIÓN DE TENSIÓN: Extrae los registros evaluados a tensión nominal de 10 kV (10000 V / 10 kV).
       - REGLA CRÍTICA DE CONVERSIÓN DE CAPACITANCIA:
         * La capacitancia debe reportarse siempre en picofaradios (pF).
         * Si el reporte expresa la capacitancia en nanofaradios (nF), MULTIPLICA POR 1000 (ejemplo: 22.20 nF -> 22200 pF; 19.47 nF -> 19470 pF; 2.739 nF -> 2739 pF).
         * Si ya está en pF (o P@F), mantén el valor numérico directo.
       - Columnas requeridas: ["Conexión / Aislamiento", "Modo", "Tensión (kV)", "I (mA)", "Capacitancia (pF)", "%FP@20°C"].

    6. Factor de Potencia y Capacitancia de Bushings C1 y C2 (Antes y Después a 10 kV):
       - Mediciones de bornes a 10 kV si están presentes, con capacitancia en pF.

    Reglas obligatorias de formato:
    - CONVERSIONES: Corrientes de excitación en Amperios (A), Resistencias de devanados en Ohmios (Ω), Capacitancias en picofaradios (pF).
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
             [27, 10.0, 0.09595, 0.07004, 0.09627, 726.2]
          ]
        },
        {
          "nombre_prueba": "5a. Factor de Potencia y Capacitancia de Devanados (Antes - 10 kV)",
          "columnas": ["Conexión / Aislamiento", "Modo", "Tensión (kV)", "I (mA)", "Capacitancia (pF)", "%FP@20°C"],
          "filas": [
             ["CHG + CHL", "GSTg-B", 10.01, 83.71, 22200.0, 0.209],
             ["CHL", "UST-R", 10.01, 73.38, 19470.0, 0.206]
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

                # Generador de archivo Excel (.xlsx) con una pestaña por prueba
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    for i, t in enumerate(lista_tablas):
                        cols = t.get("columnas", [])
                        filas = t.get("filas", [])
                        df_sheet = pd.DataFrame(filas, columns=cols)
                        
                        raw_name = t.get("nombre_prueba", f"Prueba_{i+1}")
                        sheet_name = "".join([c for c in raw_name if c not in r"[]:*?/\\]"])[:30]
                        df_sheet.to_excel(writer, sheet_name=sheet_name, index=False)

                excel_bytes = output.getvalue()

                st.download_button(
                    label="📥 Descargar Protocolo Completo en Excel (.xlsx)",
                    data=excel_bytes,
                    file_name="Protocolo_Pruebas_Consolidado.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

                st.markdown("---")
                st.markdown("### O copia individualmente la prueba que necesites:")

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
