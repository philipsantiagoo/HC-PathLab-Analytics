"""Importador idempotente do CSV para o schema canônico ``pathlab``."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.patologia import (
    AmostraPatologia,
    CasoPatologia,
    ExamePatologia,
    ImportacaoPatologia,
    LinhaImportacaoPatologia,
    PacientePatologia,
    TipoExamePatologia,
)
from .patologia import CasoCandidato, agrupar_casos, ler_csv_patologia


def _chave_paciente_serializada(chave: tuple[str, ...]) -> str:
    return hashlib.sha256("\x1f".join(chave).encode("utf-8")).hexdigest()


async def importar_csv_patologia(
    session: AsyncSession,
    caminho: str | Path,
) -> ImportacaoPatologia:
    """Importa sem criar fluxo operacional antes da revisão das pendências.

    Repetir o mesmo arquivo retorna o lote anterior. A linha de origem também é
    única por hash, impedindo duplicação entre arquivos sobrepostos.
    """
    arquivo = Path(caminho)
    hash_arquivo = hashlib.sha256(arquivo.read_bytes()).hexdigest()
    existente = (
        await session.execute(
            select(ImportacaoPatologia).where(ImportacaoPatologia.hash_arquivo == hash_arquivo)
        )
    ).scalar_one_or_none()
    linhas = ler_csv_patologia(arquivo)
    casos = agrupar_casos(linhas)
    if existente is not None:
        if existente.status == "CONCLUIDO":
            return existente
        lote = existente
        lote.status = "EM_ANDAMENTO"
        lote.erro = None
        lote.linhas_lidas = len(linhas)
        lote.linhas_rejeitadas = 0
        lote.casos_prontos = 0
        lote.casos_revisao = 0
        lote.concluido_em = None
    else:
        lote = ImportacaoPatologia(
            id=str(uuid.uuid4()),
            arquivo_origem=str(arquivo),
            hash_arquivo=hash_arquivo,
            linhas_lidas=len(linhas),
        )
        session.add(lote)
    await session.flush()

    tipos = {
        tipo.codigo: tipo
        for tipo in (await session.execute(select(TipoExamePatologia))).scalars().all()
    }
    if {linha.tipo_exame for linha in linhas} - set(tipos):
        raise ValueError("O catálogo pathlab não contém todos os tipos de exame do CSV.")

    pacientes: dict[str, PacientePatologia] = {
        paciente.chave_origem: paciente
        for paciente in (await session.execute(select(PacientePatologia))).scalars().all()
    }
    casos_existentes: dict[str, CasoPatologia] = {
        caso.chave_origem: caso
        for caso in (await session.execute(select(CasoPatologia))).scalars().all()
    }

    try:
        casos_para_linhas: list[tuple[CasoCandidato, CasoPatologia, dict[str, ExamePatologia], str]] = []
        novos_pacientes: list[PacientePatologia] = []
        novos_casos: list[CasoPatologia] = []
        novos_exames: list[ExamePatologia] = []
        for candidato in casos:
            chave_paciente = _chave_paciente_serializada(candidato.chave_paciente)
            paciente = pacientes.get(chave_paciente)
            primeira = candidato.linhas[0]
            if paciente is None:
                paciente = PacientePatologia(
                    id=str(uuid.uuid4()),
                    chave_origem=chave_paciente,
                    prontuario=primeira.prontuario or None,
                    nome=primeira.nome_paciente or "PACIENTE NÃO IDENTIFICADO",
                    data_nascimento=primeira.data_nascimento,
                )
                session.add(paciente)
                novos_pacientes.append(paciente)
                pacientes[chave_paciente] = paciente

            caso = casos_existentes.get(candidato.chave)
            if caso is None:
                caso = CasoPatologia(
                    id=str(uuid.uuid4()),
                    chave_origem=candidato.chave,
                    id_paciente=paciente.id,
                    data_solicitacao=candidato.data_solicitacao,
                    situacao_importacao="REVISAR" if candidato.exige_revisao else "PRONTO",
                    pendencias=sorted(candidato.pendencias),
                )
                session.add(caso)
                novos_casos.append(caso)
                casos_existentes[candidato.chave] = caso

            exames_por_tipo: dict[str, ExamePatologia] = {}
            # O número da solicitação AGHU é o que o usuário procura no
            # dashboard. Ele chega por linha (amostra), então acumulamos os
            # distintos do exame aqui e desnormalizamos abaixo.
            codigos_aghu_por_tipo: dict[str, list[str]] = {}
            for linha in candidato.linhas:
                exame = exames_por_tipo.get(linha.tipo_exame)
                if exame is None:
                    exame = ExamePatologia(
                        id=str(uuid.uuid4()),
                        id_caso=caso.id,
                        id_tipo_exame=tipos[linha.tipo_exame].id,
                    )
                    session.add(exame)
                    novos_exames.append(exame)
                    exames_por_tipo[linha.tipo_exame] = exame
                    codigos_aghu_por_tipo[linha.tipo_exame] = []

                codigos = codigos_aghu_por_tipo[linha.tipo_exame]
                if linha.codigo_solicitacao and linha.codigo_solicitacao not in codigos:
                    codigos.append(linha.codigo_solicitacao)

            # O agrupamento por proximidade pode juntar solicitações
            # consecutivas do mesmo paciente num único exame; nesse caso
            # guardamos as duas. O filtro do dashboard usa ILIKE, então buscar
            # por qualquer uma delas continua encontrando o exame.
            for tipo_exame, exame in exames_por_tipo.items():
                codigos = sorted(codigos_aghu_por_tipo[tipo_exame])
                exame.numero_exame_aghu = ", ".join(codigos)[:50] or None

            casos_para_linhas.append((candidato, caso, exames_por_tipo, chave_paciente))

        # Sem relacionamentos ORM, a ordem de flush não é deduzida pelo
        # SQLAlchemy entre schemas. Primeiro persiste cada nível de pais.
        if novos_pacientes:
            await session.flush(novos_pacientes)
        if novos_casos:
            await session.flush(novos_casos)
        if novos_exames:
            await session.flush(novos_exames)

        linhas_importadas: list[LinhaImportacaoPatologia] = []
        amostras_pendentes: list[tuple[LinhaImportacaoPatologia, CasoPatologia, ExamePatologia, object, list[str]]] = []
        for candidato, caso, exames_por_tipo, chave_paciente in casos_para_linhas:
            pendencias = sorted(candidato.pendencias)
            for linha in candidato.linhas:
                linha_importada = LinhaImportacaoPatologia(
                    id=str(uuid.uuid4()),
                    id_importacao=lote.id,
                    ordem_origem=linha.ordem_origem,
                    hash_origem=linha.hash_origem,
                    codigo_solicitacao=linha.codigo_solicitacao,
                    numero_amostra=linha.numero_amostra,
                    codigo_lab=linha.codigo_lab,
                    tipo_exame=linha.tipo_exame,
                    chave_paciente_origem=chave_paciente,
                    codigo_conjunto_amostras=linha.codigo_conjunto_amostras,
                    situacao="REVISAR" if pendencias else "PRONTO",
                    pendencias=pendencias,
                    payload_origem=linha.dados,
                )
                session.add(linha_importada)
                linhas_importadas.append(linha_importada)
                amostras_pendentes.append((
                    linha_importada,
                    caso,
                    exames_por_tipo[linha.tipo_exame],
                    linha,
                    pendencias,
                ))

        if linhas_importadas:
            await session.flush(linhas_importadas)
        for linha_importada, caso, exame, linha, pendencias in amostras_pendentes:
            session.add(AmostraPatologia(
                    id=str(uuid.uuid4()),
                    id_caso=caso.id,
                    id_exame=exame.id,
                    id_linha_importacao=linha_importada.id,
                    numero_amostra=linha.numero_amostra,
                    codigo_solicitacao=linha.codigo_solicitacao,
                    descricao_material=linha.dados.get("descricao_material") or None,
                    status="REVISAR" if pendencias else "AGUARDANDO_RECEBIMENTO",
            ))

        lote.casos_prontos = sum(not caso.exige_revisao for caso in casos)
        lote.casos_revisao = sum(caso.exige_revisao for caso in casos)
        lote.status = "CONCLUIDO"
        lote.concluido_em = datetime.utcnow()
        await session.commit()
    except Exception as exc:
        await session.rollback()
        lote.status = "FALHOU"
        lote.erro = str(exc)
        lote.concluido_em = datetime.utcnow()
        session.add(lote)
        await session.commit()
        raise
    return lote
