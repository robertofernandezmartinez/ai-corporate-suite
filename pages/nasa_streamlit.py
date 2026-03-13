import streamlit as st
import pandas as pd
import plotly.express as px

from db.supabase_client import get_nasa_batches


st.set_page_config(
    page_title="NASA RUL | Predictive Maintenance",
    page_icon="🛠️",
    layout="wide"
)

st.title("🛠️ NASA RUL — Predictive Maintenance Monitoring")
st.caption("Operational dashboard for stored Remaining Useful Life prediction batches.")


@st.cache_data(ttl=60)
def load_data():
    df = get_nasa_batches()
    if df is None:
        return pd.DataFrame()
    if not df.empty:
        if "predicted_rul" in df.columns:
            df["predicted_rul"] = pd.to_numeric(df["predicted_rul"], errors="coerce")
        if "time_in_cycles" in df.columns:
            df["time_in_cycles"] = pd.to_numeric(df["time_in_cycles"], errors="coerce")
        if "unit_id" in df.columns:
            df["unit_id"] = pd.to_numeric(df["unit_id"], errors="coerce")
    return df


def get_batch_list(df: pd.DataFrame):
    if df.empty or "batch_id" not in df.columns:
        return []
    tmp = df[["batch_id", "created_at"]].drop_duplicates()
    if "created_at" in tmp.columns:
        tmp = tmp.sort_values("created_at", ascending=False)
    return tmp["batch_id"].tolist()


df = load_data()

st.markdown(
    """
This dashboard displays stored NASA predictive maintenance batches.

**What you are seeing**
- Each upload creates a new `batch_id`
- Manual uploads and automatic demo runs can coexist
- Historical batches remain available until cleaned
- The main prediction is **Remaining Useful Life (RUL)**
"""
)

st.markdown("---")

if df.empty:
    st.warning("No NASA prediction batches found.")
    st.stop()

available_batches = get_batch_list(df)

selected_batch = st.selectbox(
    "Select Batch",
    available_batches,
    index=0 if available_batches else None
)

if not selected_batch:
    st.info("No batch available.")
    st.stop()

batch_df = df[df["batch_id"] == selected_batch].copy()

if batch_df.empty:
    st.info("Selected batch returned no records.")
    st.stop()

total_records = len(batch_df)
engine_count = int(batch_df["unit_id"].nunique()) if "unit_id" in batch_df.columns else 0
avg_rul = float(batch_df["predicted_rul"].mean()) if "predicted_rul" in batch_df.columns else 0.0
min_rul = float(batch_df["predicted_rul"].min()) if "predicted_rul" in batch_df.columns else 0.0

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric("Batch Records", total_records)

with m2:
    st.metric("Engine Units", engine_count)

with m3:
    st.metric("Average Predicted RUL", f"{avg_rul:.1f}")

with m4:
    st.metric("Minimum Predicted RUL", f"{min_rul:.1f}")

st.markdown("---")

left, right = st.columns([1.5, 1])

with left:
    if {"unit_id", "predicted_rul"}.issubset(batch_df.columns):
        engine_summary = (
            batch_df.groupby("unit_id", as_index=False)["predicted_rul"]
            .mean()
            .sort_values("predicted_rul", ascending=True)
            .head(20)
        )

        fig = px.bar(
            engine_summary,
            x="unit_id",
            y="predicted_rul",
            title="Lowest Average Predicted RUL by Engine Unit"
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    if "predicted_rul" in batch_df.columns:
        fig2 = px.histogram(
            batch_df,
            x="predicted_rul",
            nbins=30,
            title="Predicted RUL Distribution"
        )
        st.plotly_chart(fig2, use_container_width=True)

if {"unit_id", "time_in_cycles", "predicted_rul"}.issubset(batch_df.columns):
    st.subheader("Engine Degradation View")

    unit_options = sorted(batch_df["unit_id"].dropna().unique())
    selected_unit = st.selectbox("Select Engine Unit", unit_options)

    unit_df = batch_df[batch_df["unit_id"] == selected_unit].copy()
    unit_df = unit_df.sort_values("time_in_cycles")

    fig3 = px.line(
        unit_df,
        x="time_in_cycles",
        y="predicted_rul",
        markers=True,
        title=f"Predicted RUL over Time — Unit {int(selected_unit)}"
    )
    st.plotly_chart(fig3, use_container_width=True)

st.subheader("Batch Records")

preferred_cols = [
    "unit_id",
    "time_in_cycles",
    "predicted_rul",
    "created_at",
]

visible_cols = [c for c in preferred_cols if c in batch_df.columns]
if visible_cols:
    st.dataframe(
        batch_df[visible_cols].head(200),
        use_container_width=True,
        hide_index=True
    )
else:
    st.dataframe(
        batch_df.head(200),
        use_container_width=True,
        hide_index=True
    )

with st.expander("Batch Interpretation"):
    st.markdown(
        """
- **Predicted RUL** estimates how many cycles remain before the engine approaches failure.
- Lower values indicate engines that may require earlier inspection or maintenance.
- Use the engine view to observe how predicted RUL evolves across operating cycles.
- Use the batch selector to compare historical uploads without mixing datasets.
"""
    )

st.caption(f"Showing batch_id: {selected_batch}")