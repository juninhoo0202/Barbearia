from django.db import migrations, models
from django.utils.crypto import get_random_string


ALLOWED_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def gerar_codigo_unico(model):
    while True:
        codigo = get_random_string(8, allowed_chars=ALLOWED_CHARS)
        if not model.objects.filter(codigo_cancelamento=codigo).exists():
            return codigo


def preencher_codigos_cancelamento(apps, schema_editor):
    Agendamento = apps.get_model("barbearia", "Agendamento")
    for agendamento in Agendamento.objects.filter(codigo_cancelamento__isnull=True).order_by("id"):
        Agendamento.objects.filter(pk=agendamento.pk).update(
            codigo_cancelamento=gerar_codigo_unico(Agendamento)
        )


class Migration(migrations.Migration):

    dependencies = [
        ("barbearia", "0003_alter_agendamento_options_alter_agendamento_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="agendamento",
            name="codigo_cancelamento",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=8,
                null=True,
                unique=True,
                verbose_name="Código de cancelamento",
            ),
        ),
        migrations.RunPython(preencher_codigos_cancelamento, migrations.RunPython.noop),
    ]
