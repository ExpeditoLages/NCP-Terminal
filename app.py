# ==============================================================================
# PLATAFORMA DE ANÁLISE QUANTITATIVA - NCP v11
# Tecnologias: Streamlit (Interface) + Plotly (Gráficos) + Pandas (Dados)
# ==============================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import time

# ------------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="NCP v11 | Quant Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS personalizado para o Tema Escuro
st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    h1, h2, h3 { color: #E0E0E0; font-family: 'Courier New', monospace; }
    .stMetric { background-color: #1E2129; padding: 15px; border-radius: 8px; border-left: 4px solid #00E676; }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 2. MOTOR DE DADOS HISTÓRICOS (Lendo Dados Cozidos)
# ------------------------------------------------------------------------------
@st.cache_data
def carregar_dados_ncp():
    """Lê o ficheiro CSV leve gerado pelo Google Colab"""
    try:
        df = pd.read_csv('NCP_Platform_Data.csv')
        
        # O nome da primeira coluna costuma ser o timestamp (ex: open_time)
        nome_coluna_data = df.columns[0]
        df[nome_coluna_data] = pd.to_datetime(df[nome_coluna_data])
        df.set_index(nome_coluna_data, inplace=True)
        
        return df
    except FileNotFoundError:
        return None

df = carregar_dados_ncp()

# ------------------------------------------------------------------------------
# 3. MOTOR DE DADOS AO VIVO (API DA BINANCE)
# ------------------------------------------------------------------------------
def buscar_vela_atual_binance(ativo="BTCUSDT"):
    """Vai à Binance buscar as agressões reais dos últimos minutos"""
    try:
        url = f"https://api.binance.com/api/v3/aggTrades?symbol={ativo}&limit=1000"
        resposta = requests.get(url)
        trades = resposta.json()
        
        df_live = pd.DataFrame(trades)
        df_live['price'] = df_live['p'].astype(float)
        df_live['qty'] = df_live['q'].astype(float)
        df_live['is_buyer_maker'] = df_live['m'] # True se foi agressão de venda
        
        # Calcula o Delta instantâneo
        df_live['volume'] = df_live['price'] * df_live['qty']
        df_live['delta_trade'] = np.where(df_live['is_buyer_maker'], -df_live['volume'], df_live['volume'])
        delta_atual = df_live['delta_trade'].sum()
        
        preco_atual = df_live['price'].iloc[-1]
        
        return {
            'close': preco_atual,
            'delta_ao_vivo': delta_atual,
        }
    except Exception as e:
        return None

# ------------------------------------------------------------------------------
# 4. INTERFACE DE UTILIZADOR (Sidebar)
# ------------------------------------------------------------------------------
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/GitHub_Invertocat_Logo.svg/1200px-GitHub_Invertocat_Logo.svg.png", width=50)
st.sidebar.title("NCP v11 Engine")
st.sidebar.markdown("---")

ativo_selecionado = st.sidebar.selectbox("Ativo", ["BTCUSDT", "ETHUSDT", "SOLUSDT"])

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Indicador Institucional")

# Controlos Deslizantes para a Matemática do Sinal
ind_delta_fundo = st.sidebar.slider("Delta % Max (Fundo)", min_value=-15.0, max_value=0.0, value=-4.0, step=0.5)
ind_delta_topo = st.sidebar.slider("Delta % Min (Topo)", min_value=0.0, max_value=15.0, value=4.0, step=0.5)
ind_rejeicao = st.sidebar.slider("Rejeição Mínima (%)", min_value=5.0, max_value=80.0, value=20.0, step=1.0)

ligar_indicador = st.sidebar.toggle("🟢 Ligar Sinais no Gráfico", value=True)

st.sidebar.markdown("---")
modo_live = st.sidebar.toggle("🔴 LIVE MODE (Auto-Refresh)", value=False)

# ------------------------------------------------------------------------------
# 5. PAINEL PRINCIPAL (Top Dashboard)
# ------------------------------------------------------------------------------
st.title(f"⚡ Terminal Quantitativo: {ativo_selecionado}")

# Lógica de Falha no CSV
if df is None:
    st.error("⚠️ Ficheiro 'NCP_Platform_Data.csv' não encontrado! Por favor, faça o upload para o GitHub.")
    st.stop()

# Painel Ao Vivo (Métricas instantâneas)
dados_frescos = buscar_vela_atual_binance(ativo_selecionado)
if dados_frescos:
    col_live1, col_live2, col_live3 = st.columns(3)
    col_live1.metric("Preço Spot (Ao Vivo)", f"${dados_frescos['close']:,.2f}")
    
    cor_delta = "normal" if dados_frescos['delta_ao_vivo'] > 0 else "inverse"
    estado_delta = "🟢 Compradores a Agredir" if dados_frescos['delta_ao_vivo'] > 0 else "🔴 Vendedores a Agredir"
    col_live2.metric("Delta (Últimos trades)", f"{dados_frescos['delta_ao_vivo']:,.0f}", estado_delta, delta_color=cor_delta)
    
st.markdown("---")

# ------------------------------------------------------------------------------
# 6. MOTOR LÓGICO & GRÁFICO (Plotly)
# ------------------------------------------------------------------------------
# Expandimos para os últimos 1000 candles para apanhar mais histórico de sinais
df_plot = df.tail(1000).copy()

if ligar_indicador:
    # A Mágica Matemática: Cruza o Delta com a Rejeição de Pavio
    df_plot['sinal_compra'] = (df_plot['delta_pct'] <= ind_delta_fundo) & (df_plot['rejection_bot'] >= ind_rejeicao)
    df_plot['sinal_venda'] = (df_plot['delta_pct'] >= ind_delta_topo) & (df_plot['rejection_top'] >= ind_rejeicao)
    
    sinais_compra = df_plot[df_plot['sinal_compra']]
    sinais_venda = df_plot[df_plot['sinal_venda']]

# Construção do Gráfico de duas linhas (Preço em cima, Delta em baixo)
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])

# Linha 1: Candlesticks
fig.add_trace(go.Candlestick(
    x=df_plot.index, open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'],
    name='Preço', increasing_line_color='#00E676', decreasing_line_color='#FF1744'
), row=1, col=1)

# Linha 1: Desenhar Sinais Institucionais
if ligar_indicador:
    if not sinais_compra.empty:
        fig.add_trace(go.Scatter(
            x=sinais_compra.index, y=sinais_compra['low'] - (sinais_compra['close']*0.005), 
            mode='markers+text', marker=dict(symbol='triangle-up', size=16, color='#00E676'), 
            name='BUY', text="BUY", textposition="bottom center"
        ), row=1, col=1)
        
    if not sinais_venda.empty:
        fig.add_trace(go.Scatter(
            x=sinais_venda.index, y=sinais_venda['high'] + (sinais_venda['close']*0.005), 
            mode='markers+text', marker=dict(symbol='triangle-down', size=16, color='#FF1744'), 
            name='SELL', text="SELL", textposition="top center"
        ), row=1, col=1)

# Linha 2: Histograma de Volume/Delta
cores_delta = ['#00E676' if d > 0 else '#FF1744' for d in df_plot['delta']]
fig.add_trace(go.Bar(
    x=df_plot.index, y=df_plot['delta'], name='Delta', marker_color=cores_delta, opacity=0.8
), row=2, col=1)

# Formatação Final do Gráfico
fig.update_layout(template='plotly_dark', height=700, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False, showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# Footer: Tabela de Sinais Recentes
st.subheader("📊 Footprint (Sinais Recentes)")
if ligar_indicador:
    df_table = df_plot[df_plot['sinal_compra'] | df_plot['sinal_venda']].tail(5)
    if not df_table.empty:
        st.dataframe(df_table[['close', 'delta_pct', 'rejection_bot', 'rejection_top']])
    else:
        st.write("Nenhum sinal institucional forte encontrado na janela recente com estes parâmetros.")

# ------------------------------------------------------------------------------
# 7. LÓGICA DE RECARREGAMENTO AO VIVO (Posicionada no fim, de forma correta)
# ------------------------------------------------------------------------------
if modo_live:
    time.sleep(15)
    st.rerun()
