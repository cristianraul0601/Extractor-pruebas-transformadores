import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import io
import time

st.set_page_config(page_title="Extractor Rápido a Excel", layout="wide")
st.title("⚡ Copiador Rápido de Pruebas a Excel")

api_key = st.sidebar.text_input("Ingresa tu Gemini API Key:", type="password")

st.markdown("### Sube la captura de tu tabla o archivo")
uploaded_files = st.file_uploader(
    "Selecciona una o varias capturas/archivos (PNG, JPG, PDF):", 
    type=["png", "jpg", "jpeg", "pdf"], 
    accept_multiple_files=False
)

def procesar_con_ia(file_bytes, mime_type, api_key):
    client = genai.Client(api_key=api_key)
    
    prompt = """
    Analiza esta imagen/documento de prueba de transformadores eléctricos.
    Extrae la tabla con sus datos y devuélvela en formato JSON válido.
    
    Reglas obligatorias:
    1. Si la corriente está en mA, conviértela a A (divide entre 1000).
    2. Si la resistencia está en mΩ, conviértela a Ω (divide entre 1000).
    3. Ordena los Taps de menor a mayor (1 a 27).
    4. Quita el símbolo '%' de errores o desbalances numéricos.
    
    Estructura JSON:
    {
      "columnas": ["Tap", "Columna 1", "Columna 2"],
      "filas": [
         [1, 65.345, 3.267],
         [2, 64.780, 3.239]
      ]
    }
    """
    
    modelos_a_probar = ['gemini-2.5-flash', 'gemini-2.5-flash-lite']
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
                return json.loads(response.text)
            except Exception as e:
                last_error = e
                time.sleep(1.5)
                continue
    raise last_error

# Procesamiento
if uploaded_files and api_key:
    mime = "application/pdf" if uploaded_files.name.lower().endswith(".pdf") else "image/png"
    if uploaded_files.name.lower().endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
        
    with st.spinner("⚡ Extrayendo y convirtiendo datos..."):
        try:
            datos = procesar_con_ia(uploaded_files.getvalue(), mime, api_key)
            
            if isinstance(datos, list) and len(datos) > 0:
                datos = datos[0]
            elif isinstance(datos, dict) and "tablas" in datos:
                datos = datos["tablas"][0]

            cols = datos.get("columnas", [])
            filas = datos.get("filas", [])
            df = pd.DataFrame(filas, columns=cols)

            st.success("✓ ¡Datos listos!")
            st.markdown("### Copia tus datos:")

            texto_excel = df.to_csv(sep="\t", index=False)
            st.code(texto_excel, language="text")
            st.caption("👆 Presiona el ícono de **Copiar** arriba a la derecha y pega directo en tu Excel compartido.")

            st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(f"Error procesando el archivo: {e}")
elif not api_key:
    st.info("💡 Pega tu API Key de Gemini en la barra lateral para empezar.")
