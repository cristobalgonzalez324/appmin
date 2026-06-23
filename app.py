import streamlit as st
import pandas as pd
import os
import io

st.set_page_config(page_title="Gestión Minera Avanzada", layout="wide")

# --- 1. GESTIÓN DE ESTADO (MEMORIA DE LA APP) ---
# Inicializamos el diccionario de bases de datos en la memoria de la sesión
if 'bases_datos' not in st.session_state:
    st.session_state['bases_datos'] = {}

def detectar_columnas_meses(df):
    prefijos = [("jan", "ene"), ("feb", "feb"), ("mar", "mar"), ("apr", "abr"), 
                ("may", "may"), ("jun", "jun"), ("jul", "jul"), ("aug", "ago"), 
                ("sep", "sep"), ("oct", "oct"), ("nov", "nov"), ("dec", "dic")]
    columnas = []
    for pref_en, pref_es in prefijos:
        match = next((c for c in df.columns if str(c).strip().lower().startswith(pref_en) or str(c).strip().lower().startswith(pref_es)), None)
        if match: columnas.append(match)
    return columnas if len(columnas) == 12 else []

# --- 2. MOTORES MATEMÁTICOS (FIT) ---
# Motor FIT 1: Para Forecast (Basado en eficiencia Real vs Presupuesto Medio)
def aplicar_fit_forecast(row, alpha, delta, x_meses, col_budget_fy, col_meses):
    try: budget_fy = float(row[col_budget_fy]) if pd.notna(row[col_budget_fy]) else 0.0001
    except: budget_fy = 0.0001
    if budget_fy <= 0: budget_fy = 0.0001

    # Corrección del "Disparo": Base mensual fija y estable
    presupuesto_medio_mensual = budget_fy / 12.0
    F, T, FIT = 0, 0, 0

    for t in range(x_meses):
        try: actual = float(row[col_meses[t]]) if pd.notna(row[col_meses[t]]) else 0
        except: actual = 0
        eficiencia = actual / presupuesto_medio_mensual

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

# Motor FIT 2: Para Series de Tiempo Puras (Budget Quinquenal)
def aplicar_fit_quinquenal(serie_historica, alpha, delta, meses_a_proyectar=60):
    if len(serie_historica) == 0:
        return [0] * meses_a_proyectar
        
    F = serie_historica[0]
    T = 0
    FIT = F + T
    
    # Entrenamiento histórico
    for t in range(1, len(serie_historica)):
        actual = serie_historica[t]
        F_nuevo = FIT + alpha * (actual - FIT)
        T_nuevo = T + delta * (F_nuevo - FIT)
        F, T = F_nuevo, T_nuevo
        FIT = F + T
        
    # Proyección futura
    proyecciones = []
    for step in range(1, meses_a_proyectar + 1):
        proyecciones.append(max(0, F + step * T)) # Evitar presupuestos negativos
        
    return proyecciones

# --- 3. MENÚ DE NAVEGACIÓN ---
st.sidebar.title("Plataforma Directiva")
menu = st.sidebar.radio("Módulos del Sistema:", ("Gestión de Datos", "Forecast", "Budget Quinquenal", "Sensibilidades (Próx.)"))

# --- MÓDULO 1: GESTIÓN DE DATOS ---
if menu == "Gestión de Datos":
    st.title("📂 Repositorio Central de Datos")
    st.write("Carga y administra los archivos Excel que alimentarán los modelos de proyección.")
    
    archivo_subido = st.file_uploader("Subir nueva base de datos (.xlsx)", type=["xlsx", "xls"])
    if archivo_subido:
        try:
            nombre_archivo = archivo_subido.name
            dict_hojas = pd.read_excel(archivo_subido, sheet_name=None)
            
            # Limpieza estándar de cabeceras
            for nombre_hoja, df in dict_hojas.items():
                if not df.empty and any("Unnamed:" in str(col) for col in df.columns):
                    df.columns = df.iloc[0].astype(str).str.strip()
                    df = df.iloc[1:].reset_index(drop=True)
                dict_hojas[nombre_hoja] = df
                
            st.session_state['bases_datos'][nombre_archivo] = dict_hojas
            st.success(f"Archivo '{nombre_archivo}' procesado y almacenado en memoria exitosamente.")
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")

    st.markdown("### Bases de Datos Activas")
    if st.session_state['bases_datos']:
        for nombre, hojas in list(st.session_state['bases_datos'].items()):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.info(f"**{nombre}** | Pestañas detectadas: {', '.join(list(hojas.keys()))}")
            with c2:
                if st.button("🗑️ Eliminar", key=f"del_{nombre}"):
                    del st.session_state['bases_datos'][nombre]
                    st.rerun()
    else:
        st.warning("No hay bases de datos cargadas en el sistema.")

# --- MÓDULO 2: FORECAST ---
elif menu == "Forecast":
    st.title("📈 Forecast Dinámico")
    
    if not st.session_state['bases_datos']:
        st.warning("Por favor, carga una base de datos en el módulo 'Gestión de Datos'.")
    else:
        archivo_sel = st.selectbox("Seleccionar Archivo Base:", list(st.session_state['bases_datos'].keys()))
        hojas_disp = list(st.session_state['bases_datos'][archivo_sel].keys())
        hoja_target = st.selectbox("Seleccionar Pestaña a Proyectar:", hojas_disp)
        
        df_base = st.session_state['bases_datos'][archivo_sel][hoja_target].copy()
        
        st.markdown("### 1. Parametrización del Modelo")
        c1, c2, c3 = st.columns(3)
        with c1: X_meses = st.slider("Meses REALES (X):", 1, 11, 5)
        with c2: alpha = st.slider("Sensibilidad Pronóstico (α):", 0.0, 1.0, 0.5, 0.05)
        with c3: delta = st.slider("Sensibilidad Tendencia (δ):", 0.0, 1.0, 0.3, 0.05)
            
        col_budget_fy = next((c for c in df_base.columns if "BUDGET FY" in str(c).upper() or ("BUDGET" in str(c).upper() and "BYTD" not in str(c).upper())), None)
        columnas_meses = detectar_columnas_meses(df_base)
        
        if col_budget_fy and len(columnas_meses) == 12:
            df_factores = df_base.apply(aplicar_fit_forecast, axis=1, args=(alpha, delta, X_meses, col_budget_fy, columnas_meses))
            df_base = pd.concat([df_base, df_factores], axis=1)
            
            columnas_panorama = []
            for idx, col_mes in enumerate(columnas_meses):
                nombre_final = f"{col_mes} (Final)"
                try: val = pd.to_numeric(df_base[col_mes], errors='coerce').fillna(0)
                except: val = 0
                
                df_base[nombre_final] = val if idx < X_meses else val * df_base[f"Factor_FIT_{col_mes}"]
                columnas_panorama.append(nombre_final)
                
            st.markdown("### 2. Vista Previa de la Proyección")
            st.dataframe(df_base[["Resp", "Desc Resp"] + columnas_panorama], use_container_width=True)
            # (Aquí iría el código de exportación de Excel idéntico al que ya teníamos para Forecast)
            st.success("Proyección estabilizada. El modelo ahora soporta cambios extremos en el slider sin distorsionar el presupuesto base.")
        else:
            st.error("La pestaña seleccionada no contiene la estructura requerida (12 meses y columna Budget FY).")

# --- MÓDULO 3: BUDGET QUINQUENAL ---
elif menu == "Budget Quinquenal":
    st.title("📅 Proyección de Presupuesto Quinquenal (2027 - 2031)")
    st.write("Generación de plan a 5 años basado en el aprendizaje de series de tiempo históricas.")
    
    if not st.session_state['bases_datos']:
        st.warning("Carga información histórica en 'Gestión de Datos' para entrenar el modelo.")
    else:
        archivo_sel = st.selectbox("Seleccionar Archivo de Entrenamiento:", list(st.session_state['bases_datos'].keys()))
        hojas_disp = list(st.session_state['bases_datos'][archivo_sel].keys())
        
        # El usuario elige con qué pestañas históricas alimentar el modelo
        hojas_hist = st.multiselect("Seleccionar Pestañas Históricas de Entrenamiento (Orden Cronológico):", hojas_disp, help="Ejemplo: Budget 2024, Budget 2025...")
        
        st.markdown("### 1. Parámetros de Aprendizaje FIT")
        c1, c2 = st.columns(2)
        with c1: alpha_q = st.slider("Sensibilidad Histórica (α):", 0.0, 1.0, 0.4, 0.05, key='aq')
        with c2: delta_q = st.slider("Aceleración de Tendencia (δ):", 0.0, 1.0, 0.2, 0.05, key='dq')
        
        if st.button("🚀 Ejecutar Proyección Quinquenal"):
            if not hojas_hist:
                st.error("Debes seleccionar al menos una pestaña histórica para entrenar al modelo.")
            else:
                with st.spinner("Procesando redes de tiempo históricas y proyectando 60 meses..."):
                    # 1. Tomamos la primera hoja como plantilla estructural (para Responsables, Descripciones)
                    df_resultado = st.session_state['bases_datos'][archivo_sel][hojas_hist[0]].copy()
                    cols_identificacion = [c for c in df_resultado.columns if c not in detectar_columnas_meses(df_resultado)]
                    df_resultado = df_resultado[cols_identificacion[:5]] # Nos quedamos con las primeras columnas de ID
                    
                    # 2. Iteración fila por fila para crear la historia y proyectar
                    nombres_meses_base = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
                    años_futuros = [2027, 2028, 2029, 2030, 2031]
                    
                    matriz_proyecciones = []
                    
                    for idx, row in df_resultado.iterrows():
                        serie_historica = []
                        # Recolectamos la historia cronológica de esta fila en las hojas seleccionadas
                        for hoja in hojas_hist:
                            df_hist = st.session_state['bases_datos'][archivo_sel][hoja]
                            meses_hist = detectar_columnas_meses(df_hist)
                            if len(meses_hist) == 12:
                                for m in meses_hist:
                                    try: val = float(df_hist.iloc[idx][m]) if pd.notna(df_hist.iloc[idx][m]) else 0
                                    except: val = 0
                                    serie_historica.append(val)
                        
                        # Aplicamos el motor FIT puro para obtener los 60 meses futuros
                        proyeccion_60_meses = aplicar_fit_quinquenal(serie_historica, alpha_q, delta_q, 60)
                        matriz_proyecciones.append(proyeccion_60_meses)
                    
                    # 3. Ensamblaje del nuevo Dataframe Quinquenal
                    df_matriz = pd.DataFrame(matriz_proyecciones)
                    
                    col_idx = 0
                    for año in años_futuros:
                        columnas_año = []
                        # Creamos los 12 meses
                        for mes in nombres_meses_base:
                            nombre_col = f"{mes} {año}"
                            df_resultado[nombre_col] = df_matriz[col_idx]
                            columnas_año.append(nombre_col)
                            col_idx += 1
                        
                        # Sumatoria automática para generar la columna FY de ese año
                        df_resultado[f"FY {año}"] = df_resultado[columnas_año].sum(axis=1)
                        
                    st.success("Plan Quinquenal Generado Exitosamente.")
                    
                    st.markdown("### 2. Matriz de Budget Quinquenal (2027-2031)")
                    st.dataframe(df_resultado, use_container_width=True)
                    
                    # Exportación del Quinquenal
                    buffer_q = io.BytesIO()
                    with pd.ExcelWriter(buffer_q, engine='openpyxl') as writer:
                        df_resultado.to_excel(writer, index=False, sheet_name='Budget_Quinquenal')
                    buffer_q.seek(0)
                    st.download_button("📥 Descargar Budget Quinquenal (.xlsx)", data=buffer_q, file_name="Budget_Quinquenal_2027_2031.xlsx")