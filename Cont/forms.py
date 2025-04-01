from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, SubmitField, PasswordField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, Optional

class ContaForm(FlaskForm):
    nome = StringField('Nome da Conta', validators=[DataRequired()])
    valor = StringField('Valor', validators=[DataRequired()])  # Alterado para StringField
    vencimento = DateField('Vencimento', format='%Y-%m-%d', validators=[DataRequired()])
    categoria = SelectField('Categoria', choices=[
        ('Contas do Apartamento', 'Contas do Apartamento'),
        ('Alimentação', 'Alimentação'),
        ('Transporte', 'Transporte'),
        ('Lazer', 'Lazer'),
        ('Mercado', 'Mercado'),
        ('Cartão Santander', 'Cartão Santander'),
        ('Cartão Santander mãe ', 'Cartão Santander mãe'),
        ('Cartão Nubank', 'Cartão Nubank'),
        ('Cartão Nubank mãe', 'Cartão Nubank mãe'),
        ('Cartão Nubank Luana', 'Cartão Nubank Luana'),
        ('Cartão Itaú', 'Cartão Itaú'),
        ('Outros', 'Outros')
    ])
    parcela_atual = IntegerField('Parcela Atual', validators=[Optional()])
    total_parcelas = IntegerField('Total de Parcelas', validators=[Optional()])
    recorrente = BooleanField('Compra Recorrente')
    tipo_pagamento = SelectField('Pagar com', coerce=int)
    submit = SubmitField('Salvar')


class CartaoForm(FlaskForm):
    nome = StringField('Nome do Cartão', validators=[DataRequired()])
    limite = StringField('Limite Total', validators=[DataRequired()]) # Alterado para StringField
    submit = SubmitField('Salvar Cartão')


class ContaBancariaForm(FlaskForm):
    nome = StringField('Nome da Conta', validators=[DataRequired()])
    saldo = StringField('Saldo Atual', validators=[DataRequired()]) # Alterado para StringField
    submit = SubmitField('Salvar Conta')


class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar')


class RegisterForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirme a Senha', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Registrar')


class ResetPasswordForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    new_password = PasswordField('Nova Senha', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirme a Nova Senha', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Redefinir Senha')
