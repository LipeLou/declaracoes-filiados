# -*- coding: utf-8 -*-
"""
Mapeamento de campos do template PDF (exemplo-alexandre-irpf.pdf).

Coordenadas em pontos, origem canto superior esquerdo (PyMuPDF).
Página A4: 595.28 x 841.89 pt.

Estrutura do template:
- Página 1: Resumo (cabeçalho + NOME, CPF, LOTAÇÃO + tabela de totais por convênio + TOTAL + rodapé fixo)
- Página 2: Consultas UNIMED (tabela: nome, código família, valor)
- Página 3: Mensalidades UNIMED (tabela: nome, código cartão, valor)
- Página 4: Mensalidade UNIODONTO (tabela: nome, CPF, valor)
"""

PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89

# Índice de páginas por tipo (0-based) — modelo.pdf tem 5 páginas
PAGE_RESUMO = 0
PAGE_CONSULTAS = 1
PAGE_MENSALIDADES_RETRO = 2
PAGE_MENSALIDADES = 3
PAGE_UNIODONTO = 4

# Cabeçalho (comum às 4 páginas) — posições para sobrescrever
HEADER = {
    "titulo": (67.65, 155.44, 525.74, 168.85),  # "COMPROVANTE DE DESPESAS..."
    "ano": (225.90, 169.64, 343.26, 183.05),    # "RENDA - ANO BASE"
    "nome_value": (90.00, 212.09, 340.00, 225.49),
    "cpf_value": (90.00, 230.89, 220.00, 244.30),
}

# Cabeçalho por página (para evitar sobreposição no modelo novo)
HEADER_BY_PAGE = {
    PAGE_RESUMO: {
        "ano": (225.90, 169.64, 343.26, 183.05),
        "nome_value": (90.00, 212.09, 340.00, 225.49),
        "cpf_value": (90.00, 230.89, 220.00, 244.30),
    },
    PAGE_CONSULTAS: {
        "ano": (225.90, 165.996, 345.94, 179.403),
        "nome_value": (90.00, 208.45, 340.00, 221.85),
        "cpf_value": (90.00, 227.25, 220.00, 240.65),
    },
    PAGE_MENSALIDADES_RETRO: {
        "ano": (225.90, 169.64, 343.26, 183.05),
        "nome_value": (90.00, 212.09, 340.00, 225.49),
        "cpf_value": (90.00, 230.89, 220.00, 244.30),
    },
    PAGE_MENSALIDADES: {
        "ano": (225.90, 169.64, 343.26, 183.05),
        "nome_value": (90.00, 212.09, 340.00, 225.49),
        "cpf_value": (90.00, 230.89, 220.00, 244.30),
    },
    PAGE_UNIODONTO: {
        "ano": (225.90, 183.44, 343.26, 196.85),
        "nome_value": (90.00, 225.89, 340.00, 239.30),
        "cpf_value": (90.00, 244.69, 220.00, 258.10),
    },
}

# Página 1 — Resumo: tabela convênio / valor (até 3 linhas + total)
# Linhas de dados em y ≈ 301, 323, 346; total em 372
RESUMO = {
    "header_y": 290.00,
    "row_height": 22.0,
    "first_row_y": 312.00,
    "col_desc_left": 40.00,
    "col_desc_right": 340.00,
    "col_cnpj_left": 365.00,
    "col_cnpj_right": 450.00,
    "col_valor_left": 500.00,
    "col_valor_right": 560.00,
    "total_row_y": 372.00,
    "total_value_rect": (500.00, 372.00, 560.00, 385.40),
}

# Página 2 — Consultas: nome, código família, valor (linhas dinâmicas)
CONSULTAS = {
    "header_y": 290.00,
    "row_height": 22.0,
    "first_row_y": 312.00,
    "col_nome_left": 40.00,
    "col_nome_right": 340.00,
    "col_cod_left": 340.00,
    "col_cod_right": 450.00,
    "col_valor_left": 490.00,
    "col_valor_right": 560.00,
    "total_row_y": 372.00,
    "total_value_rect": (490.00, 372.00, 560.00, 385.40),
}

# Página 3 — Mensalidades: nome, código cartão, valor
MENSALIDADES_RETRO = {
    "header_y": 290.00,
    "row_height": 22.0,
    "first_row_y": 312.00,
    "col_nome_left": 40.00,
    "col_nome_right": 340.00,
    "col_cartao_left": 340.00,
    "col_cartao_right": 450.00,
    "col_valor_left": 490.00,
    "col_valor_right": 560.00,
    "total_row_y": 372.00,
    "total_value_rect": (490.00, 372.00, 560.00, 385.40),
}

MENSALIDADES = {
    "header_y": 290.00,
    "row_height": 22.0,
    "first_row_y": 312.00,
    "col_nome_left": 40.00,
    "col_nome_right": 340.00,
    "col_cartao_left": 340.00,
    "col_cartao_right": 450.00,
    "col_valor_left": 490.00,
    "col_valor_right": 560.00,
    "total_row_y": 372.00,
    "total_value_rect": (490.00, 372.00, 560.00, 385.40),
}

# Página 4 — Uniodonto: nome, CPF, valor
UNIODONTO = {
    "header_y": 290.00,
    "row_height": 22.0,
    "first_row_y": 312.00,
    "col_nome_left": 40.00,
    "col_nome_right": 340.00,
    "col_cpf_left": 340.00,
    "col_cpf_right": 450.00,
    "col_valor_left": 490.00,
    "col_valor_right": 560.00,
    "total_row_y": 372.00,
    "total_value_rect": (490.00, 372.00, 560.00, 385.40),
}

# Rodapé / assinatura (fixo, não sobrescrevemos)
# Área variável termina antes de y ≈ 414 (texto "Atesto que...")
