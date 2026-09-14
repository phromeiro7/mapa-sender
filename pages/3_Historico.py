import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
import streamlit as st
from db import get_senders, get_history_df, QUALIDADE_COLORS
from alerts import render_sidebar_alerts

st.set_page_config(page_title="Mapa Sender", page_icon="📶", layout="wide")
render_sidebar_alerts()
st.title("🗄️ Histórico")
st.caption("Log completo de lançamentos diários, com filtro por sender e período.")

senders_df = get_senders(active_only=False)

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    opcoes_sender = ["Todos"] + [
        f"{r['numero']} — {r['parceiro_segmento'] or r['setor'] or '—'}" for _, r in senders_df.iterrows()
    ]
    sel_sender = c1.selectbox("Sender", opcoes_sender)
    data_inicio = c2.date_input("De", value=None, format="DD/MM/YYYY")
    data_fim = c3.date_input("Até", value=None, format="DD/MM/YYYY")

sender_id = None
if sel_sender != "Todos":
    idx = opcoes_sender.index(sel_sender) - 1
    sender_id = int(senders_df.iloc[idx]["id"])

df = get_history_df(
    sender_id=sender_id,
    data_inicio=data_inicio.isoformat() if isinstance(data_inicio, datetime.date) else None,
    data_fim=data_fim.isoformat() if isinstance(data_fim, datetime.date) else None,
)

st.write(f"{len(df)} registros encontrados.")

df = df.drop(columns=["parceiro_segmento"]).rename(columns={"setor": "Tipo"})


def style_qualidade(val):
    color = QUALIDADE_COLORS.get(val)
    return f"color: {color}; font-weight: 600;" if color else ""


styled = df.style.map(style_qualidade)
st.dataframe(styled, width="stretch", hide_index=True)

st.download_button(
    "⬇️ Exportar CSV",
    df.to_csv(index=False).encode("utf-8-sig"),
    file_name="historico_sender.csv",
    mime="text/csv",
)
