import re

import matplotlib.pyplot as plt
import streamlit as st
from mplsoccer import VerticalPitch

from datos_america import EQUIPO_REGEX, nombre_equipo


def mostrar_mapa_tiros(df_total):
    """df_total: eventos del América (los entrega cargar_datos_america)."""
    st.subheader("Mapa de tiros")

    # Solo tiros con ubicación
    tiros = df_total[df_total["type"] == "Shot"].dropna(subset=["location_x", "location_y"]).copy()
    tiros = tiros.assign(
        x=tiros["location_x"],
        y=tiros["location_y"],
        shot_statsbomb_xg=tiros["shot_statsbomb_xg"].fillna(0),
    )
    if tiros.empty:
        st.warning("No hay tiros con ubicación en los datos descargados.")
        return

    equipo = nombre_equipo(df_total)
    tiros["es_equipo"] = tiros["team"].astype(str).str.contains(EQUIPO_REGEX, case=False, regex=True)

    # ------------------------------------------------------------------
    # SECCIÓN 1 (arriba): mapa de tiros
    # ------------------------------------------------------------------
    zona_mapa = st.container()
    st.divider()

    # ------------------------------------------------------------------
    # SECCIÓN 2 (abajo): parámetros
    # ------------------------------------------------------------------
    st.subheader("Parámetros del mapa de tiros")

    c1, c2, c3 = st.columns(3)
    with c1:
        vista = st.radio("Vista", [f"Ataque {equipo}", f"Defensa {equipo}"], key="mt_vista")
    with c2:
        partidos = sorted(tiros["partido"].unique())
        partidos_sel = st.multiselect("Partidos", partidos, default=partidos, key="mt_partidos")
    with c3:
        max_min = int(tiros["minute"].max())
        rango_min = st.slider("Minutos", 0, max_min, (0, max_min), key="mt_min")

    c4, c5, c6 = st.columns(3)
    with c4:
        partes = sorted(tiros["shot_body_part"].dropna().unique())
        partes_sel = st.multiselect("Parte del cuerpo", partes, default=partes, key="mt_cuerpo")
    with c5:
        tipos = sorted(tiros["shot_type"].dropna().unique())
        tipos_sel = st.multiselect("Tipo de tiro", tipos, default=tipos, key="mt_tipo")
    with c6:
        escala = st.slider("Tamaño de los círculos (xG)", 100, 1000, 500, 50, key="mt_escala")
        alpha_tiros = st.slider("Transparencia de tiros", 0.2, 1.0, 0.6, 0.05, key="mt_alpha")

    c7, c8, c9 = st.columns(3)
    with c7:
        mostrar_goles = st.checkbox("Mostrar goles", value=True, key="mt_goles")
    with c8:
        mostrar_no_goles = st.checkbox("Mostrar tiros sin gol", value=True, key="mt_nogoles")
    with c9:
        color_gol = st.color_picker("Color de los goles", "#1f4fff", key="mt_color")

    # ------------------------------------------------------------------
    # Filtrado
    # ------------------------------------------------------------------
    if vista.startswith("Ataque"):
        df = tiros[tiros["es_equipo"]]
        titulo = f"Ataque\n{equipo}"
    else:
        df = tiros[~tiros["es_equipo"]]
        titulo = f"Defensa\n{equipo}"

    df = df[df["partido"].isin(partidos_sel)]
    df = df[(df["minute"] >= rango_min[0]) & (df["minute"] <= rango_min[1])]
    df = df[df["shot_body_part"].isin(partes_sel) & df["shot_type"].isin(tipos_sel)]

    goles = df[df["shot_outcome"] == "Goal"]
    no_goles = df[df["shot_outcome"] != "Goal"]

    # ------------------------------------------------------------------
    # Dibujo dentro del contenedor superior
    # ------------------------------------------------------------------
    with zona_mapa:
        if df.empty:
            st.warning("No hay tiros con los filtros seleccionados.")
            return

        fig, ax = plt.subplots(figsize=(16, 9))
        pitch = VerticalPitch(pitch_type="statsbomb", goal_type="box", half=True)
        pitch.draw(ax=ax)

        # espacio a la derecha para el resumen
        plt.xlim(-5, 100)

        if mostrar_goles and not goles.empty:
            pitch.scatter(
                goles.x, goles.y, ax=ax,
                s=goles.shot_statsbomb_xg * escala,
                alpha=0.9, ec="black", label="Goles", color=color_gol, zorder=0.99,
            )
        if mostrar_no_goles and not no_goles.empty:
            pitch.scatter(
                no_goles.x, no_goles.y, ax=ax,
                s=no_goles.shot_statsbomb_xg * escala,
                alpha=alpha_tiros, ec="black", label="Tiros", color="white", zorder=0,
            )

        plt.legend(ncol=2, loc="lower center", prop={"size": 16}, shadow=True, edgecolor="black")

        ax.text(90, 115, titulo, va="center", ha="center", fontsize=25)
        ax.text(90, 100, f"{len(df)} Tiros", va="center", ha="center", fontsize=20)
        ax.text(90, 90, f"{len(goles)} Goles", va="center", ha="center", fontsize=20)
        ax.text(90, 80, f"{round(df.shot_statsbomb_xg.sum(), 2)} xG", va="center", ha="center", fontsize=20)

        st.pyplot(fig)
        plt.close(fig)