"""Alertas globais exibidos na barra lateral de todas as páginas do app."""
import streamlit as st
from db import get_alerts, confirmar_recarga_hoje, CICLO_RECARGA_DIAS
from slack_alert import verificar_e_alertar_recarga, verificar_e_enviar_relatorio_semanal


def render_sidebar_alerts():
    resultado_slack = verificar_e_alertar_recarga()
    if resultado_slack["status"] == "erro":
        st.sidebar.caption(f"⚠️ Falha ao enviar alerta de recarga pro Slack: {resultado_slack['detalhe']}")
    elif resultado_slack["status"] == "enviado":
        st.sidebar.caption("📨 Alerta de recarga enviado pro Slack.")

    resultado_semanal = verificar_e_enviar_relatorio_semanal()
    if resultado_semanal["status"] == "erro":
        st.sidebar.caption(f"⚠️ Falha ao enviar relatório semanal pro Slack: {resultado_semanal['detalhe']}")
    elif resultado_semanal["status"] == "enviado":
        st.sidebar.caption("📨 Relatório semanal enviado pro Slack.")

    alerts = get_alerts()
    st.sidebar.divider()
    if not alerts:
        st.sidebar.success("✅ Nenhum alerta no momento.")
        return
    for alert in alerts:
        getattr(st.sidebar, alert["level"])(alert["message"])
        if alert.get("tipo") == "recarga":
            if st.sidebar.button(
                f"✅ Confirmar recarga hoje (+{CICLO_RECARGA_DIAS}d)",
                key="confirmar_recarga_sidebar",
                width="stretch",
            ):
                confirmar_recarga_hoje()
                st.rerun()
