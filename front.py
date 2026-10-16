import numpy as np
import pandas as pd
import streamlit as st
from mplsoccer import Pitch

from datos_america import cargar_datos_america
from mapa_calor import mostrar_mapa_calor
from mapa_de_tiros import mostrar_mapa_tiros

# Configuración de la página (solo se llama aquí, una vez)
st.set_page_config(page_title="Predicción de estadísticas de partidos", layout="wide")

# Encabezado
st.title("Predicción de estadísticas de partidos")

# Los datos del América se cargan UNA vez y se comparten con los dos mapas
df_america = cargar_datos_america()

tab_inicio, tab_mapa, tab_tiros = st.tabs(["Inicio", "Mapa de calor", "Mapa de tiros"])

# ---------------------------------------------------------------------------
# Pestaña 1: tu página original
# ---------------------------------------------------------------------------
with tab_inicio:
    st.write("Esta es una página básica para empezar a aprender Streamlit.")

    nombre = st.text_input("¿Cómo te llamas?")
    if st.button("Saludar"):
        if nombre:
            st.success(f"¡Hola, {nombre}! Bienvenido/a.")
        else:
            st.warning("Escribe tu nombre primero.")

    st.divider()

    st.subheader("Gráfico de ejemplo")
    n_puntos = st.slider("Número de puntos", min_value=10, max_value=200, value=50)
    mostrar_tabla = st.checkbox("Mostrar tabla de datos", value=False)

    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "x": rng.uniform(0, 120, n_puntos),
        "y": rng.uniform(0, 80, n_puntos),
    })

    pitch = Pitch(pitch_color="grass", line_color="white", stripe=True)
    fig, ax = pitch.draw(figsize=(8, 5))
    pitch.scatter(df["x"], df["y"], ax=ax, color="white", edgecolor="black", s=60)
    st.pyplot(fig)

    if mostrar_tabla:
        st.dataframe(df)

# ---------------------------------------------------------------------------
# Pestaña 2: mapa de calor (datos del América)
# ---------------------------------------------------------------------------
with tab_mapa:
    if df_america is not None:
        mostrar_mapa_calor(df_america)

# ---------------------------------------------------------------------------
# Pestaña 3: mapa de tiros (datos del América)
# ---------------------------------------------------------------------------
with tab_tiros:
    if df_america is not None:
        mostrar_mapa_tiros(df_america)

st.caption("Hecho con Streamlit 🚀")