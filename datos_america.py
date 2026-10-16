import os
import re
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
from statsbombpy import sb

# ---------------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / ".cache_statsbomb"

COMPETICION_REGEX = r"Liga MX|Mexico"
EQUIPO_REGEX = r"Am[eé]rica"          # coincide con "América" y "America"

# Columnas de coordenadas según la especificación StatsBomb v11
ORIGENES = {
    "Inicio del evento (location)": "location",
    "Fin del pase (pass_end_location)": "pass_end_location",
    "Fin de la conducción (carry_end_location)": "carry_end_location",
    "Fin del tiro (shot_end_location)": "shot_end_location",
}

# Solo se guardan estas columnas (más rápido y ocupa menos memoria).
# Se agregaron las de tiros: xG, resultado, parte del cuerpo, tipo y equipo en posesión.
COLUMNAS_USADAS = {
    "match_id", "type", "team", "possession_team", "player", "period", "minute",
    "play_pattern", "under_pressure",
    "shot_statsbomb_xg", "shot_outcome", "shot_body_part", "shot_type",
    *ORIGENES.values(),
}

TEXTOS_DE_EJEMPLO = {"tu_contraseña", "tu contraseña real", "tu_usuario"}

AVISO_SIN_DATOS = (
    "La API de StatsBomb no devolvió datos. Casi siempre es que el usuario o la contraseña "
    "son incorrectos (o la cuenta no tiene acceso). Revisa la terminal: statsbombpy imprime "
    "una línea como '.../competitions -> 401'. Un 401 es contraseña incorrecta y un 403 es "
    "cuenta sin acceso."
)


# ---------------------------------------------------------------------------
# ACCESO A LA API
# ---------------------------------------------------------------------------
def obtener_credenciales():
    """Busca credenciales en .streamlit/secrets.toml, luego en variables de entorno
    (STATSBOMB_USER / STATSBOMB_PASSWD) y, si no, las pide en la barra lateral."""
    try:
        cfg = st.secrets["statsbomb"]
        user, passwd = str(cfg["user"]).strip(), str(cfg["passwd"]).strip()
        if user and passwd and passwd not in TEXTOS_DE_EJEMPLO:
            return {"user": user, "passwd": passwd}
    except Exception:
        pass
    user, passwd = os.getenv("STATSBOMB_USER"), os.getenv("STATSBOMB_PASSWD")
    if user and passwd and passwd.strip() not in TEXTOS_DE_EJEMPLO:
        return {"user": user.strip(), "passwd": passwd.strip()}

    with st.sidebar.expander("Credenciales de StatsBomb", expanded=True):
        user = st.text_input("Usuario (correo)", key="sb_user")
        passwd = st.text_input("Contraseña", type="password", key="sb_passwd")
    if user and passwd:
        return {"user": user.strip(), "passwd": passwd}
    return None


@st.cache_data(ttl=3600, show_spinner="Consultando competiciones en StatsBomb...")
def listar_temporadas(_creds):
    comp = sb.competitions(creds=_creds)
    if comp is None or comp.empty or "competition_name" not in comp.columns:
        raise PermissionError(AVISO_SIN_DATOS)
    comp = comp[comp["competition_name"].str.contains(COMPETICION_REGEX, case=False, na=False)]
    cols = ["competition_id", "season_id", "competition_name", "season_name"]
    return comp[cols].sort_values("season_name", ascending=False).reset_index(drop=True)


def _extraer_xy(serie):
    def componente(i):
        return serie.map(
            lambda p: p[i] if isinstance(p, (list, tuple, np.ndarray)) and len(p) >= 2 else np.nan
        )
    return pd.to_numeric(componente(0), errors="coerce"), pd.to_numeric(componente(1), errors="coerce")


def _preparar(df):
    """Convierte las listas de coordenadas en columnas numéricas *_x, *_y."""
    for col in ORIGENES.values():
        if col in df.columns:
            df[col + "_x"], df[col + "_y"] = _extraer_xy(df[col])
            df = df.drop(columns=col)
    return df


def descargar_eventos(creds, competition_id, season_id, progreso=None):
    """Descarga los eventos de todos los partidos del América en la temporada.
    Devuelve (DataFrame o None, lista de partidos que fallaron)."""
    partidos = sb.matches(competition_id=competition_id, season_id=season_id, creds=creds)
    if partidos is None or partidos.empty or "home_team" not in partidos.columns:
        raise PermissionError(AVISO_SIN_DATOS)
    del_equipo = (
        partidos["home_team"].str.contains(EQUIPO_REGEX, case=False, na=False, regex=True)
        | partidos["away_team"].str.contains(EQUIPO_REGEX, case=False, na=False, regex=True)
    )
    partidos = partidos[del_equipo]

    if "match_status" in partidos.columns:
        disponibles = partidos[partidos["match_status"] == "available"]
        if not disponibles.empty:
            partidos = disponibles

    # Etiqueta legible de cada partido: "2025-02-01 · América vs Pumas"
    etiquetas = {}
    for r in partidos.itertuples():
        fecha = str(getattr(r, "match_date", ""))
        etiquetas[r.match_id] = (fecha, f"{fecha} · {r.home_team} vs {r.away_team}")

    ids = list(partidos["match_id"])
    piezas, fallidos = [], []
    for i, match_id in enumerate(ids, start=1):
        if progreso:
            progreso(i, len(ids), match_id)
        try:
            ev = sb.events(match_id=match_id, creds=creds)
        except Exception as e:
            fallidos.append((match_id, str(e)[:120]))
            continue
        if ev is None or ev.empty:
            fallidos.append((match_id, "sin eventos"))
            continue
        ev = ev[[c for c in COLUMNAS_USADAS if c in ev.columns]].copy()
        ev["match_id"] = match_id
        ev["fecha"], ev["partido"] = etiquetas[match_id]
        piezas.append(ev)

    if not piezas:
        return None, fallidos
    return _preparar(pd.concat(piezas, ignore_index=True)), fallidos


@st.cache_data(show_spinner="Leyendo datos guardados...")
def leer_cache(ruta, firma):
    return pd.read_pickle(ruta)


def nombre_equipo(df):
    """Nombre exacto del América tal como viene en los datos (p. ej. 'América')."""
    if "team" in df.columns:
        for e in sorted(df["team"].dropna().unique()):
            if re.search(EQUIPO_REGEX, str(e), re.I):
                return e
    return "América"


def cargar_datos_america():
    """Devuelve el DataFrame de eventos del América (de caché o descargándolo), o None.
    Debe llamarse UNA sola vez por ejecución (usa widgets de la barra lateral)."""
    st.sidebar.header("Datos")
    creds = obtener_credenciales()
    if creds is None:
        st.info(
            "Escribe tu usuario y contraseña de StatsBomb en la barra lateral para descargar los datos. "
            "Si no quieres escribirlos cada vez, guárdalos en `.streamlit/secrets.toml` "
            "(sección `[statsbomb]` con `user` y `passwd`)."
        )
        return None

    try:
        temporadas = listar_temporadas(creds)
    except Exception as e:
        st.error(f"No pude conectar con la API de StatsBomb: {e}")
        return None
    if temporadas.empty:
        st.warning(f"La API no devolvió competiciones que coincidan con '{COMPETICION_REGEX}'.")
        return None

    etiquetas = [f"{r.competition_name} {r.season_name}" for r in temporadas.itertuples()]
    elegida = st.sidebar.selectbox("Temporada", etiquetas)
    fila = temporadas.iloc[etiquetas.index(elegida)]
    comp_id, season_id = int(fila["competition_id"]), int(fila["season_id"])

    CACHE_DIR.mkdir(exist_ok=True)
    # v2: incluye las columnas de tiros; ignora cachés viejas que no las traen
    ruta = CACHE_DIR / f"eventos_v2_{comp_id}_{season_id}.pkl"

    if st.sidebar.button("Actualizar desde la API"):
        ruta.unlink(missing_ok=True)
        leer_cache.clear()

    if not ruta.exists():
        barra = st.progress(0.0, text="Conectando con StatsBomb...")

        def progreso(i, total, match_id):
            barra.progress(i / max(total, 1), text=f"Descargando partido {i} de {total} (id {match_id})...")

        try:
            df, fallidos = descargar_eventos(creds, comp_id, season_id, progreso)
        except Exception as e:
            barra.empty()
            st.error(f"Error al descargar los datos de StatsBomb: {e}")
            return None
        barra.empty()
        if df is None:
            st.warning(f"No encontré partidos de '{EQUIPO_REGEX}' en {elegida}.")
            if fallidos:
                st.caption(f"Partidos con error: {fallidos}")
            return None
        df.to_pickle(ruta)
        if fallidos:
            st.warning(f"No se pudieron descargar {len(fallidos)} partido(s): "
                       + ", ".join(str(m) for m, _ in fallidos))

    df = leer_cache(str(ruta), ruta.stat().st_mtime)
    st.sidebar.success(f"{len(df):,} eventos | {df['match_id'].nunique()} partido(s)")
    # Guardado para reutilizarlo en otras partes de la app (p. ej. el modelo)
    st.session_state["df_eventos"] = df
    return df
