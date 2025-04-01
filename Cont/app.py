from flask import Flask, render_template, request, redirect, url_for, flash, g, current_app
from models import Conta, User, Cartao, ContaBancaria, db
from database import (
    get_db_connection,
    init_db,
    update_conta,
    get_conta_by_id,
    get_user_by_username,
    create_user,
    get_contas_by_user,
    get_tipos_pagamento_by_user,
    create_tipo_pagamento,
    get_tipo_pagamento_by_id,
    update_tipo_pagamento,
    delete_tipo_pagamento,
    check_and_add_columns
)
from forms import ContaForm, LoginForm, RegisterForm, ResetPasswordForm, CartaoForm, ContaBancariaForm
from datetime import date, timedelta
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import decimal
import os
import sqlite3
import calendar
import decimal
from waitress import serve
from datetime import datetime
import calendar
import decimal
from datetime import datetime

app = Flask(__name__)  # Corrigido: Usar __name__
app.config['SECRET_KEY'] = 'sua_super_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///contas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicialização do Banco (GARANTIDA E CORRETA) - Movido para fora do contexto
# Execute as funções de migração uma única vez (FORA do contexto da aplicação Flask)
from database import add_recorrente_column, add_tipo_pagamento_id_column, check_and_add_columns
#check_and_add_columns() #Execute aqui uma vez

init_db()

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(row['id'], row['username'], row['password'])
    return None


# Funções Auxiliares

def atualizar_limite_saldo(tipo_pagamento, valor, adicionar=False, total_parcelas=None):
    """Atualiza o limite de um cartão ou o saldo de uma conta bancária."""
    if tipo_pagamento:
        if isinstance(tipo_pagamento, Cartao):
            if total_parcelas:
                valor_total = valor * total_parcelas
            else:
                valor_total = valor
            # Converter para Decimal antes de subtrair/somar
            limite_disponivel = decimal.Decimal(str(tipo_pagamento.limite_disponivel)) #Converter para string antes de criar Decimal
            tipo_pagamento.limite_disponivel = limite_disponivel - valor_total if not adicionar else limite_disponivel + valor_total
        elif isinstance(tipo_pagamento, ContaBancaria):
            # Converter para Decimal antes de somar/subtrair
            saldo = decimal.Decimal(str(tipo_pagamento.saldo)) #Converter para string antes de criar Decimal
            #Converter valor para decimal antes de operar
            valor_decimal = decimal.Decimal(str(valor))
            tipo_pagamento.saldo =  saldo - valor_decimal if not adicionar else saldo + valor_decimal
        update_tipo_pagamento(tipo_pagamento)

def update_parcelas():
    today = date.today()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Contas parceladas
    cursor.execute(
        "SELECT * FROM contas WHERE total_parcelas IS NOT NULL "
        "AND parcela_atual < total_parcelas AND vencimento < ?",
        (today.isoformat(),)  # Converter para string para comparação
    )
    contas_para_atualizar = [Conta(*row) for row in cursor.fetchall()]

    for conta in contas_para_atualizar:
        new_parcela_atual = conta.parcela_atual + 1
        new_vencimento = proximo_vencimento(conta.vencimento)
        cursor.execute(
            "UPDATE contas SET parcela_atual = ?, vencimento = ? WHERE id = ?",
            (new_parcela_atual, new_vencimento.isoformat(), conta.id)
        )
        print(f"Conta ID {conta.id} (parcelada) atualizada: parcela {new_parcela_atual}/{conta.total_parcelas}, vencimento: {new_vencimento}")

    # Contas recorrentes
    cursor.execute(
        "SELECT * FROM contas WHERE recorrente = 1 AND vencimento < ?", (today.isoformat(),) # Converter para string para comparação
    )
    contas_recorrentes = [Conta(*row) for row in cursor.fetchall()]

    for conta in contas_recorrentes:
        new_vencimento = proximo_vencimento(conta.vencimento)

        # Obter o tipo de pagamento ANTES de atualizar o vencimento
        tipo_pagamento = get_tipo_pagamento_by_id(conta.tipo_pagamento_id)

        # Atualizar o vencimento no banco de dados
        cursor.execute("UPDATE contas SET vencimento = ? WHERE id = ?", (new_vencimento.isoformat(), conta.id))

        # Ajustar o limite/saldo APÓS atualizar o vencimento
        if tipo_pagamento:
            atualizar_limite_saldo(tipo_pagamento, conta.valor)

        print(f"Conta ID {conta.id} (recorrente) atualizada: vencimento: {new_vencimento}")

    conn.commit()
    conn.close()


def proximo_vencimento(vencimento_atual):
    year = vencimento_atual.year
    month = vencimento_atual.month + 1
    day = vencimento_atual.day

    if month > 12:
        month = 1
        year += 1

    while True:
        try:
            new_vencimento = date(year, month, day)
            break
        except ValueError:
            day -= 1
            if day == 0:
                # Adicione esta verificação para evitar loop infinito
                # Se chegamos ao dia 0, significa que nenhum dia é válido
                # No mês seguinte.  Podemos definir para o último dia
                # Do mês anterior (vencimento atual).
                last_day_of_prev_month = calendar.monthrange(vencimento_atual.year, vencimento_atual.month)[1]
                new_vencimento = date(year, month-1, last_day_of_prev_month)
                break # Ou raise ValueError("Erro ao calcular...")

    return new_vencimento


def valor_para_decimal(valor_str):
    """
    Converte uma string formatada em português brasileiro (ex: '1.234,56')
    para um objeto Decimal.
    """
    if isinstance(valor_str, decimal.Decimal):
        return valor_str

    if isinstance(valor_str, (int, float)):
        return decimal.Decimal(str(valor_str)) # Converter int ou float para Decimal

    if isinstance(valor_str, str):
        # Remove os pontos (separadores de milhar)
        valor_str = valor_str.replace('.', '')
        # Substitui a vírgula (separador decimal) por ponto
        valor_str = valor_str.replace(',', '.')
        try:
            return decimal.Decimal(valor_str)
        except decimal.InvalidOperation:
            return None
    return None

def formatar_br(valor):
    if valor is None:
        return "N/A"
    try:
        valor_str = "{:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {valor_str}"
    except (ValueError, TypeError):
        return "Valor inválido"


@app.context_processor
def inject_formatar_br():
    return dict(formatar_br=formatar_br)


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['SQLALCHEMY_DATABASE_URI'])  # Corrigido: Usar config para o URI
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


app.teardown_appcontext(close_db)


# Rotas

@app.route('/')
@login_required
def index():
    update_parcelas()
    contas = get_contas_by_user(current_user.id)

    total_geral = sum(conta.valor for conta in contas)

    total_por_categoria = {}
    for conta in contas:
        if conta.categoria not in total_por_categoria:
            total_por_categoria[conta.categoria] = 0
        total_por_categoria[conta.categoria] += conta.valor

    total_por_vencimento = {}
    for conta in contas:
        vencimento_str = conta.vencimento.strftime('%Y-%m-%d')
        if vencimento_str not in total_por_vencimento:
            total_por_vencimento[vencimento_str] = 0
        total_por_vencimento[vencimento_str] += conta.valor

    contas_por_categoria = {}
    for conta in contas:
        if conta.categoria not in contas_por_categoria:
            contas_por_categoria[conta.categoria] = []
        contas_por_categoria[conta.categoria].append(conta)

    return render_template(
        'index.html',
        contas=contas,
        total_geral=total_geral,
        total_por_categoria=total_por_categoria,
        total_por_vencimento=total_por_vencimento,
        contas_por_categoria=contas_por_categoria
    )


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_conta():
    form = ContaForm()
    tipos_pagamento = get_tipos_pagamento_by_user(current_user.id)
    form.tipo_pagamento.choices = [(tp.id, tp.nome) for tp in tipos_pagamento]

    if form.validate_on_submit():
        valor_decimal = valor_para_decimal(form.valor.data)
        if valor_decimal is None:
            flash('Valor inválido.', 'error')
            return render_template('add_conta.html', form=form)

        if valor_decimal < 0:
            flash('O valor deve ser maior ou igual a zero.', 'error')
            return render_template('add_conta.html', form=form)

        parcela_atual = form.parcela_atual.data or 1
        total_parcelas = form.total_parcelas.data
        recorrente = form.recorrente.data
        tipo_pagamento_id = form.tipo_pagamento.data
        vencimento_str = form.vencimento.data.isoformat()  # Formata a data
        valor_float = float(valor_decimal)  # Converte decimal para float

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO contas (nome, valor, vencimento, categoria,
                                   parcela_atual, total_parcelas, user_id, recorrente, tipo_pagamento_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (form.nome.data, valor_float, vencimento_str, form.categoria.data,
             parcela_atual, total_parcelas, current_user.id, recorrente, tipo_pagamento_id)
        )
        conta_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Atualizar o limite/saldo
        tipo_pagamento = get_tipo_pagamento_by_id(tipo_pagamento_id)
        atualizar_limite_saldo(tipo_pagamento, valor_decimal, total_parcelas=total_parcelas)

        flash('Conta adicionada com sucesso!', 'success')
        return redirect(url_for('index'))

    return render_template('add_conta.html', form=form)


@app.route('/contas_bancarias/add', methods=['GET', 'POST'])
@login_required
def add_conta_bancaria():
    form = ContaBancariaForm()
    if form.validate_on_submit():
        saldo_decimal = valor_para_decimal(form.saldo.data)
        if saldo_decimal is None:
            flash('Saldo inválido', 'error')
            return render_template('add_conta_bancaria.html', form=form)

        if saldo_decimal < 0:
            flash("O saldo deve ser maior ou igual a zero", "error")
            return render_template('add_conta_bancaria.html', form=form)

        saldo_float = float(saldo_decimal)  # Converte para float

        tipo_pagamento_id = create_tipo_pagamento(
            nome=form.nome.data,
            tipo='conta',
            saldo=saldo_float,
            user_id=current_user.id
        )
        #conn.close() #Removido: Não fechar a conexão aqui.
        flash('Conta bancária adicionada com sucesso!', 'success')
        return redirect(url_for('listar_contas_bancarias'))
    return render_template('add_conta_bancaria.html', form=form)


@app.route('/edit/<int:id>', methods=['GET', 'POST'])  # Corrigido: Sintaxe da rota
@login_required
def edit_conta(id):
    conta = get_conta_by_id(id)
    if not conta or conta.user_id != current_user.id:
        flash('Conta não encontrada ou acesso não permitido.', 'error')
        return redirect(url_for('index'))

    form = ContaForm()
    tipos_pagamento = get_tipos_pagamento_by_user(current_user.id)
    form.tipo_pagamento.choices = [(tp.id, tp.nome) for tp in tipos_pagamento]

    if request.method == 'GET':  # Preencher o formulário com os dados da conta
        form.nome.data = conta.nome
        form.valor.data = conta.valor
        form.vencimento.data = conta.vencimento
        form.categoria.data = conta.categoria
        form.parcela_atual.data = conta.parcela_atual
        form.total_parcelas.data = conta.total_parcelas
        form.recorrente.data = conta.recorrente
        form.tipo_pagamento.data = conta.tipo_pagamento_id

    if form.validate_on_submit():
        valor_decimal = valor_para_decimal(form.valor.data)
        if valor_decimal is None:
            flash('Valor inválido.', 'error')
            return render_template('edit_conta.html', form=form, conta=conta)

        if valor_decimal < 0:
            flash('O valor deve ser maior ou igual a zero.', 'error')
            return render_template('edit_conta.html', form=form, conta=conta)

        # Reverter o valor antigo no tipo de pagamento anterior
        tipo_pagamento_antigo = get_tipo_pagamento_by_id(conta.tipo_pagamento_id)
        atualizar_limite_saldo(tipo_pagamento_antigo, conta.valor, adicionar=True,
                               total_parcelas=conta.total_parcelas)

        # Atualizar a conta com os novos dados
        conta.nome = form.nome.data
        valor_float = float(valor_decimal)  # Converte decimal para float
        conta.valor = valor_float
        conta.vencimento = form.vencimento.data
        conta.categoria = form.categoria.data
        conta.parcela_atual = form.parcela_atual.data or 1
        conta.total_parcelas = form.total_parcelas.data
        conta.recorrente = form.recorrente.data
        conta.tipo_pagamento_id = form.tipo_pagamento.data
        success = update_conta(conta)

        # Aplicar o novo valor ao tipo de pagamento atual
        tipo_pagamento_novo = get_tipo_pagamento_by_id(conta.tipo_pagamento_id)
        atualizar_limite_saldo(tipo_pagamento_novo, valor_decimal, total_parcelas=conta.total_parcelas)

        if success:
            flash('Conta atualizada com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Erro ao atualizar conta.', 'error')
            return render_template('edit_conta.html', form=form, conta=conta)

    return render_template('edit_conta.html', form=form, conta=conta)


@app.route('/delete/<int:id>', methods=['POST'])  # Corrigido: Sintaxe da rota
@login_required
def delete_conta(id):
    conta = get_conta_by_id(id)
    if not conta or conta.user_id != current_user.id:
        flash('Conta não encontrada ou acesso não permitido.', 'error')
        return redirect(url_for('index'))

    # Reverter o valor no tipo de pagamento
    tipo_pagamento = get_tipo_pagamento_by_id(conta.tipo_pagamento_id)
    atualizar_limite_saldo(tipo_pagamento, conta.valor, adicionar=True, total_parcelas=conta.total_parcelas)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Contas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash('Conta deletada com sucesso', 'success')
    return redirect(url_for('index'))


# Rotas de Cartões

@app.route('/cartoes')
@login_required
def listar_cartoes():
    cartoes = [tp for tp in get_tipos_pagamento_by_user(current_user.id) if isinstance(tp, Cartao)]
    return render_template('listar_cartoes.html', cartoes=cartoes)


@app.route('/cartoes/add', methods=['GET', 'POST'])
@login_required
def add_cartao():
    form = CartaoForm()
    if form.validate_on_submit():
        limite_decimal = valor_para_decimal(form.limite.data)
        if limite_decimal is None:
            flash('Limite inválido.', 'error')
            return render_template('add_cartao.html', form=form)

        if limite_decimal < 0:
            flash('O limite deve ser maior ou igual a zero.', 'error')
            return render_template('add_cartao.html', form=form)

        limite_float = float(limite_decimal)

        create_tipo_pagamento(
            nome=form.nome.data,
            tipo='cartao',
            limite=limite_float,
            limite_disponivel=limite_float,
            user_id=current_user.id
        )
        #conn.close() #Não fechar a conexão.
        flash('Cartão adicionado com sucesso!', 'success')
        return redirect(url_for('listar_cartoes'))
    return render_template('add_cartao.html', form=form)


@app.route('/cartoes/edit/<int:id>', methods=['GET', 'POST'])  # Corrigido: Sintaxe da rota
@login_required
def edit_cartao(id):
    cartao = get_tipo_pagamento_by_id(id)
    if not cartao or not isinstance(cartao, Cartao) or cartao.user_id != current_user.id:
        flash('Cartão não encontrado ou sem permissão', "error")
        return redirect(url_for('listar_cartoes'))

    form = CartaoForm()
    if request.method == 'GET':
        form.nome.data = cartao.nome
        form.limite.data = cartao.limite

    if form.validate_on_submit():
        limite_decimal = valor_para_decimal(form.limite.data)
        if limite_decimal is None:
            flash('Limite inválido', 'error')
            return render_template('edit_cartao.html', form=form, cartao=cartao)

        if limite_decimal < 0:
            flash('O limite deve ser maior ou igual a zero.', 'error')
            return render_template('edit_cartao.html', form=form, cartao=cartao)

        cartao.nome = form.nome.data
        limite_float = float(limite_decimal)
        cartao.limite = limite_float
        #conn = get_db_connection() #Removido. Usar a conexão existente.
        update_tipo_pagamento(cartao)
        #conn.close() #Removido. Não fechar a conexão aqui.
        flash('Cartão atualizado com sucesso!', 'success')
        return redirect(url_for('listar_cartoes'))

    return render_template('edit_cartao.html', form=form, cartao=cartao)


@app.route('/cartoes/delete/<int:id>', methods=['POST'])
@login_required
def delete_cartao(id):
    cartao = get_tipo_pagamento_by_id(id)
    if not cartao or not isinstance(cartao, Cartao) or cartao.user_id != current_user.id:
        flash('Cartão não encontrado ou sem permissão', "error")
        return redirect(url_for('listar_cartoes'))

    conn = get_db_connection() # Usar get_db_connection
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contas WHERE tipo_pagamento_id = ?", (id,))
    contas_vinculadas = cursor.fetchall()

    if contas_vinculadas:
        flash('Não é possível excluir o cartão, pois existem contas vinculadas a ele.', 'error')
        conn.close() # Fechar a conexão aqui
        return redirect(url_for('listar_cartoes'))

    delete_tipo_pagamento(id) # Passar a conexão
    conn.close() # Fechar a conexão aqui
    flash('Cartão excluído com sucesso!', 'success')
    return redirect(url_for('listar_cartoes'))

# Rotas de Contas Bancárias

@app.route('/contas_bancarias')
@login_required
def listar_contas_bancarias():
    contas_bancarias = [tp for tp in get_tipos_pagamento_by_user(current_user.id) if isinstance(tp, ContaBancaria)]
    return render_template('listar_contas_bancarias.html', contas_bancarias=contas_bancarias)


@app.route('/contas_bancarias/edit/<int:id>', methods=['GET', 'POST'])  # Corrigido: Sintaxe da rota
@login_required
def edit_conta_bancaria(id):
    conta_bancaria = get_tipo_pagamento_by_id(id)
    if not conta_bancaria or not isinstance(conta_bancaria, ContaBancaria) or conta_bancaria.user_id != current_user.id:
        flash('Conta bancária não encontrada, ou sem permissão', "error")
        return redirect(url_for('listar_contas_bancarias'))

    form = ContaBancariaForm()
    if request.method == 'GET':
        form.nome.data = conta_bancaria.nome
        form.saldo.data = conta_bancaria.saldo

    if form.validate_on_submit():
        saldo_decimal = valor_para_decimal(form.saldo.data)
        if saldo_decimal is None:
            flash('Saldo inválido', 'error')
            return render_template('edit_conta_bancaria.html', form=form, conta_bancaria=conta_bancaria)

        if saldo_decimal < 0:
            flash('O saldo deve ser maior ou igual a zero.', 'error')
            return render_template('edit_conta_bancaria.html', form=form, conta_bancaria=conta_bancaria)

        conta_bancaria.nome = form.nome.data
        saldo_float = float(saldo_decimal)
        conta_bancaria.saldo = saldo_float
        #conn = get_db_connection() #Removido: Usar a conexão existente
        update_tipo_pagamento(conta_bancaria)
        #conn.close() #Removido: Não fechar conexão
        flash('Conta bancária atualizada com sucesso!', 'success')
        return redirect(url_for('listar_contas_bancarias'))

    return render_template('edit_conta_bancaria.html', form=form, conta_bancaria=conta_bancaria)

@app.route('/contas_bancarias/delete/<int:id>', methods=['POST'])
@login_required
def delete_conta_bancaria(id):
    conta_bancaria = get_tipo_pagamento_by_id(id)
    if not conta_bancaria or not isinstance(conta_bancaria, ContaBancaria) or conta_bancaria.user_id != current_user.id:
        flash('Conta bancária não encontrada ou sem permissão', 'error')
        return redirect(url_for('listar_contas_bancarias'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contas WHERE tipo_pagamento_id = ?", (id,))
    contas_vinculadas = cursor.fetchall()

    if contas_vinculadas:
        flash('Não é possível excluir a conta bancária, pois existem contas vinculadas a ela.', 'error')
        conn.close() #Fechar a conexão aqui
        return redirect(url_for('listar_contas_bancarias')) #Retorno estava faltando

    delete_tipo_pagamento(id)
    conn.close() #Fechar a conexão aqui
    flash('Conta bancária excluída com sucesso!', 'success')
    return redirect(url_for('listar_contas_bancarias')) #Retorno estava faltando

    #conn = get_db_connection() #Removido: Usar a conexão existente
def delete_tipo_pagamento(tipo_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tipos_pagamento WHERE id = ?", (tipo_id,))
    conn.commit()
    conn.close()


# Rotas de Login/Registro/Reset

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = get_user_by_username(form.username.data)
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Usuário ou senha inválidos.', 'error')
            return render_template('login.html', form=form)
    return render_template('login.html', form=form) #Adicionado: renderizar o template em GET

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegisterForm()
    if form.validate_on_submit():
        user = get_user_by_username(form.username.data)
        if user:
            flash("Nome de usuário já existe", 'error')
            return render_template('register.html', form=form)

        hashed_password = generate_password_hash(form.password.data)
        user = create_user(form.username.data, hashed_password)

        if user:
            login_user(user)
            flash("Conta criada com sucesso!", 'success')
            return redirect(url_for('index'))
        else:
            flash('Erro ao criar a conta.', 'error')
            return render_template('register.html', form=form)
    return render_template('register.html', form=form)


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = get_user_by_username(form.username.data)
        if user:
            new_hashed_password = generate_password_hash(form.new_password.data)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_hashed_password, user.id))
            conn.commit()
            conn.close()
            flash("Senha alterada com sucesso!", 'success')
            return redirect(url_for('login'))
        else:
            flash("Usuário não encontrado", 'error')
            return render_template('reset_password.html', form=form)
    return render_template('reset_password.html', form=form) #Adicionado: renderizar o template em GET


# Rota para o relatório mensal (esqueleto)

from datetime import datetime # Certifique-se que está importado

# ...

# Rota para exibir o formulário de seleção do relatório
@app.route('/relatorio/selecionar', methods=['GET'])
@login_required
def selecionar_relatorio():
    now = datetime.now()
    ano_atual = now.year
    mes_atual = now.month # Para pré-seleção

    anos_disponiveis = range(ano_atual + 1, ano_atual - 5, -1) # Inclui próximo ano
    meses_disponiveis = [
        (1, 'Janeiro'), (2, 'Fevereiro'), (3, 'Março'), (4, 'Abril'),
        (5, 'Maio'), (6, 'Junho'), (7, 'Julho'), (8, 'Agosto'),
        (9, 'Setembro'), (10, 'Outubro'), (11, 'Novembro'), (12, 'Dezembro')
    ]

    # Buscar categorias distintas do usuário (NOVO)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT categoria FROM contas WHERE user_id = ? ORDER BY categoria",
        (current_user.id,)
    )
    # Extrai apenas o nome da categoria de cada tupla retornada
    categorias_disponiveis = [row[0] for row in cursor.fetchall() if row[0]] # Garante que não pega categorias vazias/None
    conn.close()

    return render_template(
        'selecionar_relatorio.html',
        anos=anos_disponiveis,
        meses=meses_disponiveis,
        categorias_disponiveis=categorias_disponiveis, # Passa as categorias para o template
        ano_atual=ano_atual, # Passa ano atual para pré-seleção
        mes_atual=mes_atual   # Passa mês atual para pré-seleção
    )

# Rota para visualizar o relatório gerado com base na seleção
@app.route('/relatorio/visualizar', methods=['GET'])
@login_required
def visualizar_relatorio_mensal():
    try:
        mes = int(request.args.get('mes'))
        ano = int(request.args.get('ano'))
        # Obter a lista de categorias selecionadas (NOVO)
        selected_categories = request.args.getlist('categoria') # Retorna uma lista
        if not (1 <= mes <= 12):
            raise ValueError("Mês inválido")
    except (TypeError, ValueError, AttributeError):
        flash('Mês, Ano ou Categoria inválido(s).', 'error')
        return redirect(url_for('selecionar_relatorio'))

    mes_str = f"{mes:02d}"
    ano_str = str(ano)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Construir a consulta SQL dinamicamente (NOVO)
    base_query = """
        SELECT * FROM contas
        WHERE user_id = ?
        AND strftime('%Y', vencimento) = ?
        AND strftime('%m', vencimento) = ?
    """
    params = [current_user.id, ano_str, mes_str]

    # Adicionar filtro de categoria SE alguma foi selecionada
    if selected_categories:
        # Cria placeholders (?, ?, ...) para a cláusula IN
        placeholders = ', '.join('?' for _ in selected_categories)
        base_query += f" AND categoria IN ({placeholders})"
        params.extend(selected_categories) # Adiciona as categorias aos parâmetros

    base_query += " ORDER BY vencimento" # Adiciona ordenação no final

    # Executar a consulta final
    cursor.execute(base_query, params)
    contas_raw = cursor.fetchall()
    conn.close()

    contas_mes = [Conta(*row) for row in contas_raw]

    # Calcular totais (a lógica não muda, opera sobre os dados já filtrados)
    total_mes = decimal.Decimal(0)
    total_por_categoria_mes = {}
    for conta in contas_mes:
        valor_decimal_conta = decimal.Decimal(str(conta.valor))
        total_mes += valor_decimal_conta
        cat = conta.categoria if conta.categoria else "Sem Categoria" # Trata categoria None/vazia
        if cat not in total_por_categoria_mes:
            total_por_categoria_mes[cat] = decimal.Decimal(0)
        total_por_categoria_mes[cat] += valor_decimal_conta

    nome_mes = calendar.month_name[mes].capitalize()

    return render_template(
        'visualizar_relatorio_mensal.html',
        contas_mes=contas_mes,
        total_mes=total_mes,
        total_por_categoria_mes=total_por_categoria_mes,
        mes=mes,
        ano=ano,
        nome_mes=nome_mes,
        selected_categories=selected_categories # Passa categorias selecionadas para exibição
    )


@app.context_processor
def inject_functions():
    return dict(get_tipo_pagamento_by_id=get_tipo_pagamento_by_id)

if __name__ == '__main__':
    #Execute as funções de migração uma única vez (FORA do contexto da aplicação Flask)
    from database import add_recorrente_column, add_tipo_pagamento_id_column, check_and_add_columns
    check_and_add_columns() #Execute aqui uma vez
    serve(app, host='0.0.0.0', port=5000)  # Remova debug=True aqui
