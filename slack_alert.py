"""Notificações automáticas no Slack: alerta de recarga (D-3/D-0, com CSV anexado),
mudanças de qualidade ao salvar o Lançamento Diário, e relatório semanal (CSV completo).

Configuração via variáveis de ambiente SLACK_BOT_TOKEN e SLACK_CHANNEL, lidas de um
arquivo .env local (veja .env.example) — nunca commitado. Sem essas variáveis, todas as
notificações ficam desativadas silenciosamente.
"""
import datetime
import os

import requests
from dotenv import load_dotenv

from db import (
    get_ultima_recarga,
    get_senders_export_recarga,
    get_senders_export_semanal,
    try_claim_state,
    clear_state,
    QUALIDADE_RANK,
)

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

ESTADO_CHAVE = "slack_ultimo_alerta_recarga"
DIAS_ANTECEDENCIA = 3

ESTADO_CHAVE_RELATORIO_SEMANAL = "slack_ultimo_relatorio_semanal"
DIA_SEMANA_RELATORIO = 0  # segunda-feira (0=segunda ... 6=domingo, igual date.weekday())


def _carregar_config():
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL")
    if not bot_token or not channel:
        return None
    return {"bot_token": bot_token, "channel": channel}


def _montar_csv():
    return get_senders_export_recarga().to_csv(index=False).encode("utf-8-sig")


def _enviar_arquivo_slack(token, channel, texto, csv_bytes, filename):
    """Sobe um arquivo e posta no canal, via fluxo de upload externo (files.upload é legado)."""
    headers = {"Authorization": f"Bearer {token}"}

    r1 = requests.post(
        "https://slack.com/api/files.getUploadURLExternal",
        headers=headers,
        data={"filename": filename, "length": len(csv_bytes)},
        timeout=10,
    )
    r1.raise_for_status()
    d1 = r1.json()
    if not d1.get("ok"):
        raise RuntimeError(f"files.getUploadURLExternal: {d1.get('error')}")

    r2 = requests.post(d1["upload_url"], files={"file": (filename, csv_bytes)}, timeout=30)
    r2.raise_for_status()

    r3 = requests.post(
        "https://slack.com/api/files.completeUploadExternal",
        headers=headers,
        json={
            "files": [{"id": d1["file_id"], "title": filename}],
            "channel_id": channel,
            "initial_comment": texto,
        },
        timeout=10,
    )
    r3.raise_for_status()
    d3 = r3.json()
    if not d3.get("ok"):
        raise RuntimeError(f"files.completeUploadExternal: {d3.get('error')}")
    return d3


def _enviar_mensagem_slack(token, channel, texto):
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}"},
        json={"channel": channel, "text": texto},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"chat.postMessage: {data.get('error')}")
    return data


def _seta_direcao(qualidade_anterior, qualidade_atual):
    """Seta indicando se a qualidade melhorou (para cima) ou piorou (para baixo)."""
    anterior = QUALIDADE_RANK.get(qualidade_anterior, 0)
    atual = QUALIDADE_RANK.get(qualidade_atual, 0)
    return "⬆️" if atual > anterior else "⬇️"


def enviar_mudancas_qualidade_slack(changes_df, data_label):
    """Manda no Slack a lista de senders que mudaram de qualidade no lançamento do dia.

    Não faz nada (sem erro) se não houver configuração do Slack ou se a lista estiver vazia —
    dias sem nenhuma mudança não geram mensagem.

    Retorna {"status": ...}: sem_config, sem_mudancas, enviado, erro.
    """
    config = _carregar_config()
    if config is None:
        return {"status": "sem_config"}
    if changes_df.empty:
        return {"status": "sem_mudancas"}

    linhas = "\n".join(
        f"{_seta_direcao(c['qualidade_anterior'], c['qualidade_atual'])} `{c['numero']}` "
        f"({c['setor'] or '—'} · {c['waba'] or '—'}) — *{c['qualidade_anterior']}* → *{c['qualidade_atual']}*"
        for _, c in changes_df.iterrows()
    )
    texto = f":arrows_counterclockwise: *Mudanças de qualidade — {data_label}*\n{linhas}"

    try:
        _enviar_mensagem_slack(config["bot_token"], config["channel"], texto)
    except Exception as e:
        return {"status": "erro", "detalhe": str(e)}

    return {"status": "enviado", "quantidade": len(changes_df)}


def verificar_e_alertar_recarga():
    """Manda 1 alerta no Slack (com CSV de senders/operadoras anexado) exatamente 2 vezes por
    ciclo de recarga: DIAS_ANTECEDENCIA dias antes de vencer, e no dia do vencimento. Fora
    desses dois dias — inclusive se a recarga ficar vencida sem ninguém confirmar — fica em
    silêncio no Slack (o aviso dentro do app continua normalmente via get_alerts()).

    Retorna {"status": ...} descrevendo o resultado (útil para depuração/testes):
    sem_config, sem_recarga_registrada, fora_do_prazo, ja_alertado_hoje, enviado, erro.
    """
    config = _carregar_config()
    if config is None:
        return {"status": "sem_config"}

    ultima = get_ultima_recarga()
    if ultima is None:
        return {"status": "sem_recarga_registrada"}

    _, proxima_recarga, _ = ultima
    hoje = datetime.date.today()
    dias = (datetime.date.fromisoformat(proxima_recarga) - hoje).days
    if dias not in (DIAS_ANTECEDENCIA, 0):
        return {"status": "fora_do_prazo"}

    if not try_claim_state(ESTADO_CHAVE, hoje.isoformat()):
        return {"status": "ja_alertado_hoje"}

    data_fmt = datetime.date.fromisoformat(proxima_recarga).strftime("%d/%m/%Y")
    if dias == 0:
        texto = (
            f":red_circle: *Recarga vence hoje* ({data_fmt}). "
            "Segue a lista de senders/operadoras para recarga:"
        )
    else:
        texto = (
            f":large_yellow_circle: *Recarga vence em {dias} dias* ({data_fmt}). "
            "Segue a lista de senders/operadoras para recarga:"
        )

    try:
        _enviar_arquivo_slack(
            config["bot_token"], config["channel"], texto,
            _montar_csv(), f"senders_recarga_{hoje.isoformat()}.csv",
        )
    except Exception as e:
        clear_state(ESTADO_CHAVE)
        return {"status": "erro", "detalhe": str(e)}

    return {"status": "enviado"}


def verificar_e_enviar_relatorio_semanal():
    """Manda no Slack, 1 vez por semana (toda segunda-feira), um CSV com Sender/Produto/
    WABA/Operadora de todo sender ativo. Se ninguém abrir o app naquela segunda, a semana
    passa em silêncio — sem envio atrasado nos outros dias.

    Retorna {"status": ...}: sem_config, nao_e_dia, ja_enviado_essa_semana, enviado, erro.
    """
    config = _carregar_config()
    if config is None:
        return {"status": "sem_config"}

    hoje = datetime.date.today()
    if hoje.weekday() != DIA_SEMANA_RELATORIO:
        return {"status": "nao_e_dia"}

    ano, semana, _ = hoje.isocalendar()
    chave_semana = f"{ano}-W{semana:02d}"
    if not try_claim_state(ESTADO_CHAVE_RELATORIO_SEMANAL, chave_semana):
        return {"status": "ja_enviado_essa_semana"}

    texto = f":bar_chart: *Relatório semanal de senders* — {hoje.strftime('%d/%m/%Y')}"
    csv_bytes = get_senders_export_semanal().to_csv(index=False).encode("utf-8-sig")

    try:
        _enviar_arquivo_slack(
            config["bot_token"], config["channel"], texto,
            csv_bytes, f"senders_semanal_{hoje.isoformat()}.csv",
        )
    except Exception as e:
        clear_state(ESTADO_CHAVE_RELATORIO_SEMANAL)
        return {"status": "erro", "detalhe": str(e)}

    return {"status": "enviado"}
