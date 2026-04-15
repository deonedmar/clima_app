import streamlit as st
import pandas as pd
import openmeteo_requests
from geopy.geocoders import Nominatim
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium
import datetime
from geopy.geocoders import ArcGIS

st.set_page_config(page_title="Climate Extractor", layout="wide", page_icon="☁️")


st.markdown("""
    <style>
    .stApp {
        background: url('https://images.unsplash.com/photo-1513002749550-c59d786b8e6c?q=80&w=2000&auto=format&fit=crop');
        background-size: cover;
        background-attachment: fixed;
    }
    [data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.85) !important;
        padding: 20px !important;
        border-radius: 15px !important;
        border-left: 5px solid #007BFF !important;
    }
    .info-box {
        background-color: rgba(0, 64, 128, 0.85);
        color: white;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #00d4ff;
        font-size: 0.85rem;
        margin-bottom: 20px;
    }
    /* Forçando as fontes das métricas para PRETO */
    [data-testid="stMetricLabel"] p { color: rgba(0, 0, 0, 1) !important; font-weight: bold; }
    [data-testid="stMetricValue"] div { color: rgba(0, 0, 0, 1) !important; }

    h1, h2, h3 { color: #000000 !important; text-shadow: 1px 1px 2px rgba(255,255,255,0.5); }
    </style>
    """, unsafe_allow_html=True)



def obter_coordenadas(cidade):
    try:
        geolocator = ArcGIS() # Não precisa de user_agent, alterado todo bloco
        location = geolocator.geocode(cidade)
        if location:
            return location.latitude, location.longitude, location.address
    except Exception as e:
        st.error(f"Erro na busca: {e}")
    return None, None, None


def buscar_dados(lat, lon, inicio, fim):
    openmeteo = openmeteo_requests.Client()
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": inicio, "end_date": fim,
        "hourly": ["temperature_2m", "precipitation", "wind_speed_10m"],
        "wind_speed_unit": "kn", "timezone": "auto"
    }
    try:
        responses = openmeteo.weather_api(url, params=params)
        hourly = responses[0].Hourly()
        datas = pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s"),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s"),
            freq=pd.Timedelta(seconds=hourly.Interval()), inclusive="left"
        )
        df = pd.DataFrame({
            "data_hora": datas,
            "temperatura_c": hourly.Variables(0).ValuesAsNumpy(),
            "chuva_mm": hourly.Variables(1).ValuesAsNumpy(),
            "vento_nos": hourly.Variables(2).ValuesAsNumpy(),
            "latitude": [lat] * len(datas), "longitude": [lon] * len(datas)
        })
        df['data_br'] = df['data_hora'].dt.strftime('%d/%m/%Y %H:%M')
        return df
    except Exception as e:
        print(f"Erro na API: {e}")
        return None



with st.sidebar:
    st.markdown("### ☁️ Sobre o Sistema")
    st.markdown(
        '<div class="info-box"><strong>📅 Dados Disponíveis</strong><br>Consultas históricas desde 01/01/1940.<br><br><strong>🌐 Fonte</strong><br>Modelo ERA5 (ECMWF).</div>',
        unsafe_allow_html=True)
    st.info("deonedmar@gmail.com Eddy Minimum")


st.title("☁️ Climate Extractor")
tab1, tab2 = st.tabs(["🚀 Extração de Dados", "📊 Análise Visual"])

with tab1:
    st.markdown("### 📥 Configurar Coleta")
    c1, c2, c3 = st.columns([2, 1, 1])

    # AJUSTE DATA 1940
    data_minima = datetime.date(1940, 1, 1)
    data_hoje = datetime.date.today()

    with c1:
        cid = st.text_input("Cidade e Estado", "Praia Grande, SP")
    with c2:
        d_ini = st.date_input("Data Inicial", value=data_hoje, min_value=data_minima, max_value=data_hoje)
    with c3:
        d_fim = st.date_input("Data Final", value=data_hoje, min_value=data_minima, max_value=data_hoje)

    if st.button("Executar Extração"):
        if d_ini > d_fim:
            st.error("A data inicial não pode ser maior que a final.")
        else:
            with st.spinner("Buscando no banco de dados histórico..."):
                lat, lon, ender = obter_coordenadas(cid)
                if lat:
                    df_res = buscar_dados(lat, lon, d_ini.strftime('%Y-%m-%d'), d_fim.strftime('%Y-%m-%d'))
                    if df_res is not None and not df_res.empty:
                        st.session_state['df_final'] = df_res
                        st.session_state['local_final'] = ender
                        st.success(f"Dados coletados com sucesso para: {ender}")
                    else:
                        st.error("Sem dados para este período ou erro na API.")
                else:
                    st.error("Localização não encontrada. Tente: Cidade, Estado, País.")

with tab2:
    if 'df_final' in st.session_state:
        df = st.session_state['df_final']
        st.subheader(f"📍 {st.session_state['local_final']}")

        m1, m2, m3 = st.columns(3)
        m1.metric("🌡️ Temp. Média", f"{df['temperatura_c'].mean():.1f} °C")
        m2.metric("🌧️ Chuva Total", f"{df['chuva_mm'].sum():.1f} mm")
        m3.metric("💨 Vento Máx.", f"{df['vento_nos'].max():.1f} kt")

        # Gráfico Plotly
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['data_hora'], y=df['temperatura_c'], name="Temperatura",
                                 line=dict(color='#E63946', width=3), customdata=df['data_br'],
                                 hovertemplate="<b>%{customdata}</b><br>Temp: %{y}°C<extra></extra>"))
        fig.add_trace(
            go.Bar(x=df['data_hora'], y=df['chuva_mm'], name="Chuva", yaxis="y2", marker_color='#457B9D', opacity=0.6,
                   customdata=df['data_br'], hovertemplate="<b>%{customdata}</b><br>Chuva: %{y}mm<extra></extra>"))

        fig.update_layout(
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=0, r=0, t=30, b=0),
            yaxis=dict(title="Temp (°C)"),
            yaxis2=dict(overlaying="y", side="right", title="Chuva (mm)")
        )
        st.plotly_chart(fig, use_container_width=True)

        # Mapa
        m = folium.Map(location=[df['latitude'].iloc[0], df['longitude'].iloc[0]], zoom_start=12)
        folium.Marker([df['latitude'].iloc[0], df['longitude'].iloc[0]], popup=st.session_state['local_final']).add_to(
            m)
        st_folium(m, width="100%", height=300, returned_objects=[])
    else:
        st.info("Aguardando extração na primeira aba.")
