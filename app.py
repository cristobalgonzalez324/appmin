import streamlit as st
import pandas as pd
import os
import io

st.set_page_config(page_title="Proyecto Minería - Forecast Avanzado", layout="wide")

@st.cache_data
def cargar_datos_sistema():
    ruta_base = os.getcwd()
    archivo_encontrado = None
    for root, dirs, files in os.walk(ruta_base):
        if '.git' in root: continue
        for f in files:
            if (f.endswith('.xlsx') or f.endswith('.xls')) and not f.startswith('~$'):
                archivo_encontrado = os.path.join(root, f)
                break
        if archivo_encontrado: break
            
    if not archivo_encontrado: return None, "Archivo no detectado"
        
    try:
        dict_hojas = pd.read_excel(archivo_encontrado, sheet_name=None)
        for nombre_hoja, df in dict_hojas.items():
            if not df.empty:
                if any(isinstance(col, str) and "Unnamed:" in col for col in df.columns):
                    df.columns = df.iloc[0].astype(str).str.strip()
                    df = df.iloc[1:].reset_index(drop=True)
                    dict_hojas[nombre_hoja] = df
                    
        hoja_forecast = next((n for n in dict_hojas.keys() if "forecast" in n.lower()), list(dict_hojas.keys())[0])
        return dict_hojas, hoja_forecast
    except:
        return None, "Error al procesar el archivo"

dict_hojas, hoja_automatica = cargar_datos_sistema()

def detectar_columnas_meses(df):
    prefijos = [("jan", "ene"), ("feb", "feb"), ("mar", "mar"), ("apr", "abr"), 
                ("may", "may"), ("jun", "jun"), ("jul", "jul"), ("aug", "ago"), 
                ("sep", "sep"), ("oct", "oct"), ("nov", "nov"), ("dec", "dic")]
    columnas = []
    for pref_en, pref_es in prefijos:
        match = next((c for c in df.columns if str(c).strip().lower().startswith(pref_en) or str(c).strip().lower().startswith(pref_es)), None)
        if match: columnas.append(match)
    return columnas if len(columnas) == 12 else []

# --- MOTOR DE SUAVIZADO EXPONENCIAL CON TENDENCIA (FIT) ---
def aplicar_fit(row, alpha, delta, x_meses, col_bytd, col_meses):
    try: bytd = float(row[col_bytd]) if pd.notna(row[col_bytd]) else 0.0001
    except: bytd = 0.0001
    if bytd <= 0: bytd = 0.0001

    presupuesto_medio = bytd / x_meses
    F, T, FIT = 0, 0, 0

    for t in range(x_meses):
        try: actual = float(row[col_meses[t]]) if pd.notna(row[col_meses[t]]) else 0
        except: actual = 0
        eficiencia = actual / presupuesto_medio

        if t == 0:
            F, T = eficiencia, 0
            FIT = F + T
        else:
            F_nuevo = FIT + alpha * (eficiencia - FIT)
            T_nuevo = T + delta * (F_nuevo - FIT)
            F, T = F_nuevo, T_nuevo
            FIT = F + T

    factores_futuros = {}
    for step, i in enumerate(range(x_meses, 12)):
        factor_proyectado = F + (step + 1) * T
        factores_futuros[f"Factor_FIT_{col_meses[i]}"] = max(0, factor_proyectado)

    return pd.Series(factores_futuros)

st.sidebar.title("Navegación Ejecutiva")
menu = st.sidebar.radio("Seleccione un módulo:", ("Inicio", "Exploración de Datos", "Forecast 5+7 Avanzado", "Propuesta de Mejora"))

if menu == "Inicio":
    st.title("Sistema de Gestión y Proyección Minera")
    st.write("Bienvenido a la plataforma de análisis estratégico corporativo.")

elif menu == "Forecast 5+7 Avanzado":
    st.title("Proyección Dinámica: Suavizado Exponencial (FIT)")
    st.write("Modelo predictivo híbrido que aprende de la ineficiencia reciente para proyectar el ciclo restante ajustando la tendencia.")
    
    st.latex(r"F_t = FIT_{t-1} + \alpha(Eficiencia_t - FIT_{t-1}) \quad | \quad T_t = T_{t-1} + \delta(F_t - FIT_{t-1}) \quad | \quad FIT_t = F_t + T_t")
    
    if dict_hojas:
        df_base = dict_hojas[hoja_automatica].copy()
        
        c1, c2, c3 = st.columns(3)
        with c1:
            X_meses = st.slider("Meses REALES (X):", 1, 11, 5)
        with c2:
            alpha = st.slider("Sensibilidad Pronóstico (Alpha - α):", 0.0, 1.0, 0.5, 0.05)
        with c3:
            delta = st.slider("Sensibilidad Tendencia (Delta - δ):", 0.0, 1.0, 0.3, 0.05)
            
        col_ytd = next((c for c in df_base.columns if "YTD" in str(c).upper()), None)
        col_budget_fy = next((c for c in df_base.columns if "BUDGET FY" in str(c).upper() or ("BUDGET" in str(c).upper() and "BYTD" not in str(c).upper())), None)
        col_bytd = next((c for c in df_base.columns if "BYTD" in str(c).upper()), col_budget_fy)
                
        columnas_meses = detectar_columnas_meses(df_base)
        
        if col_bytd and len(columnas_meses) == 12:
            df_factores = df_base.apply(aplicar_fit, axis=1, args=(alpha, delta, X_meses, col_bytd, columnas_meses))
            df_base = pd.concat([df_base, df_factores], axis=1)
            
            # --- Generación de columnas finales en la app ---
            columnas_panorama_final = []
            for idx, col_mes in enumerate(columnas_meses):
                nombre_col_final = f"{col_mes} (Final)"
                try: valor_base = pd.to_numeric(df_base[col_mes], errors='coerce').fillna(0)
                except: valor_base = 0
                
                if idx < X_meses:
                    df_base[nombre_col_final] = valor_base
                else:
                    df_base[nombre_col_final] = valor_base * df_base[f"Factor_FIT_{col_mes}"]
                    
                columnas_panorama_final.append(nombre_col_final)
            
            st.markdown("---")
            st.markdown("### Reporte de Panorama General Integrado (12 Meses)")
            columnas_claves = ["Resp", "Desc Resp"] + columnas_panorama_final
            cols_existentes = [c for c in columnas_claves if c in df_base.columns]
            st.dataframe(df_base[cols_existentes], use_container_width=True)
            
            # --- NUEVA ARQUITECTURA: Módulo de Descarga Corporativa Limpia ---
            st.markdown("### 4. Exportación de Resultados (Matriz Ejecutiva)")
            
            df_descarga = df_base.copy()
            
            # 1. Sobreescribimos las 12 columnas originales de los meses con sus valores limpios finales
            for col_mes in columnas_meses:
                df_descarga[col_mes] = df_descarga[f"{col_mes} (Final)"]
                
            # 2. Recálculo Dinámico de Métricas Clave
            df_descarga['YTD Calculado'] = df_descarga[columnas_meses[:X_meses]].sum(axis=1)
            df_descarga['Forecast FY Calculado'] = df_descarga[columnas_meses].sum(axis=1)
            
            if col_budget_fy:
                df_descarga['Var Calculado'] = df_descarga['Forecast FY Calculado'] - pd.to_numeric(df_descarga[col_budget_fy], errors='coerce').fillna(0)
            else:
                df_descarga['Var Calculado'] = 0

            # 3. Limpieza: Aislamos únicamente lo que la gerencia debe ver
            idx_primer_mes = df_base.columns.get_loc(columnas_meses[0])
            cols_identificacion = list(df_base.columns[:idx_primer_mes])
            # Evitar filtraciones de columnas internas
            cols_identificacion = [c for c in cols_identificacion if "Factor" not in str(c) and "(Final)" not in str(c)]
            
            # Ensamblamos la tabla final en el orden perfecto
            columnas_limpias = cols_identificacion + columnas_meses + ['YTD Calculado', 'Forecast FY Calculado']
            if col_budget_fy: columnas_limpias.append(col_budget_fy)
            columnas_limpias.append('Var Calculado')
            if col_bytd: columnas_limpias.append(col_bytd)

            df_export = df_descarga[[c for c in columnas_limpias if c in df_descarga.columns]].copy()
            
            # Renombramos las métricas de vuelta a sus nombres formales para el Excel
            df_export.rename(columns={
                'YTD Calculado': 'YTD',
                'Forecast FY Calculado': 'Forecast FY',
                'Var Calculado': 'Var'
            }, inplace=True)
            
            # 4. Compilación del Excel en memoria RAM
            buffer_excel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Forecast_Ejecutivo')
            buffer_excel.seek(0)
            
            st.download_button(
                label="📥 Descargar Reporte Ejecutivo Limpio (.xlsx)",
                data=buffer_excel,
                file_name=f"Reporte_Forecast_Ejecutivo_{X_meses}mas{12-X_meses}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.caption("El archivo generado está optimizado. Contiene exclusivamente los datos de identificación, los 12 meses consolidados y las métricas YTD, Forecast FY y Varianza recalculadas dinámicamente según el modelo FIT.")
            
            st.markdown("---")
            st.markdown("### 5. Auditoría de la Curva de Aprendizaje")
            if st.checkbox("Ver evolución de los Factores Proyectados (FIT)"):
                cols_factores = ["Resp"] + [f"Factor_FIT_{m}" for m in columnas_meses[X_meses:]]
                st.dataframe(df_base[cols_factores], use_container_width=True)
        else:
            st.error("Error en el mapeo estructural de las variables base.")
    else:
        st.error("Base de datos no detectada.")

elif menu == "Exploración de Datos":
    if dict_hojas:
        hoja_sel = st.selectbox("Seleccione la matriz a analizar:", list(dict_hojas.keys()))
        st.dataframe(dict_hojas[hoja_sel], use_container_width=True)
elif menu == "Propuesta de Mejora":
    st.title("Reporte y Propuestas")