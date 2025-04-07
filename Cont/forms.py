from flask_wtf import FlaskForm  # Importa a classe base para formulários Flask-WTF
from wtforms import (  # Importa os tipos de campos de formulário
    StringField, DateField, SelectField, SubmitField, PasswordField,
    IntegerField, BooleanField, HiddenField  # HiddenField não usado aqui, mas comum
)
from wtforms.validators import (  # Importa validadores para os campos
    DataRequired,  # Garante que o campo não está vazio
    Length,  # Valida o comprimento mínimo e/ou máximo de uma string
    EqualTo,  # Garante que o valor de um campo é igual ao de outro (ex: confirmação de senha)
    Optional,  # Torna a validação DataRequired opcional (campo pode ser vazio)
    InputRequired,  # Semelhante a DataRequired, mas funciona melhor com SelectField e 0 como valor inválido
    NumberRange,  # Garante que um número está dentro de um intervalo (min/max)
    ValidationError  # Usado para lançar erros de validação personalizados
)
import decimal  # Para manipulação precisa de valores decimais (monetários)


# --- Função Auxiliar para Validação de Campo Decimal ---
# Esta função será usada como um validador customizado para campos que representam dinheiro.
def valor_para_decimal(valor_str):
    """
    Converte uma string formatada em português brasileiro (ex: '1.234,56')
    ou formato numérico ('1234.56') para um objeto Decimal.
    Também aceita int ou float. Retorna None em caso de erro.
    """
    # Se já for Decimal, retorna
    if isinstance(valor_str, decimal.Decimal):
        return valor_str
    # Se for int ou float, converte para string primeiro para evitar imprecisão
    if isinstance(valor_str, (int, float)):
        return decimal.Decimal(str(valor_str))
    # Se for string, processa
    if isinstance(valor_str, str):
        valor_str = valor_str.strip()  # Remove espaços extras
        # Verifica se já está em formato decimal direto (ex: '1234.56')
        if '.' in valor_str and ',' not in valor_str:
            try:
                return decimal.Decimal(valor_str)
            except decimal.InvalidOperation:
                pass  # Se falhar, continua para verificar formato BR

        # Assume formato BR: remove '.' de milhar, troca ',' de decimal por '.'
        valor_sem_milhar = valor_str.replace('.', '')
        valor_com_ponto = valor_sem_milhar.replace(',', '.')
        try:
            # Tenta converter após tratamento do formato BR
            return decimal.Decimal(valor_com_ponto)
        except decimal.InvalidOperation:
            # Última tentativa: converter a string original diretamente (pode funcionar para '123')
            try:
                return decimal.Decimal(valor_str)
            except decimal.InvalidOperation:
                # Se todas as tentativas falharem
                print(f"AVISO (valor_para_decimal): Falha ao converter '{valor_str}' para Decimal.")
                return None  # Indica falha
    # Se não for um tipo reconhecido
    return None


# --- Validador Customizado para Campos Decimal ---
def decimal_field_validator(form, field):
    """Validador WTForms para garantir que o campo contém um valor decimal válido e não negativo.
       Tenta converter a string usando a função `valor_para_decimal`.
    """
    try:
        # Tenta converter o dado do campo (que vem como string) para Decimal
        # usando a função auxiliar 'valor_para_decimal'.
        val = valor_para_decimal(field.data)
        # Se a conversão retornar None, significa que o formato é inválido.
        if val is None:
            raise ValidationError('Valor inválido. Use formato como 1.234,56 ou 1234.56')
        # Verifica se o valor convertido é negativo.
        if val < decimal.Decimal('0.00'):
            raise ValidationError('O valor não pode ser negativo.')
    # Captura erros que podem ocorrer durante a conversão (ValueError, TypeError) ou
    # operações com Decimal (InvalidOperation).
    except (ValueError, TypeError, decimal.InvalidOperation):
        raise ValidationError('Formato de valor inválido.')
    except NameError:
        # --- Fallback caso `valor_para_decimal` não esteja definida neste escopo ---
        # Isso é menos robusto, mas tenta uma conversão básica.
        print("AVISO: Função 'valor_para_decimal' não encontrada. Usando validação decimal básica.")
        try:
            # Limpeza básica: remove pontos de milhar, troca vírgula por ponto.
            cleaned_data = str(field.data).replace('.', '').replace(',', '.')
            val = decimal.Decimal(cleaned_data)  # Tenta converter a string limpa
            # Verifica se é negativo.
            if val < decimal.Decimal('0.00'):
                raise ValidationError('O valor não pode ser negativo.')
        except:  # Captura qualquer erro na conversão fallback.
            raise ValidationError('Formato de valor inválido.')


# --- Formulário para Adicionar/Editar Conta (Despesa/Receita) ---
class ContaForm(FlaskForm):
    # Campo para o nome/descrição da conta. Obrigatório, máximo 100 caracteres.
    nome = StringField('Nome da Conta',
                       validators=[DataRequired(message="O nome da conta é obrigatório."),
                                   Length(max=100)])
    # Campo para o valor da PARCELA. Usa StringField para aceitar formatos com vírgula/ponto.
    # Obrigatório. Usa o validador customizado 'decimal_field_validator'.
    valor = StringField('Valor da Parcela',
                        validators=[DataRequired(message="O valor da parcela é obrigatório."),
                                    decimal_field_validator])
    # Campo para o valor TOTAL da compra. Opcional.  Usa o mesmo validador.
    valor_total_compra = StringField('Valor Total da Compra (Opcional)', validators=[Optional(), decimal_field_validator]) # Valor TOTAL
    # Campo para a data de vencimento. Obrigatório. Espera formato YYYY-MM-DD.
    vencimento = DateField('Vencimento', format='%Y-%m-%d',
                            validators=[DataRequired(message="A data de vencimento é obrigatória.")])
    # Campo de seleção (dropdown) para a categoria.
    # `coerce=int` converte o valor selecionado (que vem como string) para inteiro.
    # `InputRequired` garante que uma opção válida (não o valor padrão 0) seja selecionada.
    categoria_id = SelectField(
        'Categoria',
        coerce=int,
        validators=[InputRequired(message="Selecione uma categoria.")],
        # As opções ('choices') serão preenchidas dinamicamente na rota/view.
        # Define uma opção padrão inicial que será considerada inválida pelo `validate_categoria_id`.
        choices=[(0, '-- Selecione uma Categoria --')]
    )
    # Campo para a parcela atual. Opcional, mas se preenchido, deve ser um número >= 1.
    parcela_atual = IntegerField('Parcela Atual',
                                 validators=[Optional(), NumberRange(min=1, message="Parcela deve ser 1 ou maior.")])
    # Campo para o total de parcelas. Opcional, mas se preenchido, deve ser >= 1.
    total_parcelas = IntegerField('Total de Parcelas',
                                  validators=[Optional(), NumberRange(min=1, message="Total de parcelas deve ser 1 ou maior.")])
    # Campo checkbox para indicar se a conta é recorrente.
    recorrente = BooleanField('Esta conta é recorrente?')  # Label ligeiramente alterado para clareza
    # Campo de seleção (dropdown) para o tipo de pagamento (Cartão/Conta Bancária).
    # `coerce=int` converte para inteiro. `Optional` permite que seja deixado em branco (ou a opção padrão).
    # Se for obrigatório associar a um pagamento, use `InputRequired`.
    tipo_pagamento = SelectField('Pagar com / Associar a', coerce=int,
                                  validators=[Optional()])  # Texto do label mais explicativo
    # Botão de submissão do formulário.
    submit = SubmitField('Salvar Conta')

    # --- Validação Customizada entre Campos ---
    # Método chamado automaticamente pelo WTForms para validar o campo 'total_parcelas' APÓS os validadores básicos.
    def validate_total_parcelas(self, field):
        # Verifica se 'total_parcelas' (field.data) e 'parcela_atual' foram preenchidos
        # E se a parcela atual é maior que o total.
        if field.data and self.parcela_atual.data and self.parcela_atual.data > field.data:
            # Se for maior, lança um erro de validação específico para o campo 'total_parcelas'.
            raise ValidationError('Parcela atual não pode ser maior que o total de parcelas.')
        # Se o total de parcelas foi informado, mas a parcela atual não foi...
        if field.data and not self.parcela_atual.data:
            # Define a parcela atual como 1 por padrão.
            self.parcela_atual.data = 1

    # Método para validar especificamente o campo 'categoria_id'.
    def validate_categoria_id(self, field):
        # Verifica se o valor selecionado é 0 (que definimos como a opção inválida '-- Selecione --').
        if field.data == 0:
            # Lança um erro se a opção padrão ainda estiver selecionada.
            raise ValidationError('Por favor, selecione uma categoria válida.')


# --- Formulário para Adicionar/Editar Categoria ---
class CategoriaForm(FlaskForm):
    # Campo para o nome da categoria. Obrigatório, entre 2 e 50 caracteres.
    nome = StringField('Nome da Categoria', validators=[
        DataRequired(message="O nome da categoria é obrigatório."),
        Length(min=2, max=50, message="Nome deve ter entre 2 e 50 caracteres.")
    ])
    # Botão de submissão.
    submit = SubmitField('Salvar Categoria')


# --- Formulário para Adicionar/Editar Cartão de Crédito ---
class CartaoForm(FlaskForm):
    # Campo para o nome do cartão. Obrigatório, máximo 50 caracteres.
    nome = StringField('Nome do Cartão',
                       validators=[DataRequired(message="O nome do cartão é obrigatório."), Length(max=50)])
    # Campo para o limite total. Usa StringField para a máscara e o validador decimal customizado. Obrigatório.
    limite = StringField('Limite Total',
                         validators=[DataRequired(message="O limite é obrigatório."), decimal_field_validator])
    # Botão de submissão.
    submit = SubmitField('Salvar Cartão')


# --- Formulário para Adicionar/Editar Conta Bancária ---
class ContaBancariaForm(FlaskForm):
    # Campo para o nome da conta. Obrigatório, máximo 50 caracteres.
    nome = StringField('Nome da Conta',
                       validators=[DataRequired(message="O nome da conta é obrigatório."), Length(max=50)])
    # Campo para o saldo atual. Usa StringField para a máscara e o validador decimal customizado. Obrigatório.
    saldo = StringField('Saldo Atual',
                        validators=[DataRequired(message="O saldo é obrigatório."), decimal_field_validator])
    # Botão de submissão.
    submit = SubmitField('Salvar Conta')


# --- Formulários de Autenticação ---
# (Mantidos como estavam, assumindo que funcionam bem)

class LoginForm(FlaskForm):
    # Campo username. Obrigatório.
    username = StringField('Usuário', validators=[DataRequired(message="Nome de usuário é obrigatório.")])
    # Campo password. Obrigatório.
    password = PasswordField('Senha', validators=[DataRequired(message="Senha é obrigatória.")])
    # Botão de submissão.
    submit = SubmitField('Entrar')


class RegisterForm(FlaskForm):
    # Campo username. Obrigatório, entre 4 e 20 caracteres.
    username = StringField('Usuário', validators=[
        DataRequired(message="Nome de usuário é obrigatório."),
        Length(min=4, max=20, message="Usuário deve ter entre 4 e 20 caracteres.")
    ])
    # Campo password. Obrigatório, mínimo 6 caracteres.
    password = PasswordField('Senha', validators=[
        DataRequired(message="Senha é obrigatória."),
        Length(min=6, message="Senha deve ter no mínimo 6 caracteres.")
    ])
    # Campo para confirmar a senha. Obrigatório e deve ser igual ao campo 'password'.
    confirm_password = PasswordField('Confirme a Senha', validators=[
        DataRequired(message="Confirmação de senha é obrigatória."),
        EqualTo('password', message='As senhas não conferem.')
    ])
    # Botão de submissão.
    submit = SubmitField('Registrar')


class ResetPasswordForm(FlaskForm):
    # Campo username. Obrigatório. (Embora possa ser preenchido automaticamente na view).
    username = StringField('Usuário', validators=[DataRequired(message="Nome de usuário é obrigatório.")])
    # Campo para a nova senha. Obrigatório, mínimo 6 caracteres.
    new_password = PasswordField('Nova Senha', validators=[
        DataRequired(message="Nova senha é obrigatória."),
        Length(min=6, message="Nova senha deve ter no mínimo 6 caracteres.")
    ])
    # Campo para confirmar a nova senha. Obrigatório e deve ser igual a 'new_password'.
    confirm_password = PasswordField('Confirme a Nova Senha', validators=[
        DataRequired(message="Confirmação da nova senha é obrigatória."),
        EqualTo('new_password', message='As senhas não conferem.')
    ])
    # Botão de submissão.
    submit = SubmitField('Redefinir Senha')
