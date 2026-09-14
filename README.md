# Mapa Sender

Projeto pessoal (Streamlit) para controle de status, qualidade e recargas de uma frota de
números (senders) de WhatsApp Business Platform — inventário, ciclo de recarga de chip,
histórico de qualidade e alertas automáticos no Slack.

> Este é um projeto de portfólio: a ideia nasceu de um problema real que resolvi no trabalho,
> mas o código aqui usa nomes de empresa, WABAs e dados fictícios (veja `seed_demo_data.py`
> para popular o app com alguns senders de exemplo).

## Funcionalidades

- **Painel** (página principal) — cards com situação atual de cada sender, busca, filtro por
  WABA, destaque para mudanças de qualidade e tendência dos últimos dias. É também onde se
  cadastra (botão "➕ Adicionar sender") e gerencia cada sender (botão "✏️ Editar" no card abre
  um diálogo para editar, desativar/reativar ou excluir).
- **Lançamento Diário** — registrar qualidade/status do dia para cada sender. Todo sender já
  vem marcado como Alta/Conectado por padrão; só é preciso alterar quem estiver diferente
  disso no site da Meta.
- **Recargas** — controle de quando recarregar os chips dos senders, com confirmação em 1
  clique e exportação de CSV.
- **Histórico** — consultar e exportar o log completo de lançamentos.

Números de sender não podem se repetir — o cadastro/edição valida isso antes de salvar
(ignorando diferenças de formatação, como espaços/traços/parênteses).

### WABAs padronizados

Os nomes de WABA são fixos (selecionados por dropdown no cadastro, não texto livre):
`PROVEDOR_A_RESERVA`, `PROVEDOR_A_TITULAR`, `PROVEDOR_B_TITULAR`, `PROVEDOR_B_RESERVA_01`, `PROVEDOR_B_RESERVA_02`.
Nomes antigos/informais usados antes da padronização (`IR`, `IT`, `KT`, `Provedor B Reserva`) são
migrados automaticamente para o nome canônico na inicialização do banco.

## Stack

- [Streamlit](https://streamlit.io/) (UI)
- [pandas](https://pandas.pydata.org/)
- SQLite local (`data/senders.db`, criado automaticamente na primeira execução)
- [requests](https://requests.readthedocs.io/) + [python-dotenv](https://saurabh-kumar.com/python-dotenv/) (integração com Slack)

## Como rodar

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run Painel.py
```

Ou, no Windows, basta executar `iniciar.bat`.

O banco de dados SQLite (`data/senders.db`) é criado automaticamente na primeira execução e
**não é versionado** (veja `.gitignore`) — então o app começa vazio. Para ver o Painel já
populado com alguns senders fictícios:

```powershell
python seed_demo_data.py
```

## Testes

```powershell
pip install -r requirements-dev.txt
pytest
```

A suíte cobre a camada de dados (`tests/test_db.py`), a integração com o Slack
(`tests/test_slack_alert.py`) e o fluxo completo do Lançamento Diário via
`streamlit.testing.v1.AppTest` (`tests/test_lancamento_diario.py`). Roda automaticamente a
cada push/PR na `main` (veja `.github/workflows/tests.yml`).

## Integração com o Slack (opcional)

O app manda automaticamente três tipos de notificação — todas verificadas sempre que alguém
abre qualquer página, sem precisar de servidor separado:

- **Alerta de recarga**, com o CSV de senders/operadoras anexado — exatamente 2 vezes por
  ciclo: 3 dias antes do vencimento e no dia do vencimento. Fora desses dois dias fica em
  silêncio no Slack, mesmo que a recarga fique vencida sem ninguém confirmar (o aviso dentro
  do app continua normal).
- **Mudanças de qualidade do dia**, sempre que alguém salva o Lançamento Diário.
- **Relatório semanal em CSV** (Sender, Produto, WABA, Operadora) de todo sender ativo, toda
  segunda-feira — se ninguém abrir o app naquela segunda, a semana passa em silêncio, sem
  envio atrasado.

Para ativar:

1. Crie um Slack App em [api.slack.com/apps](https://api.slack.com/apps) → "From scratch".
2. Em **OAuth & Permissions**, adicione os escopos de Bot Token `chat:write` e `files:write`,
   depois instale o app no workspace e copie o **Bot User OAuth Token** (`xoxb-...`).
3. Convide o bot para o canal onde as notificações devem cair (`/invite @nome-do-bot` no Slack).
4. Copie o arquivo de exemplo e preencha:

   ```powershell
   Copy-Item .env.example .env
   ```

   ```
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_CHANNEL=C0123456789
   ```

   `SLACK_CHANNEL` pode ser o ID do canal (recomendado, veja em "Detalhes do canal" no Slack) ou
   `#nome-do-canal`. O arquivo `.env` é ignorado pelo git e **nunca** deve ser commitado.

Sem esse arquivo (ou sem as duas variáveis preenchidas), o app funciona normalmente e todas as
notificações ficam só desativadas.

## Estrutura

```
Painel.py                   # página inicial (Painel) — cadastro, edição, situação atual
db.py                       # camada de acesso a dados (SQLite)
alerts.py                   # alertas exibidos na sidebar de todas as páginas
slack_alert.py              # notificações automáticas no Slack (recarga, mudanças, semanal)
styles.py                   # CSS compartilhado (badges, tags, linhas de mudança)
pages/                      # demais páginas (Lançamento Diário, Recargas, Histórico)
tests/                      # suíte pytest (dados, Slack, fluxo do Lançamento Diário)
data/                       # banco de dados local (ignorado pelo git)
.streamlit/config.toml      # tema e configurações do Streamlit
```
