"""Regras canônicas para importar solicitações de patologia.

Uma linha do extrato não é, por si só, um exame operacional: ela representa
uma amostra vinculada a um conjunto de amostras do paciente. Este módulo mantém
essa regra fora de controllers e do formato físico do banco.
"""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable


TIPO_POR_CODIGO_LAB: dict[str, str] = {
    "139": "CCV",
    "203": "CG",
    "205": "CONG",
    "207": "HP",
    "209": "IHQ",
}


class CodigoLaboratorioDesconhecido(ValueError):
    """O extrato trouxe um código de laboratório ainda não homologado."""


def tipo_por_codigo_lab(codigo_lab: str) -> str:
    codigo = str(codigo_lab).strip()
    try:
        return TIPO_POR_CODIGO_LAB[codigo]
    except KeyError as exc:
        raise CodigoLaboratorioDesconhecido(
            f"codigo_lab não homologado: {codigo or '<vazio>'}"
        ) from exc


def _parse_data(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return datetime.strptime(valor.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _normalizar(valor: str | None) -> str:
    return (valor or "").strip()


@dataclass(frozen=True)
class LinhaPatologia:
    ordem_origem: int
    codigo_solicitacao: str
    numero_amostra: int
    codigo_lab: str
    tipo_exame: str
    prontuario: str
    nome_paciente: str
    data_nascimento: date | None
    data_solicitacao: date | None
    codigo_conjunto_amostras: str | None
    dados: dict[str, str]

    @property
    def chave_paciente(self) -> tuple[str, ...]:
        """Prontuário é preferencial; nome+DN é apenas fallback de importação."""
        if self.prontuario:
            return ("prontuario", self.prontuario)
        return (
            "nome-data-nascimento",
            self.nome_paciente.upper(),
            self.data_nascimento.isoformat() if self.data_nascimento else "",
        )

    @property
    def hash_origem(self) -> str:
        serializado = "\x1f".join(
            f"{chave}={self.dados.get(chave, '')}" for chave in sorted(self.dados)
        )
        return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


@dataclass
class CasoCandidato:
    chave: str
    chave_paciente: tuple[str, ...]
    data_solicitacao: date | None
    linhas: list[LinhaPatologia] = field(default_factory=list)
    pendencias: set[str] = field(default_factory=set)

    @property
    def exige_revisao(self) -> bool:
        return bool(self.pendencias)


def ler_csv_patologia(caminho: str | Path) -> list[LinhaPatologia]:
    """Lê o extrato sem alterar os dados de origem."""
    linhas: list[LinhaPatologia] = []
    with Path(caminho).open("r", encoding="utf-8-sig", newline="") as arquivo:
        for ordem, dados in enumerate(csv.DictReader(arquivo), start=2):
            numero = _normalizar(dados.get("numero_amostra"))
            if not numero.isdigit() or int(numero) < 1:
                continue
            codigo_lab = _normalizar(dados.get("codigo_lab"))
            linhas.append(
                LinhaPatologia(
                    ordem_origem=ordem,
                    codigo_solicitacao=_normalizar(dados.get("codigo_solicitacao")),
                    numero_amostra=int(numero),
                    codigo_lab=codigo_lab,
                    tipo_exame=tipo_por_codigo_lab(codigo_lab),
                    prontuario=_normalizar(dados.get("prontuario")),
                    nome_paciente=_normalizar(dados.get("nome_paciente")),
                    data_nascimento=_parse_data(dados.get("data_nascimento")),
                    data_solicitacao=_parse_data(dados.get("data_solicitacao")),
                    codigo_conjunto_amostras=(
                        _normalizar(dados.get("codigo_conjunto_amostras")) or None
                    ),
                    dados={chave: valor or "" for chave, valor in dados.items()},
                )
            )
    return linhas


def _componentes_por_proximidade(linhas: list[LinhaPatologia]) -> list[CasoCandidato]:
    """Agrupa fallback sem supor que a ordenação do CSV seja a chave do caso.

    Cada amostra N é ligada à amostra N-1 mais próxima do mesmo paciente e
    data. Se isso não puder ser demonstrado, a pendência é mantida para revisão
    humana, em vez de se criar uma associação silenciosamente incorreta.
    """
    por_numero: dict[int, list[LinhaPatologia]] = defaultdict(list)
    for linha in linhas:
        por_numero[linha.numero_amostra].append(linha)

    pai = {linha.ordem_origem: linha.ordem_origem for linha in linhas}

    def raiz(valor: int) -> int:
        while pai[valor] != valor:
            pai[valor] = pai[pai[valor]]
            valor = pai[valor]
        return valor

    def unir(a: int, b: int) -> None:
        a, b = raiz(a), raiz(b)
        if a != b:
            pai[b] = a

    pendencias_por_linha: dict[int, set[str]] = defaultdict(set)
    for linha in linhas:
        if linha.numero_amostra == 1:
            continue
        antecessoras = por_numero.get(linha.numero_amostra - 1, [])
        if not antecessoras:
            pendencias_por_linha[linha.ordem_origem].add("AMOSTRA_SEM_ANTECESSORA")
            continue
        antecessora = min(
            antecessoras,
            key=lambda candidata: abs(candidata.ordem_origem - linha.ordem_origem),
        )
        unir(linha.ordem_origem, antecessora.ordem_origem)

    componentes: dict[int, list[LinhaPatologia]] = defaultdict(list)
    for linha in linhas:
        componentes[raiz(linha.ordem_origem)].append(linha)

    casos: list[CasoCandidato] = []
    for indice, grupo in enumerate(componentes.values(), start=1):
        grupo.sort(key=lambda linha: linha.ordem_origem)
        data = grupo[0].data_solicitacao.isoformat() if grupo[0].data_solicitacao else "sem-data"
        chave = "fallback:" + ":".join(
            (*grupo[0].chave_paciente, data, str(grupo[0].ordem_origem), str(indice))
        )
        caso = CasoCandidato(
            chave=chave,
            chave_paciente=grupo[0].chave_paciente,
            data_solicitacao=grupo[0].data_solicitacao,
            linhas=grupo,
        )
        vistos: set[int] = set()
        for linha in grupo:
            caso.pendencias.update(pendencias_por_linha[linha.ordem_origem])
            if linha.numero_amostra in vistos:
                caso.pendencias.add("NUMERO_AMOSTRA_REPETIDO")
            vistos.add(linha.numero_amostra)
        if min(vistos, default=1) != 1:
            caso.pendencias.add("CONJUNTO_SEM_AMOSTRA_1")
        casos.append(caso)
    return casos


def agrupar_casos(linhas: Iterable[LinhaPatologia]) -> list[CasoCandidato]:
    """Produz casos candidatos usando chave estável quando o AGHU a fornecer."""
    por_chave_estavel: dict[tuple[tuple[str, ...], str], list[LinhaPatologia]] = defaultdict(list)
    por_fallback: dict[tuple[tuple[str, ...], date | None], list[LinhaPatologia]] = defaultdict(list)

    for linha in linhas:
        if linha.codigo_conjunto_amostras:
            por_chave_estavel[(linha.chave_paciente, linha.codigo_conjunto_amostras)].append(linha)
        else:
            por_fallback[(linha.chave_paciente, linha.data_solicitacao)].append(linha)

    casos: list[CasoCandidato] = []
    for (chave_paciente, chave_aghu), grupo in por_chave_estavel.items():
        caso = CasoCandidato(
            chave=f"aghu:{chave_aghu}",
            chave_paciente=chave_paciente,
            data_solicitacao=grupo[0].data_solicitacao,
            linhas=sorted(grupo, key=lambda linha: linha.ordem_origem),
        )
        numeros = [linha.numero_amostra for linha in caso.linhas]
        if len(numeros) != len(set(numeros)):
            caso.pendencias.add("NUMERO_AMOSTRA_REPETIDO")
        casos.append(caso)

    for grupo in por_fallback.values():
        casos.extend(_componentes_por_proximidade(grupo))
    return casos
