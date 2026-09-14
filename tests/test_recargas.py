from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import db

PAGINA = str(Path(__file__).resolve().parent.parent / "pages" / "2_Recargas.py")


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


def _abrir():
    at = AppTest.from_file(PAGINA)
    at.run()
    assert not at.exception
    return at


def test_recargas_sem_registro_mostra_aviso(temp_db):
    at = _abrir()
    assert any("Nenhuma recarga registrada" in w.value for w in at.warning)


def test_confirmar_recarga_hoje(temp_db):
    at = _abrir()
    botao = [w for w in at.button if "Confirmar recarga feita hoje" in w.label][0]
    botao.click().run()
    assert not at.exception

    ultima = temp_db.get_ultima_recarga()
    assert ultima is not None
    data_recarga, proxima_recarga, _ = ultima
    import datetime
    assert data_recarga == datetime.date.today().isoformat()
    assert proxima_recarga == (datetime.date.today() + datetime.timedelta(days=db.CICLO_RECARGA_DIAS)).isoformat()


def test_registrar_recarga_pelo_formulario(temp_db):
    at = _abrir()
    data_inputs = at.date_input
    data_recarga_in = data_inputs[0]
    proxima_recarga_in = data_inputs[1]

    import datetime
    nova_data = datetime.date.today()
    nova_proxima = nova_data + datetime.timedelta(days=10)
    data_recarga_in.set_value(nova_data)
    proxima_recarga_in.set_value(nova_proxima)

    botao = [w for w in at.button if w.label == "Registrar recarga"][0]
    botao.click().run()
    assert not at.exception

    ultima = temp_db.get_ultima_recarga()
    assert ultima == (nova_data.isoformat(), nova_proxima.isoformat(), None)


def test_exportar_senders_nao_mostra_tabela_de_telefones(temp_db):
    temp_db.add_sender("5511900002001", "A", "P", "Auto", "ACME", "Vivo", True)
    at = _abrir()
    # a pagina nao deve ter nenhum dataframe com os telefones na secao de exportacao —
    # so metrica + botao de download (pedido explicito do usuario)
    assert len(at.dataframe) == 1  # so o historico de recargas, nao a lista de telefones
