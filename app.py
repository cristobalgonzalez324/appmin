import streamlit as st
import pandas as pd
import os
import io
from docx import Document
from docx.shared import Pt

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

    if budget_fy <= 0.01:
        return pd.Series({f"Factor_FIT_{col_meses[i]}": 1.0 for i in range(x_meses, 12)})

    presupuesto_medio_mensual = budget_fy / 12.0
    F, T, FIT = 0, 0, 0

    for t in range(x_meses):
        try: actual = float(row[col_meses[t]]) if pd.notna(row[col_meses[t]]) else 0
        except: actual = 0
        
        eficiencia_cruda = actual / presupuesto_medio_mensual
        eficiencia = min(max(eficiencia_cruda, 0.1), 3.0) 

        if t == 0: 
            F, T = eficiencia, 0
            FIT = F + T
        else:
            F_nuevo = FIT + alpha * (eficiencia - FIT)
            F_nuevo = min(max(F_nuevo, 0.3), 2.5) 
            T_nuevo = T + delta * (F_nuevo - FIT)
            T_nuevo = min(max(T_nuevo, -0.05), 0.05) 
            F, T = F_nuevo, T_nuevo
            FIT = F + T

    factores_futuros = {}
    for step, i in enumerate(range(x_meses, 12)):
        factor_proyectado = F + (step + 1) * T
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

# --- 3. MOTOR DE EXPORTACIÓN DE REPORTES TÉCNICOS (WORD) ---
def generar_reporte_word(titulo, kpis, parametros, conclusiones):
    doc = Document()
    
    # Título Principal
    titulo_doc = doc.add_heading(f'Informe Técnico: {titulo}', 0)
    titulo_doc.alignment = 1 # Centrado
    
    doc.add_paragraph('Generado automáticamente por el Sistema Predictivo de Gestión Minera Avanzada.').alignment = 1
    doc.add_paragraph('_' * 70).alignment = 1
    
    # Sección 1: Parámetros del Modelo
    doc.add_heading('1. Parametrización del Modelo Operativo', level=1)
    doc.add_paragraph('El modelo predictivo fue ejecutado considerando las siguientes variables de calibración:')
    for key, value in parametros.items():
        doc.add_paragraph(f'{key}: {value}', style='List Bullet')
        
    # Sección 2: Resumen de KPIs
    doc.add_heading('2. Resumen Ejecutivo (Métricas Clave)', level=1)
    doc.add_paragraph('Resultados financieros consolidados obtenidos tras la simulación:')
    for key, value in kpis.items():
        p = doc.add_paragraph(style='List Bullet')
        p.add_run(f'{key}: ').bold = True
        p.add_run(str(value))
        
    # Sección 3: Metodología y Conclusiones
    doc.add_heading('3. Metodología y Notas Analíticas', level=1)
    doc.add_paragraph(conclusiones)
    doc.add_paragraph('\nEste informe es un documento de apoyo a la toma de decisiones y debe evaluarse en conjunto con la matriz de datos Excel adjunta generada por la plataforma.')

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- 4. MENÚ DE NAVEGACIÓN ---
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
            porcentaje_var = (variacion/total_planificado)*100 if total_planificado>0 else 0
            
            kpi1, kpi2, kpi3 = st.columns(3)
            with kpi1: st.metric("Presupuesto Base (Budget FY)", f"USD {total_planificado:,.0f}")
            with kpi2: st.metric("Estimación (Forecast FIT)", f"USD {total_estimado:,.0f}")
            with kpi3: st.metric("Varianza Anual", f"USD {variacion:,.0f}", delta=f"{porcentaje_var:.2f}%", delta_color="inverse")
            
            st.write("**Análisis de Desviación Temporal:**")
            df_grafico = pd.DataFrame({
                'Original': [pd.to_numeric(df_base[m], errors='coerce').fillna(0).sum() for m in columnas_meses],
                'Proyectado': [df_base[c].sum() for c in columnas_panorama]
            }, index=[f"{i+1:02d}. {str(m).split('-')[0].strip()}" for i, m in enumerate(columnas_meses)])
            st.bar_chart(df_grafico, use_container_width=True)

            st.markdown("### 3. Matriz de Forecast y Reportes")
            cols_identificacion = [c for c in df_base.columns if c not in columnas_meses and "Factor" not in c and "(Final)" not in c]
            st.dataframe(df_base[cols_identificacion[:4] + columnas_panorama], use_container_width=True)

            # --- SECCIÓN DE DESCARGAS ---
            col_d1, col_d2 = st.columns(2)
            
            # Exportar Excel (Matriz Estándar)
            df_export = df_base[cols_identificacion[:4] + columnas_panorama].copy()
            buffer_excel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Forecast_Proyectado')
            buffer_excel.seek(0)
            col_d1.download_button("📊 Descargar Matriz Forecast (.xlsx)", data=buffer_excel, file_name=f"Forecast_M{X_meses}.xlsx")

            # Exportar Word (Informe Técnico)
            parametros_doc = {"Meses de Datos Reales (Histórico)": X_meses, "Sensibilidad de Pronóstico (Alpha)": alpha, "Sensibilidad de Tendencia (Delta)": delta}
            kpis_doc = {"Presupuesto Anual Original": f"USD {total_planificado:,.2f}", "Estimación Forecast Proyectado": f"USD {total_estimado:,.2f}", "Desviación Esperada (Varianza)": f"USD {variacion:,.2f} ({porcentaje_var:.2f}%)"}
            conclusion_doc = f"El pronóstico se calculó utilizando un modelo de Suavizado Exponencial con Ajuste de Tendencia (FIT) adaptado a límites de contingencia corporativos. Basado en el comportamiento de los primeros {X_meses} meses, la operación minera proyecta cerrar el año con una desviación neta del {porcentaje_var:.2f}%. Se recomienda focalizar planes de contención de costos inmediatos en los ítems con mayores varianzas acumuladas evidenciados en el archivo anexo."
            
            buffer_word = generar_reporte_word("Proyección de Forecast Dinámico", kpis_doc, parametros_doc, conclusion_doc)
            col_d2.download_button("📄 Descargar Informe Técnico (.docx)", data=buffer_word, file_name=f"Informe_Forecast_M{X_meses}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

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
            
            st.markdown("---")
            st.markdown("### Módulo de Análisis de Sensibilidades")
            with st.expander("⚙️ Ponderación de Estructura de Costos de la Planta", expanded=False):
                s1, s2, s3 = st.columns(3)
                peso_comb = s1.number_input("% Peso Combustible", 0, 100, 20)
                peso_div = s2.number_input("% Peso Divisas", 0, 100, 35)
                peso_mo = s3.number_input("% Peso Mano de Obra", 0, 100, 30)
            
            st.markdown("**Simulador de Shocks Macroeconómicos:**")
            col_s1, col_s2, col_s3 = st.columns(3)
            var_comb = col_s1.slider("🛢️ Δ Combustible (%)", -50, 50, 0)
            var_div = col_s2.slider("💱 Δ Divisas (%)", -50, 50, 0)
            var_mo = col_s3.slider("👷 Δ Mano de Obra (%)", -50, 50, 0)
            
            factor_impacto = 1 + ((peso_comb/100) * (var_comb/100)) + ((peso_div/100) * (var_div/100)) + ((peso_mo/100) * (var_mo/100))
            df_sensibilizado = df_q.copy()
            for col in cols_2027 + cols_fy:
                df_sensibilizado[col] = df_sensibilizado[col] * factor_impacto
                
            st.markdown("### Dashboard de Impacto Quinquenal")
            totales_base = [df_q[fy].sum() for fy in cols_fy]
            totales_sens = [df_sensibilizado[fy].sum() for fy in cols_fy]
            
            suma_quinquenio_base = sum(totales_base)
            suma_quinquenio_sens = sum(totales_sens)
            impacto_neto = suma_quinquenio_sens - suma_quinquenio_base
            porc_impacto = (impacto_neto/suma_quinquenio_base)*100 if suma_quinquenio_base>0 else 0
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Costo Total Quinquenio (Base)", f"USD {suma_quinquenio_base:,.0f}")
            k2.metric("Costo Quinquenio Sensibilizado", f"USD {suma_quinquenio_sens:,.0f}")
            k3.metric("Impacto Neto (Varianza)", f"USD {impacto_neto:,.0f}", delta=f"{porc_impacto:.2f}%", delta_color="inverse")
            
            df_graf_q = pd.DataFrame({'Escenario Base': totales_base, 'Escenario Sensibilizado': totales_sens}, index=[fy.replace("FY ", "") for fy in cols_fy])
            st.bar_chart(df_graf_q, use_container_width=True)

            # --- SECCIÓN DE DESCARGAS ---
            st.markdown("### Exportación de Reportes")
            col_d1, col_d2 = st.columns(2)
            
            buffer_q = io.BytesIO()
            with pd.ExcelWriter(buffer_q, engine='openpyxl') as writer:
                df_sensibilizado[cols_id + cols_2027 + cols_fy].to_excel(writer, index=False, sheet_name='Quinquenal_Sensibilizado')
            buffer_q.seek(0)
            col_d1.download_button("📊 Descargar Matriz Quinquenal (.xlsx)", data=buffer_q, file_name="Budget_Quinquenal.xlsx")
            
            # Exportar Word Quinquenal (Informe Técnico)
            parametros_q_doc = {"Sensibilidad de Aprendizaje (Alpha)": alpha_q, "Aceleración de Tendencia (Delta)": delta_q, "Peso de Combustibles": f"{peso_comb}% (Variación: {var_comb}%)", "Peso de Divisas": f"{peso_div}% (Variación: {var_div}%)", "Peso de Mano de Obra": f"{peso_mo}% (Variación: {var_mo}%)"}
            kpis_q_doc = {"Proyección Estructural Base (5 años)": f"USD {suma_quinquenio_base:,.2f}", "Proyección tras Shocks de Mercado": f"USD {suma_quinquenio_sens:,.2f}", "Impacto Macroeconómico Neto": f"USD {impacto_neto:,.2f} ({porc_impacto:.2f}%)"}
            conclusion_q_doc = f"El presupuesto quinquenal 2027-2031 ha sido calculado aplicando un modelo predictivo FIT sobre la matriz de entrenamiento histórico. Las variaciones introducidas en el módulo de sensibilidad (combustibles, divisas y remuneraciones) generan una desviación proyectada total del {porc_impacto:.2f}% sobre la estructura original. Estos antecedentes soportan la planificación estratégica y permiten la anticipación operativa frente a posibles escenarios adversos del mercado global."
            
            buffer_word_q = generar_reporte_word("Planificación Estratégica Quinquenal (2027-2031)", kpis_q_doc, parametros_q_doc, conclusion_q_doc)
            col_d2.download_button("📄 Descargar Informe Técnico (.docx)", data=buffer_word_q, file_name="Informe_Quinquenal.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")