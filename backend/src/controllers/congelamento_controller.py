"""Congelamento: persistência, ciclos e HP correlato.

A tela era inteiramente mock — dois casos fixos num dicionário, ciclos guardados
numa variável do componente e o número do HP correlato gerado por um contador do
navegador. Nada disso sobrevivia a um F5, e dois postos gerariam o mesmo HP.

Aqui tudo é persistido, o HP é gerado no backend dentro da mesma transação da
liberação, e o tipo interno é sempre ``CONG`` — o prefixo ``CO`` que a tela
usava não existe no catálogo.
"""

import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..helpers.identificacao import gerar_codigo_interno_frasco, gerar_qr_code
from ..models.patologia import (
    AmostraPatologia, CasoPatologia, CicloCongelamentoPatologia, CongelamentoPatologia,
    ExamePatologia, TipoExamePatologia,
)
from ..services import etapas
from ..services.fluxo_comum import (
    S_AGUARDANDO_MACRO, S_EM_CONGELAMENTO, S_LIBERADO, agora, proximo_numero_exame,
    registrar_movimentacao,
)


TIPO_CONGELAMENTO = "CONG"
TIPO_HISTOPATOLOGICO = "HP"

CONDUTA_LIVRE = "LIVRE"
CONDUTA_COMPROMETIDA = "COMPROMETIDA"
CONDUTA_AGUARDANDO = "AGUARDANDO"
CONDUTAS = (CONDUTA_LIVRE, CONDUTA_COMPROMETIDA, CONDUTA_AGUARDANDO)


TOTAL_CICLOS = (
    select(func.count(CicloCongelamentoPatologia.id))
    .select_from(CicloCongelamentoPatologia)
    .join(CongelamentoPatologia, CicloCongelamentoPatologia.id_congelamento == CongelamentoPatologia.id)
    .where(CongelamentoPatologia.id_exame == ExamePatologia.id)
    .correlate(ExamePatologia)
    .scalar_subquery()
    .label("total_ciclos")
)

SITUACAO_RESULTADO = (
    select(CongelamentoPatologia.status)
    .where(CongelamentoPatologia.id_exame == ExamePatologia.id)
    .correlate(ExamePatologia)
    .scalar_subquery()
    .label("situacao_resultado")
)

EXTRAS_FILA = (TOTAL_CICLOS, SITUACAO_RESULTADO)


def _enriquecer(item: dict, registro, exame, valores) -> None:
    ciclos, situacao = valores
    item["total_ciclos"] = ciclos or 0
    item["situacao_resultado"] = situacao or "EM_ANALISE"


async def listar_fila(
    session: AsyncSession,
    usuario: Optional[str],
    filtro: str = "aguardando",
    busca: Optional[str] = None,
    pagina: int = 1,
    por_pagina: int = 25,
) -> dict:
    return await etapas.pagina_fila(
        session, etapas.CONGELAMENTO, usuario,
        filtro=filtro, busca=busca, pagina=pagina, por_pagina=por_pagina,
        extras=EXTRAS_FILA, enriquecer=_enriquecer,
    )


async def _linha(session: AsyncSession, id_exame: str) -> dict:
    return await etapas.linha_exame(
        session, id_exame, etapas.CONGELAMENTO, extras=EXTRAS_FILA, enriquecer=_enriquecer,
    )


async def assumir(session: AsyncSession, id_exame: str, usuario, nome_usuario) -> dict:
    await etapas.assumir(session, id_exame, etapas.CONGELAMENTO, usuario, nome_usuario)
    return await _linha(session, id_exame)


async def repassar(session: AsyncSession, id_exame: str, dados, usuario, eh_admin: bool = False) -> dict:
    await etapas.repassar(session, id_exame, etapas.CONGELAMENTO, dados, usuario, eh_admin)
    return await _linha(session, id_exame)


async def liberar(session: AsyncSession, id_exame: str, usuario, eh_admin: bool = False) -> dict:
    await etapas.liberar(session, id_exame, etapas.CONGELAMENTO, usuario, eh_admin)
    return await _linha(session, id_exame)


# =====================================================================
# Registro do congelamento
# =====================================================================


async def _garantir_congelamento(session: AsyncSession, id_exame: str) -> CongelamentoPatologia:
    registro = (await session.execute(
        select(CongelamentoPatologia).where(CongelamentoPatologia.id_exame == id_exame)
    )).scalar_one_or_none()
    if registro is not None:
        return registro
    registro = CongelamentoPatologia(id=str(uuid.uuid4()), id_exame=id_exame, status="EM_ANALISE")
    session.add(registro)
    try:
        await session.flush()
    except IntegrityError:
        # UNIQUE em id_exame: outra requisição criou primeiro.
        await session.rollback()
        return (await session.execute(
            select(CongelamentoPatologia).where(CongelamentoPatologia.id_exame == id_exame)
        )).scalar_one()
    return registro


async def _ciclos(session: AsyncSession, id_congelamento: str) -> list[dict]:
    return [
        {"id": c.id, "ordinal": c.ordinal, "residente": c.residente, "patologista": c.patologista,
         "quantidade_laminas": c.quantidade_laminas, "diagnostico": c.diagnostico,
         "conduta": c.conduta, "observacao": c.observacao, "registrado_por": c.registrado_por,
         "criado_em": c.criado_em}
        for c in (await session.execute(
            select(CicloCongelamentoPatologia)
            .where(CicloCongelamentoPatologia.id_congelamento == id_congelamento)
            .order_by(CicloCongelamentoPatologia.ordinal)
        )).scalars()
    ]


async def obter_workspace(
    session: AsyncSession, id_exame: str, usuario: Optional[str], eh_admin: bool = False
) -> dict:
    registro = await etapas.exigir_etapa(session, id_exame, etapas.CONGELAMENTO)
    return await _montar_workspace(session, registro, usuario, eh_admin)


async def _montar_workspace(
    session: AsyncSession, registro, usuario: Optional[str], eh_admin: bool = False
) -> dict:
    """Monta a resposta a partir de uma etapa já carregada.

    Separado de ``obter_workspace`` porque a liberação do resultado conclui a
    etapa: buscá-la de novo como "etapa ativa" devolveria 404/409 justamente na
    resposta que precisa mostrar o HP correlato recém-gerado.
    """
    id_exame = registro.id_exame
    congelamento = (await session.execute(
        select(CongelamentoPatologia).where(CongelamentoPatologia.id_exame == id_exame)
    )).scalar_one_or_none()
    posse = etapas.posse(registro, usuario, eh_admin)
    return {
        "exame": await _linha(session, id_exame),
        "posse": posse,
        "historico_etapas": etapas.historico_etapas(await etapas.etapas_do_exame(session, id_exame)),
        "congelamento": {
            "id": congelamento.id, "status": congelamento.status,
            "resultado_final": congelamento.resultado_final,
            "numero_hp_correlato": congelamento.numero_hp_correlato,
            "id_exame_hp": congelamento.id_exame_hp,
            "liberado_em": congelamento.liberado_em, "liberado_por": congelamento.liberado_por,
        } if congelamento else None,
        "ciclos": await _ciclos(session, congelamento.id) if congelamento else [],
        "pode_registrar": posse["pode_executar"] and (congelamento is None or congelamento.status != "LIBERADO"),
    }


async def registrar_ciclo(
    session: AsyncSession, id_exame: str, dados, usuario: Optional[str],
    nome_usuario: Optional[str], eh_admin: bool = False,
) -> dict:
    """Registra uma rodada de análise enquanto o cirurgião aguarda.

    "Margem comprometida" mantém o exame em andamento — é o caso em que se
    espera um novo fragmento. "Margem livre" fecha a etapa e gera o HP.
    """
    await etapas.exigir_posse(session, id_exame, etapas.CONGELAMENTO, usuario, eh_admin)
    if dados.conduta not in CONDUTAS:
        raise HTTPException(status_code=400, detail=f"conduta inválida: '{dados.conduta}'.")
    if not dados.diagnostico.strip():
        raise HTTPException(status_code=400, detail="Informe o diagnóstico.")
    if dados.conduta == CONDUTA_COMPROMETIDA and not (dados.observacao or "").strip():
        raise HTTPException(status_code=400, detail="Descreva a observação para o cirurgião.")

    congelamento = await _garantir_congelamento(session, id_exame)
    if congelamento.status == "LIBERADO":
        raise HTTPException(status_code=409, detail="Este congelamento já teve o resultado liberado.")

    ultimo = (await session.execute(
        select(func.max(CicloCongelamentoPatologia.ordinal))
        .where(CicloCongelamentoPatologia.id_congelamento == congelamento.id)
    )).scalar_one() or 0

    ciclo = CicloCongelamentoPatologia(
        id=str(uuid.uuid4()), id_congelamento=congelamento.id, ordinal=ultimo + 1,
        residente=dados.residente, patologista=dados.patologista,
        quantidade_laminas=dados.quantidade_laminas, diagnostico=dados.diagnostico.strip(),
        conduta=dados.conduta, observacao=(dados.observacao or "").strip() or None,
        registrado_por=nome_usuario or usuario,
    )
    session.add(ciclo)

    exame = await session.get(ExamePatologia, id_exame)
    registrar_movimentacao(
        session, exame=exame, etapa="Congelamento", anterior=S_EM_CONGELAMENTO,
        novo=dados.conduta, usuario=usuario,
        observacoes=f"Ciclo {ciclo.ordinal}: {dados.diagnostico.strip()[:200]}",
    )

    if dados.conduta == CONDUTA_LIVRE:
        return await _liberar_resultado(session, exame, congelamento, ciclo, usuario, nome_usuario, eh_admin)

    await session.commit()
    return await obter_workspace(session, id_exame, usuario, eh_admin)


async def _liberar_resultado(
    session: AsyncSession, exame: ExamePatologia, congelamento: CongelamentoPatologia,
    ciclo: CicloCongelamentoPatologia, usuario: Optional[str], nome_usuario: Optional[str],
    eh_admin: bool = False,
) -> dict:
    """Encerra o congelamento e cria o HP correlato na mesma transação.

    O HP é um exame de verdade — entra na fila da macroscopia junto com o
    material que volta à recepção. Antes era só uma string calculada no
    navegador, que ninguém conseguia procurar depois.
    """
    tipo_hp = (await session.execute(
        select(TipoExamePatologia).where(TipoExamePatologia.codigo == TIPO_HISTOPATOLOGICO)
    )).scalar_one_or_none()
    if tipo_hp is None:
        raise HTTPException(status_code=422, detail="Tipo de exame HP não configurado no catálogo.")

    referencia = agora()
    numero_hp, sequencial, ano, semestre = await proximo_numero_exame(session, tipo_hp)

    # O HP correlato precisa de um caso próprio: ``exames`` tem UNIQUE em
    # (id_caso, id_tipo_exame), e o caso da congelação frequentemente já tem um
    # HP. Além disso é uma nova entrada na recepção, não a mesma solicitação.
    caso_origem = await session.get(CasoPatologia, exame.id_caso)
    caso_hp = CasoPatologia(
        id=str(uuid.uuid4()),
        chave_origem=f"CONGELAMENTO:{exame.id}",
        id_paciente=caso_origem.id_paciente,
        data_solicitacao=referencia.date(),
        situacao_importacao="PRONTO",
    )
    session.add(caso_hp)
    await session.flush()

    exame_hp = ExamePatologia(
        id=str(uuid.uuid4()), id_caso=caso_hp.id, id_tipo_exame=tipo_hp.id,
        numero_local=numero_hp, sequencial=sequencial, ano=ano, semestre=semestre,
        status=S_AGUARDANDO_MACRO, numero_exame_aghu=exame.numero_exame_aghu,
        tipo_peca=exame.tipo_peca, topografia=exame.topografia,
        data_recebimento=referencia, criado_por=usuario,
    )
    session.add(exame_hp)
    try:
        await session.flush()
    except IntegrityError:
        # UNIQUE em numero_local: duas liberações simultâneas pegaram o mesmo
        # sequencial. Falhar aqui é melhor que gravar um código duplicado.
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Outro congelamento gerou um HP ao mesmo tempo. Tente novamente.",
        )

    # O HP nasce com o frasco do material que volta para a recepção.
    id_amostra = str(uuid.uuid4())
    session.add(AmostraPatologia(
        id=id_amostra, id_caso=caso_hp.id, id_exame=exame_hp.id, numero_amostra=1,
        codigo_solicitacao=numero_hp, codigo_interno=gerar_codigo_interno_frasco(numero_hp),
        qr_code=gerar_qr_code("FRASCO", numero_hp, identificador=id_amostra),
        status=S_AGUARDANDO_MACRO, criado_por=usuario,
    ))

    congelamento.status = "LIBERADO"
    congelamento.resultado_final = ciclo.diagnostico
    congelamento.id_exame_hp = exame_hp.id
    congelamento.numero_hp_correlato = numero_hp
    congelamento.liberado_em = referencia
    congelamento.liberado_por = nome_usuario or usuario

    exame.status = S_LIBERADO
    exame.data_conclusao = referencia
    for amostra in (await session.execute(
        select(AmostraPatologia).where(AmostraPatologia.id_exame == exame.id)
    )).scalars():
        amostra.status = S_LIBERADO

    registro = await etapas.concluir(
        session, exame.id, etapas.CONGELAMENTO, usuario,
        observacoes=f"Resultado liberado — HP correlato {numero_hp}",
    )
    # O material volta à recepção e segue o fluxo histopatológico normal.
    await etapas.abrir(session, exame_hp.id, etapas.MACROSCOPIA, usuario=usuario,
                       observacoes=f"HP correlato do congelamento {exame.numero_local}")
    registrar_movimentacao(
        session, exame=exame_hp, etapa="Triagem", anterior=None, novo=S_AGUARDANDO_MACRO,
        usuario=usuario, observacoes=f"Gerado a partir do congelamento {exame.numero_local}",
    )
    await session.commit()
    return await _montar_workspace(session, registro, usuario, eh_admin)


async def buscar_por_codigo(session: AsyncSession, codigo: str) -> dict:
    """Resolve o código digitado para um exame de congelação.

    Aceita ``CONG-0001/26.1`` e também o antigo ``CO-0001/26.1`` que circula nas
    etiquetas: o prefixo exibido mudou, o tipo interno sempre foi ``CONG``.
    """
    alvo = (codigo or "").strip()
    if not alvo:
        raise HTTPException(status_code=400, detail="Informe o código do congelamento.")
    candidatos = [alvo]
    if alvo.upper().startswith("CO-"):
        candidatos.append(f"CONG-{alvo[3:]}")

    exame = (await session.execute(
        select(ExamePatologia)
        .join(TipoExamePatologia, ExamePatologia.id_tipo_exame == TipoExamePatologia.id)
        .where(
            ExamePatologia.numero_local.in_(candidatos),
            TipoExamePatologia.codigo == TIPO_CONGELAMENTO,
        )
        .limit(1)
    )).scalar_one_or_none()
    if exame is None:
        # Também aceita o número da solicitação AGHU.
        exame = (await session.execute(
            select(ExamePatologia)
            .join(TipoExamePatologia, ExamePatologia.id_tipo_exame == TipoExamePatologia.id)
            .where(
                ExamePatologia.numero_exame_aghu.ilike(f"%{alvo}%"),
                TipoExamePatologia.codigo == TIPO_CONGELAMENTO,
            )
            .limit(1)
        )).scalar_one_or_none()
    if exame is None:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma congelação com esse código. Confira a unidade executora no AGHU (205 — Congelamento).",
        )
    return {"id_exame": exame.id, "numero_solicitacao": exame.numero_local}
