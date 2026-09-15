from datetime import datetime, time, timedelta, timezone as dt_timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils.timezone import now, localtime
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from urllib.parse import quote

from .models import Cliente, Servico, Agendamento, BloqueioHorario

User = get_user_model()

BARBEARIA_CONTATO = {
    "nome": "Barbearia Estilo",
    "endereco": "Rua Própria, 123 - Centro",
    "cidade": "Japoatã - SE",
    "maps_url": "https://www.google.com/maps/search/?api=1&query=Rua+Pr%C3%B3pria,+123+-+Centro,+Japoat%C3%A3+-+SE",
    "maps_embed_url": "https://maps.google.com/maps?q=Rua%20Pr%C3%B3pria%2C%20123%20-%20Centro%2C%20Japoat%C3%A3%20-%20SE&output=embed",
    "whatsapp_url": "https://wa.me/5599999999999",
    "instagram_url": "https://www.instagram.com/edivaldojunior.09/",
    "facebook_url": "https://facebook.com/sua_barbearia",
}

SERVICOS_DESTAQUE = [
    {"nome": "Corte Masculino", "preco": "30,00"},
    {"nome": "Barba Completa", "preco": "40,00"},
    {"nome": "Combo Corte + Barba", "preco": "65,00"},
]


# =====================================
# Helpers
# =====================================
def get_horario_funcionamento(dia_semana):
    if 0 <= dia_semana <= 4:   # Segunda a Sexta
        return time(8, 0), time(19, 0)
    elif dia_semana == 5:      # SÃ¡bado
        return time(8, 0), time(18, 0)
    return None, None          # Domingo fechado


def q_agendamentos_futuros():
    agora = localtime(now())
    hoje = agora.date()
    hora_atual = agora.time()
    return Q(data__gt=hoje) | Q(data=hoje, hora__gte=hora_atual)


def contar_agendamentos_hoje_visiveis(agora=None):
    agora = agora or localtime(now())
    if agora.hour >= 20:
        return 0
    return Agendamento.objects.filter(
        data=agora.date(),
        hora__gte=agora.time(),
        status="agendado",
    ).count()


def normalizar_telefone(valor):
    return "".join(ch for ch in (valor or "") if ch.isdigit())


def normalizar_codigo_cancelamento(valor):
    return "".join((valor or "").split()).upper()


def _limpar_recuperacao_senha(request):
    for chave in ("recuperacao", "recuperacao_tentativas", "recuperacao_validada"):
        request.session.pop(chave, None)


def _limpar_ultimo_agendamento(request):
    request.session.pop("ultimo_agendamento", None)


def _mascarar_email(email):
    email = (email or "").strip()
    if "@" not in email:
        return email

    local, dominio = email.split("@", 1)
    if len(local) <= 2:
        local_mask = f"{local[:1]}*"
    else:
        local_mask = f"{local[:2]}***"
    return f"{local_mask}@{dominio}"


def _buscar_usuario_admin_email(email):
    email = (email or "").strip()
    if not email:
        return None
    return User.objects.filter(email__iexact=email, is_staff=True).first()


def _admin_sem_email_cadastrado():
    return User.objects.filter(is_staff=True).filter(Q(email__isnull=True) | Q(email="")).first()


def _enviar_codigo_recuperacao(email, codigo):
    assunto = "CÃ³digo de recuperaÃ§Ã£o - Barbearia Estilo"
    mensagem = (
        "OlÃ¡!\n\n"
        f"Seu cÃ³digo de recuperaÃ§Ã£o Ã©: {codigo}\n\n"
        "Use esse cÃ³digo para redefinir sua senha. Ele expira em 10 minutos."
    )
    html_message = (
        "<div style=\"font-family:Arial,sans-serif;line-height:1.6;color:#1f2937\">"
        "<h2 style=\"margin:0 0 12px;color:#198754\">Barbearia Estilo</h2>"
        "<p>Recebemos uma solicitaÃ§Ã£o para redefinir a senha do administrador.</p>"
        f"<p style=\"font-size:28px;font-weight:700;letter-spacing:4px;margin:20px 0;color:#0f5132\">{codigo}</p>"
        "<p>Use esse cÃ³digo no site. Ele expira em 10 minutos.</p>"
        "</div>"
    )
    remetente = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None) or None
    send_mail(assunto, mensagem, remetente, [email], html_message=html_message, fail_silently=False)


NOMES_DIAS_SEMANA = [
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
]


def nome_dia_semana(data_obj):
    return NOMES_DIAS_SEMANA[data_obj.weekday()]


def rotulo_data(data_obj):
    hoje = localtime(now()).date()
    if data_obj == hoje:
        return "Hoje", "bg-success"
    if data_obj == hoje + timedelta(days=1):
        return "Amanhã", "bg-secondary"
    return f"Dia {data_obj.day}", "bg-secondary"


def formatar_preco_br(valor):
    return f"R$ {str(valor).replace('.', ',')}"


def _resumo_operacional(agora=None):
    agora = agora or localtime(now())
    hora_inicio, hora_fim = get_horario_funcionamento(agora.weekday())

    if not hora_inicio or not hora_fim:
        return {
            "label": "Fechado",
            "variant": "danger",
            "icone": "x-circle-fill",
            "texto": "Domingo fechado",
            "detalhe": "Retornamos na segunda-feira às 08h.",
        }

    aberto = hora_inicio <= agora.time() <= hora_fim
    return {
        "label": "Aberto agora" if aberto else "Fechado",
        "variant": "success" if aberto else "danger",
        "icone": "check-circle-fill" if aberto else "x-circle-fill",
        "texto": f"{nome_dia_semana(agora.date())}: {hora_inicio.strftime('%Hh')} - {hora_fim.strftime('%Hh')}",
        "detalhe": "Estamos atendendo neste momento." if aberto else "Fora do horário atual de atendimento.",
    }


def obter_proximo_horario_disponivel(dias_limite=14):
    hoje = localtime(now()).date()
    for offset in range(dias_limite + 1):
        data = hoje + timedelta(days=offset)
        horarios = get_horarios_disponiveis(data)
        if horarios:
            rotulo = "Hoje" if offset == 0 else "Amanhã" if offset == 1 else nome_dia_semana(data)
            return {
                "data": data,
                "data_formatada": data.strftime("%d/%m/%Y"),
                "hora": horarios[0],
                "rotulo": rotulo,
                "texto": f"{rotulo} às {horarios[0]}",
            }
    return None


def gerar_link_whatsapp(telefone, mensagem):
    telefone_numeros = normalizar_telefone(telefone)
    if not telefone_numeros:
        return ""

    if telefone_numeros.startswith("55") and len(telefone_numeros) > 11:
        numero = telefone_numeros
    else:
        numero = f"55{telefone_numeros}"

    return f"https://wa.me/{numero}?text={quote(mensagem)}"


def get_horarios_disponiveis(data_selecionada):
    hora_inicio, hora_fim = get_horario_funcionamento(data_selecionada.weekday())
    if not hora_inicio or not hora_fim:
        return []

    horarios_validos = [f"{h:02d}:00" for h in range(hora_inicio.hour, hora_fim.hour + 1)]

    agendamentos_ocupados = {
        hora.strftime("%H:%M")
        for hora in Agendamento.objects.filter(data=data_selecionada, status="agendado").values_list("hora", flat=True)
    }
    bloqueios_ocupados = {
        hora.strftime("%H:%M")
        for hora in BloqueioHorario.objects.filter(data=data_selecionada).values_list("hora", flat=True)
    }
    ocupados = agendamentos_ocupados | bloqueios_ocupados

    agora = localtime(now())
    hoje = agora.date()
    hora_atual = agora.time()

    if data_selecionada == hoje:
        horarios_validos = [
            h for h in horarios_validos if time(int(h.split(":")[0]), int(h.split(":")[1])) > hora_atual
        ]

    return [h for h in horarios_validos if h not in ocupados]


def get_admin_dashboard_context():
    agendamentos = Agendamento.objects.filter(q_agendamentos_futuros(), status="agendado").order_by("data", "hora")
    return {
        "agendamentos": agendamentos,
        "total_agendamentos": agendamentos.count(),
        "total_clientes": Cliente.objects.count(),
    }


def _obter_ultimo_agendamento_salvo(request):
    dados = request.session.get("ultimo_agendamento")
    if not dados:
        return None

    agendamento_id = dados.get("id")
    if not agendamento_id:
        _limpar_ultimo_agendamento(request)
        return None

    try:
        agendamento = (
            Agendamento.objects.select_related("cliente", "servico")
            .get(id=agendamento_id)
        )
    except Agendamento.DoesNotExist:
        _limpar_ultimo_agendamento(request)
        return None

    if agendamento.status != "agendado":
        _limpar_ultimo_agendamento(request)
        return None

    mensagem_whatsapp = (
        f"OlÃ¡, {agendamento.cliente.nome}! Seu agendamento na Barbearia Estilo foi confirmado para "
        f"{agendamento.data.strftime('%d/%m/%Y')} Ã s {agendamento.hora.strftime('%H:%M')}. "
        f"CÃ³digo para cancelar: {agendamento.codigo_cancelamento}."
    )

    return {
        "id": agendamento.id,
        "cliente": agendamento.cliente.nome,
        "telefone": agendamento.cliente.telefone,
        "servico": agendamento.servico.nome,
        "data": agendamento.data.strftime("%d/%m/%Y"),
        "hora": agendamento.hora.strftime("%H:%M"),
        "codigo_cancelamento": agendamento.codigo_cancelamento,
        "whatsapp_link": dados.get("whatsapp_link") or gerar_link_whatsapp(agendamento.cliente.telefone, mensagem_whatsapp),
    }


def agendamento_response(request, ok, message, *, status=200, redirect_name="agendar", extra=None):
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get(
        "accept", ""
    )
    if is_ajax:
        payload = {"ok": ok, "message": message}
        if extra:
            payload.update(extra)
        return JsonResponse(payload, status=status)

    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect(redirect_name)


# =====================================
# Home
# =====================================
@ensure_csrf_cookie
def home(request):
    telefone_cliente = normalizar_telefone(request.session.get("telefone_cliente"))
    is_staff = request.user.is_authenticated and request.user.is_staff
    agora = localtime(now())
    horario_operacional = _resumo_operacional(agora)
    ultimo_agendamento = _obter_ultimo_agendamento_salvo(request)

    agendamentos = list(
        Agendamento.objects.filter(q_agendamentos_futuros(), status="agendado")
        .select_related("cliente", "servico")
        .order_by("data", "hora")
    )

    if not is_staff:
        if telefone_cliente:
            agendamentos = [
                agendamento
                for agendamento in agendamentos
                if normalizar_telefone(agendamento.cliente.telefone) == telefone_cliente
            ]
        else:
            agendamentos = []

    agendamentos_hoje_count = contar_agendamentos_hoje_visiveis(agora)
    for agendamento in agendamentos:
        agendamento.dia_semana = nome_dia_semana(agendamento.data)
        agendamento.rotulo_destaque, agendamento.rotulo_classe = rotulo_data(agendamento.data)
        agendamento.meu_agendamento = (not is_staff) and bool(
            telefone_cliente and normalizar_telefone(agendamento.cliente.telefone) == telefone_cliente
        )

    servicos = Servico.objects.all().order_by("id")
    return render(
        request,
        "barbearia/index.html",
        {
            "agendamentos": agendamentos,
            "agendamentos_hoje_count": agendamentos_hoje_count,
            "servicos": servicos,
            "servicos_destaque": SERVICOS_DESTAQUE,
            "ultimo_agendamento": ultimo_agendamento,
            "barbearia": BARBEARIA_CONTATO,
            "horario_operacional": horario_operacional,
            "proximo_horario_livre": obter_proximo_horario_disponivel(),
        },
    )


@ensure_csrf_cookie
def horarios_agendados(request):
    telefone_cliente = normalizar_telefone(request.session.get("telefone_cliente"))
    agendamentos = list(
        Agendamento.objects.filter(q_agendamentos_futuros(), status="agendado")
        .select_related("cliente", "servico")
        .order_by("data", "hora")
    )

    for agendamento in agendamentos:
        agendamento.dia_semana = nome_dia_semana(agendamento.data)
        agendamento.rotulo_destaque, agendamento.rotulo_classe = rotulo_data(agendamento.data)
        agendamento.eh_meu = bool(
            telefone_cliente and normalizar_telefone(agendamento.cliente.telefone) == telefone_cliente
        )

    return render(
        request,
        "barbearia/horarios_agendados.html",
        {
            "agendamentos": agendamentos,
            "barbearia": BARBEARIA_CONTATO,
            "proximo_horario_livre": obter_proximo_horario_disponivel(),
        },
    )


# =====================================
# Agendamento
# =====================================
def agendar(request):
    servicos = Servico.objects.all().order_by("id")
    proximo_horario_livre = obter_proximo_horario_disponivel()

    data_get = request.GET.get("data")
    if data_get:
        try:
            data_selecionada = datetime.strptime(data_get, "%Y-%m-%d").date()
        except ValueError:
            data_selecionada = localtime(now()).date()
    else:
        data_selecionada = localtime(now()).date()

    horarios_livres = get_horarios_disponiveis(data_selecionada)
    if not data_get and not horarios_livres and proximo_horario_livre:
        data_selecionada = proximo_horario_livre["data"]
        horarios_livres = get_horarios_disponiveis(data_selecionada)

    if request.method == "POST":
        nome_cliente = (request.POST.get("cliente") or "").strip()
        telefone = (request.POST.get("telefone") or "").strip()
        servico_id = request.POST.get("servico")
        data_str = request.POST.get("data")
        hora_str = (request.POST.get("hora") or "").strip()
        observacoes = request.POST.get("observacoes", "").strip()

        if not (nome_cliente and telefone and servico_id and data_str and hora_str):
            return agendamento_response(
                request,
                False,
                "Todos os campos sÃ£o obrigatÃ³rios.",
                status=400,
                redirect_name="agendar",
            )

        try:
            data_obj = datetime.strptime(data_str, "%Y-%m-%d").date()
        except ValueError:
            return agendamento_response(request, False, "Data invÃ¡lida.", status=400, redirect_name="agendar")

        try:
            servico = Servico.objects.get(id=servico_id)
        except Servico.DoesNotExist:
            return agendamento_response(request, False, "ServiÃ§o invÃ¡lido.", status=400, redirect_name="agendar")

        try:
            h, m = map(int, hora_str.split(":"))
            hora = time(h, m)
        except Exception:
            return agendamento_response(request, False, "HorÃ¡rio invÃ¡lido.", status=400, redirect_name="agendar")

        if hora_str not in get_horarios_disponiveis(data_obj):
            return agendamento_response(
                request,
                False,
                "Esse horário está indisponível ou bloqueado.",
                status=400,
                redirect_name="agendar",
            )

        telefone_normalizado = normalizar_telefone(telefone)
        duplicado_mesmo_horario = any(
            normalizar_telefone(ag.cliente.telefone) == telefone_normalizado
            for ag in Agendamento.objects.filter(
                data=data_obj,
                hora=hora,
                status="agendado",
            ).select_related("cliente")
        )
        if duplicado_mesmo_horario:
            return agendamento_response(
                request,
                False,
                "Este telefone já possui agendamento nesse mesmo horário.",
                status=409,
                redirect_name="agendar",
            )

        cliente, _ = Cliente.objects.get_or_create(nome=nome_cliente, telefone=telefone)

        agendamento = Agendamento.objects.create(
            cliente=cliente,
            servico=servico,
            data=data_obj,
            hora=hora,
            observacoes=observacoes,
            status="agendado",
        )
        mensagem = (
            f"Agendamento para {data_obj.strftime('%d/%m/%Y')} às {hora_str} confirmado! "
            f"Seu código para cancelar é {agendamento.codigo_cancelamento}."
        )
        whatsapp_mensagem = (
            f"Olá, {nome_cliente}! Seu agendamento na Barbearia Estilo foi confirmado para "
            f"{data_obj.strftime('%d/%m/%Y')} às {hora_str}. "
            f"Código para cancelar: {agendamento.codigo_cancelamento}."
        )
        request.session["telefone_cliente"] = telefone
        request.session["ultimo_agendamento"] = {
            "id": agendamento.id,
            "cliente": nome_cliente,
            "telefone": telefone,
            "servico": servico.nome,
            "data": data_obj.isoformat(),
            "hora": hora_str,
            "codigo_cancelamento": agendamento.codigo_cancelamento,
            "whatsapp_link": gerar_link_whatsapp(telefone, whatsapp_mensagem),
        }
        return agendamento_response(
            request,
            True,
            mensagem,
            redirect_name="home",
            extra={
                "codigo_cancelamento": agendamento.codigo_cancelamento,
                "whatsapp_link": gerar_link_whatsapp(telefone, whatsapp_mensagem),
                "cliente": nome_cliente,
                "servico_nome": servico.nome,
                "servico_preco": formatar_preco_br(servico.preco),
                "data_formatada": data_obj.strftime("%d/%m/%Y"),
                "hora_formatada": hora_str,
            },
        )

    return render(
        request,
        "barbearia/agendar.html",
        {
            "servicos": servicos,
            "horarios": horarios_livres,
            "data_selecionada": data_selecionada,
            "proximo_horario_livre": proximo_horario_livre,
        },
    )


def limpar_ultimo_agendamento(request):
    if request.method != "POST":
        return redirect("home")

    _limpar_ultimo_agendamento(request)
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get(
        "accept", ""
    )
    if is_ajax:
        return JsonResponse({"ok": True, "message": "Aviso removido da tela."})

    messages.success(request, "CÃ³digo removido da tela.")
    return redirect("home")


# =====================================
# API horÃ¡rios livres
# =====================================
def horarios_livres_api(request):
    data = request.GET.get('data')
    if not data:
        return JsonResponse({'horarios': []})

    try:
        data_obj = datetime.strptime(data, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'horarios': []})

    return JsonResponse({'horarios': get_horarios_disponiveis(data_obj)})


# =====================================
# Listar agendamentos
# =====================================
def listar_agendamentos(request):
    telefone_cliente = normalizar_telefone(request.session.get("telefone_cliente"))
    is_staff = request.user.is_authenticated and request.user.is_staff
    agora = localtime(now())
    hoje = agora.date()
    hora_atual = agora.time()
    agendamentos = list(
        Agendamento.objects.filter(Q(data__gt=hoje) | Q(data=hoje, hora__gte=hora_atual), status="agendado")
        .select_related("cliente", "servico")
        .order_by("data", "hora")
    )

    if not is_staff:
        if telefone_cliente:
            agendamentos = [
                ag for ag in agendamentos if normalizar_telefone(ag.cliente.telefone) == telefone_cliente
            ]
        else:
            agendamentos = []

    data = []
    for ag in agendamentos:
        rotulo_destaque, rotulo_classe = rotulo_data(ag.data)
        data.append({
            "id": ag.id,
            "cliente": ag.cliente.nome,
            "data": ag.data.strftime("%d/%m/%Y"),
            "data_iso": ag.data.isoformat(),
            "hora": ag.hora.strftime("%H:%M"),
            "dia_semana": nome_dia_semana(ag.data),
            "rotulo_destaque": rotulo_destaque,
            "rotulo_classe": rotulo_classe,
            "eh_hoje": ag.data == hoje,
            "is_staff": is_staff,
            "meu_agendamento": bool(
                (not is_staff)
                and telefone_cliente
                and normalizar_telefone(ag.cliente.telefone) == telefone_cliente
            ),
        })
    return JsonResponse(data, safe=False)


# =====================================
# Cancelar agendamento
# =====================================
def cancelar_agendamento(request, id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "MÃ©todo nÃ£o permitido."}, status=405)

    agendamento = get_object_or_404(Agendamento, id=id)
    if agendamento.status != "agendado":
        return agendamento_response(
            request,
            False,
            "Esse agendamento jÃ¡ foi cancelado.",
            status=409,
            redirect_name="home",
        )

    if request.user.is_authenticated and request.user.is_staff:
        agendamento.status = "cancelado"
        agendamento.save(update_fields=["status"])
        return agendamento_response(
            request,
            True,
            "Agendamento cancelado pelo administrador.",
            redirect_name="home",
        )

    telefone_digitado = normalizar_telefone(request.POST.get("telefone"))
    codigo_digitado = normalizar_codigo_cancelamento(request.POST.get("codigo_cancelamento") or request.POST.get("codigo"))
    telefone_cadastrado = normalizar_telefone(agendamento.cliente.telefone)
    codigo_cadastrado = normalizar_codigo_cancelamento(agendamento.codigo_cancelamento)
    telefone_sessao = normalizar_telefone(request.session.get("telefone_cliente"))
    meu_agendamento = bool(telefone_sessao and telefone_sessao == telefone_cadastrado)

    if meu_agendamento:
        if not codigo_digitado:
            return agendamento_response(
                request,
                False,
                "Informe o cÃ³digo de cancelamento.",
                status=400,
                redirect_name="home",
            )
        if codigo_digitado != codigo_cadastrado:
            return agendamento_response(
                request,
                False,
                "CÃ³digo de cancelamento nÃ£o corresponde a este agendamento.",
                status=403,
                redirect_name="home",
            )
    else:
        if not telefone_digitado or not codigo_digitado:
            return agendamento_response(
                request,
                False,
                "Informe telefone e cÃ³digo de cancelamento.",
                status=400,
                redirect_name="home",
            )

        if telefone_digitado != telefone_cadastrado or codigo_digitado != codigo_cadastrado:
            if telefone_digitado != telefone_cadastrado and codigo_digitado != codigo_cadastrado:
                message = "Telefone e cÃ³digo de cancelamento nÃ£o correspondem a este agendamento."
            elif telefone_digitado != telefone_cadastrado:
                message = "Telefone informado nÃ£o corresponde a este agendamento."
            else:
                message = "CÃ³digo de cancelamento nÃ£o corresponde a este agendamento."
            return agendamento_response(
                request,
                False,
                message,
                status=403,
                redirect_name="home",
            )

    agendamento.status = "cancelado"
    agendamento.save(update_fields=["status"])
    return agendamento_response(
        request,
        True,
        "Agendamento cancelado com sucesso!",
        redirect_name="home",
    )


# =====================================
# Admin Agendamentos
# =====================================
@staff_member_required(login_url="admin_login")
def admin_agendamentos(request):
    return render(request, "barbearia/admin_agendamentos.html", get_admin_dashboard_context())


@staff_member_required(login_url="admin_login")
def excluir_agendamento(request, id):
    if request.method == "POST":
        agendamento = get_object_or_404(Agendamento, id=id)
        agendamento.delete()
        return JsonResponse({"ok": True, "msg": "âœ… Agendamento excluÃ­do com sucesso!"})
    return JsonResponse({"ok": False, "msg": "MÃ©todo nÃ£o permitido."}, status=405)


@staff_member_required(login_url="admin_login")
def excluir_todos_agendamentos(request):
    if request.method == "POST":
        Agendamento.objects.all().delete()
        return JsonResponse({"ok": True, "msg": "âœ… Todos os agendamentos foram excluÃ­dos!"})
    return JsonResponse({"ok": False, "msg": "MÃ©todo nÃ£o permitido."}, status=405)


# =====================================
# Login / Logout
# =====================================
def _buscar_usuario_admin(identificador):
    identificador = (identificador or "").strip()
    if not identificador:
        return None
    return User.objects.filter(
        Q(username__iexact=identificador) | Q(email__iexact=identificador)
    ).first()


def admin_login(request):
    if request.method == "POST":
        identificador = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        context = {"username_value": identificador}

        if not identificador or not password:
            messages.error(request, "Preencha usuÃ¡rio e senha.")
            return render(request, "barbearia/admin_login.html", context)

        user = authenticate(request, username=identificador, password=password)
        if not user:
            candidato = _buscar_usuario_admin(identificador)
            if candidato:
                user = authenticate(request, username=candidato.get_username(), password=password)

        if user and user.is_staff:
            login(request, user)
            return redirect("painel_admin")

        if user and not user.is_staff:
            messages.error(request, "Essa conta nÃ£o tem permissÃ£o de administrador.")
            return render(request, "barbearia/admin_login.html", context)

        messages.error(request, "UsuÃ¡rio ou senha incorretos.")
    return render(request, "barbearia/admin_login.html", {"username_value": request.POST.get("username", "")})


def custom_logout(request):
    logout(request)
    return redirect("admin_login")


# =====================================
# Painel Admin
# =====================================
@staff_member_required(login_url="admin_login")
def painel_admin(request):
    return render(request, "barbearia/admin_agendamentos.html", get_admin_dashboard_context())


# =====================================
# Dados grÃ¡ficos
# =====================================
def dados_graficos(request):
    agora = localtime(now())
    hoje = agora.date()
    hora_atual = agora.time()
    servicos = {
        "Corte": Agendamento.objects.filter(servico__nome__iexact="corte", status="agendado").filter(Q(data__gt=hoje) | Q(data=hoje, hora__gte=hora_atual)).count(),
        "Barba": Agendamento.objects.filter(servico__nome__iexact="barba", status="agendado").filter(Q(data__gt=hoje) | Q(data=hoje, hora__gte=hora_atual)).count(),
        "Corte + Barba": Agendamento.objects.filter(
            Q(servico__nome__iexact="corte + barba") | Q(servico__nome__iexact="combo"),
            status="agendado",
        ).filter(Q(data__gt=hoje) | Q(data=hoje, hora__gte=hora_atual)).count(),
        "Sobrancelha": Agendamento.objects.filter(servico__nome__iexact="sobrancelha", status="agendado").filter(Q(data__gt=hoje) | Q(data=hoje, hora__gte=hora_atual)).count(),
    }

    semana_inicio = hoje - timedelta(days=hoje.weekday())
    semana_valores = []
    for i in range(7):
        dia = semana_inicio + timedelta(days=i)
        if dia < hoje:
            semana_valores.append(0)
        elif dia == hoje:
            semana_valores.append(Agendamento.objects.filter(data=dia, hora__gte=hora_atual, status="agendado").count())
        else:
            semana_valores.append(Agendamento.objects.filter(data=dia, status="agendado").count())

    total_agendamentos = Agendamento.objects.filter(q_agendamentos_futuros(), status="agendado").count()
    total_clientes = Cliente.objects.count()

    return JsonResponse(
        {
            "servicos": list(servicos.values()),
            "semana": semana_valores,
            "total_agendamentos": total_agendamentos,
            "total_clientes": total_clientes,
        }
    )


def novos_agendamentos(request):
    hoje = localtime(now()).date()
    novos = Agendamento.objects.filter(data=hoje, status="agendado").count()
    return JsonResponse({"novos": novos})


# =====================================
# =====================================
# AUTENTICAÃ‡ÃƒO / RECUPERAÃ‡ÃƒO DE SENHA
# =====================================
def login_admin(request):
    return admin_login(request)


def sair(request):
    logout(request)
    messages.info(request, "VocÃª saiu da sua conta.")
    return redirect("admin_login")


def esqueceu_senha(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        user = _buscar_usuario_admin_email(email)
        if not user:
            admin_sem_email = _admin_sem_email_cadastrado()
            if admin_sem_email:
                messages.error(
                    request,
                    f"A conta de administrador '{admin_sem_email.username}' ainda nÃ£o tem e-mail cadastrado.",
                )
            else:
                messages.error(request, "E-mail nÃ£o encontrado ou sem acesso de administrador.")
            return render(request, "barbearia/esqueceu_senha.html", {"email_value": email})

        codigo = get_random_string(length=6, allowed_chars='0123456789')
        _limpar_recuperacao_senha(request)
        request.session['recuperacao'] = {'email': user.email, 'codigo': codigo, 'ts': now().isoformat()}
        request.session['recuperacao_tentativas'] = 0

        try:
            _enviar_codigo_recuperacao(user.email, codigo)
            messages.success(request, "CÃ³digo de recuperaÃ§Ã£o enviado para o seu e-mail.")
            return redirect("confirmar_codigo")
        except Exception:
            _limpar_recuperacao_senha(request)
            messages.error(request, "NÃ£o foi possÃ­vel enviar o cÃ³digo agora. Verifique a configuraÃ§Ã£o de e-mail.")
            return render(request, "barbearia/esqueceu_senha.html", {"email_value": email})

    return render(request, "barbearia/esqueceu_senha.html")


def confirmar_codigo(request):
    sessao = request.session.get('recuperacao')
    if not sessao:
        messages.error(request, "SessÃ£o expirada. Solicite novamente o cÃ³digo.")
        return redirect("esqueceu_senha")

    email = sessao.get('email')
    codigo_armazenado = sessao.get('codigo')
    ts_iso = sessao.get('ts')

    try:
        ts = datetime.fromisoformat(ts_iso)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt_timezone.utc)
        if (now() - ts).total_seconds() > 600:
            _limpar_recuperacao_senha(request)
            messages.error(request, "CÃ³digo expirado. Solicite novo cÃ³digo.")
            return redirect("esqueceu_senha")
    except Exception:
        _limpar_recuperacao_senha(request)
        messages.error(request, "Erro de sessÃ£o. Solicite novo cÃ³digo.")
        return redirect("esqueceu_senha")

    if request.method == "POST":
        codigo_digitado = request.POST.get("codigo", "").strip().replace(" ", "")
        tentativas = request.session.get('recuperacao_tentativas', 0)
        if tentativas >= 5:
            _limpar_recuperacao_senha(request)
            messages.error(request, "Muitas tentativas incorretas. Solicite novo cÃ³digo.")
            return redirect("esqueceu_senha")

        if codigo_digitado == codigo_armazenado:
            request.session['recuperacao_validada'] = True
            messages.success(request, "CÃ³digo confirmado! Defina nova senha.")
            return redirect("nova_senha")
        else:
            request.session['recuperacao_tentativas'] = tentativas + 1
            messages.error(request, "CÃ³digo incorreto. Tente novamente.")
            return redirect("confirmar_codigo")

    return render(request, "barbearia/confirmar_codigo.html", {"email_mask": _mascarar_email(email)})


def nova_senha(request):
    sessao = request.session.get('recuperacao')
    if not sessao or not request.session.get('recuperacao_validada'):
        messages.error(request, "SessÃ£o invÃ¡lida ou expirada. Solicite cÃ³digo novamente.")
        return redirect("esqueceu_senha")

    email = sessao.get('email')

    if request.method == "POST":
        senha = request.POST.get("senha", "")
        confirma = request.POST.get("confirma_senha", "")
        if not senha or not confirma:
            messages.error(request, "Preencha ambos os campos de senha.")
            return redirect("nova_senha")
        if senha != confirma:
            messages.error(request, "As senhas nÃ£o coincidem.")
            return redirect("nova_senha")
        if len(senha) < 6:
            messages.error(request, "Use senha com no mÃ­nimo 6 caracteres.")
            return redirect("nova_senha")

        try:
            user = _buscar_usuario_admin_email(email)
            if not user:
                raise User.DoesNotExist
            user.set_password(senha)
            user.save(update_fields=["password"])
        except User.DoesNotExist:
            messages.error(request, "UsuÃ¡rio nÃ£o encontrado.")
            return redirect("esqueceu_senha")

        _limpar_recuperacao_senha(request)

        messages.success(request, "Senha alterada com sucesso! FaÃ§a login.")
        return redirect("login_admin")

    return render(request, "barbearia/nova_senha.html")

