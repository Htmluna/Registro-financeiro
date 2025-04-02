# database.py
import sqlite3
from models import Conta, User, Cartao, ContaBancaria, Categoria # Importa todos os modelos definidos em models.py
from datetime import date, datetime # Garante que date e datetime estão importados para manipulação de datas
import decimal # Importa decimal para tratamento preciso de valores monetários

# Define o nome do arquivo do banco de dados SQLite
DB_FILE = 'contas.db'

def get_db_connection():
    """Estabelece e retorna uma conexão com o banco de dados SQLite.
       Configura a conexão para retornar linhas como objetos semelhantes a dicionários
       e habilita o suporte a chaves estrangeiras.
    """
    conn = sqlite3.connect(DB_FILE) # Conecta ao arquivo do banco de dados
    # Configura a fábrica de linhas para sqlite3.Row, permitindo acesso às colunas por nome (ex: row['nome'])
    conn.row_factory = sqlite3.Row
    # Habilita a verificação de restrições de chave estrangeira (FOREIGN KEY)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn # Retorna o objeto de conexão

def init_db():
    """Inicializa o schema do banco de dados.
       Cria as tabelas necessárias ('users', 'categorias', 'tipos_pagamento', 'contas')
       se elas ainda não existirem.
    """
    conn = get_db_connection() # Obtém uma conexão com o DB
    cursor = conn.cursor()     # Cria um cursor para executar comandos SQL

    # --- Criação da Tabela de Usuários ---
    # Guarda informações de login dos usuários.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- Chave primária única e auto-incremental
            username TEXT UNIQUE NOT NULL,        -- Nome de usuário (deve ser único)
            password TEXT NOT NULL                 -- Hash da senha do usuário
        )
    """)

    # --- Criação da Tabela de Categorias ---
    # Armazena as categorias criadas pelos usuários para classificar contas.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- Chave primária da categoria
            nome TEXT NOT NULL,                   -- Nome da categoria (ex: "Alimentação", "Transporte")
            user_id INTEGER NOT NULL,             -- Chave estrangeira referenciando o usuário dono da categoria
            UNIQUE(nome, user_id),                -- Garante que um mesmo usuário não pode ter duas categorias com o mesmo nome
            FOREIGN KEY (user_id) REFERENCES users(id) -- Define a relação com a tabela 'users'
                ON DELETE CASCADE                     -- IMPORTANTE: Se um usuário for deletado, suas categorias também serão (efeito cascata)
        )
    """)

    # --- Criação da Tabela de Tipos de Pagamento ---
    # Armazena informações de Cartões de Crédito e Contas Bancárias usados para pagar/receber contas.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tipos_pagamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- Chave primária do tipo de pagamento
            nome TEXT NOT NULL,                   -- Nome dado pelo usuário (ex: "Cartão Nubank", "Conta Itaú")
            tipo TEXT NOT NULL,                   -- Tipo: 'cartao' ou 'conta' (para diferenciar a lógica)
            limite REAL,                          -- Limite total (usado apenas para 'cartao', armazena como número real/float)
            limite_disponivel REAL,               -- Limite disponível (usado apenas para 'cartao', armazena como real/float)
            saldo REAL,                           -- Saldo atual (usado apenas para 'conta', armazena como real/float)
            user_id INTEGER NOT NULL,             -- Chave estrangeira referenciando o usuário dono
            FOREIGN KEY (user_id) REFERENCES users(id) -- Define a relação com 'users'
                ON DELETE CASCADE                     -- IMPORTANTE: Se um usuário for deletado, seus tipos de pagamento também serão
        )
    """)

    # --- Criação da Tabela de Contas (Despesas/Receitas) ---
    # Armazena os registros de contas a pagar ou receber.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, -- Chave primária da conta
            nome TEXT NOT NULL,                   -- Descrição da conta (ex: "Supermercado", "Salário")
            valor REAL NOT NULL,                  -- Valor da conta (armazena como número real/float)
            vencimento TEXT NOT NULL,             -- Data de vencimento (armazena como texto no formato ISO 'YYYY-MM-DD')
            categoria_id INTEGER,                 -- Chave estrangeira referenciando a categoria (opcional)
            parcela_atual INTEGER,                -- Número da parcela atual (se for conta parcelada)
            total_parcelas INTEGER,               -- Número total de parcelas (se for conta parcelada)
            user_id INTEGER NOT NULL,             -- Chave estrangeira referenciando o usuário dono
            recorrente INTEGER DEFAULT 0,         -- Flag para conta recorrente (0 = Não, 1 = Sim)
            tipo_pagamento_id INTEGER,            -- Chave estrangeira referenciando o tipo de pagamento usado (opcional)
            FOREIGN KEY (user_id) REFERENCES users(id) -- Relação com 'users'
                ON DELETE CASCADE,                    -- Deleta contas se o usuário for deletado
            FOREIGN KEY (tipo_pagamento_id) REFERENCES tipos_pagamento(id) -- Relação com 'tipos_pagamento'
                ON DELETE SET NULL,                   -- IMPORTANTE: Se o tipo de pagamento for deletado, define este campo como NULL na conta (não deleta a conta)
            FOREIGN KEY (categoria_id) REFERENCES categorias(id) -- Relação com 'categorias'
                ON DELETE SET NULL                    -- IMPORTANTE: Se a categoria for deletada, define este campo como NULL na conta (não deleta a conta)
        )
    """)

    conn.commit() # Salva todas as alterações (criação das tabelas) no banco de dados
    conn.close()  # Fecha a conexão
    print("Schema do banco de dados inicializado/verificado com sucesso.")


# --- Funções CRUD (Create, Read, Update, Delete) para Categorias ---

def create_categoria(nome, user_id):
    """Cria uma nova categoria para um usuário específico no banco de dados.

    Args:
        nome (str): O nome da nova categoria.
        user_id (int): O ID do usuário ao qual a categoria pertence.

    Returns:
        int: O ID da categoria recém-criada se sucesso, None caso contrário (ex: nome duplicado).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Tenta inserir a nova categoria
        cursor.execute(
            "INSERT INTO categorias (nome, user_id) VALUES (?, ?)",
            (nome, user_id)
        )
        conn.commit() # Salva a inserção
        categoria_id = cursor.lastrowid # Obtém o ID da linha recém-inserida
        conn.close()
        return categoria_id # Retorna o ID da nova categoria
    except sqlite3.IntegrityError:
        # Captura erro se a restrição UNIQUE(nome, user_id) for violada (categoria duplicada para o usuário)
        print(f"Erro de Integridade: Categoria '{nome}' já existe para o usuário ID {user_id}.")
        conn.close()
        return None # Retorna None indicando falha
    except Exception as e:
        # Captura outros erros possíveis
        print(f"Erro inesperado ao criar categoria: {e}")
        conn.rollback() # Desfaz a tentativa de inserção
        conn.close()
        return None

def get_categorias_by_user(user_id):
    """Busca todas as categorias pertencentes a um usuário específico.

    Args:
        user_id (int): O ID do usuário.

    Returns:
        list[Categoria]: Uma lista de objetos Categoria, ordenada por nome.
                         Retorna lista vazia se o usuário não tiver categorias ou ocorrer erro.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Seleciona todas as colunas da tabela categorias onde user_id corresponde, ordenado por nome
        cursor.execute("SELECT * FROM categorias WHERE user_id = ? ORDER BY nome", (user_id,))
        # Cria uma lista de objetos Categoria usando os dados de cada linha retornada
        categorias = [Categoria(row['id'], row['nome'], row['user_id']) for row in cursor.fetchall()]
        conn.close()
        return categorias
    except Exception as e:
        print(f"Erro ao buscar categorias para user ID {user_id}: {e}")
        if conn: conn.close()
        return [] # Retorna lista vazia em caso de erro

def get_categoria_by_id(categoria_id, user_id):
    """Busca uma categoria específica pelo seu ID, garantindo que ela pertença ao usuário informado.

    Args:
        categoria_id (int): O ID da categoria a ser buscada.
        user_id (int): O ID do usuário que deve ser o dono da categoria.

    Returns:
        Categoria or None: O objeto Categoria se encontrado e pertencente ao usuário, None caso contrário.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Busca a categoria pelo ID E pelo user_id
        cursor.execute("SELECT * FROM categorias WHERE id = ? AND user_id = ?", (categoria_id, user_id))
        row = cursor.fetchone() # Pega a primeira (e única) linha correspondente
        conn.close()
        if row:
            # Se encontrou, cria e retorna o objeto Categoria
            return Categoria(row['id'], row['nome'], row['user_id'])
        return None # Retorna None se não encontrou
    except Exception as e:
        print(f"Erro ao buscar categoria ID {categoria_id} para user ID {user_id}: {e}")
        if conn: conn.close()
        return None

def get_categoria_by_name_and_user(nome, user_id):
    """Verifica se uma categoria com um nome específico já existe para um determinado usuário.
       Útil para evitar a criação de categorias duplicadas.

    Args:
        nome (str): O nome da categoria a ser verificada.
        user_id (int): O ID do usuário.

    Returns:
        Categoria or None: O objeto Categoria se existir, None caso contrário.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Busca pela combinação exata de nome e user_id
        cursor.execute("SELECT * FROM categorias WHERE nome = ? AND user_id = ?", (nome, user_id))
        row = cursor.fetchone()
        conn.close()
        if row:
            # Se encontrou, retorna o objeto Categoria
            return Categoria(row['id'], row['nome'], row['user_id'])
        return None # Não encontrou
    except Exception as e:
        print(f"Erro ao buscar categoria por nome '{nome}' para user ID {user_id}: {e}")
        if conn: conn.close()
        return None

def update_categoria(categoria_id, nome, user_id):
    """Atualiza o nome de uma categoria existente, verificando propriedade e duplicidade.

    Args:
        categoria_id (int): O ID da categoria a ser atualizada.
        nome (str): O novo nome para a categoria.
        user_id (int): O ID do usuário dono da categoria.

    Returns:
        bool: True se a atualização foi bem-sucedida, False caso contrário
              (ex: nome duplicado, categoria não encontrada, erro).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # --- Verificação de Duplicidade ---
        # Verifica se já existe OUTRA categoria (id != categoria_id) com o novo nome para este usuário.
        cursor.execute("SELECT id FROM categorias WHERE nome = ? AND user_id = ? AND id != ?", (nome, user_id, categoria_id))
        if cursor.fetchone(): # Se encontrou alguma outra categoria com o mesmo nome
             print(f"Erro: Já existe outra categoria com o nome '{nome}' para o usuário ID {user_id}.")
             conn.close()
             return False # Indica falha por nome duplicado

        # --- Atualização ---
        # Tenta atualizar a categoria, garantindo que o ID e o user_id correspondem
        cursor.execute(
            "UPDATE categorias SET nome = ? WHERE id = ? AND user_id = ?",
            (nome, categoria_id, user_id)
        )
        updated_rows = cursor.rowcount # Verifica quantas linhas foram realmente afetadas pelo UPDATE
        conn.commit() # Salva a alteração
        conn.close()
        # Retorna True APENAS se exatamente uma linha foi atualizada
        return updated_rows > 0
    except sqlite3.IntegrityError: # Segurança extra para violação de UNIQUE (improvável com a verificação acima)
        print(f"Erro de Integridade ao tentar atualizar categoria ID {categoria_id} para nome '{nome}'.")
        conn.close()
        return False
    except Exception as e:
        print(f"Erro inesperado ao atualizar categoria ID {categoria_id}: {e}")
        conn.rollback() # Desfaz a tentativa de atualização
        conn.close()
        return False

def delete_categoria(categoria_id, user_id):
    """Deleta uma categoria específica, se ela pertencer ao usuário.
       As contas associadas a esta categoria terão seu campo 'categoria_id'
       definido como NULL automaticamente devido à configuração da FOREIGN KEY.

    Args:
        categoria_id (int): O ID da categoria a ser deletada.
        user_id (int): O ID do usuário dono da categoria.

    Returns:
        bool: True se a exclusão foi bem-sucedida, False caso contrário.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Tenta deletar a categoria, verificando o ID e o user_id
        cursor.execute("DELETE FROM categorias WHERE id = ? AND user_id = ?", (categoria_id, user_id))
        deleted_rows = cursor.rowcount # Verifica quantas linhas foram deletadas
        conn.commit() # Salva a deleção
        conn.close()
        if deleted_rows == 0:
            # Se nenhuma linha foi deletada, a categoria não foi encontrada ou não pertencia ao usuário
            print(f"Aviso: Nenhuma categoria encontrada com ID {categoria_id} para o usuário ID {user_id} para deletar.")
        # Retorna True se pelo menos uma linha foi deletada (deve ser 1 ou 0)
        return deleted_rows > 0
    except Exception as e:
        print(f"Erro ao deletar categoria ID {categoria_id}: {e}")
        conn.rollback() # Desfaz a tentativa de deleção
        conn.close()
        return False

# --- Funções CRUD para Contas (Despesas/Receitas) ---

def update_conta(conta):
    """Atualiza os dados de uma conta existente no banco de dados.

    Args:
        conta (Conta): O objeto Conta contendo os dados atualizados.
                       O objeto deve ter os atributos id, nome, valor, vencimento, etc.,
                       incluindo o user_id para verificação de propriedade.

    Returns:
        bool: True se a atualização foi bem-sucedida, False caso contrário.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Garante que a data de vencimento está no formato ISO 'YYYY-MM-DD' para salvar como TEXT
        vencimento_str = None
        if isinstance(conta.vencimento, (date, datetime)):
            vencimento_str = conta.vencimento.isoformat()
        elif isinstance(conta.vencimento, str):
             # Tenta validar se a string já está no formato correto ou converter
             try: vencimento_str = date.fromisoformat(conta.vencimento).isoformat()
             except ValueError: print(f"Aviso: String de vencimento inválida '{conta.vencimento}' para conta ID {conta.id}. Salvando como estava.")
        else:
            print(f"Aviso: Tipo de vencimento inválido ({type(conta.vencimento)}) para conta ID {conta.id}. Salvando como NULL.")
            # Considerar lançar erro ou salvar como NULL dependendo da regra de negócio
            # vencimento_str = None # Descomente para salvar NULL

        # Garante que valor seja float para salvar como REAL
        try: valor_float = float(conta.valor) if conta.valor is not None else 0.0
        except ValueError:
             print(f"Erro: Valor inválido '{conta.valor}' não pode ser convertido para float para salvar conta ID {conta.id}.")
             return False # Impede salvar com valor inválido

        # Executa o UPDATE, incluindo user_id na cláusula WHERE para segurança
        cursor.execute(
            """UPDATE contas
               SET nome = ?, valor = ?, vencimento = ?, categoria_id = ?,
                   parcela_atual = ?, total_parcelas = ?, user_id = ?,
                   recorrente = ?, tipo_pagamento_id = ?
               WHERE id = ? AND user_id = ?""", # Verifica ID e User ID
            (conta.nome, valor_float, vencimento_str, conta.categoria_id,
             conta.parcela_atual, conta.total_parcelas, conta.user_id,
             int(conta.recorrente), conta.tipo_pagamento_id, conta.id, conta.user_id)
        )
        updated_rows = cursor.rowcount # Verifica se alguma linha foi atualizada
        conn.commit() # Salva a alteração
        conn.close()
        if updated_rows == 0:
             # Se nenhuma linha foi atualizada, a conta não foi encontrada ou não pertence ao usuário
             print(f"Aviso: Nenhuma conta encontrada com ID {conta.id} para o usuário ID {conta.user_id} para atualizar.")
        return updated_rows > 0 # Retorna True se a atualização ocorreu
    except Exception as e:
        print(f"Erro inesperado ao atualizar conta ID {getattr(conta, 'id', 'N/A')}: {e}")
        # Tentar rollback e fechar conexão em caso de erro
        try:
            if conn:
                conn.rollback()
                conn.close()
        except: pass # Ignora erros ao tentar fechar/rollback
        return False # Retorna False indicando falha

def get_conta_by_id(id, user_id):
    """Busca uma conta específica pelo ID, garantindo que pertence ao usuário
       e incluindo o nome da categoria associada (se houver).

    Args:
        id (int): O ID da conta a ser buscada.
        user_id (int): O ID do usuário dono da conta.

    Returns:
        Conta or None: O objeto Conta (com atributo extra 'categoria_nome') se encontrado, None caso contrário.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Seleciona todas as colunas da conta ('c.*') e o nome da categoria ('cat.nome')
        # Usa LEFT JOIN para incluir contas mesmo que não tenham categoria_id definido (será NULL)
        cursor.execute("""
            SELECT c.*, cat.nome as categoria_nome
            FROM contas c
            LEFT JOIN categorias cat ON c.categoria_id = cat.id
            WHERE c.id = ? AND c.user_id = ?
        """, (id, user_id))
        row = cursor.fetchone() # Pega o resultado
        conn.close()
        if row:
            # Se encontrou a linha, cria o objeto Conta
            conta_obj = Conta(
                id=row['id'],
                nome=row['nome'],
                valor=row['valor'],           # O modelo Conta deve converter para Decimal
                vencimento=row['vencimento'], # O modelo Conta deve converter string ISO para date
                categoria_id=row['categoria_id'],
                parcela_atual=row['parcela_atual'],
                total_parcelas=row['total_parcelas'],
                user_id=row['user_id'],
                recorrente=row['recorrente'],
                tipo_pagamento_id=row['tipo_pagamento_id']
            )
            # Adiciona o nome da categoria como um atributo extra ao objeto
            conta_obj.categoria_nome = row['categoria_nome']
            return conta_obj # Retorna o objeto Conta
        return None # Retorna None se não encontrou
    except Exception as e:
        print(f"Erro ao buscar conta ID {id} para user ID {user_id}: {e}")
        if conn: conn.close()
        return None

def get_contas_by_user(user_id):
    """Busca todas as contas pertencentes a um usuário específico, incluindo os nomes das categorias.

    Args:
        user_id (int): O ID do usuário.

    Returns:
        list[Conta]: Uma lista de objetos Conta (com atributo extra 'categoria_nome'),
                     ordenada por vencimento mais recente. Retorna lista vazia se erro.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    contas = [] # Inicializa a lista de contas
    try:
        # Seleciona contas e nomes de categoria via LEFT JOIN, ordenado por vencimento descendente
        cursor.execute("""
            SELECT c.*, cat.nome as categoria_nome
            FROM contas c
            LEFT JOIN categorias cat ON c.categoria_id = cat.id
            WHERE c.user_id = ?
            ORDER BY c.vencimento DESC, c.id DESC -- Ordena por vencimento mais recente, depois por ID
        """, (user_id,))

        # Itera sobre cada linha retornada
        for row in cursor.fetchall():
            # Cria o objeto Conta para cada linha
            conta_obj = Conta(
                id=row['id'],
                nome=row['nome'],
                valor=row['valor'],
                vencimento=row['vencimento'],
                categoria_id=row['categoria_id'],
                parcela_atual=row['parcela_atual'],
                total_parcelas=row['total_parcelas'],
                user_id=row['user_id'],
                recorrente=row['recorrente'],
                tipo_pagamento_id=row['tipo_pagamento_id']
            )
            # Adiciona o nome da categoria ao objeto
            conta_obj.categoria_nome = row['categoria_nome']
            contas.append(conta_obj) # Adiciona o objeto à lista
        conn.close()
        return contas # Retorna a lista de objetos Conta
    except Exception as e:
        print(f"Erro ao buscar contas para user ID {user_id}: {e}")
        if conn: conn.close()
        return [] # Retorna lista vazia em caso de erro

# --- Funções CRUD para Usuários ---

def get_user_by_username(username):
    """Busca um usuário no banco de dados pelo seu nome de usuário.

    Args:
        username (str): O nome de usuário a ser buscado.

    Returns:
        User or None: O objeto User se encontrado, None caso contrário.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Busca o usuário pelo nome de usuário (que é UNIQUE)
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row:
            # Se encontrou, cria e retorna um objeto User (definido em models.py)
            # A classe User deve aceitar id, username, password no construtor
            return User(id=row['id'], username=row['username'], password=row['password'])
        else:
            return None # Usuário não encontrado
    except Exception as e:
        print(f"Erro ao buscar usuário por username '{username}': {e}")
        if conn: conn.close()
        return None

def create_user(username, hashed_password):
    """Cria um novo usuário no banco de dados.

    Args:
        username (str): O nome de usuário para o novo usuário.
        hashed_password (str): O hash da senha para o novo usuário.

    Returns:
        User or None: O objeto User recém-criado se sucesso, None caso contrário (ex: username duplicado).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Tenta inserir o novo usuário
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed_password)
        )
        conn.commit() # Salva a inserção
        user_id = cursor.lastrowid # Pega o ID gerado para o novo usuário
        conn.close()
        # Busca e retorna o usuário recém-criado para confirmar e obter o objeto completo
        return get_user_by_username(username)
    except sqlite3.IntegrityError:
        # Captura erro se o username já existir (restrição UNIQUE)
        print(f"Erro de Integridade: Nome de usuário '{username}' já está em uso.")
        conn.close()
        return None # Falha devido a username duplicado
    except Exception as e:
        # Captura outros erros
        print(f"Erro inesperado ao criar usuário '{username}': {e}")
        conn.rollback() # Desfaz a tentativa de inserção
        conn.close()
        return None

# --- Funções CRUD para Tipos de Pagamento (Cartão/Conta Bancária) ---

def get_tipos_pagamento_by_user(user_id):
    """Busca todos os tipos de pagamento (Cartoes e Contas Bancarias) de um usuário.

    Args:
        user_id (int): O ID do usuário.

    Returns:
        list[Cartao | ContaBancaria]: Uma lista contendo objetos Cartao e/ou ContaBancaria,
                                       ordenada por nome. Retorna lista vazia se erro.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    tipos = [] # Inicializa a lista
    try:
        # Busca todos os tipos de pagamento do usuário, ordenados por nome
        cursor.execute("SELECT * FROM tipos_pagamento WHERE user_id = ? ORDER BY nome", (user_id,))
        # Itera sobre cada linha retornada
        for row in cursor.fetchall():
            # Verifica o valor da coluna 'tipo' para decidir qual objeto criar
            if row['tipo'] == 'cartao':
                # Cria um objeto Cartao. A classe Cartao deve lidar com a conversão
                # dos valores REAL (limite, limite_disponivel) para Decimal internamente.
                tipos.append(Cartao(row['id'], row['nome'], row['limite'], row['limite_disponivel'], row['user_id']))
            elif row['tipo'] == 'conta':
                # Cria um objeto ContaBancaria. A classe deve converter saldo REAL para Decimal.
                tipos.append(ContaBancaria(row['id'], row['nome'], row['saldo'], row['user_id']))
        conn.close()
        return tipos # Retorna a lista de objetos
    except Exception as e:
        print(f"Erro ao buscar tipos de pagamento para user ID {user_id}: {e}")
        if conn: conn.close()
        return [] # Retorna lista vazia em caso de erro

def create_tipo_pagamento(nome, tipo, limite=None, limite_disponivel=None, saldo=None, user_id=None):
    """Cria um novo tipo de pagamento (Cartão ou Conta Bancária) no banco.

    Args:
        nome (str): Nome do tipo de pagamento.
        tipo (str): 'cartao' ou 'conta'.
        limite (Decimal, float, int, str, optional): Limite total (para cartao).
        limite_disponivel (Decimal, float, int, str, optional): Limite disponível (para cartao).
        saldo (Decimal, float, int, str, optional): Saldo inicial (para conta).
        user_id (int): ID do usuário dono.

    Returns:
        int or None: O ID do tipo de pagamento criado se sucesso, None caso contrário.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Converte os valores numéricos (idealmente Decimal) para float antes de salvar no SQLite (tipo REAL)
    # Lida com None para os campos não aplicáveis
    try:
        limite_float = float(limite) if limite is not None else None
        limite_disp_float = float(limite_disponivel) if limite_disponivel is not None else None
        saldo_float = float(saldo) if saldo is not None else None
    except (ValueError, TypeError) as conv_err:
        print(f"Erro de conversão de valor ao criar tipo de pagamento '{nome}': {conv_err}")
        conn.close()
        return None

    try:
        # Insere o novo registro na tabela tipos_pagamento
        cursor.execute(
            """INSERT INTO tipos_pagamento (nome, tipo, limite, limite_disponivel, saldo, user_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (nome, tipo, limite_float, limite_disp_float, saldo_float, user_id)
        )
        conn.commit() # Salva a inserção
        tipo_pagamento_id = cursor.lastrowid # Pega o ID gerado
        conn.close()
        return tipo_pagamento_id # Retorna o ID
    except Exception as e:
        print(f"Erro inesperado ao criar tipo de pagamento '{nome}': {e}")
        conn.rollback() # Desfaz a tentativa
        conn.close()
        return None

def get_tipo_pagamento_by_id(tipo_id):
    """Busca um tipo de pagamento específico (Cartao ou ContaBancaria) pelo ID.

    Args:
        tipo_id (int): O ID do tipo de pagamento a ser buscado.

    Returns:
        Cartao or ContaBancaria or None: O objeto correspondente se encontrado, None caso contrário.
    """
    # Retorna None imediatamente se o ID for inválido (None, 0, etc.)
    if not tipo_id: return None
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Busca o registro pelo ID
        cursor.execute("SELECT * FROM tipos_pagamento WHERE id = ?", (tipo_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            # Se encontrou, verifica o tipo e cria o objeto apropriado
            if row['tipo'] == 'cartao':
                # O modelo Cartao deve lidar com a conversão dos valores REAL para Decimal
                return Cartao(row['id'], row['nome'], row['limite'], row['limite_disponivel'], row['user_id'])
            elif row['tipo'] == 'conta':
                # O modelo ContaBancaria deve lidar com a conversão do saldo REAL para Decimal
                return ContaBancaria(row['id'], row['nome'], row['saldo'], row['user_id'])
        return None # Retorna None se não encontrou a linha
    except Exception as e:
        print(f"Erro ao buscar tipo de pagamento ID {tipo_id}: {e}")
        if conn: conn.close()
        return None

def update_tipo_pagamento(tipo_pagamento):
    """Atualiza os dados de um tipo de pagamento (Cartao ou ContaBancaria) no banco.

    Args:
        tipo_pagamento (Cartao | ContaBancaria): O objeto com os dados atualizados.
                                                 Deve conter o ID e o user_id corretos.

    Returns:
        bool: True se a atualização foi bem-sucedida, False caso contrário.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verifica o tipo do objeto passado para executar o UPDATE correto
        if isinstance(tipo_pagamento, Cartao):
            # Para Cartao, atualiza nome, limite e limite_disponivel
            # Converte os valores Decimal do objeto para float antes de salvar no DB (REAL)
            cursor.execute(
                "UPDATE tipos_pagamento SET nome = ?, limite = ?, limite_disponivel = ? WHERE id = ? AND user_id = ?",
                (tipo_pagamento.nome, float(tipo_pagamento.limite), float(tipo_pagamento.limite_disponivel),
                 tipo_pagamento.id, tipo_pagamento.user_id) # Inclui user_id no WHERE por segurança
            )
        elif isinstance(tipo_pagamento, ContaBancaria):
             # Para ContaBancaria, atualiza nome e saldo
             # Converte o saldo Decimal para float
            cursor.execute(
                "UPDATE tipos_pagamento SET nome = ?, saldo = ? WHERE id = ? AND user_id = ?",
                (tipo_pagamento.nome, float(tipo_pagamento.saldo), tipo_pagamento.id, tipo_pagamento.user_id) # Inclui user_id no WHERE
            )
        else:
            # Se o objeto não for nem Cartao nem ContaBancaria
            print(f"Erro: Tipo de pagamento desconhecido para atualização: {type(tipo_pagamento)}")
            conn.close()
            return False # Falha

        updated_rows = cursor.rowcount # Verifica se alguma linha foi afetada
        conn.commit() # Salva a alteração
        conn.close()
        if updated_rows == 0:
            # Se nenhuma linha foi atualizada, o tipo não foi encontrado ou não pertence ao usuário
            print(f"Aviso: Nenhum tipo de pagamento encontrado com ID {tipo_pagamento.id} para o usuário ID {tipo_pagamento.user_id} para atualizar.")
        return updated_rows > 0 # Retorna True se a atualização ocorreu
    except Exception as e:
        print(f"Erro inesperado ao atualizar tipo de pagamento ID {getattr(tipo_pagamento, 'id', 'N/A')}: {e}")
        conn.rollback() # Desfaz a tentativa
        conn.close()
        return False

def delete_tipo_pagamento(tipo_id, user_id):
    """Deleta um tipo de pagamento (Cartao ou ContaBancaria), mas APENAS se não houver
       contas (despesas/receitas) vinculadas a ele.

    Args:
        tipo_id (int): O ID do tipo de pagamento a ser deletado.
        user_id (int): O ID do usuário dono.

    Returns:
        bool: True se a exclusão foi bem-sucedida, False caso contrário
              (incluindo o caso de contas vinculadas existirem).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # PASSO 1: Verificar se existem contas vinculadas a este tipo de pagamento para este usuário.
        cursor.execute("SELECT COUNT(*) FROM contas WHERE tipo_pagamento_id = ? AND user_id = ?", (tipo_id, user_id))
        count = cursor.fetchone()[0] # Pega o resultado da contagem
        if count > 0:
            # Se houver contas vinculadas, a exclusão não é permitida
            print(f"Erro: Não é possível excluir o tipo de pagamento ID {tipo_id}, pois existem {count} contas vinculadas a ele.")
            conn.close()
            return False # Retorna False indicando falha devido a contas vinculadas

        # PASSO 2: Se não houver contas vinculadas, prosseguir com a exclusão.
        # Deleta o tipo de pagamento, verificando ID e user_id.
        cursor.execute("DELETE FROM tipos_pagamento WHERE id = ? AND user_id = ?", (tipo_id, user_id))
        deleted_rows = cursor.rowcount # Verifica se alguma linha foi deletada
        conn.commit() # Salva a deleção
        conn.close()
        if deleted_rows == 0:
             # Se nenhuma linha foi deletada (tipo não encontrado ou não pertence ao usuário)
             print(f"Aviso: Nenhum tipo de pagamento encontrado com ID {tipo_id} para o usuário ID {user_id} para deletar.")
        return deleted_rows > 0 # Retorna True se a exclusão ocorreu
    except Exception as e:
        print(f"Erro ao deletar tipo de pagamento ID {tipo_id}: {e}")
        conn.rollback() # Desfaz a tentativa
        conn.close()
        return False

# --- Funções Auxiliares de Migração/Atualização de Schema ---
# Estas funções ajudam a adicionar colunas a tabelas existentes se elas não existirem.
# São úteis quando se adiciona novas funcionalidades a uma aplicação já existente.

def add_categoria_id_column_to_contas():
    """Adiciona a coluna 'categoria_id' (com chave estrangeira) à tabela 'contas' se ela não existir."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Tenta adicionar a coluna categoria_id, que referencia a tabela categorias.
        # ON DELETE SET NULL: Se a categoria referenciada for deletada, o valor em contas.categoria_id será NULL.
        cursor.execute("ALTER TABLE contas ADD COLUMN categoria_id INTEGER REFERENCES categorias(id) ON DELETE SET NULL")
        conn.commit()
        print("Coluna 'categoria_id' adicionada à tabela 'contas' com sucesso.")
    except sqlite3.OperationalError as e:
        # Se a coluna já existir, o SQLite gera um erro "duplicate column name". Ignoramos esse erro específico.
        if "duplicate column name" not in str(e).lower():
            # Se for outro erro operacional, imprime
            print(f"Erro operacional ao adicionar coluna 'categoria_id': {e}")
        # else: # Se for o erro de coluna duplicada, podemos comentar
            # print("Coluna 'categoria_id' já existe em 'contas'.")
    except Exception as e:
        print(f"Erro geral ao adicionar coluna 'categoria_id': {e}")
        conn.rollback()
    finally:
        conn.close()

# Função para dropar coluna antiga - Geralmente EVITADA em SQLite devido a limitações.
# Manter dados na coluna antiga ou migrar para a nova e ignorar a antiga é mais seguro.
# def drop_old_categoria_column_from_contas():
#      """(PERIGOSO/NÃO RECOMENDADO EM SQLite) Tenta remover a coluna 'categoria' antiga."""
#      # ... implementação ... (mas geralmente não funciona bem ou requer recriar tabela)

def add_recorrente_column():
    """Adiciona a coluna 'recorrente' (INTEGER com default 0) à tabela 'contas' se não existir."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Adiciona a coluna para marcar contas recorrentes, com valor padrão 0 (não recorrente)
        cursor.execute("ALTER TABLE contas ADD COLUMN recorrente INTEGER DEFAULT 0")
        conn.commit()
        print("Coluna 'recorrente' adicionada à tabela 'contas' com sucesso.")
    except sqlite3.OperationalError as e:
        # Ignora erro se a coluna já existir
        if "duplicate column name" not in str(e).lower():
            print(f"Erro operacional ao adicionar coluna 'recorrente': {e}")
        # else:
            # print("Coluna 'recorrente' já existe em 'contas'.")
    except Exception as e:
        print(f"Erro geral ao adicionar coluna 'recorrente': {e}")
        conn.rollback()
    finally:
        conn.close()

def add_tipo_pagamento_id_column():
    """Adiciona a coluna 'tipo_pagamento_id' (com chave estrangeira) à tabela 'contas' se não existir."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Adiciona a coluna que referencia a tabela tipos_pagamento.
        # ON DELETE SET NULL: Se o tipo de pagamento for deletado, o valor em contas.tipo_pagamento_id será NULL.
        cursor.execute("ALTER TABLE contas ADD COLUMN tipo_pagamento_id INTEGER REFERENCES tipos_pagamento(id) ON DELETE SET NULL")
        conn.commit()
        print("Coluna 'tipo_pagamento_id' adicionada à tabela 'contas' com sucesso.")
    except sqlite3.OperationalError as e:
         # Ignora erro se a coluna já existir
         if "duplicate column name" not in str(e).lower():
            print(f"Erro operacional ao adicionar coluna 'tipo_pagamento_id': {e}")
         # else:
            # print("Coluna 'tipo_pagamento_id' já existe em 'contas'.")
    except Exception as e:
        print(f"Erro geral ao adicionar coluna 'tipo_pagamento_id': {e}")
        conn.rollback()
    finally:
        conn.close()

def check_and_apply_schema_updates():
    """Função principal para verificar e aplicar atualizações necessárias no schema do banco de dados.
       Chama init_db() para garantir que as tabelas base existam e depois verifica/adiciona colunas específicas.
    """
    print("Verificando e aplicando atualizações de schema do banco de dados...")
    # 1. Garante que todas as tabelas base definidas em init_db() existam.
    # Se as tabelas já existirem, init_db() não fará nada devido ao "IF NOT EXISTS".
    init_db()

    # 2. Verifica a existência de colunas específicas que podem ter sido adicionadas posteriormente.
    #    Esta abordagem é simples para SQLite. Ferramentas como Alembic são melhores para bancos mais complexos.
    conn = get_db_connection()
    cursor = conn.cursor()

    # Função auxiliar interna para verificar uma coluna
    def check_column(table, column):
        try:
            # Tentativa simples de selecionar a coluna. Se falhar, ela não existe.
            cursor.execute(f"SELECT {column} FROM {table} LIMIT 1")
            return True # Coluna existe
        except sqlite3.OperationalError:
            return False # Coluna não existe

    # Verifica e adiciona 'categoria_id' em 'contas'
    if not check_column('contas', 'categoria_id'):
        print("Coluna 'categoria_id' não encontrada em 'contas'. Adicionando...")
        add_categoria_id_column_to_contas()
        # OBS: Se houvesse uma coluna 'categoria' antiga (TEXT), a migração dos dados
        # para 'categoria_id' precisaria ser feita aqui antes de (opcionalmente) dropar a antiga.

    # Verifica e adiciona 'recorrente' em 'contas'
    if not check_column('contas', 'recorrente'):
        print("Coluna 'recorrente' não encontrada em 'contas'. Adicionando...")
        add_recorrente_column()

    # Verifica e adiciona 'tipo_pagamento_id' em 'contas'
    if not check_column('contas', 'tipo_pagamento_id'):
        print("Coluna 'tipo_pagamento_id' não encontrada em 'contas'. Adicionando...")
        add_tipo_pagamento_id_column()

    conn.close() # Fecha a conexão usada para as verificações
    print("Verificação e aplicação de atualizações de schema concluída.")

# --- Bloco para execução direta do script (útil para testes isolados) ---
# if __name__ == '__main__':
#     print("Executando database.py diretamente para inicializar/verificar schema.")
#     check_and_apply_schema_updates()
#     print("\nTeste de conexão com o banco:")
#     try:
#         conn = get_db_connection()
#         print("Conexão bem-sucedida.")
#         # Exemplo: Listar tabelas
#         cursor = conn.cursor()
#         cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
#         tables = cursor.fetchall()
#         print("Tabelas encontradas:", [table['name'] for table in tables])
#         conn.close()
#     except Exception as e:
#         print(f"Falha na conexão de teste: {e}")
