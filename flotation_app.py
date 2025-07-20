import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import time
import random

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
    50: {"recovery": 88.0, "grade": 46.0},
    75: {"recovery": 90.0, "grade": 31.0},
    100: {"recovery": 40.0, "grade": 16.0}
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
    9.0: {"recovery_multiplier": 1.0, "grade_bonus": 3.9},
    9.5: {"recovery_multiplier": 1.0, "grade_bonus": 4.5},
    10.0: {"recovery_multiplier": 0.98, "grade_bonus": 5.0},
    10.5: {"recovery_multiplier": 0.95, "grade_bonus": 5.5},
    11.0: {"recovery_multiplier": 0.90, "grade_bonus": 7.5},
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

def calculate_performance(collector, air_rate, frother, ph, luproset, mn_grade, zn_feed_grade):
    """Calculate flotation performance from parameters"""
    
    # Get individual effects
    collector_metrics = interpolate_lookup(collector, COLLECTOR_LOOKUP)
    air_metrics = interpolate_lookup(air_rate, AIR_RATE_LOOKUP)
    frother_metrics = interpolate_lookup(frother, FROTHER_LOOKUP)
    ph_metrics = interpolate_lookup(ph, PH_LOOKUP)
    
    # NEW: Calculate grade recovery factor based on Zn feed grade
    # Higher feed grades have better recovery potential
    # Scale from 0.6 (at 2% Zn) to 1.0 (at 15% Zn)
    grade_recovery_factor = 0.7 + ((zn_feed_grade - 2.0) / (15.0 - 2.0)) * 0.4
    
    # Weighted combination with feed grade factor
    base_recovery = (collector_metrics["recovery"] * 0.40 + 
                    air_metrics["recovery"] * 0.25 + 
                    frother_metrics["recovery"] * 0.15 +
                    88.0 * 0.25) * grade_recovery_factor
    
    # Apply pH multiplier
    recovery = base_recovery * ph_metrics["recovery_multiplier"]
    
    # Luproset reduces recovery slightly
    recovery -= luproset * 0.015
    
    # Grade calculation - higher feed grades can achieve slightly higher concentrate grades
    feed_grade_bonus = (zn_feed_grade - 8.0) * 0.3  # Bonus/penalty from 8% baseline
    
    base_grade = (collector_metrics["grade"] * 0.45 + 
                 air_metrics["grade"] * 0.30 + 
                 frother_metrics["grade"] * 0.15 +
                 50.0 * 0.10)
    
    grade = base_grade + ph_metrics["grade_bonus"] - (mn_grade*3) + feed_grade_bonus
    
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

st.title("🏭 Zinc Froth Flotation Simulator")

# Initialize session state for all parameters if not exists
if 'zn_feed_grade' not in st.session_state:
    st.session_state.zn_feed_grade = 8.0
if 'mn_grade' not in st.session_state:
    st.session_state.mn_grade = 0.8
if 'collector' not in st.session_state:
    st.session_state.collector = 0
if 'air_rate' not in st.session_state:
    st.session_state.air_rate = 0
if 'frother' not in st.session_state:
    st.session_state.frother = 0
if 'ph' not in st.session_state:
    st.session_state.ph = 8.5
if 'luproset' not in st.session_state:
    st.session_state.luproset = 0

# Sidebar controls
st.sidebar.header("Feed Characteristics")

# New scenario button
if st.sidebar.button("🎲 New Scenario", help="Generate new random operating conditions", type="primary"):
    # Randomize feed characteristics
    st.session_state.zn_feed_grade = round(random.uniform(8.0, 13.0), 1)
    st.session_state.mn_grade = round(random.uniform(0.2, 1.0), 1)
    
    # Randomize flotation parameters to realistic starting values
    st.session_state.collector = random.randint(20, 80)  # Typical range
    st.session_state.air_rate = random.randint(30, 70)   # Typical range
    st.session_state.frother = random.randint(15, 60)    # Typical range
    st.session_state.ph = round(random.uniform(9.0, 10.5), 1)  # Typical range
    st.session_state.luproset = random.randint(0, 40)    # Lower typical range
    
    st.rerun()


mn_grade = st.sidebar.slider(
    "Feed Mn Grade (%)",
    min_value=0.1, max_value=1.0, value=st.session_state.mn_grade, step=0.1,
    help="Manganese content in feed ore"
)

st.sidebar.header("Flotation Parameters")

collector = st.sidebar.slider(
    "Collector Dosage (g/t)",
    min_value=0, max_value=150, value=st.session_state.collector, step=5,
    help="Primary reagent for mineral hydrophobicity"
)

air_rate = st.sidebar.slider(
    "Air Rate (L/min)",
    min_value=0, max_value=100, value=st.session_state.air_rate, step=5,
    help="Bubble generation rate - bell curve optimization"
)

frother = st.sidebar.slider(
    "Frother Dosage (g/t)",
    min_value=0, max_value=100, value=st.session_state.frother, step=5,
    help="Bubble stability and size control"
)

ph = st.sidebar.slider(
    "pH",
    min_value=8.5, max_value=12.0, value=st.session_state.ph, step=0.1,
    help="Pulp pH - affects mineral surface chemistry"
)

luproset = st.sidebar.slider(
    "Luproset Dosage (g/t)",
    min_value=0, max_value=100, value=st.session_state.luproset, step=5,
    help="Carbon depressant - reduces carbon content"
)

# Calculate current performance using session state feed grade
recovery, grade, carbon = calculate_performance(
    collector, air_rate, frother, ph, luproset, mn_grade, st.session_state.zn_feed_grade
)

# Main dashboard
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Feed Zn Grade", 
        f"{st.session_state.zn_feed_grade:.1f}%",
        delta=None
    )

with col2:
    st.metric(
        "Zinc Recovery", 
        f"{recovery:.1f}%",
        delta=f"{recovery - 88:.1f}%" if recovery != 88 else None
    )

with col3:
    st.metric(
        "Zinc Grade", 
        f"{grade:.1f}%",
        delta=f"{grade - 50:.1f}%" if grade != 50 else None
    )

with col4:
    st.metric(
        "Carbon Content", 
        f"{carbon:.2f}%",
        delta=f"{carbon - 0.8:.2f}%" if carbon != 0.8 else None,
        delta_color="inverse"
    )

with col5:
    st.metric(
        "Feed Manganese", 
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
        name=f'Current Operation (Feed: {st.session_state.zn_feed_grade}% Zn)',
        hovertemplate='Recovery: %{x:.1f}%<br>Grade: %{y:.1f}%<extra></extra>'
    )
    
    # Add target zone
    fig1.add_shape(
        type="rect",
        x0=80, y0=45, x1=95, y1=55,
        fillcolor="lightgreen", opacity=0.3,
        line=dict(color="green", width=2)
    )
    
    # Add text annotation for target zone
    fig1.add_annotation(
        x=87.5, y=50,
        text="Target Zone",
        showarrow=False,
        font=dict(color="green", size=12)
    )
    
    fig1.update_layout(
        title="Grade-Recovery Performance",
        xaxis_title="Zinc Recovery (%)",
        yaxis_title="Zinc Grade (%)",
        showlegend=True,
        xaxis=dict(range=[0, 100]),
        yaxis=dict(range=[20, 65])
    )
    
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    # Parameter effects radar chart
    params = ['Collector', 'Air Rate', 'Frother', 'pH', 'Luproset', 'Feed Zn Grade']
    values = [
        collector/150*100, 
        air_rate, 
        frother, 
        (ph-8.5)/(12-8.5)*100, 
        luproset,
        (st.session_state.zn_feed_grade-2.0)/(15.0-2.0)*100
    ]
    
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

# Reset button
if st.button("Reset All Parameters"):
    # Force page reload to reset all sliders
    st.rerun()