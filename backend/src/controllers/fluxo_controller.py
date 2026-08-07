"""Triagem, dashboard, macroscopia e histórico.

A fila e a posse são delegadas a ``services.etapas``, o mesmo motor usado por
Processamento, Microscopia e Congelamento. Aqui ficam apenas as regras próprias
da recepção e da macroscopia.
"""

import uuid
from datetime import timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
    EtapaExamePatologia, ExamePatologia, LaminaPatologia, LaudoMicroscopiaPatologia,
    MacroscopiaPatologia, MovimentacaoPatologia, PacientePatologia,
    ParteMacroscopiaPatologia, TipoExamePatologia,
)
from ..models.usuarios import PerfilUsuario
from ..schemas.paginacao import montar_pagina
from ..services import etapas
from ..services.fluxo_comum import (
    S_AGUARDANDO_MACRO, S_AGUARDANDO_PROCESSAMENTO, S_EM_MACRO, S_EM_PROCESSAMENTO,
    S_EM_CONGELAMENTO, S_PROCESSADO, S_RECEPCAO, TOTAL_FRASCOS, agora, atrasado,
    etapa_exibida, proximo_numero_exame, registrar_movimentacao, status_da_etapa,
)


# Reexportados: os testes manuais e os controllers vizinhos importam daqui.
_now = agora
_atrasado = atrasado
_mov = registrar_movimentacao
_TOTAL_FRASCOS = TOTAL_FRASCOS

TIPO_CONGELAMENTO = "CONG"


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


_proximo_numero = proximo_numero_exame


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
        data_solicitacao=agora().date(), situacao_importacao="PRONTO")
    exame = ExamePatologia(id=str(uuid.uuid4()), id_caso=caso.id, id_tipo_exame=tipo.id,
        numero_local=numero, sequencial=sequencial, ano=ano, semestre=semestre,
        status=S_RECEPCAO, numero_exame_aghu=dados.numero_exame_aghu, tipo_peca=dados.tipo_peca,
        topografia=dados.topografia, data_recebimento=agora(), criado_por=usuario)
    session.add_all([caso, exame])
    try:
        await session.flush()
    except IntegrityError:
        # UNIQUE em numero_local: duas recepções pegaram o mesmo sequencial.
        # Falhar aqui é melhor que gravar um código duplicado.
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Outro exame foi registrado ao mesmo tempo. Tente novamente.",
        )
    amostra_id = str(uuid.uuid4())
    amostra = AmostraPatologia(id=amostra_id, id_caso=caso.id, id_exame=exame.id, numero_amostra=1,
        codigo_solicitacao=numero, codigo_interno=gerar_codigo_interno_frasco(numero),
        qr_code=gerar_qr_code("FRASCO", numero, identificador=amostra_id), status=S_AGUARDANDO_MACRO,
        criado_por=usuario)
    session.add(amostra)
    registrar_movimentacao(session, exame=exame, etapa="Triagem", anterior=None, novo=S_RECEPCAO,
                           usuario=usuario, observacoes="Exame criado na recepção")

    # A congelação não passa pela macroscopia: é análise intraoperatória e entra
    # direto na fila do próprio setor.
    if codigo == TIPO_CONGELAMENTO:
        exame.status = S_EM_CONGELAMENTO
        amostra.status = S_EM_CONGELAMENTO
        await etapas.abrir(session, exame.id, etapas.CONGELAMENTO, usuario=usuario)
    else:
        # O exame entra na FILA da macroscopia; "Em Macroscopia" só quando alguém
        # assumir. Antes isso era avançado aqui e a base inteira ficou num status
        # que não refletia trabalho nenhum.
        exame.status = S_AGUARDANDO_MACRO
        await etapas.abrir(session, exame.id, etapas.MACROSCOPIA, usuario=usuario)
    registrar_movimentacao(session, amostra=amostra, etapa="Triagem", anterior=None, novo=amostra.status,
                           usuario=usuario, observacoes="Amostra registrada")

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
    """Visão unificada do caso, usada pelo dashboard e pelo cabeçalho de todas
    as estações. Preenche a cadeia inteira a partir do banco — antes as seções
    de macroscopia, processamento e microscopia vinham sempre nulas."""
    exame = await obter_exame(session, id_exame)
    row = (await session.execute(
        select(ExamePatologia, CasoPatologia, PacientePatologia)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(ExamePatologia.id == id_exame)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Exame não encontrado.")
    e, _, p = row
    amostras = list((await session.execute(
        select(AmostraPatologia).where(AmostraPatologia.id_exame == id_exame)
        .order_by(AmostraPatologia.numero_amostra)
    )).scalars())

    macro = (await session.execute(
        select(MacroscopiaPatologia).where(MacroscopiaPatologia.id_exame == id_exame)
    )).scalar_one_or_none()

    cassetes = list((await session.execute(
        select(CassetePatologia, ParteMacroscopiaPatologia)
        .outerjoin(ParteMacroscopiaPatologia, CassetePatologia.id_parte_macroscopia == ParteMacroscopiaPatologia.id)
        .where(CassetePatologia.id_exame == id_exame)
        .order_by(CassetePatologia.identificador)
    )).all())

    blocos = list((await session.execute(
        select(BlocoParafinaPatologia, CassetePatologia)
        .join(CassetePatologia, BlocoParafinaPatologia.id_cassete == CassetePatologia.id)
        .where(CassetePatologia.id_exame == id_exame)
        .order_by(BlocoParafinaPatologia.codigo_bloco)
    )).all())

    laminas = list((await session.execute(
        select(LaminaPatologia, BlocoParafinaPatologia.codigo_bloco)
        .join(BlocoParafinaPatologia, LaminaPatologia.id_bloco == BlocoParafinaPatologia.id)
        .join(CassetePatologia, BlocoParafinaPatologia.id_cassete == CassetePatologia.id)
        .where(CassetePatologia.id_exame == id_exame)
        .order_by(LaminaPatologia.codigo_lamina)
    )).all())

    laudo = (await session.execute(
        select(LaudoMicroscopiaPatologia)
        .where(LaudoMicroscopiaPatologia.id_exame == id_exame)
        .order_by(LaudoMicroscopiaPatologia.ciclo.desc())
        .limit(1)
    )).scalar_one_or_none()

    return {
        "codigo_local": e.numero_local, "etapa_atual": etapa_exibida(e.status), "urgente": False,
        "aghu": {
            "nome_paciente": p.nome,
            "prontuario": p.prontuario or p.cns or p.cpf or "—",
            "idade": 0, "origem": p.origem or "—",
            "tipo_material": e.tipo_peca or "",
            "tipo_exame": exame["tipo_exame"],
            "numero_solicitacao_aghu": e.numero_exame_aghu or "—",
            "procedimento_sus": "—",
            "indicacao_clinica": f"Topografia: {e.topografia}" if e.topografia else "—",
        },
        "recepcao": {
            "data_entrada": e.data_recebimento, "quantidade_frascos": len(amostras),
            "descricao_fisica": e.tipo_peca or "—",
            "frascos_ids": [a.codigo_interno or a.codigo_solicitacao for a in amostras],
            "responsavel": e.criado_por or "—",
        } if amostras else None,
        "macroscopia": {
            "data_macro": macro.criado_em, "responsavel": macro.responsavel or "—",
            "descricao": macro.descricao, "sobra_material": False,
            "cassetes": [
                {"id": c.identificador, "estrutura": (parte.descricao_estrutura if parte else "—"),
                 "coloracao": c.coloracao_padrao}
                for c, parte in cassetes
            ],
        } if macro else None,
        "processamento": {
            "blocos": [
                {"id": b.codigo_bloco, "cassete_id": c.identificador,
                 "responsavel": "—", "data_inclusao": b.criado_em}
                for b, c in blocos
            ],
            "laminas": [
                {"id": lm.codigo_lamina, "bloco_id": codigo_bloco, "coloracao": lm.coloracao}
                for lm, codigo_bloco in laminas
            ],
            "data_liberacao": None, "responsavel": "—",
        } if blocos else None,
        "microscopia": {
            "data_recebimento": laudo.criado_em,
            "data_liberacao_laudo": laudo.liberado_em,
            "responsavel": laudo.patologista or laudo.residente or "—",
            "laudo": laudo.laudo_previo,
            "conclusao": laudo.conclusao,
        } if laudo else None,
    }


# =====================================================================
# Dashboard
# =====================================================================

# Etapa aberta do exame, como LATERAL com LIMIT 1: garante 1:1 mesmo se uma
# inconsistência criasse duas etapas ativas, e assim a paginação não infla.
_ETAPA_ATIVA = (
    select(
        EtapaExamePatologia.etapa.label("etapa_atual"),
        EtapaExamePatologia.status.label("situacao_etapa"),
        EtapaExamePatologia.subetapa.label("subetapa"),
        EtapaExamePatologia.responsavel_nome.label("responsavel_nome"),
        EtapaExamePatologia.assumido_em.label("assumido_em"),
    )
    .where(
        EtapaExamePatologia.id_exame == ExamePatologia.id,
        EtapaExamePatologia.status != etapas.CONCLUIDA,
    )
    .order_by(EtapaExamePatologia.criado_em.desc(), EtapaExamePatologia.id.desc())
    .limit(1)
    .lateral("etapa_ativa")
)


class _Ativa:
    """Empacota as colunas da LATERAL — todas NULL quando não há etapa aberta."""

    __slots__ = ("etapa_atual", "situacao_etapa", "subetapa", "responsavel_nome", "assumido_em")

    def __init__(self, etapa_atual=None, situacao_etapa=None, subetapa=None, responsavel_nome=None, assumido_em=None):
        self.etapa_atual = etapa_atual
        self.situacao_etapa = situacao_etapa
        self.subetapa = subetapa
        self.responsavel_nome = responsavel_nome
        self.assumido_em = assumido_em


def _linha_dashboard(exame, paciente_nome, total_frascos, ativa, referencia) -> dict:
    entrada = exame.data_recebimento or exame.criado_em
    return {
        "id": exame.id,
        "solicitacao": exame.numero_local or "PENDENTE",
        "codigo_aghu": exame.numero_exame_aghu,
        "paciente": paciente_nome,
        "etapa": etapa_exibida(exame.status),
        "data_entrada": entrada,
        "atrasado": atrasado(entrada, referencia),
        "total_frascos": total_frascos or 0,
        # Agora vale para qualquer estação, não só a macroscopia: quem está com
        # o exame neste momento e desde quando.
        "data_inicio_trabalho": ativa.assumido_em if ativa else None,
        "responsavel_macroscopia_nome": ativa.responsavel_nome if ativa else None,
        "etapa_ativa": ativa.etapa_atual if ativa else None,
        "situacao_etapa": ativa.situacao_etapa if ativa else None,
    }


def _clausulas_dashboard(
    etapa: Optional[str] = None,
    codigo_aghu: Optional[str] = None,
    codigo_interno: Optional[str] = None,
    nome_paciente: Optional[str] = None,
    busca: Optional[str] = None,
) -> list:
    """Filtros do dashboard, compartilhados entre a página e o COUNT.

    ``busca`` é o campo único (usado pelas filas); os demais são os filtros
    dedicados da barra de pesquisa do dashboard. Combinam-se com AND.
    """
    clausulas = []
    if etapa:
        # "Em Macroscopia" precisa alcançar quem ainda está "Aguardando
        # Macroscopia" — é a mesma casa do fluxo.
        clausulas.append(ExamePatologia.status.in_(status_da_etapa(etapa)))
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


def _base_dashboard(clausulas: list):
    return (
        select(ExamePatologia, PacientePatologia.nome, TOTAL_FRASCOS, _ETAPA_ATIVA)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .outerjoin(_ETAPA_ATIVA, true())
        .where(*clausulas)
        .order_by(ExamePatologia.criado_em.desc(), ExamePatologia.id.desc())
    )


async def listar_dashboard(
    session: AsyncSession,
    limite: int | None = None,
    etapa: Optional[str] = None,
    codigo_aghu: Optional[str] = None,
    codigo_interno: Optional[str] = None,
    nome_paciente: Optional[str] = None,
):
    """Rota antiga, mantida por compatibilidade. Prefira ``listar_dashboard_paginado``."""
    stmt = _base_dashboard(_clausulas_dashboard(etapa, codigo_aghu, codigo_interno, nome_paciente))
    if limite is not None:
        stmt = stmt.limit(limite)
    rows = (await session.execute(stmt)).all()
    referencia = agora()
    return [_linha_dashboard(e, nome, n, _Ativa(*ativa_cols), referencia) for e, nome, n, *ativa_cols in rows]


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

    base = _base_dashboard(clausulas).limit(por_pagina).offset((pagina - 1) * por_pagina)
    contagem = (
        select(func.count(ExamePatologia.id))
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(*clausulas)
    )

    rows = (await session.execute(base)).all()
    total = (await session.execute(contagem)).scalar_one()
    referencia = agora()
    itens = [_linha_dashboard(e, nome, n, _Ativa(*ativa_cols), referencia) for e, nome, n, *ativa_cols in rows]
    return montar_pagina(itens, total, pagina, por_pagina)


async def resumo_dashboard(session: AsyncSession) -> dict:
    """Contagens calculadas no banco; evita transferir toda a fila ao dashboard."""
    referencia = agora()
    entrada = func.coalesce(ExamePatologia.data_recebimento, ExamePatologia.criado_em)
    linhas = (await session.execute(
        select(ExamePatologia.status, func.count(ExamePatologia.id))
        .group_by(ExamePatologia.status)
    )).all()
    # Soma "Aguardando X" dentro de "Em X": o card da etapa tem de bater com o
    # que a tabela mostra quando se clica nele.
    por_status: dict[str, int] = {}
    for status, total in linhas:
        por_status[etapa_exibida(status)] = por_status.get(etapa_exibida(status), 0) + total
    atrasados = (await session.execute(select(func.count(ExamePatologia.id)).where(entrada < referencia - timedelta(days=20)))).scalar_one()
    alerta = (await session.execute(select(func.count(ExamePatologia.id)).where(
        entrada >= referencia - timedelta(days=20), entrada < referencia - timedelta(days=15)
    ))).scalar_one()
    # Contagem por etapa aberta: o status global não distingue "aguardando" de
    # "assumido", que é justamente o que a operação quer ver.
    por_etapa = {
        f"{etapa}:{status}": total
        for etapa, status, total in (await session.execute(
            select(EtapaExamePatologia.etapa, EtapaExamePatologia.status, func.count(EtapaExamePatologia.id))
            .where(EtapaExamePatologia.status != etapas.CONCLUIDA)
            .group_by(EtapaExamePatologia.etapa, EtapaExamePatologia.status)
        )).all()
    }
    return {
        "por_status": por_status,
        "por_etapa": por_etapa,
        "atrasados": atrasados,
        "alerta": alerta,
    }


async def listar_pendencias_recepcao(session: AsyncSession):
    return await _listar_amostras(session, [S_RECEPCAO])


async def listar_pendencias_macroscopia(session: AsyncSession, limite: int | None = None):
    """Fila antiga por frasco. Substituída por ``GET /api/macroscopia/fila``."""
    return await _listar_amostras(session, [S_AGUARDANDO_MACRO, S_EM_MACRO], limite)


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
        registrar_movimentacao(session, amostra=amostra, etapa="Triagem", anterior=anterior, novo=amostra.status, usuario=usuario)
    if exame.status == S_RECEPCAO:
        # Vai para a FILA da macroscopia; "Em Macroscopia" só quando assumido.
        anterior, exame.status = exame.status, S_AGUARDANDO_MACRO
        await etapas.abrir(session, exame.id, etapas.MACROSCOPIA, usuario=usuario)
        registrar_movimentacao(session, exame=exame, etapa="Macroscopia", anterior=anterior, novo=exame.status, usuario=usuario)
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
# Fila e posse da macroscopia — sobre o motor genérico
# =====================================================================


async def listar_fila_macroscopia(
    session: AsyncSession,
    usuario: Optional[str],
    filtro: str = "aguardando",
    busca: Optional[str] = None,
    pagina: int = 1,
    por_pagina: int = 25,
) -> dict:
    return await etapas.pagina_fila(
        session, etapas.MACROSCOPIA, usuario,
        filtro=filtro, busca=busca, pagina=pagina, por_pagina=por_pagina,
    )


async def assumir_exame(session: AsyncSession, id_exame: str, usuario: Optional[str], nome_usuario: Optional[str]) -> dict:
    registro = await etapas.assumir(session, id_exame, etapas.MACROSCOPIA, usuario, nome_usuario)
    # As amostras acompanham o exame — os frascos andam juntos.
    exame = await session.get(ExamePatologia, id_exame)
    if exame.status != S_EM_MACRO:
        exame.status = S_EM_MACRO
    for amostra in (await session.execute(
        select(AmostraPatologia).where(
            AmostraPatologia.id_exame == id_exame, AmostraPatologia.status == S_AGUARDANDO_MACRO
        )
    )).scalars():
        amostra.status = S_EM_MACRO
    await session.commit()
    return await etapas.linha_exame(session, id_exame, etapas.MACROSCOPIA)


async def repassar_exame(session: AsyncSession, id_exame: str, dados, usuario: Optional[str], eh_admin: bool = False) -> dict:
    await etapas.repassar(session, id_exame, etapas.MACROSCOPIA, dados, usuario, eh_admin)
    return await etapas.linha_exame(session, id_exame, etapas.MACROSCOPIA)


async def liberar_exame(session: AsyncSession, id_exame: str, usuario: Optional[str], eh_admin: bool = False) -> dict:
    await etapas.liberar(session, id_exame, etapas.MACROSCOPIA, usuario, eh_admin)
    exame = await session.get(ExamePatologia, id_exame)
    if exame.status == S_EM_MACRO:
        exame.status = S_AGUARDANDO_MACRO
    for amostra in (await session.execute(
        select(AmostraPatologia).where(
            AmostraPatologia.id_exame == id_exame, AmostraPatologia.status == S_EM_MACRO
        )
    )).scalars():
        amostra.status = S_AGUARDANDO_MACRO
    await session.commit()
    return await etapas.linha_exame(session, id_exame, etapas.MACROSCOPIA)


async def obter_workspace_macroscopia(session: AsyncSession, id_exame: str, usuario: Optional[str], eh_admin: bool = False) -> dict:
    """Tudo que a estação precisa para abrir um exame."""
    registro = await etapas.exigir_etapa(session, id_exame, etapas.MACROSCOPIA)

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

    return {
        "exame": await etapas.linha_exame(session, id_exame, etapas.MACROSCOPIA),
        "posse": etapas.posse(registro, usuario, eh_admin),
        "historico_etapas": etapas.historico_etapas(await etapas.etapas_do_exame(session, id_exame)),
        "frascos": [_frasco(a) for a in amostras],
        "macroscopia": {
            "id": macro.id, "id_exame": macro.id_exame, "descricao": macro.descricao,
            "data_realizacao": macro.criado_em, "responsavel": macro.responsavel,
            "numero_cassetes": macro.numero_cassetes,
        } if macro else None,
        "partes": partes,
        "cassetes": cassetes,
    }


async def listar_usuarios_candidatos(
    session: AsyncSession, busca: Optional[str] = None, limite: int = 30, etapa: Optional[str] = None
) -> list[dict]:
    """Candidatos a receber um repasse.

    ``perfis_usuarios`` só ganha linha quando alguém faz login, então uma lista
    baseada só nela nasce praticamente vazia. Completamos com os usernames que
    já aparecem no fluxo, marcados como ``historico``.

    ``etapa`` prioriza quem já trabalhou nela — enquanto o HC não definir os
    grupos do AD por perfil, é a melhor aproximação de "usuários compatíveis
    com o setor" que o banco permite.
    """
    encontrados: dict[str, dict] = {}

    if etapa:
        stmt = (
            select(EtapaExamePatologia.responsavel_username, EtapaExamePatologia.responsavel_nome)
            .where(
                EtapaExamePatologia.etapa == etapa,
                EtapaExamePatologia.responsavel_username.is_not(None),
            )
            .distinct()
            .limit(limite)
        )
        if busca:
            alvo = f"%{busca.strip()}%"
            stmt = stmt.where(or_(
                EtapaExamePatologia.responsavel_username.ilike(alvo),
                EtapaExamePatologia.responsavel_nome.ilike(alvo),
            ))
        for username, nome in (await session.execute(stmt)).all():
            if username:
                encontrados[username] = {
                    "username": username, "nome_exibicao": nome, "email": None,
                    "departamento": None, "origem": "etapa",
                }

    stmt = select(PerfilUsuario).where(PerfilUsuario.ativo.is_(True))
    if busca:
        alvo = f"%{busca.strip()}%"
        stmt = stmt.where(or_(PerfilUsuario.username.ilike(alvo), PerfilUsuario.nome_exibicao.ilike(alvo)))
    for perfil in (await session.execute(stmt.limit(limite))).scalars():
        encontrados.setdefault(perfil.username, {
            "username": perfil.username, "nome_exibicao": perfil.nome_exibicao,
            "email": perfil.email, "departamento": perfil.departamento, "origem": "perfil",
        })

    colunas = (
        EtapaExamePatologia.responsavel_username,
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
        _, exame_origem, _ = await _contexto_amostra(session, dados.id_frasco)
        id_exame = exame_origem.id

    exame = await session.get(ExamePatologia, id_exame)
    if not exame:
        raise HTTPException(status_code=404, detail="Exame não encontrado.")

    # Sem esta guarda, "assumir" não significaria nada.
    await etapas.exigir_posse(session, id_exame, etapas.MACROSCOPIA, usuario, eh_admin)

    amostras = list((await session.execute(
        select(AmostraPatologia)
        .where(AmostraPatologia.id_exame == id_exame)
        .order_by(AmostraPatologia.numero_amostra)
    )).scalars())
    if not amostras:
        raise HTTPException(status_code=422, detail="O exame não tem frascos registrados.")

    registro = await etapas.exigir_etapa(session, id_exame, etapas.MACROSCOPIA)
    numero = exame.numero_local or amostras[0].codigo_solicitacao
    macro = MacroscopiaPatologia(
        id=str(uuid.uuid4()), id_exame=exame.id, descricao=dados.descricao,
        responsavel=registro.responsavel_username or usuario,
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
        registrar_movimentacao(session, amostra=amostra, etapa="Macroscopia", anterior=anterior, novo=amostra.status, usuario=usuario)

    exame.status = S_EM_PROCESSAMENTO
    # Conclui a macroscopia e abre o processamento já na fila, sem dono: quem
    # cliva não herda o exame na estação seguinte.
    await etapas.transferir(
        session, id_exame, etapas.MACROSCOPIA, etapas.PROCESSAMENTO, usuario,
        observacoes=f"{len(cassetes)} cassete(s) gerados",
    )

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
