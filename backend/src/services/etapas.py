"""Fila e posse por etapa do exame — mecânica compartilhada.

Macroscopia, Processamento, Microscopia e Congelamento seguem o mesmo roteiro:

    fila da etapa → abrir exame → assumir → executar → concluir / repassar / devolver

Tudo o que é comum a esse roteiro vive aqui. Cada estação acrescenta apenas as
suas colunas na fila e as suas regras de conclusão, e as URLs continuam
separadas por setor.

Duas invariantes que este módulo existe para proteger:

* **Uma posse por exame e etapa.** Garantida no banco pelo índice parcial
  ``uq_exame_etapas_ativa`` e no código pelo UPDATE condicional de ``assumir``.
* **Posse é do exame inteiro**, mesmo quando a etapa manipula cassetes, blocos
  ou lâminas — todos são filhos do mesmo exame.
"""

import uuid
from typing import Any, Callable, Iterable, Optional, Sequence

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.patologia import (
    CasoPatologia,
    EtapaExamePatologia,
    ExamePatologia,
    PacientePatologia,
    TipoExamePatologia,
)
from ..schemas.paginacao import montar_pagina
from .fluxo_comum import TOTAL_FRASCOS, agora, atrasado, registrar_movimentacao


# --- Vocabulário ---------------------------------------------------------
MACROSCOPIA = "MACROSCOPIA"
PROCESSAMENTO = "PROCESSAMENTO"
MICROSCOPIA = "MICROSCOPIA"
CONGELAMENTO = "CONGELAMENTO"

ETAPAS = (MACROSCOPIA, PROCESSAMENTO, MICROSCOPIA, CONGELAMENTO)

AGUARDANDO = "AGUARDANDO"
EM_ANDAMENTO = "EM_ANDAMENTO"
CONCLUIDA = "CONCLUIDA"

# Subetapas da microscopia: quem é esperado em cada momento.
SUB_LAUDO_PREVIO = "LAUDO_PREVIO"
SUB_REVISAO = "REVISAO"

FILTROS = ("meus", "aguardando", "em_andamento", "todos")

# Rótulos usados nas movimentações e nas mensagens ao usuário.
ROTULO_ETAPA = {
    MACROSCOPIA: "Macroscopia",
    PROCESSAMENTO: "Processamento",
    MICROSCOPIA: "Microscopia",
    CONGELAMENTO: "Congelamento",
}


def rotulo(etapa: str) -> str:
    return ROTULO_ETAPA.get(etapa, etapa.title())


# =====================================================================
# Leitura da etapa
# =====================================================================


async def etapa_ativa(
    session: AsyncSession, id_exame: str, etapa: str, *, para_atualizar: bool = False
) -> Optional[EtapaExamePatologia]:
    """A etapa aberta do exame — no máximo uma, pelo índice parcial.

    ``populate_existing`` é obrigatório: a sessão usa ``expire_on_commit=False``
    e os UPDATE em massa rodam com ``synchronize_session=False``, então sem isso
    o identity map devolveria a instância anterior à mudança de posse.
    """
    stmt = (
        select(EtapaExamePatologia)
        .where(
            EtapaExamePatologia.id_exame == id_exame,
            EtapaExamePatologia.etapa == etapa,
            EtapaExamePatologia.status != CONCLUIDA,
        )
        .execution_options(populate_existing=True)
    )
    if para_atualizar:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def exigir_etapa(session: AsyncSession, id_exame: str, etapa: str) -> EtapaExamePatologia:
    registro = await etapa_ativa(session, id_exame, etapa)
    if registro is None:
        if await session.get(ExamePatologia, id_exame) is None:
            raise HTTPException(status_code=404, detail="Exame não encontrado.")
        raise HTTPException(
            status_code=409,
            detail=f"Este exame não está na etapa de {rotulo(etapa).lower()}.",
        )
    return registro


async def exigir_posse(
    session: AsyncSession, id_exame: str, etapa: str, usuario: Optional[str], eh_admin: bool = False
) -> EtapaExamePatologia:
    """Guarda das ações operacionais. Sem ela, "assumir" não significaria nada.

    Esconder botões no frontend não é controle de acesso: toda ação que altera
    o exame passa por aqui.
    """
    registro = await exigir_etapa(session, id_exame, etapa)
    if registro.status != EM_ANDAMENTO:
        raise HTTPException(
            status_code=409,
            detail=f"Assuma o exame antes de executar ações na {rotulo(etapa).lower()}.",
        )
    if registro.responsavel_username != usuario and not eh_admin:
        dono = registro.responsavel_nome or registro.responsavel_username
        raise HTTPException(status_code=403, detail=f"Este exame está com {dono}.")
    return registro


async def etapas_do_exame(session: AsyncSession, id_exame: str) -> list[EtapaExamePatologia]:
    """Histórico de etapas do exame, para o cabeçalho do workspace."""
    return list((await session.execute(
        select(EtapaExamePatologia)
        .where(EtapaExamePatologia.id_exame == id_exame)
        .order_by(EtapaExamePatologia.criado_em, EtapaExamePatologia.id)
    )).scalars())


# =====================================================================
# Ciclo de vida da etapa
# =====================================================================


async def abrir(
    session: AsyncSession,
    id_exame: str,
    etapa: str,
    *,
    subetapa: Optional[str] = None,
    usuario: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> EtapaExamePatologia:
    """Coloca o exame na fila da etapa, sem responsável.

    Idempotente: se a etapa já está aberta, apenas ajusta a subetapa. Quando a
    etapa já foi concluída antes (retorno da microscopia para o processamento),
    abre um novo ciclo em vez de sobrescrever o progresso do anterior.
    """
    existente = await etapa_ativa(session, id_exame, etapa)
    if existente is not None:
        if subetapa is not None and existente.subetapa != subetapa:
            existente.subetapa = subetapa
        return existente

    ultimo = (await session.execute(
        select(func.max(EtapaExamePatologia.ciclo)).where(
            EtapaExamePatologia.id_exame == id_exame, EtapaExamePatologia.etapa == etapa
        )
    )).scalar_one() or 0

    registro = EtapaExamePatologia(
        id=str(uuid.uuid4()), id_exame=id_exame, etapa=etapa, status=AGUARDANDO,
        subetapa=subetapa, ciclo=ultimo + 1, criado_em=agora(),
    )
    session.add(registro)
    try:
        await session.flush()
    except IntegrityError:
        # Corrida com outra requisição abrindo a mesma etapa: o índice parcial
        # barrou a segunda. A que perdeu simplesmente adota a linha vencedora.
        await session.rollback()
        vencedora = await etapa_ativa(session, id_exame, etapa)
        if vencedora is None:
            raise
        return vencedora

    exame = await session.get(ExamePatologia, id_exame)
    registrar_movimentacao(
        session, exame=exame, etapa=rotulo(etapa), anterior=None, novo=AGUARDANDO,
        usuario=usuario,
        observacoes=observacoes or (
            f"Entrada na etapa (ciclo {registro.ciclo})" if registro.ciclo > 1 else "Entrada na etapa"
        ),
    )
    return registro


async def assumir(
    session: AsyncSession, id_exame: str, etapa: str, usuario: Optional[str], nome_usuario: Optional[str]
) -> EtapaExamePatologia:
    """Assume o exame na etapa para quem chamou.

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
        update(EtapaExamePatologia)
        .where(
            EtapaExamePatologia.id_exame == id_exame,
            EtapaExamePatologia.etapa == etapa,
            EtapaExamePatologia.status == AGUARDANDO,
            EtapaExamePatologia.responsavel_username.is_(None),
        )
        .values(
            responsavel_username=usuario,
            responsavel_nome=nome_usuario or usuario,
            assumido_em=agora(),
            status=EM_ANDAMENTO,
        )
        .execution_options(synchronize_session=False)
    )

    if resultado.rowcount == 0:
        await session.rollback()
        registro = await etapa_ativa(session, id_exame, etapa)
        if registro is None:
            if await session.get(ExamePatologia, id_exame) is None:
                raise HTTPException(status_code=404, detail="Exame não encontrado.")
            raise HTTPException(
                status_code=409,
                detail=f"A {rotulo(etapa).lower()} deste exame já foi concluída.",
            )
        if registro.responsavel_username == usuario:
            return registro  # já é meu
        dono = registro.responsavel_nome or registro.responsavel_username
        raise HTTPException(status_code=409, detail=f"Exame já assumido por {dono}. Peça um repasse.")

    exame = await session.get(ExamePatologia, id_exame)
    registrar_movimentacao(
        session, exame=exame, etapa=rotulo(etapa), anterior=AGUARDANDO, novo=EM_ANDAMENTO,
        usuario=usuario, observacoes="Exame assumido",
    )
    await session.commit()
    return await exigir_etapa(session, id_exame, etapa)


async def repassar(
    session: AsyncSession,
    id_exame: str,
    etapa: str,
    dados,
    usuario: Optional[str],
    eh_admin: bool = False,
) -> EtapaExamePatologia:
    """Transfere a posse. Só o dono atual — ou um admin — pode repassar."""
    registro = await exigir_etapa(session, id_exame, etapa)
    if not registro.responsavel_username:
        raise HTTPException(status_code=409, detail="Assuma o exame antes de repassá-lo.")
    if registro.responsavel_username != usuario and not eh_admin:
        dono = registro.responsavel_nome or registro.responsavel_username
        raise HTTPException(status_code=403, detail=f"Só {dono} pode repassar este exame.")

    destino = (dados.para_username or "").strip()
    if not destino:
        raise HTTPException(status_code=400, detail="Informe o destinatário.")
    if destino == registro.responsavel_username:
        raise HTTPException(status_code=400, detail="O exame já está com esse responsável.")

    dono_anterior = registro.responsavel_username
    # Mesmo padrão condicional do assumir: se a posse mudou entre a leitura
    # acima e este UPDATE, rowcount fica 0.
    resultado = await session.execute(
        update(EtapaExamePatologia)
        .where(
            EtapaExamePatologia.id == registro.id,
            EtapaExamePatologia.responsavel_username == dono_anterior,
        )
        .values(
            responsavel_username=destino,
            responsavel_nome=(dados.para_nome or destino),
            assumido_em=agora(),
            status=EM_ANDAMENTO,
        )
        .execution_options(synchronize_session=False)
    )
    if resultado.rowcount == 0:
        await session.rollback()
        raise HTTPException(status_code=409, detail="A posse do exame mudou. Recarregue a fila.")

    exame = await session.get(ExamePatologia, id_exame)
    registrar_movimentacao(
        session, exame=exame, etapa=f"Repasse {rotulo(etapa)}", anterior=dono_anterior,
        novo=destino, usuario=usuario, observacoes=dados.motivo,
    )
    await session.commit()
    return await exigir_etapa(session, id_exame, etapa)


async def liberar(
    session: AsyncSession, id_exame: str, etapa: str, usuario: Optional[str], eh_admin: bool = False
) -> EtapaExamePatologia:
    """Devolve o exame à fila. Saída para quando o dono fica indisponível."""
    registro = await exigir_etapa(session, id_exame, etapa)
    if not registro.responsavel_username:
        return registro  # idempotente
    if registro.responsavel_username != usuario and not eh_admin:
        raise HTTPException(
            status_code=403, detail="Só o responsável ou um administrador pode liberar o exame."
        )

    dono_anterior = registro.responsavel_username
    registro.responsavel_username = None
    registro.responsavel_nome = None
    registro.assumido_em = None
    registro.status = AGUARDANDO

    exame = await session.get(ExamePatologia, id_exame)
    registrar_movimentacao(
        session, exame=exame, etapa=rotulo(etapa), anterior=dono_anterior, novo=AGUARDANDO,
        usuario=usuario, observacoes="Exame devolvido à fila",
    )
    await session.commit()
    return await exigir_etapa(session, id_exame, etapa)


async def concluir(
    session: AsyncSession,
    id_exame: str,
    etapa: str,
    usuario: Optional[str],
    *,
    observacoes: Optional[str] = None,
) -> EtapaExamePatologia:
    """Encerra a etapa. Não limpa o responsável — é trilha de auditoria.

    Sem commit: a conclusão é sempre parte de uma transação maior (registrar a
    clivagem, gerar blocos, liberar o laudo), e comitar aqui deixaria o exame
    fora de toda fila caso o resto falhasse.
    """
    registro = await exigir_etapa(session, id_exame, etapa)
    registro.status = CONCLUIDA
    registro.concluido_em = agora()

    exame = await session.get(ExamePatologia, id_exame)
    registrar_movimentacao(
        session, exame=exame, etapa=rotulo(etapa), anterior=EM_ANDAMENTO, novo=CONCLUIDA,
        usuario=usuario, observacoes=observacoes or "Etapa concluída",
    )
    return registro


async def mudar_subetapa(
    session: AsyncSession,
    id_exame: str,
    etapa: str,
    subetapa: str,
    usuario: Optional[str],
    *,
    encerrar_posse: bool = True,
    observacoes: Optional[str] = None,
) -> EtapaExamePatologia:
    """Avança a etapa para outra subetapa (residente → patologista).

    ``encerrar_posse`` devolve o exame à fila: quem assume o laudo prévio não é
    quem revisa, então manter a posse anterior travaria o exame com a pessoa
    errada. Sem commit — quem chama fecha a transação.
    """
    registro = await exigir_etapa(session, id_exame, etapa)
    anterior = registro.subetapa
    registro.subetapa = subetapa
    if encerrar_posse:
        registro.responsavel_username = None
        registro.responsavel_nome = None
        registro.assumido_em = None
        registro.status = AGUARDANDO

    exame = await session.get(ExamePatologia, id_exame)
    registrar_movimentacao(
        session, exame=exame, etapa=rotulo(etapa), anterior=anterior, novo=subetapa,
        usuario=usuario, observacoes=observacoes or f"Subetapa alterada para {subetapa}",
    )
    return registro


async def transferir(
    session: AsyncSession,
    id_exame: str,
    de_etapa: str,
    para_etapa: str,
    usuario: Optional[str],
    *,
    subetapa: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> EtapaExamePatologia:
    """Conclui a etapa atual e abre a seguinte como AGUARDANDO, sem responsável.

    Toda entrada em etapa começa livre: quem executou a etapa anterior não
    herda o exame na próxima.
    """
    await concluir(session, id_exame, de_etapa, usuario, observacoes=observacoes)
    return await abrir(session, id_exame, para_etapa, subetapa=subetapa, usuario=usuario)


# =====================================================================
# Fila
# =====================================================================


def clausulas(
    etapa: str,
    filtro: str,
    usuario: Optional[str],
    busca: Optional[str],
    subetapa: Optional[str] = None,
) -> list:
    """Condições da fila, compartilhadas entre a página e o COUNT.

    Um helper só para os dois nunca divergirem — se a contagem usar um filtro
    diferente da listagem, a paginação passa a mentir.
    """
    if filtro not in FILTROS:
        raise HTTPException(status_code=400, detail=f"filtro inválido: '{filtro}'.")

    condicoes = [EtapaExamePatologia.etapa == etapa]
    if filtro == "meus":
        # Sem usuário no token não há "meus" — devolve vazio em vez de tudo.
        condicoes.append(EtapaExamePatologia.responsavel_username == (usuario or "\x00"))
        condicoes.append(EtapaExamePatologia.status == EM_ANDAMENTO)
    elif filtro == "aguardando":
        condicoes.append(EtapaExamePatologia.status == AGUARDANDO)
    elif filtro == "em_andamento":
        condicoes.append(EtapaExamePatologia.status == EM_ANDAMENTO)
    else:  # todos — fila é fila, concluídos não entram
        condicoes.append(EtapaExamePatologia.status.in_([AGUARDANDO, EM_ANDAMENTO]))

    if subetapa:
        condicoes.append(EtapaExamePatologia.subetapa == subetapa)

    if busca:
        alvo = f"%{busca.strip()}%"
        condicoes.append(or_(
            ExamePatologia.numero_local.ilike(alvo),
            ExamePatologia.numero_exame_aghu.ilike(alvo),
            PacientePatologia.nome.ilike(alvo),
        ))
    return condicoes


def _joins(stmt):
    return (
        stmt.join(ExamePatologia, EtapaExamePatologia.id_exame == ExamePatologia.id)
        .join(CasoPatologia, ExamePatologia.id_caso == CasoPatologia.id)
        .join(PacientePatologia, CasoPatologia.id_paciente == PacientePatologia.id)
    )


def linha(registro: EtapaExamePatologia, exame, paciente_nome, tipo_codigo, total_frascos, referencia) -> dict:
    """Campos comuns a toda fila. Cada estação acrescenta os seus por cima."""
    entrada = exame.data_recebimento or exame.criado_em
    return {
        "id_exame": exame.id,
        "numero_solicitacao": exame.numero_local or "PENDENTE",
        "tipo_exame": tipo_codigo,
        "paciente_nome": paciente_nome,
        "numero_exame_aghu": exame.numero_exame_aghu,
        "tipo_peca": exame.tipo_peca,
        "total_frascos": total_frascos or 0,
        "etapa": registro.etapa,
        "situacao": registro.status,
        "subetapa": registro.subetapa,
        "ciclo": registro.ciclo,
        "responsavel": registro.responsavel_username,
        "responsavel_nome": registro.responsavel_nome,
        "assumido_em": registro.assumido_em,
        "entrou_na_etapa_em": registro.criado_em,
        "data_entrada": entrada,
        "atrasado": atrasado(entrada, referencia),
        "status_exame": exame.status,
    }


async def pagina_fila(
    session: AsyncSession,
    etapa: str,
    usuario: Optional[str],
    *,
    filtro: str = "aguardando",
    busca: Optional[str] = None,
    subetapa: Optional[str] = None,
    pagina: int = 1,
    por_pagina: int = 25,
    extras: Sequence = (),
    enriquecer: Optional[Callable[[dict, EtapaExamePatologia, Any, Sequence], None]] = None,
) -> dict:
    """Uma página da fila + os contadores das quatro abas.

    ``extras`` são colunas/subqueries específicas da estação (cassetes
    pendentes, lâminas, ciclos) e chegam a ``enriquecer`` na mesma ordem, para
    a estação decidir como nomeá-las na resposta.
    """
    condicoes = clausulas(etapa, filtro, usuario, busca, subetapa)

    base = _joins(
        select(
            EtapaExamePatologia, ExamePatologia, PacientePatologia.nome,
            TipoExamePatologia.codigo, TOTAL_FRASCOS, *extras,
        )
    ).join(TipoExamePatologia, ExamePatologia.id_tipo_exame == TipoExamePatologia.id).where(*condicoes).order_by(
        # O ", id" é obrigatório: os exames vieram de importação em lote e
        # compartilham criado_em. Sem desempate o OFFSET duplica e pula linhas.
        EtapaExamePatologia.criado_em.desc(), EtapaExamePatologia.id.desc(),
    ).limit(por_pagina).offset((pagina - 1) * por_pagina)

    # O COUNT roda só sobre exame_etapas + os joins 1:1 necessários para a
    # busca por nome; nenhum deles altera a cardinalidade.
    contagem = _joins(select(func.count(EtapaExamePatologia.id))).where(*condicoes)

    linhas = (await session.execute(base)).all()
    total = (await session.execute(contagem)).scalar_one()
    referencia = agora()

    itens = []
    for registro, exame, nome, tipo_codigo, total_frascos, *valores in linhas:
        item = linha(registro, exame, nome, tipo_codigo, total_frascos, referencia)
        if enriquecer:
            enriquecer(item, registro, exame, valores)
        itens.append(item)

    return {
        **montar_pagina(itens, total, pagina, por_pagina),
        "contadores": await contadores(session, etapa, usuario, busca, subetapa),
    }


async def contadores(
    session: AsyncSession,
    etapa: str,
    usuario: Optional[str],
    busca: Optional[str] = None,
    subetapa: Optional[str] = None,
) -> dict:
    """Contagem das quatro abas numa única varredura agregada."""
    condicoes = [
        EtapaExamePatologia.etapa == etapa,
        EtapaExamePatologia.status.in_([AGUARDANDO, EM_ANDAMENTO]),
    ]
    if subetapa:
        condicoes.append(EtapaExamePatologia.subetapa == subetapa)
    if busca:
        alvo = f"%{busca.strip()}%"
        condicoes.append(or_(
            ExamePatologia.numero_local.ilike(alvo),
            ExamePatologia.numero_exame_aghu.ilike(alvo),
            PacientePatologia.nome.ilike(alvo),
        ))

    stmt = _joins(
        select(
            EtapaExamePatologia.status,
            EtapaExamePatologia.responsavel_username,
            func.count(EtapaExamePatologia.id),
        )
    ).where(*condicoes).group_by(
        EtapaExamePatologia.status, EtapaExamePatologia.responsavel_username
    )

    meus = aguardando = em_andamento = 0
    for status, responsavel, total in (await session.execute(stmt)).all():
        if status == AGUARDANDO:
            aguardando += total
        elif status == EM_ANDAMENTO:
            em_andamento += total
            if usuario and responsavel == usuario:
                meus += total
    return {
        "meus": meus,
        "aguardando": aguardando,
        "em_andamento": em_andamento,
        "todos": aguardando + em_andamento,
    }


async def linha_exame(
    session: AsyncSession,
    id_exame: str,
    etapa: str,
    *,
    extras: Sequence = (),
    enriquecer: Optional[Callable[[dict, EtapaExamePatologia, Any, Sequence], None]] = None,
) -> dict:
    """Recarrega a linha da fila para um exame — resposta de assumir/repassar."""
    stmt = _joins(
        select(
            EtapaExamePatologia, ExamePatologia, PacientePatologia.nome,
            TipoExamePatologia.codigo, TOTAL_FRASCOS, *extras,
        )
    ).join(TipoExamePatologia, ExamePatologia.id_tipo_exame == TipoExamePatologia.id).where(
        EtapaExamePatologia.id_exame == id_exame,
        EtapaExamePatologia.etapa == etapa,
    ).order_by(EtapaExamePatologia.ciclo.desc()).limit(1).execution_options(populate_existing=True)

    resultado = (await session.execute(stmt)).first()
    if not resultado:
        raise HTTPException(status_code=404, detail="Exame não encontrado nesta etapa.")
    registro, exame, nome, tipo_codigo, total_frascos, *valores = resultado
    item = linha(registro, exame, nome, tipo_codigo, total_frascos, agora())
    if enriquecer:
        enriquecer(item, registro, exame, valores)
    return item


def posse(registro: EtapaExamePatologia, usuario: Optional[str], eh_admin: bool = False) -> dict:
    """Bloco de posse consumido pelo card genérico do frontend."""
    sou_o_dono = bool(usuario) and registro.responsavel_username == usuario
    return {
        "etapa": registro.etapa,
        "situacao": registro.status,
        "subetapa": registro.subetapa,
        "ciclo": registro.ciclo,
        "responsavel": registro.responsavel_username,
        "responsavel_nome": registro.responsavel_nome,
        "assumido_em": registro.assumido_em,
        "sou_o_dono": sou_o_dono,
        "pode_assumir": registro.status == AGUARDANDO and not registro.responsavel_username,
        "pode_liberar": bool(registro.responsavel_username) and (sou_o_dono or eh_admin),
        "pode_executar": sou_o_dono or (eh_admin and registro.status == EM_ANDAMENTO),
    }


def historico_etapas(registros: Iterable[EtapaExamePatologia]) -> list[dict]:
    return [
        {
            "etapa": r.etapa, "situacao": r.status, "subetapa": r.subetapa, "ciclo": r.ciclo,
            "responsavel_nome": r.responsavel_nome, "assumido_em": r.assumido_em,
            "concluido_em": r.concluido_em, "criado_em": r.criado_em,
        }
        for r in registros
    ]
