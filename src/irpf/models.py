# -*- coding: utf-8 -*-
"""Estruturas de dados por titular para geração do informe IRPF."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class FilialRow:
    """Uma linha de detalhe (consultas, mensalidades ou uniodonto)."""
    nome: str
    valor: float
    codigo_familia: str = ""   # para consultas
    carteira: str = ""         # para mensalidades
    cpf: str = ""              # para uniodonto


@dataclass
class DadosTitular:
    """Dados agregados por titular (CPF do titular) para um informe."""
    cpf_titular: str
    nome_titular: str
    # Resumo (página 1)
    total_consultas: float
    total_mensalidades: float
    total_mensalidades_retro: float
    total_uniodonto: float
    total_unimed_bh: float
    # Detalhes para cada página
    linhas_consultas: List[FilialRow] = field(default_factory=list)
    linhas_mensalidades: List[FilialRow] = field(default_factory=list)
    linhas_mensalidades_retro: List[FilialRow] = field(default_factory=list)
    linhas_uniodonto: List[FilialRow] = field(default_factory=list)
    linhas_unimed_bh: List[FilialRow] = field(default_factory=list)

    @property
    def total_geral(self) -> float:
        return (
            self.total_consultas
            + self.total_mensalidades
            + self.total_mensalidades_retro
            + self.total_uniodonto
            + self.total_unimed_bh
        )

    def tem_consultas(self) -> bool:
        return self.total_consultas > 0

    def tem_mensalidades(self) -> bool:
        return self.total_mensalidades > 0

    def tem_mensalidades_retro(self) -> bool:
        return self.total_mensalidades_retro > 0

    def tem_uniodonto(self) -> bool:
        return self.total_uniodonto > 0

    def tem_unimed_bh(self) -> bool:
        return self.total_unimed_bh > 0
