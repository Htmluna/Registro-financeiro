import sqlite3
from models import Conta, User, Cartao, ContaBancaria

DB_FILE = 'contas.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabela de usuários (sem mudanças)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Tabela de contas (AGORA COM RECORRENTE E TIPO DE PAGAMENTO)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            valor REAL NOT NULL,
            vencimento TEXT NOT NULL,
            categoria TEXT,
            parcela_atual INTEGER,
            total_parcelas INTEGER,
            user_id INTEGER NOT NULL,
            recorrente INTEGER DEFAULT 0,  -- 0 para não, 1 para sim
            tipo_pagamento_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (tipo_pagamento_id) REFERENCES tipos_pagamento(id)
        )
    """)

    # Nova tabela para tipos de pagamento (cartões e contas bancárias)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tipos_pagamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,  -- 'cartao' ou 'conta'
            limite REAL,        -- Para cartões
            limite_disponivel REAL, -- Para cartões
            saldo REAL,         -- Para contas
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


def update_conta(conta):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE contas SET nome = ?, valor = ?, vencimento = ?, categoria = ?,
               parcela_atual = ?, total_parcelas = ?, user_id = ?,
               recorrente = ?, tipo_pagamento_id = ? WHERE id = ?""",
            (conta.nome, conta.valor, conta.vencimento.isoformat(), conta.categoria,
             conta.parcela_atual, conta.total_parcelas, conta.user_id,
             conta.recorrente, conta.tipo_pagamento_id, conta.id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Erro ao atualizar conta: {e}")
        return False


def get_conta_by_id(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contas WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return Conta(*row)
    return None


def get_user_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(row['id'], row['username'], row['password'])
    else:
        return None


def create_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)",
        (username, password)
    )
    conn.commit()
    conn.close()
    return get_user_by_username(username)


def get_contas_by_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contas WHERE user_id = ?", (user_id,))
    contas = []
    for row in cursor.fetchall():
        contas.append(Conta(*row)) #Correção: Usar os dados da linha para criar um objeto Conta
    conn.close()
    return contas


def get_tipos_pagamento_by_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tipos_pagamento WHERE user_id = ?", (user_id,))
    tipos = []
    for row in cursor.fetchall():
        if row['tipo'] == 'cartao':
            tipos.append(Cartao(row['id'], row['nome'], row['limite'], row['limite_disponivel'], row['user_id']))
        elif row['tipo'] == 'conta':
            tipos.append(ContaBancaria(row['id'], row['nome'], row['saldo'], row['user_id']))
    conn.close()
    return tipos


def create_tipo_pagamento(nome, tipo, limite=None, limite_disponivel=None, saldo=None, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Conversão explícita para float
    limite = float(limite) if limite is not None else None
    limite_disponivel = float(limite_disponivel) if limite_disponivel is not None else None
    saldo = float(saldo) if saldo is not None else None

    cursor.execute(
        """INSERT INTO tipos_pagamento (nome, tipo, limite, limite_disponivel, saldo, user_id)
            VALUES (?, ?, ?, ?, ?, ?)""",
        (nome, tipo, limite, limite_disponivel, saldo, user_id)
    )
    conn.commit()
    tipo_pagamento_id = cursor.lastrowid
    conn.close()
    return tipo_pagamento_id


def get_tipo_pagamento_by_id(tipo_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tipos_pagamento WHERE id = ?", (tipo_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        if row['tipo'] == 'cartao':
            return Cartao(row['id'], row['nome'], row['limite'], row['limite_disponivel'], row['user_id'])
        elif row['tipo'] == 'conta':
            return ContaBancaria(row['id'], row['nome'], row['saldo'], row['user_id'])
    return None


def update_tipo_pagamento(tipo_pagamento):
    conn = get_db_connection()
    cursor = conn.cursor()
    if isinstance(tipo_pagamento, Cartao):
        cursor.execute(
            "UPDATE tipos_pagamento SET nome = ?, limite = ?, limite_disponivel = ? WHERE id = ?",
            (tipo_pagamento.nome, float(tipo_pagamento.limite), float(tipo_pagamento.limite_disponivel),
             tipo_pagamento.id)  # Converter para float
        )
    elif isinstance(tipo_pagamento, ContaBancaria):
        cursor.execute(
            "UPDATE tipos_pagamento SET nome = ?, saldo = ? WHERE id = ?",
            (tipo_pagamento.nome, float(tipo_pagamento.saldo), tipo_pagamento.id)  # Converter para float
        )
    conn.commit()
    conn.close()


def delete_tipo_pagamento(tipo_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tipos_pagamento WHERE id = ?", (tipo_id,))
    conn.commit()
    conn.close()

def add_recorrente_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE contas ADD COLUMN recorrente INTEGER DEFAULT 0")
        conn.commit()
        print("Coluna 'recorrente' adicionada com sucesso.")
    except sqlite3.OperationalError as e:
        print(f"Erro ao adicionar coluna 'recorrente': {e}")
    conn.close()


def add_tipo_pagamento_id_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE contas ADD COLUMN tipo_pagamento_id INTEGER")
        conn.commit()
        print("Coluna 'tipo_pagamento_id' adicionada com sucesso.")
    except sqlite3.OperationalError as e:
        print(f"Erro ao adicionar coluna 'tipo_pagamento_id': {e}")
    conn.close()


def check_and_add_columns():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT recorrente FROM contas LIMIT 1")
    except sqlite3.OperationalError:
        add_recorrente_column()

    try:
        cursor.execute("SELECT tipo_pagamento_id FROM contas LIMIT 1")
    except sqlite3.OperationalError:
        add_tipo_pagamento_id_column()
    conn.close()
