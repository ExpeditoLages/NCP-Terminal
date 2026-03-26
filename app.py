# ==============================================================================
# PLATAFORMA DE ANÁLISE QUANTITATIVA - NCP v11 (VERSÃO DEEP ANALYSIS)
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
# 1. CONFIGURAÇÃO DA PÁGINA E CSS
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="NCP v11 | Quant Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    h1, h2, h3 { color: #E0E0E0; font-family: 'Courier New', monospace; }
    .stMetric { background-color: #1E2129; padding: 15px; border-radius: 8px; border-left: 4px solid #00E676; }
    div[data-testid="stExpander"] { background-color: #1E2129; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 2. MOTOR DE DADOS HISTÓRICOS (Com Validação de Escala)
# ------------------------------------------------------------------------------
@st.cache_data(ttl=60) # Recarrega o CSV a cada 60s se houver alterações no GitHub
def carregar_dados_ncp():
    try:
        df = pd.read_csv('NCP_Platform_Data.csv')
        
        # Converte a primeira coluna (timestamp) para index
        nome_coluna_data = df.columns[0]
        df[nome_coluna_data] = pd.to_datetime(df[nome_coluna_data])
        df.set_index(nome_coluna_data, inplace=True)
        
        # VERIFICAÇÃO DE SEGURANÇA: Garante que as colunas essenciais existem
        colunas_necessarias = [
            'open', 'high', 'low', 'close', 'delta_pct', 'delta',
            'rejection_bot', 'rejection_top', 'whale_buy_pct', 'whale_sell_pct'
        ]
        for col in colunas_necessarias:
            if col not in df.columns:
                df[col] = 0.0 # Se faltar alguma, cria colunas zeradas
        
        # NORMALIZAÇÃO DE ESCALA: Corrige dados decimais (0.5) para percentuais (50.0%)
        if df['rejection_bot'].max() <= 1.0 and df['rejection_bot'].max() > 0:
            df['rejection_bot'] = df['rejection_bot'] * 100
            df['rejection_top'] = df['rejection_top'] * 100
            
        if abs(df['delta_pct'].max()) <= 1.0 and abs(df['delta_pct'].min()) >= -1.0:
            df['delta_pct'] = df['delta_pct'] * 100
            
        if df['whale_buy_pct'].max() <= 1.0 and df['whale_buy_pct'].max() > 0:
            df['whale_buy_pct'] = df['whale_buy_pct'] * 100
            df['whale_sell_pct'] = df['whale_sell_pct'] * 100
            
        return df
    except Exception as e:
        return None

df = carregar_dados_ncp()

# ------------------------------------------------------------------------------
# 3. MOTOR DE DADOS AO VIVO (API DA BINANCE)
# ------------------------------------------------------------------------------
def buscar_vela_atual_binance(ativo="BTCUSDT"):
    """Busca o Delta Real das agressões na Binance"""
    try:
        url = f"https://api.binance.com/api/v3/aggTrades?symbol={ativo}&limit=1000"
        resposta = requests.get(url, timeout=5)
        if resposta.status_code != 200:
            return None
            
        trades = resposta.json()
        df_live = pd.DataFrame(trades)
        df_live['price'] = df_live['p'].astype(float)
        df_live['qty'] = df_live['q'].astype(float)
        df_live['is_buyer_maker'] = df_live['m']
        
        df_live['volume'] = df_live['price'] * df_live['qty']
        df_live['delta_trade'] = np.where(df_live['is_buyer_maker'], -df_live['volume'], df_live['volume'])
        delta_atual = df_live['delta_trade'].sum()
        preco_atual = df_live['price'].iloc[-1]
        
        return {'close': preco_atual, 'delta_ao_vivo': delta_atual}
    except:
        return None

# ------------------------------------------------------------------------------
# 4. INTERFACE DE UTILIZADOR (Sidebar)
# ------------------------------------------------------------------------------
st.sidebar.title("⚡ NCP v11 Engine")
st.sidebar.markdown("---")

ativo_selecionado = st.sidebar.selectbox("Ativo", ["BTCUSDT", "ETHUSDT", "SOLUSDT"])

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Calibração Profunda (VSA & Flow)")
st.sidebar.caption("Filtros avançados de Absorção e Exaustão.")

# Sliders de Agressão (Delta)
ind_delta_fundo = st.sidebar.slider("Delta % Máximo (Exaustão Venda)", min_value=-20.0, max_value=0.0, value=-5.0, step=0.5)
ind_delta_topo  = st.sidebar.slider("Delta % Mínimo (Exaustão Compra)", min_value=0.0, max_value=20.0, value=5.0, step=0.5)

# Sliders de Anatomia da Vela (Absorção e Esforço vs Resultado)
ind_rejeicao    = st.sidebar.slider("Rejeição Mínima (%)", min_value=1.0, max_value=80.0, value=40.0, step=1.0)
ind_corpo_max   = st.sidebar.slider("Tamanho Máx. Corpo (%)", min_value=5.0, max_value=100.0, value=35.0, step=1.0, help="Corpos menores indicam que o esforço não gerou deslocamento (Absorção).")

# Sliders de Gatilho Institucional
ind_baleias     = st.sidebar.slider("Ativ. Baleias Mínima (%)", min_value=0.0, max_value=100.0, value=35.0, step=1.0)

ligar_indicador = st.sidebar.toggle("🟢 Ligar Sinais de Alta Precisão", value=True)

st.sidebar.markdown("---")
modo_live = st.sidebar.toggle("🔴 LIVE MODE (Atualização a cada 10s)", value=False)

# ------------------------------------------------------------------------------
# 5. LÓGICA DO LIVE MODE (Segura)
# ------------------------------------------------------------------------------
if modo_live:
    placeholder = st.sidebar.empty()
    placeholder.info("🔄 Auto-refresh ativado...")

# ------------------------------------------------------------------------------
# 6. PAINEL PRINCIPAL
# ------------------------------------------------------------------------------
st.title(f"Terminal Quantitativo: {ativo_selecionado}")

if df is None or len(df) == 0:
    st.error("⚠️ Erro Crítico: O ficheiro 'NCP_Platform_Data.csv' não foi encontrado ou está vazio. Por favor, verifique o seu GitHub.")
    st.stop()

# --- DADOS AO VIVO NO TOPO ---
dados_frescos = buscar_vela_atual_binance(ativo_selecionado)
if dados_frescos:
    col1, col2, col3 = st.columns(3)
    col1.metric("Preço Spot (Ao Vivo)", f"${dados_frescos['close']:,.2f}")
    
    cor_delta = "normal" if dados_frescos['delta_ao_vivo'] > 0 else "inverse"
    estado_delta = "🟢 Compradores a Agredir" if dados_frescos['delta_ao_vivo'] > 0 else "🔴 Vendedores a Agredir"
    col2.metric("Delta (Últimos 1000 trades)", f"{dados_frescos['delta_ao_vivo']:,.0f}", estado_delta, delta_color=cor_delta)
else:
    st.warning("A aguardar conexão com a Binance para dados ao vivo...")

st.markdown("---")

# ------------------------------------------------------------------------------
# 7. MOTOR LÓGICO PROFUNDO & GRÁFICO (Plotly)
# ------------------------------------------------------------------------------
df_plot = df.tail(1000).copy()

# Cálculo adicional em tempo de execução: Esforço vs Resultado (Percentagem de Corpo)
range_vela = df_plot['high'] - df_plot['low']
range_vela = range_vela.replace(0, 0.00001) # Prevenir divisão por zero
df_plot['body_pct'] = (abs(df_plot['close'] - df_plot['open']) / range_vela) * 100

if ligar_indicador:
    # Lógica de Cruzamento Pentadimensional:
    # 1. Delta Extremo (Exaustão do Retalho)
    # 2. Pavio Longo (Limite Passivo/Absorção)
    # 3. Corpo Pequeno (Anomalia de Esforço vs Resultado)
    # 4. Envolvimento de Baleias
    # 5. Predominância Direcional Real das Baleias
    
    df_plot['sinal_compra'] = (
        (df_plot['delta_pct'] <= ind_delta_fundo) & 
        (df_plot['rejection_bot'] >= ind_rejeicao) &
        (df_plot['body_pct'] <= ind_corpo_max) & 
        (df_plot['whale_buy_pct'] >= ind_baleias) &
        (df_plot['whale_buy_pct'] > df_plot['whale_sell_pct']) # Trava Mestra
    )
    
    df_plot['sinal_venda'] = (
        (df_plot['delta_pct'] >= ind_delta_topo) & 
        (df_plot['rejection_top'] >= ind_rejeicao) &
        (df_plot['body_pct'] <= ind_corpo_max) & 
        (df_plot['whale_sell_pct'] >= ind_baleias) &
        (df_plot['whale_sell_pct'] > df_plot['whale_buy_pct']) # Trava Mestra
    )
    
    sinais_compra = df_plot[df_plot['sinal_compra']]
    sinais_venda = df_plot[df_plot['sinal_venda']]
else:
    sinais_compra = pd.DataFrame()
    sinais_venda = pd.DataFrame()

# Criação do Gráfico
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])

# Velas
fig.add_trace(go.Candlestick(
    x=df_plot.index, open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'],
    name='Preço', increasing_line_color='#00E676', decreasing_line_color='#FF1744'
), row=1, col=1)

# Sinais
if ligar_indicador:
    if not sinais_compra.empty:
        fig.add_trace(go.Scatter(
            x=sinais_compra.index, y=sinais_compra['low'] - (sinais_compra['close']*0.01), 
            mode='markers+text', marker=dict(symbol='triangle-up', size=18, color='#00E676', line=dict(width=2, color='white')), 
            name='BUY', text="BUY", textposition="bottom center"
        ), row=1, col=1)
        
    if not sinais_venda.empty:
        fig.add_trace(go.Scatter(
            x=sinais_venda.index, y=sinais_venda['high'] + (sinais_venda['close']*0.01), 
            mode='markers+text', marker=dict(symbol='triangle-down', size=18, color='#FF1744', line=dict(width=2, color='white')), 
            name='SELL', text="SELL", textposition="top center"
        ), row=1, col=1)

# Delta Bar
cores_delta = ['#00E676' if d > 0 else '#FF1744' for d in df_plot['delta']]
fig.add_trace(go.Bar(
    x=df_plot.index, y=df_plot['delta'], name='Delta Volume', marker_color=cores_delta, opacity=0.8
), row=2, col=1)

fig.update_layout(
    template='plotly_dark', height=650, margin=dict(l=10, r=10, t=10, b=10), 
    xaxis_rangeslider_visible=False, showlegend=False,
    plot_bgcolor='#0E1117', paper_bgcolor='#0E1117'
)
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------------------
# 8. DIAGNÓSTICO DO SISTEMA E ESTATÍSTICAS
# ------------------------------------------------------------------------------
with st.expander("🛠️ Raio-X do Motor (Microestrutura)", expanded=True):
    st.markdown("Verifique os limites matemáticos extraídos do dataset para afinar os Filtros de Absorção.")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    col_d1.metric("Delta Mais Negativo (Exaustão)", f"{df_plot['delta_pct'].min():.2f}%")
    col_d2.metric("Maior Rejeição Inferior", f"{df_plot['rejection_bot'].max():.2f}%")
    col_d3.metric("Maior Compra de Baleias", f"{df_plot['whale_buy_pct'].max():.2f}%")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_d4, col_d5, col_d6 = st.columns(3)
    col_d4.metric("Delta Mais Positivo (Euforia)", f"{df_plot['delta_pct'].max():.2f}%")
    col_d5.metric("Maior Rejeição Superior", f"{df_plot['rejection_top'].max():.2f}%")
    col_d6.metric("Menor Corpo Observado (Doji)", f"{df_plot['body_pct'].min():.2f}%")

# ------------------------------------------------------------------------------
# 9. EXECUÇÃO DO REFRESH AO VIVO (No Final do Script)
# ------------------------------------------------------------------------------
if modo_live:
    time.sleep(10) # Pausa segura
    st.rerun()
