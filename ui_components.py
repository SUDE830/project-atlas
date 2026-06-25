from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import streamlit as st


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --atlas-navy: #0f172a;
            --atlas-blue: #2563eb;
            --atlas-green: #16a34a;
            --atlas-yellow: #d97706;
            --atlas-red: #dc2626;
            --atlas-muted: #64748b;
        }
        .stApp { background: #f8fafc; }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #172554 100%);
        }
        [data-testid="stSidebar"] * { color: #f8fafc; }
        [data-testid="stSidebar"] .stRadio label {
            padding: .32rem .35rem;
            border-radius: .5rem;
        }
        .atlas-hero {
            padding: 1.25rem 1.4rem;
            border-radius: 18px;
            color: white;
            background: linear-gradient(135deg, #172554 0%, #2563eb 100%);
            box-shadow: 0 16px 40px rgba(37, 99, 235, .16);
            margin-bottom: 1rem;
        }
        .atlas-hero h1 { margin: 0; font-size: clamp(1.7rem, 5vw, 2.5rem); }
        .atlas-hero p { margin: .35rem 0 0; opacity: .86; }
        .atlas-card {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 1rem;
            min-height: 112px;
            box-shadow: 0 5px 18px rgba(15, 23, 42, .05);
            margin-bottom: .75rem;
        }
        .atlas-card.good { border-top: 4px solid var(--atlas-green); }
        .atlas-card.warning { border-top: 4px solid var(--atlas-yellow); }
        .atlas-card.risk { border-top: 4px solid var(--atlas-red); }
        .atlas-label { color: var(--atlas-muted); font-size: .83rem; font-weight: 650; }
        .atlas-value { color: var(--atlas-navy); font-size: 1.55rem; font-weight: 750; margin-top: .38rem; }
        .atlas-note { color: var(--atlas-muted); font-size: .78rem; margin-top: .22rem; }
        .atlas-alert {
            border-radius: 14px;
            padding: .9rem 1rem;
            margin: .5rem 0 1rem;
            font-weight: 650;
        }
        .atlas-alert.good { background: #dcfce7; color: #166534; }
        .atlas-alert.warning { background: #fef3c7; color: #92400e; }
        .atlas-alert.risk { background: #fee2e2; color: #991b1b; }
        .block-container { padding-top: 1.35rem; max-width: 1180px; }
        @media (max-width: 640px) {
            .block-container { padding: 1rem .75rem; }
            .atlas-card { min-height: 96px; }
            .atlas-value { font-size: 1.3rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_try(amount: float) -> str:
    value = f"{float(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{value} TL"


def format_usd(amount: float) -> str:
    return f"${float(amount):,.2f}"


def page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="atlas-hero">
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, note: str = "", status: str = "good") -> None:
    safe_status = status if status in {"good", "warning", "risk"} else "good"
    st.markdown(
        f"""
        <div class="atlas-card {safe_status}">
            <div class="atlas-label">{html.escape(label)}</div>
            <div class="atlas-value">{html.escape(value)}</div>
            <div class="atlas-note">{html.escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def alert(message: str, status: str = "warning") -> None:
    safe_status = status if status in {"good", "warning", "risk"} else "warning"
    st.markdown(
        f'<div class="atlas-alert {safe_status}">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


def empty_state(message: str) -> None:
    st.info(message)


def monthly_bar_chart(frame: pd.DataFrame, x: str, y: str, title: str, color: str):
    if frame.empty:
        return None
    fig = px.bar(frame, x=x, y=y, title=title, text_auto=".2s")
    fig.update_traces(marker_color=color, hovertemplate="%{x}<br>%{y:,.2f} TL<extra></extra>")
    fig.update_layout(
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Tutar (TL)",
        xaxis_title="Ay",
    )
    return fig


def line_chart(frame: pd.DataFrame, x: str, y: str, title: str, color: str):
    if frame.empty:
        return None
    fig = px.line(frame, x=x, y=y, title=title, markers=True)
    fig.update_traces(line_color=color, hovertemplate="%{x}<br>%{y:,.2f} TL<extra></extra>")
    fig.update_layout(
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Tutar (TL)",
        xaxis_title="Dönem",
    )
    return fig

