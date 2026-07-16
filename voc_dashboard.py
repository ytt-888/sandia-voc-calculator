import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
from io import BytesIO

st.set_page_config(page_title="Voc Calculator", layout="wide")
st.title("🌞 Voc String Calculator")

# ==================== PAN PARSER ====================
def parse_pan_file(uploaded_file):
    content = uploaded_file.getvalue().decode("utf-8")
    params = {}
    for line in content.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            try:
                params[key] = float(val)
            except ValueError:
                params[key] = val
    return params

# ==================== SIDEBAR ====================
st.sidebar.header("📁 Upload .PAN File (optional)")
uploaded_file = st.sidebar.file_uploader("Upload .PAN file", type=["pan", "PAN", "txt"])

pan_params = {}
if uploaded_file:
    pan_params = parse_pan_file(uploaded_file)
    st.sidebar.success("PAN loaded!")

# ==================== MODEL SELECTOR (САМОЕ ВЕРХНЕЕ) ====================
st.sidebar.header("Calculation Model")
model_choice = st.sidebar.selectbox(
    "Select model",
    ["Sandia SAPM Model", "Simple Temperature Correction"],
    index=0
)

# ==================== CONDITIONAL SIDEBAR ====================
if model_choice == "Sandia SAPM Model":
    # Полная версия Sandia
    st.sidebar.header("Module Parameters")
    default_Voc0 = pan_params.get("Voc", 48.90)
    default_muVoc = pan_params.get("muVocSpec")
    default_NCelS = pan_params.get("NCelS", 66)
    is_twin = pan_params.get("SubModuleLayout") == "slTwinHalfCells"
    default_Ns = default_NCelS * 2 if is_twin else default_NCelS

    Voc0 = st.sidebar.number_input("Voc₀ at STC (V)", value=float(default_Voc0), step=0.01)
    if default_muVoc is not None:
        default_beta = default_muVoc / 1000.0
    else:
        default_beta = -0.117
    beta_voc = st.sidebar.number_input("β_Voc (V/°C)", value=float(default_beta), step=0.001, format="%.3f")
    Ns = st.sidebar.number_input("Cells in series (Ns)", value=int(default_Ns))

    st.sidebar.header("Environmental Inputs")
    Tamb = st.sidebar.number_input("Ambient Temperature (°C)", value=-8.0, step=0.5)
    WS = st.sidebar.number_input("Wind Speed (m/s)", value=1.0, step=0.5)

    st.sidebar.header("Mounting Type")
    mounting_type = st.sidebar.selectbox(
        "Mounting",
        ["Open Rack (Ground Mount / Tracker)", "Glass/Glass Open Rack", "Close Mount"]
    )
    if "Glass/Glass" in mounting_type:
        a, b = -3.47, -0.0594
    elif "Close Mount" in mounting_type:
        a, b = -2.98, -0.0471
    else:
        a, b = -3.56, -0.075
    st.sidebar.write(f"a = {a}, b = {b}")

    modules_in_string = st.sidebar.number_input("Modules per String", value=29)

else:
    # Простая модель - только необходимое
    st.sidebar.header("Module Parameters")
    default_Voc0 = pan_params.get("Voc", 48.90)
    default_muVoc = pan_params.get("muVocSpec")
    default_Ns = pan_params.get("NCelS", 66) * 2 if pan_params.get("SubModuleLayout") == "slTwinHalfCells" else pan_params.get("NCelS", 66)

    Voc0 = st.sidebar.number_input("Voc₀ at STC (V)", value=float(default_Voc0), step=0.01)
    if default_muVoc is not None:
        default_beta = default_muVoc / 1000.0
    else:
        default_beta = -0.117
    beta_voc = st.sidebar.number_input("β_Voc (V/°C)", value=float(default_beta), step=0.001, format="%.3f")
    Ns = st.sidebar.number_input("Cells in series (Ns)", value=int(default_Ns))

    st.sidebar.header("Design Conditions")
    design_low_temp = st.sidebar.number_input(
        "Design Low Cell Temperature (°C)", 
        value=-10.0, 
        step=0.5,
        help="Самая низкая ожидаемая температура ячеек для расчёта максимального Voc"
    )
    modules_in_string = st.sidebar.number_input("Modules per String", value=29)

# ==================== ГЛАВНЫЙ ЭКРАН - ПОЛНОСТЬЮ ЗАВИСИТ ОТ МОДЕЛИ ====================
if model_choice == "Sandia SAPM Model":
    # ==================== ПОЛНАЯ ВЕРСИЯ SANDIA ====================
    st.subheader("📊 Sandia SAPM Model - Full Calculation")

    irradiance = np.arange(50, 1001, 50)

    def calculate_sandia(Ee):
        Tm = Tamb + (Ee / 1000) * np.exp(a + b * WS)
        delta_T = 2.0 * (Ee / 1000)
        Tc = Tm + delta_T
        Ee_norm = Ee / 1000.0
        delta = 1.0 * (1.380649e-23 / 1.60217662e-19) * (Tc + 273.15)
        Voc_mod = Voc0 + Ns * delta * np.log(Ee_norm) + beta_voc * (Tc - 25)
        return round(Tc, 2), round(Voc_mod, 2)

    results = []
    for Ee in irradiance:
        Tc, Voc_mod = calculate_sandia(Ee)
        results.append({
            "Irradiance (W/m²)": Ee,
            "Cell Temp Tc (°C)": Tc,
            "Module Voc (V)": Voc_mod,
            "String Voc (V)": round(Voc_mod * modules_in_string, 1)
        })
    df = pd.DataFrame(results)

    st.dataframe(df, use_container_width=True, hide_index=True)

    max_row = df.loc[df["String Voc (V)"].idxmax()]
    st.success(f"**Maximum String Voc = {max_row['String Voc (V)']} V** at {max_row['Irradiance (W/m²)']} W/m² (Tc = {max_row['Cell Temp Tc (°C)']} °C)")

    col1, col2 = st.columns(2)
    with col1:
        fig1 = px.line(df, x="Irradiance (W/m²)", y="Cell Temp Tc (°C)", title="Cell Temperature vs Irradiance", markers=True)
        st.plotly_chart(fig1, use_container_width=True)
    with col2:
        fig2 = px.line(df, x="Irradiance (W/m²)", y="String Voc (V)", title="String Voc vs Irradiance", markers=True, color_discrete_sequence=["red"])
        st.plotly_chart(fig2, use_container_width=True)

else:
    # ==================== ПРОСТАЯ МОДЕЛЬ ====================
    st.subheader("📊 Simple Temperature Correction Model")

    # Расчёт по фиксированной низкой температуре
    Tc_fixed = design_low_temp
    Voc_module = Voc0 * (1 + beta_voc * (Tc_fixed - 25))
    Voc_string = Voc_module * modules_in_string

    # Большой красивый результат
    st.metric(
        label=f"String Voc при минимальной температуре ({Tc_fixed}°C)",
        value=f"{Voc_string:.1f} V",
        delta=f"{Voc_module:.2f} V на модуль"
    )

    st.info(f"""
    **Формула:**  
    Voc(Tc) = Voc₀ × (1 + β_Voc × (Tc − 25))
    """)

    # Небольшая справочная таблица
    st.markdown("### Параметры расчёта")
    ref = {
        "Параметр": ["Voc при STC", "β_Voc", "Расчётная низкая температура", "Модулей в стринге", "Итоговый String Voc"],
        "Значение": [f"{Voc0} V", f"{beta_voc} V/°C", f"{Tc_fixed} °C", modules_in_string, f"{Voc_string:.1f} V"]
    }
    st.table(pd.DataFrame(ref))

# ==================== ОПИСАНИЕ МОДЕЛИ (динамическое) ====================
st.markdown("---")
with st.expander("📘 Описание модели и формулы", expanded=False):

    if model_choice == "Sandia SAPM Model":
        st.markdown("### Sandia SAPM Model (полная)")
        st.latex(r"V_{oc} = V_{oc0} + N_s \cdot \delta \cdot \ln\left(\frac{E_e}{1000}\right) + \beta_{Voc} \cdot (T_c - 25)")
        st.markdown("Используется полная модель Sandia с учётом иррадиации и температуры.")

    else:
        st.markdown("### Simple Temperature Correction (простая модель)")
        st.latex(r"V_{oc}(T_c) = V_{oc0} \times (1 + \beta_{Voc} \times (T_c - 25))")
        st.markdown("""
        Классическая линейная коррекция по температуре.  
        Используется в большинстве руководств по sizing стрингов.
        """)

st.caption("Две полностью разные модели | Полное обновление интерфейса при смене модели")
