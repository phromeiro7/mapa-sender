from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import db

PAGINA = str(Path(__file__).resolve().parent.parent / "Painel.py")

# Observação: st.dialog (usado em "Adicionar sender" e "Editar sender") não é suportado pelo
# streamlit.testing.v1.AppTest — a persistência do dialog entre reruns depende de um mecanismo
# interno do runtime "ao vivo" que o harness de teste não simula. Esses dois fluxos já foram
# validados manualmente contra o app rodando de verdade (navegador real); aqui testamos o que
# o AppTest cobre com confiança: a página principal, filtros e o card grid.


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


def test_painel_sem_senders_mostra_aviso(temp_db):
    at = _abrir()
    assert any("Nenhum sender cadastrado" in info.value for info in at.info)


def test_painel_carrega_com_um_sender_sem_erro(temp_db):
    """Regressão: com exatamente 1 sender, o expander de tendência quebrava — o
    pandas.Styler.map(subset=[...lista de colunas...]) não sobrevivia ao pipeline de
    serialização Arrow do Streamlit quando o DataFrame tinha só 1 linha."""
    temp_db.add_sender("5511900001005", "Acme", "P", "Auto", "ACME")
    at = _abrir()
    assert not at.exception
    assert any("Acme" in md.value for md in at.markdown)


def test_busca_filtra_cards(temp_db):
    temp_db.add_sender("5511900001003", "Acme", "P", "Auto", "ACME")
    temp_db.add_sender("5511900001004", "Outro", "P", "Viagem", "PROVEDOR_A_RESERVA")

    at = _abrir()
    busca = [w for w in at.text_input if w.label == "🔍 Buscar sender"][0]
    # numero e formatado (+55 11 90000-1003) pela migracao ao iniciar o app — busca por um
    # trecho que sobrevive a formatacao, nao pelos digitos brutos originais.
    busca.set_value("90000-1003").run()
    assert not at.exception

    metrica = [m for m in at.metric if m.label == "Senders exibidos"][0]
    assert metrica.value == "1"


def test_filtro_waba_por_pills(temp_db):
    temp_db.add_sender("5511900001006", "A", "P", "Auto", "PROVEDOR_B_TITULAR")
    temp_db.add_sender("5511900001007", "B", "P", "Auto", "PROVEDOR_A_RESERVA")

    at = _abrir()
    pills = at.pills[0]
    pills.set_value(["PROVEDOR_B_TITULAR"]).run()
    assert not at.exception

    metrica = [m for m in at.metric if m.label == "Senders exibidos"][0]
    assert metrica.value == "1"
