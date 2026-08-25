"""
ajustes_frontend.py
-------------------
Ajustes funcionais aplicados ao HTML do SIGO **no momento de servir**.

O arquivo em disco continua intacto (byte a byte). Cada ajuste é ancorado em
um trecho único do HTML e falha de forma explícita se a âncora não for
encontrada — assim, se o frontend for substituído por uma nova versão, o
problema aparece imediatamente em vez de gerar uma página silenciosamente
quebrada.

Ajustes desta versão
--------------------
  1. ENVIO DO PACOTE .ZIP PELA INTERFACE
     O botão "Atualizar dados" passa a aceitar o pacote compactado e o envia
     ao servidor, que reprocessa tudo e recarrega o painel já no exercício
     do pacote. O envio de .xlsx avulso continua funcionando como antes.

  2. GRÁFICO "CONTRATOS POR TIPO DE OBJETO"
     O gráfico usava a função genérica de barras, que exibe no máximo 15
     categorias e trunca os rótulos em 28 caracteres — com isso, o 16º tipo
     do catálogo ficava de fora e tipos de nome parecido apareciam
     idênticos. Passa a exibir TODOS os tipos, com rolagem vertical dentro
     do próprio cartão (a estrutura da página não muda).
"""

from __future__ import annotations


class AncoraNaoEncontrada(RuntimeError):
    """O HTML não contém o trecho esperado por um ajuste."""


def _trocar(html: str, antigo: str, novo: str, rotulo: str) -> str:
    """Substitui uma ocorrência única, falhando se houver zero ou várias."""
    n = html.count(antigo)
    if n != 1:
        raise AncoraNaoEncontrada(
            f"Ajuste '{rotulo}': esperava 1 ocorrência da âncora, encontrei {n}."
        )
    return html.replace(antigo, novo, 1)


# ---------------------------------------------------------------------------
# 0. Base compartilhada dos gráficos com rolagem
#
#    CORREÇÃO IMPORTANTE (empilhamento de faixas de rolagem)
#    ------------------------------------------------------
#    A versão anterior obtinha o contêiner com `cv.parentElement`. Isso só
#    estava correto na PRIMEIRA renderização: a partir da segunda, o pai do
#    canvas já era a própria faixa de rolagem criada antes. A busca por uma
#    faixa existente passava então a ocorrer DENTRO da faixa anterior, não
#    a encontrava, e uma nova era criada aninhada — uma a cada mudança de
#    filtro, exatamente como observado.
#
#    A função abaixo resolve o contêiner sempre pelo `.chart-box` (que é fixo),
#    devolve o canvas para ele, remove qualquer faixa remanescente — inclusive
#    as aninhadas de execuções anteriores — e cria uma única faixa nova. É
#    idempotente: chamar dez vezes deixa o mesmo resultado de chamar uma.
# ---------------------------------------------------------------------------
_FUNCAO_BASE = r"""
/* === Contêiner de rolagem: sempre uma única faixa ========================= */
function prepararFaixa(cv, classe){
  var caixa = cv.closest ? cv.closest('.chart-box') : null;
  if(!caixa){
    /* Sem .chart-box (layout inesperado): sobe um nível a partir de qualquer
       faixa antiga, para não aninhar. */
    caixa = cv.parentElement;
    while(caixa && /^rolagem-/.test(caixa.className)) caixa = caixa.parentElement;
  }
  if(!caixa) return null;

  /* Tira o canvas de dentro de qualquer faixa antiga... */
  caixa.appendChild(cv);
  /* ...e elimina TODAS as faixas remanescentes, inclusive aninhadas. */
  var antigas = caixa.querySelectorAll('.' + classe);
  for(var i = antigas.length - 1; i >= 0; i--){
    if(antigas[i].parentNode) antigas[i].parentNode.removeChild(antigas[i]);
  }

  var faixa = document.createElement('div');
  faixa.className = classe;
  faixa.style.position = 'relative';
  caixa.insertBefore(faixa, cv);
  faixa.appendChild(cv);
  return { caixa: caixa, faixa: faixa };
}
"""


# ---------------------------------------------------------------------------
# 1. Botão de atualização: aceita o pacote .zip
# ---------------------------------------------------------------------------
_BTN_ANTIGO = '>Atualizar dados (.xlsx)</button>'
_BTN_NOVO = '>Atualizar dados (.zip)</button>'

_INPUT_ANTIGO = '<input type="file" id="fileImport" accept=".xlsx" multiple style="display:none">'
_INPUT_NOVO = '<input type="file" id="fileImport" accept=".zip,.xlsx" multiple style="display:none">'

# Script acrescentado ao final: intercepta o envio e trata o .zip.
_SCRIPT_UPLOAD = r"""
<script>
/* === Atualização de dados por pacote .zip + histórico de relatórios ======= */
(function(){
  var inp = document.getElementById('fileImport');
  var btn = document.getElementById('btnImport');
  if(!inp || !btn) return;

  var tratarXlsx = inp.onchange;   /* comportamento original (.xlsx avulso) */

  btn.title = 'Envie o pacote .zip com a pasta CONTRATOS_<ano> contendo as '
            + 'planilhas das secretarias. O painel e reprocessado no servidor '
            + 'e recarregado ja no exercicio do pacote.';

  /* --- Botão para reabrir o relatório da última atualização --------------- */
  var btnRel = document.createElement('button');
  btnRel.className = btn.className;
  btnRel.id = 'btnRelatorios';
  btnRel.textContent = 'Relatório de dados';
  btnRel.title = 'Reabrir o relatório da última atualização e consultar o histórico.';
  btn.parentNode.insertBefore(btnRel, btn.nextSibling);

  /* --- Janela reutilizável ------------------------------------------------ */
  function janela(){
    var d = document.getElementById('sigoPainelCarga');
    if(!d){
      d = document.createElement('div');
      d.id = 'sigoPainelCarga';
      d.style.cssText = 'position:fixed;inset:0;background:rgba(15,28,42,.55);'
        + 'display:flex;align-items:center;justify-content:center;z-index:99999;'
        + 'font:13px/1.55 system-ui,-apple-system,Segoe UI,sans-serif';
      d.innerHTML =
          '<div style="background:#fff;max-width:760px;width:calc(100% - 40px);'
        + 'max-height:84vh;display:flex;flex-direction:column;border-radius:10px;'
        + 'box-shadow:0 18px 50px rgba(0,0,0,.35)">'
        + '<div id="sigoPainelTopo" style="background:#1B4B7A;color:#fff;'
        + 'padding:12px 16px;font-weight:700;border-radius:10px 10px 0 0;'
        + 'display:flex;justify-content:space-between;align-items:center">'
        + '<span id="sigoPainelTitulo">Atualização de dados</span>'
        + '<span id="sigoPainelSel"></span></div>'
        + '<div id="sigoPainelCorpo" style="padding:14px 16px;overflow:auto;'
        + 'color:#243444;flex:1"></div>'
        + '<div style="padding:10px 16px 14px;text-align:right;border-top:1px solid #e6ebf1" '
        + 'id="sigoPainelRodape"></div></div>';
      document.body.appendChild(d);
      d.addEventListener('click', function(ev){ if(ev.target === d) fechar(); });
    }
    d.style.display = 'flex';
    return d;
  }
  function fechar(){
    var d = document.getElementById('sigoPainelCarga');
    if(d) d.style.display = 'none';
  }
  function escapar(t){
    return String(t == null ? '' : t)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  function pintar(titulo, corpoHTML, cor, botoes, seletorHTML){
    janela();
    document.getElementById('sigoPainelTitulo').textContent = titulo;
    document.getElementById('sigoPainelTopo').style.background = cor || '#1B4B7A';
    document.getElementById('sigoPainelSel').innerHTML = seletorHTML || '';
    document.getElementById('sigoPainelCorpo').innerHTML = corpoHTML;
    var rod = document.getElementById('sigoPainelRodape');
    rod.innerHTML = '';
    (botoes || []).forEach(function(b){
      var el = document.createElement('button');
      el.textContent = b.texto;
      el.style.cssText = 'margin-left:8px;padding:8px 14px;border:0;border-radius:6px;'
        + 'cursor:pointer;font-weight:600;background:' + (b.cor || '#1B4B7A') + ';color:#fff';
      el.onclick = b.acao;
      rod.appendChild(el);
    });
  }

  /* --- Símbolos de situação ---------------------------------------------- */
  var OK   = '<span style="color:#2E8B6A;font-weight:900;font-size:15px">&#10004;</span>';
  var FALHA= '<span style="color:#B24545;font-weight:900;font-size:15px">&#10008;</span>';

  /* --- Montagem do relatório em HTML ------------------------------------- */
  function montarRelatorio(d, cabecalho){
    var H = [];
    if(cabecalho) H.push('<div style="margin-bottom:10px">' + escapar(cabecalho) + '</div>');

    var linhaInfo = [];
    if(d.exercicio) linhaInfo.push('Exercício <b>' + escapar(d.exercicio) + '</b>');
    if(d.pasta_contratos) linhaInfo.push('pasta <b>' + escapar(d.pasta_contratos) + '</b>');
    if(d.pacote) linhaInfo.push('pacote <b>' + escapar(d.pacote) + '</b>');
    if(linhaInfo.length)
      H.push('<div style="color:#5a6b7d;margin-bottom:12px">' + linhaInfo.join(' &middot; ') + '</div>');

    var lista = d.por_planilha || [];
    var comDados = lista.filter(function(p){ return p.contratos; }).length;
    var semDados = lista.length - comDados;

    H.push('<div style="display:flex;gap:16px;margin-bottom:12px;flex-wrap:wrap">'
      + '<div>' + OK + ' <b>' + comDados + '</b> secretaria(s) com dados</div>'
      + '<div>' + FALHA + ' <b>' + semDados + '</b> sem contratos</div>'
      + '<div><b>' + (d.total_contratos || 0) + '</b> contrato(s) no painel</div></div>');

    H.push('<table style="width:100%;border-collapse:collapse;font-size:12.5px">');
    H.push('<tr style="background:#f2f6fa;color:#1B4B7A;text-align:left">'
      + '<th style="padding:6px 8px;width:28px"></th>'
      + '<th style="padding:6px 8px">Secretaria</th>'
      + '<th style="padding:6px 8px;text-align:right;width:90px">Contratos</th>'
      + '<th style="padding:6px 8px">Situação</th></tr>');

    lista.forEach(function(p){
      var ok = !!p.contratos;
      var detalhe = ok
        ? ('lido de ' + escapar(p.origem || '—'))
        : escapar(p.motivo || 'sem contratos');
      if(!ok && p.abas && p.abas.length)
        detalhe += '<div style="color:#7b8794;margin-top:2px">abas: ' + escapar(p.abas.join(', ')) + '</div>';
      H.push('<tr style="border-bottom:1px solid #eef2f6">'
        + '<td style="padding:7px 8px;vertical-align:top">' + (ok ? OK : FALHA) + '</td>'
        + '<td style="padding:7px 8px;vertical-align:top"><b>' + escapar(p.secretaria) + '</b>'
        + '<div style="color:#7b8794">' + escapar(p.arquivo || '') + '</div></td>'
        + '<td style="padding:7px 8px;text-align:right;vertical-align:top">' + (p.contratos || 0) + '</td>'
        + '<td style="padding:7px 8px;vertical-align:top;color:' + (ok ? '#41566b' : '#8a4a4a') + '">'
        + detalhe + '</td></tr>');
    });
    H.push('</table>');

    if(semDados){
      H.push('<div style="margin-top:12px;padding:10px 12px;background:#fbf6ec;'
        + 'border-left:3px solid #C98A2B;color:#6b5a34">'
        + 'Secretaria sem contratos não significa falha do sistema: normalmente a '
        + 'planilha ainda não foi preenchida pela equipe responsável. A coluna '
        + '“Situação” indica o caso de cada uma.</div>');
    }

    if((d.alertas_qualidade || []).length){
      H.push('<div style="margin-top:12px;padding:10px 12px;background:#fdf1f1;'
        + 'border-left:3px solid #B24545;color:#7a3b3b">'
        + '<b>Atenção na leitura dos indicadores</b><ul style="margin:6px 0 0 18px">');
      d.alertas_qualidade.forEach(function(a){ H.push('<li>' + escapar(a) + '</li>'); });
      H.push('</ul></div>');
    }

    var ign = (d.auditoria_arquivos || []).filter(function(a){ return a.situacao === 'ignorado'; });
    if(ign.length){
      H.push('<div style="margin-top:12px"><b>Arquivos ignorados</b><ul style="margin:6px 0 0 18px">');
      ign.forEach(function(a){
        H.push('<li>' + escapar(a.arquivo) + ' — ' + escapar(a.motivo) + '</li>');
      });
      H.push('</ul></div>');
    }
    if((d.avisos || []).length){
      H.push('<div style="margin-top:12px"><b>Avisos</b><ul style="margin:6px 0 0 18px;color:#6b5a34">');
      d.avisos.forEach(function(a){ H.push('<li>' + escapar(a) + '</li>'); });
      H.push('</ul></div>');
    }
    return H.join('');
  }

  /* --- Histórico ---------------------------------------------------------- */
  async function abrirRelatorio(id){
    pintar('Relatório de atualização', '<div style="color:#5a6b7d">Carregando…</div>', '#1B4B7A', []);
    try{
      var lista = await (await fetch('/api/relatorios')).json();
      var resp  = await fetch('/api/relatorios/' + (id || 'ultimo'));
      if(!resp.ok){
        return pintar('Relatório de atualização',
          '<div>Nenhuma atualização registrada ainda. O relatório fica disponível '
          + 'assim que o primeiro pacote for enviado.</div>', '#1B4B7A',
          [{texto:'Fechar', acao:fechar}]);
      }
      var d = await resp.json();
      var itens = (lista.relatorios || []);
      var sel = '';
      if(itens.length > 1){
        sel = '<select id="sigoHistorico" style="font:600 12px system-ui;padding:4px 6px;'
            + 'border-radius:5px;border:0">';
        itens.forEach(function(it){
          var m = (it.id === d.id) ? ' selected' : '';
          sel += '<option value="' + escapar(it.id) + '"' + m + '>'
              + escapar(it.momento_legivel) + ' — ' + it.total_contratos + ' contratos</option>';
        });
        sel += '</select>';
      }
      pintar('Relatório de atualização',
             montarRelatorio(d.diagnostico || {}, 'Carga de ' + (d.momento_legivel || '')),
             '#1B4B7A',
             [{texto:'Abrir em texto', cor:'#5a6b7d', acao:function(){
                 window.open('/api/relatorios/' + d.id + '/texto', '_blank'); }},
              {texto:'Fechar', acao:fechar}],
             sel);
      var combo = document.getElementById('sigoHistorico');
      if(combo) combo.onchange = function(){ abrirRelatorio(this.value); };
    }catch(err){
      pintar('Relatório de atualização',
        '<div style="color:#B24545">Não foi possível carregar: ' + escapar(err.message) + '</div>',
        '#B24545', [{texto:'Fechar', acao:fechar}]);
    }
  }
  btnRel.onclick = function(){ abrirRelatorio(''); };

  /* --- Envio do pacote ---------------------------------------------------- */
  inp.onchange = async function(e){
    var arquivos = Array.prototype.slice.call(e.target.files || []);
    if(!arquivos.length) return;
    var zips = arquivos.filter(function(f){
      return f.name.toLowerCase().slice(-4) === '.zip';
    });

    if(!zips.length){
      if(typeof tratarXlsx === 'function') return tratarXlsx.call(inp, e);
      return;
    }

    pintar('Atualizando dados',
      '<div>Enviando <b>' + escapar(zips[0].name) + '</b> e processando as planilhas…</div>'
      + '<div style="color:#5a6b7d;margin-top:6px">Isso pode levar alguns segundos '
      + 'por secretaria.</div>', '#1B4B7A', []);

    var resp, texto;
    try{
      var fd = new FormData();
      fd.append('arquivo', zips[0]);
      resp = await fetch('/api/pacote', { method:'POST', body: fd });
      texto = await resp.text();
    }catch(err){
      e.target.value = '';
      return pintar('Falha de comunicação',
        '<div>Não foi possível falar com o servidor.</div>'
        + '<div style="margin-top:8px;color:#B24545">' + escapar(err.message) + '</div>'
        + '<div style="margin-top:8px">Verifique se o servidor continua em execução '
        + 'na janela do terminal.</div>',
        '#B24545', [{texto:'Fechar', acao:fechar}]);
    }

    /* A resposta pode não ser JSON (erro interno, proxy). Nunca presumir o
       formato: ler como texto e só então tentar interpretar. */
    var dados = null;
    try{ dados = JSON.parse(texto); }catch(_){ dados = null; }
    e.target.value = '';

    if(!resp.ok || !dados){
      var det = (dados && dados.erro) ? dados.erro : (texto || '').slice(0, 400);
      return pintar('Não foi possível carregar o pacote',
        '<div>HTTP ' + resp.status + '</div>'
        + '<div style="margin-top:8px;color:#B24545;white-space:pre-line">' + escapar(det) + '</div>'
        + '<div style="margin-top:8px;color:#5a6b7d">O detalhamento completo aparece '
        + 'na janela do terminal onde o servidor está sendo executado.</div>',
        '#B24545', [{texto:'Fechar', acao:fechar}]);
    }

    var d = dados.diagnostico || {};
    pintar('Dados atualizados', montarRelatorio(d, dados.mensagem), '#2E8B6A',
      [{texto:'Abrir em texto', cor:'#5a6b7d', acao:function(){
          window.open('/api/relatorios/' + (d.relatorio_id || 'ultimo') + '/texto', '_blank'); }},
       {texto:'Atualizar painel', cor:'#2E8B6A', acao:function(){ location.reload(); }}]);
  };
})();
</script>
"""


# ---------------------------------------------------------------------------
# 2. Gráfico "Contratos por tipo de objeto": todos os tipos, com rolagem
# ---------------------------------------------------------------------------
_CHAMADA_ANTIGA = "hbar('chTipo',agg(data,'tipo_objeto'),null);"
_CHAMADA_NOVA = "hbarTipoTodos('chTipo',agg(data,'tipo_objeto'));"

# Definida no MESMO bloco de script do painel (logo após o vetor de dados),
# para já estar disponível na primeira renderização.
_FUNCAO_TIPO = r"""
/* === Gráfico de tipos de objeto: exibe TODOS os tipos, com rolagem ======== */
function hbarTipoTodos(id, obj){
  destroy(id);
  var itens = Object.entries(obj).sort(function(a,b){ return b[1]-a[1]; });
  var cv = document.getElementById(id);
  if(!cv) return;

  var ref = prepararFaixa(cv, 'rolagem-tipos');
  if(!ref) return;
  var caixa = ref.caixa, interno = ref.faixa;
  caixa.style.overflowY = 'auto';
  caixa.style.overflowX = 'hidden';
  caixa.style.paddingRight = '4px';

  /* Altura proporcional ao número de tipos: a barra rola dentro do cartão,
     sem alterar o tamanho do cartão nem o restante da página. */
  var alturaLinha = 30;
  var minima = caixa.clientHeight || 250;
  interno.style.height = Math.max(minima, itens.length * alturaLinha + 24) + 'px';

  var rotulo = function(t){ return t.length > 46 ? t.slice(0,46) + '…' : t; };

  charts[id] = new Chart(cv, {
    type: 'bar',
    data: {
      labels: itens.map(function(x){ return rotulo(x[0]); }),
      datasets: [{
        data: itens.map(function(x){ return x[1]; }),
        backgroundColor: '#4A87B8',
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: {
          title: function(c){ return itens[c[0].dataIndex][0]; },   /* nome completo */
          label: function(c){ return c.raw + ' contrato(s)'; }
        }}
      },
      scales: {
        x: { ticks: { precision: 0 } },
        y: { ticks: { autoSkip: false, font: { size: 11 } } }
      }
    }
  });
}
"""


# ---------------------------------------------------------------------------
# 3. Execução Orçamentária: "Previsto × Empenhado × Pago por unidade"
#    Com muitas secretarias as barras ficam finas demais. Passa a ter rolagem
#    horizontal: cada unidade recebe uma faixa de largura fixa e o gráfico
#    desliza dentro do próprio cartão, que mantém o tamanho original.
# ---------------------------------------------------------------------------
_ORC_ANTIGO = "  const uni=[...new Set(data.map(c=>c.unidade))];\n  destroy('chOrcUnidade');\n  charts.chOrcUnidade=new Chart(document.getElementById('chOrcUnidade'),{type:'bar',\n    data:{labels:uni,datasets:[\n      {label:'Previsto',data:uni.map(u=>sum(data.filter(c=>c.unidade===u),'valor_total_exerc')),backgroundColor:'#1B4B7A',borderRadius:4},\n      {label:'Empenhado',data:uni.map(u=>sum(data.filter(c=>c.unidade===u),'valor_empenhado')),backgroundColor:'#2E8B6A',borderRadius:4},\n      {label:'Pago',data:uni.map(u=>sum(data.filter(c=>c.unidade===u),'valor_pago')),backgroundColor:'#C98A2B',borderRadius:4}]},\n    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top'},tooltip:{callbacks:{label:c=>c.dataset.label+': '+fmtBRL(c.raw)}}},scales:{y:{ticks:{callback:money}}}}});\n\n"

_ORC_NOVO = "  barOrcUnidadeRolavel(data);\n\n"

_FUNCAO_ORC = r"""
/* === Previsto x Empenhado x Pago por unidade ==============================
   Duas particularidades:

   1. TETO DE ESCALA. Quando uma secretaria tem orçamento muito acima das
      demais, o eixo se estica para caber a maior barra e todas as outras
      encolhem até sumir. O eixo passa a ter teto fixo de R$ 500 milhões: as
      barras que ultrapassam são cortadas na borda (a unidade recebe a marca
      "+++" no rótulo e o valor real continua no tooltip), e as demais voltam
      a ter altura legível.

   2. VISÃO EXPANDIDA. O botão "Expandir" abre o gráfico sem teto, com escala
      FIXA de 1 pixel por R$ 1 milhão. O gráfico fica maior que a tela e o
      usuário rola na horizontal e na vertical para ler todas as barras. */
var SERIES_ORC = [
  { rotulo: 'Previsto',  campo: 'valor_total_exerc', cor: '#1B4B7A' },
  { rotulo: 'Empenhado', campo: 'valor_empenhado',   cor: '#2E8B6A' },
  { rotulo: 'Pago',      campo: 'valor_pago',        cor: '#C98A2B' }
];
var TETO_ORC = 500000000;          /* R$ 500 milhões */
var PX_POR_REAL_ORC = 1 / 1000000; /* visão expandida: 1 px = R$ 1 milhão */
var DADOS_ORC = [];                /* recorte atual, usado pela expansão */

function somaOrc(dados, u, campo){
  return sum(dados.filter(function(c){ return c.unidade === u; }), campo);
}

function seriesOrc(dados, unidades){
  return SERIES_ORC.map(function(s){
    return {
      label: s.rotulo,
      data: unidades.map(function(u){ return somaOrc(dados, u, s.campo); }),
      backgroundColor: s.cor,
      borderRadius: 4
    };
  });
}

/* Legenda em HTML, fora da área que rola, com o botão de expandir ao lado. */
function cabecalhoOrc(cartao){
  var barra = cartao.querySelector('.legenda-orc');
  if(barra) return barra;

  barra = document.createElement('div');
  barra.className = 'legenda-orc';
  barra.style.cssText = 'display:flex;gap:14px;flex-wrap:wrap;align-items:center;'
    + 'margin:2px 0 8px;font-size:11.5px;color:#41566b';

  SERIES_ORC.forEach(function(s){
    var item = document.createElement('span');
    item.style.cssText = 'display:inline-flex;align-items:center;gap:6px';
    item.innerHTML = '<span style="width:12px;height:12px;border-radius:3px;'
      + 'background:' + s.cor + ';display:inline-block"></span>' + s.rotulo;
    barra.appendChild(item);
  });

  var btn = document.createElement('button');
  btn.type = 'button';
  btn.id = 'btnExpandirOrc';
  btn.textContent = 'Expandir';
  btn.title = 'Abrir o gráfico sem teto de escala, com rolagem horizontal e '
            + 'vertical para ler todas as barras.';
  btn.style.cssText = 'margin-left:auto;padding:2px 9px;font:600 11px system-ui,sans-serif;'
    + 'color:#1B4B7A;background:#eef3f8;border:1px solid #cfdcea;border-radius:5px;'
    + 'cursor:pointer;line-height:1.6';
  btn.onmouseover = function(){ btn.style.background = '#e2ebf4'; };
  btn.onmouseout  = function(){ btn.style.background = '#eef3f8'; };
  btn.onclick = abrirOrcExpandido;
  barra.appendChild(btn);

  var box = cartao.querySelector('.chart-box');
  cartao.insertBefore(barra, box);
  return barra;
}

function barOrcUnidadeRolavel(data){
  destroy('chOrcUnidade');
  var cv = document.getElementById('chOrcUnidade');
  if(!cv) return;

  DADOS_ORC = data;
  var uni = Array.from(new Set(data.map(function(c){ return c.unidade; })));

  var ref = prepararFaixa(cv, 'rolagem-orc');
  if(!ref) return;
  var caixa = ref.caixa, faixa = ref.faixa;
  faixa.style.height = '100%';
  caixa.style.overflowX = 'auto';
  caixa.style.overflowY = 'hidden';

  var cartao = caixa.closest ? caixa.closest('.card') : caixa.parentElement;
  if(cartao) cabecalhoOrc(cartao);

  var porUnidade = 78;
  var disponivel = caixa.clientWidth || 600;
  faixa.style.width = Math.max(disponivel, uni.length * porUnidade) + 'px';

  var datasets = seriesOrc(data, uni);

  /* Unidades cujo maior valor ultrapassa o teto recebem a marca "+++". */
  var estoura = uni.map(function(u, i){
    return datasets.some(function(d){ return d.data[i] > TETO_ORC; });
  });
  var rotulos = uni.map(function(u, i){ return estoura[i] ? u + ' +++' : u; });

  charts.chOrcUnidade = new Chart(cv, {
    type: 'bar',
    data: { labels: rotulos, datasets: datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: {
          title: function(c){ return uni[c[0].dataIndex]; },
          label: function(c){
            var t = c.dataset.label + ': ' + fmtBRL(c.raw);
            return (c.raw > TETO_ORC)
              ? t + ' (acima do teto do gráfico — use "Expandir")'
              : t;
          }
        }}
      },
      scales: {
        y: {
          max: TETO_ORC,
          ticks: {
            callback: function(v){
              return (v >= TETO_ORC) ? 'R$ 500M +++' : money(v);
            }
          }
        },
        x: { ticks: { autoSkip: false, maxRotation: 60, minRotation: 0, font: { size: 11 } } }
      }
    }
  });
}

/* --- Visão expandida: sem teto, escala fixa, rolagem nos dois eixos ------- */
function abrirOrcExpandido(){
  var jan = document.getElementById('sigoOrcExpandido');
  if(!jan){
    jan = document.createElement('div');
    jan.id = 'sigoOrcExpandido';
    jan.style.cssText = 'position:fixed;inset:0;background:rgba(15,28,42,.55);'
      + 'display:flex;align-items:center;justify-content:center;z-index:99998;'
      + 'font:13px/1.5 system-ui,-apple-system,Segoe UI,sans-serif';
    jan.innerHTML =
        '<div style="background:#fff;width:calc(100% - 48px);height:calc(100% - 60px);'
      + 'display:flex;flex-direction:column;border-radius:10px;'
      + 'box-shadow:0 18px 50px rgba(0,0,0,.35)">'
      + '<div style="background:#1B4B7A;color:#fff;padding:11px 16px;font-weight:700;'
      + 'border-radius:10px 10px 0 0;display:flex;justify-content:space-between;'
      + 'align-items:center">'
      + '<span>Previsto × Empenhado × Pago por unidade — todos os valores</span>'
      + '<button id="sigoOrcFechar" style="background:transparent;border:0;color:#fff;'
      + 'font-size:20px;line-height:1;cursor:pointer">&times;</button></div>'
      + '<div id="sigoOrcLegenda" style="padding:8px 16px 0;display:flex;gap:16px;'
      + 'flex-wrap:wrap;font-size:12px;color:#41566b"></div>'
      + '<div id="sigoOrcEscala" style="padding:4px 16px 6px;color:#7b8794;'
      + 'font-size:11.5px"></div>'
      + '<div id="sigoOrcArea" style="flex:1;overflow:auto;padding:0 16px 16px">'
      + '<div id="sigoOrcInterno" style="position:relative">'
      + '<canvas id="chOrcExpandido"></canvas></div></div></div>';
    document.body.appendChild(jan);
    jan.addEventListener('click', function(ev){ if(ev.target === jan) fecharOrcExpandido(); });
    document.getElementById('sigoOrcFechar').onclick = fecharOrcExpandido;
  }
  jan.style.display = 'flex';

  var leg = document.getElementById('sigoOrcLegenda');
  leg.innerHTML = '';
  SERIES_ORC.forEach(function(s){
    var it = document.createElement('span');
    it.style.cssText = 'display:inline-flex;align-items:center;gap:6px';
    it.innerHTML = '<span style="width:12px;height:12px;border-radius:3px;background:'
      + s.cor + ';display:inline-block"></span>' + s.rotulo;
    leg.appendChild(it);
  });

  var uni = Array.from(new Set(DADOS_ORC.map(function(c){ return c.unidade; })));
  var datasets = seriesOrc(DADOS_ORC, uni);

  var maximo = 0;
  datasets.forEach(function(d){
    d.data.forEach(function(v){ if(v > maximo) maximo = v; });
  });
  if(!maximo) maximo = TETO_ORC;

  /* Escala FIXA: a altura decorre do VALOR, não do espaço disponível.
     Um limite de 20.000 px evita estourar o tamanho máximo de canvas dos
     navegadores quando o orçamento for muito alto; nesse caso a escala é
     recalculada e informada ao usuário. */
  var interno = document.getElementById('sigoOrcInterno');
  var area = document.getElementById('sigoOrcArea');
  var alturaIdeal = maximo * PX_POR_REAL_ORC + 90;
  var altura = Math.min(20000, Math.max(420, alturaIdeal));
  var largura = Math.max((area.clientWidth || 800) - 8, uni.length * 96);
  interno.style.height = altura + 'px';
  interno.style.width = largura + 'px';

  var reaisPorPx = maximo / Math.max(1, altura - 90);
  document.getElementById('sigoOrcEscala').textContent =
    'Escala fixa: 1 pixel = ' + fmtBRL(Math.round(reaisPorPx))
    + '. Role na horizontal e na vertical para percorrer todas as barras. '
    + 'O gráfico abre na base do eixo.';

  destroy('chOrcExpandido');
  charts.chOrcExpandido = new Chart(document.getElementById('chOrcExpandido'), {
    type: 'bar',
    data: { labels: uni, datasets: datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: {
          label: function(c){ return c.dataset.label + ': ' + fmtBRL(c.raw); }
        }}
      },
      scales: {
        y: { beginAtZero: true, max: maximo, ticks: { callback: money } },
        x: { ticks: { autoSkip: false, maxRotation: 60, minRotation: 0 } }
      }
    }
  });

  /* Abre na BASE do eixo: é onde estão os rótulos das unidades e as barras
     menores. Rolar para cima mostra até onde vai a barra mais alta. */
  requestAnimationFrame(function(){ area.scrollTop = area.scrollHeight; });
}

function fecharOrcExpandido(){
  var jan = document.getElementById('sigoOrcExpandido');
  if(jan) jan.style.display = 'none';
  destroy('chOrcExpandido');
}
"""


# ---------------------------------------------------------------------------
# 4. "Valor no exercício por unidade" (chUnidade) — legenda clicável
#    Clicar no nome de uma secretaria na legenda aplica o filtro
#    Unidade/Órgão àquela secretaria. Clicar de novo no mesmo nome limpa.
# ---------------------------------------------------------------------------
_UNI_ANTIGO = "  donut('chUnidade',agg(data,'unidade','valor_total_exerc'),fmtBRL);"
_UNI_NOVO = "  donutUnidadeFiltravel(data);"

_FUNCAO_UNI = r"""
/* === Valor no exercício por unidade: legenda aplica o filtro ==============
   O comportamento padrão do Chart.js ao clicar na legenda é apenas ocultar a
   fatia. Aqui isso é substituído: o clique passa o nome da secretaria para o
   filtro Unidade/Órgão, o mesmo que o seletor da barra superior alimenta.
   Clicar novamente na secretaria já filtrada limpa o filtro. */
function aplicarFiltroUnidade(nome){
  var atual = state.unidade || '';
  var novo  = (atual === nome) ? '' : nome;   /* clicar de novo desmarca */

  state.unidade = novo;

  /* Mantém o seletor da barra superior em sincronia. Se o valor não existir
     entre as opções (lista ainda não montada), não força nada. */
  var sel = document.getElementById('fUnidade');
  if(sel){
    var existe = Array.prototype.some.call(sel.options, function(o){
      return o.value === novo;
    });
    if(existe || novo === '') sel.value = novo;
  }
  renderAll();
}

function donutUnidadeFiltravel(data){
  var id = 'chUnidade';
  destroy(id);

  var totais = agg(data, 'unidade', 'valor_total_exerc');
  var pares  = Object.entries(totais).sort(function(a,b){ return b[1]-a[1]; });

  /* Rótulo exibido é encurtado; o nome completo fica guardado à parte para
     que o filtro receba exatamente o valor usado nos dados. */
  var nomes   = pares.map(function(x){ return x[0]; });
  var rotulos = nomes.map(function(n){ return n.length>26 ? n.slice(0,26)+'…' : n; });

  var cv = document.getElementById(id);
  if(!cv) return;

  charts[id] = new Chart(cv, {
    type: 'doughnut',
    data: {
      labels: rotulos,
      datasets: [{
        data: pares.map(function(x){ return x[1]; }),
        backgroundColor: PAL,
        borderWidth: 2,
        borderColor: '#fff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          onClick: function(evt, item){
            var nome = nomes[item.index];
            if(nome) aplicarFiltroUnidade(nome);
          },
          onHover: function(evt){
            if(evt.native && evt.native.target) evt.native.target.style.cursor = 'pointer';
          },
          onLeave: function(evt){
            if(evt.native && evt.native.target) evt.native.target.style.cursor = 'default';
          },
          labels: {
            /* Marca visualmente a secretaria que está filtrada.
               O gerador de rótulos usado precisa ser o DA ROSCA: o gerador
               global produz um item por conjunto de dados, o que num gráfico
               de rosca resultaria numa legenda com um único item. */
            generateLabels: function(chart){
              var gen = (Chart.overrides
                         && Chart.overrides.doughnut
                         && Chart.overrides.doughnut.plugins
                         && Chart.overrides.doughnut.plugins.legend
                         && Chart.overrides.doughnut.plugins.legend.labels
                         && Chart.overrides.doughnut.plugins.legend.labels.generateLabels)
                        || Chart.defaults.plugins.legend.labels.generateLabels;
              var base = gen(chart);
              base.forEach(function(l, i){
                if(state.unidade && nomes[i] === state.unidade){
                  l.text = '● ' + l.text;
                  l.fontColor = '#1B4B7A';
                }
              });
              return base;
            }
          }
        },
        tooltip: {
          callbacks: {
            title: function(c){ return nomes[c[0].dataIndex]; },
            label: function(c){
              var sufixo = (state.unidade === nomes[c.dataIndex])
                ? ' (filtrada — clique na legenda para limpar)'
                : ' (clique na legenda para filtrar)';
              return fmtBRL(c.raw) + sufixo;
            }
          }
        }
      }
    }
  });
}
"""


# ---------------------------------------------------------------------------
# 5. "Aditivos por contrato" (chAditivos) — dois defeitos corrigidos
#
#    (a) O gráfico usava a função genérica de barras, limitada a 15 categorias.
#        Com mais de 15 contratos aditivados, os excedentes sumiam sem aviso —
#        e o KPI "Com aditivos" continuava contando todos, o que fazia painel e
#        indicador se contradizerem.
#    (b) A chave de cada barra era o NOME DA CONTRATADA. Dois contratos da
#        mesma empresa colidiam na mesma chave e um deles era descartado.
#        A chave passa a ser ficha + contratada, única por contrato.
#
#    Passa a exibir todos, com rolagem vertical dentro do próprio cartão.
# ---------------------------------------------------------------------------
_ADIT_ANTIGO = "    hbar('chAditivos',Object.fromEntries(comAdit.map(c=>[c.contratada||c.ficha,num(c.qtde_aditivos)])),null,'#6A5ACD');"
_ADIT_NOVO = "    hbarAditivosTodos('chAditivos', comAdit);"

_FUNCAO_ADIT = r"""
/* === Aditivos por contrato: todos os contratos, com rolagem =============== */
function hbarAditivosTodos(id, contratos){
  destroy(id);
  var cv = document.getElementById(id);
  if(!cv) return;

  /* Uma entrada por CONTRATO (não por fornecedor): dois contratos da mesma
     empresa precisam aparecer como barras distintas. */
  var itens = contratos.map(function(c){
    var ficha = c.ficha ? String(c.ficha).split(' ')[0] : '';
    var nome  = c.contratada || c.ficha || 'Não informado';
    return { rotulo: (ficha ? ficha + ' · ' : '') + nome,
             valor: num(c.qtde_aditivos) };
  }).sort(function(a,b){ return b.valor - a.valor; });

  var ref = prepararFaixa(cv, 'rolagem-adit');
  if(!ref) return;
  var caixa = ref.caixa, faixa = ref.faixa;
  caixa.style.overflowY = 'auto';
  caixa.style.overflowX = 'hidden';
  caixa.style.paddingRight = '4px';
  var alturaLinha = 26;
  var minima = caixa.clientHeight || 250;
  faixa.style.height = Math.max(minima, itens.length * alturaLinha + 24) + 'px';

  var curto = function(t){ return t.length > 40 ? t.slice(0,40) + '…' : t; };

  charts[id] = new Chart(cv, {
    type: 'bar',
    data: {
      labels: itens.map(function(x){ return curto(x.rotulo); }),
      datasets: [{ data: itens.map(function(x){ return x.valor; }),
                   backgroundColor: '#6A5ACD', borderRadius: 4 }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: {
          title: function(c){ return itens[c[0].dataIndex].rotulo; },
          label: function(c){ return c.raw + ' aditivo(s)'; }
        }}
      },
      scales: {
        x: { ticks: { precision: 0 } },
        y: { ticks: { autoSkip: false, font: { size: 11 } } }
      }
    }
  });
}
"""


# ---------------------------------------------------------------------------
# 6. "Top 20 fornecedores por valor no exercício" (chForn)
#    O título anuncia 20, mas o gráfico usava a função genérica de barras,
#    limitada a 15 categorias — cinco fornecedores do recorte prometido
#    ficavam de fora. Passa a exibir os 20, com rolagem vertical no cartão.
# ---------------------------------------------------------------------------
_FORN_ANTIGO = "  hbar('chForn',Object.fromEntries(Object.entries(agg(data,'contratada','valor_total_exerc')).sort((a,b)=>b[1]-a[1]).slice(0,20)),fmtBRL,'#1B4B7A');"
_FORN_NOVO = "  hbarFornTop20('chForn', data);"

_FUNCAO_FORN = r"""
/* === Top 20 fornecedores: exibe os 20 anunciados no título =============== */
function hbarFornTop20(id, data){
  destroy(id);
  var cv = document.getElementById(id);
  if(!cv) return;

  var itens = Object.entries(agg(data, 'contratada', 'valor_total_exerc'))
    .sort(function(a,b){ return b[1]-a[1]; })
    .slice(0, 20);

  var ref = prepararFaixa(cv, 'rolagem-forn');
  if(!ref) return;
  var caixa = ref.caixa, faixa = ref.faixa;
  caixa.style.overflowY = 'auto';
  caixa.style.overflowX = 'hidden';
  caixa.style.paddingRight = '4px';

  var alturaLinha = 26;
  var minima = caixa.clientHeight || 320;
  faixa.style.height = Math.max(minima, itens.length * alturaLinha + 24) + 'px';

  var curto = function(t){ return t.length > 40 ? t.slice(0,40) + '…' : t; };

  charts[id] = new Chart(cv, {
    type: 'bar',
    data: {
      labels: itens.map(function(x){ return curto(x[0]); }),
      datasets: [{ data: itens.map(function(x){ return x[1]; }),
                   backgroundColor: '#1B4B7A', borderRadius: 4 }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: {
          title: function(c){ return itens[c[0].dataIndex][0]; },
          label: function(c){ return fmtBRL(c.raw); }
        }}
      },
      scales: {
        x: { ticks: { callback: money } },
        y: { ticks: { autoSkip: false, font: { size: 11 } } }
      }
    }
  });
}
"""


# ---------------------------------------------------------------------------
# 7. Relatórios — identificação da secretaria e diferenciação dos duplicados
#
#    Diagnóstico que motivou o ajuste:
#
#    (a) Relatórios 02 e 03 agrupam por "elemento de despesa" e "fonte de
#        recurso". Esses campos vêm em branco nas planilhas; a função de
#        agrupamento então lança todos os contratos em um único grupo
#        ("Não informado"), e o relatório degenera em uma lista corrida de
#        todos os contratos — a mesma do relatório 07. Não era duplicidade de
#        código: era o agrupamento colapsando por falta de dado.
#
#    (b) Relatórios 04 e 11 aplicavam o MESMO critério de seleção (vencido ou
#        vencendo em 90 dias) e a mesma ordenação, diferindo apenas nas
#        colunas. Ainda que as finalidades sejam distintas — acompanhamento de
#        prazo e planejamento de licitação —, o conteúdo era o mesmo conjunto.
#
#    (c) Em todos eles a secretaria aparecia apenas como sigla, em coluna
#        estreita rotulada "Unid.", sem agrupamento nem subtotal — o contrato
#        ficava solto, difícil de atribuir e de analisar.
#
#    Correções: coluna "Secretaria" destacada em todos os relatórios de
#    contrato; resumo e subtotais por secretaria; agrupamento por secretaria
#    como alternativa quando o campo de agrupamento está vazio; e horizonte de
#    planejamento próprio para o relatório 11.
# ---------------------------------------------------------------------------
_SCRIPT_RELATORIOS = r"""
<script>
/* === Relatórios: secretaria visível e diferenciação dos duplicados ======== */
(function(){
  if(typeof RELATORIOS === 'undefined' || typeof imprimir !== 'function') return;

  var HORIZONTE_LICITACAO = 180;   /* dias — prazo de planejamento de licitação */

  /* ---------- utilitários ---------- */
  function secretaria(c){ return c.unidade || c.org || 'Não informado'; }

  function porSecretaria(dados){
    var m = {};
    dados.forEach(function(c){
      var u = secretaria(c);
      (m[u] = m[u] || []).push(c);
    });
    return Object.entries(m).sort(function(a, b){
      return sum(b[1], 'valor_total_exerc') - sum(a[1], 'valor_total_exerc');
    });
  }

  /* Faixa com a contagem por secretaria, no topo do relatório. Responde de
     imediato "quais secretarias estão nesta lista e com quantos contratos". */
  function resumoSecretarias(dados, rotulo){
    var gs = porSecretaria(dados);
    if(!gs.length) return '';
    var itens = gs.map(function(g){
      return '<span style="display:inline-block;margin:0 14px 4px 0">'
           + '<b style="color:#1B4B7A">' + g[0] + '</b> — ' + g[1].length
           + ' contrato(s) · ' + fmtBRLc(sum(g[1], 'valor_total_exerc')) + '</span>';
    }).join('');
    return '<div style="margin:10px 0 12px;padding:9px 11px;background:#F2F6FA;'
         + 'border-left:3px solid #1B4B7A;font-size:11px;color:#41566b">'
         + '<b>' + (rotulo || 'Distribuição por secretaria') + ':</b><br>' + itens + '</div>';
  }

  var TAGSEC = TD + ';font-weight:700;color:#1B4B7A;white-space:nowrap';

  /* Tabelas agrupadas por secretaria, com subtotal em cada grupo. */
  function tabelasPorSecretaria(dados, colunas, estilos, linhaFn, colsSoma){
    var gs = porSecretaria(dados);
    if(!gs.length) return tbl(colunas, []);
    var html = '';
    gs.forEach(function(g){
      var u = g[0], cs = g[1];
      html += '<div style="font-size:12.5px;font-weight:800;color:#1B4B7A;'
           +  'margin:14px 0 6px;padding-bottom:3px;border-bottom:2px solid #D5DFE9">'
           +  'SECRETARIA: ' + u + ' — ' + cs.length + ' contrato(s) · '
           +  fmtBRLc(sum(cs, 'valor_total_exerc')) + '</div>';
      var linhas = cs.map(linhaFn);
      if(colsSoma){
        var sub = colunas.map(function(_, i){
          if(i === 0) return '<b>Subtotal ' + u + '</b>';
          var campo = colsSoma[i];
          return campo ? '<b>' + fmtBRLc(sum(cs, campo)) + '</b>' : '';
        });
        linhas.push(tRow(sub, estilos));
      }
      html += tbl(colunas, linhas);
    });
    return html;
  }

  /* ---------- 02 e 03: agrupamento com alternativa ---------- */
  function relAgrupado(dados, campo, titulo, rotulo){
    var vazios = dados.filter(function(c){ return val(c[campo]) == null; }).length;
    var todosVazios = dados.length > 0 && vazios === dados.length;

    /* Campo vazio em TODO o recorte: agrupar por ele produziria um único grupo
       "Não informado" com todos os contratos — uma lista corrida idêntica à de
       outros relatórios. Em vez disso, emite-se o quadro de pendência de
       preenchimento, que é o que efetivamente falta resolver. */
    if(todosVazios){
      var gs = porSecretaria(dados);
      var linhasP = gs.map(function(g){
        return tRow([g[0], g[1].length, g[1].length, '0%',
                     '<b style="color:#B24545">Campo não preenchido</b>'],
                    [TAGSEC, TDn, TDn, TDn, TD]);
      });
      linhasP.push(tRow(['<b>TOTAL</b>', '<b>' + dados.length + '</b>',
                         '<b>' + dados.length + '</b>', '<b>0%</b>', ''],
                        [TD, TDn, TDn, TDn, TD]));
      imprimir(cabecalhoRel(titulo, filtrosTexto())
        + '<div style="margin:10px 0 12px;padding:11px 13px;background:#FBF3E6;'
        + 'border-left:3px solid #C98A2B;font-size:11.5px;color:#6b5a34">'
        + '<b>Não foi possível emitir este relatório: o campo "' + rotulo
        + '" não está preenchido em nenhum contrato do recorte.</b><br>'
        + 'Agrupar por um campo vazio reuniria todos os contratos em um único '
        + 'grupo, produzindo uma lista idêntica à do Relatório 07 — sem utilidade '
        + 'analítica. O quadro abaixo indica, por secretaria, o que falta preencher '
        + 'para que este relatório passe a funcionar.</div>'
        + tbl(['Secretaria', 'Contratos', 'Sem o campo "' + rotulo + '"',
               'Preenchido', 'Situação'], linhasP));
      return;
    }

    var aviso = '';
    if(vazios){
      aviso = '<div style="margin:10px 0 4px;padding:9px 11px;background:#FBF3E6;'
            + 'border-left:3px solid #C98A2B;font-size:11px;color:#6b5a34">'
            + vazios + ' de ' + dados.length + ' contrato(s) estão sem o campo "'
            + rotulo + '" e aparecem agrupados como "Não informado".</div>';
    }

    var colunas = ['Ficha', 'Contratada', 'Secretaria', 'Vigência',
                   'Previsto exerc.', 'Empenhado', '% Emp.', 'Situação'];
    var estilos = [TD, TD, TAGSEC, TD, TDn, TDn, TDn, TD];
    var linha = function(c){
      return tRow([c.ficha, c.contratada, secretaria(c),
                   fmtDateP(c.inicio_vig) + ' a ' + fmtDateP(c.termino_vig),
                   fmtBRLc(c.valor_total_exerc), fmtBRLc(c.valor_empenhado),
                   fmtPct(c.pct_empenhado), val(c.situacao) || '—'], estilos);
    };

    var corpo = '';
    {
      var gsCampo = {};
      dados.forEach(function(c){ var g = grp(c[campo]); (gsCampo[g] = gsCampo[g] || []).push(c); });
      Object.entries(gsCampo).sort(function(a, b){
        return sum(b[1], 'valor_total_exerc') - sum(a[1], 'valor_total_exerc');
      }).forEach(function(par){
        var g = par[0], cs = par[1];
        corpo += '<div style="font-size:12.5px;font-weight:800;color:#1B4B7A;margin:14px 0 6px">'
              +  rotulo + ': ' + g + ' — ' + cs.length + ' contrato(s) · '
              +  fmtBRLc(sum(cs, 'valor_total_exerc')) + '</div>';
        corpo += resumoSecretarias(cs, 'Secretarias neste grupo');
        corpo += tbl(colunas, cs.sort(function(a, b){
          return num(b.valor_total_exerc) - num(a.valor_total_exerc);
        }).map(linha));
      });
    }
    imprimir(cabecalhoRel(titulo, filtrosTexto()) + aviso + corpo);
  }

  /* ---------- 04: acompanhamento de prazo ---------- */
  function relVencimento(dados){
    var sel = dados.filter(function(c){ return isSim(c.vencido) || isSim(c.vence_90); })
                   .sort(function(a, b){ return num(a.dias_vencer) - num(b.dias_vencer); });
    var estilos = [TD, TD, TAGSEC, TD, TDn, TD, TDn];
    var linhas = sel.map(function(c){
      return tRow([c.ficha, c.contratada, secretaria(c), fmtDateP(c.termino_vig),
                   num(c.dias_vencer) + ' d',
                   isSim(c.vencido) ? 'VENCIDO' : 'Vence em 90d',
                   fmtBRLc(c.saldo_empenhar)], estilos);
    });
    imprimir(cabecalhoRel('Relatório de Contratos Próximos do Vencimento',
      filtrosTexto() + '<br><span style="font-size:11px">Critério: vigência vencida ou '
      + 'expirando em até 90 dias. Ordenado pela urgência, do mais crítico ao menos.</span>')
      + resumoSecretarias(sel)
      + tbl(['Ficha', 'Contratada', 'Secretaria', 'Término', 'Dias', 'Situação',
             'Saldo a empenhar'], linhas));
  }

  /* ---------- 07: execução por contrato, com subtotal por secretaria ------- */
  function relExecucao(dados){
    var colunas = ['Ficha', 'Contratada', 'Secretaria', 'Previsto', 'Empenhado',
                   'Liquidado', 'Pago', 'Saldo emp.', 'A suplementar', '% Emp.'];
    var estilos = [TD, TD, TAGSEC, TDn, TDn, TDn, TDn, TDn, TDn, TDn];
    var linha = function(c){
      return tRow([c.ficha, c.contratada, secretaria(c),
                   fmtBRLc(c.valor_total_exerc), fmtBRLc(c.valor_empenhado),
                   fmtBRLc(c.valor_liquidado), fmtBRLc(c.valor_pago),
                   fmtBRLc(c.saldo_empenhar), fmtBRLc(c.valor_suplementar),
                   fmtPct(c.pct_empenhado)], estilos);
    };
    var corpo = tabelasPorSecretaria(dados, colunas, estilos, linha,
      [null, null, null, 'valor_total_exerc', 'valor_empenhado', 'valor_liquidado',
       'valor_pago', 'saldo_empenhar', 'valor_suplementar', null]);

    var geral = tRow(['<b>TOTAL GERAL</b>', '<b>' + dados.length + ' contratos</b>', '',
      '<b>' + fmtBRLc(sum(dados, 'valor_total_exerc')) + '</b>',
      '<b>' + fmtBRLc(sum(dados, 'valor_empenhado')) + '</b>',
      '<b>' + fmtBRLc(sum(dados, 'valor_liquidado')) + '</b>',
      '<b>' + fmtBRLc(sum(dados, 'valor_pago')) + '</b>',
      '<b>' + fmtBRLc(sum(dados, 'saldo_empenhar')) + '</b>',
      '<b>' + fmtBRLc(sum(dados, 'valor_suplementar')) + '</b>', ''], estilos);

    imprimir(cabecalhoRel('Relatório de Execução Orçamentária por Contrato',
      filtrosTexto() + '<br><span style="font-size:11px">Contratos agrupados por '
      + 'secretaria, com subtotal em cada uma e total geral ao final.</span>')
      + resumoSecretarias(dados)
      + corpo
      + '<div style="margin-top:12px">' + tbl(colunas, [geral]) + '</div>');
  }

  /* ---------- 11: planejamento de licitação ---------- */
  function relLicitacao(dados){
    /* Horizonte mais largo que o do relatório 04: instaurar e concluir um novo
       processo licitatório leva meses, de modo que o planejamento precisa
       enxergar além do alerta de 90 dias. Contratos cuja continuidade já está
       resolvida por nova vigência registrada são excluídos. */
    var sel = dados.filter(function(c){
      var d = num(c.dias_vencer);
      var dentro = isSim(c.vencido) || (val(c.dias_vencer) != null && d <= HORIZONTE_LICITACAO);
      var jaProrrogado = val(c.nova_vigencia) != null;
      return dentro && !jaProrrogado;
    }).sort(function(a, b){ return num(a.dias_vencer) - num(b.dias_vencer); });

    var prorrogados = dados.filter(function(c){
      var d = num(c.dias_vencer);
      return (isSim(c.vencido) || (val(c.dias_vencer) != null && d <= HORIZONTE_LICITACAO))
             && val(c.nova_vigencia) != null;
    }).length;

    var estilos = [TD, TD, TAGSEC, TD, TD, TD, TDn, TDn];
    var linhas = sel.map(function(c){
      var d = num(c.dias_vencer);
      var prazo = isSim(c.vencido) ? 'Vencido há ' + Math.abs(d) + ' d'
                                   : 'Vence em ' + d + ' d';
      return tRow([c.ficha, c.contratada, secretaria(c),
                   val(c.objeto_resumido) || String(c.objeto || '').slice(0, 70),
                   val(c.modalidade) || '—', prazo,
                   fmtDateP(c.termino_vig), fmtBRLc(c.valor_total_exerc)], estilos);
    });

    var nota = 'Critério: vigência vencida ou expirando em até ' + HORIZONTE_LICITACAO
             + ' dias — horizonte de planejamento da contratação, mais largo que o '
             + 'alerta de 90 dias do Relatório 04, por considerar o tempo de '
             + 'instrução do processo. Contratos com nova vigência já registrada '
             + 'foram excluídos'
             + (prorrogados ? ' (' + prorrogados + ' neste recorte)' : '')
             + '. Avaliar caso a caso a possibilidade legal de prorrogação.';

    imprimir(cabecalhoRel('Contratos que Exigem Novo Processo Licitatório',
      filtrosTexto() + '<br><span style="font-size:11px">' + nota + '</span>')
      + resumoSecretarias(sel, 'Demanda de licitação por secretaria')
      + tbl(['Ficha', 'Contratada', 'Secretaria', 'Objeto', 'Modalidade atual',
             'Prazo', 'Término', 'Valor no exercício'], linhas));
  }

  /* ---------- 05, 06 e 10: mesma nomenclatura de secretaria ---------- */
  /* Mantêm critério e colunas próprias; apenas a coluna da unidade passa a se
     chamar "Secretaria" e a receber o mesmo destaque dos demais relatórios,
     para que a atribuição do contrato seja imediata em qualquer relatório. */
  function relSaldoCritico(dados){
    var est = [TD, TD, TAGSEC, TDn, TDn, TDn, TDn];
    var sel = dados.filter(function(c){ return isSim(c.saldo_menor_20); })
                   .sort(function(a, b){ return num(b.pct_empenhado) - num(a.pct_empenhado); });
    imprimir(cabecalhoRel('Relatório de Contratos com Saldo Crítico (< 20%)', filtrosTexto())
      + resumoSecretarias(sel)
      + tbl(['Ficha', 'Contratada', 'Secretaria', 'Previsto', 'Empenhado', '% Emp.', 'Saldo'],
        sel.map(function(c){
          return tRow([c.ficha, c.contratada, secretaria(c), fmtBRLc(c.valor_total_exerc),
                       fmtBRLc(c.valor_empenhado), fmtPct(c.pct_empenhado),
                       fmtBRLc(c.saldo_empenhar)], est); })));
  }

  function relSaldoElevado(dados){
    var est = [TD, TD, TAGSEC, TDn, TDn, TDn, TDn];
    var sel = dados.filter(function(c){
        return num(c.valor_total_exerc) > 0 &&
               num(c.saldo_empenhar) / num(c.valor_total_exerc) > 0.5;
      }).sort(function(a, b){ return num(b.saldo_empenhar) - num(a.saldo_empenhar); });
    imprimir(cabecalhoRel('Relatório de Contratos com Saldo Elevado (> 50%)', filtrosTexto())
      + resumoSecretarias(sel)
      + tbl(['Ficha', 'Contratada', 'Secretaria', 'Previsto', 'Empenhado',
             'Saldo a empenhar', '% Saldo'],
        sel.map(function(c){
          return tRow([c.ficha, c.contratada, secretaria(c), fmtBRLc(c.valor_total_exerc),
                       fmtBRLc(c.valor_empenhado), fmtBRLc(c.saldo_empenhar),
                       fmtPct(num(c.saldo_empenhar) / num(c.valor_total_exerc))], est); })));
  }

  function relAditivos(dados){
    var est = [TD, TD, TAGSEC, TDn, TDn, TDn, TDn, TD, TD];
    var sel = dados.filter(function(c){ return num(c.qtde_aditivos) > 0; })
                   .sort(function(a, b){ return num(b.qtde_aditivos) - num(a.qtde_aditivos); });
    var nota = sel.length ? '' : '<br><span style="font-size:11px">Nenhum aditivo '
             + 'registrado no recorte — o quadro será preenchido conforme o grupo de '
             + 'aditivos das fichas for alimentado.</span>';
    imprimir(cabecalhoRel('Relatório de Aditivos Contratuais', filtrosTexto() + nota)
      + (sel.length ? resumoSecretarias(sel) : '')
      + tbl(['Ficha', 'Contratada', 'Secretaria', 'Qtde', 'Acrescido', 'Suprimido',
             'Novo valor', 'Nova vigência', 'Justificativa'],
        sel.map(function(c){
          return tRow([c.ficha, c.contratada, secretaria(c), num(c.qtde_aditivos),
                       fmtBRLc(c.valor_acrescido), fmtBRLc(c.valor_suprimido),
                       fmtBRLc(c.novo_valor), fmtDateP(c.nova_vigencia),
                       val(c.ultima_justif) || '—'], est); })));
  }

  /* ---------- substituição ---------- */
  var novos = {
    r2:  { d: 'Agrupamento pelo elemento de despesa. Quando o campo não está '
              + 'preenchido, os contratos são organizados por secretaria.',
           run: function(d){ relAgrupado(d, 'elemento_despesa',
                  'Relatório por Elemento de Despesa', 'Elemento'); } },
    r3:  { d: 'Agrupamento por fonte de recurso. Quando o campo não está '
              + 'preenchido, os contratos são organizados por secretaria.',
           run: function(d){ relAgrupado(d, 'fonte_recurso',
                  'Relatório por Fonte de Recurso', 'Fonte'); } },
    r4:  { d: 'Vencidos e a vencer em até 90 dias, por urgência, com a '
              + 'secretaria de cada contrato e o saldo a empenhar.',
           run: relVencimento },
    r5:  { d: 'Saldo a empenhar abaixo de 20% do previsto, com a secretaria de '
              + 'cada contrato.',
           run: relSaldoCritico },
    r6:  { d: 'Saldo a empenhar acima de 50% do previsto, com a secretaria de '
              + 'cada contrato.',
           run: relSaldoElevado },
    r10: { d: 'Contratos com aditivos, por secretaria: quantidades, acréscimos, '
              + 'supressões e novas vigências.',
           run: relAditivos },
    r7:  { d: 'Quadro completo por contrato, agrupado por secretaria, com '
              + 'subtotal em cada uma e total geral.',
           run: relExecucao },
    r11: { t: 'Contratos que exigem novo processo licitatório',
           d: 'Horizonte de ' + HORIZONTE_LICITACAO + ' dias para planejar a '
              + 'contratação, por secretaria, excluídos os já prorrogados.',
           run: relLicitacao }
  };

  RELATORIOS.forEach(function(r){
    if(novos[r.id]) Object.assign(r, novos[r.id]);
  });
  if(typeof renderRelatorios === 'function') renderRelatorios();
})();
</script>
"""


def aplicar_ajustes(html: str) -> str:
    """Aplica todos os ajustes ao HTML já com os dados injetados."""
    html = _trocar(html, _BTN_ANTIGO, _BTN_NOVO, "rótulo do botão de atualização")
    html = _trocar(html, _INPUT_ANTIGO, _INPUT_NOVO, "campo de arquivo")
    html = _trocar(html, _CHAMADA_ANTIGA, _CHAMADA_NOVA, "chamada do gráfico chTipo")
    html = _trocar(html, _ORC_ANTIGO, _ORC_NOVO, "gráfico por unidade (orçamentária)")
    html = _trocar(html, _UNI_ANTIGO, _UNI_NOVO, "gráfico de valor por unidade")
    html = _trocar(html, _ADIT_ANTIGO, _ADIT_NOVO, "gráfico de aditivos por contrato")
    html = _trocar(html, _FORN_ANTIGO, _FORN_NOVO, "gráfico de top fornecedores")
    html = _trocar(html, "</body>",
                   _SCRIPT_UPLOAD + _SCRIPT_RELATORIOS + "</body>", "fim do documento")
    return html


def funcoes_graficos() -> str:
    """Trechos inseridos junto ao vetor de dados (mesmo bloco de script)."""
    return (_FUNCAO_BASE + _FUNCAO_TIPO + _FUNCAO_ORC
            + _FUNCAO_UNI + _FUNCAO_ADIT + _FUNCAO_FORN)
