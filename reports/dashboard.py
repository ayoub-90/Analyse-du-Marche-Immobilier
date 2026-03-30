#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard Interactif — Analyse du Marché Immobilier Marocain
=============================================================
Equivaut à un dashboard Power BI / Tableau mais 100% Python.

Lancement :
    pip install streamlit plotly
    streamlit run reports/dashboard.py
"""

import os
import glob
import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

warnings.filterwarnings("ignore")

# ─── Configuration ────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_FINAL     = ROOT / "data" / "final"

st.set_page_config(
    page_title="🏠 Immobilier Maroc — Dashboard",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f1117; }
    .metric-card {
        background: linear-gradient(135deg, #1e2130, #252a3d);
        border-radius: 12px; padding: 16px 20px;
        border-left: 4px solid #6c63ff;
        margin-bottom: 8px;
    }
    .metric-value { font-size: 2rem; font-weight: 700; color: #ffffff; }
    .metric-label { font-size: 0.85rem; color: #8892b0; text-transform: uppercase; }
    .section-title { color: #6c63ff; font-size: 1.3rem; font-weight: 700; margin: 24px 0 12px; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e2130, #252a3d);
        border-radius: 12px; padding: 12px 20px;
        border-left: 4px solid #6c63ff;
    }
</style>
""", unsafe_allow_html=True)

# ─── Helpers ──────────────────────────────────────────────
@st.cache_data
def load_processed_data():
    files = glob.glob(str(DATA_PROCESSED / "immobilier_maroc_*.csv"))
    if not files:
        return None
    latest = max(files, key=os.path.getctime)
    return pd.read_csv(latest), latest

@st.cache_data
def load_final_data():
    result = {}
    for name in ["X_train", "X_test", "y_train", "y_test"]:
        f = DATA_FINAL / f"{name}.csv"
        if f.exists():
            result[name] = pd.read_csv(f)
    return result

@st.cache_data
def load_model_results():
    f = DATA_FINAL / "model_results.json"
    if not f.exists():
        return None
    with open(f, encoding="utf-8") as fp:
        return json.load(fp)

def fmt_price(val):
    if pd.isna(val):
        return "N/A"
    return f"{val:,.0f} MAD"

# ─── Chargement des données ────────────────────────────────
data_result = load_processed_data()
if data_result is None:
    st.error("❌ Aucune donnée trouvée dans data/processed/. Lancez d'abord le scraping.")
    st.stop()

df, data_file = data_result
df["prix"] = pd.to_numeric(df["prix"], errors="coerce")
df["surface_m2"] = pd.to_numeric(df["surface_m2"], errors="coerce")
df["prix_m2"] = df["prix"] / df["surface_m2"].replace(0, np.nan)

final = load_final_data()
model_results = load_model_results()

# ─── Sidebar ──────────────────────────────────────────────
with st.sidebar:
    st.image("https://via.placeholder.com/280x60/6c63ff/ffffff?text=🏠+Immobilier+Maroc", use_column_width=True)
    st.markdown("---")
    st.markdown("### 🔍 Filtres")

    villes = ["Toutes"] + sorted(df["ville"].dropna().unique().tolist())
    ville_sel = st.selectbox("Ville", villes)

    types = ["Tous"] + sorted(df["type_bien"].dropna().unique().tolist())
    type_sel = st.selectbox("Type de bien", types)

    sources = ["Toutes"] + sorted(df["source"].dropna().unique().tolist())
    source_sel = st.selectbox("Source", sources)

    prix_range = st.slider(
        "Fourchette de prix (MAD)",
        int(df["prix"].dropna().min()),
        int(df["prix"].dropna().max()),
        (int(df["prix"].dropna().min()), int(df["prix"].dropna().max())),
        step=50000
    )
    st.markdown("---")
    st.markdown(f"📄 `{os.path.basename(data_file)}`")
    st.markdown(f"🕐 Actualisé : {df['date_scraping'].max() if 'date_scraping' in df else 'N/A'}")

# ─── Filtrage ─────────────────────────────────────────────
dff = df.copy()
if ville_sel != "Toutes":
    dff = dff[dff["ville"] == ville_sel]
if type_sel != "Tous":
    dff = dff[dff["type_bien"] == type_sel]
if source_sel != "Toutes":
    dff = dff[dff["source"] == source_sel]
dff = dff[dff["prix"].isna() | ((dff["prix"] >= prix_range[0]) & (dff["prix"] <= prix_range[1]))]

# ═════════════════════════════════════════════════════════
# PAGE 1 : MARCHÉ
# ═════════════════════════════════════════════════════════
page = st.sidebar.radio("📊 Navigation", ["🏠 Marché", "🤖 Modèles ML", "📋 Données"])
st.markdown(f"# {'🏠 Analyse du Marché Immobilier Marocain' if page=='🏠 Marché' else ('🤖 Performance des Modèles ML' if page=='🤖 Modèles ML' else '📋 Données Brutes')}")

if page == "🏠 Marché":
    # ── KPIs ──────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📊 Total Annonces", len(dff))
    with col2:
        st.metric("💰 Prix Moyen", fmt_price(dff["prix"].mean()))
    with col3:
        st.metric("💰 Prix Médian", fmt_price(dff["prix"].median()))
    with col4:
        st.metric("📐 Surface Moy.", f"{dff['surface_m2'].mean():.0f} m²" if dff['surface_m2'].notna().any() else "N/A")
    with col5:
        st.metric("💵 Prix/m² Moy.", f"{dff['prix_m2'].mean():,.0f} MAD" if dff['prix_m2'].notna().any() else "N/A")

    st.markdown("---")

    # ── Row 1 : Ville + Type ──────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<p class="section-title">📍 Prix Moyen par Ville</p>', unsafe_allow_html=True)
        ville_data = dff[dff["prix"].notna()].groupby("ville").agg(
            prix_moyen=("prix", "mean"),
            nb=("prix", "count")
        ).reset_index().sort_values("prix_moyen", ascending=True)
        if len(ville_data) > 0:
            fig = px.bar(ville_data, x="prix_moyen", y="ville", orientation="h",
                         color="prix_moyen", color_continuous_scale="Viridis",
                         labels={"prix_moyen": "Prix Moyen (MAD)", "ville": ""},
                         text=ville_data["prix_moyen"].apply(lambda x: f"{x/1e6:.2f}M"))
            fig.update_traces(textposition="outside")
            fig.update_layout(template="plotly_dark", showlegend=False, height=350,
                              coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown('<p class="section-title">🏗️ Répartition par Type de Bien</p>', unsafe_allow_html=True)
        type_data = dff["type_bien"].value_counts().reset_index()
        type_data.columns = ["type_bien", "count"]
        if len(type_data) > 0:
            fig = px.pie(type_data, names="type_bien", values="count",
                         color_discrete_sequence=px.colors.qualitative.Pastel,
                         hole=0.4)
            fig.update_traces(textinfo="label+percent+value")
            fig.update_layout(template="plotly_dark", height=350)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2 : Prix Distribution + Scatter ──────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<p class="section-title">💰 Distribution des Prix</p>', unsafe_allow_html=True)
        prix_data = dff[dff["prix"].notna()]
        if len(prix_data) > 0:
            fig = px.histogram(prix_data, x="prix", nbins=25, color="source",
                               labels={"prix": "Prix (MAD)", "source": "Source"},
                               barmode="overlay", opacity=0.75)
            fig.add_vline(x=prix_data["prix"].mean(), line_dash="dash",
                         annotation_text=f"Moy: {prix_data['prix'].mean():,.0f}")
            fig.update_layout(template="plotly_dark", height=350)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown('<p class="section-title">📐 Prix vs Surface</p>', unsafe_allow_html=True)
        scatter_data = dff[dff["prix"].notna() & dff["surface_m2"].notna()]
        if len(scatter_data) > 1:
            fig = px.scatter(scatter_data, x="surface_m2", y="prix",
                             color="type_bien", size="prix_m2",
                             hover_data=["ville", "source"],
                             labels={"surface_m2": "Surface (m²)", "prix": "Prix (MAD)"},
                             trendline="ols")
            fig.update_layout(template="plotly_dark", height=350)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 3 : Équipements ───────────────────────────────
    st.markdown('<p class="section-title">🛋️ Taux d\'Équipements</p>', unsafe_allow_html=True)
    equip_cols = ["parking", "ascenseur", "balcon", "piscine", "jardin"]
    equip_data = {}
    for col in equip_cols:
        if col in dff.columns:
            rate = pd.to_numeric(dff[col], errors="coerce").mean() * 100
            equip_data[col.capitalize()] = round(rate, 1) if not np.isnan(rate) else 0

    if equip_data:
        fig = go.Figure(go.Bar(
            x=list(equip_data.keys()),
            y=list(equip_data.values()),
            marker_color=["#6c63ff", "#ff6584", "#43dde6", "#ffbe0b", "#2ecc71"],
            text=[f"{v:.1f}%" for v in equip_data.values()],
            textposition="outside"
        ))
        fig.update_layout(template="plotly_dark", height=300,
                         yaxis_title="Pourcentage (%)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # ── Source Comparison ─────────────────────────────────
    st.markdown('<p class="section-title">🌐 Avito vs Mubawab</p>', unsafe_allow_html=True)
    src_data = dff.groupby("source").agg(
        nb=("prix", "count"),
        prix_moy=("prix", "mean"),
        surface_moy=("surface_m2", "mean")
    ).reset_index().fillna(0)
    src_data["prix_moy"] = src_data["prix_moy"].round(0)
    src_data["surface_moy"] = src_data["surface_moy"].round(1)
    st.dataframe(src_data, use_container_width=True)


# ═════════════════════════════════════════════════════════
# PAGE 2 : MODÈLES ML
# ═════════════════════════════════════════════════════════
elif page == "🤖 Modèles ML":

    if model_results is None:
        st.warning("⚠️ Aucun résultat de modèle trouvé. Exécutez d'abord `03_Model_Training.ipynb`.")
    else:
        best = model_results.get("best_model", "N/A")
        r2   = model_results.get("r2_test", 0)
        mae  = model_results.get("mae_test", 0)

        # KPIs modèle
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏆 Meilleur Modèle", best)
        with col2:
            st.metric("📈 R² Test", f"{r2:.4f}")
        with col3:
            st.metric("📉 MAE", f"{mae:,.0f} MAD")
        with col4:
            n_feat = len(model_results.get("features", []))
            st.metric("🔢 Features", n_feat)

        st.markdown("---")

        # Tableau comparatif
        all_res = model_results.get("all_results", [])
        if all_res:
            df_models = pd.DataFrame(all_res).sort_values("R² Test", ascending=False)

            st.markdown('<p class="section-title">📊 Comparaison des Modèles</p>', unsafe_allow_html=True)
            st.dataframe(
                df_models.style.background_gradient(cmap="RdYlGn", subset=["R² Test", "CV R² (mean)"])
                               .background_gradient(cmap="RdYlGn_r", subset=["MAE (MAD)", "MAPE (%)"]),
                use_container_width=True
            )

            st.markdown("---")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown('<p class="section-title">R² Score par Modèle</p>', unsafe_allow_html=True)
                fig = px.bar(df_models, x="Modèle", y="R² Test",
                             color="R² Test", color_continuous_scale="Viridis",
                             text=df_models["R² Test"].apply(lambda x: f"{x:.3f}"))
                fig.update_layout(template="plotly_dark", showlegend=False, height=380)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown('<p class="section-title">MAE — Erreur Moyenne (MAD)</p>', unsafe_allow_html=True)
                fig = px.bar(df_models, x="Modèle", y="MAE (MAD)",
                             color="MAE (MAD)", color_continuous_scale="RdYlGn_r",
                             text=df_models["MAE (MAD)"].apply(lambda x: f"{x:,.0f}"))
                fig.update_layout(template="plotly_dark", showlegend=False, height=380)
                st.plotly_chart(fig, use_container_width=True)

            # R² Train vs Test
            st.markdown('<p class="section-title">📈 R² Train vs Test (Overfitting)</p>', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Bar(name="R² Train", x=df_models["Modèle"],
                                 y=df_models["R² Train"], marker_color="#6c63ff"))
            fig.add_trace(go.Bar(name="R² Test", x=df_models["Modèle"],
                                 y=df_models["R² Test"], marker_color="#ff6584"))
            fig.update_layout(barmode="group", template="plotly_dark", height=380)
            st.plotly_chart(fig, use_container_width=True)

        # Features
        features = model_results.get("features", [])
        if features:
            st.markdown('<p class="section-title">🔑 Features Utilisées</p>', unsafe_allow_html=True)
            st.code(", ".join(features))

        # Dataset info
        if final:
            st.markdown('<p class="section-title">📂 Dataset ML</p>', unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("X_train", f"{final['X_train'].shape[0]} × {final['X_train'].shape[1]}")
            with col2:
                st.metric("X_test", f"{final['X_test'].shape[0]} × {final['X_test'].shape[1]}")
            with col3:
                st.metric("y_train", f"{final['y_train'].shape[0]} lignes")
            with col4:
                st.metric("NaN total", int(final["X_train"].isnull().sum().sum() + final["X_test"].isnull().sum().sum()))


# ═════════════════════════════════════════════════════════
# PAGE 3 : DONNÉES BRUTES
# ═════════════════════════════════════════════════════════
elif page == "📋 Données":
    st.markdown(f"**{len(dff)} annonces** après filtres — `{os.path.basename(data_file)}`")

    # Colonnes affichées
    show_cols = ["source", "type_bien", "ville", "prix", "surface_m2",
                 "prix_m2", "nb_chambres", "parking", "ascenseur", "titre"]
    display_cols = [c for c in show_cols if c in dff.columns]

    st.dataframe(
        dff[display_cols].sort_values("prix", ascending=False).reset_index(drop=True),
        use_container_width=True,
        height=600
    )

    # Export
    csv_bytes = dff.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Télécharger CSV filtré",
        data=csv_bytes,
        file_name="immobilier_filtre.csv",
        mime="text/csv"
    )
