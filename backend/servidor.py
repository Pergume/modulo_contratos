"""
servidor.py
-----------
Servidor do SIGO — versão v2 (alimentação por pacote .zip).

O QUE MUDOU NESTA VERSÃO
------------------------
 • A integração automática com o Google Drive foi abandonada.
 • A alimentação passa a ser MANUAL: a usuária envia um pacote .zip com a
   pasta CONTRATOS_<AnoExercicio> contendo as planilhas das secretarias.
 • O ANO DE EXERCÍCIO exibido no painel passa a vir do pacote enviado
   (nome da pasta CONTRATOS_<ano>), e não mais fixo em 2026.
 • As planilhas passam a ser lidas pela aba nativa "Base de Dados".

O FRONTEND CONTINUA INTACTO
---------------------------
O arquivo frontend/SIGO_Gestao_Contratos.html não é alterado em disco. O
servidor monta a resposta em memória, substituindo apenas:
   (a) o vetor de exemplo `let CONTRACTS = [...];`
   (b) o ano de exercício (2026 no arquivo original) pelo ano do pacote.
Nenhum outro byte é tocado.

Execução:
    cd backend
    uvicorn servidor:app --reload
    # abrir http://127.0.0.1:8000/
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import traceback
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import config  # noqa: E402
from adaptador_sigo import montar_contracts  # noqa: E402
from ajustes_frontend import aplicar_ajustes, funcoes_graficos  # noqa: E402
import relatorios  # noqa: E402
from pacote import (  # noqa: E402
    PacoteInvalido,
    extrair_pacote,
    pacote_mais_recente,
)

# Âncora do vetor de dados no HTML (uma única linha).
_PADRAO_CONTRACTS = re.compile(r"let\s+CONTRACTS\s*=\s*\[.*?\];", re.DOTALL)

app = FastAPI(title="SIGO · Gestão de Contratos — v2 (pacote .zip)")

if (config.FRONTEND_DIR / "libs").exists():
    app.mount("/libs", StaticFiles(directory=str(config.FRONTEND_DIR / "libs")), name="libs")

# Estado em memória do pacote ativo.
_ESTADO: dict = {
    "pacote": None,        # objeto Pacote
    "contratos": [],       # vetor CONTRACTS
    "diagnostico": None,   # resumo da carga
    "origem": None,        # nome do .zip
}


# ---------------------------------------------------------------------------
# Carga do pacote
# ---------------------------------------------------------------------------
def carregar_pacote(zip_path: Path) -> dict:
    """Extrai o .zip, lê as planilhas e passa a ser o pacote ativo."""
    pct = extrair_pacote(zip_path, config.DADOS_ATIVOS_DIR)
    contratos, diagnostico = montar_contracts(pct, referencia=date.today())

    _ESTADO["pacote"] = pct
    _ESTADO["contratos"] = contratos
    _ESTADO["diagnostico"] = diagnostico
    _ESTADO["origem"] = zip_path.name
    diagnostico["pacote"] = zip_path.name

    # Grava o relatório para consulta posterior (JSON + TXT legível).
    try:
        registro = relatorios.salvar(diagnostico, zip_path.name, config.RELATORIOS_DIR)
        diagnostico["relatorio_id"] = registro["id"]
        diagnostico["relatorio_momento"] = registro["momento_legivel"]
    except OSError as e:  # noqa: BLE001
        print(f"[SIGO] Não foi possível gravar o relatório: {e}")

    return diagnostico


def _tentar_carga_inicial() -> None:
    """Na subida do servidor, carrega o .zip mais recente da pasta /pacotes."""
    zip_path = pacote_mais_recente(config.PACOTES_DIR)
    if not zip_path:
        return
    try:
        carregar_pacote(zip_path)
        print(f"[SIGO] Pacote carregado: {zip_path.name} "
              f"(exercício {_ESTADO['diagnostico']['exercicio']}, "
              f"{_ESTADO['diagnostico']['total_contratos']} contratos)")
    except PacoteInvalido as e:
        print(f"[SIGO] Pacote '{zip_path.name}' não pôde ser carregado: {e}")


@app.on_event("startup")
def _startup() -> None:  # pragma: no cover - substituído por lifespan
    _tentar_carga_inicial()


# ---------------------------------------------------------------------------
# Montagem do HTML servido
# ---------------------------------------------------------------------------
def _montar_html(contratos: list[dict], exercicio: int) -> str:
    """
    Devolve o HTML do SIGO com os dados reais e o exercício corretos.

    A troca do ano é feita apenas na parte NÃO-dados do arquivo: o vetor de
    contratos é isolado antes, para que datas contidas nos registros jamais
    sejam alteradas.
    """
    html = config.HTML_SIGO.read_text(encoding="utf-8")

    m = _PADRAO_CONTRACTS.search(html)
    if not m:
        raise RuntimeError(
            "Âncora 'let CONTRACTS = [...]' não encontrada no HTML do SIGO. "
            "A injeção foi abortada para não corromper o frontend."
        )

    prefixo, sufixo = html[:m.start()], html[m.end():]

    # (b) Ano de exercício — só no texto/lógica, nunca nos dados.
    ano_base = str(config.ANO_BASE_FRONTEND)
    ano_novo = str(exercicio)
    if ano_novo != ano_base:
        prefixo = prefixo.replace(ano_base, ano_novo)
        sufixo = sufixo.replace(ano_base, ano_novo)

    # (a) Vetor de dados + função do gráfico de tipos (mesmo bloco de script,
    #     para já estar disponível na primeira renderização).
    payload = json.dumps(contratos, ensure_ascii=False)
    html = (
        f"{prefixo}let CONTRACTS = {payload};\n"
        f"{funcoes_graficos()}{sufixo}"
    )

    # (c) Ajustes funcionais (envio de .zip pela interface, gráfico de tipos).
    html = aplicar_ajustes(html)

    # TESTE_LIBS_LOCAIS: em ambiente sem acesso ao CDN, serve as bibliotecas
    # locais se a pasta frontend/libs existir. Em produção não tem efeito.
    if (config.FRONTEND_DIR / "libs").exists():
        html = html.replace(
            "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js",
            "/libs/chart.umd.min.js").replace(
            "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js",
            "/libs/xlsx.full.min.js")
    return html


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Serve o painel com o pacote ativo já embutido."""
    contratos = _ESTADO["contratos"]
    exercicio = (
        _ESTADO["diagnostico"]["exercicio"]
        if _ESTADO["diagnostico"] else config.ANO_BASE_FRONTEND
    )
    return HTMLResponse(content=_montar_html(contratos, exercicio))


@app.post("/api/pacote")
async def enviar_pacote(arquivo: UploadFile = File(...)) -> JSONResponse:
    """
    Recebe o pacote .zip, valida a estrutura, identifica o exercício e
    recarrega o painel.

    Toda falha é convertida em JSON com mensagem legível: o painel precisa
    conseguir ler a resposta mesmo quando algo dá errado. Um erro devolvido
    como página HTML de erro faria o navegador exibir apenas um problema de
    leitura de JSON, escondendo a causa real.
    """
    nome = Path(arquivo.filename or "pacote.zip").name  # ignora caminhos
    if not nome.lower().endswith(".zip"):
        return JSONResponse(
            status_code=400,
            content={"erro": f"'{nome}' não é um .zip. Compacte a pasta e "
                             f"envie o arquivo compactado."},
        )

    destino = config.PACOTES_DIR / nome
    try:
        with destino.open("wb") as f:
            shutil.copyfileobj(arquivo.file, f)
    except OSError as e:
        return JSONResponse(
            status_code=500,
            content={"erro": f"Não foi possível gravar o pacote em "
                             f"{config.PACOTES_DIR}: {e}"},
        )

    try:
        diagnostico = carregar_pacote(destino)
    except PacoteInvalido as e:
        return JSONResponse(status_code=400, content={"erro": str(e)})
    except PermissionError as e:
        return JSONResponse(
            status_code=500,
            content={"erro": "Um arquivo da carga anterior está aberto e não "
                             "pôde ser substituído. Feche a planilha se ela "
                             "estiver aberta no Excel e envie novamente. "
                             f"Detalhe: {e}"},
        )
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"erro": f"Falha ao processar o pacote: "
                             f"{type(e).__name__}: {e}"},
        )

    return JSONResponse(content={
        "mensagem": (
            f"Pacote carregado: exercício {diagnostico['exercicio']}, "
            f"{diagnostico['total_contratos']} contrato(s) em "
            f"{len(diagnostico['secretarias'])} secretaria(s)."
        ),
        "diagnostico": diagnostico,
    })


@app.post("/api/verificar")
async def verificar_pacote(arquivo: UploadFile = File(...)) -> JSONResponse:
    """
    Confere um pacote SEM substituir os dados em uso.

    Serve para validar a estrutura e o preenchimento antes de publicar: diz
    quantos contratos cada secretaria traria, quais ficariam de fora e por quê.
    """
    nome = Path(arquivo.filename or "pacote.zip").name
    if not nome.lower().endswith(".zip"):
        return JSONResponse(status_code=400,
                            content={"erro": f"'{nome}' não é um .zip."})

    temporario = config.PACOTES_DIR / f"_verificacao_{nome}"
    try:
        with temporario.open("wb") as f:
            shutil.copyfileobj(arquivo.file, f)
        pct = extrair_pacote(temporario, config.DADOS_ATIVOS_DIR / "_verificacao")
        _, diagnostico = montar_contracts(pct, referencia=date.today())
        return JSONResponse(content={
            "mensagem": (
                f"Verificação: exercício {diagnostico['exercicio']}, "
                f"{diagnostico['total_contratos']} contrato(s) em "
                f"{len(diagnostico['secretarias'])} secretaria(s). "
                f"Os dados em uso NÃO foram alterados."
            ),
            "diagnostico": diagnostico,
        })
    except PacoteInvalido as e:
        return JSONResponse(status_code=400, content={"erro": str(e)})
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return JSONResponse(status_code=500,
                            content={"erro": f"{type(e).__name__}: {e}"})
    finally:
        try:
            temporario.unlink(missing_ok=True)
        except OSError:
            pass


@app.get("/api/diagnostico")
def diagnostico() -> JSONResponse:
    """Resumo da carga ativa: exercício, secretarias, leiaute e avisos."""
    if not _ESTADO["diagnostico"]:
        return JSONResponse(
            status_code=404,
            content={"erro": "Nenhum pacote carregado. Envie um .zip em /api/pacote "
                             "ou coloque-o na pasta /pacotes e reinicie."},
        )
    return JSONResponse(content=_ESTADO["diagnostico"])


@app.get("/api/contratos")
def api_contratos() -> JSONResponse:
    """Vetor CONTRACTS em JSON (inspeção/depuração)."""
    return JSONResponse(content={
        "total": len(_ESTADO["contratos"]),
        "exercicio": (_ESTADO["diagnostico"] or {}).get("exercicio"),
        "contratos": _ESTADO["contratos"],
    })


@app.get("/api/relatorios")
def listar_relatorios() -> JSONResponse:
    """Índice do histórico de atualizações, do mais recente ao mais antigo."""
    return JSONResponse(content={"relatorios": relatorios.listar(config.RELATORIOS_DIR)})


@app.get("/api/relatorios/{identificador}")
def obter_relatorio(identificador: str) -> JSONResponse:
    """
    Relatório completo. Use 'ultimo' para o mais recente.

    Permite reler a qualquer momento o resultado de uma atualização — inclusive
    de cargas anteriores — sem precisar reenviar o pacote.
    """
    alvo = "" if identificador in ("ultimo", "último") else identificador
    d = relatorios.ler(config.RELATORIOS_DIR, alvo)
    if not d:
        return JSONResponse(status_code=404,
                            content={"erro": "Relatório não encontrado."})
    return JSONResponse(content=d)


@app.get("/api/relatorios/{identificador}/texto", response_class=PlainTextResponse)
def obter_relatorio_texto(identificador: str) -> PlainTextResponse:
    """Mesma informação em texto puro, para imprimir ou anexar a um processo."""
    alvo = "" if identificador in ("ultimo", "último") else identificador
    d = relatorios.ler(config.RELATORIOS_DIR, alvo)
    if not d:
        return PlainTextResponse("Relatório não encontrado.", status_code=404)
    arq = config.RELATORIOS_DIR / f"{d['id']}.txt"
    if arq.exists():
        return PlainTextResponse(arq.read_text(encoding="utf-8"))
    from datetime import datetime as _dt
    return PlainTextResponse(relatorios.formatar_texto(
        d["diagnostico"], d.get("pacote", ""), _dt.fromisoformat(d["momento"])))


@app.get("/api/saude")
def saude() -> dict:
    d = _ESTADO["diagnostico"] or {}
    return {
        "status": "ok",
        "pacote_ativo": _ESTADO["origem"],
        "exercicio": d.get("exercicio"),
        "total_contratos": d.get("total_contratos", 0),
        "secretarias": d.get("secretarias", []),
        "pacotes_dir": str(config.PACOTES_DIR),
    }
