from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from django.utils.timezone import localtime, now

from barbearia.models import Agendamento
from barbearia.views import gerar_link_whatsapp


def limpar_agendamentos():
    agora = localtime(now())
    hoje = agora.date()
    if agora.hour >= 20:
        Agendamento.objects.filter(data=hoje).delete()
        print(f"[Scheduler] Agendamentos de {hoje} apagados às {agora.strftime('%H:%M')}.")


def enviar_lembretes_whatsapp():
    agora = localtime(now())
    inicio_janela = agora + timedelta(minutes=59)
    fim_janela = agora + timedelta(minutes=61)

    agendamentos = (
        Agendamento.objects.filter(
            status="agendado",
            lembrete_whatsapp_enviado=False,
            data=agora.date(),
        )
        .select_related("cliente", "servico")
        .order_by("hora")
    )

    for agendamento in agendamentos:
        agendamento_dt = datetime.combine(agendamento.data, agendamento.hora, tzinfo=agora.tzinfo)
        if not (inicio_janela <= agendamento_dt <= fim_janela):
            continue

        mensagem = (
            f"Olá, {agendamento.cliente.nome}! Lembrete da Barbearia Estilo: "
            f"seu horário é hoje às {agendamento.hora.strftime('%H:%M')} "
            f"para {agendamento.servico.nome}."
        )
        link = gerar_link_whatsapp(agendamento.cliente.telefone, mensagem)

        # Integração atual: registra o lembrete no log e marca como enviado.
        # Se quiser envio real automático, conectamos uma API de WhatsApp em seguida.
        print(f"[Lembrete WhatsApp] Agendamento #{agendamento.id} | Link: {link}")
        agendamento.marcar_lembrete_enviado()


scheduler = BackgroundScheduler()
scheduler.add_job(limpar_agendamentos, "cron", hour=20, minute=0)
scheduler.add_job(enviar_lembretes_whatsapp, "cron", minute="*")
