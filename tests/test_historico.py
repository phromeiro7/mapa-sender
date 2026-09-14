from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import db

PAGINA = str(Path(__file__).resolve().parent.parent / "pages" / "3_Historico.py")


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


def test_historico_sem_dados(temp_db):
    at = AppTest.from_file(PAGINA)
    at.run()
    assert not at.exception
    assert any("0 registros encontrados" in w.value for w in at.markdown)


def test_historico_filtra_por_sender(temp_db):
    sid = temp_db.add_sender("5511900003001", "A", "P", "Auto", "ACME")
    outro = temp_db.add_sender("5511900003002", "B", "P", "Auto", "ACME")
    temp_db.upsert_snapshot(sid, "2024-01-01", "Alta", "Conectado")
    temp_db.upsert_snapshot(outro, "2024-01-01", "Baixa", "Conectado")

    at = AppTest.from_file(PAGINA)
    at.run()
    assert not at.exception

    seletor = at.selectbox[0]
    opcao_do_sid = [o for o in seletor.options if "900003001" in o][0]
    seletor.set_value(opcao_do_sid).run()
    assert not at.exception

    assert any("1 registros encontrados" in w.value for w in at.markdown)
