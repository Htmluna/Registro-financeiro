# Gestão Financeira Pessoal (Flask App)

## Visão Geral

Este é um aplicativo web construído com Flask projetado para ajudar os usuários a gerenciar suas finanças pessoais. Ele permite rastrear despesas e receitas (contas), categorizá-las, gerenciar cartões de crédito e contas bancárias, e visualizar relatórios mensais. A aplicação inclui autenticação de usuários e armazena os dados em um banco de dados SQLite.

## Funcionalidades Principais

*   **Autenticação de Usuários:**
    *   Registro de novos usuários.
    *   Login e Logout seguros.
    *   Redefinição/Alteração de senha para usuários logados.
    *   Proteção de rotas que exigem login (`@login_required`).
*   **Gerenciamento de Contas (Despesas/Receitas):**
    *   Adicionar, Editar e Excluir contas.
    *   Campos: Nome, Valor, Vencimento, Categoria, Parcela Atual/Total, Recorrente, Tipo de Pagamento associado.
    *   Validação de dados dos formulários (incluindo valores monetários e lógica de parcelas).
    *   Formatação de valores monetários para o padrão brasileiro (R$).
    *   Cálculo automático do próximo vencimento para contas recorrentes e parceladas.
    *   Atualização automática do limite disponível (cartão) ou saldo (conta bancária) ao adicionar/editar/excluir contas associadas.
*   **Gerenciamento de Categorias:**
    *   Adicionar, Editar e Excluir categorias personalizadas.
    *   Associação de contas a categorias.
    *   Garante nomes de categoria únicos por usuário.
    *   Ao excluir uma categoria, as contas associadas têm a categoria removida (definida como NULL).
*   **Gerenciamento de Tipos de Pagamento:**
    *   **Cartões de Crédito:**
        *   Adicionar, Editar e Excluir cartões.
        *   Gerenciamento de Limite Total e Limite Disponível.
        *   Limite disponível é ajustado automaticamente com base nas contas associadas.
    *   **Contas Bancárias:**
        *   Adicionar, Editar e Excluir contas bancárias.
        *   Gerenciamento de Saldo.
        *   Saldo é ajustado automaticamente com base nas contas associadas.
    *   Exclusão de tipo de pagamento é impedida se houver contas vinculadas.
*   **Dashboard:**
    *   Exibe contas com vencimento no mês atual e no próximo mês.
    *   Mostra o total geral das contas listadas no período.
    *   Agrupa contas e totais por categoria para o período exibido.
    *   Destaca contas com vencimento anterior à data atual.
    *   **Importante:** Acessar o dashboard dispara a atualização de contas recorrentes/parceladas vencidas.
*   **Relatórios:**
    *   Seleção de período (Mês/Ano) para visualização.
    *   Filtro opcional por uma ou mais categorias.
    *   Exibição do resumo do mês (Total Gasto, Totais por Categoria).
    *   Listagem detalhada das contas do período/filtro selecionado.
    *   Opção de impressão formatada do relatório.
*   **Interface:**
    *   Utiliza Bootstrap para estilização e responsividade.
    *   Usa Font Awesome para ícones.
    *   Máscara de input para valores monetários (via jQuery Mask Plugin).
    *   Modal de confirmação genérico para exclusões (Bootstrap Modal).
    *   Mensagens flash para feedback ao usuário (sucesso, erro, aviso).

## Tecnologias Utilizadas

*   **Backend:** Python 3
*   **Framework Web:** Flask
*   **Autenticação:** Flask-Login
*   **Formulários:** Flask-WTF / WTForms
*   **Banco de Dados:** SQLite 3
*   **Servidor WSGI:** Waitress (para execução)
*   **Frontend:**
    *   HTML5
    *   CSS3 (com Bootstrap 4)
    *   JavaScript (com jQuery, jQuery Mask Plugin, Bootstrap JS)
*   **Templating:** Jinja2
*   **Manipulação de Datas:** `datetime`, `calendar`, `python-dateutil` (para `relativedelta`)
*   **Valores Monetários:** `decimal`

## Estrutura do Projeto (Arquivos Principais)

*   `app.py`: Arquivo principal da aplicação Flask. Contém a configuração do app, definições de rotas (views), lógica de negócios e interação com outras partes.
*   `database.py`: Contém funções para interagir com o banco de dados SQLite (conexão, inicialização de schema, CRUD para os modelos, verificação/atualização de schema).
*   `models.py`: Define as classes que representam as estruturas de dados (Conta, User, Categoria, Cartao, ContaBancaria).
*   `forms.py`: Define os formulários web usando Flask-WTF/WTForms, incluindo validações.
*   `templates/`: Diretório contendo os arquivos HTML com Jinja2 para renderizar as páginas web.
    *   `base.html`: Template base herdado por outras páginas, contém a estrutura comum (sidebar, navbar, scripts base).
    *   Outros arquivos `.html` para cada página/funcionalidade (ex: `index.html`, `login.html`, `add_conta.html`, etc.).
*   `contas.db`: Arquivo do banco de dados SQLite (criado na primeira execução, se não existir).
*   `requirements.txt` (Recomendado): Arquivo listando as dependências Python do projeto (Flask, Flask-Login, Flask-WTF, Werkzeug, python-dateutil, Waitress, etc.).

## Como Funciona

1.  **Inicialização:** Quando `app.py` é executado, ele configura a instância do Flask, o LoginManager e, crucialmente, chama `check_and_apply_schema_updates()` de `database.py`. Isso garante que o arquivo `contas.db` exista e que todas as tabelas e colunas necessárias estejam criadas ou atualizadas.
2.  **Requisição e Roteamento:** O Flask recebe uma requisição HTTP (ex: um usuário acessando `/`). Ele direciona a requisição para a função Python associada à rota (ex: `index()` para a rota `/`).
3.  **Autenticação:** Rotas protegidas com `@login_required` verificam se o usuário está logado usando Flask-Login. Se não estiver, ele é redirecionado para a página de login (`/login`). O `load_user` busca o usuário no DB com base no ID armazenado na sessão.
4.  **Interação com Banco de Dados:**
    *   As funções em `database.py` são usadas para realizar operações CRUD (Criar, Ler, Atualizar, Deletar) no banco de dados SQLite.
    *   A conexão com o banco é gerenciada por requisição usando `g` e as funções `get_db()` e `close_db()` para eficiência.
    *   Os dados lidos do banco são frequentemente convertidos em instâncias das classes definidas em `models.py` (ex: `Conta`, `Categoria`).
5.  **Formulários:**
    *   Para páginas com formulários (adicionar/editar), uma instância do formulário correspondente de `forms.py` é criada.
    *   Flask-WTF lida com a renderização dos campos HTML (incluindo o token CSRF para segurança) e a validação dos dados enviados pelo usuário via POST.
    *   Validadores customizados (como `decimal_field_validator`) garantem a qualidade dos dados.
6.  **Lógica de Negócios:**
    *   A função `atualizar_limite_saldo` é chamada ao adicionar/editar/excluir contas para manter a consistência dos limites de cartão e saldos de conta bancária.
    *   A função `update_parcelas_recorrentes` é chamada no início da rota `index` para avançar o vencimento e/ou parcela de contas recorrentes ou parceladas que já passaram da data de vencimento.
    *   Cálculos de totais e agrupamentos para o dashboard e relatórios são feitos nas respectivas rotas.
7.  **Renderização de Templates:**
    *   Após processar a lógica, a rota geralmente chama `render_template()`, passando o nome do arquivo HTML (em `templates/`) e quaisquer dados necessários (ex: lista de contas, objeto de formulário, totais).
    *   Jinja2 processa o template, executando loops (`{% for %}`), condicionais (`{% if %}`), herdando de `base.html` (`{% extends %}`), preenchendo blocos (`{% block %}`) e exibindo variáveis (`{{ variavel }}`).
    *   Funções auxiliares injetadas via `context_processor` (como `formatar_br`) podem ser usadas diretamente nos templates.
8.  **Resposta:** O HTML renderizado é enviado de volta ao navegador do usuário como a resposta HTTP. O navegador então exibe a página. JavaScript (jQuery, Mask) é executado no lado do cliente para funcionalidades como máscaras de input e modais.

## Configuração e Execução

1.  **Pré-requisitos:** Certifique-se de ter o Python 3 instalado.
2.  **Clone o Repositório:** `git clone <url_do_repositorio>`
3.  **Navegue até o Diretório:** `cd <nome_do_diretorio>`
4.  **(Recomendado) Crie e Ative um Ambiente Virtual:**
    *   `python -m venv venv`
    *   No Windows: `venv\Scripts\activate`
    *   No Linux/macOS: `source venv/bin/activate`
5.  **Instale as Dependências:** (Assumindo que existe um `requirements.txt`)
    *   `pip install -r requirements.txt`
    *   *Se não houver `requirements.txt`, instale manualmente: `pip install Flask Flask-Login Flask-WTF Werkzeug python-dateutil Waitress decimal`*
6.  **Configure a Chave Secreta:** É **essencial** definir uma chave secreta segura para produção. Defina a variável de ambiente `FLASK_SECRET_KEY`:
    *   No Linux/macOS: `export FLASK_SECRET_KEY='sua_chave_secreta_super_segura'`
    *   No Windows (cmd): `set FLASK_SECRET_KEY=sua_chave_secreta_super_segura`
    *   No Windows (PowerShell): `$env:FLASK_SECRET_KEY='sua_chave_secreta_super_segura'`
    *   *Para desenvolvimento, o fallback no `app.py` funcionará, mas não é seguro.*
7.  **Execute a Aplicação:**
    *   `python app.py`
8.  **Acesse no Navegador:** Abra seu navegador e vá para `http://localhost:5000` ou `http://127.0.0.1:5000`. O servidor Waitress também ouvirá em `0.0.0.0`, tornando-o acessível por outros dispositivos na mesma rede usando o IP da máquina que está rodando o app (ex: `http://192.168.1.100:5000`).

## Banco de Dados

*   A aplicação utiliza SQLite, armazenando todos os dados no arquivo `contas.db` no mesmo diretório do `app.py`.
*   O schema é inicializado e verificado/atualizado automaticamente na inicialização da aplicação pela função `check_and_apply_schema_updates` em `database.py`.
*   Relações entre tabelas (usuários, categorias, tipos de pagamento, contas) são definidas usando chaves estrangeiras (`FOREIGN KEY`).
*   As opções `ON DELETE CASCADE` e `ON DELETE SET NULL` são usadas para manter a integridade referencial ao excluir usuários, categorias ou tipos de pagamento.
