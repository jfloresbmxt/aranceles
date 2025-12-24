import streamlit as st
import pandas as pd
import numpy as np
import os

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE LA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Dashboard Arancelario Integral")

st.title("📊 Monitor de Comercio y Aranceles: México - EUA")

# -----------------------------------------------------------------------------
# 2. FUNCIONES DE LIMPIEZA Y CARGA
# -----------------------------------------------------------------------------

def clean_percentage(val):
    """Convierte strings como '15%', 'Ex.', 'Libre' a flotantes. Ex/Libre = 0."""
    if pd.isna(val):
        return None
    val = str(val).strip().lower()
    if 'ex' in val or 'libre' in val or 'free' in val:
        return 0.0
    try:
        return float(val.replace('%', '').strip())
    except ValueError:
        return None

def calculate_hts_sum(row):
    """Suma las tarifas de EU ignorando textos y excluyendo la 232."""
    cols_to_sum = ['EU General', 'EU 301', 'Recíproco', 'Fentanilo']
    total = 0.0
    valid_number_found = False
    
    for col in cols_to_sum:
        val = row.get(col, 0)
        cleaned_val = clean_percentage(val)
        if cleaned_val is not None:
            total += cleaned_val
            valid_number_found = True
            
    return total if valid_number_found else None

@st.cache_data
def load_data():
    # 1. Obtiene la ruta absoluta de la carpeta donde vive main.py
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Construye la ruta al excel
    file_path = os.path.join(base_path, 'data', 'LIGIE_HTS_Dashboard.xlsx')
    
    # --- DEBUGGING (Verás esto en los logs de Streamlit si falla) ---
    print(f"Ruta construida: {file_path}")
    if not os.path.exists(file_path):
        print(f"¡ALERTA! El archivo no existe en: {file_path}")
        print(f"Contenido de {base_path}: {os.listdir(base_path)}")
        if os.path.exists(os.path.join(base_path, 'data')):
             print(f"Contenido de data: {os.listdir(os.path.join(base_path, 'data'))}")
    # ----------------------------------------------------------------
    
    # 1. Carga LIGIE
    ligie = pd.read_excel(file_path, sheet_name='LIGIE', dtype=str)
    
    # 2. Carga HTS
    hts = pd.read_excel(file_path, sheet_name='HTS', dtype=str)
    hts = hts.drop(columns=['#'], errors='ignore')
    hts = hts.drop(index=[0], errors='ignore')
    hts = hts.rename(columns={'EU IEEPA': 'Recíproco', 'Unnamed: 12' : 'Fentanilo'})
    hts = hts.ffill()

    # 3. Carga Datos Financieros (Participación)
    part = pd.read_excel(file_path, sheet_name='Participación')
    part['Date'] = pd.to_datetime(part['Date'])
    part['Subpartida'] = part['Subpartida'].astype(str).str.zfill(6)
    part.columns = part.columns.str.strip()

    # 4. Carga Aranceles Efectivos
    # Columnas esperadas: Subpartida, date, Mexico, China
    aranceles = pd.read_excel(file_path, sheet_name='Aranceles efectivos')
    
    if 'date' in aranceles.columns:
        aranceles.rename(columns={'date': 'Date'}, inplace=True)
    
    aranceles['Date'] = pd.to_datetime(aranceles['Date'])
    aranceles['Subpartida'] = aranceles['Subpartida'].astype(str).str.zfill(6)

    return ligie, hts, part, aranceles

try:
    ligie, hts, part, aranceles = load_data()
except Exception as e:
    st.error(f"Error al cargar los archivos: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. INTERFAZ Y LÓGICA
# -----------------------------------------------------------------------------

st.sidebar.header("Búsqueda")
hs6_input = st.sidebar.text_input("Ingresa la Subpartida (6 Dígitos):", max_chars=6, placeholder="Ej: 870321")

if st.sidebar.button("Buscar") or hs6_input:
    hs6_input = hs6_input.strip()

    # =========================================================================
    # SECCIÓN 1: MÓDULO LIGIE (MÉXICO)
    # =========================================================================
    st.header("🇲🇽 Módulo LIGIE (México)")
    
    ligie_filtrado = ligie[ligie['HS6 México'] == hs6_input].copy()

    if not ligie_filtrado.empty:
        desc_hs2 = ligie_filtrado['Descripción HS2'].iloc[0] if 'Descripción HS2' in ligie_filtrado else "N/A"
        desc_hs4 = ligie_filtrado['Descripción HS4'].iloc[0] if 'Descripción HS4' in ligie_filtrado else "N/A"
        desc_hs6 = ligie_filtrado['Descripción HS6'].iloc[0]

        with st.expander("📂 Detalles de la Clasificación (Jerarquía)", expanded=True):
            st.markdown(f"**Capítulo:** {desc_hs2}")
            st.markdown(f"**Partida:** {desc_hs4}")
            st.markdown(f"**Subpartida ({hs6_input}):** {desc_hs6}")

        # Cálculo de TOTAL y Promedio
        ligie_filtrado['LIGIE_Num'] = ligie_filtrado['LIGIE'].apply(clean_percentage)
        ligie_filtrado['TOTAL'] = ligie_filtrado['LIGIE_Num'] 
        
        avg_ligie = ligie_filtrado['TOTAL'].mean()

        col1, col2 = st.columns([1, 3])
        with col1:
            st.metric("Promedio Arancel LIGIE", f"{avg_ligie:,.2f}%" if pd.notna(avg_ligie) else "N/A")
        
        with col2:
            cols_show = ['HS8 México', 'Descripción HS8', 'LIGIE', 'TOTAL']
            st.dataframe(
                ligie_filtrado[cols_show].style.format({'TOTAL': '{:.2f}%'}), 
                use_container_width=True, 
                hide_index=True
            )
    else:
        st.warning(f"No se encontró información LIGIE para {hs6_input}")

    st.markdown("---")

    # =========================================================================
    # SECCIÓN 2: MÓDULO HTS (ESTADOS UNIDOS)
    # =========================================================================
    st.header("🇺🇸 Módulo HTS (Estados Unidos)")
    
    hts_filtrado = hts[hts['HS6'] == hs6_input].copy()

    if not hts_filtrado.empty:
        desc_hs2_us = hts_filtrado['Descripción HS2'].iloc[0] if 'Descripción HS2' in hts_filtrado else "N/A"
        desc_hs4_us = hts_filtrado['Descripción HS4'].iloc[0] if 'Descripción HS4' in hts_filtrado else "N/A"
        desc_hs6_us = hts_filtrado['Descripción HS6'].iloc[0]

        with st.expander("📂 Classification Details (Hierarchy)", expanded=False):
            st.markdown(f"**Chapter:** {desc_hs2_us}")
            st.markdown(f"**Heading:** {desc_hs4_us}")
            st.markdown(f"**Subheading ({hs6_input}):** {desc_hs6_us}")

        # --- A. TABLA DE ARANCELES ---
        hts_filtrado['TOTAL'] = hts_filtrado.apply(calculate_hts_sum, axis=1)
        avg_hts = hts_filtrado['TOTAL'].mean()

        st.subheader("1. Desglose Arancelario")
        col_m1, col_m2 = st.columns([1, 3])
        with col_m1:
            st.metric("Promedio Total Aranceles (Excl. 232)", f"{avg_hts:,.2f}%" if pd.notna(avg_hts) else "N/A")
        
        with col_m2:
            cols_hts_show = ['HS8 Estados Unidos', 'Descripción HS8', 'EU General', 'EU 301', 'EU 232', 'Recíproco', 'Fentanilo', 'TOTAL']
            st.dataframe(
                hts_filtrado[cols_hts_show].style.format({'TOTAL': '{:.2f}%'}), 
                use_container_width=True, 
                hide_index=True
            )

        # --- B. CUADRO RESUMEN (Participación + Efectivos) ---
        st.subheader("2. Resumen de Desempeño: México vs. China")

        # 1. Datos de Participación
        df_part_sub = part[part['Subpartida'] == hs6_input].sort_values('Date').copy()
        
        # 2. Datos de Aranceles Efectivos
        df_aranceles_sub = aranceles[aranceles['Subpartida'] == hs6_input].sort_values('Date').copy()

        if not df_part_sub.empty and not df_aranceles_sub.empty:
            
            # --- CÁLCULOS PARTICIPACIÓN ---
            cols_num = ['Mexico', 'Total', 'China']
            for col in cols_num:
                if col in df_part_sub.columns:
                    df_part_sub[col] = pd.to_numeric(df_part_sub[col], errors='coerce').fillna(0)
            
            if 'Total' in df_part_sub.columns and 'Mexico' in df_part_sub.columns:
                df_part_sub['Market_Share_Mex'] = df_part_sub.apply(lambda x: (x['Mexico'] / x['Total'] * 100) if x['Total'] > 0 else 0, axis=1)
                df_part_sub['Market_Share_China'] = df_part_sub.apply(lambda x: (x['China'] / x['Total'] * 100) if x['Total'] > 0 else 0, axis=1)
            
            # Estadísticas Participación
            last_row_part = df_part_sub.iloc[-1]
            last_date_part = last_row_part['Date'].strftime('%B %Y')
            df_12m_part = df_part_sub.iloc[-12:]

            # --- CÁLCULOS ARANCELES EFECTIVOS (CORRECCIÓN * 100) ---
            cols_eff = ['Mexico', 'China']
            for col in cols_eff:
                 if col in df_aranceles_sub.columns:
                    # Multiplicamos por 100 aquí para corregir la escala (0.46 -> 46.0)
                    df_aranceles_sub[col] = pd.to_numeric(df_aranceles_sub[col], errors='coerce').fillna(0) * 100

            last_row_ara = df_aranceles_sub.iloc[-1]
            df_12m_ara = df_aranceles_sub.iloc[-12:]

            # --- CONSTRUCCIÓN TABLA RESUMEN DESGLOSADA ---
            # Extraemos valores para México
            mx_money_last = last_row_part.get('Mexico', 0)
            mx_money_avg  = df_12m_part['Mexico'].mean()
            mx_share_last = last_row_part.get('Market_Share_Mex', 0)
            mx_share_avg  = df_12m_part['Market_Share_Mex'].mean()
            mx_tariff_last = last_row_ara.get('Mexico', 0)
            mx_tariff_avg  = df_12m_ara['Mexico'].mean()

            # Extraemos valores para China
            cn_money_last = last_row_part.get('China', 0)
            cn_money_avg  = df_12m_part['China'].mean()
            cn_share_last = last_row_part.get('Market_Share_China', 0)
            cn_share_avg  = df_12m_part['Market_Share_China'].mean()
            cn_tariff_last = last_row_ara.get('China', 0)
            cn_tariff_avg  = df_12m_ara['China'].mean()

            resumen_data = {
                'Concepto': [f"Último Dato ({last_date_part})", "Promedio 12 Meses"],
                
                # Columnas México
                'Part. $ (Mx)': [f"${mx_money_last:,.2f}", f"${mx_money_avg:,.2f}"],
                'Share % (Mx)': [f"{mx_share_last:,.2f}%", f"{mx_share_avg:,.2f}%"],
                'Arancel % (Mx)': [f"{mx_tariff_last:,.2f}%", f"{mx_tariff_avg:,.2f}%"],
                
                # Columnas China
                'Part. $ (Ch)': [f"${cn_money_last:,.2f}", f"${cn_money_avg:,.2f}"],
                'Share % (Ch)': [f"{cn_share_last:,.2f}%", f"{cn_share_avg:,.2f}%"],
                'Arancel % (Ch)': [f"{cn_tariff_last:,.2f}%", f"{cn_tariff_avg:,.2f}%"]
            }
            
            st.table(pd.DataFrame(resumen_data))
            
            # --- C. GRÁFICAS ---
            st.subheader("3. Análisis Histórico: México vs China")
            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                st.markdown("**Participación de Mercado (%)**")
                chart_data_share = df_part_sub[['Date', 'Market_Share_Mex', 'Market_Share_China']].set_index('Date')
                chart_data_share.columns = ['México', 'China']
                st.line_chart(chart_data_share, color=["#006400", "#FF0000"]) 

            with col_chart2:
                st.markdown("**Arancel Efectivo (%)**")
                # Graficamos los datos ya multiplicados por 100
                chart_data_tariff = df_aranceles_sub[['Date', 'Mexico', 'China']].set_index('Date')
                chart_data_tariff.columns = ['México', 'China']
                st.line_chart(chart_data_tariff, color=["#006400", "#FF0000"])
        
        else:
            st.info("No se encontraron datos históricos completos.")
    else:
        st.warning(f"No se encontró información HTS para {hs6_input}")

else:
    st.info("👈 Ingresa una subpartida para comenzar.")