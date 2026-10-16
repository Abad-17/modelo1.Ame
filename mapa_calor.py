
import re
 
import streamlit as st
from matplotlib.colors import LinearSegmentedColormap
from mplsoccer import Pitch
 
from datos_america import EQUIPO_REGEX, ORIGENES
 
# Estilo: fondo negro, líneas de cancha en gris azulado y mancha azul
COLOR_FONDO = "#000000"
COLOR_LINEAS = "#6b7c93"
COLOR_TEXTO = "#e6edf5"
CMAP_AZUL = LinearSegmentedColormap.from_list(
    "mancha_azul", [COLOR_FONDO, "#0a2a66", "#1864c9", "#3b9cff", "#8cc8ff"]
)
 
 
def dibujar_mancha(df, suavizado=1.0, titulo="", subtitulo=""):
    """Mapa de calor tipo mancha (KDE) sobre cancha negra con la mancha en azul.
    df necesita columnas x, y (cancha StatsBomb 120x80, el equipo ataca hacia x=120)."""
    pitch = Pitch(pitch_type="statsbomb", pitch_color=COLOR_FONDO, line_color=COLOR_LINEAS,
                  linewidth=1.2, line_zorder=3, goal_type="box")
    fig, axs = pitch.grid(figheight=7, title_height=0.09, endnote_height=0.07,
                          title_space=0.0, endnote_space=0.0, grid_height=0.84, axis=False)
    ax = axs["pitch"]
    fig.set_facecolor(COLOR_FONDO)
 
    if len(df) > 15000:
        df = df.sample(15000, random_state=1)
    pitch.kdeplot(df["x"], df["y"], ax=ax, fill=True, levels=80, thresh=0.02,
                  cmap=CMAP_AZUL, zorder=1, bw_adjust=max(0.5, 0.5 + suavizado * 0.3))
 
    axs["title"].text(0.5, 0.62, titulo, ha="center", va="center", fontsize=16,
                      fontweight="bold", color=COLOR_TEXTO)
    axs["title"].text(0.5, 0.14, subtitulo, ha="center", va="center", fontsize=10.5,
                      color=COLOR_TEXTO, alpha=0.8)
 
    axs["endnote"].annotate("", xy=(0.66, 0.68), xytext=(0.34, 0.68), xycoords="axes fraction",
                            arrowprops=dict(arrowstyle="-|>", color=COLOR_LINEAS, lw=2))
    axs["endnote"].text(0.5, 0.25, "Dirección de ataque", ha="center", va="center",
                        color=COLOR_TEXTO, fontsize=9.5, alpha=0.8)
    return fig
 
 
def mostrar_mapa_calor(df_total):
    """df_total: eventos del América (los entrega cargar_datos_america)."""
    st.subheader("Mapa de calor de la temporada")
 
    # ----------------------------------------------------------------
    # SECCIÓN 1 (arriba): el mapa
    # ----------------------------------------------------------------
    zona_mapa = st.container()
    st.divider()
 
    # ----------------------------------------------------------------
    # SECCIÓN 2 (abajo): parámetros / filtros
    # ----------------------------------------------------------------
    st.subheader("Parámetros del mapa de calor")
    df = df_total
    equipo, jugador = None, "Todos"
 
    f1, f2, f3 = st.columns(3)
    f4, f5, f6 = st.columns(3)
    f7, f8, f9 = st.columns(3)
 
    with f1:
        equipos = sorted(df["team"].dropna().unique())
        idx = next((i for i, e in enumerate(equipos) if re.search(EQUIPO_REGEX, str(e), re.I)), 0)
        equipo = st.selectbox("Equipo", equipos, index=idx, key="mc_equipo")
        df = df[df["team"] == equipo]
 
    # Los partidos se cuentan antes de filtrar por tipo de evento
    with f2:
        etiquetas = sorted(df["partido"].unique())
        part_sel = st.multiselect("Partidos", etiquetas, default=etiquetas, key="mc_partidos")
        df = df[df["partido"].isin(part_sel)]
        n_partidos = len(part_sel)
 
    tipos_sel = []
    with f3:
        tipos = sorted(df["type"].dropna().unique())
        defecto = ["Shot"] if "Shot" in tipos else (["Pass"] if "Pass" in tipos else tipos[:1])
        tipos_sel = st.multiselect("Tipo de evento", tipos, default=defecto, key="mc_tipos")
        df = df[df["type"].isin(tipos_sel)]
 
    with f4:
        jugadores = ["Todos"] + sorted(df["player"].dropna().unique())
        jugador = st.selectbox("Jugador", jugadores, key="mc_jugador")
        if jugador != "Todos":
            df = df[df["player"] == jugador]
 
    with f5:
        periodos = sorted(df["period"].dropna().unique())
        per_sel = st.multiselect("Periodo", periodos, default=periodos, key="mc_periodo")
        df = df[df["period"].isin(per_sel)]
 
    with f6:
        patrones = sorted(df["play_pattern"].dropna().unique())
        pat_sel = st.multiselect("Patrón de juego", patrones, default=patrones, key="mc_patron")
        df = df[df["play_pattern"].isin(pat_sel)]
 
    with f7:
        if "under_pressure" in df.columns and st.checkbox("Solo eventos bajo presión", key="mc_presion"):
            df = df[df["under_pressure"].astype(str).str.lower() == "true"]
 
    with f8:
        disponibles = {k: v for k, v in ORIGENES.items() if v + "_x" in df.columns}
        if not disponibles:
            st.error("Los eventos descargados no traen columnas de ubicación (location).")
            return
        origen_txt = st.selectbox("Qué ubicación mostrar", list(disponibles), key="mc_origen")
        col = disponibles[origen_txt]
 
    with f9:
        suavizado = st.slider("Suavizado de la mancha", 0.0, 3.0, 1.0, 0.1, key="mc_suavizado")
 
    df = df.dropna(subset=[col + "_x", col + "_y"])
    df = df.assign(x=df[col + "_x"], y=df[col + "_y"])
 
    # ----------------------------------------------------------------
    # Dibujo en el contenedor superior
    # ----------------------------------------------------------------
    with zona_mapa:
        if n_partidos == 0:
            st.warning("Selecciona al menos un partido.")
            return
        if len(df) < 3:
            st.warning("Hay muy pocos eventos con esos filtros para dibujar la mancha.")
            return
 
        partes = [equipo]
        if jugador != "Todos":
            partes.append(jugador)
        titulo = " · ".join(partes)
        subtitulo = (f"{', '.join(tipos_sel) if tipos_sel else 'Eventos'} · "
                     f"{len(df):,} eventos · {n_partidos} partido(s)")
 
        st.pyplot(dibujar_mancha(df, suavizado=suavizado, titulo=titulo, subtitulo=subtitulo))
 
        c1, c2, c3 = st.columns(3)
        c1.metric("Partidos", n_partidos)
        c2.metric("Eventos mostrados", f"{len(df):,}")
        c3.metric("Eventos por partido", f"{len(df) / n_partidos:.1f}")