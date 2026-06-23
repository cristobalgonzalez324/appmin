import streamlit as st
import pandas as pd
import os
import io

st.set_page_config(page_title="Gestión Minera Avanzada", layout="wide")

# --- 1. GESTIÓN DE ESTADO (MEMORIA DE LA APP) ---
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
def aplicar_fit_forecast(row, alpha, delta, x_meses, col_budget_fy, col_meses):
    try: budget_fy = float(row[col_budget_fy]) if pd.notna(row[col_budget_fy]) else 0.0
    except: budget_fy = 0.0

    # Si el presupuesto es cero o casi cero, no hay cálculo de ineficiencia posible.
    if budget_fy <= 0.01:
        return pd.Series({f"Factor_FIT_{col_meses[i]}": 1.0 for i in range(x_meses, 12)})

    presupuesto_medio_mensual = budget_fy / 12.0
    F, T, FIT = 0, 0, 0

    # ENTRENAMIENTO HISTÓRICO
    for t in range(x_meses):
        try: actual = float(row[col_meses[t]]) if pd.notna(row[col_meses[t]]) else 0
        except: actual = 0
        
        # Ineficiencia pura del mes
        eficiencia_cruda = actual / presupuesto_medio_mensual
        # Tope primario para evitar que ceros o errores del excel rompan la base
        eficiencia = min(max(eficiencia_cruda, 0.1), 3.0) 

        if t == 0: 
            F, T = eficiencia, 0
            FIT = F + T
        else:
            F_nuevo = FIT + alpha * (eficiencia - FIT)
            # REGLA 1: Acotamos el nivel base aprendido (entre 30% de ahorro y 250% de sobrecosto)
            F_nuevo = min(max(F_nuevo, 0.3), 2.5) 
            
            T_nuevo = T + delta * (F_nuevo - FIT)
            # REGLA 2: Acotamos la tendencia para evitar explosión geométrica (max +- 5% de deriva mensual)
            T_nuevo = min(max(T_nuevo, -0.05), 0.05) 
            
            F, T = F_nuevo, T_nuevo
            FIT = F + T

    # PROYECCIÓN FUTURA
    factores_futuros = {}
    for step, i in enumerate(range(x_meses, 12)):
        # Proyectamos linealmente la base más la tendencia amortiguada
        factor_proyectado = F + (step + 1) * T
        
        # REGLA 3: Límite Corporativo Absoluto. El Forecast jamás será mayor al doble del presupuesto base.
        factor_proyectado = min(max(factor_proyectado, 0.4), 2.0) 
        
        factores_futuros[f"Factor_FIT_{col_meses[i]}"] = factor_proyectado
        
    return pd.Series(factores_futuros)

def aplicar_fit_quinquenal(serie_historica, alpha, delta, meses_a_proyectar=60):
    if len(serie_historica) == 0: return [0] * meses_a_proyectar
    F, T = serie_historica[0], 0
    FIT = F + T
    for t in range(1, len(serie_historica)):
        F_nuevo = FIT + alpha * (serie_historica[t] - FIT)
        T_nuevo = T + delta * (F_nuevo - FIT)
        F, T = F_nuevo, T_nuevo
        FIT = F + T
    return [max(0, F + step * T) for step in range(1, meses_a_proyectar + 1)]

# --- 3. MENÚ DE NAVEGACIÓN ---
st.sidebar.title("Plataforma Directiva")
menu = st.sidebar.radio("Módulos del Sistema:", ("Gestión de Datos", "Forecast", "Budget Quinquenal"))

# --- MÓDULO 1: GESTIÓN DE DATOS ---
if menu == "Gestión de Datos":
    st.title("📂 Repositorio Central de Datos")
    archivo_subido = st.file_uploader("Subir nueva base de datos (.xlsx)", type=["xlsx", "xls"])
    if archivo_subido:
        try:
            dict_hojas = pd.read_excel(archivo_subido, sheet_name=None)
            for nombre_hoja, df in dict_hojas.items():
                if not df.empty and any("Unnamed:" in str(col) for col in df.columns):
                    df.columns = df.iloc[0].astype(str).str.strip()
                    df = df.iloc[1:].reset_index(drop=True)
                dict_hojas[nombre_hoja] = df
            st.session_state['bases_datos'][archivo_subido.name] = dict_hojas
            st.success(f"Archivo '{archivo_subido.name}' procesado exitosamente.")
        except Exception as e: st.error(f"Error: {e}")

    st.markdown("### Bases de Datos Activas")
    if st.session_state['bases_datos']:
        for nombre, hojas in list(st.session_state['bases_datos'].items()):
            c1, c2 = st.columns([4, 1])
            with c1: st.info(f"**{nombre}** | Pestañas: {', '.join(list(hojas.keys()))}")
            with c2:
                if st.button("🗑️ Eliminar", key=f"del_{nombre}"):
                    del st.session_state['bases_datos'][nombre]; st.rerun()
    else: st.warning("No hay bases de datos cargadas.")

# --- MÓDULO 2: FORECAST ---
elif menu == "Forecast":
    st.title("📈 Forecast Dinámico")
    if not st.session_state['bases_datos']: st.warning("Carga una base de datos en 'Gestión de Datos'.")
    else:
        archivo_sel = st.selectbox("Seleccionar Archivo Base:", list(st.session_state['bases_datos'].keys()))
        hoja_target = st.selectbox("Seleccionar Pestaña a Proyectar:", list(st.session_state['bases_datos'][archivo_sel].keys()))
        df_base = st.session_state['bases_datos'][archivo_sel][hoja_target].copy()
        
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
                
            st.markdown("---")
            st.markdown("### 2. Dashboard Ejecutivo: Impacto sobre el Plan Anual Base")
            total_planificado = pd.to_numeric(df_base[col_budget_fy], errors='coerce').fillna(0).sum()
            total_estimado = sum([df_base[c].sum() for c in columnas_panorama])
            variacion = total_estimado - total_planificado
            
            kpi1, kpi2, kpi3 = st.columns(3)
            with kpi1: st.metric("Presupuesto Base (Budget FY)", f"USD {total_planificado:,.0f}")
            with kpi2: st.metric("Estimación (Forecast FIT)", f"USD {total_estimado:,.0f}")
            with kpi3: st.metric("Varianza Anual", f"USD {variacion:,.0f}", delta=f"{(variacion/total_planificado)*100 if total_planificado>0 else 0:.2f}%", delta_color="inverse")
            
            st.write("**Análisis de Desviación Temporal:**")
            df_grafico = pd.DataFrame({
                'Original': [pd.to_numeric(df_base[m], errors='coerce').fillna(0).sum() for m in columnas_meses],
                'Proyectado': [df_base[c].sum() for c in columnas_panorama]
            }, index=[f"{i+1:02d}. {str(m).split('-')[0].strip()}" for i, m in enumerate(columnas_meses)])
            st.bar_chart(df_grafico, use_container_width=True)

            st.markdown("### 3. Matriz de Forecast")
            cols_identificacion = [c for c in df_base.columns if c not in columnas_meses and "Factor" not in c and "(Final)" not in c]
            st.dataframe(df_base[cols_identificacion[:4] + columnas_panorama], use_container_width=True)
        else: st.error("Estructura inválida (faltan 12 meses o Budget FY).")

# --- MÓDULO 3: BUDGET QUINQUENAL & SENSIBILIDADES ---
elif menu == "Budget Quinquenal":
    st.title("📅 Presupuesto Quinquenal & Sensibilidades")
    if not st.session_state['bases_datos']: st.warning("Carga información histórica en 'Gestión de Datos'.")
    else:
        archivo_sel = st.selectbox("Archivo de Entrenamiento:", list(st.session_state['bases_datos'].keys()))
        hojas_hist = st.multiselect("Pestañas Históricas (Orden Cronológico):", list(st.session_state['bases_datos'][archivo_sel].keys()))
        
        c1, c2 = st.columns(2)
        with c1: alpha_q = st.slider("Sensibilidad Histórica (α):", 0.0, 1.0, 0.4, 0.05)
        with c2: delta_q = st.slider("Aceleración Tendencia (δ):", 0.0, 1.0, 0.2, 0.05)
        
        if st.button("🚀 Ejecutar Proyección Quinquenal"):
            if not hojas_hist: st.error("Selecciona al menos una pestaña.")
            else:
                with st.spinner("Procesando redes de tiempo..."):
                    df_base = st.session_state['bases_datos'][archivo_sel][hojas_hist[0]].copy()
                    cols_id = [c for c in df_base.columns if c not in detectar_columnas_meses(df_base)]
                    df_resultado = df_base[cols_id[:5]].copy()
                    
                    meses_base = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
                    años_futuros = [2027, 2028, 2029, 2030, 2031]
                    matriz_proyecciones = []
                    
                    for idx, row in df_resultado.iterrows():
                        serie_historica = []
                        for hoja in hojas_hist:
                            df_hist = st.session_state['bases_datos'][archivo_sel][hoja]
                            meses_hist = detectar_columnas_meses(df_hist)
                            if len(meses_hist) == 12:
                                for m in meses_hist:
                                    try: val = float(df_hist.iloc[idx][m]) if pd.notna(df_hist.iloc[idx][m]) else 0
                                    except: val = 0
                                    serie_historica.append(val)
                        matriz_proyecciones.append(aplicar_fit_quinquenal(serie_historica, alpha_q, delta_q, 60))
                    
                    df_matriz = pd.DataFrame(matriz_proyecciones)
                    
                    col_idx = 0
                    cols_fy = []
                    cols_2027 = []
                    for año in años_futuros:
                        cols_año = []
                        for mes in meses_base:
                            nombre_col = f"{mes} {año}"
                            df_resultado[nombre_col] = df_matriz[col_idx]
                            cols_año.append(nombre_col)
                            if año == 2027: cols_2027.append(nombre_col)
                            col_idx += 1
                        fy_name = f"FY {año}"
                        df_resultado[fy_name] = df_resultado[cols_año].sum(axis=1)
                        cols_fy.append(fy_name)
                    
                    st.session_state['df_quinquenal'] = df_resultado
                    st.session_state['cols_2027'] = cols_2027
                    st.session_state['cols_fy'] = cols_fy
                    st.session_state['cols_id'] = cols_id[:5]
        
        if 'df_quinquenal' in st.session_state:
            df_q = st.session_state['df_quinquenal']
            cols_2027 = st.session_state['cols_2027']
            cols_fy = st.session_state['cols_fy']
            cols_id = st.session_state['cols_id']
            
            st.success("Proyección base estabilizada.")
            st.markdown("### 1. Vista Resumida: Presupuesto Quinquenal Base")
            st.dataframe(df_q[cols_id + cols_2027 + cols_fy], use_container_width=True)
            
            st.markdown("---")
            st.markdown("### 2. Módulo de Sensibilidades")
            
            with st.expander("⚙️ Ponderación de Estructura de Costos de la Planta", expanded=False):
                s1, s2, s3 = st.columns(3)
                peso_comb = s1.number_input("% Peso Combustible", 0, 100, 20)
                peso_div = s2.number_input("% Peso Divisas", 0, 100, 35)
                peso_mo = s3.number_input("% Peso Mano de Obra", 0, 100, 30)
            
            st.markdown("**Simulador de Variación de Mercado:**")
            col_s1, col_s2, col_s3 = st.columns(3)
            var_comb = col_s1.slider("🛢️ Δ Combustible (%)", -50, 50, 0)
            var_div = col_s2.slider("💱 Δ Divisas (%)", -50, 50, 0)
            var_mo = col_s3.slider("👷 Δ Mano de Obra (%)", -50, 50, 0)
            
            factor_impacto = 1 + ((peso_comb/100) * (var_comb/100)) + ((peso_div/100) * (var_div/100)) + ((peso_mo/100) * (var_mo/100))
            
            df_sensibilizado = df_q.copy()
            for col in cols_2027 + cols_fy:
                df_sensibilizado[col] = df_sensibilizado[col] * factor_impacto
                
            st.markdown("### 3. Dashboard de Sensibilidad (Impacto en FY)")
            totales_base = [df_q[fy].sum() for fy in cols_fy]
            totales_sens = [df_sensibilizado[fy].sum() for fy in cols_fy]
            
            suma_quinquenio_base = sum(totales_base)
            suma_quinquenio_sens = sum(totales_sens)
            impacto_neto = suma_quinquenio_sens - suma_quinquenio_base
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Costo Total Quinquenio (Base)", f"USD {suma_quinquenio_base:,.0f}")
            k2.metric("Costo Quinquenio Sensibilizado", f"USD {suma_quinquenio_sens:,.0f}")
            k3.metric("Impacto Neto Quinquenal", f"USD {impacto_neto:,.0f}", delta=f"{(impacto_neto/suma_quinquenio_base)*100 if suma_quinquenio_base>0 else 0:.2f}%", delta_color="inverse")
            
            df_graf_q = pd.DataFrame({
                'Proyección Base': totales_base,
                'Proyección Sensibilizada': totales_sens
            }, index=[fy.replace("FY ", "") for fy in cols_fy])
            st.bar_chart(df_graf_q, use_container_width=True)
            
            st.markdown("### 4. Matriz Quinquenal Sensibilizada")
            st.dataframe(df_sensibilizado[cols_id + cols_2027 + cols_fy], use_container_width=True)
            
            buffer_q = io.BytesIO()
            with pd.ExcelWriter(buffer_q, engine='openpyxl') as writer:
                df_sensibilizado[cols_id + cols_2027 + cols_fy].to_excel(writer, index=False, sheet_name='Quinquenal_Sensibilizado')
            buffer_q.seek(0)
            st.download_button("📥 Descargar Quinquenal Sensibilizado (.xlsx)", data=buffer_q, file_name="Budget_Quinquenal_Sensibilizado.xlsx")