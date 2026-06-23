import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import time
from datetime import datetime

# --- CONFIGURACION ---
st.set_page_config(page_title="Extractor Tickets", layout="wide")
st.title("📸 Extractor de TICKETS a Formato ARCA")

GENAI_API_KEY = "AIzaSyDEutn4_ToWrk200DxAT1EygH9pNMre6is"
genai.configure(api_key=GENAI_API_KEY)

def extraer_datos_gemini(imagen):
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
        "no_gravado": float,
        "percepcion": float,
        "iva_monto": float,
        "total": float,
        "tasa_iva": 21.0, 10.5 o 27.0
    }
    Si es Factura B, calcula el neto e iva (total / 1.21).
    """
    img = {"mime_type": "image/jpeg", "data": imagen.getvalue()}
    response = model.generate_content([prompt, img])
    return json.loads(response.text.replace("```json", "").replace("```", "").strip())

def armar_fila_arca(datos):
    tasa = datos.get("tasa_iva", 0.0)
    neto = float(datos.get("neto", 0.0) or 0.0)
    iva = float(datos.get("iva_monto", 0.0) or 0.0)
    
    neto_21, iva_21 = (neto, iva) if tasa == 21.0 else (0.0, 0.0)
    neto_105, iva_105 = (neto, iva) if tasa == 10.5 else (0.0, 0.0)
    neto_27, iva_27 = (neto, iva) if tasa == 27.0 else (0.0, 0.0)
    
    fecha_val = datos.get("fecha")
    try:
        fecha_str = datetime.strptime(fecha_val, "%Y-%m-%d").strftime("%d/%m/%Y") if fecha_val else ""
    except:
        fecha_str = fecha_val or ""

    letra = str(datos.get("letra", "")).lower()
    if letra == "b":
        tipo_str = "6 - Factura B"
    elif letra == "a":
        tipo_str = "1 - Factura A"
    else:
        tipo_str = "11 - Factura C"

    # Mapeo exacto de las 28 columnas en el ORDEN ESTRICTO de ARCA para Recibidos (Compras)
    return {
        "Fecha": fecha_str,
        "Tipo": tipo_str,
        "Punto de Venta": datos.get("pto_vta") or 0,
        "Número Desde": datos.get("nro") or 0,
        "Número Hasta": datos.get("nro") or 0,
        "Cód. Autorización": "",
        "Tipo Doc. Emisor": "80", 
        "Nro. Doc. Emisor": datos.get("cuit") or "",
        "Denominación Emisor": datos.get("razon_social") or "",
        "Tipo Cambio": 1.0,
        "Moneda": "$",
        "Neto Grav. IVA 0%": 0.0,
        "IVA 2,5%": 0.0,
        "Neto Grav. IVA 2,5%": 0.0,
        "IVA 5%": 0.0,
        "Neto Grav. IVA 5%": 0.0,
        "IVA 10,5%": iva_105,
        "Neto Grav. IVA 10,5%": neto_105,
        "IVA 21%": iva_21,
        "Neto Grav. IVA 21%": neto_21,
        "IVA 27%": iva_27,
        "Neto Grav. IVA 27%": neto_27,
        "Neto Gravado Total": neto,
        "Neto No Gravado": float(datos.get("no_gravado", 0.0) or 0.0),
        "Op. Exentas": 0.0,
        "Otros Tributos": float(datos.get("percepcion", 0.0) or 0.0),
        "Total IVA": iva,
        "Imp. Total": float(datos.get("total", 0.0) or 0.0)
    }

# --- INTERFAZ ---
uploaded_files = st.file_uploader("Subí tus tickets", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if uploaded_files and st.button("🚀 Procesar Lote"):
    resultados = []
    barra = st.progress(0)
    
    for i, file in enumerate(uploaded_files):
        try:
            datos = extraer_datos_gemini(file)
            resultados.append(armar_fila_arca(datos))
            time.sleep(1) # Pequeña pausa para no saturar la cuota de la API
        except Exception as e:
            st.error(f"Error en {file.name}: {e}")
        barra.progress((i + 1) / len(uploaded_files))

    if resultados:
        df = pd.DataFrame(resultados)
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # ACA ESTA LA MAGIA: Agregamos "la fila" genérica en la primera posición (A1)
            pd.DataFrame([["Mis Comprobantes Recibidos"]]).to_excel(writer, index=False, header=False, startrow=0)
            
            # Y volcamos el DataFrame real a partir de la fila 2 (startrow=1)
            df.to_excel(writer, index=False, header=True, startrow=1, sheet_name='Sheet1')
        
        st.success("¡Lote extraído exitosamente!")
        st.download_button("📥 Descargar Excel para app1.py", output.getvalue(), "ARCA_TICKETS.xlsx")