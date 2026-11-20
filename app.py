# -*- coding: utf-8 -*-
"""Aplicación Streamlit: actividad agrícola de Costa Rica.

Los componentes espacial (VI CENAGRO) y productivo (MAG/SEPSA) se presentan
como análisis independientes y complementarios. No se cruzan sus variables.
"""

from pathlib import Path
import copy
import re
import unicodedata

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium


# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE LA PÁGINA (debe ser la primera llamada a Streamlit)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Actividad agrícola de Costa Rica",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------------------------------------------------------
# 2. RUTAS Y CONSTANTES
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CSV_NAME = "cenagro_cantones_limpio.csv"
XLSX_NAME = (
    "Costa Rica. Extensión sembrada y producción de las principales "
    "actividades agrícolas (hectáreas y toneladas métricas).xlsx"
)
CANTONES_URL = (
    "https://raw.githubusercontent.com/maufonsecasdfg/"
    "costa-rica-geojson/main/costaricacantones.geojson"
)

INEC_URL = "https://www.inec.cr/censos/censo-agropecuario-2014"
SNIT_URL = "https://www.snitcr.go.cr/"
SEPSA_REPO_URL = "https://github.com/luisgonzaveg-prog/tarea2_graficos"
CENAGRO_REPO_URL = "https://github.com/luisgonzaveg-prog/tarea3"


# -----------------------------------------------------------------------------
# 3. FUNCIONES AUXILIARES
# -----------------------------------------------------------------------------
def buscar_archivo(nombre: str) -> Path:
    """Busca el archivo junto a app.py o dentro de una carpeta datos/."""
    candidatos = [BASE_DIR / nombre, BASE_DIR / "datos" / nombre]
    for ruta in candidatos:
        if ruta.exists():
            return ruta
    rutas = "\n".join(f"- {ruta}" for ruta in candidatos)
    raise FileNotFoundError(
        f"No se encontró '{nombre}'. Se buscó en estas ubicaciones:\n{rutas}"
    )


def normalizar_texto(valor) -> str:
    """Normaliza nombres para facilitar la unión de cantones."""
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto


def convertir_numerico(serie: pd.Series) -> pd.Series:
    """Convierte columnas numéricas sin alterar los valores ya numéricos."""
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")
    texto = serie.astype(str).str.strip()
    # Los datos del Excel se esperan numéricos; se contemplan separadores
    # de miles comunes cuando los valores vienen como texto.
    texto = texto.str.replace(" ", "", regex=False)
    texto = texto.str.replace(",", "", regex=False)
    return pd.to_numeric(texto, errors="coerce")


# -----------------------------------------------------------------------------
# 4. CARGA DE DATOS EN CACHÉ
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner="Leyendo la base del VI CENAGRO...")
def cargar_cenagro(ruta_csv: str) -> pd.DataFrame:
    """Carga la tabla cantonal del CENAGRO."""
    try:
        df = pd.read_csv(ruta_csv, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(ruta_csv, encoding="latin-1")

    requeridas = {"canton_key", "total_fincas", "extension_hectareas"}
    faltantes = requeridas.difference(df.columns)
    if faltantes:
        raise ValueError(
            "El CSV del CENAGRO no contiene las columnas esperadas: "
            + ", ".join(sorted(faltantes))
        )

    df = df.copy()
    df["canton_key"] = df["canton_key"].astype(str).str.strip()
    df["llave_union"] = df["canton_key"].map(normalizar_texto)
    df["total_fincas"] = convertir_numerico(df["total_fincas"]).fillna(0)
    df["extension_hectareas"] = convertir_numerico(
        df["extension_hectareas"]
    ).fillna(0)
    df = df[df["llave_union"] != "COSTA RICA"].copy()
    return df


@st.cache_data(show_spinner="Leyendo la base de cultivos MAG/SEPSA...")
def cargar_cultivos(ruta_xlsx: str) -> tuple[pd.DataFrame, pd.DataFrame, int | None]:
    """Reproduce la extracción del notebook de la Tarea 2.

    Obtiene los datos del último año disponible (dos últimas columnas del
    archivo) y la serie histórica de producción de café.
    """
    raw = pd.read_excel(ruta_xlsx, header=None, engine="openpyxl")
    if raw.shape[0] <= 6 or raw.shape[1] < 3:
        raise ValueError("El Excel de SEPSA no tiene la estructura esperada.")

    # En el archivo original, la fila 4 contiene los años y las celdas
    # combinadas se completan hacia adelante, tal como en el notebook.
    anios_completos = raw.iloc[4, :].ffill()
    datos = raw.iloc[6:].copy()
    datos.columns = range(datos.shape[1])

    col_area = datos.shape[1] - 2
    col_produccion = datos.shape[1] - 1
    reciente = datos.iloc[:, [0, col_area, col_produccion]].copy()
    reciente.columns = ["Cultivo", "Area_Sembrada_ha", "Produccion_ton"]

    reciente["Cultivo"] = reciente["Cultivo"].astype(str).str.strip()
    reciente["Area_Sembrada_ha"] = convertir_numerico(
        reciente["Area_Sembrada_ha"]
    )
    reciente["Produccion_ton"] = convertir_numerico(
        reciente["Produccion_ton"]
    )
    reciente = reciente.dropna(
        subset=["Area_Sembrada_ha", "Produccion_ton"]
    )
    reciente = reciente[
        (reciente["Cultivo"] != "")
        & (reciente["Cultivo"].str.lower() != "nan")
        & (~reciente["Cultivo"].str.isupper())
    ].copy()

    # Evita infinitos cuando el área sembrada es cero.
    reciente["Rendimiento_ton_ha"] = np.where(
        reciente["Area_Sembrada_ha"] > 0,
        reciente["Produccion_ton"] / reciente["Area_Sembrada_ha"],
        np.nan,
    )

    # Identificación del año más reciente disponible.
    anio_reciente = None
    valores_anio = pd.to_numeric(anios_completos, errors="coerce").dropna()
    if not valores_anio.empty:
        anio_reciente = int(valores_anio.iloc[-1])

    # Serie histórica de producción de café, según la estructura del notebook.
    anios = []
    for col in range(1, raw.shape[1], 2):
        anio = pd.to_numeric(raw.iloc[4, col], errors="coerce")
        if pd.notna(anio):
            anios.append(int(anio))

    cafe = datos[
        datos[0].astype(str).str.contains("café|cafe", case=False, na=False)
    ]
    if not cafe.empty:
        produccion_cafe = cafe.iloc[0, 2::2].values
        n = min(len(anios), len(produccion_cafe))
        serie_cafe = pd.DataFrame(
            {
                "Año": anios[:n],
                "Produccion_ton": pd.to_numeric(
                    produccion_cafe[:n], errors="coerce"
                ),
            }
        ).dropna()
        serie_cafe = serie_cafe.sort_values("Año").reset_index(drop=True)
    else:
        serie_cafe = pd.DataFrame(columns=["Año", "Produccion_ton"])

    return reciente.reset_index(drop=True), serie_cafe, anio_reciente


@st.cache_data(show_spinner="Procesando cartografía y datos cantonales...")
def cargar_capa_agricola(ruta_csv: str, url_geojson: str) -> gpd.GeoDataFrame:
    """Une los datos del CENAGRO con cantones y calcula áreas en CRTM05.

    La capa se reproyecta a WGS84 al final para su representación web.
    """
    df = cargar_cenagro(ruta_csv)
    cantones = gpd.read_file(url_geojson)

    columnas_geo = {"NAME_1", "NAME_2", "geometry"}
    faltantes_geo = columnas_geo.difference(cantones.columns)
    if faltantes_geo:
        raise ValueError(
            "La cartografía no contiene los campos esperados: "
            + ", ".join(sorted(faltantes_geo))
        )

    if cantones.crs is None:
        raise ValueError("La cartografía de cantones no declara un SRC.")

    cantones = cantones.to_crs(epsg=5367)
    cantones["llave_union"] = cantones["NAME_2"].map(normalizar_texto)

    # Se conserva la lógica del notebook: unión por nombre de cantón.
    agro = cantones.merge(
        df[["llave_union", "total_fincas", "extension_hectareas"]],
        on="llave_union",
        how="left",
    )
    agro["total_fincas"] = agro["total_fincas"].fillna(0)
    agro["extension_hectareas"] = agro["extension_hectareas"].fillna(0)

    agro["area_canton_km2"] = agro.geometry.area / 1_000_000
    agro["area_canton_ha"] = agro["area_canton_km2"] * 100
    agro["porcentaje_agro"] = np.where(
        agro["area_canton_ha"] > 0,
        agro["extension_hectareas"] / agro["area_canton_ha"] * 100,
        np.nan,
    )

    # Los mapas web deben estar en WGS84 (EPSG:4326).
    return agro.to_crs(epsg=4326)


# -----------------------------------------------------------------------------
# 5. MAPA FOLIUM EN CACHÉ DE RECURSOS
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Construyendo el mapa interactivo...")
def construir_mapa(provincia: str, rango_extension: tuple[float, float], ruta_csv: str,
                    url_geojson: str) -> folium.Map:
    """Construye el mapa con las capas que dependen de los filtros laterales."""
    gdf = cargar_capa_agricola(ruta_csv, url_geojson)

    if provincia != "Todas":
        gdf = gdf[gdf["NAME_1"] == provincia].copy()
    gdf = gdf[
        gdf["extension_hectareas"].between(rango_extension[0], rango_extension[1])
    ].copy()

    mapa = folium.Map(
        location=[9.75, -83.75],
        zoom_start=7,
        tiles="CartoDB positron",
        control_scale=True,
    )

    if gdf.empty:
        folium.Marker(
            location=[9.75, -83.75],
            tooltip="No hay cantones que cumplan los filtros seleccionados.",
        ).add_to(mapa)
        return mapa

    campos_tooltip = [
        "NAME_2", "NAME_1", "total_fincas", "extension_hectareas",
        "porcentaje_agro",
    ]
    alias_tooltip = [
        "Cantón:", "Provincia:", "Total de fincas:",
        "Extensión agrícola (ha):", "Superficie agrícola (%):",
    ]

    # Capa temática 1: porcentaje de superficie agrícola por cantón.
    capa_coropletas = folium.FeatureGroup(
        name="Porcentaje de superficie agrícola (%)", show=True
    )
    valores = gdf["porcentaje_agro"].replace([np.inf, -np.inf], np.nan).dropna()
    if valores.empty:
        minimo, maximo = 0.0, 1.0
    else:
        minimo = float(valores.min())
        maximo = float(valores.max())
        if minimo == maximo:
            maximo = minimo + 1.0

    escala = folium.LinearColormap(
        colors=["#ffffcc", "#c2e699", "#78c679", "#31a354", "#006837"],
        vmin=minimo,
        vmax=maximo,
    )
    escala.caption = "Porcentaje de superficie agrícola cantonal (%)"
    escala.add_to(mapa)

    def estilo_coropleta(feature):
        valor = feature["properties"].get("porcentaje_agro")
        try:
            color = escala(float(valor))
        except (TypeError, ValueError):
            color = "#d9d9d9"
        return {
            "fillColor": color,
            "color": "#65736a",
            "weight": 0.65,
            "fillOpacity": 0.78,
        }

    folium.GeoJson(
        gdf,
        name="Coropletas cantonales",
        style_function=estilo_coropleta,
        tooltip=folium.GeoJsonTooltip(
            fields=campos_tooltip,
            aliases=alias_tooltip,
            localize=True,
            sticky=True,
            labels=True,
        ),
    ).add_to(capa_coropletas)
    capa_coropletas.add_to(mapa)

    # Capa temática 2: mapa de calor a partir de centroides cantonales.
    # Los centroides se calculan en CRTM05 y luego se reproyectan a WGS84.
    gdf_proyectado = gdf.to_crs(epsg=5367)
    puntos = gdf_proyectado.copy()
    puntos["geometry"] = puntos.geometry.centroid
    puntos = puntos.to_crs(epsg=4326)
    heat_data = [
        [float(fila.geometry.y), float(fila.geometry.x),
         float(fila.extension_hectareas)]
        for fila in puntos.itertuples()
        if pd.notna(fila.extension_hectareas) and fila.extension_hectareas > 0
    ]

    capa_calor = folium.FeatureGroup(name="Concentración agrícola (mapa de calor)", show=False)
    if heat_data:
        HeatMap(
            heat_data,
            min_opacity=0.25,
            radius=22,
            blur=16,
            max_zoom=13,
        ).add_to(capa_calor)
    capa_calor.add_to(mapa)

    # Capa de referencia: límites cantonales sin relleno.
    capa_limites = folium.FeatureGroup(name="Límites cantonales (referencia)", show=False)
    folium.GeoJson(
        gdf,
        style_function=lambda feature: {
            "fillColor": "#ffffff",
            "color": "#46534b",
            "weight": 1.0,
            "fillOpacity": 0.02,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["NAME_2", "NAME_1"],
            aliases=["Cantón:", "Provincia:"],
            localize=True,
        ),
    ).add_to(capa_limites)
    capa_limites.add_to(mapa)

    folium.LayerControl(collapsed=False).add_to(mapa)
    bounds = gdf.total_bounds  # minx, miny, maxx, maxy en WGS84
    mapa.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    return mapa


# -----------------------------------------------------------------------------
# 6. ENCABEZADO E INTRODUCCIÓN
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
      .main-title {font-size: 2.25rem; font-weight: 750; color: #174d36; margin-bottom: .2rem;}
      .sub-title {color: #5b6b62; font-size: 1rem; margin-top: 0;}
      div[data-testid="stMetric"] {
        background: #f4f8f4 !important;
        border: 1px solid #dce7dd !important;
        padding: 14px 16px;
        border-radius: 12px;
      }
      div[data-testid="stMetric"] label,
      div[data-testid="stMetric"] label *,
      div[data-testid="stMetricValue"],
      div[data-testid="stMetricValue"] *,
      div[data-testid="stMetricDelta"],
      div[data-testid="stMetricDelta"] * {
        color: #20352a !important;
        -webkit-text-fill-color: #20352a !important;
      }
      .section-note {color: #5b6b62; font-size: .92rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">Actividad agrícola de Costa Rica</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Distribución espacial de la extensión agropecuaria y '
    'caracterización estadística de los principales cultivos</div>',
    unsafe_allow_html=True,
)
st.write(
    "Esta aplicación reúne dos análisis complementarios de la actividad agrícola "
    "costarricense. El componente espacial utiliza información cantonal del VI Censo "
    "Nacional Agropecuario (CENAGRO, 2014) para visualizar extensión agrícola, fincas "
    "y proporción de superficie agropecuaria. El componente productivo utiliza datos "
    "de extensión sembrada y producción de MAG/SEPSA para comparar cultivos y observar "
    "la evolución histórica del café. **Son fuentes y unidades de análisis distintas:** "
    "no se relacionan espacialmente ni se correlacionan entre sí. Utilice el selector "
    "de la barra lateral para cambiar de componente y sus filtros correspondientes."
)


# -----------------------------------------------------------------------------
# 7. CARGA DE ARCHIVOS
# -----------------------------------------------------------------------------
try:
    ruta_csv = str(buscar_archivo(CSV_NAME))
    ruta_xlsx = str(buscar_archivo(XLSX_NAME))
except FileNotFoundError as error:
    st.error(str(error))
    st.info(
        "Coloque ambos archivos en la misma carpeta que app.py o dentro de una "
        "subcarpeta llamada 'datos'."
    )
    st.stop()


# -----------------------------------------------------------------------------
# 8. CONTROLES DE LA BARRA LATERAL
# -----------------------------------------------------------------------------
st.sidebar.title("Explorar la información")
componente = st.sidebar.radio(
    "Componente de análisis",
    ["Distribución espacial", "Cultivos y producción"],
    help="Los componentes se analizan por separado porque utilizan bases y unidades distintas.",
)
st.sidebar.divider()


# -----------------------------------------------------------------------------
# 9. COMPONENTE ESPACIAL: VI CENAGRO
# -----------------------------------------------------------------------------
if componente == "Distribución espacial":
    st.sidebar.subheader("Filtros espaciales")

    try:
        gdf_completo = cargar_capa_agricola(ruta_csv, CANTONES_URL)
        provincias = ["Todas"] + sorted(gdf_completo["NAME_1"].dropna().unique().tolist())
        valores_extension = gdf_completo["extension_hectareas"].dropna()
        min_extension = float(valores_extension.min())
        max_extension = float(valores_extension.max())
        if min_extension == max_extension:
            max_extension = min_extension + 1.0
    except Exception as error:
        st.error(
            "No fue posible cargar la cartografía o unirla con el CSV del CENAGRO. "
            "Verifique la conexión a Internet, el archivo y sus columnas. "
            f"Detalle: {error}"
        )
        st.stop()

    provincia_sel = st.sidebar.selectbox("Provincia", provincias, index=0)
    rango_extension = st.sidebar.slider(
        "Rango de extensión agrícola por cantón (ha)",
        min_value=min_extension,
        max_value=max_extension,
        value=(min_extension, max_extension),
        step=max((max_extension - min_extension) / 100, 0.1),
        help=(
            "Seleccione el mínimo y el máximo de hectáreas que desea incluir. "
            "El rango se aplica al mapa, la tabla, los indicadores y el gráfico."
        ),
        format="%.1f",
    )

    datos_espaciales = gdf_completo.copy()
    if provincia_sel != "Todas":
        datos_espaciales = datos_espaciales[
            datos_espaciales["NAME_1"] == provincia_sel
        ].copy()
    datos_espaciales = datos_espaciales[
        datos_espaciales["extension_hectareas"].between(
            rango_extension[0], rango_extension[1]
        )
    ].copy()

    st.subheader("Distribución espacial de la actividad agropecuaria")
    st.caption(
        "Unidad de análisis: cantones. La extensión corresponde a superficie "
        "agropecuaria registrada en el VI CENAGRO (2014), no a toneladas producidas."
    )

    if datos_espaciales.empty:
        st.warning("Ningún cantón cumple los filtros seleccionados. Modifique los controles de la barra lateral.")
        st.stop()

    # Indicadores calculados sobre la selección espacial actual.
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cantones seleccionados", f"{len(datos_espaciales):,}")
    col2.metric(
        "Extensión agrícola",
        f"{datos_espaciales['extension_hectareas'].sum():,.0f} ha",
    )
    col3.metric("Fincas agropecuarias", f"{datos_espaciales['total_fincas'].sum():,.0f}")
    col4.metric(
        "Promedio de superficie agrícola",
        f"{datos_espaciales['porcentaje_agro'].mean():,.1f}%",
    )

    tab_resumen, tab_tabla, tab_mapa = st.tabs(
        ["Resumen y gráfico", "Tabla cantonal", "Mapa interactivo"]
    )

    with tab_resumen:
        st.markdown("#### Extensión agrícola por provincia")
        df_provincia = (
            datos_espaciales.groupby("NAME_1", as_index=False)["extension_hectareas"]
            .sum()
            .sort_values("extension_hectareas", ascending=True)
        )
        fig_prov = px.bar(
            df_provincia,
            x="extension_hectareas",
            y="NAME_1",
            orientation="h",
            labels={
                "extension_hectareas": "Extensión agrícola (ha)",
                "NAME_1": "Provincia",
            },
            title="Extensión agrícola registrada por provincia",
            text_auto=".2s",
        )
        fig_prov.update_traces(marker_color="#32845b", textposition="outside")
        fig_prov.update_layout(
            height=470,
            xaxis_tickformat=",.0f",
            yaxis_title="Provincia",
            xaxis_title="Extensión agrícola (hectáreas)",
            margin=dict(l=20, r=35, t=70, b=30),
        )
        st.plotly_chart(fig_prov, use_container_width=True)

        top5 = datos_espaciales.nlargest(5, "extension_hectareas").copy()
        extension_seleccion = datos_espaciales["extension_hectareas"].sum()
        extension_top5 = top5["extension_hectareas"].sum()
        porcentaje_top5 = (
            extension_top5 / extension_seleccion * 100
            if extension_seleccion > 0 else 0
        )
        st.markdown("#### Cantones con mayor extensión agrícola en la selección")
        st.write(
            f"Los cinco cantones con mayor extensión agrícola reúnen "
            f"**{porcentaje_top5:.1f}%** de la extensión registrada en la selección actual."
        )
        st.dataframe(
            top5[["NAME_2", "NAME_1", "total_fincas", "extension_hectareas", "porcentaje_agro"]]
            .rename(columns={
                "NAME_2": "Cantón", "NAME_1": "Provincia",
                "total_fincas": "Total de fincas",
                "extension_hectareas": "Extensión agrícola (ha)",
                "porcentaje_agro": "Superficie agrícola (%)",
            }),
            hide_index=True,
            use_container_width=True,
        )

    with tab_tabla:
        st.markdown("#### Datos cantonales filtrados")
        tabla_espacial = datos_espaciales[
            ["NAME_2", "NAME_1", "total_fincas", "extension_hectareas", "porcentaje_agro"]
        ].rename(columns={
            "NAME_2": "Cantón", "NAME_1": "Provincia",
            "total_fincas": "Total de fincas",
            "extension_hectareas": "Extensión agrícola (ha)",
            "porcentaje_agro": "Superficie agrícola (%)",
        })
        st.dataframe(
            tabla_espacial,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Cantón": st.column_config.TextColumn("Cantón"),
                "Provincia": st.column_config.TextColumn("Provincia"),
                "Total de fincas": st.column_config.NumberColumn("Total de fincas", format="%,.0f"),
                "Extensión agrícola (ha)": st.column_config.NumberColumn("Extensión agrícola (ha)", format="%,.2f"),
                "Superficie agrícola (%)": st.column_config.NumberColumn("Superficie agrícola (%)", format="%.2f%%"),
            },
        )
        st.download_button(
            "Descargar tabla filtrada (CSV)",
            data=tabla_espacial.to_csv(index=False).encode("utf-8-sig"),
            file_name="cenagro_cantones_filtrados.csv",
            mime="text/csv",
        )

    with tab_mapa:
        st.markdown("#### Mapa interactivo de extensión agropecuaria")
        st.caption(
            "Active o desactive las capas mediante el control superior derecho. "
            "El mapa coroplético representa el porcentaje de superficie agrícola; "
            "el mapa de calor representa la extensión agrícola en los centroides cantonales."
        )
        try:
            mapa_base = construir_mapa(
                provincia_sel, rango_extension, ruta_csv, CANTONES_URL
            )
            mapa_para_dibujar = copy.deepcopy(mapa_base)
            st_folium(
                mapa_para_dibujar,
                use_container_width=True,
                height=650,
                key="mapa_cenagro",
            )
        except Exception as error:
            st.error(f"No fue posible construir el mapa interactivo: {error}")


# -----------------------------------------------------------------------------
# 10. COMPONENTE PRODUCTIVO: MAG/SEPSA
# -----------------------------------------------------------------------------
else:
    st.sidebar.subheader("Filtros productivos")
    try:
        cultivos, serie_cafe, anio_reciente = cargar_cultivos(ruta_xlsx)
    except Exception as error:
        st.error(
            "No fue posible leer el Excel de MAG/SEPSA. Verifique que el archivo "
            "sea el original y que esté en la carpeta indicada. "
            f"Detalle: {error}"
        )
        st.stop()

    nombres_cultivos = sorted(cultivos["Cultivo"].dropna().unique().tolist())
    cultivos_sel = st.sidebar.multiselect(
        "Cultivos incluidos",
        options=nombres_cultivos,
        default=nombres_cultivos,
        help="La selección se aplica a la tabla y a los gráficos del componente productivo.",
    )
    valores_area = cultivos["Area_Sembrada_ha"].dropna()
    min_area = float(valores_area.min())
    max_area = float(valores_area.max())
    if min_area == max_area:
        max_area = min_area + 1.0

    valores_produccion = cultivos["Produccion_ton"].dropna()
    min_produccion = float(valores_produccion.min())
    max_produccion = float(valores_produccion.max())
    if min_produccion == max_produccion:
        max_produccion = min_produccion + 1.0

    rango_area = st.sidebar.slider(
        "Rango de área sembrada (ha)",
        min_value=min_area,
        max_value=max_area,
        value=(min_area, max_area),
        step=max((max_area - min_area) / 100, 0.1),
        format="%.1f",
        help="El rango se calcula a partir de los valores reales de la base MAG/SEPSA.",
    )
    rango_produccion = st.sidebar.slider(
        "Rango de producción (toneladas)",
        min_value=min_produccion,
        max_value=max_produccion,
        value=(min_produccion, max_produccion),
        step=max((max_produccion - min_produccion) / 100, 0.1),
        format="%.1f",
        help="El rango se calcula a partir de los valores reales de la base MAG/SEPSA.",
    )

    datos_cultivos = cultivos[
        cultivos["Cultivo"].isin(cultivos_sel)
        & cultivos["Area_Sembrada_ha"].between(rango_area[0], rango_area[1])
        & cultivos["Produccion_ton"].between(
            rango_produccion[0], rango_produccion[1]
        )
    ].copy()

    titulo_anio = f" · {anio_reciente}" if anio_reciente is not None else ""
    st.subheader(f"Cultivos y producción agrícola{titulo_anio}")
    st.caption(
        "Fuente: MAG/SEPSA. Las cifras de esta sección corresponden a extensión "
        "sembrada y producción por cultivo; no representan una distribución por cantón."
    )

    if datos_cultivos.empty:
        st.warning("Ningún cultivo cumple los filtros seleccionados. Modifique los controles de la barra lateral.")
        st.stop()

    # Indicadores descriptivos de la selección. Se usa promedio y máximos para
    # evitar interpretar la suma de categorías agregadas y cultivos individuales
    # como un total nacional aditivo.
    col1, col2, col3 = st.columns(3)
    col1.metric("Registros de cultivos", f"{len(datos_cultivos):,}")
    col2.metric(
        "Promedio de área sembrada",
        f"{datos_cultivos['Area_Sembrada_ha'].mean():,.0f} ha",
    )
    cultivo_mayor = datos_cultivos.loc[
        datos_cultivos["Produccion_ton"].idxmax(), "Cultivo"
    ]
    col3.metric(
        "Mayor producción registrada",
        f"{datos_cultivos['Produccion_ton'].max():,.0f} t",
        help=f"Cultivo o categoría: {cultivo_mayor}",
    )

    tab_graficos, tab_datos = st.tabs(["Gráficos", "Tabla de cultivos"])

    with tab_graficos:
        # Gráfico 1: Top 20 por área sembrada, basado en el notebook de Tarea 2.
        st.markdown("#### Cultivos con mayor extensión sembrada")
        top20 = (
            datos_cultivos.nlargest(20, "Area_Sembrada_ha")
            .sort_values("Area_Sembrada_ha", ascending=True)
        )
        fig_area = px.bar(
            top20,
            x="Area_Sembrada_ha",
            y="Cultivo",
            orientation="h",
            title="Extensión sembrada en Costa Rica · principales registros",
            labels={
                "Area_Sembrada_ha": "Área sembrada (ha)",
                "Cultivo": "Cultivo o categoría",
            },
            text_auto=".2s",
        )
        fig_area.update_traces(marker_color="#4d936b", textposition="outside")
        fig_area.update_layout(height=650, xaxis_tickformat=",.0f", margin=dict(l=20, r=35, t=70, b=30))
        st.plotly_chart(fig_area, use_container_width=True)

        # Gráfico 2: relación área-producción entre registros del mismo Excel.
        st.markdown("#### Área sembrada y producción por cultivo")
        fig_disp = px.scatter(
            datos_cultivos,
            x="Area_Sembrada_ha",
            y="Produccion_ton",
            hover_name="Cultivo",
            size="Produccion_ton",
            size_max=24,
            labels={
                "Area_Sembrada_ha": "Área sembrada (ha)",
                "Produccion_ton": "Producción (toneladas métricas)",
            },
            title="Área sembrada frente a producción registrada",
        )
        fig_disp.update_traces(marker=dict(color="#2e8055", opacity=0.75, line=dict(width=0.7, color="#ffffff")))
        fig_disp.update_layout(height=500)
        st.plotly_chart(fig_disp, use_container_width=True)

        # Gráfico 3: serie temporal de café, solo si Café forma parte de la
        # selección y supera el umbral de área sembrada definido.
        contiene_cafe = datos_cultivos["Cultivo"].str.contains(
            "café|cafe", case=False, na=False
        ).any()
        if contiene_cafe and not serie_cafe.empty:
            st.markdown("#### Evolución histórica de la producción de café")
            fig_cafe = px.line(
                serie_cafe,
                x="Año",
                y="Produccion_ton",
                markers=True,
                title="Producción histórica de café en Costa Rica",
                labels={
                    "Año": "Año",
                    "Produccion_ton": "Producción (toneladas métricas)",
                },
            )
            fig_cafe.update_traces(line=dict(color="#8a5a36", width=3), marker=dict(size=8))
            fig_cafe.update_layout(height=430, yaxis_tickformat=",.0f")
            st.plotly_chart(fig_cafe, use_container_width=True)
        else:
            st.info(
                "La serie histórica del café se muestra cuando el cultivo Café está "
                "incluido en la selección y cumple el filtro de área mínima."
            )

    with tab_datos:
        st.markdown("#### Tabla de extensión sembrada y producción")
        tabla_cultivos = datos_cultivos[
            ["Cultivo", "Area_Sembrada_ha", "Produccion_ton", "Rendimiento_ton_ha"]
        ].rename(columns={
            "Area_Sembrada_ha": "Área sembrada (ha)",
            "Produccion_ton": "Producción (t)",
            "Rendimiento_ton_ha": "Rendimiento (t/ha)",
        })
        st.dataframe(
            tabla_cultivos,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Cultivo": st.column_config.TextColumn("Cultivo"),
                "Área sembrada (ha)": st.column_config.NumberColumn("Área sembrada (ha)", format="%,.2f"),
                "Producción (t)": st.column_config.NumberColumn("Producción (t)", format="%,.2f"),
                "Rendimiento (t/ha)": st.column_config.NumberColumn("Rendimiento (t/ha)", format="%.2f"),
            },
        )
        st.download_button(
            "Descargar tabla filtrada (CSV)",
            data=tabla_cultivos.to_csv(index=False).encode("utf-8-sig"),
            file_name="cultivos_sepsa_filtrados.csv",
            mime="text/csv",
        )


# -----------------------------------------------------------------------------
# 11. FUENTES DE DATOS Y NOTAS METODOLÓGICAS
# -----------------------------------------------------------------------------
st.divider()
st.markdown("#### Fuentes de información")
st.markdown(
    f"**1. VI Censo Nacional Agropecuario (2014), INEC**\n\n"
    f"[Consultar resultados]({INEC_URL})"
)
st.markdown(
    f"**2. Cartografía de cantones de Costa Rica**\n\n"
    f"[SNIT]({SNIT_URL}) · [GeoJSON utilizado]({CANTONES_URL})"
)
st.markdown(
    f"**3. Extensión sembrada y producción agrícola, MAG/SEPSA**\n\n"
    f"[Repositorio de la Tarea 2]({SEPSA_REPO_URL})"
)
st.markdown(
    f"**4. Base cantonal del CENAGRO**\n\n"
    f"[Repositorio de la Tarea 3]({CENAGRO_REPO_URL})"
)
st.caption(
    "Nota metodológica: la extensión agropecuaria cantonal del VI CENAGRO y las "
    "estadísticas de extensión sembrada/producción de MAG-SEPSA son indicadores "
    "diferentes, con fuentes y escalas distintas. Se presentan como componentes "
    "complementarios, sin establecer relaciones estadísticas o espaciales entre ellos."
)
st.caption(
    "Aplicación desarrollada con Streamlit, GeoPandas, Folium y Plotly. "
    "El código recibió apoyo de herramientas de inteligencia artificial para su estructuración y depuración."
)
