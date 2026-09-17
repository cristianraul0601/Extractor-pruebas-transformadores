import streamlit as st
from google import genai
from google.genai import types
from streamlit_paste_button import paste_image_button as pbutton
import pandas as pd
import json
import io
import time

st.set_page_config(page_title="Extractor Rápido a Excel", layout="wide")
st.title("⚡ Copiador Rápido de Pruebas a Excel")

api_key = st.sidebar.text_input("Ingresa tu Gemini API Key:", type="password")

st.markdown("### 1. Pega tu captura de pantalla")
st.caption("Usa `Win + Shift + S` para recortar la tabla de tu prueba, luego presiona el botón:")

paste_result = pbutton(
    "📋 Pegar captura del portapapeles", 
    text_color="#FFFFFF", 
    background_color="#2F5597",
    hover_background_color="#1F3864"
)

uploaded_files = st.file_uploader(
    "O sube archivos si prefieres (PDF, JPG, PNG)", 
    type=["pdf", "jpg", "jpeg", "png"], 
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
    
    modelos_a_probar = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.6-flash']
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
img_data = None
mime = "image/png"

if paste_result.image_data is not None:
    img_bytes = io.BytesIO()
    paste_result.image_data.save(img_bytes, format='PNG')
    img_data = img_bytes.getvalue()
    mime = "image/png"
elif uploaded_files:
    img_data = uploaded_files.getvalue()
    mime = "application/pdf" if uploaded_files.name.lower().endswith(".pdf") else "image/jpeg"

if img_data and api_key:
    with st.spinner("⚡ Extrayendo y convirtiendo datos..."):
        try:
            datos = procesar_con_ia(img_data, mime, api_key)
            
            # Normalizar si vino como lista o dict
            if isinstance(datos, list) and len(datos) > 0:
                datos = datos[0]
            elif isinstance(datos, dict) and "tablas" in datos:
                datos = datos["tablas"][0]

            cols = datos.get("columnas", [])
            filas = datos.get("filas", [])
            df = pd.DataFrame(filas, columns=cols)

            st.success("✓ ¡Datos listos!")
            st.markdown("### 2. Copia tus datos:")

            # Opción 1: Texto listo para copiar al portapapeles
            texto_excel = df.to_csv(sep="\t", index=False)
            st.code(texto_excel, language="text")
            st.caption("👆 Puedes presionar el ícono de **Copiar** arriba a la derecha del recuadro gris y hacer `Ctrl + V` en tu Excel compartido.")

            # Opción 2: Tabla interactiva para copiar celdas específicas
            st.markdown("#### Vista en tabla:")
            st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(f"Error procesando la imagen: {e}")
elif not api_key:
    st.info("💡 Pega tu API Key de Gemini en la barra lateral para empezar.")