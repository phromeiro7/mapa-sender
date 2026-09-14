"""Popula o banco local com senders fictícios, só para demonstração do Painel.

Uso: python seed_demo_data.py
"""
import datetime

from db import init_db, add_sender, upsert_snapshot, get_senders

DEMO_SENDERS = [
    ("+55 11 98765-4321", "Acme", "Vendas", "Auto", "PROVEDOR_A_TITULAR", "Vivo", True, "Ana"),
    ("+55 11 91234-5678", "Acme", "Suporte", "Chatbot", "PROVEDOR_A_TITULAR", "Claro", True, "Bruno"),
    ("+55 21 99887-6655", "Acme", "Cobrança", "Auto", "PROVEDOR_A_RESERVA", "TIM", True, "Ana"),
    ("+55 31 98888-2222", "Acme", "Marketing", "Auto", "PROVEDOR_B_TITULAR", "Vivo", True, "Carla"),
    ("+55 41 97777-3333", "Acme", "Fallback", "Auto", "PROVEDOR_B_RESERVA_01", "Claro", False, "Bruno"),
]

DEMO_QUALIDADE = ["Alta", "Alta", "Média", "Baixa", "Sinalizado"]
DEMO_STATUS = ["Conectado", "Conectado", "Conectado", "Conectado", "Desativado"]


def main():
    init_db()

    if not get_senders(active_only=False).empty:
        print("O banco já tem senders cadastrados — nada foi alterado.")
        return

    hoje = datetime.date.today().isoformat()
    for (numero, nome, parceiro, setor, waba, operadora, possui_chip, cadastrado_por), qualidade, status in zip(
        DEMO_SENDERS, DEMO_QUALIDADE, DEMO_STATUS
    ):
        sender_id = add_sender(numero, nome, parceiro, setor, waba, operadora, possui_chip, cadastrado_por)
        upsert_snapshot(sender_id, hoje, qualidade, status)

    print(f"{len(DEMO_SENDERS)} senders fictícios cadastrados. Rode `streamlit run Painel.py` para ver.")


if __name__ == "__main__":
    main()
