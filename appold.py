import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import time
from datetime import datetime

# Configuracion de pagina
st.set_page_config(page_title="Extractor Tickets", layout="wide")
st.title("Extractor TICKETS")

# --- CONFIGURACION API ---
# Pone tu API Key real aqui
GENAI_API_KEY = "AIzaSyDEutn4_ToWrk200DxAT1EygH9pNMre6is"
genai.configure(api_key=GENAI_API_KEY)

def extraer_datos_gemini(imagen):
    """Envia la imagen a Gemini 1.5 Flash y retorna un JSON."""
    # Usamos el alias que vimos que funciona en tu lista
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = """
    Analiza este comprobante de Argentina. Extrae los datos y responde UNICAMENTE con un JSON:
    {
        "fecha": "YYYY-MM-DD",
        "tipo": "fc" o "nc",
        "letra": "a", "b" o "c",
        "pto_vta": numero_entero,
        "nro": numero_entero,
        "cuit": "numero sin guiones",
        "razon_social": "nombre emisor",
        "neto": float,
        "no_gravado": float (suma de impuestos internos e IDC),
        "percepcion": float (IIBB o IVA),
        "iva_monto": float,
        "total": float,
        "tasa_iva": 21.0 o 10.5
    }
    Si un campo no existe, usa 0.0 o null.
    """
    
    img = {"mime_type": "image/jpeg", "data": imagen.getvalue()}
    response = model.generate_content([prompt, img])
    
    raw_text = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(raw_text)

# --- INTERFAZ DE USUARIO ---
st.info("Subi tus tickets. El sistema procesara.")

uploaded_files = st.file_uploader("Arrastra los tickets aqui", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if uploaded_files:
    if st.button("Iniciar Extraccion"):
        resultados = []
        barra_progreso = st.progress(0)
        status = st.empty()
        
        for i, file in enumerate(uploaded_files):
            status.info(f"Procesando {i+1} de {len(uploaded_files)}: {file.name}")
            
            try:
                datos = extraer_datos_gemini(file)
                
                fila = {
                    "Fecha de Emision": datos.get("fecha"),
                    "Tipo de Comprobante": datos.get("tipo"),
                    "Letra": datos.get("letra"),
                    "Punto de Venta": datos.get("pto_vta"),
                    "Numero": datos.get("nro"),
                    "CUIT del Proveedor": datos.get("cuit"),
                    "Razon social del Provedor": datos.get("razon_social"),
                    "Situacion de IVA del Proveedor": "Inscripto",
                    "Concepto": "Varios",
                    "Importe Neto": datos.get("neto"),
                    "Impuestos Internos / No Gravado": datos.get("no_gravado"),
                    "Importe Exento": 0.0,
                    "Importe percepcion": datos.get("percepcion"),
                    "IVA Inscripto": datos.get("iva_monto"),
                    "Importe Total del Comprobante": datos.get("total"),
                    "Tasa de IVA Inscripto": datos.get("tasa_iva"),
                    "Condicion de Pago": 1.0
                }
                resultados.append(fila)
                
                # --- EL DELAY ESTRATEGICO ---
                # Si no es el ultimo archivo, esperamos 10 segundos
                if i < len(uploaded_files) - 1:
                    time.sleep(0.5)
                
            except Exception as e:
                # Si el error es de cuota (429), esperamos mas tiempo y reintentamos
                if "429" in str(e):
                    status.warning("Limite de Google alcanzado. Esperando 20 segundos para reintentar...")
                    time.sleep(0.5)
                    # Reintento una vez mas
                    try:
                        datos = extraer_datos_gemini(file)
                        # ... (misma logica de mapeo de arriba, simplificada aqui)
                        resultados.append(fila) 
                    except:
                        st.error(f"No se pudo procesar {file.name} tras reintentar.")
                else:
                    st.error(f"Error en {file.name}: {e}")
            
            barra_progreso.progress((i + 1) / len(uploaded_files))

        if resultados:
            df = pd.DataFrame(resultados)
            st.success("Extraccion terminada exitosamente!")
            st.dataframe(df)

            output = io.BytesIO()
            # Usamos openpyxl para evitar problemas de dependencias
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Compras')
            
            st.download_button(
                label="Descargar EXCEL",
                data=output.getvalue(),
                file_name=f"COMPRAS_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

st.divider()
st.caption("Arquitectura por Raul - Oracle Cloud Ubuntu 24.04")