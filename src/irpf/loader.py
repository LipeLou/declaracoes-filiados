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

# Abreviações dos meses (3 letras) para nomes de abas anuais
_MESES_ABA = ("JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ")


def obter_nomes_abas_anual(ano: int) -> List[str]:
    """Gera a lista dos 12 nomes de abas mensais: JAN <ano>, FEV <ano>, ..., DEZ <ano>."""
    return [f"{mes} {ano}" for mes in _MESES_ABA]


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


def _agregar_linhas_por_chave(
    linhas: List[FilialRow],
    chave: str,
) -> List[FilialRow]:
    """
    Agrega FilialRow por chave (consultas: nome+codigo_familia, mensalidades: nome+carteira, uniodonto: nome+cpf).
    chave deve ser "consultas", "mensalidades", "uniodonto".
    """
    from collections import defaultdict
    grupos: Dict[tuple, float] = defaultdict(float)
    exemplar: Dict[tuple, FilialRow] = {}
    for row in linhas:
        if chave == "consultas":
            k = (row.nome, row.codigo_familia)
        elif chave in ("mensalidades", "mensalidades_retro"):
            k = (row.nome, row.carteira)
        else:  # uniodonto
            k = (row.nome, row.cpf)
        grupos[k] += row.valor
        if k not in exemplar:
            exemplar[k] = row
    out: List[FilialRow] = []
    for k, total in grupos.items():
        ex = exemplar[k]
        if chave == "consultas":
            out.append(FilialRow(nome=ex.nome, valor=total, codigo_familia=ex.codigo_familia))
        elif chave in ("mensalidades", "mensalidades_retro"):
            out.append(FilialRow(nome=ex.nome, valor=total, carteira=ex.carteira))
        else:
            out.append(FilialRow(nome=ex.nome, valor=total, cpf=ex.cpf))
    return out


def _normalizar_colunas(df: pd.DataFrame) -> None:
    """Normaliza nomes de colunas em maiúsculas e sem espaços extras."""
    df.columns = [str(c).strip().upper() for c in df.columns]


def _tentar_ler_unimed_com_skiprows(
    caminho: Path,
    sheet_name: Optional[str],
    skiprows: int,
) -> pd.DataFrame:
    """Tenta ler a planilha Unimed com um skiprows específico."""
    kwargs = {"skiprows": skiprows}
    if sheet_name is not None:
        kwargs["sheet_name"] = sheet_name
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Unknown type for Business Objects.*",
            category=UserWarning,
        )
        return pd.read_excel(caminho, **kwargs)


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

    required = ["NOME", "CPF", "DEPENDENCIA", "MENSALIDADE", "CONSULTA"]
    skiprows_opcoes = [skiprows] + [s for s in (0, 1, 2, 3, 4) if s != skiprows]

    df = None
    for sr in skiprows_opcoes:
        df = _tentar_ler_unimed_com_skiprows(path, sheet_name, sr)
        _normalizar_colunas(df)
        if all(col in df.columns for col in required):
            break
    else:
        # Não encontrou cabeçalho válido em nenhuma tentativa
        colunas = set(df.columns) if df is not None else set()
        faltantes = [col for col in required if col not in colunas]
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(faltantes)}")

    # Mapear variações de nome de coluna
    cod_fam = None
    for c in df.columns:
        if "FAMILIA" in c or "FAMÍLIA" in c.upper().replace("Í", "I"):
            cod_fam = c
            break
    if cod_fam is None and "CÓD DA FAMILIA" in df.columns:
        cod_fam = "CÓD DA FAMILIA"

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


def carregar_planilha_unimed_anual(
    caminho: str | Path,
    sheet_names: List[str],
    skiprows: int = 1,
) -> pd.DataFrame:
    """
    Carrega todas as abas mensais da planilha Unimed e concatena os dados.
    Se alguma aba não existir, levanta erro.
    """
    path = Path(caminho)
    if not path.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {path}")

    dfs: List[pd.DataFrame] = []
    for sheet_name in sheet_names:
        df = carregar_planilha_unimed(caminho, sheet_name=sheet_name, skiprows=skiprows)
        df["_MES_ABA"] = sheet_name
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def mesclar_mapas_uniodonto(mapas: List[Dict[str, List[FilialRow]]]) -> Dict[str, List[FilialRow]]:
    """
    Mescla múltiplos mapas titular -> [FilialRow] concatenando as listas por titular.
    """
    resultado: Dict[str, List[FilialRow]] = {}
    for mapa in mapas:
        for chave, linhas in mapa.items():
            resultado.setdefault(chave, []).extend(linhas)
    return resultado


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


def carregar_planilha_uniodonto_anual(
    caminho: str | Path,
    sheet_names: List[str],
) -> Dict[str, List[FilialRow]]:
    """
    Carrega todas as abas mensais da planilha Uniodonto e mescla os mapas por titular.
    Se alguma aba não existir, levanta erro.
    """
    mapas: List[Dict[str, List[FilialRow]]] = []
    for sheet_name in sheet_names:
        mapa = carregar_planilha_uniodonto(caminho, sheet_name=sheet_name)
        mapas.append(mapa)
    return mesclar_mapas_uniodonto(mapas)


def _mesclar_titular(destino: DadosTitular, origem: DadosTitular) -> None:
    """Soma totais e concatena linhas de detalhes."""
    destino.total_consultas += origem.total_consultas
    destino.total_mensalidades += origem.total_mensalidades
    destino.total_mensalidades_retro += origem.total_mensalidades_retro
    destino.linhas_consultas.extend(origem.linhas_consultas)
    destino.linhas_mensalidades.extend(origem.linhas_mensalidades)
    destino.linhas_mensalidades_retro.extend(origem.linhas_mensalidades_retro)


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

    titulares_map: Dict[str, DadosTitular] = {}
    df_clean = df.dropna(subset=["NOME", "CPF"]).copy()
    df_clean["_cpf_norm"] = df_clean["CPF"].apply(_normalizar_cpf)
    df_clean["_cod_fam"] = df_clean[cod_fam].apply(_normalizar_codigo)
    if "_MES_ABA" not in df_clean.columns:
        df_clean["_MES_ABA"] = ""
    for (_, cod_familia), grp in df_clean.groupby(["_MES_ABA", "_cod_fam"], sort=False):
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

        titular_parcial = DadosTitular(
            cpf_titular=cpf_tit,
            nome_titular=nome_tit,
            total_consultas=total_cons,
            total_mensalidades=total_mens,
            total_mensalidades_retro=total_retro,
            total_uniodonto=0.0,
            linhas_consultas=linhas_consultas,
            linhas_mensalidades=linhas_mensalidades,
            linhas_mensalidades_retro=linhas_mensalidades_retro,
            linhas_uniodonto=[],
        )

        if cpf_tit in titulares_map:
            _mesclar_titular(titulares_map[cpf_tit], titular_parcial)
        else:
            titulares_map[cpf_tit] = titular_parcial

    # Aplicar Uniodonto uma única vez por titular, após consolidar os meses
    if uniodonto_map:
        for d in titulares_map.values():
            chave_nome = _normalizar_nome_chave(d.nome_titular)
            chave_cpf = _normalizar_cpf(d.cpf_titular)
            chave = f"{chave_nome}|{chave_cpf}"
            d.linhas_uniodonto = uniodonto_map.get(chave, [])
            d.total_uniodonto = sum(l.valor for l in d.linhas_uniodonto)

    # Agregar detalhes por pessoa (nome + código/carteira/CPF) para informe anual
    for d in titulares_map.values():
        d.linhas_consultas = _agregar_linhas_por_chave(d.linhas_consultas, "consultas")
        d.linhas_mensalidades = _agregar_linhas_por_chave(d.linhas_mensalidades, "mensalidades")
        d.linhas_mensalidades_retro = _agregar_linhas_por_chave(d.linhas_mensalidades_retro, "mensalidades_retro")
        d.linhas_uniodonto = _agregar_linhas_por_chave(d.linhas_uniodonto, "uniodonto")
        d.total_uniodonto = sum(l.valor for l in d.linhas_uniodonto)

    return list(titulares_map.values())
