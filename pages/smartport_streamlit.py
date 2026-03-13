import streamlit as st
import pandas as pd
import plotly.express as px

from db.supabase_client import get_smartport_batches


st.set_page_config(
    page_title="SmartPort | Maritime Risk Monitor",
    page_icon="🚢",
    layout="wide"
)

st.title("🚢 SmartPort — Maritime Risk Monitoring")
st.caption("Operational dashboard for vessel risk batches stored in Supabase.")


@st.cache_data(ttl=60)
def load_data():
    df = get_smartport_batches()
    if df is None:
        return pd.DataFrame()
    if not df.empty:
        if "risk_score" in df.columns:
            df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")
        if "financial_impact" in df.columns:
            df["financial_impact"] = pd.to_numeric(df["financial_impact"], errors="coerce")
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
This dashboard displays stored SmartPort prediction batches.

**What you are seeing**
- Each upload creates a new `batch_id`
- Manual uploads and automatic demo runs can coexist
- Historical batches remain available until cleaned
"""
)

st.markdown("---")

if df.empty:
    st.warning("No SmartPort prediction batches found.")
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
avg_risk = float(batch_df["risk_score"].mean()) if "risk_score" in batch_df.columns else 0.0
total_exposure = float(batch_df["financial_impact"].sum()) if "financial_impact" in batch_df.columns else 0.0
critical_count = int((batch_df["risk_level"] == "CRITICAL").sum()) if "risk_level" in batch_df.columns else 0

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric("Batch Records", total_records)

with m2:
    st.metric("Average Risk Score", f"{avg_risk:.3f}")

with m3:
    st.metric("Critical Events", critical_count)

with m4:
    st.metric("Financial Exposure", f"${total_exposure:,.0f}")

st.markdown("---")

left, right = st.columns([1.5, 1])

with left:
    if {"vessel_id", "financial_impact", "risk_level"}.issubset(batch_df.columns):
        top_df = (
            batch_df
            .sort_values("financial_impact", ascending=False)
            .head(20)
        )

        fig = px.bar(
            top_df,
            x="vessel_id",
            y="financial_impact",
            color="risk_level",
            title="Top Vessels by Estimated Financial Exposure"
        )
        st.plotly_chart(fig, use_container_width=True)

    elif {"financial_impact", "risk_level"}.issubset(batch_df.columns):
        top_df = (
            batch_df
            .sort_values("financial_impact", ascending=False)
            .head(20)
            .reset_index(drop=True)
        )
        top_df["record"] = top_df.index.astype(str)

        fig = px.bar(
            top_df,
            x="record",
            y="financial_impact",
            color="risk_level",
            title="Top Records by Estimated Financial Exposure"
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    if "risk_level" in batch_df.columns:
        risk_dist = batch_df["risk_level"].value_counts().reset_index()
        risk_dist.columns = ["risk_level", "count"]

        fig2 = px.pie(
            risk_dist,
            names="risk_level",
            values="count",
            title="Risk Distribution"
        )
        st.plotly_chart(fig2, use_container_width=True)

st.subheader("Batch Records")

preferred_cols = [
    "vessel_id",
    "risk_score",
    "risk_level",
    "financial_impact",
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
- **Risk Score** estimates the probability or intensity of operational risk.
- **Risk Level** groups predictions into easier business categories.
- **Financial Exposure** approximates the potential economic impact.
- Use the batch selector to compare historical runs without mixing datasets.
"""
    )

st.caption(f"Showing batch_id: {selected_batch}")