import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="Sistema de Dosificación Log-Normal", layout="wide")

st.title("🚰 Calculadora de Dosificación de PAC — Modelo Log-Normal")
st.markdown("Modelo matemático continuo basado en la **Ley de Potencias para Coagulación** (Ajuste Log-Normal sobre datos históricos).")

# --- 1. CARGA Y AJUSTE MATEMÁTICO LOG-NORMAL ---
st.sidebar.header("📁 Base de Datos de Planta")
archivo_subido = st.sidebar.file_uploader("Subir archivo Excel (.xlsx)", type=["xlsx", "xls"])

nombre_archivo_local = "tabla_dosificacion.xlsx"

df = None
if archivo_subido is not None:
    df = pd.read_excel(archivo_subido)
    st.sidebar.success("¡Archivo cargado desde la web!")
elif os.path.exists(nombre_archivo_local):
    df = pd.read_excel(nombre_archivo_local)
    st.sidebar.info(f"Cargado archivo local: `{nombre_archivo_local}`")

if df is not None:
    # Limpiar nombres de columnas
    df.columns = df.columns.str.strip()
    
    col_agua = [c for c in df.columns if 'AGUA' in c.upper() or 'CRUDA' in c.upper()][0]
    col_turb = [c for c in df.columns if 'TURBIEDAD' in c.upper()][0]
    col_pac = [c for c in df.columns if 'POLICLORURO' in c.upper() or 'PAC' in c.upper()][0]
    col_polimero = [c for c in df.columns if 'POLIMERO' in c.upper()][0]
    col_cloro = [c for c in df.columns if 'CLORO' in c.upper()][0]
    col_cobre = [c for c in df.columns if 'COBRE' in c.upper()][0]

    # Excluir caudales atípicos de prueba/arranque (< 3000 m3/día)
    df_clean = df[df[col_agua] >= 3000].copy()

    # Cálculo de Dosis mg/L e Insumos Secundarios g/m3
    df_clean['DOSIS_PAC_MGL'] = (df_clean[col_pac] * 1000.0) / df_clean[col_agua]
    df_clean['POLIMERO_G_M3'] = (df_clean[col_polimero] * 1000.0) / df_clean[col_agua]
    df_clean['CLORO_G_M3'] = (df_clean[col_cloro] * 1000.0) / df_clean[col_agua]
    df_clean['COBRE_G_M3'] = (df_clean[col_cobre] * 1000.0) / df_clean[col_agua]

    # Ajuste por Regresión Log-Lineal (Distribución Log-Normal)
    valid_df = df_clean[(df_clean[col_turb] > 0) & (df_clean['DOSIS_PAC_MGL'] > 0)]
    
    log_turb = np.log(valid_df[col_turb])
    log_dosis_pac = np.log(valid_df['DOSIS_PAC_MGL'])
    
    # Parámetros de la regresión
    beta_1, beta_0 = np.polyfit(log_turb, log_dosis_pac, 1)

    # --- 2. ENTRADA DE DATOS OPERATIVOS ---
    st.sidebar.header("⚙️ Parámetros Actuales")
    
    modo_caudal = st.sidebar.radio("Modo de Ingreso de Caudal:", ["Diario (m³/día)", "Horario (m³/h)"])
    if modo_caudal == "Diario (m³/día)":
        caudal_m3dia = st.sidebar.number_input("Caudal de Entrada (m³/día)", min_value=10.0, max_value=100000.0, value=14000.0, step=100.0)
        caudal_m3h = caudal_m3dia / 24.0
    else:
        caudal_m3h = st.sidebar.number_input("Caudal de Entrada (m³/h)", min_value=1.0, max_value=5000.0, value=583.33, step=10.0)
        caudal_m3dia = caudal_m3h * 24.0

    caudal_ls = caudal_m3h / 3.6
    st.sidebar.caption(f"**Régimen:** `{caudal_m3h:.2f} m³/h` | `{caudal_ls:.2f} L/s`")

    # Turbiedad
    st.sidebar.header("💧 Control de Turbiedad")
    ntu_max_entrada = st.sidebar.number_input("Turbiedad Máxima Entrada (NTU)", min_value=0.1, max_value=2000.0, value=50.0, step=0.5)
    ntu_tratada = st.sidebar.number_input("Turbiedad Agua Tratada (NTU)", min_value=0.0, max_value=100.0, value=0.8, step=0.1)

    st.sidebar.header("🧪 Ajustes de Coagulante")
    pureza_pac = st.sidebar.number_input("Pureza Comercial del PAC (%)", min_value=1.0, max_value=100.0, value=100.0, step=1.0)
    factor_ajuste = st.sidebar.slider("Ajuste Manual Fino (Trim ±%)", min_value=-30, max_value=30, value=0, step=1)
    peso_saco_kg = st.sidebar.number_input("Peso por Saco de PAC (kg)", min_value=1.0, max_value=50.0, value=25.0, step=1.0)

    # Tanque de Carga Fijo 3 m3 Rectangular
    vol_cuba_m3 = 3.0
    vol_cuba_litros = 3000.0
    st.sidebar.info("📐 **Tanque de Carga:** Rectangular Fijo de 3.0 m³ (3,000 L)")

    # --- 3. CÁLCULO MEDIANTE MODELO LOG-NORMAL ---
    # Dosis de PAC predicha por el modelo exponencial log-normal
    dosis_pac_lognormal_mgl = np.exp(beta_0) * (ntu_max_entrada ** beta_1)

    # Dosis final con pureza y ajuste manual
    dosis_pac_final_mgl = (dosis_pac_lognormal_mgl / (pureza_pac / 100.0)) * (1.0 + (factor_ajuste / 100.0))

    # Balance de Masa
    kg_pac_dia = (caudal_m3dia * dosis_pac_final_mgl) / 1000.0
    kg_pac_hora = kg_pac_dia / 24.0
    sacos_pac_dia = kg_pac_dia / peso_saco_kg

    # Insumos Secundarios basados en la mediana histórica por turbiedad
    dosis_polimero_gm3 = valid_df['POLIMERO_G_M3'].median()
    dosis_cloro_gm3 = valid_df['CLORO_G_M3'].median()
    dosis_cobre_gm3 = valid_df['COBRE_G_M3'].median()

    kg_polimero_dia = (caudal_m3dia * dosis_polimero_gm3) / 1000.0
    kg_cloro_dia = (caudal_m3dia * dosis_cloro_gm3) / 1000.0
    kg_cobre_dia = (caudal_m3dia * dosis_cobre_gm3) / 1000.0

    # Eficiencia de remoción de turbiedad
    eficiencia_remocion = ((ntu_max_entrada - ntu_tratada) / ntu_max_entrada) * 100.0 if ntu_max_entrada > 0 else 0.0

    # --- 4. PRESENTACIÓN DE RESULTADOS ---
    st.header("📊 Indicadores Principales de Operación")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Caudal de Entrada", f"{caudal_m3h:.1f} m³/h", f"{caudal_m3dia:.0f} m³/día")
    m2.metric("Dosis Log-Normal PAC", f"{dosis_pac_final_mgl:.2f} mg/L", f"Base Exponencial")
    m3.metric("Consumo Diario PAC", f"{kg_pac_dia:.2f} kg/día", f"{kg_pac_hora:.2f} kg/h")
    m4.metric("Sacos Requeridos", f"{sacos_pac_dia:.2f} sacos/día", f"Sacos de {peso_saco_kg:.0f} kg")

    if eficiencia_remocion >= 85.0:
        m5.metric("Eficiencia Remoción", f"{eficiencia_remocion:.1f} %", "Excelente", delta_color="normal")
    elif eficiencia_remocion >= 70.0:
        m5.metric("Eficiencia Remoción", f"{eficiencia_remocion:.1f} %", "Aceptable", delta_color="off")
    else:
        m5.metric("Eficiencia Remoción", f"{eficiencia_remocion:.1f} %", "Baja / Revisar", delta_color="inverse")

    st.divider()

    # Insumos Secundarios Proporcionales
    st.subheader("📦 Estimación Proporcional de Químicos (24 Horas)")
    col_q1, col_q2, col_q3, col_q4 = st.columns(4)
    col_q1.success(f"**PAC Comercial:**\n# {kg_pac_dia:.2f} kg/día ({sacos_pac_dia:.1f} sacos)")
    col_q2.info(f"**Polímero:**\n# {kg_polimero_dia:.2f} kg/día")
    col_q3.warning(f"**Cloro Gas:**\n# {kg_cloro_dia:.2f} kg/día")
    col_q4.error(f"**Sulfato de Cobre:**\n# {kg_cobre_dia:.2f} kg/día")

    st.divider()

    # Operación de Cuba Fija (3 m3 Rectangular)
    st.subheader("🧪 Preparación en Tanque Rectangular de 3 m³ (3,000 L) y Set de Bomba")
    conc_pac_cuba = st.number_input("Concentración de la Solución de PAC en Tanque (%)", min_value=0.5, max_value=20.0, value=5.0, step=0.5)

    flujo_bomba_lh = (caudal_m3h * dosis_pac_final_mgl) / (conc_pac_cuba * 10.0) if conc_pac_cuba > 0 else 0.0
    kg_pac_por_cuba = vol_cuba_litros * (conc_pac_cuba / 100.0)
    autonomia_horas = (vol_cuba_litros / flujo_bomba_lh) if flujo_bomba_lh > 0 else 0.0

    b1, b2, b3 = st.columns(3)
    b1.info(f"**Pesaje de PAC por Tanque (3,000 L al {conc_pac_cuba:.1f}%):**\n# {kg_pac_por_cuba:.2f} kg PAC")
    b2.success(f"**Ajuste Bomba Dosificadora:**\n# {flujo_bomba_lh:.2f} L/h")
    b3.warning(f"**Autonomía del Tanque:**\n# {autonomia_horas:.1f} Horas")

    st.divider()

    # Ecuación del Modelo
    st.subheader("📐 Ecuación del Modelo Ajustado")
    st.latex(r"\text{Dosis (mg/L)} = " + f"{np.exp(beta_0):.3f} \\times (\\text{{Turbiedad}})^{{{beta_1:.4f}}}")

else:
    st.warning("⚠️ Sube el archivo Excel o mantén `tabla_dosificacion.xlsx` en la carpeta.")