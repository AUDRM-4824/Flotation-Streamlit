import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import time
import random
import base64

# Your existing lookup tables (abbreviated for demo)
COLLECTOR_LOOKUP = {
    200: {"recovery": 15.0, "grade": 55.0},
    400: {"recovery": 46.0, "grade": 52.5},
    650: {"recovery": 70.0, "grade": 50.0},
    900: {"recovery": 85.0, "grade": 47.5},
    1100: {"recovery": 93.0, "grade": 45.0},
    1500: {"recovery": 97.2, "grade": 40.0}
}

AIR_RATE_LOOKUP = {
    500: {"recovery": 30.0, "grade": 58.0},
    1500: {"recovery": 92.0, "grade": 22.0}
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

def calculate_targets(mn_grade):
    """Calculate target grade and recovery based on feed Mn grade.
    Best achievable grade uses the same Mn penalty as the main model.
    Recovery target is fixed at 80% of the practical maximum."""
    best_possible_grade = min(65, 60.0 - (mn_grade * 3))
    target_grade = best_possible_grade * 0.80
    target_recovery = 76.0  # 80% of ~95% practical max
    return target_recovery, target_grade

# Streamlit App
st.set_page_config(
    page_title="Zinc Flotation Simulator",
    page_icon="🏭",
    layout="wide"
)

def set_background(image_path):
    with open(image_path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode()
    st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{img_data}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        </style>
    """, unsafe_allow_html=True)

set_background("assets/background.jpg")

st.markdown("<h1 style='text-align: center;'>DRM Zinc Flotation</h1>", unsafe_allow_html=True)

# Initialize session state for all parameters if not exists
if 'zn_feed_grade' not in st.session_state:
    st.session_state.zn_feed_grade = 8.0
if 'mn_grade' not in st.session_state:
    st.session_state.mn_grade = 0.8
if 'collector' not in st.session_state:
    st.session_state.collector = 200
if 'air_rate' not in st.session_state:
    st.session_state.air_rate = 500
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
    
    # Reset control variables to minimum so operator must dial in from scratch
    st.session_state.collector = 200
    st.session_state.air_rate = 500
    st.session_state.frother = 0
    st.session_state.ph = 8.5
    st.session_state.luproset = 0
    
    st.rerun()


mn_grade = st.sidebar.number_input(
    "Feed Mn Grade (%)  [0.1 – 1.0]",
    min_value=0.1, max_value=1.0, step=0.1, format="%.1f", key='mn_grade'
)

st.sidebar.header("Flotation Parameters")

collector = st.sidebar.number_input(
    "Collector Dosage (ml/min)  [200 – 1500]",
    min_value=200, max_value=1500, step=25, key='collector'
)

air_rate = st.sidebar.number_input(
    "Air Rate (m³/hr)  [500 – 1500]",
    min_value=500, max_value=1500, step=25, key='air_rate'
)

frother = st.sidebar.number_input(
    "Frother Dosage (ml/min)  [0 – 100]",
    min_value=0, max_value=100, step=5, key='frother'
)

ph = st.sidebar.number_input(
    "pH  [8.5 – 12.0]",
    min_value=8.5, max_value=12.0, step=0.1, format="%.1f", key='ph'
)

luproset = st.sidebar.number_input(
    "Luproset Dosage (g/t)  [0 – 100]",
    min_value=0, max_value=100, step=5, key='luproset'
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
        f"{recovery:.1f}%"
    )

with col3:
    st.metric(
        "Zinc Grade",
        f"{grade:.1f}%"
    )

with col4:
    st.metric(
        "Carbon Content",
        f"{carbon:.2f}%"
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
    # Calculate dynamic target based on feed Mn grade
    target_recovery, target_grade = calculate_targets(mn_grade)

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

    # Shade the acceptable operating zone (recovery >= target AND grade >= target)
    fig1.add_shape(
        type="rect",
        x0=target_recovery, y0=target_grade,
        x1=100, y1=65,
        fillcolor="lightgreen", opacity=0.25,
        line=dict(width=0)
    )
    # Border lines along the two threshold edges
    fig1.add_shape(type="line", x0=target_recovery, y0=target_grade, x1=target_recovery, y1=65,
                   line=dict(color="green", width=1.5, dash="dash"))
    fig1.add_shape(type="line", x0=target_recovery, y0=target_grade, x1=100, y1=target_grade,
                   line=dict(color="green", width=1.5, dash="dash"))

    # Label the zone boundary
    fig1.add_annotation(
        x=target_recovery + 1, y=64,
        text=f"<b>Target zone<br>R≥{target_recovery:.0f}% | G≥{target_grade:.0f}%</b>",
        showarrow=False, xanchor="left",
        font=dict(color="darkgreen", size=13),
        bgcolor="white", bordercolor="green", borderwidth=1, opacity=0.85
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
        (collector - 200) / (1500 - 200) * 100,
        (air_rate - 500) / (1500 - 500) * 100,
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