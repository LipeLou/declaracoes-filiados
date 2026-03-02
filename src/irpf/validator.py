# -*- coding: utf-8 -*-
"""Validação de totais: soma dos detalhes deve bater com o resumo."""

import logging
from dataclasses import dataclass, field
from typing import List

from .models import DadosTitular

logger = logging.getLogger(__name__)


@dataclass
class Inconsistencia:
    """Registro de divergência entre total e soma das linhas."""
    cpf_titular: str
    mensagem: str
    esperado: float
    obtido: float


@dataclass
class ResultadoValidacao:
    """Resultado da validação dos totais por titular."""
    ok: bool
    inconsistencias: List[Inconsistencia] = field(default_factory=list)

    def registrar_log(self, log: logging.Logger) -> None:
        if self.ok:
            log.info("Validação concluída sem inconsistências.")
        else:
            for inc in self.inconsistencias:
                log.warning(
                    "CPF %s: %s (esperado=%.2f, obtido=%.2f)",
                    inc.cpf_titular, inc.mensagem, inc.esperado, inc.obtido,
                )


def validar_totais(titulares: List[DadosTitular]) -> ResultadoValidacao:
    """
    Verifica se, para cada titular, a soma dos detalhes equivale aos totais do resumo.
    """
    inconsistencias: List[Inconsistencia] = []

    for d in titulares:
        soma_cons = sum(l.valor for l in d.linhas_consultas)
        if abs(soma_cons - d.total_consultas) > 0.01:
            inconsistencias.append(Inconsistencia(
                cpf_titular=d.cpf_titular,
                mensagem="Soma das consultas difere do total",
                esperado=d.total_consultas,
                obtido=soma_cons,
            ))

        soma_mens = sum(l.valor for l in d.linhas_mensalidades)
        if abs(soma_mens - d.total_mensalidades) > 0.01:
            inconsistencias.append(Inconsistencia(
                cpf_titular=d.cpf_titular,
                mensagem="Soma das mensalidades difere do total",
                esperado=d.total_mensalidades,
                obtido=soma_mens,
            ))

        soma_retro = sum(l.valor for l in d.linhas_mensalidades_retro)
        if abs(soma_retro - d.total_mensalidades_retro) > 0.01:
            inconsistencias.append(Inconsistencia(
                cpf_titular=d.cpf_titular,
                mensagem="Soma das mensalidades retroativas difere do total",
                esperado=d.total_mensalidades_retro,
                obtido=soma_retro,
            ))

        soma_odonto = sum(l.valor for l in d.linhas_uniodonto)
        if abs(soma_odonto - d.total_uniodonto) > 0.01:
            inconsistencias.append(Inconsistencia(
                cpf_titular=d.cpf_titular,
                mensagem="Soma Uniodonto difere do total",
                esperado=d.total_uniodonto,
                obtido=soma_odonto,
            ))

        soma_unimed_bh = sum(l.valor for l in d.linhas_unimed_bh)
        if abs(soma_unimed_bh - d.total_unimed_bh) > 0.01:
            inconsistencias.append(Inconsistencia(
                cpf_titular=d.cpf_titular,
                mensagem="Soma Unimed BH difere do total",
                esperado=d.total_unimed_bh,
                obtido=soma_unimed_bh,
            ))

    return ResultadoValidacao(ok=len(inconsistencias) == 0, inconsistencias=inconsistencias)
