"""
adaptador_sigo.py
-----------------
Monta o vetor `CONTRACTS` que alimenta o painel SIGO, a partir das planilhas
de um pacote (.zip) já extraído.

Responsabilidades:
  1. Ler cada planilha do pacote (leiaute nativo "Base de Dados" ou legado).
  2. Garantir identidade única de cada contrato (num/ficha) — ver nota abaixo.
  3. Recalcular os indicadores de alerta na data corrente.
  4. Entregar objetos com exatamente as chaves que o frontend espera.

Nota sobre num/ficha
--------------------
O SIGO usa `unidade + '|' + (ficha || num)` como chave de deduplicação. Na
planilha 2027 a coluna "Ficha" vem quase toda vazia e a coluna "Nº" tem
lacunas — se fossem usadas como estão, contratos distintos colidiriam na
mesma chave e desapareceriam do painel. Por isso a ficha é sintetizada
(C01, C02, …) quando ausente, preservando o valor da planilha quando existe.
"""

from __future__ import annotations

from datetime import date, datetime

from leitor import XKEYS, ler_planilha
from pacote import Pacote

# Chaves extras (leiaute 2027) que viajam junto com o registro. O painel
# ignora chaves que não conhece, então são inofensivas e ficam disponíveis
# para os relatórios por fonte quando essa aba for habilitada.
EXTRAS = [
    "pago_fonte_livre", "pago_fonte_vinculado", "pago_fonte_convenio",
    "pago_fonte_op_credito", "pago_fonte_emendas", "verificacao_pago_fonte",
]


def _f(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dias_ate(termino_iso, referencia: date):
    if not termino_iso:
        return None
    try:
        d = datetime.strptime(termino_iso, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (d - referencia).days


def _reais(v: float) -> str:
    """Formata em reais no padrão brasileiro (1.234.567,89)."""
    return "R$ " + f"{v:,.2f}".translate(str.maketrans({",": ".", ".": ","}))


def _sim_nao(valor: bool) -> str:
    return "Sim" if valor else "Não"


def _calcular_alertas(reg: dict, referencia: date) -> None:
    """
    Recalcula os indicadores de alerta com as MESMAS regras do frontend.

    Os valores gravados na planilha ficam congelados no último recálculo do
    Excel; aqui são refeitos na data em que o painel é servido. Quando não há
    base para calcular (por exemplo, contrato sem término de vigência),
    preserva-se o que veio da planilha.
    """
    total = _f(reg.get("valor_total_exerc")) or 0.0
    saldo_emp = _f(reg.get("saldo_empenhar"))
    pct_emp = _f(reg.get("pct_empenhado"))

    dias = _dias_ate(reg.get("termino_vig"), referencia)
    if dias is not None:
        reg["dias_vencer"] = float(dias)
        reg["vencido"] = _sim_nao(dias < 0)
        reg["vence_90"] = _sim_nao(0 <= dias <= 90)

    if total > 0 and saldo_emp is not None:
        reg["saldo_menor_20"] = _sim_nao((saldo_emp / total) < 0.20)

    if pct_emp is not None:
        reg["exec_maior_90"] = _sim_nao(pct_emp > 0.90)


def _normalizar(reg: dict, secretaria: str, indice: int, exercicio: int) -> dict:
    """Ajusta identidade, unidade e exercício de um registro."""
    # --- Identidade única -------------------------------------------------
    ficha = reg.get("ficha")
    if not ficha or not str(ficha).strip():
        ficha = f"C{indice:02d}"
    reg["ficha"] = str(ficha).strip()

    num = reg.get("num")
    if num is None or not str(num).strip():
        num = indice
    reg["num"] = num

    # --- Unidade / órgão --------------------------------------------------
    reg["org"] = secretaria
    reg["unidade"] = secretaria
    if not reg.get("unidade_gestora"):
        reg["unidade_gestora"] = secretaria

    # --- Exercício --------------------------------------------------------
    # A coluna "Exercício Financeiro" da planilha vem quase sempre vazia;
    # o exercício de referência é o declarado na pasta CONTRATOS_<ano>.
    reg["exercicio"] = exercicio

    return reg


def montar_contracts(pct: Pacote, referencia=None):
    """
    Constrói o vetor CONTRACTS a partir de um Pacote já extraído.

    Devolve (contratos, diagnostico), em que `diagnostico` traz o resumo da
    carga por secretaria, o leiaute detectado e os avisos encontrados.
    """
    referencia = referencia or date.today()
    contratos = []
    resumo = []
    avisos = list(pct.avisos)

    for planilha in pct.planilhas:
        try:
            registros, diag_arq = ler_planilha(planilha.caminho)
        except Exception as e:  # noqa: BLE001
            avisos.append(f"Falha ao ler '{planilha.nome_original}': {e}")
            resumo.append({
                "secretaria": planilha.secretaria,
                "arquivo": planilha.nome_original,
                "caminho": planilha.caminho_relativo,
                "ano_arquivo": planilha.ano_arquivo,
                "origem": None,
                "contratos": 0,
                "motivo": f"erro de leitura: {e}",
            })
            continue

        if not registros:
            # A secretaria não aparece no painel — explica exatamente por quê.
            avisos.append(
                f"'{planilha.nome_original}' não trouxe nenhum contrato. "
                f"{diag_arq.get('motivo') or ''}".strip()
            )

        for i, reg in enumerate(registros, start=1):
            _normalizar(reg, planilha.secretaria, i, pct.exercicio)
            _calcular_alertas(reg, referencia)

            # Mantém apenas as chaves conhecidas pelo painel + extras + rótulos.
            limpo = {k: reg.get(k) for k in XKEYS}
            for k in EXTRAS:
                limpo[k] = reg.get(k)
            limpo["org"] = reg["org"]
            limpo["unidade"] = reg["unidade"]
            contratos.append(limpo)

        resumo.append({
            "secretaria": planilha.secretaria,
            "arquivo": planilha.nome_original,
            "caminho": planilha.caminho_relativo,
            "ano_arquivo": planilha.ano_arquivo,
            "origem": diag_arq.get("origem"),
            "abas": diag_arq.get("abas"),
            "tentativas": diag_arq.get("tentativas"),
            "contratos": len(registros),
            "motivo": diag_arq.get("motivo"),
            "detalhe": diag_arq.get("detalhe"),
        })

    # --- Alertas de qualidade dos dados -----------------------------------
    # Não alteram nenhum valor: apenas sinalizam leituras que podem induzir a
    # conclusão errada na aba de Execução Orçamentária.
    alertas: list[str] = []

    def _n(v):
        return v if isinstance(v, (int, float)) else None

    # "Valor a Suplementar" nasce de (Saldo a Empenhar − Saldo Orçamentário da
    # Unidade). Quando a coluna do saldo orçamentário não é preenchida, ela
    # vale zero e a suplementação passa a repetir o saldo a empenhar — o painel
    # exibe um valor alto que sugere necessidade de suplementação inexistente.
    suspeitos = [
        c for c in contratos
        if (_n(c.get("valor_suplementar")) or 0) > 0
        and not (_n(c.get("saldo_orc_unidade")) or 0)
        and abs((_n(c.get("valor_suplementar")) or 0)
                - (_n(c.get("saldo_empenhar")) or 0)) < 0.01
    ]
    if suspeitos:
        total_susp = sum(_n(c.get("valor_suplementar")) or 0 for c in suspeitos)
        unidades = sorted({c["unidade"] for c in suspeitos})
        alertas.append(
            f"O KPI 'A suplementar' soma {_reais(total_susp)} em "
            f"{len(suspeitos)} contrato(s) de {', '.join(unidades)} apenas "
            f"porque a coluna 'Saldo Orçamentário da Unidade' está zerada na "
            f"planilha — nesse caso a suplementação repete o saldo a empenhar. "
            f"Preencha essa coluna para que o valor faça sentido."
        )

    sem_execucao = [c for c in contratos if not (_n(c.get("valor_empenhado")) or 0)]
    if contratos and len(sem_execucao) == len(contratos):
        alertas.append(
            "Nenhum contrato tem valor empenhado. Os indicadores de execução "
            "(empenhado, liquidado, pago) ficarão zerados até que as "
            "secretarias lancem a execução nas planilhas."
        )

    # Mesma ordenação que o SIGO aplica após importar.
    contratos.sort(key=lambda r: (str(r.get("unidade") or ""), str(r.get("ficha") or "")))

    diagnostico = {
        "exercicio": pct.exercicio,
        "total_contratos": len(contratos),
        "secretarias": sorted({c["unidade"] for c in contratos}),
        "secretarias_sem_dados": sorted(
            r["secretaria"] for r in resumo if r["contratos"] == 0
        ),
        "por_planilha": resumo,
        "avisos": avisos,
        "auditoria_arquivos": pct.auditoria,
        "alertas_qualidade": alertas,
        "pasta_contratos": (pct.pasta_contratos.name if pct.pasta_contratos else None),
        "data_referencia": referencia.isoformat(),
    }
    return contratos, diagnostico
