# Declarações de Filiados (IRPF)

Gerador de informes de despesas médicas para declaração de IRPF, a partir de planilhas da Unimed e (opcionalmente) da Uniodonto. O script lê as planilhas, valida os totais e gera um PDF por titular com base em um template.

## Visão geral

- Leitura e normalização de planilhas Excel
- Agrupamento por titular (CPF) e cálculo de totais
- Validação automática de inconsistências
- Geração de PDFs com layout padronizado
- Suporte opcional a Uniodonto

## Estrutura do projeto

- `scripts/gerar_informes_irpf.py`: execução em lote
- `src/irpf/`: leitura, validação e geração de PDFs
- `config/irpf.yml`: configuração padrão (caminhos e parâmetros)
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

- `planilha_unimed`: planilha principal (Excel)
- `planilha_uniodonto`: planilha da Uniodonto (opcional)
- `template_pdf`: modelo do informe (PDF)
- `pasta_saida`: diretório de saída dos PDFs
- `sheet_name`: nome da aba (opcional)
- `ano_base`: ano-base do informe

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