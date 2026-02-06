# -*- coding: utf-8 -*-
"""Pacote IRPF: leitura de planilhas, validação e geração de informes em PDF."""

from .loader import (
    carregar_planilha_unimed,
    carregar_planilha_unimed_anual,
    carregar_planilha_uniodonto,
    carregar_planilha_uniodonto_anual,
    agrupar_por_titular,
    obter_nomes_abas_anual,
)
from .models import DadosTitular
from .validator import validar_totais, ResultadoValidacao

__all__ = [
    "carregar_planilha_unimed",
    "carregar_planilha_unimed_anual",
    "carregar_planilha_uniodonto",
    "carregar_planilha_uniodonto_anual",
    "agrupar_por_titular",
    "obter_nomes_abas_anual",
    "DadosTitular",
    "validar_totais",
    "ResultadoValidacao",
]
