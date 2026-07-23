"""Sincroniza a identidade autenticada com o perfil local, sem armazenar senha."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.usuarios import Papel, PapelUsuario, PerfilUsuario


CODIGO_PAPEL_POR_NOME = {
    "Admin": "ADMIN",
    "Recepcionista": "RECEPCIONISTA",
    "Macroscopista": "MACROSCOPISTA",
    "Técnico de Laboratório": "TECNICO",
    "Residente": "RESIDENTE",
    "Médico Patologista": "PATOLOGISTA",
}


async def sincronizar_usuario_autenticado(
    session: AsyncSession, usuario: dict, perfis: set[str]
) -> PerfilUsuario:
    username = usuario["username"]
    perfil = (
        await session.execute(select(PerfilUsuario).where(PerfilUsuario.username == username))
    ).scalar_one_or_none()
    if perfil is None:
        perfil = PerfilUsuario(
            subject_externo=username,
            username=username,
            nome_exibicao=(usuario.get("givenName") or [None])[0],
            email=(usuario.get("userPrincipalName") or [None])[0],
        )
        session.add(perfil)
        await session.flush()
    else:
        perfil.ultimo_login_em = datetime.utcnow()
        perfil.ativo = True

    codigos = {CODIGO_PAPEL_POR_NOME[p] for p in perfis if p in CODIGO_PAPEL_POR_NOME}
    await session.execute(delete(PapelUsuario).where(PapelUsuario.id_usuario == perfil.id))
    if codigos:
        papeis = list((await session.execute(select(Papel).where(Papel.codigo.in_(codigos)))).scalars())
        for papel in papeis:
            session.add(PapelUsuario(id_usuario=perfil.id, id_papel=papel.id, unidade=""))

    await session.commit()
    return perfil
