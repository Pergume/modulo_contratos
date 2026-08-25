"""
config.py
---------
Caminhos e parâmetros centrais.

A integração automática com o Google Drive foi ABANDONADA. A alimentação de
dados passa a ser manual, por envio de um pacote compactado (.zip) contendo
a pasta CONTRATOS_<AnoExercicio> com as planilhas das secretarias.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# Pacotes .zip enviados pela usuária (fonte oficial dos dados).
PACOTES_DIR = PROJECT_ROOT / "pacotes"
PACOTES_DIR.mkdir(exist_ok=True)

# Área de trabalho onde o pacote ativo é extraído. É recriada a cada carga.
DADOS_ATIVOS_DIR = PROJECT_ROOT / "dados_ativos"

# Histórico dos relatórios de atualização (JSON + TXT legível).
RELATORIOS_DIR = PROJECT_ROOT / "relatorios"
RELATORIOS_DIR.mkdir(exist_ok=True)

# Frontend institucional (congelado — nunca alterado em disco).
FRONTEND_DIR = PROJECT_ROOT / "frontend"
HTML_SIGO = FRONTEND_DIR / "SIGO_Gestao_Contratos.html"

# Ano de exercício que está escrito no HTML original. É o valor que o
# servidor substitui pelo exercício do pacote enviado.
ANO_BASE_FRONTEND = 2026

# Servidor
HOST = "127.0.0.1"
PORT = 8000
