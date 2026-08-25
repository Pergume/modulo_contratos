"""
relatorios.py
-------------
Histórico dos relatórios de atualização de dados.

Cada carga de pacote gera um relatório dizendo, por secretaria, quantos
contratos entraram no painel e — quando nenhum entrou — o motivo. Antes esse
relatório existia apenas na janela exibida logo após o envio: quem fechasse a
janela perdia a informação.

Agora cada relatório é gravado em `relatorios/`, em duas formas:

  • `.json` — consumido pelo painel para reexibir o relatório;
  • `.txt`  — texto legível, que pode ser aberto fora do sistema, anexado a
              um processo ou encaminhado à secretaria responsável.

Os arquivos são nomeados pela data e hora da carga, de modo que o histórico
fica em ordem cronológica.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

LIMITE_HISTORICO = 60   # relatórios mantidos; os mais antigos são descartados


def _agora() -> datetime:
    return datetime.now()


def _carimbo(dt: datetime) -> str:
    return dt.strftime("%Y%m%d_%H%M%S")


def formatar_texto(diagnostico: dict, pacote: str, momento: datetime) -> str:
    """Versão legível do relatório, para leitura fora do sistema."""
    L: list[str] = []
    L.append("SIGO — RELATÓRIO DE ATUALIZAÇÃO DE DADOS")
    L.append("=" * 62)
    L.append(f"Data da carga : {momento.strftime('%d/%m/%Y às %H:%M:%S')}")
    L.append(f"Pacote        : {pacote}")
    L.append(f"Exercício     : {diagnostico.get('exercicio')}")
    if diagnostico.get("pasta_contratos"):
        L.append(f"Pasta lida    : {diagnostico['pasta_contratos']}")
    L.append(f"Total         : {diagnostico.get('total_contratos', 0)} contrato(s) "
             f"em {len(diagnostico.get('secretarias', []))} secretaria(s)")
    L.append("")
    L.append("SECRETARIAS")
    L.append("-" * 62)

    for p in diagnostico.get("por_planilha", []):
        marca = "[OK]  " if p.get("contratos") else "[--]  "
        L.append(f"{marca}{p.get('secretaria')} — {p.get('contratos', 0)} contrato(s)")
        L.append(f"          arquivo: {p.get('arquivo')}")
        if p.get("origem"):
            L.append(f"          origem : {p['origem']}")
        if p.get("motivo"):
            L.append(f"          motivo : {p['motivo']}")
        if not p.get("contratos") and p.get("abas"):
            L.append(f"          abas do arquivo: {', '.join(p['abas'])}")
        L.append("")

    ignorados = [a for a in diagnostico.get("auditoria_arquivos", [])
                 if a.get("situacao") == "ignorado"]
    if ignorados:
        L.append("ARQUIVOS IGNORADOS")
        L.append("-" * 62)
        for a in ignorados:
            L.append(f"  - {a.get('arquivo')} ({a.get('motivo')})")
        L.append("")

    if diagnostico.get("alertas_qualidade"):
        L.append("ATENÇÃO — LEITURA DOS INDICADORES")
        L.append("-" * 62)
        for a in diagnostico["alertas_qualidade"]:
            L.append(f"  ! {a}")
        L.append("")

    if diagnostico.get("avisos"):
        L.append("AVISOS")
        L.append("-" * 62)
        for a in diagnostico["avisos"]:
            L.append(f"  - {a}")
        L.append("")

    L.append("-" * 62)
    L.append("Secretarias sem contratos no painel não indicam falha do sistema:")
    L.append("normalmente a planilha ainda não foi preenchida pela equipe")
    L.append("responsável. O campo 'motivo' acima esclarece cada caso.")
    return "\n".join(L)


def salvar(diagnostico: dict, pacote: str, pasta: Path) -> dict:
    """Grava o relatório (JSON + TXT) e devolve seus metadados."""
    pasta.mkdir(parents=True, exist_ok=True)
    momento = _agora()
    base = f"relatorio_{_carimbo(momento)}"

    registro = {
        "id": base,
        "momento": momento.isoformat(timespec="seconds"),
        "momento_legivel": momento.strftime("%d/%m/%Y às %H:%M"),
        "pacote": pacote,
        "exercicio": diagnostico.get("exercicio"),
        "total_contratos": diagnostico.get("total_contratos", 0),
        "secretarias_com_dados": len(diagnostico.get("secretarias", [])),
        "secretarias_sem_dados": diagnostico.get("secretarias_sem_dados", []),
        "diagnostico": diagnostico,
    }

    (pasta / f"{base}.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta / f"{base}.txt").write_text(
        formatar_texto(diagnostico, pacote, momento), encoding="utf-8")

    _podar(pasta)
    return registro


def _podar(pasta: Path) -> None:
    """Mantém apenas os relatórios mais recentes."""
    arquivos = sorted(pasta.glob("relatorio_*.json"), reverse=True)
    for antigo in arquivos[LIMITE_HISTORICO:]:
        antigo.unlink(missing_ok=True)
        antigo.with_suffix(".txt").unlink(missing_ok=True)


def listar(pasta: Path) -> list[dict]:
    """Índice do histórico, do mais recente para o mais antigo."""
    if not pasta.exists():
        return []
    itens: list[dict] = []
    for arq in sorted(pasta.glob("relatorio_*.json"), reverse=True):
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        itens.append({
            "id": d.get("id", arq.stem),
            "momento_legivel": d.get("momento_legivel", ""),
            "pacote": d.get("pacote", ""),
            "exercicio": d.get("exercicio"),
            "total_contratos": d.get("total_contratos", 0),
            "secretarias_com_dados": d.get("secretarias_com_dados", 0),
            "secretarias_sem_dados": len(d.get("secretarias_sem_dados", [])),
        })
    return itens


def ler(pasta: Path, identificador: str) -> dict | None:
    """Relatório completo pelo identificador (ou o mais recente, se vazio)."""
    if not pasta.exists():
        return None
    if not identificador:
        arquivos = sorted(pasta.glob("relatorio_*.json"), reverse=True)
        if not arquivos:
            return None
        alvo = arquivos[0]
    else:
        alvo = pasta / f"{Path(identificador).name}.json"
        if not alvo.exists():
            return None
    try:
        return json.loads(alvo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
