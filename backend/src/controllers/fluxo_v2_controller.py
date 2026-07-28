"""Fluxo operacional apoiado exclusivamente em ``pathlab_v2``.

As respostas preservam o contrato HTTP atual para que a troca de schema não
exija uma segunda migração do frontend.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..helpers.identificacao import (
    TIPOS_EXAME_VALIDOS,
    gerar_codigo_interno_frasco,
    gerar_qr_code,
    identificadores_fragmentos,
    letra_fragmento,
    normalizar_tipo_exame,
)
from ..models.patologia_v2 import (
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


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
        raise HTTPException(status_code=422, detail="Tipo de exame não configurado no catálogo v2.")
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
    exame.status = "Em Macroscopia"
    _mov(session, exame=exame, etapa="Macroscopia", anterior=S_RECEPCAO, novo=exame.status, usuario=usuario, observacoes="Código local gerado")
    await session.commit()
    await session.refresh(amostra)
    return {"exame": _exame(exame), "frasco": _frasco(amostra), "etiqueta": {"tipo":"FRASCO", "numero_solicitacao":numero, "codigo":amostra.codigo_interno, "qr_code":amostra.qr_code}}


def _exame(exame: ExamePatologia) -> dict:
    return {"id": exame.id, "numero_solicitacao": exame.numero_local or "", "tipo_exame": "",
            "id_paciente": "", "numero_exame_aghu": exame.numero_exame_aghu,
            "tipo_peca": exame.tipo_peca, "topografia": exame.topografia,
            "status": exame.status, "data_recebimento": exame.data_recebimento}


async def listar_exames(session: AsyncSession):
    rows = (await session.execute(select(ExamePatologia, TipoExamePatologia).join(TipoExamePatologia).order_by(ExamePatologia.criado_em.desc()))).all()
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


async def listar_dashboard(session: AsyncSession, limite: int = 50):
    rows = (await session.execute(select(ExamePatologia, PacientePatologia).join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id).join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id).order_by(ExamePatologia.criado_em.desc()).limit(limite))).all()
    hoje = _now()
    return [{"id": e.id, "solicitacao": e.numero_local or "PENDENTE", "paciente": p.nome,
             "etapa": e.status, "data_entrada": e.data_recebimento or e.criado_em,
             "atrasado": bool((hoje - (e.data_recebimento or e.criado_em)).days >= 20)} for e, p in rows]


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


async def listar_pendencias_macroscopia(session: AsyncSession, limite: int = 50):
    return await _listar_amostras(session, [S_AGUARDANDO_MACRO], limite)


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
        anterior, exame.status = exame.status, "Em Macroscopia"
        _mov(session, exame=exame, etapa="Macroscopia", anterior=anterior, novo=exame.status, usuario=usuario)
    await session.commit(); await session.refresh(amostra)
    return _frasco(amostra)


async def iniciar_macroscopia(session, id_frasco: str, usuario, ip):
    amostra, exame, _ = await _contexto_amostra(session, id_frasco)
    if amostra.status != S_AGUARDANDO_MACRO: raise HTTPException(status_code=409, detail=f"Amostra não está aguardando macroscopia: {amostra.status}.")
    anterior, amostra.status = amostra.status, S_EM_MACRO
    _mov(session, amostra=amostra, etapa="Macroscopia", anterior=anterior, novo=amostra.status, usuario=usuario)
    if exame.status != "Em Macroscopia":
        anterior, exame.status = exame.status, "Em Macroscopia"; _mov(session, exame=exame, etapa="Macroscopia", anterior=anterior, novo=exame.status, usuario=usuario)
    await session.commit(); await session.refresh(amostra)
    return _frasco(amostra)


async def obter_etiqueta_frasco(session, id_frasco: str):
    amostra, exame, _ = await _contexto_amostra(session, id_frasco)
    return {"tipo":"FRASCO", "numero_solicitacao":exame.numero_local or amostra.codigo_solicitacao, "codigo":amostra.codigo_interno or "", "qr_code":amostra.qr_code or ""}


async def registrar_macroscopia(session, dados, usuario, ip):
    amostra, exame, _ = await _contexto_amostra(session, dados.id_frasco)
    if amostra.status != S_EM_MACRO: raise HTTPException(status_code=409, detail="A amostra precisa estar Em Macroscopia.")
    macro = MacroscopiaPatologia(id=str(uuid.uuid4()), id_amostra=amostra.id, descricao=dados.descricao, responsavel=usuario, numero_cassetes=sum(len(x.fragmentos) for x in dados.partes))
    session.add(macro); await session.flush()
    partes, cassetes, etiquetas = [], [], []
    numero = exame.numero_local or amostra.codigo_solicitacao
    for idx, dados_parte in enumerate(dados.partes):
        parte = ParteMacroscopiaPatologia(id=str(uuid.uuid4()), id_macroscopia=macro.id, ordinal=idx+1, letra_identificacao=letra_fragmento(idx), descricao_estrutura=dados_parte.estrutura.strip(), quantidade_fragmentos=len(dados_parte.fragmentos))
        session.add(parte); partes.append(parte)
    await session.flush()
    for parte, dados_parte in zip(partes, dados.partes):
        for ident, frag in zip(identificadores_fragmentos(parte.letra_identificacao, len(dados_parte.fragmentos)), dados_parte.fragmentos):
            cid=str(uuid.uuid4()); cassete=CassetePatologia(id=cid, id_amostra=amostra.id, id_parte_macroscopia=parte.id, identificador=ident, qr_code=gerar_qr_code("CASSETE",numero,identificador=cid), coloracao_padrao=frag.coloracao, status=S_AGUARDANDO_PROCESSAMENTO)
            session.add(cassete); cassetes.append(cassete); etiquetas.append({"tipo":"CASSETE","numero_solicitacao":numero,"codigo":ident,"qr_code":cassete.qr_code})
    anterior, amostra.status = amostra.status, S_PROCESSADO; amostra.descricao_macroscopia=dados.descricao; amostra.numero_cassetes_gerados=len(cassetes)
    _mov(session, amostra=amostra, etapa="Macroscopia", anterior=anterior, novo=amostra.status, usuario=usuario)
    anterior, exame.status = exame.status, S_EM_PROCESSAMENTO; _mov(session, exame=exame, etapa="Macroscopia", anterior=anterior, novo=exame.status, usuario=usuario)
    await session.commit(); await session.refresh(macro); await session.refresh(amostra)
    return {"macroscopia":{"id":macro.id,"id_frasco":amostra.id,"descricao":macro.descricao,"data_realizacao":macro.criado_em,"responsavel":macro.responsavel,"numero_cassetes":macro.numero_cassetes},"frasco":_frasco(amostra),"partes":[{"id":x.id,"id_macroscopia":x.id_macroscopia,"ordinal":x.ordinal,"letra_identificacao":x.letra_identificacao,"descricao_estrutura":x.descricao_estrutura,"quantidade_fragmentos":x.quantidade_fragmentos} for x in partes],"cassetes":[{"id":x.id,"id_frasco":x.id_amostra,"id_parte_macroscopia":x.id_parte_macroscopia,"letra_fragmento":x.identificador,"qr_code":x.qr_code,"descricao_estrutura":None,"observacoes_macroscopia":None,"coloracao_padrao":x.coloracao_padrao,"status":x.status} for x in cassetes],"etiquetas":etiquetas}


async def listar_pendencias_processamento(session):
    rows = (await session.execute(select(CassetePatologia, AmostraPatologia, ExamePatologia, PacientePatologia).join(AmostraPatologia, CassetePatologia.id_amostra == AmostraPatologia.id).join(ExamePatologia, AmostraPatologia.id_exame == ExamePatologia.id).join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id).join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id).where(CassetePatologia.status == S_AGUARDANDO_PROCESSAMENTO))).all()
    return [{"id":c.id,"letra_fragmento":c.identificador,"qr_code":c.qr_code,"status":c.status,"codigo_interno_frasco":a.codigo_interno,"numero_solicitacao":e.numero_local,"paciente_nome":p.nome,"data_criacao":c.criado_em} for c,a,e,p in rows]


async def iniciar_lote(session, dados, usuario, ip):
    cassetes = list((await session.execute(select(CassetePatologia).where(CassetePatologia.id.in_(dados.cassete_ids)))).scalars())
    if len(cassetes) != len(set(dados.cassete_ids)): raise HTTPException(status_code=404, detail="Cassete não encontrado.")
    if any(c.status != S_AGUARDANDO_PROCESSAMENTO for c in cassetes): raise HTTPException(status_code=409, detail="Todos os cassetes devem aguardar processamento.")
    lote=LoteProcessamentoPatologia(id=str(uuid.uuid4()),responsavel=usuario or dados.responsavel,status="Em Andamento",observacoes=dados.observacoes)
    session.add(lote)
    for c in cassetes:
        anterior,c.status=c.status,S_PROCESSAMENTO;c.id_lote_processamento=lote.id
        _mov(session, amostra=await session.get(AmostraPatologia,c.id_amostra), etapa="Processamento", anterior=anterior, novo=c.status, usuario=usuario, observacoes=f"Lote {lote.id[:8]}")
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
        amostra=await session.get(AmostraPatologia,c.id_amostra); exame=await session.get(ExamePatologia,amostra.id_exame)
        codigo=f"{exame.numero_local or amostra.codigo_solicitacao}-{c.identificador}"; bid=str(uuid.uuid4())
        b=BlocoParafinaPatologia(id=bid,id_cassete=c.id,id_lote_processamento=lote.id,codigo_bloco=codigo,qr_code=gerar_qr_code("BLOCO",exame.numero_local or codigo,identificador=bid),status=S_AGUARDANDO_CORTE)
        session.add(b); blocos.append(b); anterior,c.status=c.status,S_PROCESSADO
        _mov(session,amostra=amostra,etapa="Processamento",anterior=anterior,novo=c.status,usuario=usuario,observacoes=f"Bloco {codigo} gerado"); exames.add(exame.id)
    for eid in exames:
        exame=await session.get(ExamePatologia,eid)
        if exame.status == S_EM_PROCESSAMENTO:
            anterior,exame.status=exame.status,S_EM_MICRO;_mov(session,exame=exame,etapa="Processamento",anterior=anterior,novo=exame.status,usuario=usuario)
    lote.status="Concluído";lote.concluido_em=_now()
    if dados.observacoes:lote.observacoes=" | ".join(x for x in [lote.observacoes,dados.observacoes] if x)
    await session.commit();await session.refresh(lote)
    return {"lote":{"id":lote.id,"responsavel":lote.responsavel,"status":lote.status,"data_inicio":lote.iniciado_em,"data_fim":lote.concluido_em,"observacoes":lote.observacoes,"data_criacao":lote.iniciado_em},"blocos":[{"id":b.id,"id_cassete":b.id_cassete,"id_lote":b.id_lote_processamento,"codigo_bloco":b.codigo_bloco,"qr_code":b.qr_code,"status":b.status,"data_criacao":b.criado_em,"criado_por":usuario} for b in blocos]}


async def listar_blocos_pendentes(session):
    rows=(await session.execute(select(BlocoParafinaPatologia,CassetePatologia,AmostraPatologia,ExamePatologia,PacientePatologia).join(CassetePatologia,BlocoParafinaPatologia.id_cassete==CassetePatologia.id).join(AmostraPatologia,CassetePatologia.id_amostra==AmostraPatologia.id).join(ExamePatologia,AmostraPatologia.id_exame==ExamePatologia.id).join(CasoPatologia,ExamePatologia.id_caso==CasoPatologia.id).join(PacientePatologia,CasoPatologia.id_paciente==PacientePatologia.id).where(BlocoParafinaPatologia.status==S_AGUARDANDO_CORTE))).all()
    return [{"id":b.id,"codigo_bloco":b.codigo_bloco,"status":b.status,"letra_fragmento":c.identificador,"numero_solicitacao":e.numero_local,"paciente_nome":p.nome,"data_criacao":b.criado_em} for b,c,a,e,p in rows]


async def buscar_bloco(session,codigo_bloco):
    if not codigo_bloco: raise HTTPException(status_code=400,detail="Informe codigo_bloco.")
    rows=await listar_blocos_pendentes(session);result=[r for r in rows if r["codigo_bloco"]==codigo_bloco]
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
        stmt = stmt.where(MovimentacaoPatologia.id_amostra == cassete.id_amostra)
    registros = (await session.execute(stmt.order_by(MovimentacaoPatologia.criado_em.desc()))).scalars()
    return [{"id":m.id,"id_exame":m.id_exame,"id_frasco":m.id_amostra,"id_cassete":None,
             "etapa":m.etapa,"status_anterior":m.status_anterior,"status_novo":m.status_novo,
             "usuario_responsavel":m.usuario_responsavel,"timestamp_transicao":m.criado_em,
             "ip_origem":None,"observacoes":m.observacoes} for m in registros]
