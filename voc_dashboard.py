import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
from io import BytesIO

st.set_page_config(page_title="Sandia Voc Calculator", layout="wide")
st.title("🌞 Sandia Voc String Calculator with .PAN Upload")

# ==================== PAN FILE PARSER ====================
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
st.sidebar.header("📁 Upload .PAN File")
uploaded_file = st.sidebar.file_uploader("Upload module .PAN file", type=["pan", "PAN", "txt"])

pan_params = {}
if uploaded_file:
    pan_params = parse_pan_file(uploaded_file)
    st.sidebar.success("PAN file loaded successfully!")

st.sidebar.header("Module Parameters")

default_Voc0 = pan_params.get("Voc", 48.90)
default_muVoc = pan_params.get("muVocSpec")
default_NCelS = pan_params.get("NCelS", 66)
is_twin = pan_params.get("SubModuleLayout") == "slTwinHalfCells"
default_Ns = default_NCelS * 2 if is_twin else default_NCelS

Voc0 = st.sidebar.number_input("Voc₀ at STC (V)", value=float(default_Voc0), step=0.01)

if default_muVoc is not None:
    default_beta = default_muVoc / 1000
else:
    default_beta = -0.117

beta_voc = st.sidebar.number_input("β_Voc (V/°C)", value=float(default_beta), step=0.001, format="%.3f")
Ns = st.sidebar.number_input("Cells in series (Ns)", value=int(default_Ns))

st.sidebar.header("Environmental Inputs")
Tamb = st.sidebar.number_input("Ambient Temperature (°C)", value=-8.0, step=0.5)
WS = st.sidebar.number_input("Wind Speed (m/s)", value=1.0, step=0.5)
modules_in_string = st.sidebar.number_input("Modules per String", value=29)

st.sidebar.header("Mounting Type")
mounting_type = st.sidebar.selectbox(
    "Mounting Configuration",
    ["Open Rack (Ground Mount / Tracker)", "Glass/Glass Open Rack", "Close Mount"]
)

if "Glass/Glass" in mounting_type:
    a, b = -3.47, -0.0594
elif "Close Mount" in mounting_type:
    a, b = -2.98, -0.0471
else:
    a, b = -3.56, -0.075

st.sidebar.write(f"**a = {a}**, **b = {b}**")

# ==================== CALCULATION (Updated) ====================
irradiance = np.arange(50, 1001, 50)

def calculate(Ee):
    # Module back-surface temperature
    Tm = Tamb + (Ee / 1000) * np.exp(a + b * WS)
    
    # Cell temperature - irradiance dependent
    delta_T = 2.0 * (Ee / 1000)          # 2.0°C at 1000 W/m²
    Tc = Tm + delta_T
    
    # Voc calculation
    Ee_norm = Ee / 1000.0
    delta = 1.0 * (1.380649e-23 / 1.60217662e-19) * (Tc + 273.15)
    Voc_mod = Voc0 + Ns * delta * np.log(Ee_norm) + beta_voc * (Tc - 25)
    
    return round(Tc, 2), round(Voc_mod, 2)

results = []
for Ee in irradiance:
    Tc, Voc_mod = calculate(Ee)
    results.append({
        "Irradiance (W/m²)": Ee,
        "Cell Temp Tc (°C)": Tc,
        "Module Voc (V)": Voc_mod,
        "String Voc (V)": round(Voc_mod * modules_in_string, 1)
    })

df = pd.DataFrame(results)

# ==================== RESULTS ====================
st.subheader("📊 Results Table")
st.dataframe(df, use_container_width=True, hide_index=True)

max_row = df.loc[df["String Voc (V)"].idxmax()]
st.success(f"**Maximum String Voc = {max_row['String Voc (V)']} V** at {max_row['Irradiance (W/m²)']} W/m² "
           f"(Tc = {max_row['Cell Temp Tc (°C)']} °C)")

# ==================== DOWNLOAD ====================
st.subheader("⬇️ Download Results")

col1, col2 = st.columns(2)
with col1:
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download CSV", csv, "sandia_voc_results.csv", "text/csv")

with col2:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Voc Results')
    st.download_button("📥 Download Excel", output.getvalue(), "sandia_voc_results.xlsx", 
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ==================== GRAPHS ====================
st.subheader("📈 Graphs")
col1, col2 = st.columns(2)
with col1:
    fig1 = px.line(df, x="Irradiance (W/m²)", y="Cell Temp Tc (°C)", title="Cell Temperature vs Irradiance", markers=True)
    st.plotly_chart(fig1, use_container_width=True)
with col2:
    fig2 = px.line(df, x="Irradiance (W/m²)", y="String Voc (V)", title="String Voc vs Irradiance", markers=True, color_discrete_sequence=["red"])
    st.plotly_chart(fig2, use_container_width=True)

# ==================== MODEL DESCRIPTION (Clean & Correct) ====================
st.markdown("---")
with st.expander("📘 Model Description, Equations & Assumptions", expanded=False):

    st.markdown("### 1. Cell Temperature Model (Sandia SAPM)")

    st.latex(r"""
    T_m = T_{amb} + \frac{E_e}{1000} \cdot \exp(a + b \cdot WS)
    """)

    st.markdown("**Cell temperature** (irradiance-dependent):")

    st.latex(r"""
    T_c = T_m + \Delta T_0 \cdot \frac{E_e}{1000}
    """)

    st.markdown("""
    Where:
    - $\Delta T_0 = 2.0^\circ C$ = cell-to-module temperature difference at 1000 W/m²  
    - This makes the temperature difference between the cell and the back surface of the module **vary with irradiance**, which is more physically accurate.
    """)

    st.markdown("**Source:** [pvlib.temperature.sapm_module](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.temperature.sapm_module.html)")

    st.markdown("### 2. Open-Circuit Voltage Model (Sandia SAPM)")

    st.latex(r"""
    V_{oc} = V_{oc0} + N_s \cdot \delta \cdot \ln\left(\frac{E_e}{1000}\right) + \beta_{Voc} \cdot (T_c - 25)
    """)

    st.markdown("Where $\delta = n \cdot k \cdot (T_c + 273.15) / q$ and $n = 1.0$.")

    st.markdown("**Source:** [pvlib.pvsystem.sapm](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.pvsystem.sapm.html)")

    st.markdown("### 3. Key Assumptions & Justifications")

    assumptions = {
        "Parameter": [
            "Diode ideality factor (n)",
            "Cell vs Module ΔT at 1000 W/m²",
            "Temperature model coefficients (a, b)",
            "Wind speed for cold condition",
            "Irradiance range"
        ],
        "Value": [
            "1.0",
            "2.0 °C (irradiance dependent)",
            "Open Rack: a = -3.56, b = -0.075\nGlass/Glass: a = -3.47, b = -0.0594",
            "1.0 m/s (user adjustable)",
            "50 – 1000 W/m² (step 50)"
        ],
        "Justification": [
            "Standard engineering simplification used in Sandia Voc calculations for string sizing",
            "Reasonable value for glass/glass bifacial modules. ΔT now varies with irradiance (more accurate)",
            "Recommended values from pvlib for ground-mounted single-axis tracker systems",
            "Conservative low-wind assumption commonly used for cold-temperature Voc analysis",
            "Covers typical operating range relevant for string voltage sizing"
        ]
    }

    st.table(pd.DataFrame(assumptions))

    st.markdown("""
    **Primary References:**
    - [pvlib-python Documentation](https://pvlib-python.readthedocs.io/)
    - Sandia National Laboratories – *Photovoltaic Array Performance Model* (SAND2004-3535)
    - King et al. (2004), *Sandia Array Performance Model*
    """)

st.caption("Sandia SAPM Model | n = 1.0 | Irradiance-dependent cell temperature | Supports .PAN upload + Excel/CSV export")
