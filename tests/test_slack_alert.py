import datetime

import pandas as pd
import pytest

import db
import slack_alert


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


@pytest.fixture
def slack_config(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-fake")
    monkeypatch.setenv("SLACK_CHANNEL", "C123")


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture
def slack_calls(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if url == "https://slack.com/api/files.getUploadURLExternal":
            return _FakeResponse({"ok": True, "upload_url": "https://upload.example/x", "file_id": "F123"})
        if url == "https://upload.example/x":
            return _FakeResponse({})
        if url == "https://slack.com/api/files.completeUploadExternal":
            return _FakeResponse({"ok": True})
        if url == "https://slack.com/api/chat.postMessage":
            return _FakeResponse({"ok": True})
        raise AssertionError(f"unexpected URL posted: {url}")

    monkeypatch.setattr(slack_alert.requests, "post", fake_post)
    return calls


def test_sem_config_nao_faz_nada(temp_db, monkeypatch, slack_calls):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_CHANNEL", raising=False)
    resultado = slack_alert.verificar_e_alertar_recarga()
    assert resultado == {"status": "sem_config"}
    assert slack_calls == []


def test_sem_recarga_registrada(temp_db, slack_config, slack_calls):
    resultado = slack_alert.verificar_e_alertar_recarga()
    assert resultado == {"status": "sem_recarga_registrada"}
    assert slack_calls == []


def test_fora_do_prazo_nao_alerta(temp_db, slack_config, slack_calls):
    futuro = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
    temp_db.add_recarga(datetime.date.today().isoformat(), futuro, None)
    resultado = slack_alert.verificar_e_alertar_recarga()
    assert resultado == {"status": "fora_do_prazo"}
    assert slack_calls == []


@pytest.mark.parametrize("dias_faltando", [1, 2, 4, 5, -1, -5])
def test_dias_fora_de_d3_e_d0_nao_alertam(temp_db, slack_config, slack_calls, dias_faltando):
    """Só dispara em D-3 (3 dias antes) e D-0 (dia do vencimento) — qualquer outro dia fica quieto."""
    data = (datetime.date.today() + datetime.timedelta(days=dias_faltando)).isoformat()
    temp_db.add_recarga("2024-01-01", data, None)
    resultado = slack_alert.verificar_e_alertar_recarga()
    assert resultado == {"status": "fora_do_prazo"}
    assert slack_calls == []


def test_alerta_no_dia_do_vencimento_d0(temp_db, slack_config, slack_calls):
    temp_db.add_sender("5511700000009", "A", "P", "Auto", "ACME", "Vivo", True)
    hoje = datetime.date.today().isoformat()
    temp_db.add_recarga("2024-01-01", hoje, None)

    resultado = slack_alert.verificar_e_alertar_recarga()

    assert resultado == {"status": "enviado"}
    urls = [url for url, _ in slack_calls]
    assert urls == [
        "https://slack.com/api/files.getUploadURLExternal",
        "https://upload.example/x",
        "https://slack.com/api/files.completeUploadExternal",
    ]
    # o csv realmente foi anexado com o sender cadastrado
    upload_kwargs = slack_calls[1][1]
    csv_bytes = upload_kwargs["files"]["file"][1]
    assert b"5511700000009" in csv_bytes
    # mensagem do dia do vencimento, não "vencida"
    texto = slack_calls[2][1]["json"]["initial_comment"]
    assert "vence hoje" in texto


def test_alerta_3_dias_antes_d3(temp_db, slack_config, slack_calls):
    daqui_3_dias = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
    temp_db.add_recarga("2024-01-01", daqui_3_dias, None)

    resultado = slack_alert.verificar_e_alertar_recarga()

    assert resultado == {"status": "enviado"}
    texto = slack_calls[2][1]["json"]["initial_comment"]
    assert "vence em 3 dias" in texto


def test_recarga_vencida_no_passado_nao_alerta_mais(temp_db, slack_config, slack_calls):
    """Depois que passa do D-0 sem ninguém confirmar, o Slack não repete o aviso."""
    ha_5_dias = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
    temp_db.add_recarga("2024-01-01", ha_5_dias, None)
    resultado = slack_alert.verificar_e_alertar_recarga()
    assert resultado == {"status": "fora_do_prazo"}
    assert slack_calls == []


def test_nao_alerta_duas_vezes_no_mesmo_dia(temp_db, slack_config, slack_calls):
    hoje = datetime.date.today().isoformat()
    temp_db.add_recarga("2024-01-01", hoje, None)

    primeiro = slack_alert.verificar_e_alertar_recarga()
    segundo = slack_alert.verificar_e_alertar_recarga()

    assert primeiro == {"status": "enviado"}
    assert segundo == {"status": "ja_alertado_hoje"}
    # só a primeira chamada bateu no Slack (3 requests); a segunda não gerou nenhuma
    assert len(slack_calls) == 3


def test_erro_no_envio_nao_marca_como_alertado(temp_db, slack_config, monkeypatch):
    def fake_post_com_erro(url, **kwargs):
        raise ConnectionError("falha de rede simulada")

    monkeypatch.setattr(slack_alert.requests, "post", fake_post_com_erro)

    hoje = datetime.date.today().isoformat()
    temp_db.add_recarga("2024-01-01", hoje, None)

    resultado = slack_alert.verificar_e_alertar_recarga()

    assert resultado["status"] == "erro"
    assert "falha de rede simulada" in resultado["detalhe"]
    assert temp_db.get_state(slack_alert.ESTADO_CHAVE) is None


# ---------- enviar_mudancas_qualidade_slack ----------

def _changes_df(linhas):
    return pd.DataFrame(linhas, columns=["sender_id", "numero", "setor", "waba", "data_atual", "qualidade_atual", "qualidade_anterior"])


def test_mudancas_sem_config_nao_faz_nada(slack_calls, monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_CHANNEL", raising=False)
    df = _changes_df([(1, "5511900000001", "Auto", "ACME", "2024-01-02", "Alta", "Baixa")])
    resultado = slack_alert.enviar_mudancas_qualidade_slack(df, "02/01/2024")
    assert resultado == {"status": "sem_config"}
    assert slack_calls == []


def test_mudancas_vazias_nao_envia(slack_config, slack_calls):
    resultado = slack_alert.enviar_mudancas_qualidade_slack(_changes_df([]), "02/01/2024")
    assert resultado == {"status": "sem_mudancas"}
    assert slack_calls == []


def test_mudancas_envia_mensagem_com_setas_e_waba(slack_config, slack_calls):
    df = _changes_df([
        (1, "5511900000001", "Auto", "PROVEDOR_B_TITULAR", "2024-01-02", "Alta", "Baixa"),  # melhorou
        (2, "5511900000002", "Viagem", "PROVEDOR_A_RESERVA", "2024-01-02", "Sinalizado", "Alta"),  # piorou
    ])
    resultado = slack_alert.enviar_mudancas_qualidade_slack(df, "02/01/2024")

    assert resultado == {"status": "enviado", "quantidade": 2}
    assert len(slack_calls) == 1
    url, kwargs = slack_calls[0]
    assert url == "https://slack.com/api/chat.postMessage"
    texto = kwargs["json"]["text"]
    assert "5511900000001" in texto and "PROVEDOR_B_TITULAR" in texto and "⬆️" in texto
    assert "5511900000002" in texto and "PROVEDOR_A_RESERVA" in texto and "⬇️" in texto


def test_mudancas_erro_no_envio(slack_config, monkeypatch):
    def fake_post_com_erro(url, **kwargs):
        raise ConnectionError("falha de rede simulada")

    monkeypatch.setattr(slack_alert.requests, "post", fake_post_com_erro)
    df = _changes_df([(1, "5511900000001", "Auto", "ACME", "2024-01-02", "Alta", "Baixa")])
    resultado = slack_alert.enviar_mudancas_qualidade_slack(df, "02/01/2024")
    assert resultado["status"] == "erro"
    assert "falha de rede simulada" in resultado["detalhe"]


# ---------- verificar_e_enviar_relatorio_semanal ----------

_SEGUNDA = datetime.date(2024, 1, 1)  # 01/01/2024 foi uma segunda-feira
_TERCA = datetime.date(2024, 1, 2)


def _mock_hoje(monkeypatch, data):
    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return data

    monkeypatch.setattr(slack_alert.datetime, "date", FakeDate)


def test_relatorio_sem_config_nao_faz_nada(temp_db, slack_calls, monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_CHANNEL", raising=False)
    _mock_hoje(monkeypatch, _SEGUNDA)
    resultado = slack_alert.verificar_e_enviar_relatorio_semanal()
    assert resultado == {"status": "sem_config"}
    assert slack_calls == []


def test_relatorio_fora_do_dia_configurado(temp_db, slack_config, slack_calls, monkeypatch):
    _mock_hoje(monkeypatch, _TERCA)
    resultado = slack_alert.verificar_e_enviar_relatorio_semanal()
    assert resultado == {"status": "nao_e_dia"}
    assert slack_calls == []


def test_relatorio_enviado_na_segunda_com_csv_certo(temp_db, slack_config, slack_calls, monkeypatch):
    temp_db.add_sender("5511900000401", "A", "P", "Auto", "PROVEDOR_B_TITULAR", "Vivo", True)
    _mock_hoje(monkeypatch, _SEGUNDA)

    resultado = slack_alert.verificar_e_enviar_relatorio_semanal()

    assert resultado == {"status": "enviado"}
    urls = [url for url, _ in slack_calls]
    assert urls == [
        "https://slack.com/api/files.getUploadURLExternal",
        "https://upload.example/x",
        "https://slack.com/api/files.completeUploadExternal",
    ]
    csv_bytes = slack_calls[1][1]["files"]["file"][1]
    csv_texto = csv_bytes.decode("utf-8-sig")
    assert "Sender,Produto,WABA,Operadora" in csv_texto
    assert "5511900000401,Auto,PROVEDOR_B_TITULAR,Vivo" in csv_texto


def test_relatorio_nao_repete_na_mesma_semana(temp_db, slack_config, slack_calls, monkeypatch):
    _mock_hoje(monkeypatch, _SEGUNDA)
    primeiro = slack_alert.verificar_e_enviar_relatorio_semanal()
    segundo = slack_alert.verificar_e_enviar_relatorio_semanal()
    assert primeiro == {"status": "enviado"}
    assert segundo == {"status": "ja_enviado_essa_semana"}
    assert len(slack_calls) == 3


def test_relatorio_erro_no_envio(temp_db, slack_config, monkeypatch):
    def fake_post_com_erro(url, **kwargs):
        raise ConnectionError("falha de rede simulada")

    monkeypatch.setattr(slack_alert.requests, "post", fake_post_com_erro)
    _mock_hoje(monkeypatch, _SEGUNDA)

    resultado = slack_alert.verificar_e_enviar_relatorio_semanal()

    assert resultado["status"] == "erro"
    assert "falha de rede simulada" in resultado["detalhe"]
    assert temp_db.get_state(slack_alert.ESTADO_CHAVE_RELATORIO_SEMANAL) is None
