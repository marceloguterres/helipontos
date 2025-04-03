import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re
import matplotlib.pyplot as plt

st.set_page_config(page_title="Helipontos SP", layout="wide")
st.title("Helipontos na cidade São Paulo")

# --- Conversão de coordenadas DMS para decimal ---
def dms_para_decimal(coord):
    try:
        coord = coord.replace("’", "'").replace("‘", "'").replace("”", '"').replace("“", '"').replace("''", '"')
        match = re.match(r"(\d+)°(\d+)'{1,2}(\d+)", coord.strip())
        if not match:
            return None
        graus, minutos, segundos = map(int, match.groups())
        decimal = graus + minutos / 60 + segundos / 3600
        if "S" in coord or "O" in coord or "W" in coord:
            decimal = -decimal
        return decimal
    except:
        return None

# --- Cálculo da área ---
def calcular_area(dimensao):
    try:
        partes = dimensao.lower().replace("m", "").split("x")
        largura = float(partes[0].strip())
        comprimento = float(partes[1].strip())
        return largura * comprimento
    except:
        return None

# --- Cores fixas por tipo de superfície ---
CORES_SUPERFICIE = {
    "Aguardando dados": "#FF6B6B",
    "Grama": "#43AA8B",
    "Concreto": "#4D6CFA",
    "Metálico": "#FFA500",
    "Asfalto": "#5C33F6",
}

# --- Carregar dados dos helipontos ---
@st.cache_data
def carregar_helipontos():
    df = pd.read_csv("helipontos_sp.csv")
    df["Área (m²)"] = df["Dimensões"].apply(calcular_area)
    df["lat"] = df["Latitude"].apply(dms_para_decimal)
    df["lon"] = df["Longitude"].apply(dms_para_decimal)
    df["Superfície"] = df["Superfície"].fillna("Aguardando dados").astype(str)

    categorias_fixas = list(CORES_SUPERFICIE.keys())
    for cat in categorias_fixas:
        if cat not in df["Superfície"].unique():
            df = pd.concat([df, pd.DataFrame([{"Superfície": cat, "lat": None, "lon": None}])], ignore_index=True)
    return df

# --- Carregar dados das rotas REH ---
@st.cache_data
def carregar_rotas():
    df_rotas = pd.read_csv("REHs_SP.csv", encoding="utf-8")
    latitudes, longitudes = [], []
    for coord in df_rotas["Coordenadas"]:
        partes = coord.split("/")
        latitudes.append(dms_para_decimal(partes[0].strip()))
        longitudes.append(dms_para_decimal(partes[1].strip()))
    df_rotas["lat"] = latitudes
    df_rotas["lon"] = longitudes
    return df_rotas

# --- Carregamento
df = carregar_helipontos()
df_rotas = carregar_rotas()

# --- Filtros
st.sidebar.header("Filtros")
superficies_disponiveis = sorted(df["Superfície"].dropna().unique())
opcoes_superficie = ["Todas"] + list(superficies_disponiveis)
superficie_selecionada = st.sidebar.selectbox("Tipo de superfície:", opcoes_superficie, index=0)

operacoes_disponiveis = sorted(df["Operação"].dropna().unique())
opcoes_operacao = ["Todas"] + operacoes_disponiveis
operacao_selecionada = st.sidebar.selectbox("Tipo de operação:", opcoes_operacao, index=0)

area_min = st.sidebar.number_input("Área mínima (m²)", min_value=0, value=0, step=10)
fundo_mapa = st.sidebar.selectbox("Estilo do mapa base:", ["OpenStreetMap", "CartoDB Positron", "Stamen Terrain", "Stamen Toner"])
tamanho_circulo = st.sidebar.slider("Tamanho dos círculos (helipontos)", 2, 20, value=6)

# --- Aplicar filtros
df_filtrado = df.copy()
if superficie_selecionada != "Todas":
    df_filtrado = df_filtrado[df_filtrado["Superfície"] == superficie_selecionada]
if operacao_selecionada != "Todas":
    df_filtrado = df_filtrado[df_filtrado["Operação"] == operacao_selecionada]
df_filtrado = df_filtrado[df_filtrado["Área (m²)"].fillna(0) > area_min]
df_mapa = df_filtrado.dropna(subset=["lat", "lon"])

# --- Abas
aba_mapa, aba_tabela, aba_estat, aba_criterios = st.tabs([
    "🗺️ Mapa", "📋 Tabela", "📊 Estatísticas", "📌 Critérios e Contexto"
])

# --- Aba 1: Mapa
with aba_mapa:
    st.subheader("Mapa de Helipontos + Rotas REH")
    m = folium.Map(location=[-23.55, -46.63], zoom_start=11, tiles=fundo_mapa)

    for _, row in df_mapa.iterrows():
        cor = CORES_SUPERFICIE.get(row["Superfície"], "#999999")
        popup = f"<b>{row['Nome']}</b><br>Superfície: {row['Superfície']}<br>Área: {row['Área (m²)']} m²"
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=tamanho_circulo,
            color=cor,
            fill=True,
            fill_color=cor,
            fill_opacity=0.85,
            popup=popup
        ).add_to(m)

    for nome_reh, grupo in df_rotas.groupby("REH"):
        grupo = grupo.sort_values("Índice")
        caminho = grupo[["lat", "lon"]].dropna().values.tolist()
        if len(caminho) >= 2:
            folium.PolyLine(
                locations=caminho,
                color="#006400",  # verde escuro
                weight=5,
                tooltip=nome_reh
            ).add_to(m)

    st_data = st_folium(m, width=1100, height=600)

    st.markdown("### Legenda de Superfícies")
    for nome, cor in CORES_SUPERFICIE.items():
        st.markdown(f'''
            <div style="display:flex; align-items:center; margin-bottom:5px;">
                <div style="width:20px; height:20px; background-color: {cor}; margin-right:10px; border-radius: 3px;"></div>
                {nome}
            </div>
        ''', unsafe_allow_html=True)

# --- Aba 2: Tabela
with aba_tabela:
    st.subheader("Tabela de Helipontos")
    st.dataframe(df_filtrado)

# --- Aba 3: Estatísticas
with aba_estat:
    st.subheader("Distribuição das Áreas dos Helipontos")

    df_areas = df_filtrado[df_filtrado["Área (m²)"].notnull()]
    if df_areas.empty:
        st.warning("Nenhum dado de área disponível para gerar o histograma.")
    else:
        fig, ax = plt.subplots(figsize=(5, 2.5))
        ax.hist(df_areas["Área (m²)"], bins=20, color="#D3D3D3", edgecolor="black")
        ax.set_title("Áreas dos Helipontos", fontsize=10)
        ax.set_xlabel("Área (m²)", fontsize=9)
        ax.set_ylabel("Frequência", fontsize=9)
        ax.tick_params(axis='both', labelsize=8)
        st.pyplot(fig)



# --- Aba 4: Critérios e Contexto
with aba_criterios:
    st.subheader("Critérios de Avaliação para Helipontos")
    st.markdown("""
    - **Área (m²):** Tamanho físico da superfície do heliponto.  
    - **Altitude do heliponto:** Altura em relação ao nível do mar (impacta navegação).  
    - **Proximidade da REH:** Distância em relação a rotas aéreas principais.  
    - **Grau de importância do prédio:** Função estratégica (hospitais, governo, mídia, etc).  
    - **Grau de interferência no espaço aéreo comercial:** Avaliação de conflitos com rotas regulares.  
    - **Uso do prédio (comercial ou institucional):** Edificações comerciais costumam demandar mais movimentação aérea.  
    - **Proximidade de shoppings ou grandes estacionamentos:** Facilita o acesso terrestre e integração modal.  
    - **Tipo de operação (IFR ou VFR):** Define o nível de infraestrutura e restrições de operação conforme visibilidade e instrumentos.  
    """)

    st.divider()

    st.subheader("Contexto da Operação Aérea em São Paulo")
    st.markdown("""
    > 🚁 **400 helicópteros** registrados na cidade e **700 no estado**, realizando mais de  
    > **1.300 viagens diárias** — superando **Nova York** e **Tóquio**.  
    >
    > 📚 *Fonte: Salim e Bosco (2020)*
    """)
    
    st.divider()
    st.subheader("✈️ eVTOLs e o Uso das REHs")

    st.markdown("""
    **✅ 1.O eVTOL poderá cruzar uma REH?**  
    Sim. As REHs são espaços VFR e não exclusivos para helicópteros.  
    O importante é manter a separação adequada, cumprir os procedimentos locais e estar em coordenação com o controle (ou auto-coordenação em FCA, se for o caso).  
    O que importa não é o tipo de aeronave (helicóptero ou eVTOL), mas se ela pode operar VFR, com comunicação ativa, equipamentos obrigatórios (como transponder) e velocidade/altitude compatíveis.

    **✈️ 2. Será comum um eVTOL usar uma REH?**  
    Provavelmente sim, mas com ressalvas. Como disse Márcio André, "na prática, provavelmente acompanhará o desenho das REH".  
    Isso porque:
    - As REH seguem eixos urbanos com áreas livres para pouso de emergência (vias, rios, parques);  
    - Evitam rotas IFR de aviões, reduzindo conflito com tráfego comercial;  
    - Facilitam a gestão de tráfego misto com regras unificadas e previsibilidade.

    Entretanto, eVTOLs também poderão seguir novas rotas, como:
    - Corredores específicos para eVTOLs (otimizados para baixa velocidade e ruído);  
    - Faixas de altitude diferentes, com separação vertical das REHs.

    **🧭 3. E se o eVTOL precisar cruzar uma REH?**  
    Pode, desde que:
    - Haja separação vertical adequada (ex: cruzar 500 pés acima);  
    - Seja coordenado com controle (Torre, APP);  
    - Ou em ponto autorizado conforme carta REH ou UTM.
    """)
