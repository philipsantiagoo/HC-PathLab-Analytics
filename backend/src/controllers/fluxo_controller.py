"""Fluxo operacional apoiado exclusivamente no schema ``pathlab``.

As respostas preservam o contrato HTTP atual para que a troca de schema não
exija uma segunda migração do frontend.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.usuarios import PerfilUsuario
from ..schemas.paginacao import montar_pagina
from ..helpers.identificacao import (
    TIPOS_EXAME_VALIDOS,
    gerar_codigo_interno_frasco,
    gerar_qr_code,
    identificadores_fragmentos,
    letra_fragmento,
    normalizar_tipo_exame,
)
from ..models.patologia import (
    AmostraPatologia, BlocoParafinaPatologia, CassetePatologia, CasoPatologia,
    ExamePatologia, LaminaPatologia, LoteProcessamentoPatologia,
    MacroscopiaPatologia, MovimentacaoPatologia, PacientePatologia,
    ParteMacroscopiaPatologia, TipoExamePatologia,
)


S_RECEPCAO = "Na Recepção"
S_AGUARDANDO_MACRO = "Aguardando Macroscopia"
S_EM_MACRO = "Em Macroscopia"
S_EM_PROCESSAMENTO = "Em Processamento"
S_EM_MICRO = "Em Microscopia"
S_REVISAO = "Revisão Pendente"
S_LIBERADO = "Liberado"
S_AGUARDANDO_PROCESSAMENTO = "Aguardando Processamento"
S_PROCESSAMENTO = "Em Processamento"
S_PROCESSADO = "Processamento Completo"
S_AGUARDANDO_CORTE = "Aguardando Corte"
S_AGUARDANDO_MICRO = "Aguardando Microscopia"

# Etapa da macroscopia — coluna dedicada em ``exames.etapa_macroscopia``.
# Separada de ``status`` porque o status é escrito por vários caminhos do fluxo
# e porque CONCLUIDA precisa sobreviver ao avanço para "Em Processamento".
EM_AGUARDANDO = "AGUARDANDO"
EM_ANDAMENTO = "EM_ANDAMENTO"
EM_CONCLUIDA = "CONCLUIDA"

SLA_DIAS = 20


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _atrasado(entrada: Optional[datetime], agora: Optional[datetime] = None) -> bool:
    """SLA estourado. ``agora`` é passado pelos laços para não recalcular por linha."""
    if entrada is None:
        return False
    return ((agora or _now()) - entrada).days >= SLA_DIAS


def _mov(session, *, exame=None, amostra=None, etapa: str, anterior: str | None, novo: str, usuario: str | None, observacoes: str | None = None):
    session.add(MovimentacaoPatologia(
        id=str(uuid.uuid4()), id_exame=exame.id if exame else None,
        id_amostra=amostra.id if amostra else None, etapa=etapa,
        status_anterior=anterior, status_novo=novo,
        usuario_responsavel=usuario, observacoes=observacoes,
    ))


def _frasco(amostra: AmostraPatologia) -> dict:
    return {
        "id": amostra.id, "id_exame": amostra.id_exame,
        "codigo_interno": amostra.codigo_interno or "",
        "qr_code": amostra.qr_code or "", "status": amostra.status,
        "descricao_macroscopia": amostra.descricao_macroscopia,
        "numero_cassetes_gerados": amostra.numero_cassetes_gerados or 0,
        "data_criacao": amostra.criado_em,
    }


async def _contexto_amostra(session: AsyncSession, amostra_id: str):
    row = (await session.execute(
        select(AmostraPatologia, ExamePatologia, PacientePatologia)
        .join(ExamePatologia, AmostraPatologia.id_exame == ExamePatologia.id)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(AmostraPatologia.id == amostra_id)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Amostra não encontrada.")
    return row


async def _proximo_numero(session: AsyncSession, tipo: TipoExamePatologia):
    agora = _now()
    ano, semestre = agora.year % 100, 1 if agora.month <= 6 else 2
    maior = (await session.execute(select(func.max(ExamePatologia.sequencial)).where(
        ExamePatologia.id_tipo_exame == tipo.id, ExamePatologia.ano == ano,
        ExamePatologia.semestre == semestre,
    ))).scalar_one() or 0
    sequencial = maior + 1
    return f"{tipo.prefixo}-{sequencial:04d}/{ano:02d}.{semestre}", sequencial, ano, semestre


async def registrar_recebimento(session: AsyncSession, dados, usuario: Optional[str], ip: Optional[str]) -> dict:
    p = dados.paciente
    if not p.cpf and not p.cns:
        raise HTTPException(status_code=400, detail="Informe ao menos CPF ou CNS do paciente.")
    codigo = normalizar_tipo_exame(dados.tipo_exame)
    if codigo not in TIPOS_EXAME_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_exame inválido: '{codigo}'.")
    tipo = (await session.execute(select(TipoExamePatologia).where(TipoExamePatologia.codigo == codigo))).scalar_one_or_none()
    if not tipo:
        raise HTTPException(status_code=422, detail="Tipo de exame não configurado no catálogo.")
    paciente = (await session.execute(select(PacientePatologia).where(
        (PacientePatologia.cpf == p.cpf) if p.cpf else (PacientePatologia.cns == p.cns)
    ))).scalar_one_or_none()
    if not paciente:
        chave = f"MANUAL:{p.cpf or p.cns}"
        paciente = PacientePatologia(id=str(uuid.uuid4()), chave_origem=chave, nome=p.nome,
            cpf=p.cpf, cns=p.cns, data_nascimento=p.data_nascimento, origem=p.origem, criado_por=usuario)
        session.add(paciente)
        await session.flush()
    numero, sequencial, ano, semestre = await _proximo_numero(session, tipo)
    caso = CasoPatologia(id=str(uuid.uuid4()), chave_origem=f"MANUAL:{uuid.uuid4()}", id_paciente=paciente.id,
        data_solicitacao=_now().date(), situacao_importacao="PRONTO")
    exame = ExamePatologia(id=str(uuid.uuid4()), id_caso=caso.id, id_tipo_exame=tipo.id,
        numero_local=numero, sequencial=sequencial, ano=ano, semestre=semestre,
        status=S_RECEPCAO, numero_exame_aghu=dados.numero_exame_aghu, tipo_peca=dados.tipo_peca,
        topografia=dados.topografia, data_recebimento=_now(), criado_por=usuario)
    session.add_all([caso, exame])
    await session.flush()
    amostra_id = str(uuid.uuid4())
    amostra = AmostraPatologia(id=amostra_id, id_caso=caso.id, id_exame=exame.id, numero_amostra=1,
        codigo_solicitacao=numero, codigo_interno=gerar_codigo_interno_frasco(numero),
        qr_code=gerar_qr_code("FRASCO", numero, identificador=amostra_id), status=S_AGUARDANDO_MACRO,
        criado_por=usuario)
    session.add(amostra)
    _mov(session, exame=exame, etapa="Triagem", anterior=None, novo=S_RECEPCAO, usuario=usuario, observacoes="Exame criado na recepção")
    _mov(session, amostra=amostra, etapa="Triagem", anterior=None, novo=S_AGUARDANDO_MACRO, usuario=usuario, observacoes="Amostra disponível para macroscopia")
    # O exame entra na FILA da macroscopia; "Em Macroscopia" só quando alguém
    # assumir. Antes isso era avançado aqui e a base inteira ficou num status
    # que não refletia trabalho nenhum.
    exame.status = S_AGUARDANDO_MACRO
    exame.etapa_macroscopia = EM_AGUARDANDO
    _mov(session, exame=exame, etapa="Macroscopia", anterior=S_RECEPCAO, novo=exame.status, usuario=usuario, observacoes="Código local gerado; encaminhado à fila da macroscopia")
    await session.commit()
    await session.refresh(amostra)
    return {"exame": _exame(exame), "frasco": _frasco(amostra), "etiqueta": {"tipo":"FRASCO", "numero_solicitacao":numero, "codigo":amostra.codigo_interno, "qr_code":amostra.qr_code}}


def _exame(exame: ExamePatologia) -> dict:
    return {"id": exame.id, "numero_solicitacao": exame.numero_local or "", "tipo_exame": "",
            "id_paciente": "", "numero_exame_aghu": exame.numero_exame_aghu,
            "tipo_peca": exame.tipo_peca, "topografia": exame.topografia,
            "status": exame.status, "data_recebimento": exame.data_recebimento}


async def listar_exames(session: AsyncSession, limite: int | None = 200):
    stmt = select(ExamePatologia, TipoExamePatologia).join(TipoExamePatologia).order_by(ExamePatologia.criado_em.desc(), ExamePatologia.id.desc())
    if limite is not None:
        stmt = stmt.limit(limite)
    rows = (await session.execute(stmt)).all()
    return [{**_exame(e), "tipo_exame": t.codigo} for e, t in rows]


async def obter_exame(session: AsyncSession, id_exame: str):
    row = (await session.execute(select(ExamePatologia, TipoExamePatologia).join(TipoExamePatologia).where(ExamePatologia.id == id_exame))).first()
    if not row: raise HTTPException(status_code=404, detail="Exame não encontrado.")
    exame, tipo = row
    return {**_exame(exame), "tipo_exame": tipo.codigo}


async def obter_detalhe(session: AsyncSession, id_exame: str):
    exame = await obter_exame(session, id_exame)
    row = (await session.execute(select(ExamePatologia, CasoPatologia, PacientePatologia).join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id).join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id).where(ExamePatologia.id == id_exame))).first()
    e, _, p = row
    amostras = list((await session.execute(select(AmostraPatologia).where(AmostraPatologia.id_exame == id_exame))).scalars())
    return {"codigo_local":e.numero_local,"etapa_atual":e.status,"urgente":False,
            "aghu":{"nome_paciente":p.nome,"prontuario":p.prontuario or p.cns or p.cpf or "—","idade":0,"origem":p.origem or "—","tipo_material":e.tipo_peca or "","tipo_exame":exame["tipo_exame"],"numero_solicitacao_aghu":e.numero_exame_aghu or "—","procedimento_sus":"—","indicacao_clinica":f"Topografia: {e.topografia}" if e.topografia else "—"},
            "recepcao":{"data_entrada":e.data_recebimento,"quantidade_frascos":len(amostras),"descricao_fisica":e.tipo_peca or "—","frascos_ids":[a.codigo_interno or a.codigo_solicitacao for a in amostras],"responsavel":e.criado_por or "—"} if amostras else None,
            "macroscopia":None,"processamento":None,"microscopia":None}


def _linha_dashboard(exame, paciente_nome, total_frascos, agora) -> dict:
    entrada = exame.data_recebimento or exame.criado_em
    return {
        "id": exame.id,
        "solicitacao": exame.numero_local or "PENDENTE",
        "codigo_aghu": exame.numero_exame_aghu,
        "paciente": paciente_nome,
        "etapa": exame.status,
        "data_entrada": entrada,
        "atrasado": _atrasado(entrada, agora),
        "total_frascos": total_frascos or 0,
        "data_inicio_trabalho": exame.assumido_em,
        "responsavel_macroscopia_nome": exame.responsavel_macroscopia_nome,
    }


def _clausulas_dashboard(
    etapa: Optional[str] = None,
    codigo_aghu: Optional[str] = None,
    codigo_interno: Optional[str] = None,
    nome_paciente: Optional[str] = None,
    busca: Optional[str] = None,
) -> list:
    """Filtros do dashboard, compartilhados entre a página e o COUNT.

    ``busca`` é o campo único (usado pela fila); os demais são os filtros
    dedicados da barra de pesquisa do dashboard. Combinam-se com AND.
    """
    clausulas = []
    if etapa:
        clausulas.append(ExamePatologia.status == etapa)
    if codigo_aghu:
        clausulas.append(ExamePatologia.numero_exame_aghu.ilike(f"%{codigo_aghu.strip()}%"))
    if codigo_interno:
        clausulas.append(ExamePatologia.numero_local.ilike(f"%{codigo_interno.strip()}%"))
    if nome_paciente:
        clausulas.append(PacientePatologia.nome.ilike(f"%{nome_paciente.strip()}%"))
    if busca:
        alvo = f"%{busca.strip()}%"
        clausulas.append(or_(
            ExamePatologia.numero_local.ilike(alvo),
            ExamePatologia.numero_exame_aghu.ilike(alvo),
            PacientePatologia.nome.ilike(alvo),
        ))
    return clausulas


async def listar_dashboard(
    session: AsyncSession,
    limite: int | None = None,
    etapa: Optional[str] = None,
    codigo_aghu: Optional[str] = None,
    codigo_interno: Optional[str] = None,
    nome_paciente: Optional[str] = None,
):
    """Rota antiga, mantida por compatibilidade. Prefira ``listar_dashboard_paginado``."""
    stmt = (
        select(ExamePatologia, PacientePatologia.nome, _TOTAL_FRASCOS)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(*_clausulas_dashboard(etapa, codigo_aghu, codigo_interno, nome_paciente))
        .order_by(ExamePatologia.criado_em.desc(), ExamePatologia.id.desc())
    )
    if limite is not None:
        stmt = stmt.limit(limite)
    rows = (await session.execute(stmt)).all()
    agora = _now()
    return [_linha_dashboard(e, nome, n, agora) for e, nome, n in rows]


async def listar_dashboard_paginado(
    session: AsyncSession,
    etapa: Optional[str] = None,
    busca: Optional[str] = None,
    pagina: int = 1,
    por_pagina: int = 25,
    codigo_aghu: Optional[str] = None,
    codigo_interno: Optional[str] = None,
    nome_paciente: Optional[str] = None,
) -> dict:
    """Dashboard por exame, paginado no servidor, com os filtros da barra de pesquisa."""
    clausulas = _clausulas_dashboard(etapa, codigo_aghu, codigo_interno, nome_paciente, busca)

    base = (
        select(ExamePatologia, PacientePatologia.nome, _TOTAL_FRASCOS)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(*clausulas)
        .order_by(ExamePatologia.criado_em.desc(), ExamePatologia.id.desc())
        .limit(por_pagina)
        .offset((pagina - 1) * por_pagina)
    )
    contagem = (
        select(func.count(ExamePatologia.id))
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(*clausulas)
    )

    rows = (await session.execute(base)).all()
    total = (await session.execute(contagem)).scalar_one()
    agora = _now()
    return montar_pagina([_linha_dashboard(e, nome, n, agora) for e, nome, n in rows], total, pagina, por_pagina)


async def resumo_dashboard(session: AsyncSession) -> dict:
    """Contagens calculadas no banco; evita transferir toda a fila ao dashboard."""
    agora = _now()
    entrada = func.coalesce(ExamePatologia.data_recebimento, ExamePatologia.criado_em)
    linhas = (await session.execute(
        select(ExamePatologia.status, func.count(ExamePatologia.id))
        .group_by(ExamePatologia.status)
    )).all()
    atrasados = (await session.execute(select(func.count(ExamePatologia.id)).where(entrada < agora - timedelta(days=20)))).scalar_one()
    alerta = (await session.execute(select(func.count(ExamePatologia.id)).where(
        entrada >= agora - timedelta(days=20), entrada < agora - timedelta(days=15)
    ))).scalar_one()
    return {"por_status": {status: total for status, total in linhas}, "atrasados": atrasados, "alerta": alerta}


async def listar_pendencias_recepcao(session: AsyncSession):
    return await _listar_amostras(session, [S_RECEPCAO])


async def listar_pendencias_macroscopia(session: AsyncSession, limite: int | None = None):
    """Fila da estação: inclui as amostras já assumidas (``Em Macroscopia``)
    para que o macroscopista retome uma clivagem interrompida sem depender de
    lembrar o código do frasco."""
    return await _listar_amostras(session, [S_AGUARDANDO_MACRO, S_EM_MACRO], limite)


# =====================================================================
# Fila da macroscopia — sempre por exame, nunca por frasco.
# =====================================================================

# Contagem de frascos como subquery escalar correlacionada. Com JOIN +
# GROUP BY o LIMIT passaria a ser aplicado depois de agregar as 28k amostras;
# aqui roda uma vez por linha da página, cada uma um index scan em
# ix_amostras_id_exame.
_TOTAL_FRASCOS = (
    select(func.count(AmostraPatologia.id))
    .where(AmostraPatologia.id_exame == ExamePatologia.id)
    .correlate(ExamePatologia)
    .scalar_subquery()
    .label("total_frascos")
)

FILTROS_FILA_MACRO = ("meus", "aguardando", "em_andamento", "todos")


def _clausulas_fila_macro(filtro: str, usuario: Optional[str], busca: Optional[str]) -> list:
    """Condições da fila, compartilhadas entre a página e o COUNT.

    Um helper só para os dois nunca divergirem — se a contagem usar um filtro
    diferente da listagem, a paginação passa a mentir.
    """
    if filtro not in FILTROS_FILA_MACRO:
        raise HTTPException(status_code=400, detail=f"filtro inválido: '{filtro}'.")

    clausulas = []
    if filtro == "meus":
        # Sem usuário no token não há "meus" — devolve vazio em vez de tudo.
        clausulas.append(ExamePatologia.responsavel_macroscopia == (usuario or "\x00"))
        clausulas.append(ExamePatologia.etapa_macroscopia == EM_ANDAMENTO)
    elif filtro == "aguardando":
        clausulas.append(ExamePatologia.etapa_macroscopia == EM_AGUARDANDO)
    elif filtro == "em_andamento":
        clausulas.append(ExamePatologia.etapa_macroscopia == EM_ANDAMENTO)
    else:  # todos — fila é fila, concluídos não entram
        clausulas.append(ExamePatologia.etapa_macroscopia.in_([EM_AGUARDANDO, EM_ANDAMENTO]))

    if busca:
        alvo = f"%{busca.strip()}%"
        clausulas.append(or_(
            ExamePatologia.numero_local.ilike(alvo),
            ExamePatologia.numero_exame_aghu.ilike(alvo),
            PacientePatologia.nome.ilike(alvo),
        ))
    return clausulas


def _linha_fila_macro(exame, paciente_nome, tipo_codigo, total_frascos, agora) -> dict:
    entrada = exame.data_recebimento or exame.criado_em
    return {
        "id_exame": exame.id,
        "numero_solicitacao": exame.numero_local or "PENDENTE",
        "tipo_exame": tipo_codigo,
        "paciente_nome": paciente_nome,
        "numero_exame_aghu": exame.numero_exame_aghu,
        "tipo_peca": exame.tipo_peca,
        "total_frascos": total_frascos or 0,
        "etapa_macroscopia": exame.etapa_macroscopia,
        "responsavel_macroscopia": exame.responsavel_macroscopia,
        "responsavel_macroscopia_nome": exame.responsavel_macroscopia_nome,
        "assumido_em": exame.assumido_em,
        "data_entrada": entrada,
        "atrasado": _atrasado(entrada, agora),
    }


async def listar_fila_macroscopia(
    session: AsyncSession,
    usuario: Optional[str],
    filtro: str = "aguardando",
    busca: Optional[str] = None,
    pagina: int = 1,
    por_pagina: int = 25,
) -> dict:
    """Uma página da fila + os contadores das quatro abas."""
    clausulas = _clausulas_fila_macro(filtro, usuario, busca)

    base = (
        select(ExamePatologia, PacientePatologia.nome, TipoExamePatologia.codigo, _TOTAL_FRASCOS)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .join(TipoExamePatologia, ExamePatologia.id_tipo_exame == TipoExamePatologia.id)
        .where(*clausulas)
        # O ", id" é obrigatório: os casos vieram de importação em lote e
        # compartilham criado_em. Sem desempate o OFFSET duplica e pula linhas.
        .order_by(ExamePatologia.criado_em.desc(), ExamePatologia.id.desc())
        .limit(por_pagina)
        .offset((pagina - 1) * por_pagina)
    )

    # O COUNT roda só sobre exames + o join de paciente (necessário quando há
    # busca por nome). Os joins são 1:1, então não alteram a cardinalidade.
    contagem = (
        select(func.count(ExamePatologia.id))
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(*clausulas)
    )

    rows = (await session.execute(base)).all()
    total = (await session.execute(contagem)).scalar_one()
    agora = _now()
    itens = [_linha_fila_macro(e, nome, codigo, n, agora) for e, nome, codigo, n in rows]

    return {
        **montar_pagina(itens, total, pagina, por_pagina),
        "contadores": await _contadores_fila_macro(session, usuario, busca),
    }


async def _contadores_fila_macro(session: AsyncSession, usuario: Optional[str], busca: Optional[str]) -> dict:
    """Contagem das quatro abas numa única varredura agregada."""
    clausulas = []
    if busca:
        alvo = f"%{busca.strip()}%"
        clausulas.append(or_(
            ExamePatologia.numero_local.ilike(alvo),
            ExamePatologia.numero_exame_aghu.ilike(alvo),
            PacientePatologia.nome.ilike(alvo),
        ))

    stmt = (
        select(ExamePatologia.etapa_macroscopia, ExamePatologia.responsavel_macroscopia, func.count(ExamePatologia.id))
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(ExamePatologia.etapa_macroscopia.in_([EM_AGUARDANDO, EM_ANDAMENTO]), *clausulas)
        .group_by(ExamePatologia.etapa_macroscopia, ExamePatologia.responsavel_macroscopia)
    )
    meus = aguardando = em_andamento = 0
    for etapa, responsavel, total in (await session.execute(stmt)).all():
        if etapa == EM_AGUARDANDO:
            aguardando += total
        elif etapa == EM_ANDAMENTO:
            em_andamento += total
            if usuario and responsavel == usuario:
                meus += total
    return {
        "meus": meus,
        "aguardando": aguardando,
        "em_andamento": em_andamento,
        "todos": aguardando + em_andamento,
    }


async def _listar_amostras(session, statuses, limite: int | None = None):
    stmt = select(AmostraPatologia, ExamePatologia, PacientePatologia).join(ExamePatologia, AmostraPatologia.id_exame == ExamePatologia.id).join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id).join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id).where(AmostraPatologia.status.in_(statuses)).order_by(AmostraPatologia.criado_em)
    if limite is not None:
        stmt = stmt.limit(limite)
    rows = (await session.execute(stmt)).all()
    return [{"id_frasco":a.id, "id_exame":e.id, "codigo_interno":a.codigo_interno or a.codigo_solicitacao,
             "status":a.status, "numero_solicitacao":e.numero_local or a.codigo_solicitacao,
             "numero_exame_aghu":e.numero_exame_aghu, "tipo_peca":e.tipo_peca,
             "paciente_nome":p.nome, "data_criacao":a.criado_em} for a,e,p in rows]


async def buscar_frasco(session, numero_solicitacao: Optional[str], codigo_interno: Optional[str]):
    if not numero_solicitacao and not codigo_interno: raise HTTPException(status_code=400, detail="Informe numero_solicitacao ou codigo_interno.")
    filtros = []
    if numero_solicitacao:
        filtros.append(ExamePatologia.numero_local == numero_solicitacao)
    if codigo_interno:
        filtros.append(AmostraPatologia.codigo_interno == codigo_interno)
    rows = (await session.execute(
        select(AmostraPatologia, ExamePatologia, PacientePatologia)
        .join(ExamePatologia, AmostraPatologia.id_exame == ExamePatologia.id)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(or_(*filtros))
        .order_by(AmostraPatologia.criado_em)
        .limit(50)
    )).all()
    resultado = [{"id_frasco":a.id, "id_exame":e.id, "codigo_interno":a.codigo_interno or a.codigo_solicitacao,
                  "status":a.status, "numero_solicitacao":e.numero_local or a.codigo_solicitacao,
                  "numero_exame_aghu":e.numero_exame_aghu, "tipo_peca":e.tipo_peca,
                  "paciente_nome":p.nome, "data_criacao":a.criado_em} for a, e, p in rows]
    if not resultado: raise HTTPException(status_code=404, detail="Nenhuma amostra encontrada.")
    return resultado


async def encaminhar_para_macroscopia(session, id_frasco: str, usuario, ip):
    amostra, exame, _ = await _contexto_amostra(session, id_frasco)
    if amostra.status == S_RECEPCAO:
        anterior, amostra.status = amostra.status, S_AGUARDANDO_MACRO
        _mov(session, amostra=amostra, etapa="Triagem", anterior=anterior, novo=amostra.status, usuario=usuario)
    if exame.status == S_RECEPCAO:
        # Vai para a FILA da macroscopia; "Em Macroscopia" só quando assumido.
        anterior, exame.status = exame.status, S_AGUARDANDO_MACRO
        exame.etapa_macroscopia = EM_AGUARDANDO
        _mov(session, exame=exame, etapa="Macroscopia", anterior=anterior, novo=exame.status, usuario=usuario)
    await session.commit(); await session.refresh(amostra)
    return _frasco(amostra)


async def iniciar_macroscopia(session, id_frasco: str, usuario, ip, nome_usuario: Optional[str] = None):
    """Rota antiga por frasco. Resolve o exame e delega para ``assumir_exame``,
    para não existirem dois caminhos de posse com regras diferentes."""
    amostra, exame, _ = await _contexto_amostra(session, id_frasco)
    await assumir_exame(session, exame.id, usuario, nome_usuario)
    await session.refresh(amostra)
    return _frasco(amostra)


# =====================================================================
# Posse do exame na macroscopia
# =====================================================================


async def _linha_exame(session: AsyncSession, id_exame: str) -> dict:
    """Recarrega a linha da fila para um exame — resposta de assumir/repassar.

    ``populate_existing`` é obrigatório: a sessão usa ``expire_on_commit=False``
    e os UPDATE em massa rodam com ``synchronize_session=False``, então sem isso
    o identity map devolveria a instância anterior à mudança de posse.
    """
    row = (await session.execute(
        select(ExamePatologia, PacientePatologia.nome, TipoExamePatologia.codigo, _TOTAL_FRASCOS)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .join(TipoExamePatologia, ExamePatologia.id_tipo_exame == TipoExamePatologia.id)
        .where(ExamePatologia.id == id_exame)
        .execution_options(populate_existing=True)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Exame não encontrado.")
    exame, nome, codigo, total = row
    return _linha_fila_macro(exame, nome, codigo, total, _now())


async def assumir_exame(session: AsyncSession, id_exame: str, usuario: Optional[str], nome_usuario: Optional[str]) -> dict:
    """Assume o exame para quem chamou.

    Um único UPDATE condicional, sem SELECT antes: sob READ COMMITTED o segundo
    concorrente bloqueia no row lock e, quando o primeiro comita, o PostgreSQL
    reavalia o WHERE contra a versão nova — ``rowcount`` fica 0. Um SELECT
    seguido de UPDATE seria exatamente a corrida que queremos evitar.

    Só ``IS NULL`` adquire a posse. O caso "já é meu" cai no ramo de
    ``rowcount == 0`` e retorna sem gravar uma segunda movimentação, para um F5
    ou duplo clique não poluir a trilha de auditoria.
    """
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuário não identificado no token.")

    resultado = await session.execute(
        update(ExamePatologia)
        .where(
            ExamePatologia.id == id_exame,
            ExamePatologia.etapa_macroscopia != EM_CONCLUIDA,
            ExamePatologia.responsavel_macroscopia.is_(None),
        )
        .values(
            responsavel_macroscopia=usuario,
            responsavel_macroscopia_nome=nome_usuario or usuario,
            assumido_em=_now(),
            etapa_macroscopia=EM_ANDAMENTO,
            status=S_EM_MACRO,
        )
        .execution_options(synchronize_session=False)
    )

    if resultado.rowcount == 0:
        await session.rollback()
        exame = await session.get(ExamePatologia, id_exame)
        if not exame:
            raise HTTPException(status_code=404, detail="Exame não encontrado.")
        if exame.etapa_macroscopia == EM_CONCLUIDA:
            raise HTTPException(status_code=409, detail="A macroscopia deste exame já foi concluída.")
        if exame.responsavel_macroscopia == usuario:
            return await _linha_exame(session, id_exame)  # já é meu
        dono = exame.responsavel_macroscopia_nome or exame.responsavel_macroscopia
        raise HTTPException(status_code=409, detail=f"Exame já assumido por {dono}. Peça um repasse.")

    # As amostras acompanham o exame — os frascos andam juntos.
    await session.execute(
        update(AmostraPatologia)
        .where(AmostraPatologia.id_exame == id_exame, AmostraPatologia.status == S_AGUARDANDO_MACRO)
        .values(status=S_EM_MACRO)
        .execution_options(synchronize_session=False)
    )
    exame = await session.get(ExamePatologia, id_exame)
    _mov(session, exame=exame, etapa="Macroscopia", anterior=S_AGUARDANDO_MACRO, novo=S_EM_MACRO,
         usuario=usuario, observacoes="Exame assumido")
    await session.commit()
    return await _linha_exame(session, id_exame)


async def repassar_exame(session: AsyncSession, id_exame: str, dados, usuario: Optional[str], eh_admin: bool = False) -> dict:
    """Transfere a posse. Só o dono atual — ou um admin — pode repassar."""
    exame = await session.get(ExamePatologia, id_exame)
    if not exame:
        raise HTTPException(status_code=404, detail="Exame não encontrado.")
    if exame.etapa_macroscopia == EM_CONCLUIDA:
        raise HTTPException(status_code=409, detail="A macroscopia deste exame já foi concluída.")
    if not exame.responsavel_macroscopia:
        raise HTTPException(status_code=409, detail="Assuma o exame antes de repassá-lo.")
    if exame.responsavel_macroscopia != usuario and not eh_admin:
        dono = exame.responsavel_macroscopia_nome or exame.responsavel_macroscopia
        raise HTTPException(status_code=403, detail=f"Só {dono} pode repassar este exame.")

    destino = dados.para_username.strip()
    if not destino:
        raise HTTPException(status_code=400, detail="Informe o destinatário.")
    if destino == exame.responsavel_macroscopia:
        raise HTTPException(status_code=400, detail="O exame já está com esse responsável.")

    dono_anterior = exame.responsavel_macroscopia
    # Mesmo padrão condicional do assumir: se a posse mudou entre o SELECT
    # acima e este UPDATE, rowcount fica 0.
    resultado = await session.execute(
        update(ExamePatologia)
        .where(
            ExamePatologia.id == id_exame,
            ExamePatologia.responsavel_macroscopia == dono_anterior,
        )
        .values(
            responsavel_macroscopia=destino,
            responsavel_macroscopia_nome=(dados.para_nome or destino),
            assumido_em=_now(),
            etapa_macroscopia=EM_ANDAMENTO,
        )
        .execution_options(synchronize_session=False)
    )
    if resultado.rowcount == 0:
        await session.rollback()
        raise HTTPException(status_code=409, detail="A posse do exame mudou. Recarregue a fila.")

    exame = await session.get(ExamePatologia, id_exame)
    _mov(session, exame=exame, etapa="Repasse Macroscopia", anterior=dono_anterior, novo=destino,
         usuario=usuario, observacoes=dados.motivo)
    await session.commit()
    return await _linha_exame(session, id_exame)


async def liberar_exame(session: AsyncSession, id_exame: str, usuario: Optional[str], eh_admin: bool = False) -> dict:
    """Devolve o exame à fila. Saída para quando o dono fica indisponível."""
    exame = await session.get(ExamePatologia, id_exame)
    if not exame:
        raise HTTPException(status_code=404, detail="Exame não encontrado.")
    if exame.etapa_macroscopia == EM_CONCLUIDA:
        raise HTTPException(status_code=409, detail="A macroscopia deste exame já foi concluída.")
    if not exame.responsavel_macroscopia:
        return await _linha_exame(session, id_exame)  # idempotente
    if exame.responsavel_macroscopia != usuario and not eh_admin:
        raise HTTPException(status_code=403, detail="Só o responsável ou um administrador pode liberar o exame.")

    dono_anterior = exame.responsavel_macroscopia
    exame.responsavel_macroscopia = None
    exame.responsavel_macroscopia_nome = None
    exame.assumido_em = None
    exame.etapa_macroscopia = EM_AGUARDANDO
    exame.status = S_AGUARDANDO_MACRO
    await session.execute(
        update(AmostraPatologia)
        .where(AmostraPatologia.id_exame == id_exame, AmostraPatologia.status == S_EM_MACRO)
        .values(status=S_AGUARDANDO_MACRO)
        .execution_options(synchronize_session=False)
    )
    _mov(session, exame=exame, etapa="Macroscopia", anterior=dono_anterior, novo=S_AGUARDANDO_MACRO,
         usuario=usuario, observacoes="Exame liberado de volta à fila")
    await session.commit()
    return await _linha_exame(session, id_exame)


async def obter_workspace_macroscopia(session: AsyncSession, id_exame: str, usuario: Optional[str], eh_admin: bool = False) -> dict:
    """Tudo que a estação precisa para abrir um exame."""
    linha = await _linha_exame(session, id_exame)
    exame = await session.get(ExamePatologia, id_exame)

    amostras = list((await session.execute(
        select(AmostraPatologia)
        .where(AmostraPatologia.id_exame == id_exame)
        .order_by(AmostraPatologia.numero_amostra)
    )).scalars())

    macro = (await session.execute(
        select(MacroscopiaPatologia).where(MacroscopiaPatologia.id_exame == id_exame)
    )).scalar_one_or_none()

    partes, cassetes = [], []
    if macro:
        partes = [
            {"id": x.id, "id_macroscopia": x.id_macroscopia, "ordinal": x.ordinal,
             "letra_identificacao": x.letra_identificacao, "descricao_estrutura": x.descricao_estrutura,
             "quantidade_fragmentos": x.quantidade_fragmentos}
            for x in (await session.execute(
                select(ParteMacroscopiaPatologia)
                .where(ParteMacroscopiaPatologia.id_macroscopia == macro.id)
                .order_by(ParteMacroscopiaPatologia.ordinal)
            )).scalars()
        ]
        cassetes = [_cassete(x) for x in (await session.execute(
            select(CassetePatologia)
            .where(CassetePatologia.id_exame == id_exame)
            .order_by(CassetePatologia.identificador)
        )).scalars()]

    sou_o_dono = bool(usuario) and exame.responsavel_macroscopia == usuario
    return {
        "exame": linha,
        "posse": {
            "responsavel": exame.responsavel_macroscopia,
            "responsavel_nome": exame.responsavel_macroscopia_nome,
            "assumido_em": exame.assumido_em,
            "etapa_macroscopia": exame.etapa_macroscopia,
            "sou_o_dono": sou_o_dono,
            "pode_liberar": bool(exame.responsavel_macroscopia) and (sou_o_dono or eh_admin),
        },
        "frascos": [_frasco(a) for a in amostras],
        "macroscopia": {
            "id": macro.id, "id_exame": macro.id_exame, "descricao": macro.descricao,
            "data_realizacao": macro.criado_em, "responsavel": macro.responsavel,
            "numero_cassetes": macro.numero_cassetes,
        } if macro else None,
        "partes": partes,
        "cassetes": cassetes,
    }


async def listar_usuarios_candidatos(session: AsyncSession, busca: Optional[str] = None, limite: int = 30) -> list[dict]:
    """Candidatos a receber um repasse.

    ``perfis_usuarios`` só ganha linha quando alguém faz login, então uma lista
    baseada só nela nasce praticamente vazia. Completamos com os usernames que
    já aparecem no fluxo, marcados como ``historico``.
    """
    encontrados: dict[str, dict] = {}

    stmt = select(PerfilUsuario).where(PerfilUsuario.ativo.is_(True))
    if busca:
        alvo = f"%{busca.strip()}%"
        stmt = stmt.where(or_(PerfilUsuario.username.ilike(alvo), PerfilUsuario.nome_exibicao.ilike(alvo)))
    for perfil in (await session.execute(stmt.limit(limite))).scalars():
        encontrados[perfil.username] = {
            "username": perfil.username, "nome_exibicao": perfil.nome_exibicao,
            "email": perfil.email, "departamento": perfil.departamento, "origem": "perfil",
        }

    colunas = (
        ExamePatologia.responsavel_macroscopia,
        ExamePatologia.criado_por,
        MovimentacaoPatologia.usuario_responsavel,
    )
    for coluna in colunas:
        if len(encontrados) >= limite:
            break
        stmt = select(coluna).where(coluna.is_not(None)).distinct().limit(limite)
        if busca:
            stmt = stmt.where(coluna.ilike(f"%{busca.strip()}%"))
        for (username,) in (await session.execute(stmt)).all():
            if username and username not in encontrados:
                encontrados[username] = {
                    "username": username, "nome_exibicao": None, "email": None,
                    "departamento": None, "origem": "historico",
                }

    return sorted(encontrados.values(), key=lambda u: (u["nome_exibicao"] or u["username"]).lower())[:limite]


async def obter_etiqueta_frasco(session, id_frasco: str):
    amostra, exame, _ = await _contexto_amostra(session, id_frasco)
    return {"tipo":"FRASCO", "numero_solicitacao":exame.numero_local or amostra.codigo_solicitacao, "codigo":amostra.codigo_interno or "", "qr_code":amostra.qr_code or ""}


def _cassete(cassete: CassetePatologia, descricao_estrutura: Optional[str] = None) -> dict:
    return {
        "id": cassete.id, "id_exame": cassete.id_exame,
        "id_parte_macroscopia": cassete.id_parte_macroscopia,
        "letra_fragmento": cassete.identificador, "qr_code": cassete.qr_code,
        "descricao_estrutura": descricao_estrutura, "observacoes_macroscopia": None,
        "coloracao_padrao": cassete.coloracao_padrao, "status": cassete.status,
    }


async def registrar_macroscopia(session, dados, usuario, ip, eh_admin: bool = False):
    """Registra a clivagem do exame inteiro.

    Uma macroscopia por exame: o exame é a peça e os frascos são apenas como o
    material chegou. Todas as amostras do exame avançam juntas.
    """
    # id_frasco continua aceito pelo cliente antigo — resolve para o exame.
    id_exame = dados.id_exame
    if not id_exame:
        amostra_origem, exame_origem, _ = await _contexto_amostra(session, dados.id_frasco)
        id_exame = exame_origem.id

    exame = await session.get(ExamePatologia, id_exame)
    if not exame:
        raise HTTPException(status_code=404, detail="Exame não encontrado.")

    # Sem esta guarda, "assumir" não significaria nada.
    if exame.etapa_macroscopia == EM_CONCLUIDA:
        raise HTTPException(status_code=409, detail="Este exame já tem uma macroscopia registrada.")
    if exame.etapa_macroscopia != EM_ANDAMENTO:
        raise HTTPException(status_code=409, detail="Assuma o exame antes de registrar a clivagem.")
    if exame.responsavel_macroscopia != usuario and not eh_admin:
        dono = exame.responsavel_macroscopia_nome or exame.responsavel_macroscopia
        raise HTTPException(status_code=403, detail=f"Este exame está com {dono}.")

    amostras = list((await session.execute(
        select(AmostraPatologia)
        .where(AmostraPatologia.id_exame == id_exame)
        .order_by(AmostraPatologia.numero_amostra)
    )).scalars())
    if not amostras:
        raise HTTPException(status_code=422, detail="O exame não tem frascos registrados.")

    numero = exame.numero_local or amostras[0].codigo_solicitacao
    macro = MacroscopiaPatologia(
        id=str(uuid.uuid4()), id_exame=exame.id, descricao=dados.descricao,
        responsavel=exame.responsavel_macroscopia or usuario,
        numero_cassetes=sum(len(x.fragmentos) for x in dados.partes),
    )
    session.add(macro)
    try:
        await session.flush()
    except IntegrityError:
        # A UNIQUE em id_exame é a última defesa contra duplo submit.
        await session.rollback()
        raise HTTPException(status_code=409, detail="Este exame já tem uma macroscopia registrada.")

    partes, cassetes, etiquetas = [], [], []
    for idx, dados_parte in enumerate(dados.partes):
        parte = ParteMacroscopiaPatologia(
            id=str(uuid.uuid4()), id_macroscopia=macro.id, ordinal=idx + 1,
            letra_identificacao=letra_fragmento(idx),
            descricao_estrutura=dados_parte.estrutura.strip(),
            quantidade_fragmentos=len(dados_parte.fragmentos),
        )
        session.add(parte); partes.append(parte)
    await session.flush()

    for parte, dados_parte in zip(partes, dados.partes):
        identificadores = identificadores_fragmentos(parte.letra_identificacao, len(dados_parte.fragmentos))
        for ident, frag in zip(identificadores, dados_parte.fragmentos):
            cid = str(uuid.uuid4())
            cassete = CassetePatologia(
                id=cid, id_exame=exame.id, id_parte_macroscopia=parte.id, identificador=ident,
                qr_code=gerar_qr_code("CASSETE", numero, identificador=cid),
                coloracao_padrao=frag.coloracao, status=S_AGUARDANDO_PROCESSAMENTO,
            )
            session.add(cassete); cassetes.append(cassete)
            etiquetas.append({"tipo": "CASSETE", "numero_solicitacao": numero, "codigo": ident, "qr_code": cassete.qr_code})

    # Todas as amostras do exame andam juntas. numero_cassetes_gerados não é
    # mais atribuível por frasco — a fonte única passa a ser
    # macroscopias.numero_cassetes.
    for amostra in amostras:
        anterior, amostra.status = amostra.status, S_PROCESSADO
        amostra.descricao_macroscopia = dados.descricao
        _mov(session, amostra=amostra, etapa="Macroscopia", anterior=anterior, novo=amostra.status, usuario=usuario)

    anterior, exame.status = exame.status, S_EM_PROCESSAMENTO
    exame.etapa_macroscopia = EM_CONCLUIDA
    exame.macroscopia_concluida_em = _now()
    _mov(session, exame=exame, etapa="Macroscopia", anterior=anterior, novo=exame.status,
         usuario=usuario, observacoes=f"{len(cassetes)} cassete(s) gerados")

    await session.commit()
    await session.refresh(macro)
    for amostra in amostras:
        await session.refresh(amostra)

    estrutura_por_parte = {p.id: p.descricao_estrutura for p in partes}
    return {
        "macroscopia": {
            "id": macro.id, "id_exame": macro.id_exame, "descricao": macro.descricao,
            "data_realizacao": macro.criado_em, "responsavel": macro.responsavel,
            "numero_cassetes": macro.numero_cassetes,
        },
        "frasco": _frasco(amostras[0]),
        "frascos": [_frasco(a) for a in amostras],
        "partes": [
            {"id": x.id, "id_macroscopia": x.id_macroscopia, "ordinal": x.ordinal,
             "letra_identificacao": x.letra_identificacao, "descricao_estrutura": x.descricao_estrutura,
             "quantidade_fragmentos": x.quantidade_fragmentos} for x in partes
        ],
        "cassetes": [_cassete(x, estrutura_por_parte.get(x.id_parte_macroscopia)) for x in cassetes],
        "etiquetas": etiquetas,
    }


async def listar_pendencias_processamento(session, limite: int | None = 500):
    """Cassetes aguardando processamento. O cassete pertence ao exame, então a
    cadeia de JOIN não passa mais por amostras."""
    stmt = (
        select(CassetePatologia, ExamePatologia, PacientePatologia)
        .join(ExamePatologia, CassetePatologia.id_exame == ExamePatologia.id)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(CassetePatologia.status == S_AGUARDANDO_PROCESSAMENTO)
        .order_by(CassetePatologia.criado_em, CassetePatologia.id)
    )
    if limite is not None:
        stmt = stmt.limit(limite)
    rows = (await session.execute(stmt)).all()
    # Não há mais um frasco único por cassete: o código exibido é o do exame.
    return [{"id":c.id,"letra_fragmento":c.identificador,"qr_code":c.qr_code,"status":c.status,"codigo_interno_frasco":e.numero_local,"numero_solicitacao":e.numero_local,"paciente_nome":p.nome,"data_criacao":c.criado_em} for c,e,p in rows]


async def iniciar_lote(session, dados, usuario, ip):
    cassetes = list((await session.execute(select(CassetePatologia).where(CassetePatologia.id.in_(dados.cassete_ids)))).scalars())
    if len(cassetes) != len(set(dados.cassete_ids)): raise HTTPException(status_code=404, detail="Cassete não encontrado.")
    if any(c.status != S_AGUARDANDO_PROCESSAMENTO for c in cassetes): raise HTTPException(status_code=409, detail="Todos os cassetes devem aguardar processamento.")
    lote=LoteProcessamentoPatologia(id=str(uuid.uuid4()),responsavel=usuario or dados.responsavel,status="Em Andamento",observacoes=dados.observacoes)
    session.add(lote)
    for c in cassetes:
        anterior,c.status=c.status,S_PROCESSAMENTO;c.id_lote_processamento=lote.id
        # Movimentação no exame: o cassete pertence ao exame, e isso elimina o
        # SELECT por cassete que existia aqui.
        _mov(session, exame=await session.get(ExamePatologia,c.id_exame), etapa="Processamento", anterior=anterior, novo=c.status, usuario=usuario, observacoes=f"Cassete {c.identificador} — lote {lote.id[:8]}")
    await session.commit();await session.refresh(lote)
    return {"lote":{"id":lote.id,"responsavel":lote.responsavel,"status":lote.status,"data_inicio":lote.iniciado_em,"data_fim":lote.concluido_em,"observacoes":lote.observacoes,"data_criacao":lote.iniciado_em},"cassetes":cassetes}


async def concluir_lote(session, id_lote, dados, usuario, ip):
    lote=await session.get(LoteProcessamentoPatologia,id_lote)
    if not lote: raise HTTPException(status_code=404,detail="Lote não encontrado.")
    if lote.status != "Em Andamento": raise HTTPException(status_code=409,detail=f"Lote já está {lote.status}.")
    cassetes=list((await session.execute(select(CassetePatologia).where(CassetePatologia.id_lote_processamento==id_lote))).scalars())
    if not cassetes: raise HTTPException(status_code=422,detail="Nenhum cassete associado a este lote.")
    blocos=[]; exames=set()
    for c in cassetes:
        if c.status != S_PROCESSAMENTO: raise HTTPException(status_code=409,detail="Cassete fora do processamento.")
        exame=await session.get(ExamePatologia,c.id_exame)
        codigo=f"{exame.numero_local or c.id_exame}-{c.identificador}"; bid=str(uuid.uuid4())
        b=BlocoParafinaPatologia(id=bid,id_cassete=c.id,id_lote_processamento=lote.id,codigo_bloco=codigo,qr_code=gerar_qr_code("BLOCO",exame.numero_local or codigo,identificador=bid),status=S_AGUARDANDO_CORTE)
        session.add(b); blocos.append(b); anterior,c.status=c.status,S_PROCESSADO
        _mov(session,exame=exame,etapa="Processamento",anterior=anterior,novo=c.status,usuario=usuario,observacoes=f"Bloco {codigo} gerado"); exames.add(exame.id)
    for eid in exames:
        exame=await session.get(ExamePatologia,eid)
        if exame.status == S_EM_PROCESSAMENTO:
            anterior,exame.status=exame.status,S_EM_MICRO;_mov(session,exame=exame,etapa="Processamento",anterior=anterior,novo=exame.status,usuario=usuario)
    lote.status="Concluído";lote.concluido_em=_now()
    if dados.observacoes:lote.observacoes=" | ".join(x for x in [lote.observacoes,dados.observacoes] if x)
    await session.commit();await session.refresh(lote)
    return {"lote":{"id":lote.id,"responsavel":lote.responsavel,"status":lote.status,"data_inicio":lote.iniciado_em,"data_fim":lote.concluido_em,"observacoes":lote.observacoes,"data_criacao":lote.iniciado_em},"blocos":[{"id":b.id,"id_cassete":b.id_cassete,"id_lote":b.id_lote_processamento,"codigo_bloco":b.codigo_bloco,"qr_code":b.qr_code,"status":b.status,"data_criacao":b.criado_em,"criado_por":usuario} for b in blocos]}


async def listar_blocos_pendentes(session, codigo_bloco: Optional[str] = None, limite: int | None = 500):
    stmt=(select(BlocoParafinaPatologia,CassetePatologia,ExamePatologia,PacientePatologia)
        .join(CassetePatologia,BlocoParafinaPatologia.id_cassete==CassetePatologia.id)
        .join(ExamePatologia,CassetePatologia.id_exame==ExamePatologia.id)
        .join(CasoPatologia,ExamePatologia.id_caso==CasoPatologia.id)
        .join(PacientePatologia,CasoPatologia.id_paciente==PacientePatologia.id)
        .where(BlocoParafinaPatologia.status==S_AGUARDANDO_CORTE)
        .order_by(BlocoParafinaPatologia.criado_em,BlocoParafinaPatologia.id))
    if codigo_bloco:
        stmt=stmt.where(BlocoParafinaPatologia.codigo_bloco==codigo_bloco)
    if limite is not None:
        stmt=stmt.limit(limite)
    rows=(await session.execute(stmt)).all()
    return [{"id":b.id,"codigo_bloco":b.codigo_bloco,"status":b.status,"letra_fragmento":c.identificador,"numero_solicitacao":e.numero_local,"paciente_nome":p.nome,"data_criacao":b.criado_em} for b,c,e,p in rows]


async def buscar_bloco(session,codigo_bloco):
    if not codigo_bloco: raise HTTPException(status_code=400,detail="Informe codigo_bloco.")
    # Filtra no SQL; antes varria a lista inteira em Python.
    result=await listar_blocos_pendentes(session,codigo_bloco=codigo_bloco)
    if not result: raise HTTPException(status_code=404,detail="Nenhum bloco encontrado.")
    return result


async def gerar_laminas(session,id_bloco,dados,usuario,ip):
    bloco=await session.get(BlocoParafinaPatologia,id_bloco)
    if not bloco:raise HTTPException(status_code=404,detail="Bloco não encontrado.")
    if bloco.status != S_AGUARDANDO_CORTE:raise HTTPException(status_code=409,detail="Bloco precisa estar Aguardando Corte.")
    existentes=(await session.execute(select(func.max(LaminaPatologia.numero_lamina)).where(LaminaPatologia.id_bloco==id_bloco))).scalar_one() or 0
    laminas=[]
    for i in range(dados.quantidade):
        n=existentes+i+1;lid=str(uuid.uuid4());lm=LaminaPatologia(id=lid,id_bloco=bloco.id,numero_lamina=n,codigo_lamina=f"{bloco.codigo_bloco}-L{n}",qr_code=gerar_qr_code("LAMINA",bloco.codigo_bloco,identificador=lid),coloracao=dados.coloracao)
        session.add(lm);laminas.append(lm)
    anterior,bloco.status=bloco.status,S_AGUARDANDO_MICRO
    await session.commit();await session.refresh(bloco)
    return {"bloco_id":bloco.id,"codigo_bloco":bloco.codigo_bloco,"laminas":[{"id":lm.id,"id_bloco":lm.id_bloco,"numero_lamina":lm.numero_lamina,"codigo_lamina":lm.codigo_lamina,"qr_code":lm.qr_code,"coloracao":lm.coloracao,"status":lm.status,"data_criacao":lm.criado_em,"criado_por":usuario} for lm in laminas],"etiquetas":[{"tipo":"LAMINA","numero_solicitacao":bloco.codigo_bloco,"codigo":lm.codigo_lamina,"qr_code":lm.qr_code} for lm in laminas]}


async def listar_laminas(session,id_bloco):
    if not await session.get(BlocoParafinaPatologia,id_bloco):raise HTTPException(status_code=404,detail="Bloco não encontrado.")
    return [{"id":x.id,"id_bloco":x.id_bloco,"numero_lamina":x.numero_lamina,"codigo_lamina":x.codigo_lamina,"qr_code":x.qr_code,"coloracao":x.coloracao,"status":x.status,"data_criacao":x.criado_em,"criado_por":None} for x in (await session.execute(select(LaminaPatologia).where(LaminaPatologia.id_bloco==id_bloco).order_by(LaminaPatologia.numero_lamina))).scalars()]


async def listar_pendencias_microscopia(session):
    rows=(await session.execute(select(ExamePatologia,PacientePatologia).join(CasoPatologia,ExamePatologia.id_caso==CasoPatologia.id).join(PacientePatologia,CasoPatologia.id_paciente==PacientePatologia.id).where(ExamePatologia.status.in_([S_EM_MICRO,S_REVISAO])))).all()
    return [{"id":e.id,"numero_solicitacao":e.numero_local,"status":e.status,"data_recebimento":e.data_recebimento,"tipo_exame":None,"paciente_nome":p.nome} for e,p in rows]


async def registrar_laudo(session,id_exame,acao,responsavel,laudo,observacoes,usuario,ip):
    destino={"liberar":S_LIBERADO,"revisao":S_REVISAO,"complemento":S_EM_PROCESSAMENTO}.get(acao)
    if not destino:raise HTTPException(status_code=400,detail="Ação inválida.")
    exame=await session.get(ExamePatologia,id_exame)
    if not exame:raise HTTPException(status_code=404,detail="Exame não encontrado.")
    if exame.status != destino:
        anterior,exame.status=exame.status,destino
        if destino==S_LIBERADO:exame.data_conclusao=_now()
        _mov(session,exame=exame,etapa="Microscopia",anterior=anterior,novo=destino,usuario=responsavel or usuario,observacoes=" | ".join(x for x in [laudo,observacoes] if x) or None)
        await session.commit()
    return {"exame_id":exame.id,"numero_solicitacao":exame.numero_local,"status":exame.status}


async def listar_historico(session, id_exame=None, id_frasco=None, id_cassete=None):
    if not any([id_exame, id_frasco, id_cassete]):
        raise HTTPException(status_code=400, detail="Informe id_exame, id_frasco ou id_cassete.")
    stmt = select(MovimentacaoPatologia)
    if id_exame:
        stmt = stmt.where(MovimentacaoPatologia.id_exame == id_exame)
    if id_frasco:
        stmt = stmt.where(MovimentacaoPatologia.id_amostra == id_frasco)
    if id_cassete:
        cassete = await session.get(CassetePatologia, id_cassete)
        if not cassete:
            return []
        # O cassete pertence ao exame; o histórico dele é o do exame.
        stmt = stmt.where(MovimentacaoPatologia.id_exame == cassete.id_exame)
    registros = (await session.execute(stmt.order_by(MovimentacaoPatologia.criado_em.desc()))).scalars()
    return [{"id":m.id,"id_exame":m.id_exame,"id_frasco":m.id_amostra,"id_cassete":None,
             "etapa":m.etapa,"status_anterior":m.status_anterior,"status_novo":m.status_novo,
             "usuario_responsavel":m.usuario_responsavel,"timestamp_transicao":m.criado_em,
             "ip_origem":None,"observacoes":m.observacoes} for m in registros]
