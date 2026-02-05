# -*- coding: utf-8 -*-
"""
Leitura e normalização das planilhas Unimed (e Uniodonto futura).
Agrupamento por CPF do titular.
"""

import re
import warnings
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .models import DadosTitular, FilialRow


def _normalizar_cpf(cpf: object) -> str:
    """Remove formatação e retorna apenas dígitos; vazio se inválido."""
    if pd.isna(cpf):
        return ""
    s = str(cpf).strip()
    digits = re.sub(r"\D", "", s)
    return digits if len(digits) == 11 else ""


def _formatar_cpf_exibicao(cpf: str) -> str:
    """Formato XXX.XXX.XXX-XX para exibição no PDF."""
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def _normalizar_nome(nome: object) -> str:
    """Converte o nome para string limpa e sem espaços extras."""
    if pd.isna(nome):
        return ""
    return str(nome).strip()


def _normalizar_nome_chave(nome: object) -> str:
    """Normaliza nome para chave de comparação (maiúsculas)."""
    return _normalizar_nome(nome).upper()


def _normalizar_codigo(val: object) -> str:
    """Normaliza códigos numéricos e texto para comparação/agrupamento."""
    if pd.isna(val):
        return ""
    return str(int(val)) if isinstance(val, (int, float)) else str(val).strip()


def carregar_planilha_unimed(
    caminho: str | Path,
    sheet_name: Optional[str] = None,
    skiprows: int = 1,
) -> pd.DataFrame:
    """
    Carrega a planilha Unimed (Excel).
    Espera colunas: NOME, CPF, DEPENDENCIA, MENSALIDADE, CONSULTA, CARTEIRA, CÓD DA FAMILIA (ou similar).
    """
    path = Path(caminho)
    if not path.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {path}")

    kwargs = {"skiprows": skiprows}
    if sheet_name is not None:
        kwargs["sheet_name"] = sheet_name

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Unknown type for Business Objects.*",
            category=UserWarning,
        )
        df = pd.read_excel(path, **kwargs)

    # Normalizar nomes de colunas (maiúsculas, strip)
    df.columns = [str(c).strip().upper() for c in df.columns]

    # Mapear variações de nome de coluna
    cod_fam = None
    for c in df.columns:
        if "FAMILIA" in c or "FAMÍLIA" in c.upper().replace("Í", "I"):
            cod_fam = c
            break
    if cod_fam is None and "CÓD DA FAMILIA" in df.columns:
        cod_fam = "CÓD DA FAMILIA"

    required = ["NOME", "CPF", "DEPENDENCIA", "MENSALIDADE", "CONSULTA"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Coluna obrigatória ausente: {col}")

    if "CARTEIRA" not in df.columns:
        df["CARTEIRA"] = ""
    if "RETROATIVO" not in df.columns:
        df["RETROATIVO"] = 0.0
    if "RETROATIVO RN" not in df.columns:
        df["RETROATIVO RN"] = 0.0
    if cod_fam and cod_fam not in df.columns:
        df[cod_fam] = ""

    return df


def carregar_planilha_uniodonto(
    caminho: str | Path,
    sheet_name: Optional[str] = None,
) -> Dict[str, List[FilialRow]]:
    """
    Lê a planilha Uniodonto e retorna um mapa:
    {NOME_TITULAR_NORMALIZADO: [FilialRow(nome, cpf, valor)]}

    Regras:
    - Titular é identificado quando 'ID do Usuário' contém 'Usuário Responsável:'.
    - Para cada linha do grupo, incluir se Parentesco != 'AGREGADO(A)'.
    """
    path = Path(caminho)
    if not path.exists():
        raise FileNotFoundError(f"Planilha Uniodonto não encontrada: {path}")

    kwargs = {}
    if sheet_name is not None:
        kwargs["sheet_name"] = sheet_name

    df = pd.read_excel(path, **kwargs)
    df.columns = [str(c).strip() for c in df.columns]
    col_map = {c.casefold(): c for c in df.columns}

    required = ["id do usuário", "nome do usuário", "parentesco", "cpf", "mensalidade"]
    for col in required:
        if col not in col_map:
            raise ValueError(f"Coluna obrigatória ausente na Uniodonto: {col}")

    col_id = col_map["id do usuário"]
    col_nome = col_map["nome do usuário"]
    col_parentesco = col_map["parentesco"]
    col_cpf = col_map["cpf"]
    col_mensalidade = col_map["mensalidade"]

    mapa: Dict[str, List[FilialRow]] = {}
    titular_atual = ""

    for _, row in df.iterrows():
        id_usuario = str(row.get(col_id, "")).strip()
        if "Usuário Responsável:" in id_usuario:
            trecho = id_usuario.split("Usuário Responsável:", 1)[-1].strip()
            if " - CPF:" in trecho:
                nome_titular, cpf_titular = trecho.split(" - CPF:", 1)
                nome_titular = _normalizar_nome_chave(nome_titular)
                cpf_titular = _normalizar_cpf(cpf_titular)
            else:
                nome_titular = _normalizar_nome_chave(trecho)
                cpf_titular = ""
            titular_atual = f"{nome_titular}|{cpf_titular}"
            mapa.setdefault(titular_atual, [])
            continue

        if not titular_atual:
            continue

        nome_raw = row.get(col_nome, "")
        if pd.isna(nome_raw) or str(nome_raw).strip() == "":
            continue

        parentesco = str(row.get(col_parentesco, "")).strip().upper()
        if parentesco == "AGREGADO(A)":
            continue

        nome = _normalizar_nome(nome_raw)
        cpf = _normalizar_cpf(row.get(col_cpf, ""))
        valor_raw = row.get(col_mensalidade, 0)
        if pd.isna(valor_raw):
            valor_raw = 0
        valor = float(valor_raw or 0)

        mapa[titular_atual].append(FilialRow(nome=nome, cpf=cpf, valor=valor))

    return mapa


def agrupar_por_titular(df: pd.DataFrame, uniodonto_map: Optional[Dict[str, List[FilialRow]]] = None) -> List[DadosTitular]:
    """
    Agrupa as linhas por titular (DEPENDENCIA == 'Titular') usando código da família.
    Retorna uma lista de DadosTitular, um por titular.
    """
    cod_fam = None
    for c in df.columns:
        if "FAMILIA" in c or "FAMÍLIA" in c.upper().replace("Í", "I"):
            cod_fam = c
            break
    if cod_fam is None:
        cod_fam = "CÓD DA FAMILIA" if "CÓD DA FAMILIA" in df.columns else None

    if cod_fam is None:
        # Fallback: usar CPF como chave se não houver código de família
        df = df.copy()
        df["_COD_FAMILIA"] = df["CPF"].apply(_normalizar_cpf)
        cod_fam = "_COD_FAMILIA"

    titulares: List[DadosTitular] = []
    df_clean = df.dropna(subset=["NOME", "CPF"]).copy()
    df_clean["_cpf_norm"] = df_clean["CPF"].apply(_normalizar_cpf)
    df_clean["_cod_fam"] = df_clean[cod_fam].apply(_normalizar_codigo)

    for cod_familia, grp in df_clean.groupby("_cod_fam", sort=False):
        if not cod_familia:
            continue
        titular_row = grp[grp["DEPENDENCIA"].astype(str).str.strip().str.upper() == "TITULAR"]
        if titular_row.empty:
            # Usar primeira linha do grupo como titular
            titular_row = grp.head(1)
        titular_row = titular_row.iloc[0]
        cpf_tit = _normalizar_cpf(titular_row["CPF"])
        nome_tit = _normalizar_nome(titular_row["NOME"])
        if not cpf_tit:
            continue

        total_cons = grp["CONSULTA"].fillna(0).astype(float).sum()
        total_mens = grp["MENSALIDADE"].fillna(0).astype(float).sum()
        total_retro = (
            grp["RETROATIVO"].fillna(0).astype(float).sum()
            + grp["RETROATIVO RN"].fillna(0).astype(float).sum()
        )

        linhas_consultas: List[FilialRow] = []
        for _, r in grp.iterrows():
            v = float(r["CONSULTA"]) if pd.notna(r["CONSULTA"]) else 0
            if v > 0:
                linhas_consultas.append(FilialRow(
                    nome=_normalizar_nome(r["NOME"]),
                    valor=v,
                    codigo_familia=_normalizar_codigo(r.get(cod_fam, "")),
                ))

        linhas_mensalidades: List[FilialRow] = []
        for _, r in grp.iterrows():
            v = float(r["MENSALIDADE"]) if pd.notna(r["MENSALIDADE"]) else 0
            if v > 0:
                cart = r.get("CARTEIRA", "")
                if pd.notna(cart):
                    cart = str(int(cart)) if isinstance(cart, (int, float)) else str(cart).strip()
                else:
                    cart = ""
                linhas_mensalidades.append(FilialRow(
                    nome=_normalizar_nome(r["NOME"]),
                    valor=v,
                    carteira=cart,
                ))

        linhas_mensalidades_retro: List[FilialRow] = []
        for _, r in grp.iterrows():
            v_retro = 0.0
            if pd.notna(r.get("RETROATIVO", 0)):
                v_retro += float(r.get("RETROATIVO", 0) or 0)
            if pd.notna(r.get("RETROATIVO RN", 0)):
                v_retro += float(r.get("RETROATIVO RN", 0) or 0)
            if v_retro > 0:
                cart = r.get("CARTEIRA", "")
                if pd.notna(cart):
                    cart = str(int(cart)) if isinstance(cart, (int, float)) else str(cart).strip()
                else:
                    cart = ""
                linhas_mensalidades_retro.append(FilialRow(
                    nome=_normalizar_nome(r["NOME"]),
                    valor=v_retro,
                    carteira=cart,
                ))

        linhas_uniodonto: List[FilialRow] = []
        total_uniodonto = 0.0
        if uniodonto_map:
            chave_nome = _normalizar_nome_chave(nome_tit)
            chave_cpf = _normalizar_cpf(cpf_tit)
            chave = f"{chave_nome}|{chave_cpf}"
            linhas_uniodonto = uniodonto_map.get(chave, [])
            total_uniodonto = sum(l.valor for l in linhas_uniodonto)

        titulares.append(DadosTitular(
            cpf_titular=cpf_tit,
            nome_titular=nome_tit,
            total_consultas=total_cons,
            total_mensalidades=total_mens,
            total_mensalidades_retro=total_retro,
            total_uniodonto=total_uniodonto,
            linhas_consultas=linhas_consultas,
            linhas_mensalidades=linhas_mensalidades,
            linhas_mensalidades_retro=linhas_mensalidades_retro,
            linhas_uniodonto=linhas_uniodonto,
        ))

    return titulares
