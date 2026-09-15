from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string


def gerar_codigo_cancelamento():
    return get_random_string(8, allowed_chars="ABCDEFGHJKLMNPQRSTUVWXYZ23456789")


class Servico(models.Model):
    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        return f"{self.nome} - R$ {self.preco}"


class BloqueioHorario(models.Model):
    data = models.DateField(verbose_name="Data do bloqueio")
    hora = models.TimeField(verbose_name="Horário bloqueado")
    motivo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Motivo")

    class Meta:
        verbose_name = "Bloqueio de Horário"
        verbose_name_plural = "Bloqueios de Horários"
        ordering = ["data", "hora"]
        unique_together = ("data", "hora")

    def __str__(self):
        return f"{self.data.strftime('%d/%m/%Y')} - {self.hora.strftime('%H:%M')}"


class Cliente(models.Model):
    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome


class Agendamento(models.Model):
    STATUS_CHOICES = [
        ("agendado", "Agendado"),
        ("cancelado", "Cancelado"),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE)
    data = models.DateField()
    hora = models.TimeField()
    observacoes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="agendado")
    codigo_cancelamento = models.CharField(
        max_length=8,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        verbose_name="Código de cancelamento",
    )
    lembrete_whatsapp_enviado = models.BooleanField(default=False)
    lembrete_whatsapp_enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["data", "hora"]

    def __str__(self):
        return (
            f"{self.cliente.nome} - {self.servico.nome} em "
            f"{self.data.strftime('%d/%m/%Y')} as {self.hora.strftime('%H:%M')}"
        )

    def save(self, *args, **kwargs):
        if self.status != "agendado":
            self.lembrete_whatsapp_enviado = False
            self.lembrete_whatsapp_enviado_em = None

        if not self.codigo_cancelamento:
            codigo = gerar_codigo_cancelamento()
            qs = Agendamento.objects.filter(codigo_cancelamento=codigo)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.exists():
                codigo = gerar_codigo_cancelamento()
                qs = Agendamento.objects.filter(codigo_cancelamento=codigo)
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
            self.codigo_cancelamento = codigo
        super().save(*args, **kwargs)

    def marcar_lembrete_enviado(self):
        self.lembrete_whatsapp_enviado = True
        self.lembrete_whatsapp_enviado_em = timezone.now()
        self.save(update_fields=["lembrete_whatsapp_enviado", "lembrete_whatsapp_enviado_em"])
