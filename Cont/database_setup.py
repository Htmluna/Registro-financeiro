# arquivo database_setup.py
from app import app, get_db_connection
from database import add_recorrente_column, add_tipo_pagamento_id_column, check_and_add_columns

with app.app_context():
    #add_recorrente_column()
    #add_tipo_pagamento_id_column()
    pass
