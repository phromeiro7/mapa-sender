import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
import streamlit as st
from db import (
    add_recarga,
    confirmar_recarga_hoje,
    CICLO_RECARGA_DIAS,
    get_ultima_recarga,
    get_recargas_historico,
    get_senders,
    get_senders_export_recarga,
)
from alerts import render_sidebar_alerts

st.set_page_config(page_title="Mapa Sender", page_icon="📶", layout="wide")
render_sidebar_alerts()
st.title("🔋 Recargas dos Senders")
st.caption("Controle de quando a recarga (SIM/chip) foi feita e quando precisa ser feita de novo.")

ultima = get_ultima_recarga()

with st.container(border=True):
    if ultima is None:
        st.warning("Nenhuma recarga registrada ainda. Registre a primeira abaixo.")
    else:
        data_recarga, proxima_recarga, observacao = ultima
        dias = (datetime.date.fromisoformat(proxima_recarga) - datetime.date.today()).days

        c1, c2, c3 = st.columns(3)
        c1.metric("Última recarga", datetime.date.fromisoformat(data_recarga).strftime("%d/%m/%Y"))
        c2.metric("Próxima recarga", datetime.date.fromisoformat(proxima_recarga).strftime("%d/%m/%Y"))
        c3.metric("Dias restantes", dias, delta=None)

        if dias < 0:
            st.error(f"🔴 **RECARGA VENCIDA** há {abs(dias)} dia(s).")
        elif dias <= 3:
            st.warning(f"🟡 **Recarga vence em breve** — faltam {dias} dia(s).")
        else:
            st.success("🟢 Tudo certo.")
        if observacao:
            st.caption(observacao)

    if st.button(f"✅ Confirmar recarga feita hoje (agenda a próxima em {CICLO_RECARGA_DIAS} dias)", type="primary"):
        confirmar_recarga_hoje()
        st.success("Recarga confirmada.")
        st.rerun()

st.divider()

st.subheader("➕ Registrar recarga")
with st.container(border=True):
    with st.form("form_recarga", clear_on_submit=True):
        c1, c2 = st.columns(2)
        data_recarga_in = c1.date_input("Data da recarga", value=datetime.date.today(), format="DD/MM/YYYY")
        proxima_recarga_in = c2.date_input(
            "Próxima recarga (data de vencimento) *",
            value=datetime.date.today() + datetime.timedelta(days=CICLO_RECARGA_DIAS),
            format="DD/MM/YYYY",
        )
        observacao_in = st.text_input("Observação (opcional)", placeholder="Ex: recarga feita via portal da operadora")

        submitted = st.form_submit_button("Registrar recarga", type="primary")
        if submitted:
            add_recarga(data_recarga_in.isoformat(), proxima_recarga_in.isoformat(), observacao_in.strip() or None)
            st.success("Recarga registrada.")
            st.rerun()

st.divider()

st.subheader("📜 Histórico de recargas")
historico_df = get_recargas_historico()
st.dataframe(historico_df, width="stretch", hide_index=True)

st.divider()

st.subheader("⬇️ Exportar senders para recarga")
senders_df = get_senders(active_only=True)
senders_com_chip = senders_df[senders_df["possui_chip"] == 1]
sem_chip = len(senders_df) - len(senders_com_chip)

with st.container(border=True):
    st.caption("Gera um CSV com telefone e operadora dos senders que possuem chip, para usar na recarga.")
    st.metric("Senders com chip prontos para recarga", len(senders_com_chip))
    if sem_chip:
        st.caption(f"({sem_chip} sender(s) sem chip foram excluídos desta lista.)")

    export_df = get_senders_export_recarga()
    st.download_button(
        "⬇️ Exportar CSV",
        export_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"senders_recarga_{datetime.date.today().isoformat()}.csv",
        mime="text/csv",
    )
