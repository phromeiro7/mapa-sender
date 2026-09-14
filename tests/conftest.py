import pytest


@pytest.fixture(autouse=True)
def sem_slack_real(monkeypatch):
    """Garante que nenhum teste bata na API real do Slack.

    slack_alert.py carrega o .env de verdade via load_dotenv(); se a máquina de quem roda os
    testes tiver SLACK_BOT_TOKEN/SLACK_CHANNEL configurados para uso normal do app, qualquer
    AppTest que renderize uma página (todas chamam render_sidebar_alerts() no sidebar) dispararia
    chamadas de rede reais para verificar recarga/relatório semanal — lento e flaky. Testes que
    querem exercitar o envio pro Slack usam monkeypatch.setenv(...) explicitamente por cima disso.
    """
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_CHANNEL", raising=False)
