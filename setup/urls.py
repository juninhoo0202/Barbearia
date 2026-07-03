from django.contrib import admin
from django.urls import path
from barbearia import views

urlpatterns = [
    # Admin Django
    path("admin/", admin.site.urls),

    # Login personalizado (ADM)
    path("admin-login/", views.admin_login, name="admin_login"),
    path("login/", views.admin_login, name="login"),
    path("login-admin/", views.admin_login, name="login_admin"),
    path("painel-admin/", views.painel_admin, name="painel_admin"),
    path("logout/", views.custom_logout, name="logout"),
    path("sair/", views.sair, name="sair"),
    path("logout-custom/", views.custom_logout, name="custom_logout"),

    # Páginas principais
    path("", views.home, name="home"),
    path("agendar/", views.agendar, name="agendar"),
    path("limpar-ultimo-agendamento/", views.limpar_ultimo_agendamento, name="limpar_ultimo_agendamento"),

    # Admin de agendamentos
    path("admin-agendamentos/", views.admin_agendamentos, name="admin_agendamentos"),

    # APIs/Ações AJAX
    path("agendamentos/", views.listar_agendamentos, name="listar_agendamentos"),
    path("cancelar/<int:id>/", views.cancelar_agendamento, name="cancelar_agendamento"),
    path("horarios-livres-api/", views.horarios_livres_api, name="horarios_livres_api"),

    # Exclusão de agendamentos
    path("excluir/<int:id>/", views.excluir_agendamento, name="excluir_agendamento"),
    path("excluir-todos/", views.excluir_todos_agendamentos, name="excluir_todos_agendamentos"),

    # Dados dos gráficos
    path("dados-graficos/", views.dados_graficos, name="dados_graficos"),
    path("novos-agendamentos/", views.novos_agendamentos, name="novos_agendamentos"),

    # 🔑 Recuperação de senha customizada
    path("esqueceu-senha/", views.esqueceu_senha, name="esqueceu_senha"),
    path("confirmar-codigo/", views.confirmar_codigo, name="confirmar_codigo"),
    path("nova-senha/", views.nova_senha, name="nova_senha"),
]
