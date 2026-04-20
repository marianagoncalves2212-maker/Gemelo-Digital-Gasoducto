import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from dataclasses import dataclass

# 1. Configuración inicial de la aplicación
# En esta sección preparamos el entorno visual, las variables físicas
# inmutables y la base de datos de materiales del proyecto

# 1.1 Configuración de página y estilos (CSS)
# Inicializamos la página ocupando todo el ancho de la pantalla
st.set_page_config(page_title="Gemelo Digital - Gasoducto", layout="wide", initial_sidebar_state="expanded")

# Escribimos CSS personalizado para refinar la interfaz:
# - Reducimos el margen superior para aprovechar el espacio
# - Ajustamos el ancho máximo del panel lateral
# - Ocultamos el mensaje nativo de Streamlit ("Please press Enter to apply") en los inputs numéricos
st.markdown("""
    <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 1rem;
        }
        [data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 310px;
            max-width: 330px;
        }
        [data-testid="InputInstructions"] {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

# 1.2 Definición de parámetros físicos y termodinámicos
# Utilizamos un Dataclass para agrupar de forma limpia las constantes del sistema
@dataclass
class ParametrosSistema:
    longitud_total: float = 400.0 # Longitud total del tramo en km
    p_inicial: float = 800.0 # Presión de inyección en psia
    p_minima: float = 500.0 # Presión de entrega requerida en psia
    temp_maxima: float = 65.0 # Límite térmico operativo en °C
    temperatura_ref: float = 293.15 # Temperatura del suelo/referencia en K (20°C)
    gravedad_esp: float = 0.65 # Gravedad específica del gas natural
    z_factor: float = 0.90 # Factor de compresibilidad promedio
    eficiencia_comp: float = 0.75 # Eficiencia adiabática de los compresores
    k_cp: float = 1.3 # Relación de calores específicos
    r_gas: float = 10.73 # Constante universal de los gases (unidades imperiales)
    vida_util: int = 20 # Horizonte del proyecto en años
    costo_hp_inst: float = 1500.0 # Costo unitario de compresión en USD/HP

params = ParametrosSistema()

# 1.3 Base de datos de materiales
# Diccionarios con las especificaciones estándar para tuberías API 5L (Schedule 40)
# y los límites de fluencia según el grado del acero
ESPECIFICACIONES_TUBERIA = {
    12.0: {"od_mm": 323.8, "wt_mm": 10.31, "costo": 185.0},
    16.0: {"od_mm": 406.4, "wt_mm": 12.70, "costo": 260.0},
    20.0: {"od_mm": 508.0, "wt_mm": 15.09, "costo": 350.0},
    24.0: {"od_mm": 609.6, "wt_mm": 17.48, "costo": 440.0}
}

SMYS_ACERO = {
    "X52": 52000.0,
    "X60": 60000.0
}

# 1.4 Funciones auxiliares de interfaz
def tarjeta_color(titulo: str, valor: str, color_fondo: str):
    """
    Renderiza una tarjeta de KPI (Key Performance Indicator) con estilo personalizado.
    Evitamos usar st.metric nativo para tener control total sobre el fondo y la sombra.
    """
    html = f"""
    <div style="background-color: {color_fondo}; padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px; box-shadow: 3px 3px 10px rgba(0,0,0,0.1);">
        <h2 style="color: white; margin: 0; font-size: 32px; font-weight: bold;">{valor}</h2>
        <p style="margin: 5px 0 0 0; font-size: 16px; opacity: 0.9;">{titulo}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# 2. Motor de cálculo y simulación
# Este bloque contiene toda la lógica matemática del gemelo digital. 

# 2.1 Verificación de integridad estructural
def calcular_maop(diametro_nominal: float, grado_acero: str) -> float:
    """Calcula la Presión Máxima Operativa Permisible (MAOP) usando la Ecuación de Barlow"""
    especs = ESPECIFICACIONES_TUBERIA[diametro_nominal]
    od_pulg = especs["od_mm"] / 25.4 # Conversión de milímetros a pulgadas
    wt_pulg = especs["wt_mm"] / 25.4
    smys = SMYS_ACERO[grado_acero]
    factor_diseno = 0.72 # Factor de seguridad estándar (clase de localidad 1)
    
    maop = (2 * smys * wt_pulg / od_pulg) * factor_diseno
    return maop

# 2.2 Hidráulica del gasoducto
def calcular_weymouth(p_in: float, q: float, longitud: float, diametro: float, eficiencia: float = 1.0) -> float:
    """
    Determina la presión de llegada en un tramo de tubería utilizando la ecuación de Weymouth.
    Lanza una excepción si la caída de presión es matemáticamente imposible de sostener.
    """
    constante = 433.5
    termino_flujo = (q / eficiencia)**2
    termino_friccion = (longitud * params.gravedad_esp * params.temperatura_ref * params.z_factor) / (diametro**5.33)
    caida_presion = constante * termino_flujo * termino_friccion
    p_out_cuadrado = (p_in**2) - caida_presion
    
    # Manejo de errores para evitar raíces de números negativos
    if p_out_cuadrado < 0:
        raise ValueError("**Configuración no viable:** El gradiente de presión es insuficiente para el flujo solicitado. Incremente el diámetro o el número de estaciones.")
    
    return np.sqrt(p_out_cuadrado)

# 2.3 Termodinámica de las estaciones de compresión
def calcular_compresion(p_in: float, p_out: float, t_in: float, q_diseno: float) -> tuple[float, float]:
    """Calcula la potencia requerida (HP) y la temperatura resultante tras el proceso de compresión."""
    flujo_seg = (q_diseno * 1e6) / (24 * 3600)
    factor_k = (params.k_cp - 1) / params.k_cp
    
    trabajo = (params.z_factor * params.r_gas * t_in) / (params.k_cp - 1)
    relacion_presion = (p_out / p_in)**factor_k - 1
    
    hp_req = (flujo_seg / params.eficiencia_comp) * trabajo * relacion_presion
    t_out = t_in * (p_out / p_in)**factor_k
    
    return hp_req, t_out

# 2.4 Evaluación económica
def calcular_tac(diametro: float, hp_total: float, tasa_interes: float, costo_energia: float) -> tuple[float, float, float]:
    """
    Estima el Costo Total Anualizado (TAC).
    Considera la inversión inicial (CAPEX) amortizada y los costos operativos (OPEX).
    """
    costo_tuberia_total = ESPECIFICACIONES_TUBERIA[diametro]["costo"] * (params.longitud_total * 1000)
    costo_compresores = hp_total * params.costo_hp_inst
    capex_total = costo_tuberia_total + costo_compresores
    
    # Factor de recuperación de capital (CRF)
    crf = (tasa_interes * (1 + tasa_interes)**params.vida_util) / (((1 + tasa_interes)**params.vida_util) - 1)
    capex_anual = capex_total * crf
    
    # Conversión de HP a kW para cálculo de facturación eléctrica
    kw_total = hp_total * 0.7457
    opex_anual = kw_total * 24 * 365 * costo_energia
    
    tac = capex_anual + opex_anual
    return tac, capex_anual, opex_anual

# 2.5 Bucle principal de simulación del gasoducto
# Usamos caché para que el modelo solo se recalcule si cambian las entradas del usuario
@st.cache_data
def simular_gasoducto(diametro: float, n_estaciones: int, q_diseno: float, tasa_interes: float, costo_energia: float):
    """Orquesta la simulación nodo por nodo a lo largo de todo el gasoducto."""
    tramos = n_estaciones + 1
    longitud_tramo = params.longitud_total / tramos
    
    presion_actual = params.p_inicial
    potencia_total = 0.0
    temperatura_max_alcanzada = params.temperatura_ref
    
    # Listas de registro para alimentar posteriormente el gráfico de perfil hidráulico
    perfil_distancia = [0.0]
    perfil_presion = [params.p_inicial]
    
    for i in range(tramos):
        # 1. Pérdida de presión a lo largo del tramo actual
        p_llegada = calcular_weymouth(presion_actual, q_diseno, longitud_tramo, diametro)
        distancia_actual = perfil_distancia[-1] + longitud_tramo
        perfil_distancia.append(distancia_actual)
        perfil_presion.append(p_llegada)
        presion_actual = p_llegada
        
        # 2. Re-compresión al final del tramo (omitido en el destino final)
        if i < n_estaciones:
            potencia_nodo, t_descarga = calcular_compresion(presion_actual, params.p_inicial, params.temperatura_ref, q_diseno)
            potencia_total += potencia_nodo
            
            # Registramos el pico térmico de todo el sistema
            if t_descarga > temperatura_max_alcanzada:
                temperatura_max_alcanzada = t_descarga
                
            # Represurización para el siguiente tramo
            presion_actual = params.p_inicial 
            perfil_distancia.append(distancia_actual) 
            perfil_presion.append(presion_actual)    
            
    # 3. Consolidación financiera tras finalizar el ruteo
    tac_final, capex_a, opex_a = calcular_tac(diametro, potencia_total, tasa_interes, costo_energia)
    
    return presion_actual, potencia_total, temperatura_max_alcanzada, tac_final, capex_a, opex_a, perfil_distancia, perfil_presion


# 3. Interfaz de usuario (panel lateral)
# Captura de datos de entrada

with st.sidebar:
    st.title("Panel de configuración")
    
    # 3.1 Parámetros económicos
    st.markdown("### 1. Parámetros económicos")
    costo_energia_input = st.number_input("Costo de energía (USD/kWh)", value=0.08, step=0.01, help="Tarifa eléctrica promedio para el funcionamiento de las estaciones de compresión.")
    tasa_interes_input = st.slider("Tasa de interés (%)", min_value=1.0, max_value=15.0, value=10.0, step=0.5, help="Tasa de descuento utilizada para amortizar el CAPEX.") / 100.0
    
    # 3.2 Selección de material
    st.markdown("### 2. Selección de material")
    diametro_str = st.selectbox("Diámetro nominal (pulg)", ["12", "16", "20", "24"], index=2, help="Determina el diámetro de la tubería API 5L (Sch 40). A mayor diámetro, menor caída de presión pero mayor costo de capital.")
    diametro_input = float(diametro_str)
    grado_acero_input = st.selectbox("Grado de acero", ["X52", "X60"], help="Define el Límite de Fluencia (SMYS) para el cálculo de integridad estructural (MAOP).")
    
    # 3.3 Variables operativas
    st.markdown("### 3. Variables operativas")
    q_diseno_input = st.number_input("Flujo de gas Q (MMscfd)", value=500.0, step=10.0, help="Caudal volumétrico de diseño en millones de pies cúbicos estándar por día.")
    n_estaciones_input = st.number_input("Número de estaciones (N)", min_value=0, max_value=5, value=2, step=1, help="Cantidad de estaciones de compresión intermedias distribuidas a lo largo del ducto.")


# 4. Panel principal (dashboard y visualización)
# Renderizado de los resultados

st.title("Gasoducto Trans-Andino")
st.markdown("### Indicadores clave de desempeño")

# 4.1 Ejecución del modelo y manejo de excepciones
# Envolvemos la simulación en un bloque try-except para capturar configuraciones inviables
# e informar al operador sin que la aplicación colapse.
try:
    p_final, hp_tot, t_max_k, tac, capex, opex, distancias, presiones = simular_gasoducto(
        diametro=diametro_input, n_estaciones=n_estaciones_input, 
        q_diseno=q_diseno_input, tasa_interes=tasa_interes_input, costo_energia=costo_energia_input
    )
    
    # Post-procesamiento de unidades
    t_max_c = t_max_k - 273.15
    maop_calculado = calcular_maop(diametro_input, grado_acero_input)
    
    # 4.2 Tarjetas de Indicadores Clave (KPIs)
    c1, c2, c3 = st.columns(3)
    
    # Formato estándar con 2 decimales y comas para los miles
    str_tac = f"$ {tac/1e6:,.2f} MM"
    str_hp = f"{hp_tot:,.2f} HP"
    str_pfinal = f"{p_final:,.2f} psia"
    
    # El tercer indicador adopta un tono morado si cumple el diseño, rojo en caso de falla
    color_presion = "#5c6bc0" if p_final >= params.p_minima else "#dc3545" 
    
    with c1: tarjeta_color("Costo Total Anualizado (TAC)", str_tac, "#17a2b8")
    with c2: tarjeta_color("Potencia total instalada", str_hp, "#28a745")
    with c3: tarjeta_color("Presión final de entrega", str_pfinal, color_presion)

    # 4.3 Sistema de seguridad y validación de límites
    st.markdown("### Sistema de seguridad")
    alert1, alert2, alert3 = st.columns(3)
    
    # Evaluación mecánica (Barlow)
    with alert1:
        if maop_calculado >= params.p_inicial:
            st.success(f"**Integridad estructural:** MAOP de {maop_calculado:,.2f} psia. La tubería soporta la presión máxima del sistema ({params.p_inicial:,.2f} psia).")
        else:
            st.error(f"**Integridad estructural:** Falla. El MAOP ({maop_calculado:,.2f} psia) es inferior a la presión máxima de diseño ({params.p_inicial:,.2f} psia).")
        
    # Evaluación termodinámica
    with alert2:
        if t_max_c <= params.temp_maxima:
            st.success(f"**Cumplimiento térmico:** {t_max_c:,.2f} °C. El valor se encuentra dentro del rango operativo seguro (máx. {params.temp_maxima:,.2f} °C).")
        else:
            st.error(f"**Cumplimiento térmico:** {t_max_c:,.2f} °C. El valor supera el límite de seguridad operativo estipulado ({params.temp_maxima:,.2f} °C).")
            
    # Evaluación de entrega
    with alert3:
        if p_final >= params.p_minima:
            st.success(f"**Condición de entrega:** {p_final:,.2f} psia. El sistema garantiza el requisito mínimo de presión en el destino ({params.p_minima:,.2f} psia).")
        else:
            st.error(f"**Condición de entrega:** {p_final:,.2f} psia. El sistema no alcanza el mínimo de presión requerido por el cliente ({params.p_minima:,.2f} psia).")


    # 4.4 Visualización de resultados (gráficos interactivos)
    col_grafico, col_costos = st.columns([2, 1])
    
    color_graficos = '#1f77b4' 
    color_fuente = '#31333F' 

    # Perfil hidráulico (comportamiento de presión vs distancia)
    with col_grafico:
        st.markdown("#### Comportamiento hidráulico del gasoducto")
        fig_perfil = px.line(
            x=distancias, y=presiones, 
            labels={'x': '<b>Distancia (km)</b>', 'y': '<b>Presión (psia)</b>'},
            color_discrete_sequence=[color_graficos] 
        )
        
        # Limpiamos el gráfico retirando la cuadrícula y las líneas de origen
        fig_perfil.update_traces(line=dict(width=3))
        fig_perfil.update_layout(
            plot_bgcolor='white',
            margin=dict(l=0, r=0, t=10, b=0),
            font=dict(color=color_fuente),
            xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(weight='bold')),
            yaxis=dict(showgrid=False, zeroline=False, tickfont=dict(weight='bold')),
        )
        st.plotly_chart(fig_perfil, use_container_width=True)

    # Distribución de la inversión (CAPEX vs OPEX)
    with col_costos:
        st.markdown("#### Distribución anual de costos")
        df_costos = pd.DataFrame({"Categoría": ["CAPEX", "OPEX"], "Costo": [capex / 1e6, opex / 1e6]})
        
        fig_costos = px.bar(
            df_costos, x="Categoría", y="Costo",
            labels={'Categoría': '<b>Tipo de Costo</b>', 'Costo': '<b>Millones de USD ($)</b>'},
            text_auto=',.2f', # Agregamos la coma aquí también para los miles en las barras
            color_discrete_sequence=[color_graficos] 
        )
        
        fig_costos.update_traces(
            marker_line_width=0,
            textfont=dict(weight='bold', color='white') 
        )
        fig_costos.update_layout(
            plot_bgcolor='white',
            xaxis_tickangle=0, 
            margin=dict(l=0, r=0, t=10, b=0),
            font=dict(color=color_fuente),
            xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(weight='bold')),
            yaxis=dict(showgrid=False, zeroline=False, tickfont=dict(weight='bold')),
        )
        st.plotly_chart(fig_costos, use_container_width=True)

except ValueError as e:
    # Captura de errores operativos y renderizado de un estado de "Falla Total"
    c1, c2, c3 = st.columns(3)
    with c1: tarjeta_color("Costo Total Anualizado (TAC)", "FALLA", "#dc3545") 
    with c2: tarjeta_color("Potencia total instalada", "FALLA", "#dc3545")
    with c3: tarjeta_color("Presión final de entrega", "0.00 psia", "#dc3545")
    
    st.error(str(e))