# Declarações de Filiados (IRPF)

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Pandas](https://img.shields.io/badge/Pandas-1.3%2B-150458?logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![Licença: MIT](https://img.shields.io/badge/Licen%C3%A7a-MIT-green.svg)](LICENSE)

Gerador de informes anuais de despesas médicas para declaração de IRPF, com base em planilhas da Unimed, da Uniodonto (opcional) e da Unimed BH (opcional). O processamento consolida os valores e gera um PDF por titular usando um template padronizado.

## Visão geral

- Leitura de 12 abas mensais por planilha (Unimed e Uniodonto)
- Leitura opcional da planilha Unimed BH (aba única com total por titular)
- Consolidação anual por titular (CPF)
- Detalhes agregados por pessoa (nome + código/carteira/CPF)
- Valores retroativos (RETROATIVO e RETROATIVO RN) somados à mensalidade
- Validação automática de inconsistências
- Geração de PDFs com layout padronizado

## Estrutura do projeto

- `main.py`: execução em lote
- `src/irpf/gerar_relatorio_uniodonto.py`: relatório anual Uniodonto em Excel (famílias separadas)
- `src/irpf/`: leitura, validação e geração de PDFs
- `config/irpf.yml`: configuração (caminhos, ano_base, abas opcionais)
- `Data/`: planilhas e template PDF (mantidos localmente)

## Requisitos

- Python 3.10+
- Dependências listadas em `requirements.txt`

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuração

Edite `config/irpf.yml` para apontar para:

- `planilha_unimed`: planilha principal (Excel, com 12 abas mensais)
- `planilha_uniodonto`: planilha da Uniodonto (opcional, 12 abas mensais)
- `planilha_unimed_bh`: planilha Unimed BH (opcional, aba única com colunas `NOME`, `CPF` e `TOTAL`)
- `template_pdf`: modelo do informe (PDF)
- `pasta_saida`: diretório de saída dos PDFs
- `incluir_cpf_no_nome`: (opcional, padrão: `false`) incluir CPF no nome dos arquivos; `false` → `NOME_IRPF<ANO>.pdf`, `true` → `NOME_CPF_IRPF<ANO>.pdf`
- `ano_base`: ano-base do informe (usado para gerar abas JAN \<ano\> .. DEZ \<ano\>)
- `abas_mensais`: (opcional) lista explícita de nomes de abas

Observação: as colunas `RETROATIVO` e `RETROATIVO RN` da Unimed são somadas à mensalidade e exibidas na tabela de Mensalidades (não há página de retroativos separada).

### Abas mensais (importante)

Por padrão, as abas são geradas automaticamente no formato:

```
JAN <ano_base>, FEV <ano_base>, MAR <ano_base>, ... , DEZ <ano_base>
```

Se a sua planilha não seguir esse padrão, defina a lista manualmente em `config/irpf.yml`:

```
abas_mensais: [JAN 2025, FEV 2025, MAR 2025, ABR 2025, MAI 2025, JUN 2025, JUL 2025, AGO 2025, SET 2025, OUT 2025, NOV 2025, DEZ 2025]
```

Os arquivos de entrada e saída ficam fora do controle de versão por padrão (ver `.gitignore`).

## Execução

```bash
python main.py
```

Parâmetros úteis:

```bash
python main.py --dry-run
python main.py --config config/irpf.yml --sheet "OUT 2025" --ano 2026
python main.py --planilha Data/dados.xlsx --planilha-uniodonto Data/uniodonto.xlsx
python main.py --planilha-unimed-bh Data/unimedbh.xlsx
python main.py --incluir-cpf-no-nome  # inclui CPF no nome dos PDFs (sobrescreve config)
```

Relatório Uniodonto (Excel com Nome, Cpf, JAN..DEZ, TOTAL, famílias separadas):

```bash
python src/irpf/gerar_relatorio_uniodonto.py -o relatorio_uniodonto_2025.xlsx
```

---

**Desenvolvido para o SINTUNIFEI** | Sistema de Processamento de Declarações de IRPF
