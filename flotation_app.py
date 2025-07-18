import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import time

# Your existing lookup tables (abbreviated for demo)
COLLECTOR_LOOKUP = {
    0: {"recovery": 15.0, "grade": 55.0},
    25: {"recovery": 46.0, "grade": 52.5},
    50: {"recovery": 70.0, "grade": 50.0},
    75: {"recovery": 85.0, "grade": 47.5},
    100: {"recovery": 93.0, "grade": 45.0},
    150: {"recovery": 97.2, "grade": 40.0}
}

AIR_RATE_LOOKUP = {
    0: {"recovery": 25.0, "grade": 32.0},
    25: {"recovery": 85.0, "grade": 53.0},
    50: {"recovery": 84.0, "grade": 46.0},
    75: {"recovery": 61.0, "grade": 31.0},
    100: {"recovery": 25.0, "grade": 16.0}
}

FROTHER_LOOKUP = {
    0: {"recovery": 60.0, "grade": 47.0},
    25: {"recovery": 80.0, "grade": 52.0},
    50: {"recovery": 86.5, "grade": 54.0},
    75: {"recovery": 80.0, "grade": 50.0},
    100: {"recovery": 66.0, "grade": 45.0}
}

PH_LOOKUP = {
    8.5: {"recovery_multiplier": 1.0, "grade_bonus": 0.0},
    9.8: {"recovery_multiplier": 1.13, "grade_bonus": 3.9},
    11.0: {"recovery_multiplier": 0.86, "grade_bonus": 7.5},
    12.0: {"recovery_multiplier": 0.40, "grade_bonus": 10.5}
}

def interpolate_lookup(value, lookup_table):
    """Interpolate between lookup table values"""
    keys = sorted(lookup_table.keys())
    
    if value <= keys[0]:
        return lookup_table[keys[0]]
    if value >= keys[-1]:
        return lookup_table[keys[-1]]
    
    # Find surrounding keys
    for i in range(len(keys) - 1):
        if keys[i] <= value <= keys[i + 1]:
            lower_key, upper_key = keys[i], keys[i + 1]
            break
    
    # Linear interpolation
    weight = (value - lower_key) / (upper_key - lower_key)
    result = {}
    
    for param in lookup_table[lower_key]:
        lower_val = lookup_table[lower_key][param]
        upper_val = lookup_table[upper_key][param]
        result[param] = lower_val + weight * (upper_val - lower_val)
    
    return result

def calculate_performance(collector, air_rate, frother, ph, luproset, mn_grade):
    """Calculate flotation performance from parameters"""
    
    # Get individual effects
    collector_metrics = interpolate_lookup(collector, COLLECTOR_LOOKUP)
    air_metrics = interpolate_lookup(air_rate, AIR_RATE_LOOKUP)
    frother_metrics = interpolate_lookup(frother, FROTHER_LOOKUP)
    ph_metrics = interpolate_lookup(ph, PH_LOOKUP)
    
    # Weighted combination
    base_recovery = (collector_metrics["recovery"] * 0.40 + 
                    air_metrics["recovery"] * 0.25 + 
                    frother_metrics["recovery"] * 0.15 +
                    85.0 * 0.15)
    
    # Apply pH multiplier
    recovery = base_recovery * ph_metrics["recovery_multiplier"]
    
    # Luproset reduces recovery slightly
    recovery -= luproset * 0.015
    
    # Grade calculation
    base_grade = (collector_metrics["grade"] * 0.45 + 
                 air_metrics["grade"] * 0.30 + 
                 frother_metrics["grade"] * 0.15 +
                 50.0 * 0.10)
    
    grade = base_grade + ph_metrics["grade_bonus"] - mn_grade
    
    # Carbon content (affected by luproset)
    carbon = 2.0 * np.exp(-luproset * 0.02)
    
    # Constraints
    recovery = max(0, min(100, recovery))
    grade = max(20, min(65, grade))
    carbon = max(0.5, carbon)
    
    return recovery, grade, carbon

# Streamlit App
st.set_page_config(
    page_title="Zinc Flotation Simulator",
    page_icon="🏭",
    layout="wide"
)

st.title("🏭 Zinc Froth Flotation Control Simulator")
st.markdown("### Six-Parameter Process Control Training System")

# Sidebar controls
st.sidebar.header("Flotation Parameters")

collector = st.sidebar.slider(
    "Collector Dosage (g/t)",
    min_value=0, max_value=150, value=75, step=5,
    help="Primary reagent for mineral hydrophobicity"
)

air_rate = st.sidebar.slider(
    "Air Rate (L/min)",
    min_value=0, max_value=100, value=25, step=5,
    help="Bubble generation rate - bell curve optimization"
)

frother = st.sidebar.slider(
    "Frother Dosage (g/t)",
    min_value=0, max_value=100, value=40, step=5,
    help="Bubble stability and size control"
)

ph = st.sidebar.slider(
    "pH",
    min_value=8.5, max_value=12.0, value=9.8, step=0.1,
    help="Pulp pH - affects mineral surface chemistry"
)

luproset = st.sidebar.slider(
    "Luproset Dosage (g/t)",
    min_value=0, max_value=100, value=50, step=5,
    help="Carbon depressant - reduces carbon content"
)

mn_grade = st.sidebar.slider(
    "Feed Mn Grade (%)",
    min_value=0.1, max_value=1.0, value=0.5, step=0.1,
    help="Manganese content in feed ore"
)

# Calculate current performance
recovery, grade, carbon = calculate_performance(
    collector, air_rate, frother, ph, luproset, mn_grade
)

# Main dashboard
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Zinc Recovery", 
        f"{recovery:.1f}%",
        delta=f"{recovery - 85:.1f}%" if recovery != 85 else None
    )

with col2:
    st.metric(
        "Zinc Grade", 
        f"{grade:.1f}%",
        delta=f"{grade - 50:.1f}%" if grade != 50 else None
    )

with col3:
    st.metric(
        "Carbon Content", 
        f"{carbon:.2f}%",
        delta=f"{carbon - 1.0:.2f}%" if carbon != 1.0 else None
    )

with col4:
    st.metric(
        "Manganese", 
        f"{mn_grade:.1f}%",
        delta=None
    )

# Performance visualization
col1, col2 = st.columns(2)

with col1:
    # Grade-Recovery plot
    fig1 = go.Figure()
    
    # Add current operating point
    fig1.add_scatter(
        x=[recovery], y=[grade],
        mode='markers',
        marker=dict(size=15, color='red', symbol='star'),
        name='Current Operation'
    )
    
    # Add target zone
    fig1.add_shape(
        type="rect",
        x0=80, y0=45, x1=95, y1=55,
        fillcolor="lightgreen", opacity=0.3,
        line=dict(color="green", width=2)
    )
    
    fig1.update_layout(
        title="Grade-Recovery Performance",
        xaxis_title="Zinc Recovery (%)",
        yaxis_title="Zinc Grade (%)",
        showlegend=True
    )
    
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    # Parameter effects radar chart
    params = ['Collector', 'Air Rate', 'Frother', 'pH', 'Luproset', 'Manganese']
    values = [collector/150*100, air_rate, frother, (ph-8.5)/(12-8.5)*100, luproset, mn_grade*100]
    
    fig2 = go.Figure()
    
    fig2.add_trace(go.Scatterpolar(
        r=values,
        theta=params,
        fill='toself',
        name='Current Settings'
    ))
    
    fig2.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )),
        title="Parameter Settings Radar"
    )
    
    st.plotly_chart(fig2, use_container_width=True)

# Real-time trends (simulated)
if 'history' not in st.session_state:
    st.session_state.history = []

# Only add to history when parameters change (to avoid constant updates)
current_params = (collector, air_rate, frother, ph, luproset, mn_grade)
if 'last_params' not in st.session_state or st.session_state.last_params != current_params:
    st.session_state.history.append({
        'time': len(st.session_state.history),
        'recovery': recovery,
        'grade': grade,
        'carbon': carbon
    })
    st.session_state.last_params = current_params

# Keep only last 50 points
if len(st.session_state.history) > 50:
    st.session_state.history = st.session_state.history[-50:]

# Trends plot
if len(st.session_state.history) > 1:
    df_history = pd.DataFrame(st.session_state.history)
    
    fig3 = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Recovery Trend', 'Grade Trend', 'Carbon Trend', 'Grade vs Recovery'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # Recovery trend
    fig3.add_trace(
        go.Scatter(x=df_history['time'], y=df_history['recovery'], 
                  name='Recovery', line=dict(color='blue')),
        row=1, col=1
    )
    
    # Grade trend
    fig3.add_trace(
        go.Scatter(x=df_history['time'], y=df_history['grade'], 
                  name='Grade', line=dict(color='red')),
        row=1, col=2
    )
    
    # Carbon trend
    fig3.add_trace(
        go.Scatter(x=df_history['time'], y=df_history['carbon'], 
                  name='Carbon', line=dict(color='brown')),
        row=2, col=1
    )
    
    # Grade vs Recovery scatter
    fig3.add_trace(
        go.Scatter(x=df_history['recovery'], y=df_history['grade'], 
                  mode='markers+lines', name='Operating Path', 
                  line=dict(color='purple')),
        row=2, col=2
    )
    
    fig3.update_layout(height=500, title_text="Process Trends")
    st.plotly_chart(fig3, use_container_width=True)

# Operating guidance
st.subheader("Operating Guidance")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Optimal Ranges:**")
    st.markdown(f"- Collector: 70-80 g/t {'✅' if 70 <= collector <= 80 else '❌'}")
    st.markdown(f"- Air Rate: 20-30 L/min {'✅' if 20 <= air_rate <= 30 else '❌'}")
    st.markdown(f"- Frother: 35-45 g/t {'✅' if 35 <= frother <= 45 else '❌'}")
    st.markdown(f"- pH: 9.5-10.0 {'✅' if 9.5 <= ph <= 10.0 else '❌'}")

with col2:
    if recovery > 90 and grade > 50:
        st.success("🎯 Excellent performance! All targets met.")
    elif recovery > 85 and grade > 45:
        st.warning("⚠️ Good performance. Minor optimization possible.")
    else:
        st.error("🔴 Performance below target. Check parameter settings.")

# Reset button
if st.button("Reset Trends"):
    st.session_state.history = []
    st.rerun()

# Optional: Auto-refresh every 5 seconds (remove if not needed)
# time.sleep(0.1)