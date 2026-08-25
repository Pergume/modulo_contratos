"""
pacote.py
---------
Entrada de dados por PACOTE COMPACTADO (.zip) — modelo manual.

Estrutura esperada
------------------
    pacote.zip
      └── <Pasta extraída (nome livre)>
            └── CONTRATOS_<AnoExercicio>          ← define o EXERCÍCIO
                  ├── SEMAD_Controle_Contratos_<AnoReferente>.xlsx
                  └── ...

Princípio de projeto: NADA é descartado em silêncio
---------------------------------------------------
Todo arquivo encontrado dentro do pacote entra na auditoria, com a situação
("carregado", "ignorado", "erro") e o motivo. Se uma secretaria não aparecer
no painel, a auditoria diz exatamente por quê.

A leitura é deliberadamente tolerante: nomes fora do padrão, planilhas em
subpastas e anos ausentes geram AVISO, não descarte. O descarte só ocorre
quando o arquivo não é uma planilha legível.
"""

from __future__ import annotations

import re
import shutil
import time
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# CONTRATOS_2027, Contratos 2027, CONTRATOS-2027…
_RE_PASTA_CONTRATOS = re.compile(r"^contratos[\s_\-]*(\d{4})$", re.IGNORECASE)

# Padrão oficial: <Secretaria>_Controle_Contratos_<Ano>
_RE_ARQUIVO_OFICIAL = re.compile(
    r"^(?P<secretaria>.+?)[\s_\-]*controle[\s_\-]*contratos[\s_\-]*(?P<ano>\d{4})$",
    re.IGNORECASE,
)

# Prefixo numérico que alguns ambientes de upload acrescentam.
_RE_PREFIXO_UPLOAD = re.compile(r"^\d{6,}[_\-]")

# Qualquer ano plausível no nome do arquivo.
_RE_ANO = re.compile(r"(?:19|20)\d{2}")

# Primeiro bloco de letras do nome (sigla da secretaria).
_RE_SIGLA = re.compile(r"[A-Za-zÀ-ÿ]{2,}")

EXTENSOES_PLANILHA = {".xlsx", ".xlsm"}
EXTENSOES_ANTIGAS = {".xls"}
LIXO = ("__MACOSX", ".DS_Store", "Thumbs.db")


def _sem_acentos(txt: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", txt)
                   if unicodedata.category(ch) != "Mn")


def _nome_limpo(stem: str) -> str:
    return _RE_PREFIXO_UPLOAD.sub("", stem)


@dataclass
class PlanilhaPacote:
    caminho: Path
    secretaria: str
    ano_arquivo: int | None
    nome_original: str
    caminho_relativo: str


@dataclass
class Pacote:
    exercicio: int
    pasta_contratos: Path | None
    raiz: Path
    planilhas: list[PlanilhaPacote] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    auditoria: list[dict] = field(default_factory=list)

    @property
    def secretarias(self) -> list[str]:
        return sorted({p.secretaria for p in self.planilhas})


class PacoteInvalido(Exception):
    """Pacote que não pode ser aproveitado de forma alguma."""


def _relativo(caminho: Path, raiz: Path) -> str:
    try:
        return str(caminho.relative_to(raiz)).replace("\\", "/")
    except ValueError:
        return caminho.name


def _e_lixo(caminho: Path) -> bool:
    if any(parte in LIXO for parte in caminho.parts):
        return True
    return caminho.name.startswith(("~$", "."))


# ---------------------------------------------------------------------------
# Localização da pasta de contratos
# ---------------------------------------------------------------------------
def _localizar_pastas_contratos(raiz: Path) -> list[tuple[Path, int]]:
    achadas: list[tuple[Path, int]] = []
    for caminho in sorted(raiz.rglob("*")):
        if not caminho.is_dir() or _e_lixo(caminho):
            continue
        m = _RE_PASTA_CONTRATOS.match(_sem_acentos(caminho.name).strip())
        if m:
            achadas.append((caminho, int(m.group(1))))
    achadas.sort(key=lambda t: t[1], reverse=True)
    return achadas


# ---------------------------------------------------------------------------
# Identificação de cada planilha
# ---------------------------------------------------------------------------
def _identificar(arq: Path, exercicio: int) -> tuple[str | None, int | None, list[str]]:
    """
    Extrai (secretaria, ano) do nome do arquivo.

    O padrão oficial é o caminho preferencial; qualquer outro nome ainda é
    aproveitado, com aviso, desde que dele se consiga extrair uma sigla.
    """
    avisos: list[str] = []
    stem = _nome_limpo(arq.stem)
    normalizado = _sem_acentos(stem).strip()

    m = _RE_ARQUIVO_OFICIAL.match(normalizado)
    if m:
        secretaria = m.group("secretaria").strip(" _-").upper()
        if secretaria:
            return secretaria, int(m.group("ano")), avisos

    # Fora do padrão: aproveita assim mesmo.
    anos = _RE_ANO.findall(normalizado)
    ano = int(anos[-1]) if anos else None

    sem_ano = _RE_ANO.sub(" ", normalizado)
    sigla_m = _RE_SIGLA.search(sem_ano)
    if not sigla_m:
        return None, ano, avisos

    secretaria = sigla_m.group(0).upper()
    avisos.append(
        f"'{arq.name}' está fora do padrão "
        f"'<Secretaria>_Controle_Contratos_<Ano>.xlsx'. Foi carregado assim "
        f"mesmo, como unidade '{secretaria}'"
        + (f", exercício {ano}." if ano else f", assumindo o exercício {exercicio}.")
    )
    return secretaria, ano, avisos


# ---------------------------------------------------------------------------
# Varredura
# ---------------------------------------------------------------------------
def _varrer(raiz: Path, pasta_alvo: Path | None, exercicio: int
            ) -> tuple[list[PlanilhaPacote], list[str], list[dict]]:
    planilhas: list[PlanilhaPacote] = []
    avisos: list[str] = []
    auditoria: list[dict] = []

    for arq in sorted(raiz.rglob("*")):
        if not arq.is_file() or _e_lixo(arq):
            continue

        rel = _relativo(arq, raiz)
        ext = arq.suffix.lower()

        if ext in EXTENSOES_ANTIGAS:
            auditoria.append({"arquivo": rel, "situacao": "ignorado",
                              "motivo": "formato .xls antigo — abra no Excel e "
                                        "salve como .xlsx"})
            avisos.append(f"'{arq.name}' está no formato .xls antigo. "
                          f"Salve como .xlsx e envie novamente.")
            continue

        if ext not in EXTENSOES_PLANILHA:
            auditoria.append({"arquivo": rel, "situacao": "ignorado",
                              "motivo": f"não é planilha ({ext or 'sem extensão'})"})
            continue

        dentro = pasta_alvo is not None and pasta_alvo in arq.parents
        if not dentro:
            avisos.append(
                f"'{rel}' está fora da pasta "
                f"{pasta_alvo.name if pasta_alvo else 'CONTRATOS_<ano>'} e foi "
                f"carregado assim mesmo."
            )

        secretaria, ano, avs = _identificar(arq, exercicio)
        avisos.extend(avs)

        if not secretaria:
            auditoria.append({"arquivo": rel, "situacao": "ignorado",
                              "motivo": "não foi possível identificar a sigla da "
                                        "secretaria no nome do arquivo"})
            avisos.append(f"'{arq.name}': não foi possível identificar a "
                          f"secretaria pelo nome do arquivo.")
            continue

        if ano is not None and ano != exercicio:
            avisos.append(
                f"'{arq.name}' refere-se a {ano}, mas o exercício do pacote é "
                f"{exercicio}. Foi carregado assim mesmo; confira se o arquivo "
                f"é o correto."
            )

        planilhas.append(PlanilhaPacote(
            caminho=arq, secretaria=secretaria, ano_arquivo=ano,
            nome_original=arq.name, caminho_relativo=rel,
        ))

    return planilhas, avisos, auditoria


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------
def _limpar_antigas(base: Path, manter: Path | None = None) -> None:
    """
    Remove extrações anteriores. Falhas são toleradas: no Windows, um arquivo
    ainda aberto por outro processo impede a exclusão, e isso não pode
    derrubar o carregamento do pacote novo.
    """
    if not base.exists():
        return
    for filho in base.iterdir():
        if manter is not None and filho == manter:
            continue
        shutil.rmtree(filho, ignore_errors=True) if filho.is_dir() else None


def extrair_pacote(zip_path: Path, base_trabalho: Path) -> Pacote:
    """
    Extrai o .zip em uma subpasta NOVA de `base_trabalho` e devolve o Pacote.

    Cada carga usa um diretório próprio, em vez de apagar e recriar sempre o
    mesmo. Isso evita o erro de "arquivo em uso" no Windows quando a carga
    anterior ainda mantém planilhas abertas.
    """
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise PacoteInvalido(f"Pacote não encontrado: {zip_path}")
    if not zipfile.is_zipfile(zip_path):
        raise PacoteInvalido(
            f"'{zip_path.name}' não é um arquivo .zip válido. Compacte a pasta "
            f"novamente (botão direito → Enviar para → Pasta compactada)."
        )

    base_trabalho.mkdir(parents=True, exist_ok=True)
    destino = base_trabalho / f"carga_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%1000:03d}"
    destino.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        raiz_resolvida = destino.resolve()
        for membro in zf.namelist():
            alvo = (destino / membro).resolve()
            if not str(alvo).startswith(str(raiz_resolvida)):
                raise PacoteInvalido(f"Pacote contém caminho inválido: {membro}")
        zf.extractall(destino)

    avisos: list[str] = []
    pastas = _localizar_pastas_contratos(destino)

    if pastas:
        pasta_alvo, exercicio = pastas[0]
        if len(pastas) > 1:
            outras = ", ".join(f"{p.name}" for p, _ in pastas[1:])
            avisos.append(
                f"O pacote traz mais de uma pasta de exercício ({pasta_alvo.name}, "
                f"{outras}). Foi adotado o exercício {exercicio}; as planilhas das "
                f"demais pastas também foram carregadas."
            )
    else:
        # Sem CONTRATOS_<ano>: não desiste — deduz o exercício pelos arquivos.
        pasta_alvo = None
        anos: list[int] = []
        for arq in destino.rglob("*"):
            if arq.is_file() and arq.suffix.lower() in EXTENSOES_PLANILHA and not _e_lixo(arq):
                achados = _RE_ANO.findall(_nome_limpo(arq.stem))
                if achados:
                    anos.append(int(achados[-1]))
        if not anos:
            raise PacoteInvalido(
                "O pacote não contém a pasta 'CONTRATOS_<ano>' nem planilhas "
                ".xlsx com o ano no nome. Estrutura esperada: "
                "pacote.zip → pasta → CONTRATOS_<ano> → planilhas."
            )
        exercicio = max(set(anos), key=anos.count)
        avisos.append(
            f"O pacote não traz a pasta 'CONTRATOS_<ano>'. O exercício {exercicio} "
            f"foi deduzido pelo nome das planilhas. Para evitar ambiguidade, "
            f"coloque as planilhas dentro de uma pasta 'CONTRATOS_{exercicio}'."
        )

    planilhas, avisos_varredura, auditoria = _varrer(destino, pasta_alvo, exercicio)
    avisos.extend(avisos_varredura)

    if not planilhas:
        raise PacoteInvalido(
            "Nenhuma planilha .xlsx foi encontrada no pacote. Verifique se as "
            "planilhas estão dentro da pasta 'CONTRATOS_<ano>' e se não foram "
            "salvas no formato .xls antigo."
        )

    # Limpa cargas anteriores só depois que a nova está pronta.
    _limpar_antigas(base_trabalho, manter=destino)

    return Pacote(
        exercicio=exercicio,
        pasta_contratos=pasta_alvo,
        raiz=destino,
        planilhas=planilhas,
        avisos=avisos,
        auditoria=auditoria,
    )


def pacote_mais_recente(pasta_pacotes: Path) -> Path | None:
    zips = [p for p in pasta_pacotes.glob("*.zip") if not p.name.startswith(("~$", "."))]
    return max(zips, key=lambda p: p.stat().st_mtime) if zips else None
