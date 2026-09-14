import html
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
import streamlit as st
from db import (
    get_senders,
    upsert_snapshot,
    get_quality_changes,
    QUALIDADE_OPTIONS,
    STATUS_OPTIONS,
    QUALIDADE_COLORS,
    STATUS_COLORS,
)
from alerts import render_sidebar_alerts
from styles import inject_base_styles
from slack_alert import enviar_mudancas_qualidade_slack

st.set_page_config(page_title="Mapa Sender", page_icon="📶", layout="wide")
inject_base_styles()
render_sidebar_alerts()
st.title("📝 Lançamento Diário")
st.caption(
    "Todo sender já começa marcado como Alta/Conectado — confira no site da Meta e altere "
    "só os que estiverem diferentes disso hoje."
)

senders_df = get_senders(active_only=True)
if senders_df.empty:
    st.info("Cadastre ao menos um sender antes de lançar dados diários (página Painel).")
    st.stop()

CARD_CSS = """
<style>
.lanc-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}
.lanc-card-number {
    font-weight: 600;
    color: #e6edf3;
}
.lanc-card-sub {
    font-size: 0.8rem;
    color: #8b949e;
    margin-bottom: 8px;
}
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

with st.container(border=True):
    data_sel = st.date_input("Data do lançamento", value=datetime.date.today(), format="DD/MM/YYYY")

    busca = st.text_input("🔍 Buscar sender", placeholder="Número ou tipo...")

    wabas = sorted(senders_df["waba"].dropna().unique())
    st.caption("Filtrar por WABA")
    if wabas:
        f_waba = st.pills("WABA", wabas, selection_mode="multi", default=wabas, label_visibility="collapsed")
    else:
        f_waba = []
        st.caption("Nenhum WABA cadastrado ainda.")

    setores = sorted(senders_df["setor"].dropna().unique())
    f_setor = st.multiselect("Tipo (opcional)", setores)

data_iso = data_sel.isoformat()

senders_sel = senders_df.copy()
if busca:
    termo = busca.strip().lower()
    mask = (
        senders_sel["numero"].astype(str).str.lower().str.contains(termo, na=False)
        | senders_sel["setor"].astype(str).str.lower().str.contains(termo, na=False)
    )
    senders_sel = senders_sel[mask]
if f_waba:
    senders_sel = senders_sel[senders_sel["waba"].isin(f_waba)]
if f_setor:
    senders_sel = senders_sel[senders_sel["setor"].isin(f_setor)]

st.caption(f"{len(senders_sel)} sender(s) nesta seleção · lançamento de {data_sel.strftime('%d/%m/%Y')}")

# Guarda as edições num dicionário próprio (não só no key do widget): o Streamlit "esquece"
# o valor de um selectbox quando o card sai da tela (filtrado pela busca/WABA) e reaparece
# depois, voltando pro padrão. Gravando aqui a cada render, a edição sobrevive mesmo que o
# sender suma e volte a aparecer por causa de outra busca.
pendentes = st.session_state.setdefault("lancamento_pendente", {})

if st.button("💾 Salvar lançamento do dia", type="primary"):
    salvos = 0
    for (sender_id, d_iso), valores in pendentes.items():
        if d_iso == data_iso:
            upsert_snapshot(sender_id, d_iso, valores["qualidade"], valores["status"])
            salvos += 1
    st.success(f"Lançamento de {data_sel.strftime('%d/%m/%Y')} salvo para {salvos} senders.")

    changes_df = get_quality_changes()
    changes_df = changes_df[changes_df["data_atual"] == data_iso]
    resultado_slack = enviar_mudancas_qualidade_slack(changes_df, data_sel.strftime("%d/%m/%Y"))
    if resultado_slack["status"] == "enviado":
        st.info(f"📨 {resultado_slack['quantidade']} mudança(s) de qualidade enviada(s) pro Slack.")
    elif resultado_slack["status"] == "erro":
        st.warning(f"⚠️ Falha ao enviar mudanças de qualidade pro Slack: {resultado_slack['detalhe']}")

legenda_html = " &nbsp;&nbsp; ".join(
    f'<span class="badge" style="--dot-color:{color}">{label}</span>'
    for label, color in QUALIDADE_COLORS.items()
)
st.markdown(f"Legenda: {legenda_html}", unsafe_allow_html=True)

st.divider()

if senders_sel.empty:
    st.info("Nenhum sender para os filtros/busca selecionados.")
else:
    N_COLS = 3
    linhas = list(senders_sel.sort_values(["setor", "parceiro_segmento"]).iterrows())
    for inicio in range(0, len(linhas), N_COLS):
        cols = st.columns(N_COLS)
        for col, (_, s) in zip(cols, linhas[inicio:inicio + N_COLS]):
            sender_id = int(s["id"])
            with col:
                with st.container(border=True):
                    numero = html.escape(str(s["numero"]))
                    tipo = html.escape(s["setor"] or "—")
                    waba = html.escape(s["waba"] or "—")

                    chave = (sender_id, data_iso)
                    valor_atual = pendentes.get(chave, {"qualidade": "Alta", "status": "Conectado"})
                    idx_qualidade = QUALIDADE_OPTIONS.index(valor_atual["qualidade"])
                    idx_status = STATUS_OPTIONS.index(valor_atual["status"])

                    st.markdown(
                        '<div class="lanc-card-header">'
                        f'<span class="lanc-card-number">📱 {numero}</span>'
                        f'<span class="waba-tag">{waba}</span>'
                        '</div>'
                        f'<div class="lanc-card-sub">{tipo}</div>',
                        unsafe_allow_html=True,
                    )

                    qualidade_val = st.selectbox(
                        "Qualidade", QUALIDADE_OPTIONS, index=idx_qualidade,
                        key=f"qualidade_{sender_id}_{data_iso}",
                    )
                    status_val = st.selectbox(
                        "Status", STATUS_OPTIONS, index=idx_status,
                        key=f"status_{sender_id}_{data_iso}",
                    )
                    pendentes[chave] = {"qualidade": qualidade_val, "status": status_val}

                    dot_color = QUALIDADE_COLORS.get(qualidade_val, "#8b949e")
                    status_color = STATUS_COLORS.get(status_val, "#8b949e")
                    st.markdown(
                        f'<span class="badge" style="--dot-color:{dot_color}">{html.escape(qualidade_val)}</span>'
                        f'&nbsp;&nbsp;<span class="badge" style="--dot-color:{status_color}">{html.escape(status_val)}</span>',
                        unsafe_allow_html=True,
                    )
