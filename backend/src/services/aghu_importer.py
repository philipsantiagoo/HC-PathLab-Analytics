"""Importador idempotente do extrato AGHU para o espelho de integração.

Ele não cria exames operacionais: o CSV não informa situação suficiente para
colocar milhares de itens na fila de recepção. A criação do exame local ocorre
somente por regra explícita do fluxo de recebimento.
"""

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.catalogo_aghu import (
    AmostraAghu,
    CatalogoExameAghu,
    ItemAmostraAghu,
    ItemSolicitacaoAghu,
    LoteIntegracao,
    MapeamentoTipoExameAghu,
    SolicitacaoAghu,
    TipoExame,
)


MAPEAMENTO_INICIAL = {
    "APECR": "HP", "HPDER": "HP", "MBIOP": "HP", "MPCIR": "HP",
    "COUT2": "HP", "COLUT": "HP", "CITOP": "CG", "CPMAM": "CG",
    "CCVM": "CCV", "IMUHI": "IH", "CONGE": "CO",
}


def _data(valor: str | None):
    if not valor:
        return None
    try:
        return datetime.strptime(valor.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


async def _um(session: AsyncSession, modelo, *criterios):
    return (await session.execute(select(modelo).where(*criterios))).scalar_one_or_none()


async def importar_csv_aghu(
    session: AsyncSession,
    caminho: str | Path,
    progresso: Callable[[dict], None] | None = None,
    intervalo_progresso: int = 500,
) -> LoteIntegracao:
    caminho = Path(caminho)
    digest = hashlib.sha256(caminho.read_bytes()).hexdigest()
    lote = LoteIntegracao(origem="CSV", arquivo_origem=str(caminho), hash_origem=digest)
    session.add(lote)
    await session.flush()
    siglas_sem_mapeamento: set[str] = set()

    try:
        with caminho.open("r", encoding="utf-8-sig", newline="") as arquivo:
            for row in csv.DictReader(arquivo):
                lote.linhas_lidas += 1
                codigo_solicitacao = (row.get("codigo_solicitacao") or "").strip()
                numero_amostra = (row.get("numero_amostra") or "").strip()
                sigla = (row.get("sigla_exame") or "").strip().upper()
                lab = (row.get("codigo_lab") or "").strip()
                if not all((codigo_solicitacao, numero_amostra, sigla, lab)):
                    lote.linhas_rejeitadas += 1
                    continue

                solicitacao = await _um(
                    session, SolicitacaoAghu,
                    SolicitacaoAghu.codigo_solicitacao_aghu == codigo_solicitacao,
                )
                payload = json.loads(json.dumps(row, ensure_ascii=False))
                if solicitacao is None:
                    solicitacao = SolicitacaoAghu(
                        codigo_solicitacao_aghu=codigo_solicitacao,
                        codigo_paciente_aghu=(row.get("codigo_paciente_aghu") or None),
                        prontuario=(row.get("prontuario") or None),
                        nome_paciente_origem=(row.get("nome_paciente") or None),
                        data_nascimento_origem=_data(row.get("data_nascimento")),
                        data_solicitacao=_data(row.get("data_solicitacao")),
                        convenio=(row.get("convenio") or None),
                        origem_atendimento=(row.get("origem") or None),
                        unidade=(row.get("unidade") or None),
                        informacoes_clinicas=(row.get("informacoes_clinica") or None),
                        id_ultimo_lote_integracao=lote.id,
                        payload_origem=payload,
                    )
                    session.add(solicitacao)
                    await session.flush()
                    lote.linhas_inseridas += 1
                else:
                    solicitacao.id_ultimo_lote_integracao = lote.id
                    solicitacao.payload_origem = payload
                    lote.linhas_atualizadas += 1

                catalogo = await _um(
                    session, CatalogoExameAghu,
                    CatalogoExameAghu.codigo_laboratorio == lab,
                    CatalogoExameAghu.sigla_aghu == sigla,
                )
                if catalogo is None:
                    catalogo = CatalogoExameAghu(
                        codigo_laboratorio=lab, sigla_aghu=sigla,
                        nome_aghu=(row.get("nome_exame") or sigla),
                    )
                    session.add(catalogo)
                    await session.flush()
                    tipo_codigo = MAPEAMENTO_INICIAL.get(sigla)
                    if tipo_codigo:
                        tipo = await _um(session, TipoExame, TipoExame.codigo == tipo_codigo)
                        if tipo:
                            session.add(MapeamentoTipoExameAghu(
                                id_catalogo_exame_aghu=catalogo.id, id_tipo_exame=tipo.id,
                                observacoes="Mapeamento inicial importado do inventário CSV",
                            ))
                    else:
                        siglas_sem_mapeamento.add(sigla)

                # A view atual não expõe item.seqp. Usamos a amostra como chave
                # temporária, marcada no payload, até a view fornecer o campo.
                sequencial_item = (row.get("numero_item_exame") or f"amostra:{numero_amostra}").strip()
                item = await _um(
                    session, ItemSolicitacaoAghu,
                    ItemSolicitacaoAghu.id_solicitacao_aghu == solicitacao.id,
                    ItemSolicitacaoAghu.sequencial_item_aghu == sequencial_item,
                )
                if item is None:
                    item = ItemSolicitacaoAghu(
                        id_solicitacao_aghu=solicitacao.id,
                        sequencial_item_aghu=sequencial_item,
                        id_catalogo_exame_aghu=catalogo.id,
                        descricao_material=(row.get("descricao_material") or None),
                        payload_origem=payload,
                    )
                    session.add(item)
                    await session.flush()

                amostra = await _um(
                    session, AmostraAghu,
                    AmostraAghu.id_solicitacao_aghu == solicitacao.id,
                    AmostraAghu.numero_amostra_aghu == numero_amostra,
                )
                if amostra is None:
                    amostra = AmostraAghu(
                        id_solicitacao_aghu=solicitacao.id,
                        numero_amostra_aghu=numero_amostra,
                        payload_origem=payload,
                    )
                    session.add(amostra)
                    await session.flush()

                vinculo = await _um(
                    session, ItemAmostraAghu,
                    ItemAmostraAghu.id_item_solicitacao_aghu == item.id,
                    ItemAmostraAghu.id_amostra_aghu == amostra.id,
                )
                if vinculo is None:
                    session.add(ItemAmostraAghu(
                        id_item_solicitacao_aghu=item.id, id_amostra_aghu=amostra.id
                    ))

                if progresso and lote.linhas_lidas % intervalo_progresso == 0:
                    await session.flush()
                    progresso({
                        "lidas": lote.linhas_lidas,
                        "inseridas": lote.linhas_inseridas,
                        "atualizadas": lote.linhas_atualizadas,
                        "rejeitadas": lote.linhas_rejeitadas,
                    })

        lote.status = "Concluído"
        lote.concluido_em = datetime.utcnow()
        await session.commit()
        if progresso:
            progresso({
                "lidas": lote.linhas_lidas,
                "inseridas": lote.linhas_inseridas,
                "atualizadas": lote.linhas_atualizadas,
                "rejeitadas": lote.linhas_rejeitadas,
                "concluido": True,
                "siglas_sem_mapeamento": sorted(siglas_sem_mapeamento),
            })
    except Exception as exc:
        await session.rollback()
        lote.status = "Falhou"
        lote.erro = str(exc)
        lote.concluido_em = datetime.utcnow()
        session.add(lote)
        await session.commit()
        raise
    return lote
