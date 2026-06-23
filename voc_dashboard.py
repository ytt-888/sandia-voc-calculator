import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
from io import BytesIO

st.set_page_config(page_title="Sandia Voc Calculator", layout="wide")
st.title("🌞 Sandia Voc String Calculator with .PAN Upload")

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
st.sidebar.header("📁 Upload .PAN File")
uploaded_file = st.sidebar.file_uploader("Upload module .PAN file", type=["pan", "PAN", "txt"])

pan_params = {}
if uploaded_file:
    pan_params = parse_pan_file(uploaded_file)
    st.sidebar.success("PAN file loaded!")

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

st.sidebar.write(f"a = {a}, b = {b}")

# ==================== CALCULATION ====================
irradiance = np.arange(50, 1001, 50)

def calculate(Ee):
    Tc = Tamb + (Ee / 1000) * np.exp(a + b * WS) + 2.0
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

# ==================== DISPLAY ====================
st.subheader("📊 Results Table")
st.dataframe(df, width='stretch', hide_index=True)

max_row = df.loc[df["String Voc (V)"].idxmax()]
st.success(f"**Maximum String Voc = {max_row['String Voc (V)']} V** at {max_row['Irradiance (W/m²)']} W/m² (Tc = {max_row['Cell Temp Tc (°C)']} °C)")

# ==================== DOWNLOAD BUTTONS ====================
st.subheader("⬇️ Download Results")

col1, col2 = st.columns(2)

with col1:
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download as CSV",
        data=csv,
        file_name="sandia_voc_results.csv",
        mime="text/csv",
        width='stretch'
    )

with col2:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Voc Results')
    excel_data = output.getvalue()

    st.download_button(
        label="📥 Download as Excel",
        data=excel_data,
        file_name="sandia_voc_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width='stretch'
    )

# ==================== GRAPHS ====================
st.subheader("📈 Graphs")

col1, col2 = st.columns(2)
with col1:
    fig1 = px.line(df, x="Irradiance (W/m²)", y="Cell Temp Tc (°C)", 
                   title="Cell Temperature vs Irradiance", markers=True)
    st.plotly_chart(fig1, width='stretch')

with col2:
    fig2 = px.line(df, x="Irradiance (W/m²)", y="String Voc (V)", 
                   title="String Voc vs Irradiance", markers=True, color_discrete_sequence=["red"])
    st.plotly_chart(fig2, width='stretch')

st.caption("Sandia SAPM Model | n = 1.0 | .PAN Upload + CSV/Excel Export")
