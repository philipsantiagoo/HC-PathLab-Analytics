"""Processamento Técnico: fila por exame, posse e regras de conclusão.

Antes a tela era orientada ao cassete: buscava um código, incluía e o botão
"Enviar para Microscopia" só mexia no estado local do navegador. Um exame podia
avançar com metade dos cassetes ainda na bancada. Agora a unidade é o exame, a
posse vale para todos os seus cassetes e a saída para a Microscopia é validada
no servidor.
"""

import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..helpers.identificacao import gerar_qr_code
from ..models.patologia import (
    BlocoParafinaPatologia, CassetePatologia, CasoPatologia, EtapaExamePatologia,
    ExamePatologia, LaminaPatologia, LoteProcessamentoPatologia, PacientePatologia,
    ParteMacroscopiaPatologia,
)
from ..services import etapas
from ..services.fluxo_comum import (
    S_AGUARDANDO_CORTE, S_AGUARDANDO_MICRO, S_AGUARDANDO_PROCESSAMENTO, S_CORTADO,
    S_EM_MICRO, S_PROCESSADO, S_PROCESSAMENTO, agora, registrar_movimentacao,
)


# --- Métricas do exame, como subqueries escalares correlacionadas --------
# Com JOIN + GROUP BY o LIMIT da página passaria a ser aplicado depois de
# agregar todos os cassetes da base; aqui cada uma roda por linha da página.
def _contar_cassetes(*condicoes):
    return (
        select(func.count(CassetePatologia.id))
        .where(CassetePatologia.id_exame == ExamePatologia.id, *condicoes)
        .correlate(ExamePatologia)
        .scalar_subquery()
    )


TOTAL_CASSETES = _contar_cassetes().label("total_cassetes")
CASSETES_PROCESSADOS = _contar_cassetes(CassetePatologia.status == S_PROCESSADO).label("cassetes_processados")

TOTAL_BLOCOS = (
    select(func.count(BlocoParafinaPatologia.id))
    .select_from(BlocoParafinaPatologia)
    .join(CassetePatologia, BlocoParafinaPatologia.id_cassete == CassetePatologia.id)
    .where(CassetePatologia.id_exame == ExamePatologia.id)
    .correlate(ExamePatologia)
    .scalar_subquery()
    .label("total_blocos")
)

TOTAL_LAMINAS = (
    select(func.count(LaminaPatologia.id))
    .select_from(LaminaPatologia)
    .join(BlocoParafinaPatologia, LaminaPatologia.id_bloco == BlocoParafinaPatologia.id)
    .join(CassetePatologia, BlocoParafinaPatologia.id_cassete == CassetePatologia.id)
    .where(CassetePatologia.id_exame == ExamePatologia.id)
    .correlate(ExamePatologia)
    .scalar_subquery()
    .label("total_laminas")
)

EXTRAS_FILA = (TOTAL_CASSETES, CASSETES_PROCESSADOS, TOTAL_BLOCOS, TOTAL_LAMINAS)


def _enriquecer(item: dict, registro, exame, valores) -> None:
    total, processados, blocos, laminas = valores
    item.update({
        "total_cassetes": total or 0,
        "cassetes_processados": processados or 0,
        "total_blocos": blocos or 0,
        "total_laminas": laminas or 0,
        "cassetes_pendentes": max(0, (total or 0) - (processados or 0)),
    })


async def listar_fila(
    session: AsyncSession,
    usuario: Optional[str],
    filtro: str = "aguardando",
    busca: Optional[str] = None,
    pagina: int = 1,
    por_pagina: int = 25,
) -> dict:
    return await etapas.pagina_fila(
        session, etapas.PROCESSAMENTO, usuario,
        filtro=filtro, busca=busca, pagina=pagina, por_pagina=por_pagina,
        extras=EXTRAS_FILA, enriquecer=_enriquecer,
    )


async def _linha(session: AsyncSession, id_exame: str) -> dict:
    return await etapas.linha_exame(
        session, id_exame, etapas.PROCESSAMENTO, extras=EXTRAS_FILA, enriquecer=_enriquecer,
    )


async def assumir(session: AsyncSession, id_exame: str, usuario, nome_usuario) -> dict:
    await etapas.assumir(session, id_exame, etapas.PROCESSAMENTO, usuario, nome_usuario)
    return await _linha(session, id_exame)


async def repassar(session: AsyncSession, id_exame: str, dados, usuario, eh_admin: bool = False) -> dict:
    await etapas.repassar(session, id_exame, etapas.PROCESSAMENTO, dados, usuario, eh_admin)
    return await _linha(session, id_exame)


async def liberar(session: AsyncSession, id_exame: str, usuario, eh_admin: bool = False) -> dict:
    await etapas.liberar(session, id_exame, etapas.PROCESSAMENTO, usuario, eh_admin)
    return await _linha(session, id_exame)


# =====================================================================
# Workspace do exame
# =====================================================================


async def _cassetes_do_exame(session: AsyncSession, id_exame: str) -> list[dict]:
    """Cassetes com bloco e lâminas — uma consulta, sem N+1 por cassete."""
    linhas = (await session.execute(
        select(CassetePatologia, ParteMacroscopiaPatologia, BlocoParafinaPatologia)
        .outerjoin(ParteMacroscopiaPatologia, CassetePatologia.id_parte_macroscopia == ParteMacroscopiaPatologia.id)
        .outerjoin(BlocoParafinaPatologia, BlocoParafinaPatologia.id_cassete == CassetePatologia.id)
        .where(CassetePatologia.id_exame == id_exame)
        .order_by(CassetePatologia.identificador)
    )).all()

    ids_blocos = [b.id for _, _, b in linhas if b is not None]
    laminas_por_bloco: dict[str, list[dict]] = {}
    if ids_blocos:
        for lamina in (await session.execute(
            select(LaminaPatologia)
            .where(LaminaPatologia.id_bloco.in_(ids_blocos))
            .order_by(LaminaPatologia.numero_lamina)
        )).scalars():
            laminas_por_bloco.setdefault(lamina.id_bloco, []).append({
                "id": lamina.id, "codigo_lamina": lamina.codigo_lamina,
                "numero_lamina": lamina.numero_lamina, "coloracao": lamina.coloracao,
                "qr_code": lamina.qr_code, "status": lamina.status,
            })

    return [
        {
            "id": c.id, "identificador": c.identificador, "qr_code": c.qr_code,
            "status": c.status, "coloracao_padrao": c.coloracao_padrao,
            "descricao_estrutura": parte.descricao_estrutura if parte else None,
            "id_lote_processamento": c.id_lote_processamento,
            "bloco": {
                "id": b.id, "codigo_bloco": b.codigo_bloco, "qr_code": b.qr_code, "status": b.status,
            } if b else None,
            "laminas": laminas_por_bloco.get(b.id, []) if b else [],
        }
        for c, parte, b in linhas
    ]


def _pendencias(cassetes: list[dict]) -> list[str]:
    """O que ainda impede o envio à Microscopia, em linguagem de bancada."""
    faltas = []
    sem_processar = [c["identificador"] for c in cassetes if c["status"] != S_PROCESSADO]
    if sem_processar:
        faltas.append(f"Cassete(s) ainda não processado(s): {', '.join(sem_processar)}.")
    sem_bloco = [c["identificador"] for c in cassetes if c["bloco"] is None]
    if sem_bloco:
        faltas.append(f"Sem bloco gerado: {', '.join(sem_bloco)}.")
    sem_lamina = [c["identificador"] for c in cassetes if c["bloco"] and not c["laminas"]]
    if sem_lamina:
        faltas.append(f"Bloco sem lâmina: {', '.join(sem_lamina)}.")
    if not cassetes:
        faltas.append("O exame não tem cassetes — verifique a macroscopia.")
    return faltas


async def obter_workspace(
    session: AsyncSession, id_exame: str, usuario: Optional[str], eh_admin: bool = False
) -> dict:
    registro = await etapas.exigir_etapa(session, id_exame, etapas.PROCESSAMENTO)
    cassetes = await _cassetes_do_exame(session, id_exame)
    faltas = _pendencias(cassetes)
    posse = etapas.posse(registro, usuario, eh_admin)

    lotes = list((await session.execute(
        select(LoteProcessamentoPatologia)
        .join(CassetePatologia, CassetePatologia.id_lote_processamento == LoteProcessamentoPatologia.id)
        .where(CassetePatologia.id_exame == id_exame)
        .distinct()
        .order_by(LoteProcessamentoPatologia.iniciado_em.desc())
    )).scalars())

    return {
        "exame": await _linha(session, id_exame),
        "posse": posse,
        "historico_etapas": etapas.historico_etapas(await etapas.etapas_do_exame(session, id_exame)),
        "cassetes": cassetes,
        "lotes": [
            {"id": l.id, "responsavel": l.responsavel, "status": l.status,
             "observacoes": l.observacoes, "iniciado_em": l.iniciado_em, "concluido_em": l.concluido_em}
            for l in lotes
        ],
        "progresso": {
            "total_cassetes": len(cassetes),
            "cassetes_processados": sum(1 for c in cassetes if c["status"] == S_PROCESSADO),
            "total_blocos": sum(1 for c in cassetes if c["bloco"]),
            "total_laminas": sum(len(c["laminas"]) for c in cassetes),
        },
        "pendencias_conclusao": faltas,
        # O botão só aparece quando o servidor concorda; a validação real está
        # em ``concluir``, porque esconder botão não é controle de acesso.
        "pode_concluir": not faltas and posse["pode_executar"],
    }


# =====================================================================
# Execução: lotes, blocos e lâminas
# =====================================================================


async def _exigir_posse_dos_cassetes(
    session: AsyncSession, cassetes, usuario: Optional[str], eh_admin: bool
) -> set[str]:
    """Todo cassete pertence a um exame, e é do exame que se tem a posse."""
    ids_exames = {c.id_exame for c in cassetes}
    for id_exame in ids_exames:
        await etapas.exigir_posse(session, id_exame, etapas.PROCESSAMENTO, usuario, eh_admin)
    return ids_exames


async def iniciar_lote(session, dados, usuario, ip, eh_admin: bool = False):
    cassetes = list((await session.execute(
        select(CassetePatologia).where(CassetePatologia.id.in_(dados.cassete_ids))
    )).scalars())
    if len(cassetes) != len(set(dados.cassete_ids)):
        raise HTTPException(status_code=404, detail="Cassete não encontrado.")
    if any(c.status != S_AGUARDANDO_PROCESSAMENTO for c in cassetes):
        raise HTTPException(status_code=409, detail="Todos os cassetes devem aguardar processamento.")
    await _exigir_posse_dos_cassetes(session, cassetes, usuario, eh_admin)

    lote = LoteProcessamentoPatologia(
        id=str(uuid.uuid4()), responsavel=usuario or dados.responsavel,
        status="Em Andamento", observacoes=dados.observacoes,
    )
    session.add(lote)
    exames = {c.id_exame: await session.get(ExamePatologia, c.id_exame) for c in cassetes}
    for c in cassetes:
        anterior, c.status = c.status, S_PROCESSAMENTO
        c.id_lote_processamento = lote.id
        registrar_movimentacao(
            session, exame=exames[c.id_exame], etapa="Processamento", anterior=anterior,
            novo=c.status, usuario=usuario,
            observacoes=f"Cassete {c.identificador} — lote {lote.id[:8]}",
        )
    await session.commit()
    await session.refresh(lote)
    return {
        "lote": {"id": lote.id, "responsavel": lote.responsavel, "status": lote.status,
                 "data_inicio": lote.iniciado_em, "data_fim": lote.concluido_em,
                 "observacoes": lote.observacoes, "data_criacao": lote.iniciado_em},
        "cassetes": cassetes,
    }


async def concluir_lote(session, id_lote, dados, usuario, ip, eh_admin: bool = False):
    """Gera um bloco por cassete. Não avança mais o exame: quem decide a saída
    para a Microscopia é ``concluir_exame``, depois de conferir tudo."""
    lote = await session.get(LoteProcessamentoPatologia, id_lote)
    if not lote:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")
    if lote.status != "Em Andamento":
        raise HTTPException(status_code=409, detail=f"Lote já está {lote.status}.")
    cassetes = list((await session.execute(
        select(CassetePatologia).where(CassetePatologia.id_lote_processamento == id_lote)
    )).scalars())
    if not cassetes:
        raise HTTPException(status_code=422, detail="Nenhum cassete associado a este lote.")
    await _exigir_posse_dos_cassetes(session, cassetes, usuario, eh_admin)

    exames = {c.id_exame: await session.get(ExamePatologia, c.id_exame) for c in cassetes}
    blocos = []
    for c in cassetes:
        if c.status != S_PROCESSAMENTO:
            raise HTTPException(status_code=409, detail="Cassete fora do processamento.")
        exame = exames[c.id_exame]
        codigo = f"{exame.numero_local or c.id_exame}-{c.identificador}"
        bid = str(uuid.uuid4())
        bloco = BlocoParafinaPatologia(
            id=bid, id_cassete=c.id, id_lote_processamento=lote.id, codigo_bloco=codigo,
            qr_code=gerar_qr_code("BLOCO", exame.numero_local or codigo, identificador=bid),
            status=S_AGUARDANDO_CORTE,
        )
        session.add(bloco)
        blocos.append(bloco)
        anterior, c.status = c.status, S_PROCESSADO
        registrar_movimentacao(
            session, exame=exame, etapa="Processamento", anterior=anterior, novo=c.status,
            usuario=usuario, observacoes=f"Bloco {codigo} gerado",
        )

    lote.status = "Concluído"
    lote.concluido_em = agora()
    if dados.observacoes:
        lote.observacoes = " | ".join(x for x in [lote.observacoes, dados.observacoes] if x)
    await session.commit()
    await session.refresh(lote)
    return {
        "lote": {"id": lote.id, "responsavel": lote.responsavel, "status": lote.status,
                 "data_inicio": lote.iniciado_em, "data_fim": lote.concluido_em,
                 "observacoes": lote.observacoes, "data_criacao": lote.iniciado_em},
        "blocos": [
            {"id": b.id, "id_cassete": b.id_cassete, "id_lote": b.id_lote_processamento,
             "codigo_bloco": b.codigo_bloco, "qr_code": b.qr_code, "status": b.status,
             "data_criacao": b.criado_em, "criado_por": usuario} for b in blocos
        ],
    }


async def gerar_laminas(session, id_bloco, dados, usuario, ip, eh_admin: bool = False):
    bloco = await session.get(BlocoParafinaPatologia, id_bloco)
    if not bloco:
        raise HTTPException(status_code=404, detail="Bloco não encontrado.")
    cassete = await session.get(CassetePatologia, bloco.id_cassete)
    await etapas.exigir_posse(session, cassete.id_exame, etapas.PROCESSAMENTO, usuario, eh_admin)
    if bloco.status not in (S_AGUARDANDO_CORTE, S_AGUARDANDO_MICRO, S_CORTADO):
        raise HTTPException(status_code=409, detail="Bloco não está disponível para corte.")

    existentes = (await session.execute(
        select(func.max(LaminaPatologia.numero_lamina)).where(LaminaPatologia.id_bloco == id_bloco)
    )).scalar_one() or 0
    coloracoes = dados.coloracoes or [dados.coloracao] * dados.quantidade
    if len(coloracoes) != dados.quantidade:
        raise HTTPException(status_code=400, detail="A lista de colorações não bate com a quantidade.")

    laminas = []
    for i, coloracao in enumerate(coloracoes):
        n = existentes + i + 1
        lid = str(uuid.uuid4())
        lamina = LaminaPatologia(
            id=lid, id_bloco=bloco.id, numero_lamina=n,
            codigo_lamina=f"{bloco.codigo_bloco}-L{n}",
            qr_code=gerar_qr_code("LAMINA", bloco.codigo_bloco, identificador=lid),
            coloracao=coloracao,
        )
        session.add(lamina)
        laminas.append(lamina)
    bloco.status = S_AGUARDANDO_MICRO
    exame = await session.get(ExamePatologia, cassete.id_exame)
    registrar_movimentacao(
        session, exame=exame, etapa="Processamento", anterior=S_AGUARDANDO_CORTE,
        novo=S_AGUARDANDO_MICRO, usuario=usuario,
        observacoes=f"{len(laminas)} lâmina(s) do bloco {bloco.codigo_bloco}",
    )
    await session.commit()
    await session.refresh(bloco)
    return {
        "bloco_id": bloco.id, "codigo_bloco": bloco.codigo_bloco,
        "laminas": [
            {"id": lm.id, "id_bloco": lm.id_bloco, "numero_lamina": lm.numero_lamina,
             "codigo_lamina": lm.codigo_lamina, "qr_code": lm.qr_code, "coloracao": lm.coloracao,
             "status": lm.status, "data_criacao": lm.criado_em, "criado_por": usuario} for lm in laminas
        ],
        "etiquetas": [
            {"tipo": "LAMINA", "numero_solicitacao": bloco.codigo_bloco,
             "codigo": lm.codigo_lamina, "qr_code": lm.qr_code} for lm in laminas
        ],
    }


async def concluir_exame(session: AsyncSession, id_exame: str, usuario, eh_admin: bool = False) -> dict:
    """Envia o exame à Microscopia — a única porta de saída do Processamento.

    O antigo "Enviar para Microscopia" era um botão de frontend que só mexia
    numa store local; um lote concluído já bastava para o exame avançar. Aqui a
    conferência é feita no servidor e o exame só sai quando tudo está pronto.
    """
    await etapas.exigir_posse(session, id_exame, etapas.PROCESSAMENTO, usuario, eh_admin)
    cassetes = await _cassetes_do_exame(session, id_exame)
    faltas = _pendencias(cassetes)
    if faltas:
        raise HTTPException(status_code=409, detail=" ".join(faltas))

    exame = await session.get(ExamePatologia, id_exame)
    exame.status = S_EM_MICRO
    # A microscopia começa aguardando o laudo prévio do residente.
    await etapas.transferir(
        session, id_exame, etapas.PROCESSAMENTO, etapas.MICROSCOPIA, usuario,
        subetapa=etapas.SUB_LAUDO_PREVIO,
        observacoes=f"{sum(len(c['laminas']) for c in cassetes)} lâmina(s) enviadas à microscopia",
    )
    await session.commit()
    return {
        "id_exame": id_exame,
        "numero_solicitacao": exame.numero_local,
        "status": exame.status,
        "total_laminas": sum(len(c["laminas"]) for c in cassetes),
    }


# =====================================================================
# Rotas antigas por cassete/bloco (leitura do QR Code)
# =====================================================================


async def listar_pendencias_processamento(session, limite: int | None = 500):
    """Cassetes aguardando processamento. Mantida para a leitura direta do QR
    Code; a tela usa ``listar_fila``."""
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
    return [{"id": c.id, "id_exame": c.id_exame, "letra_fragmento": c.identificador, "qr_code": c.qr_code,
             "status": c.status, "codigo_interno_frasco": e.numero_local, "numero_solicitacao": e.numero_local,
             "paciente_nome": p.nome, "data_criacao": c.criado_em} for c, e, p in rows]


async def buscar_cassete(session, codigo: str) -> dict:
    """Resolve um código de cassete para o exame dono dele.

    A leitura do QR Code passa a ser uma porta de entrada para o exame, não uma
    unidade de trabalho isolada.
    """
    alvo = (codigo or "").strip()
    if not alvo:
        raise HTTPException(status_code=400, detail="Informe o código do cassete.")
    linha = (await session.execute(
        select(CassetePatologia, ExamePatologia)
        .join(ExamePatologia, CassetePatologia.id_exame == ExamePatologia.id)
        .where(CassetePatologia.qr_code == alvo)
        .limit(1)
    )).first()
    if not linha:
        # Formato legível "HP-0004/26.1-A": o número da solicitação contém "-",
        # então casamos pelo sufixo em vez de adivinhar onde cortar.
        linha = (await session.execute(
            select(CassetePatologia, ExamePatologia)
            .join(ExamePatologia, CassetePatologia.id_exame == ExamePatologia.id)
            .where(func.concat(ExamePatologia.numero_local, "-", CassetePatologia.identificador) == alvo)
            .limit(1)
        )).first()
    if not linha:
        # Só o número da solicitação também abre o exame.
        exame = (await session.execute(
            select(ExamePatologia).where(ExamePatologia.numero_local == alvo).limit(1)
        )).scalar_one_or_none()
        if not exame:
            raise HTTPException(status_code=404, detail="Nenhum cassete ou exame com esse código.")
        return {"id_exame": exame.id, "id_cassete": None, "numero_solicitacao": exame.numero_local}
    cassete, exame = linha
    return {"id_exame": exame.id, "id_cassete": cassete.id, "numero_solicitacao": exame.numero_local}


async def listar_blocos_pendentes(session, codigo_bloco: Optional[str] = None, limite: int | None = 500):
    stmt = (
        select(BlocoParafinaPatologia, CassetePatologia, ExamePatologia, PacientePatologia)
        .join(CassetePatologia, BlocoParafinaPatologia.id_cassete == CassetePatologia.id)
        .join(ExamePatologia, CassetePatologia.id_exame == ExamePatologia.id)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(BlocoParafinaPatologia.status == S_AGUARDANDO_CORTE)
        .order_by(BlocoParafinaPatologia.criado_em, BlocoParafinaPatologia.id)
    )
    if codigo_bloco:
        stmt = stmt.where(BlocoParafinaPatologia.codigo_bloco == codigo_bloco)
    if limite is not None:
        stmt = stmt.limit(limite)
    rows = (await session.execute(stmt)).all()
    return [{"id": b.id, "id_exame": e.id, "codigo_bloco": b.codigo_bloco, "status": b.status,
             "letra_fragmento": c.identificador, "numero_solicitacao": e.numero_local,
             "paciente_nome": p.nome, "data_criacao": b.criado_em} for b, c, e, p in rows]


async def buscar_bloco(session, codigo_bloco):
    if not codigo_bloco:
        raise HTTPException(status_code=400, detail="Informe codigo_bloco.")
    resultado = await listar_blocos_pendentes(session, codigo_bloco=codigo_bloco)
    if not resultado:
        raise HTTPException(status_code=404, detail="Nenhum bloco encontrado.")
    return resultado


async def listar_laminas(session, id_bloco):
    if not await session.get(BlocoParafinaPatologia, id_bloco):
        raise HTTPException(status_code=404, detail="Bloco não encontrado.")
    return [{"id": x.id, "id_bloco": x.id_bloco, "numero_lamina": x.numero_lamina,
             "codigo_lamina": x.codigo_lamina, "qr_code": x.qr_code, "coloracao": x.coloracao,
             "status": x.status, "data_criacao": x.criado_em, "criado_por": None}
            for x in (await session.execute(
                select(LaminaPatologia).where(LaminaPatologia.id_bloco == id_bloco)
                .order_by(LaminaPatologia.numero_lamina)
            )).scalars()]
