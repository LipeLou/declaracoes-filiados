# Declarações de Filiados (IRPF)

Gerador de informes anuais de despesas médicas para declaração de IRPF, a partir de planilhas da Unimed e (opcionalmente) da Uniodonto. O script lê as 12 abas mensais (JAN \<ano\> .. DEZ \<ano\>), soma os valores e gera um PDF por titular com base em um template.

## Visão geral

- Leitura de 12 abas mensais por planilha (Unimed e Uniodonto)
- Agrupamento por titular (CPF) e soma anual
- Detalhes agregados por pessoa (nome + código/carteira/CPF)
- Validação automática de inconsistências
- Geração de PDFs com layout padronizado

## Estrutura do projeto

- `main.py`: execução em lote
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
- `template_pdf`: modelo do informe (PDF)
- `pasta_saida`: diretório de saída dos PDFs
- `ano_base`: ano-base do informe (usado para gerar abas JAN \<ano\> .. DEZ \<ano\>)
- `abas_mensais`: (opcional) lista de nomes de abas; se omitido, usa JAN/FEV/.../DEZ + ano_base

Os arquivos de entrada e saída ficam fora do controle de versão por padrão (ver `.gitignore`).

## Execução

```bash
python main.py
```

Parâmetros úteis:

```bash
python scripts/main.py --dry-run
python scripts/main.py --config config/irpf.yml --sheet "OUT 2025" --ano 2026
python scripts/main.py --planilha Data/dados.xlsx --planilha-uniodonto Data/uniodonto.xlsx
```