import html
import datetime
import pandas as pd
import streamlit as st
from db import (
    init_db,
    add_sender,
    update_sender,
    set_sender_active,
    delete_sender,
    get_sender_by_id,
    numero_existe,
    formatar_numero,
    get_senders,
    upsert_snapshot,
    get_current_status_df,
    get_snapshots_for_dates,
    get_quality_changes,
    get_ultima_recarga,
    QUALIDADE_OPTIONS,
    OPERADORA_OPTIONS,
    WABA_OPTIONS,
    ICON_MAP,
    QUALIDADE_COLORS,
    QUALIDADE_RANK,
    STATUS_COLORS,
)
from alerts import render_sidebar_alerts
from styles import inject_base_styles

st.set_page_config(page_title="Mapa Sender", page_icon="📶", layout="wide")

init_db()
inject_base_styles()
render_sidebar_alerts()

st.title("📊 Painel — Situação dos Senders")
st.caption(f"Situação em {datetime.date.today().strftime('%d/%m/%Y')}")


def _formatar_operadora(v):
    return "Selecione (opcional)" if v == "" else v


def _fechar_edicao():
    st.session_state["editing_sender_id"] = None


@st.dialog("➕ Adicionar sender")
def dialog_adicionar_sender():
    c1, c2 = st.columns(2)
    numero = c1.text_input(
        "Número do sender *", placeholder="Ex: 5511999889928",
        help="Pode digitar com ou sem +55, espaço, traço — o número é formatado automaticamente.",
    )
    display_name = c2.text_input("Display Name", placeholder="Ex: Acme")
    parceiro_segmento = c1.text_input("Parceiro / Segmento", placeholder="Ex: 99/Localiza (opcional)")
    setor = c2.text_input("Tipo *", placeholder="Ex: Auto")
    waba = c1.selectbox("WABA *", WABA_OPTIONS)
    operadora = c2.selectbox("Operadora", OPERADORA_OPTIONS, format_func=_formatar_operadora)
    qualidade = c1.selectbox("Qualidade *", QUALIDADE_OPTIONS, help="Qualidade atual — cria o primeiro registro de hoje.")
    possui_chip = c2.checkbox("Possui chip?", value=True)
    cadastrado_por = st.text_input("Cadastrado por *", placeholder="Seu nome", help="Quem está fazendo esse cadastro.")

    if st.button("Adicionar sender", type="primary"):
        numero_limpo = formatar_numero(numero)
        if not numero_limpo or not setor.strip() or not cadastrado_por.strip():
            st.error("Preencha ao menos: Número, Tipo e Cadastrado por.")
        elif numero_existe(numero_limpo):
            st.error(f"O número **{numero_limpo}** já está cadastrado. Números não podem se repetir.")
        else:
            new_id = add_sender(
                numero_limpo, display_name.strip(), parceiro_segmento.strip(),
                setor.strip(), waba, operadora.strip(), possui_chip, cadastrado_por.strip(),
            )
            upsert_snapshot(new_id, datetime.date.today().isoformat(), qualidade, "Conectado")
            st.success(f"Sender {numero_limpo} adicionado.")
            st.rerun()


@st.dialog("✏️ Editar sender", on_dismiss=_fechar_edicao)
def dialog_editar_sender(sender_id):
    row = get_sender_by_id(sender_id)
    if row is None:
        st.warning("Esse sender não existe mais (pode ter sido excluído).")
        return

    c1, c2 = st.columns(2)
    numero_e = c1.text_input("Número", value=row["numero"])
    display_name_e = c2.text_input("Display Name", value=row["display_name"] if pd.notna(row["display_name"]) else "")
    parceiro_e = c1.text_input(
        "Parceiro / Segmento", value=row["parceiro_segmento"] if pd.notna(row["parceiro_segmento"]) else ""
    )
    setor_e = c2.text_input("Tipo", value=row["setor"] if pd.notna(row["setor"]) else "")

    waba_atual = row["waba"] if pd.notna(row["waba"]) else ""
    idx_waba = WABA_OPTIONS.index(waba_atual) if waba_atual in WABA_OPTIONS else 0
    waba_e = c1.selectbox("WABA", WABA_OPTIONS, index=idx_waba)

    operadora_atual = row["operadora"] if pd.notna(row["operadora"]) else ""
    idx_operadora = OPERADORA_OPTIONS.index(operadora_atual) if operadora_atual in OPERADORA_OPTIONS else 0
    operadora_e = c2.selectbox("Operadora", OPERADORA_OPTIONS, index=idx_operadora, format_func=_formatar_operadora)

    possui_chip_e = st.checkbox("Possui chip?", value=bool(row["possui_chip"]))
    cadastrado_por_atual = row["cadastrado_por"] if pd.notna(row["cadastrado_por"]) else ""
    cadastrado_por_e = st.text_input("Cadastrado por", value=cadastrado_por_atual)

    b1, b2, b3 = st.columns(3)
    save = b1.button("💾 Salvar", type="primary")
    toggle = b2.button("🚫 Desativar" if row["ativo"] else "🔁 Reativar")
    remove = b3.button("🗑️ Excluir")

    if save:
        numero_limpo = formatar_numero(numero_e)
        if not numero_limpo or not setor_e.strip():
            st.error("Preencha ao menos: Número e Tipo.")
        elif numero_existe(numero_limpo, excluir_id=sender_id):
            st.error(f"O número **{numero_limpo}** já está em uso por outro sender.")
        else:
            update_sender(
                sender_id, numero_limpo, display_name_e.strip(), parceiro_e.strip(),
                setor_e.strip(), waba_e, operadora_e.strip(), possui_chip_e, cadastrado_por_e.strip(),
            )
            st.success("Alterações salvas.")
            st.session_state["editing_sender_id"] = None
            st.rerun()
    if toggle:
        set_sender_active(sender_id, not row["ativo"])
        st.session_state["editing_sender_id"] = None
        st.rerun()
    if remove:
        delete_sender(sender_id)
        st.warning(f"Sender {row['numero']} excluído.")
        st.session_state["editing_sender_id"] = None
        st.rerun()


if st.session_state.get("editing_sender_id"):
    dialog_editar_sender(st.session_state["editing_sender_id"])

if st.button("➕ Adicionar sender", type="primary"):
    dialog_adicionar_sender()

current_df = get_current_status_df()
if current_df.empty:
    st.info("Nenhum sender cadastrado ainda. Use o botão acima para adicionar o primeiro.")
    st.stop()

st.divider()

with st.container(border=True):
    busca = st.text_input("🔍 Buscar sender", placeholder="Número, nome ou parceiro/segmento...")

    wabas = sorted(current_df["waba"].dropna().unique())
    st.caption("Filtrar por WABA")
    if wabas:
        f_waba = st.pills("WABA", wabas, selection_mode="multi", default=wabas, label_visibility="collapsed")
    else:
        f_waba = []
        st.caption("Nenhum WABA cadastrado ainda.")

    setores = sorted(current_df["setor"].dropna().unique())
    f_setor = st.multiselect("Tipo (opcional)", setores)

filtered = current_df.copy()
if busca:
    termo = busca.strip().lower()
    mask = (
        filtered["numero"].astype(str).str.lower().str.contains(termo, na=False)
        | filtered["display_name"].astype(str).str.lower().str.contains(termo, na=False)
        | filtered["parceiro_segmento"].astype(str).str.lower().str.contains(termo, na=False)
    )
    filtered = filtered[mask]
if f_waba:
    filtered = filtered[filtered["waba"].isin(f_waba)]
if f_setor:
    filtered = filtered[filtered["setor"].isin(f_setor)]

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Senders exibidos", len(filtered))
m2.metric("✓ Alta", int((filtered["qualidade"] == "Alta").sum()))
m3.metric("▲ Média", int((filtered["qualidade"] == "Média").sum()))
m4.metric("⮾ Baixa", int((filtered["qualidade"] == "Baixa").sum()))
m5.metric("⚠ Sinalizado", int((filtered["qualidade"] == "Sinalizado").sum()))

st.divider()

st.subheader("🔄 Mudanças de Qualidade")
changes_df = get_quality_changes()
changes_df = changes_df[changes_df["sender_id"].isin(filtered["sender_id"])]

if changes_df.empty:
    st.caption("Nenhuma mudança de qualidade desde o lançamento anterior.")
else:
    linhas_html = []
    for _, c in changes_df.iterrows():
        cor_anterior = QUALIDADE_COLORS.get(c["qualidade_anterior"], "#8b949e")
        cor_atual = QUALIDADE_COLORS.get(c["qualidade_atual"], "#8b949e")
        melhorou = QUALIDADE_RANK.get(c["qualidade_atual"], 0) > QUALIDADE_RANK.get(c["qualidade_anterior"], 0)
        seta_emoji = "⬆️" if melhorou else "⬇️"
        linhas_html.append(
            '<div class="mudanca-row">'
            f'<span class="mudanca-numero">{seta_emoji} {html.escape(c["numero"])}</span>'
            f'<span class="mudanca-tipo">{html.escape(c["setor"] or "—")}</span>'
            f'<span class="waba-tag">{html.escape(c["waba"] or "—")}</span>'
            f'<span class="badge" style="--dot-color:{cor_anterior}">{html.escape(c["qualidade_anterior"])}</span>'
            '<span class="mudanca-arrow">→</span>'
            f'<span class="badge" style="--dot-color:{cor_atual}">{html.escape(c["qualidade_atual"])}</span>'
            '</div>'
        )
    st.markdown("".join(linhas_html), unsafe_allow_html=True)

st.divider()

ultima_recarga = get_ultima_recarga()
recarga_label = "Nunca registrada"
if ultima_recarga is not None:
    data_recarga, _, _ = ultima_recarga
    recarga_label = datetime.date.fromisoformat(data_recarga).strftime("%d/%m/%Y")

st.subheader("📶 Senders")
st.caption("Clique em ✏️ Editar dentro de um card para alterar, desativar ou excluir o sender.")

export_completo_df = filtered[[
    "numero", "display_name", "parceiro_segmento", "setor", "waba",
    "operadora", "possui_chip", "qualidade", "status", "cadastrado_por",
]].rename(columns={
    "numero": "Número",
    "display_name": "Nome",
    "parceiro_segmento": "Parceiro/Segmento",
    "setor": "Tipo",
    "waba": "WABA",
    "operadora": "Operadora",
    "possui_chip": "Possui chip",
    "qualidade": "Qualidade",
    "status": "Status",
    "cadastrado_por": "Cadastrado por",
})
st.download_button(
    "⬇️ Exportar CSV completo",
    export_completo_df.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"senders_completo_{datetime.date.today().isoformat()}.csv",
    mime="text/csv",
)

if filtered.empty:
    st.info("Nenhum sender para os filtros/busca selecionados.")
else:
    N_COLS = 4
    linhas_df = list(filtered.sort_values(["setor", "parceiro_segmento"]).iterrows())
    for inicio in range(0, len(linhas_df), N_COLS):
        cols = st.columns(N_COLS)
        for col, (_, r) in zip(cols, linhas_df[inicio:inicio + N_COLS]):
            with col:
                with st.container(border=True):
                    qualidade = r["qualidade"] if pd.notna(r["qualidade"]) else None
                    dot_color = QUALIDADE_COLORS.get(qualidade, "#8b949e")
                    qualidade_label = html.escape(qualidade or "Sem lançamento")

                    status = r["status"] if pd.notna(r["status"]) else None
                    status_color = STATUS_COLORS.get(status, "#8b949e")
                    status_label = html.escape(status or "—")

                    numero = html.escape(str(r["numero"]))
                    nome = html.escape(r["display_name"] or "sem rótulo")
                    waba = html.escape(r["waba"] or "—")
                    tipo = html.escape(r["setor"] or "—")
                    recarga_txt = recarga_label if r["possui_chip"] else "Sem chip"
                    cadastrado_por = html.escape(r["cadastrado_por"] if pd.notna(r["cadastrado_por"]) else "—")

                    st.markdown(
                        '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
                        f'<span style="font-weight:600;color:#e6edf3;">📱 {numero}</span>'
                        f'<span class="badge" style="--dot-color:{dot_color}">{qualidade_label}</span>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div style="font-size:0.85rem;color:#c9d1d9;margin:6px 0;">{nome} · {tipo}</div>'
                        f'<span class="waba-tag">{waba}</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        '<div style="font-size:0.75rem;color:#8b949e;margin-top:10px;">'
                        f'<span style="color:{status_color};font-weight:600;">● {status_label}</span>'
                        f'<br>🔋 Última recarga: {recarga_txt}'
                        f'<br>👤 Cadastrado por: {cadastrado_por}'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button("✏️ Editar", key=f"edit_{r['sender_id']}", width="stretch"):
                        st.session_state["editing_sender_id"] = int(r["sender_id"])
                        st.rerun()

inativos_df = get_senders(active_only=False)
inativos_df = inativos_df[inativos_df["ativo"] == 0]
if not inativos_df.empty:
    with st.expander(f"🗃️ Senders inativos ({len(inativos_df)})"):
        for _, r in inativos_df.iterrows():
            c1, c2 = st.columns([4, 1])
            c1.write(f"{r['numero']} — {r['waba'] or '—'} ({r['setor'] or '—'})")
            if c2.button("🔁 Reativar", key=f"reativar_{r['id']}"):
                set_sender_active(r["id"], True)
                st.rerun()

st.divider()

with st.expander("📈 Tendência dos últimos 4 dias e exportação"):
    today = datetime.date.today()
    last4_dates = [(today - datetime.timedelta(days=i)) for i in range(1, 5)]
    last4_iso = [d.isoformat() for d in last4_dates]

    hist_df = get_snapshots_for_dates(filtered["sender_id"].tolist(), last4_iso)

    def icon(q):
        if pd.isna(q):
            return "—"
        return f"{ICON_MAP.get(q, '?')} {q}"

    display_rows = []
    for _, r in filtered.iterrows():
        row = {
            "Sender": r["numero"],
            "WABA": r["waba"],
            "Tipo": r["setor"],
            "Qualidade atual": icon(r["qualidade"]),
            "Status atual": r["status"] if pd.notna(r["status"]) else "—",
            "Última atualização": r["data"] if pd.notna(r["data"]) else "—",
        }
        sender_hist = hist_df[hist_df["sender_id"] == r["sender_id"]]
        for i, d_iso in enumerate(last4_iso, start=1):
            match = sender_hist[sender_hist["data"] == d_iso]
            if not match.empty:
                row[f"Qualid. D-{i}"] = icon(match.iloc[0]["qualidade"])
            else:
                row[f"Qualid. D-{i}"] = "—"
        display_rows.append(row)

    result_df = pd.DataFrame(display_rows)

    def style_qualidade(val):
        for label, color in QUALIDADE_COLORS.items():
            if isinstance(val, str) and label in val:
                return f"color: {color}; font-weight: 600;"
        return ""

    # Sem "subset": com poucas linhas, o subset como lista de colunas fica ambíguo pro pandas
    # e quebra. A função já ignora sozinha qualquer coluna sem valor de qualidade (retorna ""),
    # então aplicar em todas as células é seguro.
    styled = result_df.style.map(style_qualidade)
    st.dataframe(styled, width="stretch", hide_index=True)

    st.download_button(
        "⬇️ Exportar CSV",
        result_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"painel_sender_{today.isoformat()}.csv",
        mime="text/csv",
    )
