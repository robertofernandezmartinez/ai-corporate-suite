import streamlit as st
import pandas as pd
import plotly.express as px

from db.supabase_client import get_nasa_batches


st.set_page_config(page_title="NASA RUL Dashboard", layout="wide")

st.title("NASA Predictive Maintenance Dashboard")
st.caption("Remaining Useful Life predictions stored in Supabase")


@st.cache_data(ttl=60)
def load_data():
    df = get_nasa_batches()
    if df is None:
        return pd.DataFrame()
    return df


df = load_data()

if df.empty:
    st.warning("No NASA prediction batches found.")
    st.stop()

st.subheader("Latest Predictions")
st.dataframe(df, use_container_width=True)

col1, col2 = st.columns(2)

with col1:
    st.metric("Total Predictions", len(df))

with col2:
    if "batch_id" in df.columns:
        st.metric("Total Batches", df["batch_id"].nunique())
    else:
        st.metric("Total Batches", 0)

if "predicted_rul" in df.columns:
    st.subheader("Predicted RUL Distribution")
    fig = px.histogram(df, x="predicted_rul", nbins=30)
    st.plotly_chart(fig, use_container_width=True)

if {"unit_id", "time_in_cycles", "predicted_rul"}.issubset(df.columns):

    st.subheader("Engine Degradation View")

    selected_unit = st.selectbox(
        "Select Engine Unit",
        sorted(df["unit_id"].dropna().unique())
    )

    unit_df = df[df["unit_id"] == selected_unit].copy()
    unit_df = unit_df.sort_values("time_in_cycles")

    fig2 = px.line(
        unit_df,
        x="time_in_cycles",
        y="predicted_rul",
        markers=True
    )

    st.plotly_chart(fig2, use_container_width=True)