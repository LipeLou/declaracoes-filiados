# -*- coding: utf-8 -*-
"""
Geração do PDF do informe IRPF por titular.
Usa o template como base e sobrescreve os campos dinâmicos (PyMuPDF).
Suprime páginas sem gastos na categoria correspondente.
"""

import re
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF

from .models import DadosTitular, FilialRow
from . import pdf_layout as layout


def _fmt_valor(v: float) -> str:
    """Formata valor monetário no padrão brasileiro."""
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _draw_table_lines(page: fitz.Page, x_positions: list[float], row_starts: list[float], row_height: float, header_y: float | None = None) -> None:
    """Desenha linhas horizontais de uma tabela em posições definidas."""
    if (not row_starts and header_y is None) or len(x_positions) < 2:
        return
    top = header_y if header_y is not None else min(row_starts)
    color = (0, 0, 0)
    width = 1.4

    page.draw_line((x_positions[0], top), (x_positions[-1], top), color=color, width=width)
    if header_y is not None:
        page.draw_line((x_positions[0], header_y + row_height), (x_positions[-1], header_y + row_height), color=color, width=width)
    for y in row_starts:
        page.draw_line((x_positions[0], y + row_height), (x_positions[-1], y + row_height), color=color, width=width)

def _insert_bold(page: fitz.Page, x: float, y: float, text: str, fontsize: float = 10) -> None:
    # Simula negrito com duas passadas, evitando fontfile externo.
    page.insert_text((x, y), text, fontsize=fontsize, fontname="helv")
    page.insert_text((x + 0.4, y), text, fontsize=fontsize, fontname="helv")

def _insert_centered_text(
    page: fitz.Page,
    left: float,
    right: float,
    y: float,
    text: str,
    fontsize: float = 10,
    bold: bool = False,
) -> None:
    """Insere texto centralizado entre left/right com ajuste de fonte."""
    if not text:
        return
    text = str(text).upper()
    cell_width = max(right - left, 1)
    width = fitz.get_text_length(text, fontname="helv", fontsize=fontsize)
    if width > cell_width - 4:
        fontsize = max(7, fontsize * (cell_width - 4) / max(width, 1))
        width = fitz.get_text_length(text, fontname="helv", fontsize=fontsize)
    x = left + (cell_width - width) / 2
    if bold:
        _insert_bold(page, x, y, text, fontsize=fontsize)
    else:
        page.insert_text((x, y), text, fontsize=fontsize, fontname="helv")

def _insert_right_text(
    page: fitz.Page,
    left: float,
    right: float,
    y: float,
    text: str,
    fontsize: float = 10,
    bold: bool = False,
    padding: float = 78,
) -> None:
    """Insere texto alinhado à direita entre left/right com ajuste de fonte."""
    if not text:
        return
    text = str(text).upper()
    cell_width = max(right - left, 1)
    width = fitz.get_text_length(text, fontname="helv", fontsize=fontsize)
    if width > cell_width - (2 * padding):
        fontsize = max(7, fontsize * (cell_width - (2 * padding)) / max(width, 1))
        width = fitz.get_text_length(text, fontname="helv", fontsize=fontsize)
    x = right - width - padding
    if bold:
        _insert_bold(page, x, y, text, fontsize=fontsize)
    else:
        page.insert_text((x, y), text, fontsize=fontsize, fontname="helv")

def _compute_total_row_y(first_row_y: float, row_height: float, row_starts: list[float]) -> float:
    """Calcula a posição Y da linha de total da tabela."""
    if row_starts:
        return row_starts[-1] + row_height
    return first_row_y + row_height

def _cell_center_y(row_y: float, row_height: float, fontsize: float) -> float:
    """Centraliza verticalmente a linha de base do texto."""
    # Centraliza verticalmente a linha de base do texto
    return row_y + (row_height / 2) + (fontsize * 0.35)

def _draw_table_header(page: fitz.Page, header_y: float, row_height: float, labels: list[tuple], fontsize: float = 10) -> None:
    """Renderiza o cabeçalho de uma tabela."""
    for (left, right, text) in labels:
        _insert_centered_text(page, left, right, _cell_center_y(header_y, row_height, fontsize), text, fontsize=fontsize, bold=False)

def _inserir_resumo(page: fitz.Page, d: DadosTitular, ano: int) -> None:
    from .loader import _formatar_cpf_exibicao

    rects = [
        layout.HEADER["nome_value"],
        layout.HEADER["cpf_value"],
        layout.RESUMO["total_value_rect"],
        layout.HEADER["ano"],
    ]
    for i in range(4):
        y = layout.RESUMO["first_row_y"] + i * layout.RESUMO["row_height"]
        rects.append((layout.RESUMO["col_desc_left"], y, layout.RESUMO["col_valor_right"], y + layout.RESUMO["row_height"]))

    for r in rects:
        page.add_redact_annot(r, text="", fill=(1, 1, 1))
    page.apply_redactions()

    page.insert_text((layout.HEADER["nome_value"][0], layout.HEADER["nome_value"][1] + 11), d.nome_titular[:50], fontsize=10, fontname="helv")
    page.insert_text((layout.HEADER["cpf_value"][0], layout.HEADER["cpf_value"][1] + 11), _formatar_cpf_exibicao(d.cpf_titular), fontsize=10, fontname="helv")
    page.insert_text((layout.HEADER["ano"][0], layout.HEADER["ano"][1] + 12), f"RENDA - ANO BASE {ano}", fontsize=12, fontname="helv")

    row_y = layout.RESUMO["first_row_y"]
    linhas_resumo = []
    if d.total_uniodonto > 0:
        linhas_resumo.append(("Uniodonto Itajubá Mensalidades", d.total_uniodonto))
    if d.total_consultas > 0:
        linhas_resumo.append(("Consultas pela Unimed do Governo", d.total_consultas))
    if d.total_mensalidades > 0:
        linhas_resumo.append(("Unimed Plano do Governo", d.total_mensalidades))
    if d.total_mensalidades_retro > 0:
        linhas_resumo.append(("Unimed Plano Retroativo", d.total_mensalidades_retro))

    row_starts = []
    for i, (desc, val) in enumerate(linhas_resumo):
        if i >= 3:
            break
        y = row_y + i * layout.RESUMO["row_height"]
        row_starts.append(y)
        _insert_centered_text(
            page,
            layout.RESUMO["col_desc_left"],
            layout.RESUMO["col_desc_right"],
            _cell_center_y(y, layout.RESUMO["row_height"], 10),
            desc[:45],
            fontsize=10,
            bold=False,
        )
        _insert_centered_text(
            page,
            layout.RESUMO["col_valor_left"],
            layout.RESUMO["col_valor_right"],
            _cell_center_y(y, layout.RESUMO["row_height"], 10),
            _fmt_valor(val),
            fontsize=10,
            bold=False,
        )

    total_y = _compute_total_row_y(layout.RESUMO["first_row_y"], layout.RESUMO["row_height"], row_starts)
    _insert_centered_text(
        page,
        layout.RESUMO["col_valor_left"],
        layout.RESUMO["col_valor_right"],
        _cell_center_y(total_y, layout.RESUMO["row_height"], 10),
        _fmt_valor(d.total_geral),
        fontsize=10,
        bold=True,
    )
    _insert_centered_text(
        page,
        layout.RESUMO["col_desc_left"],
        layout.RESUMO["col_desc_right"],
        _cell_center_y(total_y, layout.RESUMO["row_height"], 10),
        "TOTAL DE GASTOS",
        fontsize=10,
        bold=True,
    )
    row_starts.append(total_y)
    _draw_table_header(
        page,
        layout.RESUMO["header_y"],
        layout.RESUMO["row_height"],
        [
            (layout.RESUMO["col_desc_left"], layout.RESUMO["col_desc_right"], "NOME DO CONVÊNIO"),
            (layout.RESUMO["col_cnpj_left"], layout.RESUMO["col_cnpj_right"], "C N P J / C P F"),
            (layout.RESUMO["col_valor_left"], layout.RESUMO["col_valor_right"], "VALOR"),
        ],
        fontsize=9,
    )
    _draw_table_lines(
        page,
        [
            layout.RESUMO["col_desc_left"],
            layout.RESUMO["col_cnpj_left"],
            layout.RESUMO["col_valor_left"],
            layout.RESUMO["col_valor_right"],
        ],
        row_starts,
        layout.RESUMO["row_height"],
        header_y=layout.RESUMO["header_y"],
    )


def _inserir_consultas(page: fitz.Page, d: DadosTitular) -> None:
    cfg = layout.CONSULTAS
    row_y = cfg["first_row_y"]
    row_starts = []
    for i, lin in enumerate(d.linhas_consultas):
        y = row_y + i * cfg["row_height"]
        page.add_redact_annot((cfg["col_nome_left"], y, cfg["col_valor_right"], y + cfg["row_height"]), text="", fill=(1, 1, 1))
        row_starts.append(y)
    page.add_redact_annot(cfg["total_value_rect"], text="", fill=(1, 1, 1))
    page.apply_redactions()

    for i, lin in enumerate(d.linhas_consultas):
        y = row_y + i * cfg["row_height"]
        _insert_right_text(page, cfg["col_nome_left"], cfg["col_nome_right"], _cell_center_y(y, cfg["row_height"], 10), lin.nome[:45], fontsize=10, bold=False)
        _insert_centered_text(page, cfg["col_cod_left"], cfg["col_cod_right"], _cell_center_y(y, cfg["row_height"], 10), lin.codigo_familia[:15], fontsize=10, bold=False)
        _insert_centered_text(page, cfg["col_valor_left"], cfg["col_valor_right"], _cell_center_y(y, cfg["row_height"], 10), _fmt_valor(lin.valor), fontsize=10, bold=False)

    total_y = _compute_total_row_y(cfg["first_row_y"], cfg["row_height"], row_starts)
    _insert_centered_text(page, cfg["col_valor_left"], cfg["col_valor_right"], _cell_center_y(total_y, cfg["row_height"], 10), _fmt_valor(d.total_consultas), fontsize=10, bold=True)
    _insert_right_text(page, cfg["col_nome_left"], cfg["col_nome_right"], _cell_center_y(total_y, cfg["row_height"], 10), "TOTAL DE GASTOS", fontsize=10, bold=True)
    row_starts.append(total_y)
    _draw_table_header(
        page,
        cfg["header_y"],
        cfg["row_height"],
        [
            (cfg["col_nome_left"], cfg["col_nome_right"], "Consultas UNIMED Itajubá"),
            (cfg["col_cod_left"], cfg["col_cod_right"], "CÓDIGO FAMÍLIA"),
            (cfg["col_valor_left"], cfg["col_valor_right"], "VALOR R$"),
        ],
        fontsize=9,
    )
    _draw_table_lines(
        page,
        [cfg["col_nome_left"], cfg["col_cod_left"], cfg["col_valor_left"], cfg["col_valor_right"]],
        row_starts,
        cfg["row_height"],
        header_y=cfg["header_y"],
    )


def _inserir_mensalidades(page: fitz.Page, d: DadosTitular) -> None:
    cfg = layout.MENSALIDADES
    row_y = cfg["first_row_y"]
    row_starts = []
    for i, lin in enumerate(d.linhas_mensalidades):
        y = row_y + i * cfg["row_height"]
        page.add_redact_annot((cfg["col_nome_left"], y, cfg["col_valor_right"], y + cfg["row_height"]), text="", fill=(1, 1, 1))
        row_starts.append(y)
    page.add_redact_annot(cfg["total_value_rect"], text="", fill=(1, 1, 1))
    page.apply_redactions()

    for i, lin in enumerate(d.linhas_mensalidades):
        y = row_y + i * cfg["row_height"]
        _insert_right_text(page, cfg["col_nome_left"], cfg["col_nome_right"], _cell_center_y(y, cfg["row_height"], 10), lin.nome[:45], fontsize=10, bold=False)
        _insert_centered_text(page, cfg["col_cartao_left"], cfg["col_cartao_right"], _cell_center_y(y, cfg["row_height"], 10), lin.carteira[:18], fontsize=10, bold=False)
        _insert_centered_text(page, cfg["col_valor_left"], cfg["col_valor_right"], _cell_center_y(y, cfg["row_height"], 10), _fmt_valor(lin.valor), fontsize=10, bold=False)

    total_y = _compute_total_row_y(cfg["first_row_y"], cfg["row_height"], row_starts)
    _insert_centered_text(page, cfg["col_valor_left"], cfg["col_valor_right"], _cell_center_y(total_y, cfg["row_height"], 10), _fmt_valor(d.total_mensalidades), fontsize=10, bold=True)
    _insert_right_text(page, cfg["col_nome_left"], cfg["col_nome_right"], _cell_center_y(total_y, cfg["row_height"], 10), "TOTAL DE GASTOS", fontsize=10, bold=True)
    row_starts.append(total_y)
    _draw_table_header(
        page,
        cfg["header_y"],
        cfg["row_height"],
        [
            (cfg["col_nome_left"], cfg["col_nome_right"], "Mensalidade UNIMED Itajubá"),
            (cfg["col_cartao_left"], cfg["col_cartao_right"], "CÓDIGO CARTÃO"),
            (cfg["col_valor_left"], cfg["col_valor_right"], "VALOR R$"),
        ],
        fontsize=9,
    )
    _draw_table_lines(
        page,
        [cfg["col_nome_left"], cfg["col_cartao_left"], cfg["col_valor_left"], cfg["col_valor_right"]],
        row_starts,
        cfg["row_height"],
        header_y=cfg["header_y"],
    )


def _inserir_mensalidades_retro(page: fitz.Page, d: DadosTitular) -> None:
    cfg = layout.MENSALIDADES_RETRO
    row_y = cfg["first_row_y"]
    row_starts = []
    for i, lin in enumerate(d.linhas_mensalidades_retro):
        y = row_y + i * cfg["row_height"]
        page.add_redact_annot((cfg["col_nome_left"], y, cfg["col_valor_right"], y + cfg["row_height"]), text="", fill=(1, 1, 1))
        row_starts.append(y)
    page.add_redact_annot(cfg["total_value_rect"], text="", fill=(1, 1, 1))
    page.apply_redactions()

    for i, lin in enumerate(d.linhas_mensalidades_retro):
        y = row_y + i * cfg["row_height"]
        _insert_right_text(page, cfg["col_nome_left"], cfg["col_nome_right"], _cell_center_y(y, cfg["row_height"], 10), lin.nome[:45], fontsize=10, bold=False)
        _insert_centered_text(page, cfg["col_cartao_left"], cfg["col_cartao_right"], _cell_center_y(y, cfg["row_height"], 10), lin.carteira[:18], fontsize=10, bold=False)
        _insert_centered_text(page, cfg["col_valor_left"], cfg["col_valor_right"], _cell_center_y(y, cfg["row_height"], 10), _fmt_valor(lin.valor), fontsize=10, bold=False)

    total_y = _compute_total_row_y(cfg["first_row_y"], cfg["row_height"], row_starts)
    _insert_centered_text(page, cfg["col_valor_left"], cfg["col_valor_right"], _cell_center_y(total_y, cfg["row_height"], 10), _fmt_valor(d.total_mensalidades_retro), fontsize=10, bold=True)
    _insert_right_text(page, cfg["col_nome_left"], cfg["col_nome_right"], _cell_center_y(total_y, cfg["row_height"], 10), "TOTAL DE GASTOS", fontsize=10, bold=True)
    row_starts.append(total_y)
    _draw_table_header(
        page,
        cfg["header_y"],
        cfg["row_height"],
        [
            (cfg["col_nome_left"], cfg["col_nome_right"], "Mensalidade Retroativa UNIMED Itajubá"),
            (cfg["col_cartao_left"], cfg["col_cartao_right"], "CÓDIGO CARTÃO"),
            (cfg["col_valor_left"], cfg["col_valor_right"], "VALOR R$"),
        ],
        fontsize=9,
    )
    _draw_table_lines(
        page,
        [cfg["col_nome_left"], cfg["col_cartao_left"], cfg["col_valor_left"], cfg["col_valor_right"]],
        row_starts,
        cfg["row_height"],
        header_y=cfg["header_y"],
    )


def _inserir_uniodonto(page: fitz.Page, d: DadosTitular) -> None:
    from .loader import _formatar_cpf_exibicao

    cfg = layout.UNIODONTO
    row_y = cfg["first_row_y"]
    row_starts = []
    for i, lin in enumerate(d.linhas_uniodonto):
        y = row_y + i * cfg["row_height"]
        page.add_redact_annot((cfg["col_nome_left"], y, cfg["col_valor_right"], y + cfg["row_height"]), text="", fill=(1, 1, 1))
        row_starts.append(y)
    page.add_redact_annot(cfg["total_value_rect"], text="", fill=(1, 1, 1))
    page.apply_redactions()

    for i, lin in enumerate(d.linhas_uniodonto):
        y = row_y + i * cfg["row_height"]
        _insert_right_text(page, cfg["col_nome_left"], cfg["col_nome_right"], _cell_center_y(y, cfg["row_height"], 10), lin.nome[:45], fontsize=10, bold=False)
        _insert_centered_text(page, cfg["col_cpf_left"], cfg["col_cpf_right"], _cell_center_y(y, cfg["row_height"], 10), _formatar_cpf_exibicao(lin.cpf) if lin.cpf else "", fontsize=10, bold=False)
        _insert_centered_text(page, cfg["col_valor_left"], cfg["col_valor_right"], _cell_center_y(y, cfg["row_height"], 10), _fmt_valor(lin.valor), fontsize=10, bold=False)

    total_y = _compute_total_row_y(cfg["first_row_y"], cfg["row_height"], row_starts)
    _insert_centered_text(page, cfg["col_valor_left"], cfg["col_valor_right"], _cell_center_y(total_y, cfg["row_height"], 10), _fmt_valor(d.total_uniodonto), fontsize=10, bold=True)
    _insert_right_text(page, cfg["col_nome_left"], cfg["col_nome_right"], _cell_center_y(total_y, cfg["row_height"], 10), "TOTAL DE GASTOS", fontsize=10, bold=True)
    row_starts.append(total_y)
    _draw_table_header(
        page,
        cfg["header_y"],
        cfg["row_height"],
        [
            (cfg["col_nome_left"], cfg["col_nome_right"], "Mensalidade UNIODONTO"),
            (cfg["col_cpf_left"], cfg["col_cpf_right"], "CPF"),
            (cfg["col_valor_left"], cfg["col_valor_right"], "VALOR R$"),
        ],
        fontsize=9,
    )
    _draw_table_lines(
        page,
        [cfg["col_nome_left"], cfg["col_cpf_left"], cfg["col_valor_left"], cfg["col_valor_right"]],
        row_starts,
        cfg["row_height"],
        header_y=cfg["header_y"],
    )


def _copiar_cabecalho(page_dest: fitz.Page, d: DadosTitular, ano: int, page_index: int) -> None:
    """Sobrescreve apenas cabeçalho (nome, CPF) na página."""
    from .loader import _formatar_cpf_exibicao

    header = layout.HEADER_BY_PAGE.get(page_index, layout.HEADER)
    for key in ["nome_value", "cpf_value"]:
        r = header[key]
        page_dest.add_redact_annot(r, text="", fill=(1, 1, 1))
    page_dest.apply_redactions()

    page_dest.insert_text((header["nome_value"][0], header["nome_value"][1] + 11), d.nome_titular[:50], fontsize=10, fontname="helv")
    page_dest.insert_text((header["cpf_value"][0], header["cpf_value"][1] + 11), _formatar_cpf_exibicao(d.cpf_titular), fontsize=10, fontname="helv")

    page_dest.add_redact_annot(header["ano"], text="", fill=(1, 1, 1))
    page_dest.apply_redactions()
    page_dest.insert_text((header["ano"][0], header["ano"][1] + 12), f"RENDA - ANO BASE {ano}", fontsize=12, fontname="helv")


def gerar_pdf_titular(
    d: DadosTitular,
    template_path: str | Path,
    ano: int,
    pasta_saida: str | Path,
    nome_arquivo: Optional[str] = None,
) -> Path:
    """
    Gera o PDF do informe para um titular e salva em pasta_saida.
    Nome do arquivo: NOME_DO_FILIADO_CPF_IRPF<ANO>.pdf (espaços e caracteres especiais normalizados).
    Retorna o Path do arquivo gerado.
    """
    template_path = Path(template_path)
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    if d.total_geral <= 0 and not d.linhas_consultas and not d.linhas_mensalidades and not d.linhas_uniodonto:
        raise ValueError("Titular sem nenhum gasto; não gerar PDF.")

    if nome_arquivo is None:
        nome_safe = re.sub(r"[^\w\s-]", "", d.nome_titular)
        nome_safe = re.sub(r"\s+", "_", nome_safe).strip("_") or "Titular"
        cpf_safe = d.cpf_titular.replace(".", "").replace("-", "").replace("/", "")
        nome_arquivo = f"{nome_safe}_{cpf_safe}_IRPF{ano}.pdf"

    doc_tpl = fitz.open(template_path)
    doc_out = fitz.open()

    # Página 1: Resumo (sempre que houver algum gasto)
    if d.total_geral > 0:
        doc_out.insert_pdf(doc_tpl, from_page=layout.PAGE_RESUMO, to_page=layout.PAGE_RESUMO)
        _inserir_resumo(doc_out[0], d, ano)

    # Página 2: Consultas (somente se houver)
    if d.tem_consultas():
        doc_out.insert_pdf(doc_tpl, from_page=layout.PAGE_CONSULTAS, to_page=layout.PAGE_CONSULTAS)
        _copiar_cabecalho(doc_out[len(doc_out) - 1], d, ano, layout.PAGE_CONSULTAS)
        _inserir_consultas(doc_out[len(doc_out) - 1], d)

    # Página 3: Mensalidades Retroativas
    if d.tem_mensalidades_retro():
        doc_out.insert_pdf(doc_tpl, from_page=layout.PAGE_MENSALIDADES_RETRO, to_page=layout.PAGE_MENSALIDADES_RETRO)
        _copiar_cabecalho(doc_out[len(doc_out) - 1], d, ano, layout.PAGE_MENSALIDADES_RETRO)
        _inserir_mensalidades_retro(doc_out[len(doc_out) - 1], d)

    # Página 4: Mensalidades
    if d.tem_mensalidades():
        doc_out.insert_pdf(doc_tpl, from_page=layout.PAGE_MENSALIDADES, to_page=layout.PAGE_MENSALIDADES)
        _copiar_cabecalho(doc_out[len(doc_out) - 1], d, ano, layout.PAGE_MENSALIDADES)
        _inserir_mensalidades(doc_out[len(doc_out) - 1], d)

    # Página 5: Uniodonto
    if d.tem_uniodonto():
        doc_out.insert_pdf(doc_tpl, from_page=layout.PAGE_UNIODONTO, to_page=layout.PAGE_UNIODONTO)
        _copiar_cabecalho(doc_out[len(doc_out) - 1], d, ano, layout.PAGE_UNIODONTO)
        _inserir_uniodonto(doc_out[len(doc_out) - 1], d)

    # Se não incluímos nenhuma página (caso limite), não faz sentido gerar PDF vazio
    if len(doc_out) == 0:
        doc_tpl.close()
        doc_out.close()
        raise ValueError("Nenhuma página gerada para o titular.")

    out_path = pasta_saida / nome_arquivo
    doc_out.save(str(out_path))
    doc_out.close()
    doc_tpl.close()

    return out_path
