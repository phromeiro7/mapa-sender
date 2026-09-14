import datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import db
import slack_alert

PAGINA = str(Path(__file__).resolve().parent.parent / "pages" / "1_Lancamento_Diario.py")


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


def _busca(at):
    return [w for w in at.text_input if w.label == "🔍 Buscar sender"][0]


def _selectbox_qualidade(at, sender_id):
    return [w for w in at.selectbox if w.key and w.key.startswith(f"qualidade_{sender_id}_")][0]


def _botao_salvar(at):
    return [w for w in at.button if "Salvar" in w.label][0]


def test_edicoes_sobrevivem_a_troca_de_busca_entre_senders(temp_db):
    """Regressão: editar o sender A, buscar por B (A some da tela) e editar B, depois salvar
    com a busca limpa, tem que gravar as duas edições — não só a última visível."""
    sid_a = temp_db.add_sender("5511900000101", "A", "P", "Auto", "ACME")
    sid_b = temp_db.add_sender("5511900000102", "B", "P", "Auto", "ACME")

    at = AppTest.from_file(PAGINA)
    at.run()
    assert not at.exception

    _busca(at).set_value("0000101").run()
    _selectbox_qualidade(at, sid_a).set_value("Baixa").run()

    _busca(at).set_value("0000102").run()
    _selectbox_qualidade(at, sid_b).set_value("Sinalizado").run()

    _busca(at).set_value("").run()
    _botao_salvar(at).click().run()
    assert not at.exception

    hoje = datetime.date.today().isoformat()
    conn = temp_db.get_connection()
    qualidade_a = conn.execute(
        "SELECT qualidade FROM snapshots WHERE sender_id=? AND data=?", (sid_a, hoje)
    ).fetchone()
    qualidade_b = conn.execute(
        "SELECT qualidade FROM snapshots WHERE sender_id=? AND data=?", (sid_b, hoje)
    ).fetchone()
    conn.close()

    assert qualidade_a == ("Baixa",)
    assert qualidade_b == ("Sinalizado",)


def test_salvar_sem_editar_grava_alta_para_todos(temp_db):
    """A tela mostra todo mundo como Alta/Conectado por padrão (pedido do usuário): salvar sem
    tocar em nada grava esse padrão para cada sender ativo, não só para quem foi editado."""
    sid_a = temp_db.add_sender("5511900000201", "A", "P", "Auto", "ACME")
    sid_c = temp_db.add_sender("5511900000203", "C", "P", "Auto", "ACME")

    at = AppTest.from_file(PAGINA)
    at.run()
    assert not at.exception

    _botao_salvar(at).click().run()
    assert not at.exception

    hoje = datetime.date.today().isoformat()
    conn = temp_db.get_connection()
    row_a = conn.execute("SELECT qualidade FROM snapshots WHERE sender_id=? AND data=?", (sid_a, hoje)).fetchone()
    row_c = conn.execute("SELECT qualidade FROM snapshots WHERE sender_id=? AND data=?", (sid_c, hoje)).fetchone()
    conn.close()

    assert row_a == ("Alta",)
    assert row_c == ("Alta",)


def test_salvar_dispara_envio_de_mudancas_pro_slack(temp_db, monkeypatch):
    """Salvar o lançamento do dia manda automaticamente as mudanças de qualidade pro Slack."""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-fake")
    monkeypatch.setenv("SLACK_CHANNEL", "C123")

    chamadas = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    def fake_post(url, **kwargs):
        chamadas.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(slack_alert.requests, "post", fake_post)

    sid = temp_db.add_sender("5511900000301", "A", "P", "Auto", "ACME")
    ontem = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    temp_db.upsert_snapshot(sid, ontem, "Baixa", "Conectado")

    at = AppTest.from_file(PAGINA)
    at.run()
    assert not at.exception

    _busca(at).set_value("0000301").run()
    _selectbox_qualidade(at, sid).set_value("Alta").run()
    _busca(at).set_value("").run()
    _botao_salvar(at).click().run()
    assert not at.exception

    assert len(chamadas) == 1
    url, kwargs = chamadas[0]
    assert url == "https://slack.com/api/chat.postMessage"
    texto = kwargs["json"]["text"]
    assert "5511900000301" in texto
    assert "Baixa" in texto and "Alta" in texto
