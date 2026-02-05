# -*- coding: utf-8 -*-
"""Pacote IRPF: leitura de planilhas, validação e geração de informes em PDF."""

from .loader import carregar_planilha_unimed, carregar_planilha_uniodonto, agrupar_por_titular
from .models import DadosTitular
from .validator import validar_totais, ResultadoValidacao

__all__ = [
    "carregar_planilha_unimed",
    "carregar_planilha_uniodonto",
    "agrupar_por_titular",
    "DadosTitular",
    "validar_totais",
    "ResultadoValidacao",
]
