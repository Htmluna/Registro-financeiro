import sqlite3
from datetime import date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Conta:
    def __init__(self, id, nome, valor, vencimento, categoria, parcela_atual, total_parcelas, user_id, recorrente,
                 tipo_pagamento_id):
        self.id = id
        self.nome = nome
        self.valor = valor
        self.vencimento = self.format_date(vencimento)
        self.categoria = categoria
        self.parcela_atual = parcela_atual
        self.total_parcelas = total_parcelas
        self.user_id = user_id
        self.recorrente = recorrente
        self.tipo_pagamento_id = tipo_pagamento_id

    @staticmethod
    def format_date(date_str):
        try:
            return date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None

    def get_parcela_display(self):
        if self.total_parcelas:
            return f"{self.parcela_atual}/{self.total_parcelas}"
        else:
            return "-"


class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password_hash = password

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Cartao:
    def __init__(self, id, nome, limite, limite_disponivel, user_id):
        self.id = id
        self.nome = nome
        self.limite = limite
        self.limite_disponivel = limite_disponivel
        self.user_id = user_id


class ContaBancaria:
    def __init__(self, id, nome, saldo, user_id):
        self.id = id
        self.nome = nome
        self.saldo = saldo
        self.user_id = user_id
