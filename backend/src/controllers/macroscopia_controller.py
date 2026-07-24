"""
Macroscopia: identificação do frasco (fila de pendências + busca manual),
início da etapa e registro da macroscopia com geração dos cassetes.
"""

import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..helpers.identificacao import (
    gerar_qr_code,
    identificadores_fragmentos,
    letra_fragmento,
)
from ..models.cassete import Cassete
from ..models.macroscopia import Macroscopia
from ..models.parte_macroscopia import ParteMacroscopia
from ..providers.implementations.cassete_repository import CasseteRepository
from ..providers.implementations.exame_repository import ExameRepository
from ..providers.implementations.frasco_repository import FrascoRepository
from ..providers.implementations.macroscopia_repository import MacroscopiaRepository
from ..schemas.etiqueta import EtiquetaOut
from ..schemas.macroscopia import MacroscopiaCreate
from ..services.maquina_estados import (
    Etapa,
    StatusCassete,
    StatusExame,
    StatusFrasco,
    registrar_historico,
    transicionar,
)


async def listar_pendencias(session: AsyncSession) -> List[dict]:
    """Fila da estação: frascos aguardando macroscopia."""
    return await FrascoRepository(session).listar_pendencias_macroscopia()


async def buscar_frasco(
    session: AsyncSession,
    numero_solicitacao: Optional[str],
    codigo_interno: Optional[str],
) -> List[dict]:
    if not numero_solicitacao and not codigo_interno:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe numero_solicitacao ou codigo_interno.",
        )
    resultados = await FrascoRepository(session).buscar_detalhe(
        numero_solicitacao, codigo_interno
    )
    if not resultados:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Nenhum frasco encontrado."
        )
    return resultados


async def iniciar_macroscopia(
    session: AsyncSession,
    id_frasco: str,
    usuario: Optional[str],
    ip: Optional[str],
):
    """
    Move frasco 'Aguardando Macroscopia' → 'Em Macroscopia' e exame
    'Na Recepção' → 'Em Macroscopia'.
    """
    frasco_repo = FrascoRepository(session)
    exame_repo = ExameRepository(session)

    frasco = await frasco_repo.obter(id_frasco)
    if frasco is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Frasco não encontrado."
        )
    exame = await exame_repo.obter(frasco.id_exame)

    transicionar(
        session,
        frasco,
        StatusFrasco.EM_MACROSCOPIA,
        etapa=Etapa.MACROSCOPIA,
        usuario=usuario,
        ip=ip,
    )
    if exame is not None and exame.status == StatusExame.NA_RECEPCAO:
        transicionar(
            session,
            exame,
            StatusExame.EM_MACROSCOPIA,
            etapa=Etapa.MACROSCOPIA,
            usuario=usuario,
            ip=ip,
        )

    await session.commit()
    await session.refresh(frasco)
    return frasco


async def registrar_macroscopia(
    session: AsyncSession,
    dados: MacroscopiaCreate,
    usuario: Optional[str],
    ip: Optional[str],
) -> dict:
    """
    Persiste as partes da peça, gera no backend os identificadores de seus
    fragmentos (A ou A1, A2...), conclui o frasco e move o exame para
    'Em Processamento'. Tudo numa única transação.
    """
    frasco_repo = FrascoRepository(session)
    exame_repo = ExameRepository(session)
    cassete_repo = CasseteRepository(session)
    macro_repo = MacroscopiaRepository(session)

    frasco = await frasco_repo.obter(dados.id_frasco)
    if frasco is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Frasco não encontrado."
        )
    if frasco.status != StatusFrasco.EM_MACROSCOPIA:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "O frasco precisa estar 'Em Macroscopia' para registrar. "
                f"Status atual: '{frasco.status}'."
            ),
        )

    exame = await exame_repo.obter(frasco.id_exame)
    numero_solicitacao = exame.numero_solicitacao if exame else ""

    total_fragmentos = sum(len(parte.fragmentos) for parte in dados.partes)
    macroscopia_id = str(uuid.uuid4())
    macroscopia = Macroscopia(
        id=macroscopia_id,
        id_frasco=frasco.id,
        descricao=dados.descricao,
        responsavel=usuario,
        numero_cassetes=total_fragmentos,
    )
    macro_repo.adicionar(macroscopia)
    await session.flush()

    partes: List[ParteMacroscopia] = []
    cassetes: List[Cassete] = []
    etiquetas: List[EtiquetaOut] = []

    for indice_parte, dados_parte in enumerate(dados.partes):
        letra_parte = letra_fragmento(indice_parte)
        parte = ParteMacroscopia(
            id=str(uuid.uuid4()),
            id_macroscopia=macroscopia_id,
            ordinal=indice_parte + 1,
            letra_identificacao=letra_parte,
            descricao_estrutura=dados_parte.estrutura.strip(),
            quantidade_fragmentos=len(dados_parte.fragmentos),
        )
        session.add(parte)
        partes.append(parte)

    # Garante que todas as partes pai existam antes dos cassetes. Sem
    # relacionamentos ORM explícitos, o SQLAlchemy não necessariamente
    # infere essa ordem apenas pelas ForeignKeys.
    await session.flush()

    for parte, dados_parte in zip(partes, dados.partes):
        letra_parte = parte.letra_identificacao
        identificadores = identificadores_fragmentos(
            letra_parte, len(dados_parte.fragmentos)
        )
        for identificador, dados_fragmento in zip(
            identificadores, dados_parte.fragmentos
        ):
            cassete_id = str(uuid.uuid4())
            qr_code = gerar_qr_code(
                "CASSETE", numero_solicitacao, identificador=cassete_id
            )
            cassete = Cassete(
                id=cassete_id,
                id_frasco=frasco.id,
                id_parte_macroscopia=parte.id,
                letra_fragmento=identificador,
                qr_code=qr_code,
                descricao_estrutura=parte.descricao_estrutura,
                observacoes_macroscopia=(
                    dados_fragmento.observacoes.strip()
                    if dados_fragmento.observacoes
                    else None
                ),
                coloracao_padrao=dados_fragmento.coloracao.strip(),
                status=StatusCassete.AGUARDANDO_PROCESSAMENTO,
                criado_por=usuario,
            )
            cassete_repo.adicionar(cassete)
            registrar_historico(
                session,
                cassete,
                status_anterior=None,
                status_novo=StatusCassete.AGUARDANDO_PROCESSAMENTO,
                etapa=Etapa.MACROSCOPIA,
                usuario=usuario,
                ip=ip,
                observacoes=(
                    f"Cassete {identificador} gerado para a parte "
                    f"{letra_parte}: {parte.descricao_estrutura}"
                ),
            )
            cassetes.append(cassete)
            etiquetas.append(
                EtiquetaOut(
                    tipo="CASSETE",
                    numero_solicitacao=numero_solicitacao,
                    codigo=identificador,
                    qr_code=qr_code,
                )
            )

    frasco.descricao_macroscopia = dados.descricao
    frasco.numero_cassetes_gerados = total_fragmentos
    transicionar(
        session,
        frasco,
        StatusFrasco.PROCESSAMENTO_COMPLETO,
        etapa=Etapa.MACROSCOPIA,
        usuario=usuario,
        ip=ip,
        observacoes=(
            f"{len(partes)} parte(s) e {total_fragmentos} cassete(s) gerado(s)"
        ),
    )
    if exame is not None:
        transicionar(
            session,
            exame,
            StatusExame.EM_PROCESSAMENTO,
            etapa=Etapa.MACROSCOPIA,
            usuario=usuario,
            ip=ip,
        )

    await session.commit()
    await session.refresh(macroscopia)
    await session.refresh(frasco)

    return {
        "macroscopia": macroscopia,
        "frasco": frasco,
        "partes": partes,
        "cassetes": cassetes,
        "etiquetas": etiquetas,
    }
