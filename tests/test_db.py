import datetime

import pytest

import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


def test_add_and_get_sender(temp_db):
    sid = temp_db.add_sender("5511999999999", "Acme", "99/Localiza", "Auto", "ACME", "Vivo", True)
    df = temp_db.get_senders()
    assert len(df) == 1
    assert df.iloc[0]["numero"] == "5511999999999"
    assert df.iloc[0]["id"] == sid


def test_add_sender_duplicate_numero_raises(temp_db):
    temp_db.add_sender("5511999999999", "Acme", "", "Auto", "ACME")
    with pytest.raises(Exception):
        temp_db.add_sender("5511999999999", "Outro", "", "Auto", "ACME")


def test_update_sender(temp_db):
    sid = temp_db.add_sender("5511111111111", "A", "P", "Auto", "ACME")
    temp_db.update_sender(sid, "5511111111111", "B", "P", "Saude", "ACME2", "Claro", False)
    row = temp_db.get_senders(active_only=False).iloc[0]
    assert row["display_name"] == "B"
    assert row["setor"] == "Saude"
    assert row["possui_chip"] == 0


def test_add_sender_grava_cadastrado_por(temp_db):
    sid = temp_db.add_sender("5511444455555", "A", "P", "Auto", "ACME", "Vivo", True, "Paulo Souza")
    row = temp_db.get_sender_by_id(sid)
    assert row["cadastrado_por"] == "Paulo Souza"


def test_update_sender_altera_cadastrado_por(temp_db):
    sid = temp_db.add_sender("5511444455556", "A", "P", "Auto", "ACME", cadastrado_por="Paulo Souza")
    temp_db.update_sender(sid, "5511444455556", "A", "P", "Auto", "ACME", cadastrado_por="Outra Pessoa")
    row = temp_db.get_sender_by_id(sid)
    assert row["cadastrado_por"] == "Outra Pessoa"


def test_add_sender_sem_cadastrado_por_fica_nulo(temp_db):
    sid = temp_db.add_sender("5511444455557", "A", "P", "Auto", "ACME")
    row = temp_db.get_sender_by_id(sid)
    assert row["cadastrado_por"] is None


def test_set_sender_active_filters_from_active_list(temp_db):
    sid = temp_db.add_sender("5511222222222", "A", "P", "Auto", "ACME")
    temp_db.set_sender_active(sid, False)
    assert temp_db.get_senders(active_only=True).empty
    assert len(temp_db.get_senders(active_only=False)) == 1


def test_delete_sender_removes_row(temp_db):
    sid = temp_db.add_sender("5511333333333", "A", "P", "Auto", "ACME")
    temp_db.delete_sender(sid)
    assert temp_db.get_senders(active_only=False).empty


def test_get_sender_by_id(temp_db):
    sid = temp_db.add_sender("5511333333001", "A", "P", "Auto", "ACME")
    row = temp_db.get_sender_by_id(sid)
    assert row["numero"] == "5511333333001"
    assert temp_db.get_sender_by_id(999999) is None


def test_formatar_numero_celular_com_e_sem_ddi(temp_db):
    esperado = "+55 11 99563-3314"
    assert temp_db.formatar_numero("+55 1199563-3314") == esperado  # falta espaço entre DDD e número
    assert temp_db.formatar_numero("+55 11 99563-3314") == esperado  # já no padrão
    assert temp_db.formatar_numero("5511995633314") == esperado  # só dígitos, com DDI
    assert temp_db.formatar_numero("11995633314") == esperado  # só dígitos, sem DDI
    assert temp_db.formatar_numero("(11) 99563-3314") == esperado  # com parênteses, sem DDI


def test_formatar_numero_fixo_8_digitos(temp_db):
    assert temp_db.formatar_numero("+55 11 5225-0525") == "+55 11 5225-0525"
    assert temp_db.formatar_numero("551152250525") == "+55 11 5225-0525"


def test_formatar_numero_padrao_nao_reconhecido_mantem_digitos(temp_db):
    assert temp_db.formatar_numero("123") == "123"
    assert temp_db.formatar_numero("") == ""
    assert temp_db.formatar_numero(None) == ""


def test_migracao_padroniza_numeros_existentes(temp_db):
    sid = temp_db.add_sender("+55 1199563-3314", "A", "P", "Auto", "ACME")
    temp_db.init_db()
    row = temp_db.get_sender_by_id(sid)
    assert row["numero"] == "+55 11 99563-3314"


def test_numero_existe(temp_db):
    sid = temp_db.add_sender("5511333333002", "A", "P", "Auto", "ACME")
    assert temp_db.numero_existe("5511333333002") is True
    assert temp_db.numero_existe("5511000000000") is False
    # o próprio sender não conta como duplicado quando excluído da checagem
    assert temp_db.numero_existe("5511333333002", excluir_id=sid) is False


def test_numero_existe_ignora_formatacao(temp_db):
    temp_db.add_sender("+55 1196366-5223", "A", "P", "Auto", "ACME")
    # mesmo número, com espaços/traço em posições diferentes
    assert temp_db.numero_existe("+55 11 96366-5223") is True
    assert temp_db.numero_existe("5511963665223") is True
    assert temp_db.numero_existe("(55) 11 96366-5223") is True
    assert temp_db.numero_existe("5511963665224") is False


def test_get_current_status_df_inclui_cadastrado_por(temp_db):
    sid = temp_db.add_sender("5511444444443", "A", "P", "Auto", "ACME", cadastrado_por="Paulo Souza")
    temp_db.upsert_snapshot(sid, datetime.date.today().isoformat(), "Alta", "Conectado")

    df = temp_db.get_current_status_df()
    assert "cadastrado_por" in df.columns
    assert df.iloc[0]["cadastrado_por"] == "Paulo Souza"


def test_upsert_snapshot_updates_same_date(temp_db):
    sid = temp_db.add_sender("5511444444444", "A", "P", "Auto", "ACME")
    today = datetime.date.today().isoformat()

    temp_db.upsert_snapshot(sid, today, "Alta", "Conectado")
    hist = temp_db.get_history_df(sender_id=sid)
    assert len(hist) == 1
    assert hist.iloc[0]["qualidade"] == "Alta"

    temp_db.upsert_snapshot(sid, today, "Baixa", "Conectado")
    hist = temp_db.get_history_df(sender_id=sid)
    assert len(hist) == 1
    assert hist.iloc[0]["qualidade"] == "Baixa"


def test_get_quality_changes_detects_change(temp_db):
    sid = temp_db.add_sender("5511555555555", "A", "P", "Auto", "ACME")
    temp_db.upsert_snapshot(sid, "2024-01-01", "Alta", "Conectado")
    temp_db.upsert_snapshot(sid, "2024-01-02", "Baixa", "Conectado")

    changes = temp_db.get_quality_changes()
    assert len(changes) == 1
    assert changes.iloc[0]["qualidade_anterior"] == "Alta"
    assert changes.iloc[0]["qualidade_atual"] == "Baixa"


def test_get_quality_changes_empty_when_stable(temp_db):
    sid = temp_db.add_sender("5511555555556", "A", "P", "Auto", "ACME")
    temp_db.upsert_snapshot(sid, "2024-01-01", "Alta", "Conectado")
    temp_db.upsert_snapshot(sid, "2024-01-02", "Alta", "Conectado")

    assert temp_db.get_quality_changes().empty


def test_recargas_history_and_latest(temp_db):
    assert temp_db.get_ultima_recarga() is None

    temp_db.add_recarga("2024-01-01", "2024-02-01", "obs 1")
    temp_db.add_recarga("2024-02-01", "2024-03-01", "obs 2")

    assert temp_db.get_ultima_recarga() == ("2024-02-01", "2024-03-01", "obs 2")
    assert len(temp_db.get_recargas_historico()) == 2


def test_get_senders_export_recarga_so_ativos_com_chip(temp_db):
    temp_db.add_sender("5511700000001", "A", "P", "Auto", "ACME", "Vivo", True)
    sem_chip = temp_db.add_sender("5511700000002", "B", "P", "Auto", "ACME", "Claro", False)
    inativo = temp_db.add_sender("5511700000003", "C", "P", "Auto", "ACME", "TIM", True)
    temp_db.set_sender_active(inativo, False)

    export_df = temp_db.get_senders_export_recarga()
    assert list(export_df.columns) == ["Telefone", "Operadora"]
    assert list(export_df["Telefone"]) == ["5511700000001"]
    assert sem_chip not in export_df.index.tolist()  # sanity: não sobrou nada além do 1 esperado
    assert len(export_df) == 1


def test_get_senders_export_semanal_so_ativos(temp_db):
    temp_db.add_sender("5511700000010", "A", "P", "Auto", "PROVEDOR_B_TITULAR", "Vivo", True)
    inativo = temp_db.add_sender("5511700000011", "B", "P", "Viagem", "PROVEDOR_A_RESERVA", "Claro", True)
    temp_db.set_sender_active(inativo, False)

    export_df = temp_db.get_senders_export_semanal()
    assert list(export_df.columns) == ["Sender", "Produto", "WABA", "Operadora"]
    assert list(export_df["Sender"]) == ["5511700000010"]
    assert export_df.iloc[0]["Produto"] == "Auto"
    assert export_df.iloc[0]["WABA"] == "PROVEDOR_B_TITULAR"


def test_get_set_state_roundtrip(temp_db):
    assert temp_db.get_state("chave_inexistente") is None
    assert temp_db.get_state("chave_inexistente", "padrao") == "padrao"

    temp_db.set_state("minha_chave", "valor1")
    assert temp_db.get_state("minha_chave") == "valor1"

    temp_db.set_state("minha_chave", "valor2")
    assert temp_db.get_state("minha_chave") == "valor2"


def test_get_alerts_no_data(temp_db):
    assert temp_db.get_alerts() == [
        {"level": "warning", "message": "🔋 Nenhuma recarga registrada ainda.", "tipo": "recarga"}
    ]


def test_get_alerts_flags_recarga_vencida(temp_db):
    ontem = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    temp_db.add_recarga("2024-01-01", ontem, None)

    alerts = temp_db.get_alerts()
    assert len(alerts) == 1
    assert alerts[0]["level"] == "error"
    assert alerts[0]["tipo"] == "recarga"
    assert "vencida" in alerts[0]["message"]


def test_get_alerts_flags_sinalizado_sender(temp_db):
    sid = temp_db.add_sender("5511666666666", "A", "P", "Auto", "ACME")
    temp_db.upsert_snapshot(sid, datetime.date.today().isoformat(), "Sinalizado", "Conectado")
    futuro = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    temp_db.add_recarga(datetime.date.today().isoformat(), futuro, None)

    alerts = temp_db.get_alerts()
    assert len(alerts) == 1
    assert alerts[0]["level"] == "error"
    assert alerts[0]["tipo"] == "qualidade"
    assert "5511666666666" in alerts[0]["message"]


def test_confirmar_recarga_hoje(temp_db):
    assert temp_db.get_ultima_recarga() is None

    temp_db.confirmar_recarga_hoje()

    hoje = datetime.date.today()
    esperado_proxima = (hoje + datetime.timedelta(days=temp_db.CICLO_RECARGA_DIAS)).isoformat()
    assert temp_db.get_ultima_recarga() == (hoje.isoformat(), esperado_proxima, None)


def test_confirmar_recarga_hoje_ciclo_customizado(temp_db):
    temp_db.confirmar_recarga_hoje(dias_proximo_ciclo=7)
    hoje = datetime.date.today()
    esperado_proxima = (hoje + datetime.timedelta(days=7)).isoformat()
    assert temp_db.get_ultima_recarga() == (hoje.isoformat(), esperado_proxima, None)


def test_waba_legacy_names_are_migrated_on_init(temp_db):
    sid = temp_db.add_sender("5511888888888", "A", "P", "Auto", "IR")
    temp_db.add_sender("5511888888889", "B", "P", "Auto", "Provedor B Reserva")
    temp_db.add_sender("5511888888890", "C", "P", "Auto", "PROVEDOR_B_RESERVA_02")

    temp_db.init_db()

    df = temp_db.get_senders(active_only=False).set_index("id")
    assert df.loc[sid, "waba"] == "PROVEDOR_A_RESERVA"
    assert set(df["waba"]) == {"PROVEDOR_A_RESERVA", "PROVEDOR_B_RESERVA_01", "PROVEDOR_B_RESERVA_02"}


def test_get_alerts_empty_when_all_ok(temp_db):
    sid = temp_db.add_sender("5511777777777", "A", "P", "Auto", "ACME")
    temp_db.upsert_snapshot(sid, datetime.date.today().isoformat(), "Alta", "Conectado")
    futuro = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    temp_db.add_recarga(datetime.date.today().isoformat(), futuro, None)

    assert temp_db.get_alerts() == []


def test_try_claim_state_so_a_primeira_chamada_ganha(temp_db):
    """Regressão: alertas duplicados no Slack porque várias sessões do Streamlit liam "ainda
    não enviei" antes de qualquer uma terminar de enviar. try_claim_state precisa ser atômico —
    só a 1ª chamada com um valor novo pode ganhar, mesmo chamada várias vezes seguidas simulando
    sessões concorrentes."""
    ganhou = [temp_db.try_claim_state("chave_x", "2026-W38") for _ in range(18)]
    assert ganhou.count(True) == 1
    assert ganhou[0] is True


def test_try_claim_state_permite_novo_valor_depois(temp_db):
    assert temp_db.try_claim_state("chave_x", "2026-W38") is True
    assert temp_db.try_claim_state("chave_x", "2026-W38") is False
    assert temp_db.try_claim_state("chave_x", "2026-W39") is True


def test_clear_state_permite_reivindicar_de_novo(temp_db):
    assert temp_db.try_claim_state("chave_x", "2026-09-14") is True
    temp_db.clear_state("chave_x")
    assert temp_db.try_claim_state("chave_x", "2026-09-14") is True
