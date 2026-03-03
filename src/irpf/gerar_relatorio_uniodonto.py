#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera relatório anual da Uniodonto em Excel, consolidado por beneficiário.

Saída:
- Colunas: Nome, Cpf, JAN, FEV, ..., DEZ, TOTAL
- Linhas: todos os beneficiários (titulares e dependentes) com movimentação
  na Uniodonto ao longo do ano.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
import yaml

# Raiz do projeto (subir de src/irpf/ para a raiz)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.irpf.loader import (
    carregar_planilha_uniodonto,
    obter_nomes_abas_anual,
)


MESES_ABREV = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]


def carregar_config(caminho: Path) -> dict:
    with open(caminho, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def mes_para_abrev(sheet_name: str) -> str:
    """
    Extrai abreviação do mês de um nome de aba.
    Ex.: "JAN 2025" -> "JAN"
    """
    token = str(sheet_name).strip().upper().split()[0] if str(sheet_name).strip() else ""
    token = re.sub(r"[^A-Z]", "", token)
    if token in MESES_ABREV:
        return token
    raise ValueError(f"Não foi possível identificar mês da aba: {sheet_name}")


def chave_beneficiario(nome: str, cpf: str) -> Tuple[str, str]:
    nome_norm = str(nome or "").strip()
    cpf_norm = str(cpf or "").strip()
    return (cpf_norm, nome_norm.upper())


def gerar_relatorio_anual_uniodonto(planilha: Path, sheet_names: list[str]) -> pd.DataFrame:
    """
    Consolida valores mensais da Uniodonto por beneficiário, agrupando por família
    (titular + dependentes) e deixando uma linha em branco entre famílias.
    """
    # índice interno:
    # family_key -> { (cpf, nome_upper) -> registro }
    acumulado_familias: Dict[str, Dict[Tuple[str, str], Dict[str, object]]] = {}

    for sheet_name in sheet_names:
        mes = mes_para_abrev(sheet_name)
        mapa_titular = carregar_planilha_uniodonto(planilha, sheet_name=sheet_name)

        for family_key, linhas in mapa_titular.items():
            familia = acumulado_familias.setdefault(family_key, {})
            for linha in linhas:
                nome = str(linha.nome or "").strip()
                cpf = str(linha.cpf or "").strip()
                valor = float(linha.valor or 0.0)
                if not nome:
                    continue
                if valor <= 0:
                    continue

                ben_key = chave_beneficiario(nome, cpf)
                if ben_key not in familia:
                    familia[ben_key] = {
                        "Nome": nome,
                        "Cpf": cpf,
                        **{m: 0.0 for m in MESES_ABREV},
                    }
                familia[ben_key][mes] += valor

    rows = []
    colunas = ["Nome", "Cpf", *MESES_ABREV, "TOTAL"]

    for family_key in sorted(acumulado_familias.keys()):
        familia = acumulado_familias[family_key]
        beneficiarios = sorted(
            familia.values(),
            key=lambda r: (str(r["Nome"]).upper(), str(r["Cpf"])),
        )
        for registro in beneficiarios:
            total = sum(float(registro[m]) for m in MESES_ABREV)
            row = {
                "Nome": registro["Nome"],
                "Cpf": registro["Cpf"],
                **{m: round(float(registro[m]), 2) for m in MESES_ABREV},
                "TOTAL": round(total, 2),
            }
            rows.append(row)

        # Linha vazia para separar famílias (removida no final)
        rows.append({c: "" for c in colunas})

    if not rows:
        return pd.DataFrame(columns=colunas)

    # Remove última linha vazia
    if all(str(rows[-1].get(c, "")) == "" for c in colunas):
        rows.pop()

    df = pd.DataFrame(rows)
    return df[colunas]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gerar relatório anual da Uniodonto (Nome/Cpf/JAN..DEZ/TOTAL)."
    )
    parser.add_argument(
        "-c",
        "--config",
        default=ROOT / "config" / "irpf.yml",
        type=Path,
        help="Caminho do arquivo de configuração YAML",
    )
    parser.add_argument(
        "--planilha-uniodonto",
        type=Path,
        help="Sobrescreve planilha_uniodonto do config",
    )
    parser.add_argument(
        "--ano",
        type=int,
        default=None,
        help="Ano base (sobrescreve config)",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        help="Lista de abas separadas por vírgula; senão usa JAN..DEZ do ano",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Arquivo Excel de saída (.xlsx)",
    )
    args = parser.parse_args()

    config_path = args.config
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    if not config_path.exists():
        print(f"ERRO: Arquivo de configuração não encontrado: {config_path}")
        return 1

    config = carregar_config(config_path)
    ano = args.ano or config.get("ano_base", 2024)

    planilha = args.planilha_uniodonto or config.get("planilha_uniodonto")
    if not planilha:
        print("ERRO: planilha_uniodonto não informada no config nem por argumento.")
        return 1
    planilha = Path(planilha)
    if not planilha.is_absolute():
        planilha = ROOT / planilha
    if not planilha.exists():
        print(f"ERRO: Planilha Uniodonto não encontrada: {planilha}")
        return 1

    if args.sheet:
        sheet_names = [s.strip() for s in args.sheet.split(",") if s.strip()]
    else:
        sheet_names = obter_nomes_abas_anual(ano)
    if not sheet_names:
        print("ERRO: Nenhuma aba configurada para leitura.")
        return 1

    output = args.output or (ROOT / f"relatorio_uniodonto_{ano}.xlsx")
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)

    df = gerar_relatorio_anual_uniodonto(planilha, sheet_names)
    df.to_excel(output, index=False)
    beneficiarios = int(df["Nome"].astype(str).str.strip().ne("").sum()) if "Nome" in df.columns else 0

    print(f"Relatório gerado: {output}")
    print(f"Beneficiários: {beneficiarios}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
