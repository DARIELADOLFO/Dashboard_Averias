# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata
import re

# Logo de la empresa
from PIL import Image

logo = Image.open("logo.png")
st.image(logo, width=150)  # Ajusta el tamaño a tu gusto

# ----------------------
# Configuración general
# ----------------------
st.set_page_config(page_title="Dashboard Ejecutivo de Averías", layout="wide", page_icon="📊")
PALETA = {"cerradas": "#a3c4f3", "repetidas": "#f3a3a3", "base": "#f7f9fb"}

st.markdown(
    """
    <style>
    .reportview-container { background: #ffffff; }
    .stApp { background: #ffffff; }
    .kpi { background: #ffffff; border-radius: 8px; padding: 6px 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------
# Helpers robustos
# ----------------------
def normalize_text(s):
    if pd.isna(s):
        return ""
    s = str(s).strip()
    # eliminar NBSP
    s = s.replace("\xa0", " ")
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def build_norm_map(df):
    return {normalize_text(c): c for c in df.columns}

def pick_col(norm_map, candidates):
    # devuelve el nombre ORIGINAL de la primer candidata encontrada o None
    for cand in candidates:
        nc = normalize_text(cand)
        if nc in norm_map:
            return norm_map[nc]
    # intento por tokens
    keys = list(norm_map.keys())
    for cand in candidates:
        tokens = [t for t in normalize_text(cand).split("_") if t]
        for k in keys:
            if all(t in k for t in tokens):
                return norm_map[k]
    return None

def truthy_series(s):
    if s is None:
        return pd.Series([], dtype=bool)
    s_s = s.astype(str).str.strip().str.lower()
    truth_words = {"1","true","si","sí","y","yes","t","repetida","repetido","s"}
    is_word = s_s.isin(truth_words)
    is_num = pd.to_numeric(s_s, errors="coerce").fillna(0) != 0
    return is_word | is_num

# ----------------------
# Cargar Excel (hoja automática)
# ----------------------
FILE = "DATA_AUDITORIA_DROP.xlsx"  # <- asegúrate de que esté en la misma carpeta que app.py

try:
    xls = pd.ExcelFile(FILE)
    sheets = xls.sheet_names
    sheet_to_use = "Hoja1" if "Hoja1" in sheets else sheets[0]
    df = pd.read_excel(xls, sheet_name=sheet_to_use)
    st.info(f"Usando hoja: **{sheet_to_use}** (si querías otra hoja cámbiala manualmente).")
except FileNotFoundError:
    st.error(f"No encontré el archivo **{FILE}**. Ponlo en la misma carpeta que `app.py` y vuelve a correr.")
    st.stop()
except Exception as e:
    st.error(f"Error al leer el Excel: {e}")
    st.stop()

# ----------------------
# Normalizar y mapear columnas
# ----------------------
norm_map = build_norm_map(df)

col_num_sol = pick_col(norm_map, ["NUMERO_SOL", "numero_sol", "numero sol"])
col_repetida = pick_col(norm_map, ["CASO_REPETIDO", "CASO REPETIDO", "caso_repetido"])
col_fc_creacion = pick_col(norm_map, ["FC_CREACION", "FC CREACION", "fc_creacion", "fecha_creacion"])
col_fecha_cierre = pick_col(norm_map, ["Fecha de Cierre", "fecha de cierre", "fecha_cierre", "fecha cierre"])
col_distrito = pick_col(norm_map, ["Nombre del Distrito", "distrito", "desc_distrito_municipal"])
col_producto = pick_col(norm_map, ["Producto Agrupado", "producto", "producto_agrupado"])
col_tecnologia = pick_col(norm_map, ["Tecnologia", "tecnología", "tecnologia"])
col_ciudad = pick_col(norm_map, ["DESC_CIUDAD", "desc_ciudad", "ciudad"])
col_sector = pick_col(norm_map, ["DESC_SECTOR", "desc_sector", "sector"])

with st.expander("🔎 Columnas detectadas y mapeo (click para ver)"):
    st.write("Columnas originales:", list(df.columns))
    st.write("Mapeo resuelto:", {
        "NUMERO_SOL": col_num_sol,
        "CASO_REPETIDO": col_repetida,
        "FC_CREACION": col_fc_creacion,
        "Fecha de Cierre": col_fecha_cierre,
        "Nombre del Distrito": col_distrito,
        "Producto Agrupado": col_producto,
        "Tecnologia": col_tecnologia,
        "DESC_CIUDAD": col_ciudad,
        "DESC_SECTOR": col_sector
    })

# ----------------------
# Preprocesamiento mínimo
# ----------------------
# asegurar columnas existan en df antes de convertir
date_col = col_fc_creacion or col_fecha_cierre
if date_col:
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

# ----------------------
# FILTROS (sidebar)
# ----------------------
st.sidebar.header("Filtros")
df_f = df.copy()

# Fecha
if date_col:
    min_date = df[date_col].min().date()
    max_date = df[date_col].max().date()
    date_range = st.sidebar.date_input("Rango de fecha", value=[min_date, max_date], min_value=min_date, max_value=max_date)
    if isinstance(date_range, list) and len(date_range) == 2:
        start, end = date_range
        df_f = df_f[df_f[date_col].dt.date.between(start, end)]
else:
    st.sidebar.info("No hay columna de fecha reconocida (FC_CREACION o Fecha de Cierre).")

# Distrito
if col_distrito:
    opts = ["Todos"] + sorted(df[col_distrito].dropna().astype(str).unique().tolist())
    sel_distr = st.sidebar.selectbox("Distrito", opts)
    if sel_distr != "Todos":
        df_f = df_f[df_f[col_distrito].astype(str) == sel_distr]

# Producto
if col_producto:
    opts = ["Todos"] + sorted(df[col_producto].dropna().astype(str).unique().tolist())
    sel_prod = st.sidebar.selectbox("Producto", opts, index=0)
    if sel_prod != "Todos":
        df_f = df_f[df_f[col_producto].astype(str) == sel_prod]

# Tecnología
if col_tecnologia:
    opts = ["Todos"] + sorted(df[col_tecnologia].dropna().astype(str).unique().tolist())
    sel_tec = st.sidebar.selectbox("Tecnología", opts, index=0)
    if sel_tec != "Todos":
        df_f = df_f[df_f[col_tecnologia].astype(str) == sel_tec]

# ----------------------
# KPIs ejecutivos (top)
# ----------------------
# total cerradas: contamos NUMERO_SOL únicos (si existe), si no, rows
if col_num_sol:
    total_cerradas = int(df_f[col_num_sol].astype(str).nunique())
else:
    total_cerradas = int(len(df_f))

# total repetidas: detectamos via CASO_REPETIDO de manera robusta
if col_repetida:
    rep_mask = truthy_series(df_f[col_repetida])
    total_repetidas = int(rep_mask.sum())
else:
    total_repetidas = 0
pct_repetidas = (total_repetidas / total_cerradas * 100) if total_cerradas else 0.0

st.markdown("### 🔑 KPIs Principales")
k1, k2, k3 = st.columns([1.4,1.4,1.4])
k1.metric("✅ Total Averías Cerradas", f"{total_cerradas:,}")
k2.metric("♻️ Total Averías Repetidas", f"{total_repetidas:,}")
k3.metric("📈 % Repetitividad (repetidas / cerradas)", f"{pct_repetidas:.2f}%")
st.markdown("---")

# ----------------------
# VISUALIZACIONES compactas y ejecutivas
# ----------------------
# 1) Tendencia mensual (por fecha_col si existe)
row1_col1, row1_col2 = st.columns([2,1])

if date_col:
    df_t = df_f.copy()
    df_t = df_t.dropna(subset=[date_col])
    df_t["__periodo__"] = df_t[date_col].dt.to_period("M").astype(str)
    if col_num_sol:
        evo = df_t.groupby("__periodo__")[col_num_sol].nunique().reset_index(name="Cantidad")
    else:
        evo = df_t.groupby("__periodo__").size().reset_index(name="Cantidad")
    if not evo.empty:
        fig_evo = px.line(evo, x="__periodo__", y="Cantidad", title="Tendencia Mensual de Averías Cerradas",
                          markers=True)
        fig_evo.update_traces(line=dict(color=PALETA["cerradas"]), marker=dict(size=6))
        fig_evo.update_layout(height=360, margin=dict(l=40,r=20,t=50,b=40), xaxis_title="Mes", yaxis_title="Cantidad")
        row1_col1.plotly_chart(fig_evo, use_container_width=True)
    else:
        row1_col1.info("No hay datos de fecha válidos para mostrar la tendencia.")
else:
    row1_col1.info("No hay columna de fecha disponible para la tendencia mensual.")

# 2) Top distritos (barra horizontal compacta)
if col_distrito:
    top_dist = df_f[col_distrito].astype(str).value_counts().reset_index()
    top_dist.columns = ["Distrito", "Cantidad"]
    top_dist = top_dist.head(12)
    fig_dist = px.bar(top_dist.sort_values("Cantidad"), x="Cantidad", y="Distrito", orientation="h",
                      title="Top Distritos - Cantidad de Averías", text="Cantidad")
    fig_dist.update_layout(height=360, margin=dict(l=40,r=20,t=50,b=40), yaxis={'categoryorder':'total ascending'})
    row1_col2.plotly_chart(fig_dist, use_container_width=True)
else:
    row1_col2.info("No hay columna de distrito detectada.")

st.markdown("---")

# 3) Pie donut Repetidas vs No repetidas + Top sectores
row2_col1, row2_col2 = st.columns([1,1])

# donut
df_tmp = df_f.copy()
if col_repetida:
    df_tmp["__rep__"] = truthy_series(df_tmp[col_repetida])
else:
    df_tmp["__rep__"] = False

pie_df = df_tmp["__rep__"].value_counts().rename_axis("repetida").reset_index(name="Cantidad")
pie_df["repetida"] = pie_df["repetida"].map({True: "Repetidas", False: "No Repetidas"})
fig_pie = px.pie(pie_df, names="repetida", values="Cantidad", title="Proporción Repetidas vs No Repetidas",
                 hole=0.45, color="repetida", color_discrete_map={"Repetidas": PALETA["repetidas"], "No Repetidas": PALETA["cerradas"]})
fig_pie.update_layout(height=360, margin=dict(l=20,r=20,t=40,b=20))
row2_col1.plotly_chart(fig_pie, use_container_width=True)

# Top sectores
if col_sector:
    top_sec = df_f.groupby(col_sector).size().reset_index(name="Cantidad").sort_values("Cantidad", ascending=False).head(12)
    top_sec.columns = ["Sector", "Cantidad"]
    fig_sec = px.bar(top_sec, x="Cantidad", y="Sector", orientation="h", title="Top Sectores por Averías", text="Cantidad")
    fig_sec.update_layout(height=360, margin=dict(l=40,r=20,t=50,b=40), yaxis={'categoryorder':'total ascending'})
    row2_col2.plotly_chart(fig_sec, use_container_width=True)
else:
    row2_col2.info("No hay columna DESC_SECTOR detectada.")

st.markdown("---")

# 4) Comparativa Producto: Cerradas vs Repetidas (gráfico agrupado)
if col_producto:
    df_prod = df_f.copy()
    df_prod["__rep__"] = truthy_series(df_prod[col_repetida]) if col_repetida else False
    # contar NUMERO_SOL únicos por producto y repetida
    if col_num_sol:
        gp = df_prod.groupby([col_producto, "__rep__"])[col_num_sol].nunique().unstack(fill_value=0).reset_index()
    else:
        gp = df_prod.groupby([col_producto, "__rep__"]).size().unstack(fill_value=0).reset_index()
    # asegurar columnas
    gp = gp.rename(columns={False: "Cerradas", True: "Repetidas"})
    gp_m = gp.melt(id_vars=[col_producto], value_vars=["Cerradas", "Repetidas"], var_name="Tipo", value_name="Cantidad")
    fig_prod = px.bar(gp_m.sort_values("Cantidad", ascending=False), x=col_producto, y="Cantidad", color="Tipo",
                      title="Comparativa por Producto: Cerradas vs Repetidas", barmode="group",
                      color_discrete_map={"Cerradas": PALETA["cerradas"], "Repetidas": PALETA["repetidas"]})
    fig_prod.update_layout(height=420, xaxis_tickangle=-45, margin=dict(l=20,r=20,t=50,b=140))
    st.plotly_chart(fig_prod, use_container_width=True)
else:
    st.info("No hay columna Producto Agrupado detectada para la comparativa por producto.")

# ----------------------
# Pie de página / nota ejecutiva
# ----------------------
st.markdown("---")
st.caption("Lectura ejecutiva: prioriza top sectores y top productos donde se concentran las repetidas. KPI principal = % Repetitividad (Repetidas / Cerradas).")
