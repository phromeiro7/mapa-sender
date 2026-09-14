"""Camada de acesso a dados do Mapa Sender (SQLite local)."""
import datetime
import re
import sqlite3
import os
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "senders.db")

QUALIDADE_OPTIONS = ["Alta", "Média", "Baixa", "Sinalizado"]
STATUS_OPTIONS = ["Conectado", "Desativado"]
OPERADORA_OPTIONS = ["", "Claro", "Vivo", "TIM"]

WABA_OPTIONS = ["PROVEDOR_A_RESERVA", "PROVEDOR_A_TITULAR", "PROVEDOR_B_TITULAR", "PROVEDOR_B_RESERVA_01", "PROVEDOR_B_RESERVA_02"]

# Nomes antigos/informais usados no cadastro antes da padronização -> nome canônico atual.
_WABA_LEGACY_MAP = {
    "IR": "PROVEDOR_A_RESERVA",
    "IT": "PROVEDOR_A_TITULAR",
    "KT": "PROVEDOR_B_TITULAR",
    "Provedor B Reserva": "PROVEDOR_B_RESERVA_01",
    "Provedor B reserva": "PROVEDOR_B_RESERVA_01",
    "provedor b reserva": "PROVEDOR_B_RESERVA_01",
}

ICON_MAP = {"Alta": "✓", "Média": "▲", "Baixa": "⮾", "Sinalizado": "⚠"}
QUALIDADE_COLORS = {
    "Alta": "#3fb950",
    "Média": "#d29922",
    "Baixa": "#db6d28",
    "Sinalizado": "#f85149",
}
STATUS_COLORS = {"Conectado": "#3fb950", "Desativado": "#8b949e"}
QUALIDADE_RANK = {"Sinalizado": 0, "Baixa": 1, "Média": 2, "Alta": 3}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _column_names(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _apenas_digitos(numero):
    return re.sub(r"\D", "", numero or "")


def formatar_numero(numero):
    """Padroniza um número de sender para +55 DD NNNNN-NNNN (celular) ou +55 DD NNNN-NNNN (fixo).

    Aceita o número com ou sem código do país, com espaços/traços/parênteses em qualquer lugar.
    Quando não reconhece o padrão (DDD + 8 ou 9 dígitos), devolve só os dígitos, sem inventar formatação.
    """
    digitos = _apenas_digitos(numero)
    if not digitos:
        return (numero or "").strip()

    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]

    if len(digitos) == 11:
        ddd, parte1, parte2 = digitos[:2], digitos[2:7], digitos[7:]
        return f"+55 {ddd} {parte1}-{parte2}"
    if len(digitos) == 10:
        ddd, parte1, parte2 = digitos[:2], digitos[2:6], digitos[6:]
        return f"+55 {ddd} {parte1}-{parte2}"

    return digitos


def _migrate(conn):
    """Remove colunas descontinuadas de bancos criados por versões anteriores do app."""
    sender_cols = _column_names(conn, "senders")
    for col in ("logo", "moments", "answers"):
        if col in sender_cols:
            conn.execute(f"ALTER TABLE senders DROP COLUMN {col}")

    if "operadora" not in sender_cols:
        conn.execute("ALTER TABLE senders ADD COLUMN operadora TEXT")

    if "possui_chip" not in sender_cols:
        conn.execute("ALTER TABLE senders ADD COLUMN possui_chip INTEGER NOT NULL DEFAULT 1")

    if "cadastrado_por" not in sender_cols:
        conn.execute("ALTER TABLE senders ADD COLUMN cadastrado_por TEXT")

    snapshot_cols = _column_names(conn, "snapshots")
    for col in ("flag", "limite"):
        if col in snapshot_cols:
            conn.execute(f"ALTER TABLE snapshots DROP COLUMN {col}")

    if "status" in snapshot_cols:
        conn.execute("UPDATE snapshots SET status='Conectado' WHERE status='Ativado'")

    for legacy, canonico in _WABA_LEGACY_MAP.items():
        conn.execute("UPDATE senders SET waba=? WHERE waba=?", (canonico, legacy))

    for sender_id, numero in conn.execute("SELECT id, numero FROM senders").fetchall():
        formatado = formatar_numero(numero)
        if formatado and formatado != numero:
            try:
                conn.execute("UPDATE senders SET numero=? WHERE id=?", (formatado, sender_id))
            except sqlite3.IntegrityError:
                pass  # já existe outro sender com o mesmo número normalizado; mantém como estava

    conn.commit()


def init_db():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS senders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL UNIQUE,
            display_name TEXT,
            parceiro_segmento TEXT,
            setor TEXT,
            waba TEXT,
            operadora TEXT,
            possui_chip INTEGER NOT NULL DEFAULT 1,
            cadastrado_por TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL REFERENCES senders(id) ON DELETE CASCADE,
            data TEXT NOT NULL,
            qualidade TEXT,
            status TEXT,
            UNIQUE(sender_id, data)
        );

        CREATE TABLE IF NOT EXISTS recargas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_recarga TEXT NOT NULL,
            proxima_recarga TEXT NOT NULL,
            observacao TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS app_state (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );
        """
    )
    conn.commit()
    _migrate(conn)
    conn.close()


# ---------- Senders ----------

def add_sender(numero, display_name, parceiro_segmento, setor, waba, operadora=None, possui_chip=True,
               cadastrado_por=None):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO senders (numero, display_name, parceiro_segmento, setor, waba, operadora, possui_chip,
           cadastrado_por)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (numero, display_name, parceiro_segmento, setor, waba, operadora, int(possui_chip), cadastrado_por),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_sender(sender_id, numero, display_name, parceiro_segmento, setor, waba, operadora=None, possui_chip=True,
                   cadastrado_por=None):
    conn = get_connection()
    conn.execute(
        """UPDATE senders SET numero=?, display_name=?, parceiro_segmento=?, setor=?, waba=?, operadora=?,
           possui_chip=?, cadastrado_por=? WHERE id=?""",
        (numero, display_name, parceiro_segmento, setor, waba, operadora, int(possui_chip), cadastrado_por, sender_id),
    )
    conn.commit()
    conn.close()


def set_sender_active(sender_id, ativo):
    conn = get_connection()
    conn.execute("UPDATE senders SET ativo=? WHERE id=?", (int(ativo), sender_id))
    conn.commit()
    conn.close()


def delete_sender(sender_id):
    conn = get_connection()
    conn.execute("DELETE FROM senders WHERE id=?", (sender_id,))
    conn.commit()
    conn.close()


def get_sender_by_id(sender_id):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM senders WHERE id=?", conn, params=[sender_id])
    conn.close()
    return df.iloc[0] if not df.empty else None


def numero_existe(numero, excluir_id=None):
    """True se já existe (outro) sender com esse número, ignorando espaços/traços/parênteses."""
    alvo = _apenas_digitos(numero)
    if not alvo:
        return False
    conn = get_connection()
    rows = conn.execute("SELECT id, numero FROM senders").fetchall()
    conn.close()
    for outro_id, outro_numero in rows:
        if excluir_id is not None and outro_id == excluir_id:
            continue
        if _apenas_digitos(outro_numero) == alvo:
            return True
    return False


def get_senders(active_only=True):
    conn = get_connection()
    query = "SELECT * FROM senders"
    if active_only:
        query += " WHERE ativo = 1"
    query += " ORDER BY setor, parceiro_segmento"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


# ---------- Snapshots ----------


def upsert_snapshot(sender_id, data_iso, qualidade, status):
    conn = get_connection()
    conn.execute(
        """INSERT INTO snapshots (sender_id, data, qualidade, status)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(sender_id, data) DO UPDATE SET
             qualidade=excluded.qualidade, status=excluded.status""",
        (sender_id, data_iso, qualidade, status),
    )
    conn.commit()
    conn.close()


def get_current_status_df():
    """Último snapshot conhecido de cada sender ativo, junto com dados de cadastro."""
    conn = get_connection()
    query = """
        SELECT s.id AS sender_id, s.numero, s.display_name, s.parceiro_segmento,
               s.setor, s.waba, s.operadora, s.possui_chip, s.cadastrado_por,
               sn.data, sn.qualidade, sn.status
        FROM senders s
        LEFT JOIN snapshots sn ON sn.id = (
            SELECT id FROM snapshots WHERE sender_id = s.id ORDER BY data DESC LIMIT 1
        )
        WHERE s.ativo = 1
        ORDER BY s.setor, s.parceiro_segmento
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_snapshots_for_dates(sender_ids, dates_iso):
    if not sender_ids or not dates_iso:
        return pd.DataFrame(columns=["sender_id", "data", "qualidade", "status"])
    conn = get_connection()
    placeholders_ids = ",".join("?" * len(sender_ids))
    placeholders_dates = ",".join("?" * len(dates_iso))
    query = f"""
        SELECT sender_id, data, qualidade, status FROM snapshots
        WHERE sender_id IN ({placeholders_ids}) AND data IN ({placeholders_dates})
    """
    df = pd.read_sql_query(query, conn, params=[*sender_ids, *dates_iso])
    conn.close()
    return df


def get_quality_changes():
    """Senders ativos cujo lançamento mais recente mudou de qualidade em relação ao anterior."""
    conn = get_connection()
    query = """
        SELECT s.id AS sender_id, s.numero, s.setor, s.waba,
               sn.data AS data_atual, sn.qualidade AS qualidade_atual,
               (
                   SELECT qualidade FROM snapshots sn2
                   WHERE sn2.sender_id = s.id AND sn2.data < sn.data
                   ORDER BY sn2.data DESC LIMIT 1
               ) AS qualidade_anterior
        FROM senders s
        JOIN snapshots sn ON sn.id = (
            SELECT id FROM snapshots WHERE sender_id = s.id ORDER BY data DESC LIMIT 1
        )
        WHERE s.ativo = 1
        ORDER BY s.setor, s.numero
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df = df[df["qualidade_anterior"].notna() & (df["qualidade_anterior"] != df["qualidade_atual"])]
    return df.reset_index(drop=True)


# ---------- Recargas ----------

CICLO_RECARGA_DIAS = 45


def add_recarga(data_recarga_iso, proxima_recarga_iso, observacao=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO recargas (data_recarga, proxima_recarga, observacao) VALUES (?, ?, ?)",
        (data_recarga_iso, proxima_recarga_iso, observacao),
    )
    conn.commit()
    conn.close()


def confirmar_recarga_hoje(dias_proximo_ciclo=CICLO_RECARGA_DIAS):
    """Atalho de 1 clique: registra a recarga de hoje e já agenda a próxima."""
    hoje = datetime.date.today()
    proxima = hoje + datetime.timedelta(days=dias_proximo_ciclo)
    add_recarga(hoje.isoformat(), proxima.isoformat(), None)


def get_ultima_recarga():
    conn = get_connection()
    row = conn.execute(
        "SELECT data_recarga, proxima_recarga, observacao FROM recargas ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row  # (data_recarga, proxima_recarga, observacao) ou None


def get_recargas_historico():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT data_recarga, proxima_recarga, observacao FROM recargas ORDER BY id DESC", conn
    )
    conn.close()
    return df


def get_senders_export_recarga():
    """Telefone + operadora dos senders ativos que possuem chip, prontos para recarga."""
    df = get_senders(active_only=True)
    df = df[df["possui_chip"] == 1]
    return df[["numero", "operadora"]].rename(columns={"numero": "Telefone", "operadora": "Operadora"})


def get_senders_export_semanal():
    """Sender, produto (tipo/setor), WABA e operadora de todo sender ativo — relatório semanal."""
    df = get_senders(active_only=True)
    return df[["numero", "setor", "waba", "operadora"]].rename(
        columns={"numero": "Sender", "setor": "Produto", "waba": "WABA", "operadora": "Operadora"}
    )


# ---------- Estado interno do app (ex.: dedupe de alertas já enviados) ----------

def get_state(chave, default=None):
    conn = get_connection()
    row = conn.execute("SELECT valor FROM app_state WHERE chave=?", (chave,)).fetchone()
    conn.close()
    return row[0] if row else default


def set_state(chave, valor):
    conn = get_connection()
    conn.execute(
        "INSERT INTO app_state (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
        (chave, valor),
    )
    conn.commit()
    conn.close()


def get_history_df(sender_id=None, data_inicio=None, data_fim=None):
    conn = get_connection()
    query = """
        SELECT sn.data, s.numero, s.display_name, s.parceiro_segmento, s.setor, s.waba,
               sn.qualidade, sn.status
        FROM snapshots sn JOIN senders s ON s.id = sn.sender_id
        WHERE 1=1
    """
    params = []
    if sender_id:
        query += " AND sn.sender_id = ?"
        params.append(sender_id)
    if data_inicio:
        query += " AND sn.data >= ?"
        params.append(data_inicio)
    if data_fim:
        query += " AND sn.data <= ?"
        params.append(data_fim)
    query += " ORDER BY sn.data DESC, s.setor"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


# ---------- Alertas (usados em todas as páginas via alerts.py) ----------

def get_alerts():
    """Alertas ativos no momento: recarga vencida/vencendo e senders sinalizados.

    Retorna uma lista de dicts {"level": "error"|"warning", "message": str, "tipo": str}.
    """
    alerts = []

    ultima = get_ultima_recarga()
    if ultima is None:
        alerts.append({"level": "warning", "message": "🔋 Nenhuma recarga registrada ainda.", "tipo": "recarga"})
    else:
        _, proxima_recarga, _ = ultima
        dias = (datetime.date.fromisoformat(proxima_recarga) - datetime.date.today()).days
        data_fmt = datetime.date.fromisoformat(proxima_recarga).strftime("%d/%m/%Y")
        if dias < 0:
            alerts.append(
                {
                    "level": "error",
                    "message": f"🔴 Recarga vencida desde {data_fmt} ({abs(dias)} dia(s) atrás).",
                    "tipo": "recarga",
                }
            )
        elif dias <= 3:
            alerts.append(
                {
                    "level": "warning",
                    "message": f"🟡 Recarga vence em {data_fmt} (faltam {dias} dia(s)).",
                    "tipo": "recarga",
                }
            )

    current_df = get_current_status_df()
    sinalizados = current_df[current_df["qualidade"] == "Sinalizado"]
    if not sinalizados.empty:
        numeros = ", ".join(sinalizados["numero"].tolist())
        alerts.append(
            {
                "level": "error",
                "message": f"⚠ {len(sinalizados)} sender(s) sinalizado(s): {numeros}",
                "tipo": "qualidade",
            }
        )

    return alerts
