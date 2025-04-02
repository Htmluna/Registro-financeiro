# models.py
import sqlite3 # Embora não usado diretamente aqui, pode ser útil para type hinting se necessário.
from datetime import date, datetime # Importa classes de data e datetime para manipulação de datas.
from flask_login import UserMixin # Importa Mixin para integrar a classe User com Flask-Login.
from werkzeug.security import generate_password_hash, check_password_hash # Funções para hashing seguro de senhas.
import decimal # Importa a classe Decimal para representação precisa de valores monetários.

# --- Modelo Categoria ---
class Categoria:
    """Representa uma categoria para classificar contas (despesas/receitas)."""
    def __init__(self, id, nome, user_id):
        """Inicializa um objeto Categoria.

        Args:
            id (int): O ID único da categoria no banco de dados.
            nome (str): O nome da categoria (ex: "Alimentação").
            user_id (int): O ID do usuário ao qual esta categoria pertence.
        """
        self.id = id
        self.nome = nome
        self.user_id = user_id

# --- Modelo Conta (Despesa/Receita) Atualizado ---
class Conta:
    """Representa uma conta a pagar ou a receber."""
    def __init__(self, id, nome, valor, vencimento, categoria_id, # Agora usa categoria_id
                 parcela_atual, total_parcelas, user_id, recorrente,
                 tipo_pagamento_id):
        """Inicializa um objeto Conta.

        Args:
            id (int): ID único da conta.
            nome (str): Descrição da conta.
            valor (float | str | Decimal): Valor da conta (será convertido para Decimal).
            vencimento (str | date | datetime): Data de vencimento (será convertida para objeto date).
            categoria_id (int | None): ID da categoria associada (ou None).
            parcela_atual (int | None): Número da parcela atual, se aplicável.
            total_parcelas (int | None): Número total de parcelas, se aplicável.
            user_id (int): ID do usuário dono da conta.
            recorrente (int | bool): Indica se a conta é recorrente (1/True ou 0/False).
            tipo_pagamento_id (int | None): ID do tipo de pagamento associado (ou None).
        """
        self.id = id
        self.nome = nome
        # Garante que o valor seja armazenado como Decimal para precisão monetária.
        # Converte de string ou float, tratando None como 0.00.
        self.valor = decimal.Decimal(str(valor)) if valor is not None else decimal.Decimal('0.00')
        # Padroniza a data de vencimento para um objeto date usando o método estático format_date.
        self.vencimento = self.format_date(vencimento)
        self.categoria_id = categoria_id # Armazena o ID da categoria.
        self.parcela_atual = parcela_atual
        self.total_parcelas = total_parcelas
        self.user_id = user_id
        self.recorrente = bool(recorrente) # Garante que seja armazenado como booleano.
        self.tipo_pagamento_id = tipo_pagamento_id
        # Atributo para armazenar o nome da categoria (preenchido externamente, ex: por JOIN no database.py).
        self.categoria_nome = None

    @staticmethod
    def format_date(date_input):
        """Tenta converter uma entrada (string, date, datetime) para um objeto date.
           Prioriza formato ISO 'YYYY-MM-DD'. Retorna None se a conversão falhar.
        """
        # Se já for date, retorna diretamente.
        if isinstance(date_input, date):
            return date_input
        # Se for datetime, retorna apenas a parte da data.
        if isinstance(date_input, datetime):
            return date_input.date()
        # Se for string ou outro tipo, tenta converter.
        try:
            # Tenta converter do formato ISO (YYYY-MM-DD), que é o formato preferido para armazenamento em TEXT.
            return date.fromisoformat(str(date_input))
        except (ValueError, TypeError):
            # Se falhar no formato ISO, tenta um formato comum (DD/MM/YYYY) como fallback.
            # ATENÇÃO: É melhor garantir que os dados sejam salvos/lidos em formato ISO no banco.
            try:
                return datetime.strptime(str(date_input), '%d/%m/%Y').date()
            except (ValueError, TypeError):
                # Se todas as tentativas falharem, retorna None.
                print(f"AVISO (Conta.format_date): Não foi possível converter '{date_input}' para data.")
                return None

    def get_parcela_display(self):
        """Retorna uma string formatada para exibição de parcelas (ex: "1/12")
           ou "-" se não for parcelado.
        """
        # Verifica se há um total de parcelas definido.
        if self.total_parcelas:
            # Retorna a string formatada. Usa self.parcela_atual ou '?' se for None.
            return f"{self.parcela_atual if self.parcela_atual else '?'}/{self.total_parcelas}"
        else:
            # Se não for parcelado, retorna um hífen.
            return "-"

# --- Modelo User (Usuário) ---
# Integra-se com Flask-Login usando UserMixin.
class User(UserMixin):
    """Representa um usuário da aplicação."""
    def __init__(self, id, username, password):
        """Inicializa um objeto User.

        Args:
            id (int): ID único do usuário.
            username (str): Nome de usuário.
            password (str): O HASH da senha, como armazenado no banco de dados.
        """
        self.id = id
        self.username = username
        # Armazena o hash da senha diretamente. A checagem será feita contra este hash.
        self.password_hash = password

    # set_password não é mais estritamente necessário aqui se o hash é gerado
    # antes de chamar create_user em app.py, mas é útil tê-lo para clareza
    # ou futuras funcionalidades (ex: alterar senha no perfil).
    # def set_password(self, password):
    #     """Gera e armazena o hash de uma senha em plain text."""
    #     self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica se uma senha em plain text corresponde ao hash armazenado.

        Args:
            password (str): A senha em plain text fornecida pelo usuário.

        Returns:
            bool: True se a senha corresponder ao hash, False caso contrário.
        """
        # Garante que temos um hash armazenado antes de tentar a comparação.
        if self.password_hash:
            # Usa a função segura do Werkzeug para comparar a senha fornecida com o hash.
            return check_password_hash(self.password_hash, password)
        # Se não há hash armazenado, a senha não pode ser verificada.
        return False

    # UserMixin fornece implementações padrão para:
    # is_authenticated: Sempre True para instâncias User logadas.
    # is_active: Assumido como True (pode ser sobrescrito se houver lógica de ativação).
    # is_anonymous: Sempre False para instâncias User.
    # get_id(): Retorna self.id (convertido para string), usado pelo Flask-Login para serializar na sessão.


# --- Modelo Cartao (Cartão de Crédito) ---
class Cartao:
    """Representa um cartão de crédito (um tipo de pagamento)."""
    def __init__(self, id, nome, limite, limite_disponivel, user_id):
        """Inicializa um objeto Cartao.

        Args:
            id (int): ID único do cartão.
            nome (str): Nome dado ao cartão (ex: "Visa Platinum").
            limite (float | str | Decimal): Limite total do cartão.
            limite_disponivel (float | str | Decimal): Limite disponível atual.
            user_id (int): ID do usuário dono do cartão.
        """
        self.id = id
        self.nome = nome
        # Converte limite para Decimal para consistência e precisão. Trata None.
        self.limite = decimal.Decimal(str(limite)) if limite is not None else decimal.Decimal('0.00')
        # Converte limite disponível para Decimal. Trata None.
        self.limite_disponivel = decimal.Decimal(str(limite_disponivel)) if limite_disponivel is not None else decimal.Decimal('0.00')
        self.user_id = user_id

# --- Modelo ContaBancaria ---
class ContaBancaria:
    """Representa uma conta bancária (um tipo de pagamento)."""
    def __init__(self, id, nome, saldo, user_id):
        """Inicializa um objeto ContaBancaria.

        Args:
            id (int): ID único da conta bancária.
            nome (str): Nome dado à conta (ex: "Conta Corrente BB").
            saldo (float | str | Decimal): Saldo atual da conta.
            user_id (int): ID do usuário dono da conta.
        """
        self.id = id
        self.nome = nome
        # Converte saldo para Decimal para consistência e precisão. Trata None.
        self.saldo = decimal.Decimal(str(saldo)) if saldo is not None else decimal.Decimal('0.00')
        self.user_id = user_id
