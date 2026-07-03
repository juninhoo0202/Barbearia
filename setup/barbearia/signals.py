from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Servico

@receiver(post_migrate)
def criar_servicos_padrao(sender, **kwargs):
    if sender.name == "barbearia":  # nome do app
        servicos = [
            ("Corte", 30.00),
            ("Barba", 20.00),
            ("Corte + Barba", 45.00),
            ("Sobrancelha", 15.00),
        ]
        for nome, preco in servicos:
            Servico.objects.get_or_create(nome=nome, defaults={"preco": preco})
