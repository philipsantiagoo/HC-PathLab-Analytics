"""Microscopia: fila por exame, posse e passagem residente → patologista.

A tela tinha um botão "Atuando como: Residente | Patologista" e um ``select``
com nomes fixos: qualquer pessoa assinava como qualquer uma. Agora o papel
esperado é uma subetapa do exame, o responsável vem do token e a passagem de um
papel para o outro encerra a posse — quem escreve o laudo prévio não é quem o
revisa.
"""

import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.patologia import (
    BlocoParafinaPatologia, CassetePatologia, CasoPatologia, EtapaExamePatologia,
    ExamePatologia, LaminaPatologia, LaudoMicroscopiaPatologia, PacientePatologia,
)
from ..services import etapas
from ..services.fluxo_comum import (
    S_EM_MICRO, S_EM_PROCESSAMENTO, S_LIBERADO, S_REVISAO, agora, registrar_movimentacao,
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

EXTRAS_FILA = (TOTAL_LAMINAS,)

# Papel esperado por subetapa — exibido na fila para ninguém abrir um exame que
# não é da sua vez.
PAPEL_DA_SUBETAPA = {
    etapas.SUB_LAUDO_PREVIO: "Residente",
    etapas.SUB_REVISAO: "Médico Patologista",
}


def _enriquecer(item: dict, registro, exame, valores) -> None:
    (laminas,) = valores
    item["total_laminas"] = laminas or 0
    item["papel_esperado"] = PAPEL_DA_SUBETAPA.get(registro.subetapa, "Médico Patologista")


async def _laudo(session: AsyncSession, id_exame: str, ciclo: int) -> Optional[LaudoMicroscopiaPatologia]:
    return (await session.execute(
        select(LaudoMicroscopiaPatologia).where(
            LaudoMicroscopiaPatologia.id_exame == id_exame,
            LaudoMicroscopiaPatologia.ciclo == ciclo,
        )
    )).scalar_one_or_none()


async def _garantir_laudo(session: AsyncSession, id_exame: str, ciclo: int) -> LaudoMicroscopiaPatologia:
    laudo = await _laudo(session, id_exame, ciclo)
    if laudo is None:
        laudo = LaudoMicroscopiaPatologia(id=str(uuid.uuid4()), id_exame=id_exame, ciclo=ciclo)
        session.add(laudo)
        await session.flush()
    return laudo


# =====================================================================
# Fila
# =====================================================================


async def listar_fila(
    session: AsyncSession,
    usuario: Optional[str],
    filtro: str = "aguardando",
    busca: Optional[str] = None,
    subetapa: Optional[str] = None,
    pagina: int = 1,
    por_pagina: int = 25,
) -> dict:
    pagina_resposta = await etapas.pagina_fila(
        session, etapas.MICROSCOPIA, usuario,
        filtro=filtro, busca=busca, subetapa=subetapa, pagina=pagina, por_pagina=por_pagina,
        extras=EXTRAS_FILA, enriquecer=_enriquecer,
    )
    # A microscopia tem duas filas de espera distintas — laudo prévio e revisão
    # —, então os quatro contadores genéricos não bastam para os badges.
    pagina_resposta["contadores"].update(await _contadores_por_subetapa(session, busca))
    return pagina_resposta


async def _contadores_por_subetapa(session: AsyncSession, busca: Optional[str]) -> dict:
    # Os joins de caso/paciente são necessários porque a busca única inclui o
    # nome do paciente; ambos são 1:1 e não alteram a contagem.
    condicoes = etapas.clausulas(etapas.MICROSCOPIA, "aguardando", None, busca)
    linhas = (await session.execute(
        select(EtapaExamePatologia.subetapa, func.count(EtapaExamePatologia.id))
        .join(ExamePatologia, EtapaExamePatologia.id_exame == ExamePatologia.id)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
        .where(*condicoes)
        .group_by(EtapaExamePatologia.subetapa)
    )).all()
    por_subetapa = {sub: total for sub, total in linhas}
    return {
        "laudo_previo": por_subetapa.get(etapas.SUB_LAUDO_PREVIO, 0),
        "revisao": por_subetapa.get(etapas.SUB_REVISAO, 0),
    }


async def _linha(session: AsyncSession, id_exame: str) -> dict:
    return await etapas.linha_exame(
        session, id_exame, etapas.MICROSCOPIA, extras=EXTRAS_FILA, enriquecer=_enriquecer,
    )


async def assumir(session: AsyncSession, id_exame: str, usuario, nome_usuario) -> dict:
    await etapas.assumir(session, id_exame, etapas.MICROSCOPIA, usuario, nome_usuario)
    return await _linha(session, id_exame)


async def repassar(session: AsyncSession, id_exame: str, dados, usuario, eh_admin: bool = False) -> dict:
    await etapas.repassar(session, id_exame, etapas.MICROSCOPIA, dados, usuario, eh_admin)
    return await _linha(session, id_exame)


async def liberar(session: AsyncSession, id_exame: str, usuario, eh_admin: bool = False) -> dict:
    await etapas.liberar(session, id_exame, etapas.MICROSCOPIA, usuario, eh_admin)
    return await _linha(session, id_exame)


# =====================================================================
# Workspace
# =====================================================================


async def obter_workspace(
    session: AsyncSession, id_exame: str, usuario: Optional[str], eh_admin: bool = False
) -> dict:
    registro = await etapas.exigir_etapa(session, id_exame, etapas.MICROSCOPIA)
    laudo = await _laudo(session, id_exame, registro.ciclo)

    laminas = (await session.execute(
        select(LaminaPatologia, BlocoParafinaPatologia.codigo_bloco, CassetePatologia.identificador)
        .join(BlocoParafinaPatologia, LaminaPatologia.id_bloco == BlocoParafinaPatologia.id)
        .join(CassetePatologia, BlocoParafinaPatologia.id_cassete == CassetePatologia.id)
        .where(CassetePatologia.id_exame == id_exame)
        .order_by(LaminaPatologia.codigo_lamina)
    )).all()

    posse = etapas.posse(registro, usuario, eh_admin)
    return {
        "exame": await _linha(session, id_exame),
        "posse": posse,
        "historico_etapas": etapas.historico_etapas(await etapas.etapas_do_exame(session, id_exame)),
        "subetapa": registro.subetapa,
        "papel_esperado": PAPEL_DA_SUBETAPA.get(registro.subetapa, "Médico Patologista"),
        "laminas": [
            {"id": lm.id, "codigo_lamina": lm.codigo_lamina, "coloracao": lm.coloracao,
             "status": lm.status, "qr_code": lm.qr_code, "codigo_bloco": codigo_bloco,
             "cassete": identificador}
            for lm, codigo_bloco, identificador in laminas
        ],
        "laudo": {
            "laudo_previo": laudo.laudo_previo, "residente": laudo.residente,
            "laudo_previo_em": laudo.laudo_previo_em, "conclusao": laudo.conclusao,
            "patologista": laudo.patologista, "liberado_em": laudo.liberado_em,
            "ciclo": laudo.ciclo,
        } if laudo else None,
        "pode_registrar_laudo_previo": posse["pode_executar"] and registro.subetapa == etapas.SUB_LAUDO_PREVIO,
        "pode_revisar": posse["pode_executar"] and registro.subetapa == etapas.SUB_REVISAO,
    }


# =====================================================================
# Ações da etapa
# =====================================================================


async def registrar_laudo_previo(
    session: AsyncSession, id_exame: str, texto: str, usuario: Optional[str],
    nome_usuario: Optional[str], eh_admin: bool = False,
) -> dict:
    """Residente conclui o laudo prévio e devolve o exame à fila do patologista."""
    registro = await etapas.exigir_posse(session, id_exame, etapas.MICROSCOPIA, usuario, eh_admin)
    if registro.subetapa != etapas.SUB_LAUDO_PREVIO:
        raise HTTPException(status_code=409, detail="Este exame já está aguardando revisão do patologista.")
    if not texto.strip():
        raise HTTPException(status_code=400, detail="Escreva o laudo prévio.")

    laudo = await _garantir_laudo(session, id_exame, registro.ciclo)
    laudo.laudo_previo = texto.strip()
    # O responsável é sempre o usuário autenticado — não um nome escolhido num
    # campo de seleção, que qualquer pessoa poderia usar para assinar por outra.
    laudo.residente = nome_usuario or usuario
    laudo.laudo_previo_em = agora()

    exame = await session.get(ExamePatologia, id_exame)
    exame.status = S_REVISAO
    await etapas.mudar_subetapa(
        session, id_exame, etapas.MICROSCOPIA, etapas.SUB_REVISAO, usuario,
        encerrar_posse=True, observacoes="Laudo prévio encaminhado para revisão",
    )
    await session.commit()
    return await _linha(session, id_exame)


async def liberar_laudo(
    session: AsyncSession, id_exame: str, conclusao: Optional[str], usuario: Optional[str],
    nome_usuario: Optional[str], eh_admin: bool = False,
) -> dict:
    """Patologista aprova e encerra o exame."""
    registro = await etapas.exigir_posse(session, id_exame, etapas.MICROSCOPIA, usuario, eh_admin)
    if registro.subetapa != etapas.SUB_REVISAO:
        raise HTTPException(status_code=409, detail="O laudo prévio ainda não foi encaminhado para revisão.")

    laudo = await _garantir_laudo(session, id_exame, registro.ciclo)
    laudo.conclusao = (conclusao or "").strip() or laudo.laudo_previo
    laudo.patologista = nome_usuario or usuario
    laudo.liberado_em = agora()

    exame = await session.get(ExamePatologia, id_exame)
    exame.status = S_LIBERADO
    exame.data_conclusao = agora()
    await etapas.concluir(
        session, id_exame, etapas.MICROSCOPIA, usuario, observacoes="Laudo liberado",
    )
    await session.commit()
    return {"id_exame": id_exame, "numero_solicitacao": exame.numero_local, "status": exame.status}


async def solicitar_complemento(
    session: AsyncSession, id_exame: str, marcadores: str, usuario: Optional[str], eh_admin: bool = False,
) -> dict:
    """IHQ/complemento: encerra a posse e reabre o Processamento como aguardando.

    Um novo ciclo, não uma reabertura do anterior: o progresso do complemento
    não pode se misturar com o do processamento original.
    """
    await etapas.exigir_posse(session, id_exame, etapas.MICROSCOPIA, usuario, eh_admin)
    if not marcadores.strip():
        raise HTTPException(status_code=400, detail="Informe os marcadores ou o complemento solicitado.")

    exame = await session.get(ExamePatologia, id_exame)
    exame.status = S_EM_PROCESSAMENTO
    await etapas.transferir(
        session, id_exame, etapas.MICROSCOPIA, etapas.PROCESSAMENTO, usuario,
        observacoes=f"Complemento/IHQ solicitado: {marcadores.strip()}",
    )
    await session.commit()
    return {"id_exame": id_exame, "numero_solicitacao": exame.numero_local, "status": exame.status}


async def solicitar_revisao(
    session: AsyncSession, id_exame: str, motivo: str, usuario: Optional[str], eh_admin: bool = False,
) -> dict:
    """Revisão interna: encerra a posse e abre um novo ciclo de revisão.

    O laudo prévio é copiado para o ciclo novo — sem isso quem revisa abriria a
    tela sem enxergar o que já tinha sido escrito.
    """
    registro = await etapas.exigir_posse(session, id_exame, etapas.MICROSCOPIA, usuario, eh_admin)
    if not motivo.strip():
        raise HTTPException(status_code=400, detail="Descreva o motivo da revisão.")

    anterior = await _laudo(session, id_exame, registro.ciclo)
    exame = await session.get(ExamePatologia, id_exame)
    exame.status = S_REVISAO

    await etapas.concluir(
        session, id_exame, etapas.MICROSCOPIA, usuario, observacoes=f"Revisão interna: {motivo.strip()}",
    )
    novo = await etapas.abrir(
        session, id_exame, etapas.MICROSCOPIA, subetapa=etapas.SUB_REVISAO, usuario=usuario,
        observacoes=f"Novo ciclo de revisão: {motivo.strip()}",
    )
    laudo = await _garantir_laudo(session, id_exame, novo.ciclo)
    if anterior is not None:
        laudo.laudo_previo = anterior.conclusao or anterior.laudo_previo
        laudo.residente = anterior.residente
        laudo.laudo_previo_em = anterior.laudo_previo_em
    registrar_movimentacao(
        session, exame=exame, etapa="Microscopia", anterior=S_EM_MICRO, novo=S_REVISAO,
        usuario=usuario, observacoes=motivo.strip(),
    )
    await session.commit()
    return await _linha(session, id_exame)


# =====================================================================
# Rota antiga
# =====================================================================


async def listar_pendencias_microscopia(session):
    """Lista simples por exame. Mantida para leitura direta de código; a tela
    usa ``listar_fila``."""
    rows = (await session.execute(
        select(ExamePatologia, EtapaExamePatologia)
        .join(EtapaExamePatologia, EtapaExamePatologia.id_exame == ExamePatologia.id)
        .where(
            EtapaExamePatologia.etapa == etapas.MICROSCOPIA,
            EtapaExamePatologia.status != etapas.CONCLUIDA,
        )
        .order_by(EtapaExamePatologia.criado_em.desc(), EtapaExamePatologia.id.desc())
        .limit(500)
    )).all()
    return [{"id": e.id, "numero_solicitacao": e.numero_local, "status": e.status,
             "subetapa": et.subetapa, "data_recebimento": e.data_recebimento}
            for e, et in rows]


async def buscar_por_codigo(session, codigo: str) -> dict:
    """Resolve lâmina, bloco ou número de solicitação para o exame."""
    alvo = (codigo or "").strip()
    if not alvo:
        raise HTTPException(status_code=400, detail="Informe o código.")

    linha = (await session.execute(
        select(CassetePatologia.id_exame)
        .join(BlocoParafinaPatologia, BlocoParafinaPatologia.id_cassete == CassetePatologia.id)
        .join(LaminaPatologia, LaminaPatologia.id_bloco == BlocoParafinaPatologia.id)
        .where((LaminaPatologia.codigo_lamina == alvo) | (LaminaPatologia.qr_code == alvo))
        .limit(1)
    )).scalar_one_or_none()
    if linha:
        return {"id_exame": linha}

    linha = (await session.execute(
        select(CassetePatologia.id_exame)
        .join(BlocoParafinaPatologia, BlocoParafinaPatologia.id_cassete == CassetePatologia.id)
        .where((BlocoParafinaPatologia.codigo_bloco == alvo) | (BlocoParafinaPatologia.qr_code == alvo))
        .limit(1)
    )).scalar_one_or_none()
    if linha:
        return {"id_exame": linha}

    exame = (await session.execute(
        select(ExamePatologia).where(ExamePatologia.numero_local == alvo).limit(1)
    )).scalar_one_or_none()
    if not exame:
        raise HTTPException(status_code=404, detail="Nenhuma lâmina, bloco ou exame com esse código.")
    return {"id_exame": exame.id}
