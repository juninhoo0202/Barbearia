from django.contrib import admin

from .models import Agendamento, BloqueioHorario, Cliente, Servico


@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ("nome", "preco")
    search_fields = ("nome",)
    ordering = ("nome",)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nome", "telefone", "data_cadastro")
    search_fields = ("nome", "telefone")
    list_filter = ("data_cadastro",)
    ordering = ("-data_cadastro",)


@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "servico", "data", "hora", "status")
    search_fields = ("cliente__nome", "cliente__telefone", "servico__nome")
    list_filter = ("status", "data", "servico")
    ordering = ("data", "hora")


@admin.register(BloqueioHorario)
class BloqueioHorarioAdmin(admin.ModelAdmin):
    list_display = ("data", "hora", "motivo")
    search_fields = ("motivo",)
    list_filter = ("data",)
    ordering = ("data", "hora")
