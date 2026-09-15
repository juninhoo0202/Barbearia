from datetime import time, timedelta

from django.core import mail
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Agendamento, BloqueioHorario, Cliente, Servico


User = get_user_model()


class BarbeariaViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="staff",
            password="senha12345",
            is_staff=True,
            is_superuser=True,
        )
        self.servico = Servico.objects.get_or_create(nome="Corte", defaults={"preco": "30.00"})[0]

    def proxima_data_util(self, dias_minimos=1):
        data = timezone.localdate() + timedelta(days=dias_minimos)
        while data.weekday() >= 5:
            data += timedelta(days=1)
        return data

    def test_public_pages_and_aliases_render(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        self.assertEqual(self.client.get(reverse("agendar")).status_code, 200)
        self.assertEqual(self.client.get(reverse("horarios_agendados")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin_login")).status_code, 200)
        self.assertEqual(reverse("login"), "/login/")
        self.assertEqual(reverse("logout"), "/logout/")
        self.assertEqual(reverse("login_admin"), "/login-admin/")
        self.assertEqual(reverse("painel_admin"), "/painel-admin/")
        self.assertEqual(reverse("horarios_agendados"), "/horarios-agendados/")

    def test_admin_dashboard_renders_for_staff(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("admin_agendamentos"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Painel Administrativo")
        self.assertContains(response, "totalAgendamentos")

        response = self.client.get(reverse("painel_admin"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Painel Administrativo")

    def test_admin_login_accepts_username(self):
        response = self.client.post(
            reverse("admin_login"),
            {
                "username": "staff",
                "password": "senha12345",
            },
        )
        self.assertRedirects(response, reverse("painel_admin"))

    def test_admin_login_accepts_email(self):
        User.objects.create_user(
            username="emailstaff",
            email="admin@barbearia.com",
            password="senha12345",
            is_staff=True,
            is_superuser=True,
        )

        response = self.client.post(
            reverse("admin_login"),
            {
                "username": "admin@barbearia.com",
                "password": "senha12345",
            },
        )
        self.assertRedirects(response, reverse("painel_admin"))

    def test_admin_login_shows_message_for_invalid_credentials(self):
        response = self.client.post(
            reverse("admin_login"),
            {
                "username": "staff",
                "password": "senhaerrada",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Usuário ou senha incorretos.")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_admin_password_reset_sends_code_email(self):
        self.staff_user.email = "admin@barbearia.com"
        self.staff_user.save(update_fields=["email"])

        response = self.client.post(
            reverse("esqueceu_senha"),
            {"email": "admin@barbearia.com"},
        )

        self.assertRedirects(response, reverse("confirmar_codigo"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@barbearia.com"])
        self.assertIn("Código de recuperação", mail.outbox[0].subject)

        codigo = self.client.session["recuperacao"]["codigo"]
        self.assertIn(codigo, mail.outbox[0].body)
        self.assertEqual(len(codigo), 6)

    def test_blocked_slot_is_hidden_and_rejected(self):
        future_date = self.proxima_data_util(2)
        BloqueioHorario.objects.update_or_create(
            data=future_date,
            hora=time(10, 0),
            defaults={"motivo": "Teste"},
        )

        response = self.client.get(reverse("horarios_livres_api"), {"data": future_date.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("10:00", response.json()["horarios"])

        before = Agendamento.objects.count()
        post_data = {
            "cliente": "Cliente Teste",
            "telefone": "(11) 99999-9999",
            "servico": str(self.servico.id),
            "data": future_date.isoformat(),
            "hora": "10:00",
            "observacoes": "Teste de bloqueio",
        }
        response = self.client.post(reverse("agendar"), post_data, follow=True)
        self.assertEqual(Agendamento.objects.count(), before)
        self.assertEqual(response.status_code, 200)

    def test_home_cliente_exibe_apenas_proprios_agendamentos(self):
        future_date = self.proxima_data_util(2)
        cliente_meu = Cliente.objects.create(nome="Cliente Meu", telefone="(11) 97777-6666")
        cliente_outro = Cliente.objects.create(nome="Cliente Outro", telefone="(11) 98888-1111")

        Agendamento.objects.create(
            cliente=cliente_meu,
            servico=self.servico,
            data=future_date,
            hora=time(11, 0),
            observacoes="Meu horário",
        )
        Agendamento.objects.create(
            cliente=cliente_outro,
            servico=self.servico,
            data=future_date,
            hora=time(12, 0),
            observacoes="Horário de outro cliente",
        )

        session = self.client.session
        session["telefone_cliente"] = cliente_meu.telefone
        session.save()

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Meus horários agendados")
        self.assertContains(response, cliente_meu.nome)
        self.assertNotContains(response, cliente_outro.nome)

    def test_horarios_agendados_pagina_lista_todos_horarios(self):
        future_date = self.proxima_data_util(2)
        cliente_1 = Cliente.objects.create(nome="Cliente Lista 1", telefone="(11) 93333-1111")
        cliente_2 = Cliente.objects.create(nome="Cliente Lista 2", telefone="(11) 94444-2222")

        Agendamento.objects.create(
            cliente=cliente_1,
            servico=self.servico,
            data=future_date,
            hora=time(10, 0),
            observacoes="",
        )
        Agendamento.objects.create(
            cliente=cliente_2,
            servico=self.servico,
            data=future_date,
            hora=time(13, 0),
            observacoes="",
        )

        response = self.client.get(reverse("horarios_agendados"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Horários já agendados")
        self.assertContains(response, "10:00")
        self.assertContains(response, "13:00")

    def test_ajax_agendamento_returns_json_success(self):
        future_date = self.proxima_data_util(2)
        before = Agendamento.objects.count()

        response = self.client.post(
            reverse("agendar"),
            {
                "cliente": "Cliente AJAX",
                "telefone": "(11) 98888-7777",
                "servico": str(self.servico.id),
                "data": future_date.isoformat(),
                "hora": "11:00",
                "observacoes": "Teste via AJAX",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("codigo_cancelamento", data)
        self.assertEqual(len(data["codigo_cancelamento"]), 8)
        self.assertIn("whatsapp_link", data)
        self.assertTrue(data["whatsapp_link"].startswith("https://wa.me/"))
        self.assertEqual(
            data["message"],
            f"Agendamento para {future_date.strftime('%d/%m/%Y')} às 11:00 confirmado! Seu código para cancelar é {data['codigo_cancelamento']}.",
        )
        self.assertEqual(Agendamento.objects.count(), before + 1)
        self.assertIn("ultimo_agendamento", self.client.session)
        self.assertEqual(self.client.session["ultimo_agendamento"]["codigo_cancelamento"], data["codigo_cancelamento"])

        home_response = self.client.get(reverse("home"))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, "Seu último código de cancelamento continua visível aqui")
        self.assertContains(home_response, data["codigo_cancelamento"])

    def test_limpar_ultimo_agendamento_remove_o_banner_da_home(self):
        future_date = self.proxima_data_util(2)

        self.client.post(
            reverse("agendar"),
            {
                "cliente": "Cliente Limpeza",
                "telefone": "(11) 95555-4444",
                "servico": str(self.servico.id),
                "data": future_date.isoformat(),
                "hora": "11:00",
                "observacoes": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertIn("ultimo_agendamento", self.client.session)

        response = self.client.post(reverse("limpar_ultimo_agendamento"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("ultimo_agendamento", self.client.session)
        self.assertNotContains(response, "Seu último código de cancelamento continua visível aqui")

    def test_limpar_ultimo_agendamento_ajax_retira_sessao(self):
        future_date = self.proxima_data_util(2)

        self.client.post(
            reverse("agendar"),
            {
                "cliente": "Cliente AJAX Limpeza",
                "telefone": "(11) 94444-3333",
                "servico": str(self.servico.id),
                "data": future_date.isoformat(),
                "hora": "11:00",
                "observacoes": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        response = self.client.post(
            reverse("limpar_ultimo_agendamento"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "message": "Aviso removido da tela."})
        self.assertNotIn("ultimo_agendamento", self.client.session)

    def test_cancelamento_exige_codigo_e_csrf(self):
        future_date = self.proxima_data_util(3)
        cliente = Cliente.objects.create(nome="Cliente Cancelamento", telefone="(11) 97777-6666")
        agendamento = Agendamento.objects.create(
            cliente=cliente,
            servico=self.servico,
            data=future_date,
            hora=time(12, 0),
            observacoes="Teste de cancelamento",
        )

        secure_client = Client(enforce_csrf_checks=True)
        secure_client.get(reverse("agendar"))
        csrf_token = secure_client.cookies["csrftoken"].value

        base_headers = {
            "HTTP_X_REQUESTED_WITH": "XMLHttpRequest",
            "HTTP_ACCEPT": "application/json",
            "HTTP_X_CSRFTOKEN": csrf_token,
        }

        response = secure_client.post(
            reverse("cancelar_agendamento", args=[agendamento.id]),
            {"telefone": cliente.telefone},
            **base_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        agendamento.refresh_from_db()
        self.assertEqual(agendamento.status, "agendado")

        response = secure_client.post(
            reverse("cancelar_agendamento", args=[agendamento.id]),
            {
                "telefone": cliente.telefone,
                "codigo_cancelamento": agendamento.codigo_cancelamento,
            },
            **base_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content.decode("utf-8"), {"ok": True, "message": "Agendamento cancelado com sucesso!"})
        agendamento.refresh_from_db()
        self.assertEqual(agendamento.status, "cancelado")

    def test_cancelamento_rejeita_codigo_de_outro_agendamento(self):
        future_date = self.proxima_data_util(3)
        cliente = Cliente.objects.create(nome="Cliente Cancelamento", telefone="(11) 97777-6666")
        agendamento_alvo = Agendamento.objects.create(
            cliente=cliente,
            servico=self.servico,
            data=future_date,
            hora=time(12, 0),
            observacoes="Agendamento alvo",
        )
        agendamento_outro = Agendamento.objects.create(
            cliente=cliente,
            servico=self.servico,
            data=self.proxima_data_util(4),
            hora=time(13, 0),
            observacoes="Outro agendamento",
        )

        secure_client = Client(enforce_csrf_checks=True)
        secure_client.get(reverse("agendar"))
        csrf_token = secure_client.cookies["csrftoken"].value

        base_headers = {
            "HTTP_X_REQUESTED_WITH": "XMLHttpRequest",
            "HTTP_ACCEPT": "application/json",
            "HTTP_X_CSRFTOKEN": csrf_token,
        }

        response = secure_client.post(
            reverse("cancelar_agendamento", args=[agendamento_alvo.id]),
            {
                "telefone": cliente.telefone,
                "codigo_cancelamento": agendamento_outro.codigo_cancelamento,
            },
            **base_headers,
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(
            response.json()["message"],
            "Código de cancelamento não corresponde a este agendamento.",
        )
        agendamento_alvo.refresh_from_db()
        self.assertEqual(agendamento_alvo.status, "agendado")

    def test_exclusao_admin_exige_csrf_e_remove_agendamento(self):
        future_date = self.proxima_data_util(4)
        cliente = Cliente.objects.create(nome="Cliente Admin", telefone="(11) 96666-5555")
        agendamento = Agendamento.objects.create(
            cliente=cliente,
            servico=self.servico,
            data=future_date,
            hora=time(13, 0),
            observacoes="Teste de exclusão do admin",
        )

        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.staff_user)
        secure_client.get(reverse("home"))
        csrf_token = secure_client.cookies["csrftoken"].value

        response = secure_client.post(
            reverse("excluir_agendamento", args=[agendamento.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(Agendamento.objects.filter(pk=agendamento.id).exists())
