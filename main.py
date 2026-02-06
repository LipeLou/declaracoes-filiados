#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script principal: execução em lote do gerador de informes IRPF.
Lê configuração (config/irpf.yml), planilhas Unimed, valida totais,
gera um PDF por titular em pasta configurável.
Nome dos arquivos: NOME_DO_FILIADO_CPF_IRPF<ANO>.pdf
"""

import argparse
import logging
import sys
import warnings
from pathlib import Path

# Permitir import do pacote src quando executado a partir da raiz do projeto
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml

from src.irpf.loader import (
    carregar_planilha_unimed_anual,
    carregar_planilha_uniodonto_anual,
    agrupar_por_titular,
    obter_nomes_abas_anual,
)
from src.irpf.models import DadosTitular
from src.irpf.validator import validar_totais, ResultadoValidacao
from src.irpf.pdf_generator import gerar_pdf_titular


def carregar_config(caminho: Path) -> dict:
    """Carrega arquivo de configuração YAML."""
    with open(caminho, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    """Executa o fluxo principal de geração de informes IRPF."""
    warnings.filterwarnings(
        "ignore",
        message=r"Unknown type for Business Objects.*",
        category=UserWarning,
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    log = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Gerar informes IRPF em lote.")
    parser.add_argument(
        "-c", "--config",
        default=ROOT / "config" / "irpf.yml",
        type=Path,
        help="Caminho do arquivo de configuração YAML",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Sobrescreve pasta_saida do config",
    )
    parser.add_argument(
        "--planilha",
        type=Path,
        help="Sobrescreve planilha_unimed do config",
    )
    parser.add_argument(
        "--planilha-uniodonto",
        type=Path,
        help="Planilha Uniodonto (opcional)",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        help="(Opcional) Lista de abas separadas por vírgula; senão usa 12 abas JAN-DEZ do ano",
    )
    parser.add_argument(
        "--ano",
        type=int,
        default=None,
        help="Ano base (sobrescreve config)",
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Apenas carregar e validar, sem gerar PDFs",
    )
    args = parser.parse_args()

    config_path = args.config
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    if not config_path.exists():
        log.error("Arquivo de configuração não encontrado: %s", config_path)
        return 1

    config = carregar_config(config_path)
    ano = args.ano or config.get("ano_base", 2024)
    pasta_saida = args.output or Path(config.get("pasta_saida", "./saida_informes_irpf"))
    if not pasta_saida.is_absolute():
        pasta_saida = ROOT / pasta_saida

    planilha_path = args.planilha or Path(config.get("planilha_unimed", ""))
    if not planilha_path.is_absolute():
        planilha_path = ROOT / planilha_path
    if not planilha_path.exists():
        log.error("Planilha Unimed não encontrada: %s", planilha_path)
        return 1

    template_path = Path(config.get("template_pdf", "Data/exemplo-alexandre-irpf.pdf"))
    if not template_path.is_absolute():
        template_path = ROOT / template_path
    if not template_path.exists():
        log.error("Template PDF não encontrado: %s", template_path)
        return 1

    # Lista de abas mensais: config/args ou padrão JAN <ano> .. DEZ <ano>
    abas_config = config.get("abas_mensais")
    if args.sheet:
        sheet_names = [s.strip() for s in args.sheet.split(",") if s.strip()]
    elif abas_config:
        sheet_names = list(abas_config) if isinstance(abas_config, (list, tuple)) else [str(abas_config)]
    else:
        sheet_names = obter_nomes_abas_anual(ano)
    if len(sheet_names) == 0:
        log.error("Nenhuma aba configurada para leitura.")
        return 1

    uniodonto_path = args.planilha_uniodonto or config.get("planilha_uniodonto")
    uniodonto_map = None
    cnpj_map = {
        "uniodonto": config.get("cnpj_uniodonto_itajuba"),
        "consultas": config.get("cnpj_consultas_unimed_governo"),
        "mensalidades": config.get("cnpj_unimed_plano_governo"),
    }

    log.info("Carregando planilha Unimed: %s (%d abas)", planilha_path, len(sheet_names))
    df = carregar_planilha_unimed_anual(planilha_path, sheet_names)
    if uniodonto_path:
        uniodonto_path = Path(uniodonto_path)
        if not uniodonto_path.is_absolute():
            uniodonto_path = ROOT / uniodonto_path
        if not uniodonto_path.exists():
            log.error("Planilha Uniodonto não encontrada: %s", uniodonto_path)
            return 1
        log.info("Carregando Uniodonto: %s (%d abas)", uniodonto_path, len(sheet_names))
        uniodonto_map = carregar_planilha_uniodonto_anual(uniodonto_path, sheet_names)
    titulares = agrupar_por_titular(df, uniodonto_map=uniodonto_map)
    log.info("Agrupados %d titulares por CPF.", len(titulares))

    resultado = validar_totais(titulares)
    resultado.registrar_log(log)
    if not resultado.ok:
        log.warning("Existem inconsistências; continuando mesmo assim.")

    if args.dry_run:
        log.info("Simulação: nenhum PDF gerado.")
        return 0

    gerados = 0
    erros = 0
    try:
        for d in titulares:
            if d.total_geral <= 0 and not d.linhas_consultas and not d.linhas_mensalidades and not d.linhas_uniodonto:
                log.debug("Titular %s sem gastos; pulando.", d.cpf_titular)
                continue
            try:
                out_path = gerar_pdf_titular(d, template_path, ano, pasta_saida, cnpjs=cnpj_map)
                gerados += 1
                log.info("Gerado: %s", out_path.name)
            except Exception as e:
                erros += 1
                log.exception("Erro ao gerar PDF para %s: %s", d.cpf_titular, e)
    except KeyboardInterrupt:
        log.warning("Execução interrompida pelo usuário.")
        return 130

    log.info("Concluído: %d PDF(s) gerado(s), %d erro(s).", gerados, erros)
    return 0 if erros == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
