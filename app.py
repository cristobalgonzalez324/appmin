import streamlit as st
import pandas as pd
import os

# 1. Configuración general de la página
st.set_page_config(page_title="Proyecto Minería", layout="wide")

# 2. Motor de extracción de datos (Buscador Universal)
@st.cache_data
def cargar_datos():
    ruta_base = os.getcwd() # Obtiene la ruta actual de tu computador
    archivo_encontrado = None
    
    # Búsqueda profunda: revisa todas las carpetas y subcarpetas
    for root, dirs, files in os.walk(ruta_base):
        if '.git' in root: 
            continue
        for f in files:
            # Buscamos exclusivamente un archivo Excel, ignorando temporales
            if (f.endswith('.xlsx') or f.endswith('.xls')) and not f.startswith('~$'):
                archivo_encontrado = os.path.join(root, f)
                break
        if archivo_encontrado:
            break
            
    if not archivo_encontrado:
        st.error(f"Error crítico: El 'Buscador Universal' rastreó todo tu proyecto ({ruta_base}) y NO encontró físicamente ningún archivo Excel.")
        return None
        
    st.success(f"Radar de sistema: Archivo Excel detectado y conectado desde -> {archivo_encontrado}")
    
    try:
        dict_hojas = pd.read_excel(archivo_encontrado, sheet_name=None)
        
        for nombre_hoja, df in dict_hojas.items():
            if not df.empty:
                if any(isinstance(col, str) and "Unnamed:" in col for col in df.columns):
                    nuevos_titulos = df.iloc[0].astype(str).str.strip()
                    df.columns = nuevos_titulos
                    df = df.iloc[1:].reset_index(drop=True)
                    dict_hojas[nombre_hoja] = df
                    
        return dict_hojas
        
    except Exception as e:
        st.error(f"Encontré el archivo, pero no pude leerlo. Detalle técnico: {e}")
        return None

try:
    datos_completos = cargar_datos()
except Exception as e:
    st.error(f"Error del sistema: {e}")
    datos_completos = None

# 3. Diseño del Menú Lateral
st.sidebar.title("Navegación Ejecutiva")
st.sidebar.markdown("---")
menu = st.sidebar.radio(
    "Seleccione un módulo:",
    ("Inicio", "Exploración de Datos", "Forecast 5+7", "Propuesta de Mejora")
)

# 4. Lógica de navegación
if menu == "Inicio":
    st.title("Sistema de Gestión y Proyección Minera")
    st.write("Bienvenido a la plataforma de análisis estratégico.")
    st.info("Utilice el menú lateral para navegar entre los distintos módulos de visualización.")

elif menu == "Exploración de Datos":
    st.title("Gestión y Exploración de Datos")
    st.write("Estado actual de los procesos, presupuestos y recursos.")
    
    if datos_completos:
        hojas = list(datos_completos.keys())
        hoja_seleccionada = st.selectbox("Seleccione la matriz de datos a analizar:", hojas)
        
        df_actual = datos_completos[hoja_seleccionada]
        
        # --- Panel Ejecutivo (Dashboard) ---
        st.markdown("### Indicadores de la Matriz")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Volumen de Registros", f"{len(df_actual)} filas")
        with col2:
            st.metric("Variables Disponibles", f"{len(df_actual.columns)} columnas")
        with col3:
            st.metric("Estado del Sistema", "Óptimo")
            
        st.markdown("---")
        
        # --- Motor de Búsqueda Dinámico ---
        st.write("**Filtrado Estructural:**")
        
        columnas_disponibles = df_actual.columns.tolist()
        
        filtro_col1, filtro_col2 = st.columns(2)
        with filtro_col1:
            col_seleccionada = st.selectbox("1. Seleccione la variable a filtrar:", columnas_disponibles)
        with filtro_col2:
            valor_busqueda = st.text_input(f"2. Ingrese el valor a buscar en '{col_seleccionada}':")
        
        if valor_busqueda:
            filtro = df_actual[col_seleccionada].astype(str).str.contains(valor_busqueda, case=False, na=False)
            df_mostrar = df_actual[filtro]
            st.success(f"Se encontraron {len(df_mostrar)} coincidencias.")
        else:
            df_mostrar = df_actual
            
        st.dataframe(df_mostrar, use_container_width=True)

elif menu == "Forecast 5+7":
    st.title("Proyección No Lineal (Forecast 5+7)")
    st.write("Aquí integraremos el modelo matemático para proyectar los datos de manera estructurada.")

elif menu == "Propuesta de Mejora":
    st.title("Reporte y Propuestas")
    st.write("Espacio reservado para las conclusiones y recomendaciones ejecutivas.")