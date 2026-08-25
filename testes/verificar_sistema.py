"""
verificar_sistema.py
--------------------
Verificação automática do sistema. Execute antes de publicar uma versão:

    cd testes
    python verificar_sistema.py

Confere:
  1. O HTML institucional não foi alterado em disco.
  2. As âncoras dos ajustes existem no HTML.
  3. O JavaScript injetado é sintaticamente válido (se o Node estiver
     instalado) e não contém quebras de linha cruas dentro de textos.
  4. As planilhas não ficam abertas após a leitura (no Windows, um arquivo
     aberto impede a substituição do pacote).
  5. Duas cargas consecutivas funcionam.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import config                      # noqa: E402
import ajustes_frontend as aj      # noqa: E402

MD5_ORIGINAL = "75af2f58bf5e0e3ace13127b1205a6e8"

falhas: list[str] = []


def checar(condicao: bool, descricao: str, detalhe: str = "") -> None:
    print(("  OK    " if condicao else "  FALHA ") + descricao + (f" — {detalhe}" if detalhe else ""))
    if not condicao:
        falhas.append(descricao)


print("1. Integridade do frontend")
md5 = hashlib.md5(config.HTML_SIGO.read_bytes()).hexdigest()
checar(md5 == MD5_ORIGINAL, "HTML institucional intacto", md5)

print("\n2. Âncoras dos ajustes")
html = config.HTML_SIGO.read_text(encoding="utf-8")
for rotulo, trecho in [
    ("botão de atualização", aj._BTN_ANTIGO),
    ("campo de arquivo", aj._INPUT_ANTIGO),
    ("chamada do gráfico de tipos", aj._CHAMADA_ANTIGA),
    ("bloco do gráfico por unidade", aj._ORC_ANTIGO),
    ("chamada do gráfico de valor por unidade", aj._UNI_ANTIGO),
    ("chamada do gráfico de aditivos", aj._ADIT_ANTIGO),
    ("chamada do gráfico de top fornecedores", aj._FORN_ANTIGO),
    ("fim do documento", "</body>"),
]:
    checar(html.count(trecho) == 1, f"âncora presente: {rotulo}",
           f"{html.count(trecho)} ocorrência(s)")

print("\n2b. Iniciador (atalho de trabalho)")
import py_compile
_lanc = config.PROJECT_ROOT / "abrir_sigo.py"
checar(_lanc.exists(), "abrir_sigo.py presente")
if _lanc.exists():
    try:
        py_compile.compile(str(_lanc), doraise=True)
        checar(True, "abrir_sigo.py compila")
    except Exception as e:  # noqa: BLE001
        checar(False, "abrir_sigo.py compila", str(e)[:90])
for _arq in ["Abrir SIGO.bat", "Criar atalho na Area de Trabalho.bat",
             "abrir_sigo.sh", "sigo.ico"]:
    checar((config.PROJECT_ROOT / _arq).exists(), f"arquivo presente: {_arq}")

print("\n3. JavaScript injetado")
js = (aj._SCRIPT_UPLOAD.split("<script>")[1].split("</script>")[0]
      + "\n" + aj._SCRIPT_RELATORIOS.split("<script>")[1].split("</script>")[0])
fn = (aj._FUNCAO_BASE + aj._FUNCAO_TIPO + aj._FUNCAO_ORC
      + aj._FUNCAO_UNI + aj._FUNCAO_ADIT + aj._FUNCAO_FORN)

# Quebra de linha crua dentro de aspas simples denuncia escape interpretado
# duas vezes (o erro "Invalid or unexpected token" no navegador).
def tem_quebra_em_texto(codigo: str) -> bool:
    for linha in codigo.split("\n"):
        if linha.count("'") % 2 == 1 and not linha.rstrip().endswith("\\"):
            return True
    return False

checar(not tem_quebra_em_texto(js), "script de envio sem texto quebrado")
checar(not tem_quebra_em_texto(fn), "funções dos gráficos sem texto quebrado")

# A legenda do gráfico por unidade precisa ficar FORA da área que rola.
checar("cabecalhoOrc" in aj._FUNCAO_ORC, "legenda fixa (HTML) definida")
checar("legend: { display: false }" in aj._FUNCAO_ORC,
       "legenda interna do Chart.js desativada")
checar("cartao.insertBefore(barra, box)" in aj._FUNCAO_ORC,
       "legenda inserida antes da área rolável")

# A legenda da rosca por unidade precisa usar o gerador DA ROSCA: o gerador
# global devolve um item por conjunto de dados (uma única fatia na legenda).
checar("Chart.overrides.doughnut.plugins.legend.labels.generateLabels" in aj._FUNCAO_UNI,
       "legenda da rosca usa o gerador correto")
checar("aplicarFiltroUnidade" in aj._FUNCAO_UNI, "clique da legenda aplica filtro")

# O gráfico de aditivos não pode usar o nome da contratada como chave nem
# herdar o limite de 15 categorias da função genérica.
checar("hbarAditivosTodos" in aj._FUNCAO_ADIT, "gráfico de aditivos próprio (sem limite de 15)")
checar("hbarFornTop20" in aj._FUNCAO_FORN, "gráfico de fornecedores exibe os 20 do título")

# Relatórios: identificação da secretaria e diferenciação dos que coincidiam.
_rel = aj._SCRIPT_RELATORIOS
checar("'Secretaria'" in _rel, "relatórios rotulam a coluna como 'Secretaria'")
checar("HORIZONTE_LICITACAO" in _rel,
       "relatório 11 com horizonte próprio (não repete o 04)")
checar("tabelasPorSecretaria" in _rel and "Subtotal " in _rel,
       "relatório 07 agrupado por secretaria com subtotal")
checar("Não foi possível emitir este relatório" in _rel,
       "relatórios 02/03 avisam quando o campo de agrupamento está vazio")

# Teto de escala e visão expandida do gráfico por unidade.
checar("TETO_ORC" in aj._FUNCAO_ORC and "500000000" in aj._FUNCAO_ORC,
       "teto de R$ 500 milhões definido")
checar("btnExpandirOrc" in aj._FUNCAO_ORC, "botão de expandir presente")
checar("abrirOrcExpandido" in aj._FUNCAO_ORC and "fecharOrcExpandido" in aj._FUNCAO_ORC,
       "visão expandida abre e fecha")

# Empilhamento de faixas de rolagem: nenhuma função pode resolver o contêiner
# por cv.parentElement — a partir da 2ª renderização esse pai É a faixa
# anterior, e uma nova acabaria criada dentro dela, uma por mudança de filtro.
checar("prepararFaixa" in aj._FUNCAO_BASE, "função que normaliza a faixa de rolagem definida")
for _nome, _fn in [("tipos", aj._FUNCAO_TIPO), ("orçamentária", aj._FUNCAO_ORC),
                   ("aditivos", aj._FUNCAO_ADIT), ("fornecedores", aj._FUNCAO_FORN)]:
    checar("cv.parentElement" not in _fn and "prepararFaixa(cv" in _fn,
           f"gráfico de {_nome} usa prepararFaixa (sem cv.parentElement)")
checar("Object.fromEntries" not in aj._FUNCAO_ADIT,
       "aditivos sem colisão por nome de contratada")

node = subprocess.run(["node", "--version"], capture_output=True)
if node.returncode == 0:
    for nome, codigo in [("script de envio", js), ("funções dos gráficos", fn)]:
        tmp = Path(f"/tmp/_chk_{abs(hash(nome))}.js")
        tmp.write_text(codigo, encoding="utf-8")
        r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
        checar(r.returncode == 0, f"sintaxe válida: {nome}", r.stderr.strip()[:120])
        tmp.unlink(missing_ok=True)
else:
    print("  (Node não instalado — conferência de sintaxe JS ignorada)")

print("\n4. Planilhas não ficam abertas após a leitura")
from leitor import ler_planilha  # noqa: E402

exemplo = next(
    (p for p in (config.PROJECT_ROOT / "pacotes").glob("*.zip")), None
)
if exemplo:
    from pacote import extrair_pacote  # noqa: E402
    pct = extrair_pacote(exemplo, config.DADOS_ATIVOS_DIR)
    for pl in pct.planilhas:
        ler_planilha(pl.caminho)

    if sys.platform.startswith("linux") and os.path.isdir("/proc/self/fd"):
        abertos = []
        for fd in os.listdir("/proc/self/fd"):
            try:
                alvo = os.readlink(f"/proc/self/fd/{fd}")
            except OSError:
                continue
            if alvo.endswith((".xlsx", ".xlsm")):
                abertos.append(alvo)
        checar(not abertos, "nenhuma planilha permanece aberta",
               f"{len(abertos)} aberta(s)")
    else:
        print("  (conferência de descritores disponível apenas no Linux)")

    print("\n5. Cargas consecutivas")
    from servidor import carregar_pacote  # noqa: E402
    try:
        d1 = carregar_pacote(exemplo)
        d2 = carregar_pacote(exemplo)
        checar(d1["total_contratos"] == d2["total_contratos"],
               "duas cargas seguidas produzem o mesmo resultado",
               f"{d1['total_contratos']} / {d2['total_contratos']}")
    except Exception as e:  # noqa: BLE001
        checar(False, "duas cargas seguidas", f"{type(e).__name__}: {e}")

    print("\n6. Histórico de relatórios")
    import relatorios  # noqa: E402
    itens = relatorios.listar(config.RELATORIOS_DIR)
    checar(len(itens) > 0, "relatório gravado após a carga", f"{len(itens)} no histórico")
    if itens:
        ultimo = relatorios.ler(config.RELATORIOS_DIR, "")
        checar(bool(ultimo and ultimo.get("diagnostico")),
               "relatório mais recente pode ser relido")
        txt = config.RELATORIOS_DIR / f"{itens[0]['id']}.txt"
        checar(txt.exists(), "versão em texto gerada", txt.name)
else:
    print("  (nenhum pacote em /pacotes — itens 4 a 6 ignorados)")


print()
if falhas:
    print(f"RESULTADO: {len(falhas)} falha(s).")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: todas as verificações passaram.")
