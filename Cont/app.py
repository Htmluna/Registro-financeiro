import os
import sqlite3
import calendar  # Para obter nomes de meses e cálculos de dias
import decimal  # Para manipulação precisa de valores monetários
from datetime import date, timedelta, datetime  # Para manipulação de datas e horas
from dateutil.relativedelta import relativedelta  # Para cálculos fáceis de meses (ex: +2 meses)
from flask import (
    Flask, render_template, request, redirect, url_for, flash, g, current_app,
)
from flask_login import (
    LoginManager,  # Gerencia a sessão de login
    login_user,  # Função para logar um usuário
    logout_user,  # Função para deslogar um usuário
    login_required,  # Decorator para proteger rotas que exigem login
    current_user,  # Proxy para o usuário atualmente logado
    UserMixin,  # Mixin para a classe User (geralmente definida em models.py)
)
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,  # Para hashing seguro de senhas
)
from waitress import serve  # Servidor WSGI recomendado para produção (alternativa ao servidor de dev do Flask)

# --- Importações Locais ---
# Assumindo que os modelos (classes de dados) estão definidos em models.py
from models import Conta, User, Cartao, ContaBancaria, Categoria

# Assumindo que as funções de interação com o banco de dados estão em database.py
from database import (
    get_db_connection,  # Função para obter uma conexão com o DB
    init_db,  # Função para inicializar o DB (criar tabelas)
    update_conta,  # Função para atualizar uma conta no DB
    get_conta_by_id,  # Função para buscar uma conta pelo ID
    get_user_by_username,  # Função para buscar um usuário pelo nome
    create_user,  # Função para criar um novo usuário
    get_contas_by_user,  # Função para buscar todas as contas de um usuário
    get_tipos_pagamento_by_user,  # Função para buscar todos os tipos de pagamento (cartões/contas) de um usuário
    create_tipo_pagamento,  # Função para criar um novo tipo de pagamento (cartão/conta)
    get_tipo_pagamento_by_id,  # Função para buscar um tipo de pagamento pelo ID
    update_tipo_pagamento,  # Função para atualizar um tipo de pagamento
    delete_tipo_pagamento,  # Função para deletar um tipo de pagamento (e verificar contas associadas)
    create_categoria,  # Função para criar uma nova categoria
    get_categorias_by_user,  # Função para buscar todas as categorias de um usuário
    get_categoria_by_id,  # Função para buscar uma categoria pelo ID
    get_categoria_by_name_and_user,  # Função para buscar categoria pelo nome (evitar duplicados)
    update_categoria,  # Função para atualizar uma categoria
    delete_categoria,  # Função para deletar uma categoria (e desassociar contas)
    check_and_apply_schema_updates,  # Função para verificar e aplicar atualizações no schema do DB
)

# Assumindo que os formulários Flask-WTF estão definidos em forms.py
from forms import (
    ContaForm,
    LoginForm,
    RegisterForm,
    ResetPasswordForm,
    CartaoForm,
    ContaBancariaForm,
    CategoriaForm,
)

# --- Funções Auxiliares Globais ---


def valor_para_decimal(valor_str):
    """Converte uma string (formatos '1.234,56' ou '1234.56') ou número para Decimal."""
    if isinstance(valor_str, decimal.Decimal):
        return valor_str
    if isinstance(valor_str, (int, float)):
        return decimal.Decimal(str(valor_str))
    if isinstance(valor_str, str):
        valor_str = valor_str.strip()
        if "." in valor_str and "," not in valor_str:
            try:
                return decimal.Decimal(valor_str)
            except decimal.InvalidOperation:
                pass
        valor_sem_milhar = valor_str.replace(".", "")
        valor_com_ponto = valor_sem_milhar.replace(",", ".")
        try:
            return decimal.Decimal(valor_com_ponto)
        except decimal.InvalidOperation:
            try:
                return decimal.Decimal(valor_str)
            except decimal.InvalidOperation:
                return None
    return None


def formatar_br(valor):
    """Formata um valor numérico (idealmente Decimal) como moeda BRL (R$ 1.234,56)."""
    if valor is None:
        return "N/A"
    try:
        if not isinstance(valor, decimal.Decimal):
            valor = decimal.Decimal(str(valor))
        valor_str = "{:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace(
            "X", "."
        )
        return f"R$ {valor_str}"
    except (ValueError, TypeError, decimal.InvalidOperation):
        return "Valor inválido"


# --- Configuração da Aplicação Flask ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "FLASK_SECRET_KEY", "dev_fallback_secret_key_123!@#"
)
app.config["DATABASE"] = "contas.db"


# --- Inicializa o Banco de Dados (Cria as Tabelas) ---
with app.app_context():
    print("Inicializando o banco de dados...")
    init_db()  # Garante que as tabelas sejam criadas
    print("Banco de dados inicializado.")

# --- Executa Verificação/Atualização do Schema ---
with app.app_context():
    print("Executando verificação do schema...")
    check_and_apply_schema_updates()
    print("Verificação do schema finalizada.")

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # Rota para redirecionar se não logado
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    """Carrega um usuário pelo ID para o Flask-Login."""
    try:
        user_id_int = int(user_id)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id_int,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return User(id=row["id"], username=row["username"], password=row["password"])
        else:
            return None
    except Exception as e:
        print(f"Erro em load_user: {e}")
        return None


# --- Gerenciamento de Conexão com Banco (por requisição) ---
def get_db():
    """Obtém uma conexão com o banco de dados para a requisição atual."""
    if "db" not in g:
        g.db = get_db_connection()
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    """Fecha a conexão com o banco ao final da requisição."""
    db = g.pop("db", None)
    if db is not None:
        db.close()
    if e:
        print(f"Erro no teardown: {e}")


# --- Processadores de Contexto (funções disponíveis nos templates) ---
@app.context_processor
def inject_formatar_br():
    """Injeta a função formatar_br nos templates."""
    return dict(formatar_br=formatar_br)


@app.context_processor
def inject_get_tipo_pagamento():
    """Injeta uma função para buscar nome do tipo de pagamento nos templates."""

    def get_tipo_pagamento_nome(tipo_id):
        if not tipo_id:
            return "N/A"
        if "_tp_cache" not in g:
            g._tp_cache = {}
        if tipo_id not in g._tp_cache:
            g._tp_cache[tipo_id] = get_tipo_pagamento_by_id(tipo_id)
        tp = g._tp_cache[tipo_id]
        return tp.nome if tp else "Desconhecido"

    return dict(get_tipo_pagamento_nome=get_tipo_pagamento_nome)


# --- Funções Auxiliares Específicas da App ---
def atualizar_limite_saldo(tipo_pagamento, valor_decimal, adicionar=False, total_parcelas=None):
    """Atualiza limite (Cartao) ou saldo (ContaBancaria)."""
    if not isinstance(valor_decimal, decimal.Decimal):
        valor_decimal = valor_para_decimal(str(valor_decimal))
        if valor_decimal is None:
            print(f"Erro: valor inválido '{valor_decimal}'")
            return
    if tipo_pagamento:
        try:
            if isinstance(tipo_pagamento, Cartao):
                limite_disp = decimal.Decimal(str(tipo_pagamento.limite_disponivel))
                tipo_pagamento.limite_disponivel = (
                    limite_disp + valor_decimal
                    if adicionar
                    else limite_disp - valor_decimal
                )
                if not update_tipo_pagamento(tipo_pagamento):
                    print(f"ERRO ao salvar atualização limite TP ID {tipo_pagamento.id}")
            elif isinstance(tipo_pagamento, ContaBancaria):
                saldo = decimal.Decimal(str(tipo_pagamento.saldo))
                tipo_pagamento.saldo = saldo + valor_decimal if adicionar else saldo - valor_decimal
                if not update_tipo_pagamento(tipo_pagamento):
                    print(f"ERRO ao salvar atualização saldo TP ID {tipo_pagamento.id}")
        except Exception as e:
            print(
                f"Erro ao atualizar limite/saldo TP ID {tipo_pagamento.id if tipo_pagamento else 'N/A'}: {e}"
            )


def proximo_vencimento(vencimento_atual):
    """Calcula o próximo vencimento (geralmente mês seguinte)."""
    if isinstance(vencimento_atual, str):
        try:
            vencimento_atual = date.fromisoformat(vencimento_atual)
        except ValueError:
            return date.today() + timedelta(days=30)
    elif isinstance(vencimento_atual, datetime):
        vencimento_atual = vencimento_atual.date()
    elif not isinstance(vencimento_atual, date):
        return date.today() + timedelta(days=30)
    try:
        return vencimento_atual + relativedelta(months=1)
    except Exception as e:
        print(f"Erro calculando próximo vencimento (usando fallback): {e}")
        year = vencimento_atual.year
        month = vencimento_atual.month + 1
        day = vencimento_atual.day
        if month > 12:
            month = 1
            year += 1
        try:
            last_day = calendar.monthrange(year, month)[1]
            day = min(day, last_day)
            return date(year, month, day)
        except ValueError:
            return date.today() + timedelta(days=30)


def update_parcelas_recorrentes():
    """Verifica e atualiza contas parceladas/recorrentes vencidas."""
    today = date.today()
    conn = get_db()
    cursor = conn.cursor()
    updated_count = 0
    try:
        # Parceladas
        cursor.execute(
            "SELECT id, parcela_atual, total_parcelas, vencimento FROM contas "
            "WHERE total_parcelas IS NOT NULL AND total_parcelas > 0 "
            "AND parcela_atual < total_parcelas AND date(vencimento) < ?",
            (today.isoformat(),),
        )
        for row in cursor.fetchall():
            new_parc = (row["parcela_atual"] or 0) + 1
            try:
                new_venc = proximo_vencimento(date.fromisoformat(row["vencimento"]))
            except:
                print(f"Erro data parc ID {row['id']}")
                continue
            cursor.execute(
                "UPDATE contas SET parcela_atual = ?, vencimento = ? WHERE id = ?",
                (new_parc, new_venc.isoformat(), row["id"]),
            )
            updated_count += 1
        # Recorrentes
        cursor.execute(
            "SELECT id, vencimento, tipo_pagamento_id, valor FROM contas "
            "WHERE recorrente = 1 AND date(vencimento) < ?",
            (today.isoformat(),),
        )
        for row in cursor.fetchall():
            try:
                new_venc = proximo_vencimento(date.fromisoformat(row["vencimento"]))
            except:
                print(f"Erro data recorr ID {row['id']}")
                continue
            cursor.execute(
                "UPDATE contas SET vencimento = ? WHERE id = ?", (new_venc.isoformat(), row["id"])
            )
            if row["tipo_pagamento_id"]:
                tp = get_tipo_pagamento_by_id(row["tipo_pagamento_id"])
                if tp:
                    try:
                        atualizar_limite_saldo(
                            tp, decimal.Decimal(str(row["valor"])), adicionar=False
                        )
                    except:
                        print(f"Aviso: Valor inválido recorr ID {row['id']}")
            updated_count += 1
        if updated_count > 0:
            conn.commit()
            print(f"{updated_count} contas atualizadas.")
    except sqlite3.Error as sql_e:
        conn.rollback()
        print(f"Erro DB ao atualizar parcelas/recorrentes: {sql_e}")
    except Exception as e:
        conn.rollback()
        print(f"Erro ao atualizar parcelas/recorrentes: {e}")


# ======================================================================
#               INÍCIO DAS ROTAS PRINCIPAIS E LANDING PAGE
# ======================================================================

# --- ROTA RAIZ '/' - LANDING PAGE ---
# Esta rota será a primeira página que um usuário vê.
# Se ele não estiver logado, mostra a página de apresentação ('landing_page.html').
# Se ele JÁ estiver logado, redireciona automaticamente para o dashboard principal.
@app.route("/")
def landing_page():
    """Exibe a landing page para usuários não logados
    ou redireciona usuários logados para o dashboard.
    """
    # Verifica se o usuário atual (gerenciado pelo Flask-Login) está autenticado.
    if current_user.is_authenticated:
        # Se sim, redireciona para a função 'dashboard' (que responde pela rota '/dashboard').
        print("DEBUG: Usuário logado acessou '/', redirecionando para /dashboard.")
        return redirect(url_for("dashboard"))  # Redireciona para a rota do dashboard
    else:
        # Se não, renderiza o template da landing page.
        print("DEBUG: Usuário não logado acessou '/', mostrando landing_page.html.")
        return render_template("landing_page.html")


# --- ROTA '/dashboard' - DASHBOARD PRINCIPAL ---
# Esta é a página principal da aplicação para usuários LOGADOS.
# Acessível somente após o login (devido ao @login_required).
# A função foi renomeada de 'index' para 'dashboard'.
@app.route("/dashboard")
@login_required
def dashboard():
    print("DEBUG: Entrando na rota /dashboard...")

    try:
        update_parcelas_recorrentes()
        print("DEBUG: update_parcelas_recorrentes executado com sucesso em /dashboard.")
    except Exception as update_err:
        print(f"ERRO durante update_parcelas_recorrentes no /dashboard: {update_err}")
        flash(
            "Ocorreu um erro ao atualizar os vencimentos automáticos das contas.", "warning"
        )

    todas_as_contas = get_contas_by_user(current_user.id)
    contas = todas_as_contas

    print(f"DEBUG: User ID: {current_user.id}")
    print(
        f"DEBUG: Número de contas retornadas por get_contas_by_user: {len(todas_as_contas)}"
    )
    for conta in todas_as_contas:
        print(
            f"  - ID: {conta.id}, Nome: {conta.nome}, Categoria Nome: {conta.categoria_nome}, Valor: {conta.valor}, Vencimento: {conta.vencimento}"
        )

    total_por_categoria = {}
    contas_por_categoria = {}
    try:
        # Agrupa contas por categoria
        for conta in contas:
            try:
                valor_conta_decimal = decimal.Decimal("0.00")
                if conta.valor is not None:
                    try:
                        valor_conta_decimal = decimal.Decimal(str(conta.valor))
                    except:
                        print(
                            f"Aviso: Ignorando valor não-decimal '{conta.valor}' (ID: {conta.id}) no total por categoria dashboard."
                        )
                cat_nome = conta.categoria_nome if conta.categoria_nome else "Sem Categoria"
                total_por_categoria[cat_nome] = (
                    total_por_categoria.get(cat_nome, decimal.Decimal("0.00"))
                    + valor_conta_decimal
                )
                if cat_nome not in contas_por_categoria:
                    contas_por_categoria[cat_nome] = []
                contas_por_categoria[cat_nome].append(conta)
            except Exception as inner_e:
                print(
                    f"Erro processando conta ID {conta.id} no loop de categorias dashboard: {inner_e}"
                )
        print("DEBUG Dashboard: Agrupamento por categoria concluído.")
    except Exception as e:
        print(f"ERRO durante o processamento de contas: {e}")
        flash("Erro ao processar suas contas.", "error")
        contas = []  # Garantir que a variável contas existe, mesmo que esteja vazia.

    print(f"DEBUG: total_por_categoria: {total_por_categoria}")
    print(f"DEBUG: contas_por_categoria: {contas_por_categoria}")

    total_geral = decimal.Decimal("0.00")
    if contas:
        try:
            for c in contas:
                if c.valor is not None:
                    try:
                        total_geral += decimal.Decimal(str(c.valor))
                    except:
                        print(
                            f"Aviso: Ignorando valor não-decimal '{c.valor}' (ID: {c.id}) no total geral dashboard."
                        )
        except Exception as e_sum:
            print(f"Erro ao calcular total_geral dashboard: {e_sum}")
    print(f"DEBUG Dashboard: Total geral calculado: {total_geral}")

    data_hoje = date.today()

    try:
        cartoes = [
            tp
            for tp in get_tipos_pagamento_by_user(current_user.id)
            if isinstance(tp, Cartao)
        ]
        contas_bancarias = [
            tp
            for tp in get_tipos_pagamento_by_user(current_user.id)
            if isinstance(tp, ContaBancaria)
        ]

        total_cartao = sum(
            decimal.Decimal(str(c.limite_disponivel))
            for c in cartoes
            if c.limite_disponivel is not None
        )
        total_conta_bancaria = sum(
            decimal.Decimal(str(c.saldo))
            for c in contas_bancarias
            if c.saldo is not None
        )

        print(f"DEBUG: Número de cartões: {len(cartoes)}")
        print(f"DEBUG: Número de contas bancárias: {len(contas_bancarias)}")

    except Exception as e:
        print(f"ERRO ao buscar cartões e contas bancárias: {e}")
        flash("Erro ao buscar seus cartões e contas bancárias.", "error")
        cartoes = []
        contas_bancarias = []
        total_cartao = decimal.Decimal("0.00")
        total_conta_bancaria = decimal.Decimal("0.00")

    print("DEBUG: Tentando renderizar index.html a partir de /dashboard...")
    try:
        return render_template(
            "index.html",
            contas=contas,
            total_geral=total_geral,
            total_por_categoria=total_por_categoria,
            contas_por_categoria=contas_por_categoria,
            hoje=data_hoje,
            cartoes=cartoes,
            contas_bancarias=contas_bancarias,
            total_cartao=total_cartao,
            total_conta_bancaria=total_conta_bancaria,
        )
    except Exception as e:
        print(f"ERRO FATAL ao renderizar index.html a partir de /dashboard: {e}")
        import traceback

        traceback.print_exc()
        return f"Erro interno ao renderizar a página principal: {e}", 500


# ======================================================================
#                FIM DAS ROTAS PRINCIPAIS E LANDING PAGE
# ======================================================================


# --- Rotas de Gerenciamento de Categorias --- (Sem alterações lógicas necessárias)
@app.route("/categorias")
@login_required
def listar_categorias():
    try:
        categorias = get_categorias_by_user(current_user.id)
        return render_template("listar_categorias.html", categorias=categorias)
    except Exception as e:
        flash("Erro ao buscar categorias.", "error")
        print(f"Erro listar_categorias: {e}")
        return redirect(url_for("dashboard"))  # REDIRECIONA PARA O DASHBOARD


@app.route("/categorias/add", methods=["GET", "POST"])
@login_required
def add_categoria():
    form = CategoriaForm()
    if form.validate_on_submit():
        nome = form.nome.data.strip()
        existing = get_categoria_by_name_and_user(nome, current_user.id)
        if existing:
            flash(f'A categoria "{nome}" já existe.', "warning")
        else:
            if create_categoria(nome, current_user.id):
                flash("Categoria adicionada com sucesso!", "success")
                return redirect(url_for("listar_categorias"))
            else:
                flash("Erro ao adicionar categoria.", "error")
    return render_template("add_categoria.html", form=form, title="Adicionar Categoria")


@app.route("/categorias/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_categoria(id):
    categoria = get_categoria_by_id(id, current_user.id)
    if not categoria:
        flash("Categoria não encontrada.", "error")
        return redirect(url_for("listar_categorias"))
    form = CategoriaForm(obj=categoria)
    if form.validate_on_submit():
        novo_nome = form.nome.data.strip()
        if novo_nome.lower() != categoria.nome.lower():
            existing = get_categoria_by_name_and_user(novo_nome, current_user.id)
            if existing and existing.id != id:
                flash(f'Já existe outra categoria com o nome "{novo_nome}".', "warning")
            else:
                if update_categoria(id, novo_nome, current_user.id):
                    flash("Categoria atualizada!", "success")
                    return redirect(url_for("listar_categorias"))
                else:
                    flash("Erro ao atualizar categoria.", "error")
        else:
            return redirect(url_for("listar_categorias"))
    return render_template(
        "add_categoria.html", form=form, title="Editar Categoria", categoria=categoria
    )

@app.route("/categorias/delete/<int:id>", methods=["POST"])
@login_required
def delete_categoria_route(id):  # Renomeei para evitar conflito com a função do banco
    categoria = get_categoria_by_id(id, current_user.id)
    if not categoria:
        flash("Categoria não encontrada.", "error")
    else:
        if delete_categoria(id, current_user.id):  # Agora passando corretamente o user_id
            flash("Categoria excluída!", "success")
        else:
            flash("Erro ao excluir categoria.", "error")
    return redirect(url_for("listar_categorias"))


# --- Rotas de Gerenciamento de Contas (Despesas/Receitas) --- (Sem alterações lógicas necessárias, exceto redirecionamentos)


def _populate_conta_form_choices(form):
    """Popula os campos SelectField do ContaForm."""
    try:
        cats = get_categorias_by_user(current_user.id)
        form.categoria_id.choices = [(0, "-- Selecione --")] + [
            (c.id, c.nome) for c in cats
        ]
        tps = get_tipos_pagamento_by_user(current_user.id)
        form.tipo_pagamento.choices = [(0, "-- Nenhum / Manual --")] + [
            (tp.id, f"{tp.nome} ({'Cartão' if isinstance(tp, Cartao) else 'Conta'})")
            for tp in tps
        ]
    except Exception as e:
        print(f"Erro ao popular choices conta: {e}")
        form.categoria_id.choices = [(0, "-- Erro --")]
        form.tipo_pagamento.choices = [(0, "-- Erro --")]


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_conta():
    form = ContaForm()
    _populate_conta_form_choices(form)
    if form.validate_on_submit():
        val_dec = valor_para_decimal(form.valor.data)
        val_total_compra_str = form.valor_total_compra.data  # Pega o valor total como STRING
        if val_dec is None:
            flash("Valor da Parcela inválido.", "error")  # Mensagem de erro apropriada
            return render_template("add_conta.html", form=form, title="Adicionar Conta")

        if val_total_compra_str:
            val_total_compra_dec = valor_para_decimal(
                val_total_compra_str
            )  # Converte valor total para Decimal
            if val_total_compra_dec is None:
                flash("Valor Total da Compra inválido.", "error")
                return render_template("add_conta.html", form=form, title="Adicionar Conta")
        else:
            val_total_compra_dec = val_dec  # Se não fornecido, usa o valor da parcela

        cat_id = form.categoria_id.data if form.categoria_id.data != 0 else None
        tp_id = form.tipo_pagamento.data if form.tipo_pagamento.data != 0 else None
        venc_date = form.vencimento.data
        parc_atual = form.parcela_atual.data or None
        total_parc = form.total_parcelas.data or None
        if total_parc and not parc_atual:
            parc_atual = 1
        if parc_atual and total_parc and parc_atual > total_parc:
            flash("Parcela atual > total.", "error")
            return render_template("add_conta.html", form=form, title="Adicionar Conta")

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO contas (nome, valor, valor_total_compra, vencimento, categoria_id, parcela_atual, total_parcelas, user_id, recorrente, tipo_pagamento_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    form.nome.data.strip(),
                    float(val_dec),
                    float(val_total_compra_dec),
                    venc_date.isoformat(),
                    cat_id,
                    parc_atual,
                    total_parc,
                    current_user.id,
                    int(form.recorrente.data),
                    tp_id,
                ),
            )
            conn.commit()
            if tp_id:
                tp = get_tipo_pagamento_by_id(tp_id)
                if tp:
                    atualizar_limite_saldo(
                        tp,
                        val_total_compra_dec,
                        adicionar=False,
                        total_parcelas=total_parc,
                    )  # Usa o valor TOTAL para atualizar o limite
            flash("Conta adicionada!", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            conn.rollback()
            flash(f"Erro: {e}", "error")
            print(f"ERRO INSERT CONTA: {e}")
    return render_template("add_conta.html", form=form, title="Adicionar Conta")


@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_conta(id):
    conta = get_conta_by_id(id, current_user.id)
    if not conta:
        flash("Conta não encontrada.", "error")
        return redirect(url_for("dashboard"))

    val_orig = conta.valor  # valor da parcela original
    val_total_orig = conta.valor_total_compra  # valor total da compra original
    tp_id_orig = conta.tipo_pagamento_id
    tot_parc_orig = conta.total_parcelas
    form = ContaForm(obj=conta)

    if request.method == "GET":
        try:
            form.valor.data = (
                str(conta.valor).replace(".", ",") if conta.valor is not None else ""
            )  # valor da parcela
            form.valor_total_compra.data = (
                str(conta.valor_total_compra).replace(".", ",")
                if conta.valor_total_compra is not None
                else ""
            )  # valor total
        except Exception as fmt_err:
            print(f"Erro formatar valor GET: {fmt_err}")
            form.valor.data = ""
            form.valor_total_compra.data = ""
        form.vencimento.data = conta.vencimento
        form.categoria_id.data = conta.categoria_id if conta.categoria_id else 0
        form.tipo_pagamento.data = conta.tipo_pagamento_id if conta.tipo_pagamento_id else 0
        form.recorrente.data = bool(conta.recorrente)

    _populate_conta_form_choices(form)

    if form.validate_on_submit():
        val_novo_dec = valor_para_decimal(form.valor.data)  # valor da parcela
        val_novo_tot_str = form.valor_total_compra.data  # pega o valor total como string

        if val_novo_dec is None:
            flash("Valor da Parcela inválido.", "error")  # Mensagem apropriada
            return render_template("edit_conta.html", form=form, conta=conta, title="Editar Conta")

        if val_novo_tot_str:
            val_novo_tot_dec = valor_para_decimal(
                val_novo_tot_str
            )  # converte valor total para decimal
            if val_novo_tot_dec is None:
                flash("Valor Total da Compra inválido.", "error")
                return render_template("edit_conta.html", form=form, conta=conta, title="Editar Conta")
        else:
            val_novo_tot_dec = val_novo_dec  # usa o valor da parcela se total não for fornecido

        tp_id_novo = form.tipo_pagamento.data if form.tipo_pagamento.data != 0 else None

        reverted_step1 = False
        try:
            # Passo 1: Reverte antigo
            if tp_id_orig:
                tp_antigo = get_tipo_pagamento_by_id(tp_id_orig)
                if tp_antigo:
                    atualizar_limite_saldo(
                        tp_antigo, val_total_orig, adicionar=True, total_parcelas=tot_parc_orig
                    )
                    reverted_step1 = True
            # Passo 2: Atualiza objeto
            conta.nome = form.nome.data.strip()
            conta.valor = val_novo_dec  # Atualiza o valor da PARCELA
            conta.valor_total_compra = val_novo_tot_dec  # atualiza o valor total
            conta.vencimento = form.vencimento.data
            conta.categoria_id = form.categoria_id.data if form.categoria_id.data != 0 else None
            conta.parcela_atual = form.parcela_atual.data or None
            conta.total_parcelas = form.total_parcelas.data or None
            conta.recorrente = form.recorrente.data
            conta.tipo_pagamento_id = tp_id_novo
            if conta.total_parcelas and not conta.parcela_atual:
                conta.parcela_atual = 1
            if conta.parcela_atual and conta.total_parcelas and conta.parcela_atual > conta.total_parcelas:
                raise ValueError("Parcela atual > total.")
            # Passo 3: Salva conta no DB
            if update_conta(conta):
                # Passo 4: Aplica novo
                if tp_id_novo:
                    tp_novo = get_tipo_pagamento_by_id(tp_id_novo)
                    if tp_novo:
                        atualizar_limite_saldo(
                            tp_novo,
                            val_novo_tot_dec,
                            adicionar=False,
                                                                          total_parcelas=conta.total_parcelas,
                        )  # Usar o valor TOTAL
                flash("Conta atualizada!", "success")
                return redirect(url_for("dashboard"))  # REDIRECIONA PARA O DASHBOARD
            else:  # Falha no save DB
                flash("Erro ao salvar alterações no DB.", "error")
                if reverted_step1 and tp_id_orig:  # Tenta reverter passo 1
                    tp_antigo_revert = get_tipo_pagamento_by_id(tp_id_orig)
                    if tp_antigo_revert:
                        atualizar_limite_saldo(
                            tp_antigo_revert,
                            val_total_orig,
                            adicionar=False,
                            total_parcelas=tot_parc_orig,
                        )  # usa valor total
        except Exception as e:  # Erro geral ou de validação
            flash(f"Erro: {e}", "error")
            print(f"ERRO EDIT CONTA: {e}")
            if reverted_step1 and tp_id_orig:  # Tenta reverter passo 1
                tp_antigo_revert_exc = get_tipo_pagamento_by_id(tp_id_orig)
                if tp_antigo_revert_exc:
                    atualizar_limite_saldo(
                        tp_antigo_revert_exc,
                        val_total_orig,
                        adicionar=False,
                        total_parcelas=tot_parc_orig,
                    )  # usa valor total
    return render_template("edit_conta.html", form=form, conta=conta, title="Editar Conta")


@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_conta(id):
    conta = get_conta_by_id(id, current_user.id)
    if not conta:
        flash("Conta não encontrada.", "error")
        return redirect(url_for("dashboard"))  # REDIRECIONA PARA O DASHBOARD

    val_conta = conta.valor  # valor da parcela
    val_total_conta = conta.valor_total_compra  # valor total
    tp_id_conta = conta.tipo_pagamento_id
    tot_parc_conta = conta.total_parcelas
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM contas WHERE id = ? AND user_id = ?", (id, current_user.id))
        deleted_rows = cursor.rowcount
        conn.commit()
        if deleted_rows > 0:
            if tp_id_conta:
                tp = get_tipo_pagamento_by_id(tp_id_conta)
                if tp:
                    atualizar_limite_saldo(
                        tp,
                        val_total_conta,
                        adicionar=True,
                        total_parcelas=tot_parc_conta,
                    )  # DEVOLVER O VALOR TOTAL!
            flash("Conta excluída!", "success")
        else:
            flash("Conta não encontrada.", "warning")
    except Exception as e:
        conn.rollback()
        flash(f"Erro: {e}", "error")
        print(f"ERRO DELETE CONTA: {e}")
    return redirect(url_for("dashboard"))  # REDIRECIONA PARA O DASHBOARD


# --- Rota view para visualizar detalhes de uma conta ---
@app.route("/detalhes_financeiros")
@login_required
def detalhes_financeiros():
    """Exibe detalhes individuais de cartões e contas bancárias."""
    try:
        cartoes = [
            tp
            for tp in get_tipos_pagamento_by_user(current_user.id)
            if isinstance(tp, Cartao)
        ]
        contas_bancarias = [
            tp
            for tp in get_tipos_pagamento_by_user(current_user.id)
            if isinstance(tp, ContaBancaria)
        ]

        # Obtenha as compras de cartão (contas) associadas a cada cartão
        for cartao in cartoes:
            cartao.compras = []  # Inicializa a lista de compras do cartão
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, nome, valor, valor_total_compra FROM contas WHERE tipo_pagamento_id = ? AND user_id = ?",
                (cartao.id, current_user.id),
            )
            compras_raw = cursor.fetchall()
            for row in compras_raw:
                compra = {
                    "id": row["id"],
                    "nome": row["nome"],
                    "valor": row["valor"],  # valor da parcela
                    "valor_total_compra": row["valor_total_compra"],  # valor total da compra
                }
                cartao.compras.append(compra)

        # Calculate total from cartoes and contas_bancarias
        total_cartao = sum(
            decimal.Decimal(str(c.limite_disponivel))
            for c in cartoes
            if c.limite_disponivel is not None
        )
        total_conta_bancaria = sum(
            decimal.Decimal(str(c.saldo))
            for c in contas_bancarias
            if c.saldo is not None
        )

    except Exception as e:
        print(f"ERRO ao buscar cartões e contas bancárias: {e}")
        flash("Erro ao buscar seus cartões e contas bancárias.", "error")
        cartoes = []
        contas_bancarias = []
        total_cartao = decimal.Decimal("0.00")
        total_conta_bancaria = decimal.Decimal("0.00")

    return render_template(
        "detalhes_financeiros.html",
        cartoes=cartoes,
        contas_bancarias=contas_bancarias,
        total_cartao=total_cartao,
        total_conta_bancaria=total_conta_bancaria,
    )


# --- Rotas de Relatórios --- (Sem alterações lógicas necessárias, exceto link Voltar)
@app.route("/relatorio/selecionar", methods=["GET"])
@login_required
def selecionar_relatorio():
    now = datetime.now()
    ano_atual = now.year
    mes_atual = now.month
    anos = range(ano_atual + 2, ano_atual - 5, -1)
    meses = [(m, calendar.month_name[m].capitalize()) for m in range(1, 13)]
    try:
        cats = get_categorias_by_user(current_user.id)
    except Exception as e:
        flash("Erro ao carregar categorias.", "error")
        print(f"Erro sel_relatorio cats: {e}")
        cats = []
    return render_template(
        "selecionar_relatorio.html",
        anos=anos,
        meses=meses,
        categorias_disponiveis=cats,
        ano_atual=ano_atual,
        mes_atual=mes_atual,
    )

@app.route("/relatorio/visualizar", methods=["GET"])
@login_required
def visualizar_relatorio_mensal():
    try:
        mes = int(request.args.get("mes"))
        ano = int(request.args.get("ano"))
        cat_ids_str = request.args.getlist("categoria_id")
        cat_ids = []
        for s in cat_ids_str:
            try:
                i = int(s)
                cat_ids.append(i) if i > 0 else None
            except ValueError:
                flash(f"ID cat inválido: {s}", "warning")
        if not (1 <= mes <= 12):
            raise ValueError("Mês inválido")
    except (TypeError, ValueError, AttributeError):
        flash("Mês ou Ano inválidos.", "error")
        return redirect(url_for("selecionar_relatorio"))

    mes_str = f"{mes:02d}"
    ano_str = str(ano)
    sel_cat_names = []
    try:  # Busca nomes das categorias selecionadas
        if cat_ids:
            all_cats_dict = {c.id: c.nome for c in get_categorias_by_user(current_user.id)}
            sel_cat_names = [all_cats_dict.get(cid, f"ID {cid}?") for cid in cat_ids]
    except Exception as e:
        print(f"Erro nomes cats: {e}")
        flash("Erro filtro cats.", "warning")

    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT c.*, cat.nome as categoria_nome FROM contas c LEFT JOIN categorias cat ON c.categoria_id = cat.id WHERE c.user_id = ? AND strftime('%Y', c.vencimento) = ? AND strftime('%m', c.vencimento) = ?"
    params = [current_user.id, ano_str, mes_str]
    if cat_ids:
        placeholders = ", ".join("?" * len(cat_ids))
        query += f" AND c.categoria_id IN ({placeholders})";
        params.extend(cat_ids)
    query += " ORDER BY c.vencimento"

    try:
        cursor.execute(query, params)
        contas_raw = cursor.fetchall()
        contas_mes = []
        for row in contas_raw:
            try:
                c_obj = Conta(
                    id=row["id"],
                    nome=row["nome"],
                    valor=row["valor"],
                    valor_total_compra=row["valor_total_compra"],  # Adicionado
                    vencimento=row["vencimento"],
                    categoria_id=row["categoria_id"],
                    parcela_atual=row["parcela_atual"],
                    total_parcelas=row["total_parcelas"],
                    user_id=row["user_id"],
                    recorrente=row["recorrente"],
                    tipo_pagamento_id=row["tipo_pagamento_id"],
                )
                c_obj.categoria_nome = row["categoria_nome"]
                contas_mes.append(c_obj)
            except Exception as init_err:
                print(f"Erro init Conta ID {row['id']} relat: {init_err}")  # Removido .get

        total_mes = sum(
            decimal.Decimal(str(c.valor)) for c in contas_mes if c.valor is not None
        )
        total_por_cat = {}
        for c in contas_mes:
            try:
                if c.valor is not None:
                    val_dec = decimal.Decimal(str(c.valor))
                    cat_n = c.categoria_nome or "Sem Categoria"
                    total_por_cat[cat_n] = total_por_cat.get(
                        cat_n, decimal.Decimal("0.00")
                    ) + val_dec
            except:
                print(f"Aviso: Ignorando valor '{c.valor}' total cat relat.")

        try:
            nome_mes = calendar.month_name[mes].capitalize()
        except IndexError:
            nome_mes = f"Mês {mes}"

        return render_template(
            "visualizar_relatorio_mensal.html",
            contas_mes=contas_mes,
            total_mes=total_mes,
            total_por_categoria_mes=total_por_cat,
            mes=mes,
            ano=ano,
            nome_mes=nome_mes,
            selected_categories_display=sel_cat_names,
        )
    except sqlite3.Error as sql_e:
        flash(f"Erro DB: {sql_e}", "error")
        print(f"ERRO SQL relat: {sql_e}")
        return redirect(url_for("selecionar_relatorio"))
    except Exception as e:
        flash(f"Erro: {e}", "error")
        print(f"ERRO relat: {e}")
        import traceback

        traceback.print_exc()
        return redirect(url_for("selecionar_relatorio"))


# --- Rotas de Gerenciamento de Cartões --- (Sem alterações lógicas necessárias, exceto redirecionamentos)
@app.route("/cartoes")
@login_required
def listar_cartoes():
    try:
        cartoes = [
            tp
            for tp in get_tipos_pagamento_by_user(current_user.id)
            if isinstance(tp, Cartao)
        ]
        return render_template("listar_cartoes.html", cartoes=cartoes)
    except Exception as e:
        flash("Erro ao listar cartões.", "error")
        print(f"Erro listar_cartoes: {e}")
        return redirect(url_for("dashboard"))  # REDIRECIONA PARA O DASHBOARD


@app.route("/cartoes/add", methods=["GET", "POST"])
@login_required
def add_cartao():
    form = CartaoForm()
    if form.validate_on_submit():
        lim_dec = valor_para_decimal(form.limite.data)
        if lim_dec is None:
            flash("Limite inválido.", "error")
            return render_template("add_cartao.html", form=form, title="Adicionar Cartão")
        try:
            create_tipo_pagamento(
                nome=form.nome.data.strip(),
                tipo="cartao",
                limite=lim_dec,
                limite_disponivel=lim_dec,
                user_id=current_user.id,
            )
            flash("Cartão adicionado!", "success")
            return redirect(url_for("listar_cartoes"))
        except Exception as e:
            flash(f"Erro: {e}", "error")
            print(f"ERRO add_cartao: {e}")
    return render_template("add_cartao.html", form=form, title="Adicionar Cartão")


@app.route("/cartoes/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_cartao(id):
    cartao = get_tipo_pagamento_by_id(id)
    if not cartao or not isinstance(cartao, Cartao) or cartao.user_id != current_user.id:
        flash("Cartão não encontrado.", "error")
        return redirect(url_for("listar_cartoes"))
    form = CartaoForm(obj=cartao)
    if request.method == "GET":
        form.limite.data = str(cartao.limite).replace(".", ",")
    if form.validate_on_submit():
        try:
            lim_novo = valor_para_decimal(form.limite.data)
            if lim_novo is None:
                flash("Limite inválido.", "error")
                return render_template(
                    "edit_cartao.html", form=form, cartao=cartao, title="Editar Cartão"
                )
            lim_antigo = cartao.limite
            dif = lim_novo - lim_antigo
            cartao.nome = form.nome.data.strip()
            cartao.limite = lim_novo
            cartao.limite_disponivel += dif
            if update_tipo_pagamento(cartao):
                flash("Cartão atualizado!", "success")
                return redirect(url_for("listar_cartoes"))
            else:
                flash("Erro ao salvar cartão.", "error")
        except Exception as e:
            flash(f"Erro: {e}", "error")
            print(f"ERRO edit_cartao: {e}")
    return render_template("edit_cartao.html", form=form, cartao=cartao, title="Editar Cartão")


@app.route("/cartoes/delete/<int:id>", methods=["POST"])
@login_required
def delete_cartao(id):
    cartao = get_tipo_pagamento_by_id(id)
    if not cartao or not isinstance(cartao, Cartao) or cartao.user_id != current_user.id:
        flash("Cartão não encontrado.", "error")
    else:
        if delete_tipo_pagamento(id, current_user.id):
            flash("Cartão excluído!", "success")
        else:
            flash("Não foi possível excluir. Verifique contas vinculadas.", "error")
    return redirect(url_for("listar_cartoes"))


# --- Rotas de Gerenciamento de Contas Bancárias --- (Sem alterações lógicas necessárias, exceto redirecionamentos)
@app.route("/contas_bancarias")
@login_required
def listar_contas_bancarias():
    try:
        contas = [
            tp
            for tp in get_tipos_pagamento_by_user(current_user.id)
            if isinstance(tp, ContaBancaria)
        ]
        return render_template("listar_contas_bancarias.html", contas_bancarias=contas)
    except Exception as e:
        flash("Erro ao listar contas bancárias.", "error")
        print(f"Erro listar_contas_bancarias: {e}")
        return redirect(url_for("dashboard"))  # REDIRECIONA PARA O DASHBOARD


@app.route("/contas_bancarias/add", methods=["GET", "POST"])
@login_required
def add_conta_bancaria():
    form = ContaBancariaForm()
    if form.validate_on_submit():
        saldo_dec = valor_para_decimal(form.saldo.data)
        if saldo_dec is None:
            flash("Saldo inválido.", "error")
            return render_template(
                "add_conta_bancaria.html", form=form, title="Adicionar Conta Bancária"
            )
        try:
            create_tipo_pagamento(
                nome=form.nome.data.strip(), tipo="conta", saldo=saldo_dec, user_id=current_user.id
            )
            flash("Conta bancária adicionada!", "success")
            return redirect(url_for("listar_contas_bancarias"))
        except Exception as e:
            flash(f"Erro: {e}", "error")
            print(f"ERRO add_conta_bancaria: {e}")
    return render_template(
        "add_conta_bancaria.html", form=form, title="Adicionar Conta Bancária"
    )


@app.route("/contas_bancarias/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_conta_bancaria(id):
    conta_b = get_tipo_pagamento_by_id(id)
    if not conta_b or not isinstance(conta_b, ContaBancaria) or conta_b.user_id != current_user.id:
        flash("Conta bancária não encontrada.", "error")
        return redirect(url_for("listar_contas_bancarias"))
    form = ContaBancariaForm(obj=conta_b)
    if request.method == "GET":
        form.saldo.data = str(conta_b.saldo).replace(".", ",")
    if form.validate_on_submit():
        try:
            saldo_novo = valor_para_decimal(form.saldo.data)
            if saldo_novo is None:
                flash("Saldo inválido.", "error")
                return render_template(
                    "edit_conta_bancaria.html",
                    form=form,
                    conta_bancaria=conta_b,
                    title="Editar Conta Bancária",
                )
            conta_b.nome = form.nome.data.strip()
            conta_b.saldo = saldo_novo
            if update_tipo_pagamento(conta_b):
                flash("Conta bancária atualizada!", "success")
                return redirect(url_for("listar_contas_bancarias"))
            else:
                flash("Erro ao salvar conta bancária.", "error")
        except Exception as e:
            flash(f"Erro: {e}", "error")
            print(f"ERRO edit_conta_bancaria: {e}")
    return render_template(
        "edit_conta_bancaria.html", form=form, conta_bancaria=conta_b, title="Editar Conta Bancária"
    )


@app.route("/contas_bancarias/delete/<int:id>", methods=["POST"])
@login_required
def delete_conta_bancaria(id):
    conta_b = get_tipo_pagamento_by_id(id)
    if not conta_b or not isinstance(conta_b, ContaBancaria) or conta_b.user_id != current_user.id:
        flash("Conta bancária não encontrada.", "error")
    else:
        if delete_tipo_pagamento(id, current_user.id):
            flash("Conta bancária excluída!", "success")
        else:
            flash("Não foi possível excluir. Verifique contas vinculadas.", "error")
    return redirect(url_for("listar_contas_bancarias"))


# --- Rotas de Autenticação --- (Ajustar redirecionamentos)
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))  # REDIRECIONA PARA O DASHBOARD
    form = LoginForm()
    if form.validate_on_submit():
        user = get_user_by_username(form.username.data)
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Login realizado com sucesso!", "success")
            print("DEBUG: Redirecionando para o dashboard após login.")
            return redirect(url_for("dashboard"))  # !! ALTERADO: Redireciona para 'dashboard' !!
        else:
            flash("Usuário ou senha inválidos.", "error")
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso!", "success")
    return redirect(url_for("login"))  # Após logout, vai para login


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))  # REDIRECIONA PARA O DASHBOARD
    form = RegisterForm()
    if form.validate_on_submit():
        if get_user_by_username(form.username.data):
            flash("Nome de usuário já em uso.", "warning")
        else:
            hashed_pw = generate_password_hash(form.password.data)
            if create_user(form.username.data, hashed_pw):
                flash("Conta criada com sucesso! Faça login.", "success")
                return redirect(url_for("login"))
            else:
                flash("Erro ao criar a conta.", "error")
    return render_template("register.html", form=form)


@app.route("/reset_password", methods=["GET", "POST"])
@login_required
def reset_password():
    form = ResetPasswordForm()
    # O campo username no form de reset pode ser removido ou apenas usado para display
    # A lógica DEVE usar current_user para identificar quem está mudando a senha.
    if form.validate_on_submit():
        user = get_user_by_username(current_user.username)  # Pega o usuário logado
        if user:
            # Idealmente, verificar a senha ATUAL aqui antes de permitir a mudança
            new_hashed_pw = generate_password_hash(form.new_password.data)
            conn = get_db()
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_hashed_pw, user.id))
                conn.commit()
                flash("Senha alterada com sucesso!", "success")
                return redirect(url_for("dashboard"))  # !! ALTERADO: Redireciona para 'dashboard' !!
            except Exception as e:
                conn.rollback()
                flash(f"Erro ao alterar senha: {e}", "error")
                print(f"ERRO reset_password DB: {e}")
        else:
            flash("Usuário não encontrado.", "error")
    # Passa o username atual para o template (pode ser usado no título ou texto)
    return render_template("reset_password.html", form=form, current_username=current_user.username)


# --- Execução Principal ---
if __name__ == "__main__":
    print("Iniciando servidor Waitress em http://0.0.0.0:5000")
    # Use Waitress para servir a aplicação em produção ou para testes mais robustos
    # O servidor de desenvolvimento do Flask (app.run()) é ideal apenas para desenvolvimento.
    serve(app, host="0.0.0.0", port=5000)
