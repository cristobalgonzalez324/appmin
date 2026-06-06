import streamlit as st

# 1. Configuración general de la página
st.set_page_config(page_title="Proyecto Minería", layout="wide")

# 2. Diseño del Menú Lateral (Sidebar)
st.sidebar.title("Navegación Ejecutiva")
st.sidebar.markdown("---")
menu = st.sidebar.radio(
    "Seleccione un módulo:",
    ("Inicio", "Exploración de Datos", "Forecast 5+7", "Propuesta de Mejora")
)

# 3. Lógica de navegación (Qué mostrar según lo que se elija)
if menu == "Inicio":
    st.title("Sistema de Gestión y Proyección Minera")
    st.write("Bienvenido a la plataforma de análisis estratégico.")
    st.info("Utilice el menú lateral para navegar entre los distintos módulos de visualización y proyección de datos.")

elif menu == "Exploración de Datos":
    st.title("Gestión y Exploración de Datos")
    st.write("En este módulo conectaremos el archivo Excel para visualizar los presupuestos y el estado actual.")

elif menu == "Forecast 5+7":
    st.title("Proyección No Lineal (Forecast 5+7)")
    st.write("Aquí integraremos el modelo matemático para proyectar los datos de manera estructurada.")

elif menu == "Propuesta de Mejora":
    st.title("Reporte y Propuestas")
    st.write("Espacio reservado para las conclusiones y recomendaciones ejecutivas.")