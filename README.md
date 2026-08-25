# SIGO · Gestão de Contratos — v10

Painel institucional de gestão de contratos da SEMEC/PMPV, alimentado por
planilhas de controle das secretarias.

## O que mudou nesta versão

| | v1 | **v2 (esta)** |
|---|---|---|
| Origem dos dados | pasta local / Drive | **pacote .zip enviado pela usuária** |
| Integração com Google Drive | prevista | **abandonada** |
| Exercício | fixo em 2026 | **lido do pacote enviado** |
| Leitura da planilha | 21 colunas (tradução) | **aba "Base de Dados" nativa (65 col.)** |

---

## 1. Como enviar os dados

A alimentação é **manual**. A usuária envia **um único arquivo .zip** com esta
estrutura:

```
pacote.zip
  └── <Pasta extraída — nome livre>
        └── CONTRATOS_<AnoExercicio>              ← define o EXERCÍCIO do painel
              ├── SEMAD_Controle_Contratos_<Ano>.xlsx
              ├── SEMEC_Controle_Contratos_<Ano>.xlsx
              └── ...
```

**Regras de nomenclatura**

- Pasta das planilhas: `CONTRATOS_<AnoExercicio>` — ex.: `CONTRATOS_2027`
- Arquivo da planilha: `<Secretaria>_Controle_Contratos_<AnoReferente>.xlsx`
  — ex.: `SEMAD_Controle_Contratos_2027.xlsx`

A sigla antes do primeiro `_` vira o rótulo de **Unidade/Órgão** no painel.

**Verificação de ano.** O sistema lê o exercício da pasta `CONTRATOS_<ano>` e
confere o ano de cada arquivo. Se um arquivo divergir do exercício da pasta,
ele é carregado assim mesmo, mas o sistema registra um aviso identificando o
arquivo — para que a divergência seja conferida antes da publicação.

**Envio**

- Pela API: `POST /api/pacote` (campo `arquivo`, multipart), ou
- Colocando o `.zip` na pasta `pacotes/` e reiniciando o servidor (ele carrega
  automaticamente o pacote mais recente).

---

## 2. O exercício é definido pelo pacote

O ano exibido no painel — cabeçalho, KPIs, rodapé, gráficos de vencimento,
projeção mensal e cabeçalho dos relatórios impressos — passa a vir da pasta
`CONTRATOS_<ano>` do pacote enviado. Enviando um pacote `CONTRATOS_2027`, todo
o painel passa a operar em 2027, sem qualquer edição manual.

---

## 3. Leitura da planilha (mudança na tabela de dados)

A partir do leiaute 2027, a planilha das secretarias traz a aba
**"Base de Dados"** já no formato nativo do painel: cabeçalho na linha 3,
contratos a partir da linha 4, uma coluna por campo, na mesma ordem esperada.
O sistema passou a ler essa aba **diretamente**, o que elimina a tradução do
modelo anterior e habilita campos que antes chegavam vazios (fonte de recurso,
natureza e elemento de despesa, fiscal, gestor, modalidade, dotação,
liquidado, pago, aditivos, medições).

Também são carregadas as 6 colunas novas do leiaute 2027 (desdobramento do
valor pago por fonte: livre, vinculado, convênio, operação de crédito,
emendas, e a verificação "Pago vs. Fonte"). Elas ainda não são exibidas pelo
painel, mas já ficam disponíveis para os relatórios por fonte.

**Compatibilidade.** Planilhas no leiaute antigo (21 colunas, aba do ano,
cabeçalho na linha 7) continuam sendo lidas por um caminho alternativo — o
sistema detecta o leiaute automaticamente e informa qual usou no diagnóstico.

**Identidade dos contratos.** O painel identifica cada contrato por
`unidade + ficha`. Como a coluna "Ficha" vem quase sempre vazia na planilha, o
sistema gera `C01, C02, …` quando ela falta, preservando o valor quando existe.
Sem isso, contratos distintos colidiriam na mesma chave e sumiriam do painel.

---

## 4. O frontend continua intacto

`frontend/SIGO_Gestao_Contratos.html` é mantido **byte a byte** idêntico ao
original (MD5 `75af2f58bf5e0e3ace13127b1205a6e8`). O servidor monta a resposta
em memória, substituindo apenas:

1. o vetor de exemplo `let CONTRACTS = [...];` pelos dados reais; e
2. o ano de exercício (2026 no arquivo original) pelo ano do pacote.

Isso é verificado automaticamente: revertendo o ano no HTML servido,
obtém-se exatamente o arquivo original.

---

## 5. Estrutura

```
SIGO_Gestao_Contratos_v10/
├── backend/
│   ├── servidor.py        # FastAPI: injeção de dados + exercício; upload do pacote
│   ├── pacote.py          # .zip: extração, pasta CONTRATOS_<ano>, verificação de ano
│   ├── leitor.py          # leitura da aba "Base de Dados" (+ fallback leiaute antigo)
│   ├── adaptador_sigo.py  # monta o vetor CONTRACTS e recalcula alertas
│   └── config.py          # caminhos e ano-base do frontend
├── frontend/
│   └── SIGO_Gestao_Contratos.html   # INALTERADO
├── pacotes/
│   └── pacote_contratos_2027.zip    # pacote de exemplo (SEMAD 2027)
├── requirements.txt
└── README.md
```

---

## 6. Como executar

```bash
cd SIGO_Gestao_Contratos_v10
pip install -r requirements.txt
cd backend
uvicorn servidor:app --reload
```

Abra **http://127.0.0.1:8000/**

### Rotas

| Rota | Método | Função |
|---|---|---|
| `/` | GET | Painel com o pacote ativo |
| `/api/pacote` | POST | Envia um novo pacote .zip e recarrega o painel |
| `/api/diagnostico` | GET | Exercício, secretarias, leiaute detectado e avisos |
| `/api/contratos` | GET | Vetor CONTRACTS em JSON |
| `/api/saude` | GET | Estado do pacote ativo |

> **Internet no primeiro carregamento:** o painel busca os componentes de
> gráfico (Chart.js e SheetJS) em CDN, como no arquivo original.

---

## 7. Recálculo das planilhas

O sistema lê o **valor já calculado** das fórmulas. A planilha precisa ter sido
aberta e salva no Excel ou LibreOffice antes de entrar no pacote — caso
contrário, as colunas com fórmula chegam vazias.

## 8. Status

- [x] Alimentação manual por pacote .zip
- [x] Identificação do exercício pela pasta `CONTRATOS_<ano>`
- [x] Verificação do ano de cada arquivo, com aviso em caso de divergência
- [x] Ano do exercício aplicado a todo o frontend
- [x] Leitura da aba nativa "Base de Dados" (65 colunas + 6 novas)
- [x] Compatibilidade com o leiaute antigo (21 colunas)
- [x] Frontend preservado byte a byte
- [x] Envio do pacote pela interface
- [x] Recuperação de planilhas sem recálculo
- [x] Gráfico de tipos de objeto com todos os tipos
- [ ] Exibição das colunas "Pago por fonte" (aba de relatórios — próxima fase)

---

## 9. Novidades da v3

### 9.1 Envio do pacote pela própria interface

O botão **"Atualizar dados (.zip)"** na barra superior agora recebe o pacote
compactado: escolha o `.zip`, e o painel envia ao servidor, reprocessa todas as
planilhas e recarrega já no exercício do pacote. Ao final é exibido um resumo
com o número de contratos por secretaria, quais não foram carregadas e por quê.

O envio de `.xlsx` avulso continua funcionando como antes — o sistema decide
pelo tipo de arquivo escolhido.

### 9.2 Por que algumas secretarias não apareciam

A aba **"Base de Dados"** não é digitada: ela é inteiramente montada por
fórmulas que espelham a aba operacional do ano. No arquivo analisado são 1.323
células de fórmula contra 1 valor digitado.

Fórmula guarda dois conteúdos: a própria fórmula e o **último valor calculado**.
Quem lê o arquivo sem abrir o Excel enxerga apenas o valor calculado. Se a
planilha foi salva sem recalcular, esse valor não existe — e a aba inteira é
lida como vazia. A secretaria some do painel sem erro aparente.

**O que a v3 faz:** ao encontrar a "Base de Dados" vazia, o sistema procura os
dados na **aba operacional do ano**, onde a secretaria efetivamente digitou, e
recompõe os campos calculados (valor total no exercício, saldo a empenhar,
percentual empenhado). A secretaria passa a aparecer mesmo sem recálculo.

Essa leitura é **dirigida pelo cabeçalho**: cada coluna é reconhecida pelo
título, não pela posição. Isso corrigiu uma falha real — o leiaute 2027 inseriu
"Modalidade de Licitação" na coluna 7, deslocando todas as seguintes; uma
leitura por posição traria objeto, vigência e valores trocados.

**Diagnóstico.** `/api/diagnostico` e a mensagem exibida após o envio informam,
por arquivo: de qual aba os dados vieram, quantos contratos foram lidos e, se
nenhum, o motivo — planilha sem recálculo, aba sem preenchimento, arquivo fora
do padrão de nome ou divergência de ano.

### 9.3 Gráfico "Contratos por tipo de objeto"

O gráfico usava a função genérica de barras, com dois limites: exibia no
**máximo 15 categorias** e truncava os rótulos em **28 caracteres**. Como o
catálogo tem **16 tipos**, o último ficava de fora; e os dois tipos mais comuns
— "Contrato de Prestação de Serviços Contínuos" e "Contrato de Prestação de
Serviços Técnicos Especializados" — apareciam com o mesmo rótulo truncado,
indistinguíveis.

Agora o gráfico exibe **todos os tipos presentes**, com rolagem vertical dentro
do próprio cartão. O tamanho do cartão e o restante da página não mudam. Os
rótulos foram ampliados e o nome completo aparece ao passar o mouse.

Os demais gráficos continuam usando a função original, sem alteração.

### 9.4 Modo offline (opcional)

A pasta `frontend/libs/` traz as bibliotecas de gráfico usadas pelo painel. Se
ela existir, o servidor as entrega localmente em vez de buscá-las na internet —
útil se a rede da Prefeitura bloquear o acesso ao CDN. Basta apagar a pasta para
voltar ao comportamento original.

---

## 10. Correções da v4

### 10.1 Erro 500 ao enviar o pacote pela interface (Windows)

**Sintoma.** O envio gravava o `.zip` na pasta `pacotes/`, mas o painel
exibia *"Falha no envio: Unexpected token 'I', "Internal S"... is not valid
JSON"*. Fechar e reabrir o servidor com o `.zip` na pasta funcionava.

**Causa.** A leitura das planilhas usa `openpyxl` em modo somente-leitura —
otimização introduzida na v3 — e esse modo **mantém o arquivo aberto** até
que seja explicitamente fechado. O código não o fechava. Na carga seguinte,
o sistema tentava apagar a pasta de trabalho para extrair o novo pacote e
esbarrava nos arquivos ainda abertos.

No Linux, apagar um arquivo aberto é permitido — por isso os testes passavam.
No Windows, não: o sistema operacional recusa a exclusão, a exceção subia sem
tratamento, o servidor devolvia a página de erro padrão (texto puro) e o
painel, que esperava JSON, exibia o erro de leitura. Reiniciar o servidor
liberava os arquivos, o que explica o comportamento observado.

**Correções.**
1. As planilhas passam a ser fechadas após a leitura (`try/finally`).
2. Cada carga extrai o pacote em uma **pasta nova**, em vez de apagar e
   recriar sempre a mesma. As pastas antigas são removidas depois, e uma
   falha nessa limpeza não interrompe a carga.
3. O endpoint devolve **sempre JSON**, inclusive em erro, com mensagem
   legível — incluindo um texto específico para arquivo em uso.
4. O painel deixa de presumir que a resposta é JSON: lê o conteúdo como
   texto e só então interpreta, exibindo o código HTTP e o trecho recebido
   quando não for JSON.

### 10.2 Planilhas que continuavam sem ser processadas

A leitura passou a ser bem mais tolerante:

- **Todas as abas são testadas.** Antes: aba "Base de Dados", depois a aba do
  ano. Agora, se nenhuma delas trouxer contratos, o sistema tenta as demais
  abas e adota a que trouxer mais.
- **Cabeçalho flexível.** Antes exigia "Contratada" **e** "Objeto do
  Contrato". Agora basta "Contratada" com qualquer uma entre objeto,
  processo, vigência, contrato/ano ou CPF/CNPJ.
- **Nome fora do padrão não descarta mais o arquivo.** O sistema extrai a
  sigla e o ano do que houver no nome e carrega assim mesmo, com aviso.
- **Busca recursiva.** Planilhas em subpastas passam a ser encontradas.
- **Pacote sem `CONTRATOS_<ano>`** deixa de ser recusado: o exercício é
  deduzido pelo nome dos arquivos, com aviso.
- **Arquivos .xls** são identificados com orientação para conversão.

**Auditoria completa.** Todo arquivo do pacote entra no relatório, com
situação e motivo. Para os que não trouxeram contratos, o relatório mostra as
abas do arquivo, as abas testadas com o número de contratos lidos em cada uma
e o caminho dentro do pacote. É o que permite distinguir "planilha em branco"
de "aba ou cabeçalho fora do padrão".

### 10.3 Verificação prévia

`POST /api/verificar` processa um pacote e devolve o relatório **sem**
substituir os dados em uso.

### 10.4 Verificação automática do sistema

`testes/verificar_sistema.py` confere integridade do HTML, âncoras dos
ajustes, sintaxe do JavaScript injetado, fechamento das planilhas e duas
cargas consecutivas. Foi criado a partir de uma falha real desta versão: um
escape interpretado duas vezes quebrava o script no navegador. O teste
reproduz e detecta esse caso.

### 10.5 Documentação

`GUIA_DE_USO.md` traz a lista de conferência para montar o pacote, como ler o
relatório, uma tabela de mensagens com a solução de cada uma e perguntas
frequentes.

---

## 11. Novidades da v5

### 11.1 Aviso do openpyxl — esclarecido e silenciado

*"Data Validation extension is not supported and will be removed"*

As planilhas usam listas suspensas cujas opções ficam na aba "Listas". O Excel
grava esse tipo de validação num formato de **extensão** que a biblioteca de
leitura (openpyxl) não interpreta, e por isso ela emite o aviso.

O "will be removed" refere-se à cópia mantida em memória: se o arquivo fosse
**salvo** por essa biblioteca, as listas suspensas se perderiam. Este sistema
apenas **lê** as planilhas — foi verificado que não há nenhuma operação de
gravação de `.xlsx` no código. O arquivo da secretaria não é alterado e nenhum
dado é afetado. A observação da usuária estava correta: não afeta o sistema.

O aviso foi silenciado (com a explicação registrada no código, em `leitor.py`)
para manter o terminal legível.

### 11.2 Relatório de atualização: símbolos e histórico

- **✔ verde** e **✘ vermelho** distinguem à primeira vista as secretarias
  carregadas das que ficaram sem contratos, agora em formato de tabela com
  contagem e situação de cada uma.
- **O relatório fica gravado.** Cada carga gera dois arquivos em `relatorios/`:
  `.json` (consumido pelo painel) e `.txt` (legível, para imprimir ou anexar a
  um processo). São mantidas as 60 atualizações mais recentes.
- **Botão "Relatório de dados"**, ao lado do de atualização, reabre o último
  relatório e permite navegar pelas cargas anteriores.
- Como as planilhas sem contratos refletem o preenchimento de cada secretaria
  — e não uma falha do sistema —, o relatório traz essa observação de forma
  explícita, para não induzir a erro quem o consultar depois.

Rotas: `GET /api/relatorios` (índice), `GET /api/relatorios/{id}` (completo,
aceita `ultimo`), `GET /api/relatorios/{id}/texto` (versão em texto).

### 11.3 Execução Orçamentária: rolagem horizontal

No gráfico "Previsto × Empenhado × Pago por unidade", cada secretaria passa a
ocupar uma faixa de largura fixa, e o gráfico desliza horizontalmente dentro do
cartão. Com 21 secretarias as barras deixam de ser comprimidas; o cartão mantém
o tamanho original e o restante da página não muda. Quando as unidades cabem no
espaço disponível, nada rola — o comportamento é idêntico ao anterior.

### 11.4 Verificação automática ampliada

`testes/verificar_sistema.py` passou a conferir também a âncora do gráfico por
unidade e a gravação/releitura dos relatórios.

---

## 12. Novidades da v6

### 12.1 Legenda do gráfico por unidade

A legenda desenhada pelo Chart.js fica **dentro do canvas** — e o canvas está
dentro da faixa que rola. Com a rolagem introduzida na v5, ela saía de vista.

A legenda interna foi desativada e substituída por uma legenda em HTML montada
no cabeçalho do cartão, **fora da área que rola**. As cores e os rótulos vêm da
mesma definição usada para desenhar as barras, de modo que não há risco de
divergirem. Verificado: após rolar até o fim, a legenda permanece visível.

### 12.2 Validação da aba Execução Orçamentária

Conferido item a item, com dados de teste (20 secretarias, 60 contratos) e com
a planilha real da SEMAD:

| Item | Resultado |
|---|---|
| KPIs (previsto, empenhado, liquidado, pago, saldo) | conferem com o cálculo do backend |
| Soma das barras do gráfico por unidade | idêntica aos KPIs |
| Unidades no gráfico | 20 — todas as que têm dados |
| Gráficos de fonte, natureza e projeção mensal | desenhados |
| Tabela "Execução por contrato" | 60 linhas, 10 colunas |
| Filtro por unidade | recalcula KPIs, gráfico e tabela |
| Ordenação por cabeçalho | funcional |
| Erros de console | nenhum |

### 12.3 Alertas de leitura dos indicadores

A validação com a planilha real revelou dois pontos que **não são falha do
sistema**, mas podem induzir a conclusão errada. O sistema passa a sinalizá-los
no relatório, sem alterar nenhum valor:

**"A suplementar" exibindo o valor total.** Na planilha, *Valor a Suplementar*
nasce de `Saldo a Empenhar − Saldo Orçamentário da Unidade`. Como a coluna
*Saldo Orçamentário da Unidade* está zerada, a suplementação repete o saldo a
empenhar — na SEMAD, R$ 80.025.066,00, que se leria como necessidade de
suplementação desse porte. Preenchida a coluna do saldo orçamentário, o
indicador passa a fazer sentido.

**Execução zerada.** Quando nenhum contrato tem valor empenhado, os
indicadores de execução ficam em zero. É o esperado num exercício ainda não
iniciado, e o relatório passa a dizê-lo explicitamente.

Os alertas aparecem em destaque no relatório de atualização e na sua versão em
texto.

---

## 13. Novidades da v7

### 13.1 Legenda do gráfico "Valor no exercício por unidade" filtra

Clicar no nome de uma secretaria na legenda aplica o filtro **Unidade/Órgão**
àquela secretaria. O seletor da barra superior é atualizado junto, e todas as
abas passam a refletir o recorte. Clicar novamente na secretaria já filtrada
limpa o filtro. A secretaria ativa fica marcada com **●** na legenda.

O nome completo é preservado internamente: o rótulo exibido é encurtado quando
longo, mas o filtro recebe exatamente o valor gravado nos dados.

> Detalhe técnico registrado no código: a legenda precisou usar o gerador de
> rótulos **da rosca** (`Chart.overrides.doughnut`). O gerador global produz um
> item por conjunto de dados, o que num gráfico de rosca resulta numa legenda
> com um único item.

### 13.2 Validação da aba Gestão Contratual

Conferida item a item contra o cálculo independente do backend, com dados
cobrindo contratos vencidos, vencendo em 30/60/90 dias, com e sem aditivos,
com e sem nova vigência:

| Item | Resultado |
|---|---|
| KPIs (contratos, vencidos, 30/60/90 dias, com aditivos) | conferem |
| "Vencimentos por mês" — faixas e contagem mês a mês | conferem; usa o exercício do pacote |
| "Por modalidade de licitação" | distribuição correta |
| Tabela "Linha do tempo de vigências" | 26 linhas, 9 colunas |
| Selos de prazo (vermelho / âmbar / verde) | corretos por faixa |
| Coluna "Nova vigência" | datas exibidas quando existem |
| Filtro por unidade e filtro de alerta | recalculam a aba |
| Ordenação por cabeçalho | funcional |
| Erros de console | nenhum |

### 13.3 Dois defeitos corrigidos em "Aditivos por contrato"

A validação revelou que o gráfico **contradizia o próprio KPI**:

**Limite de 15 barras.** O gráfico usava a função genérica de barras, limitada
a 15 categorias. Com 22 contratos aditivados, o KPI "Com aditivos" mostrava 22
e o gráfico exibia 15 — sete contratos sumiam sem aviso.

**Colisão pelo nome da contratada.** Cada barra era identificada pelo nome da
empresa. Dois contratos da mesma contratada colidiam na mesma chave e um deles
era descartado silenciosamente.

Agora cada contrato é uma barra própria, identificada por ficha + contratada, e
o gráfico exibe todos, com rolagem vertical dentro do cartão. Verificado: com
22 contratos aditivados, KPI e gráfico mostram 22, e os dois contratos da mesma
empresa aparecem separados.

### 13.4 Achado pendente (outra aba)

Na aba **Fornecedores**, o cartão "Top 20 fornecedores por valor no exercício"
seleciona os 20 maiores, mas a função de desenho corta em 15. *Corrigido na
v8 (seção 14.3).*

---

## 14. Novidades da v8

### 14.1 Correção do empilhamento das faixas de rolagem

**Sintoma.** A cada mudança de filtro, os gráficos com rolagem ganhavam uma
faixa a mais, aninhada dentro da anterior.

**Causa.** As funções obtinham o contêiner com `cv.parentElement`. Isso só
estava correto na PRIMEIRA renderização: a partir da segunda, o pai do canvas
já era a própria faixa criada antes. A busca por uma faixa existente passava
então a ocorrer *dentro* da faixa anterior, não a encontrava, e uma nova era
criada aninhada — uma por renderização.

**Correção.** Uma função única (`prepararFaixa`) passou a resolver o contêiner
sempre pelo `.chart-box`, que é fixo: devolve o canvas para ele, remove todas as
faixas remanescentes — inclusive as aninhadas de execuções anteriores — e cria
uma única faixa nova. É idempotente. Aplicada aos quatro gráficos com rolagem.

**Verificação.** O cenário relatado (filtrar uma secretaria → trocar de aba →
voltar para "Todas" → retornar à aba do gráfico) e um teste de estresse com 12
alternâncias de filtro em quatro abas passaram a terminar sempre com **uma**
faixa por gráfico. Reintroduzindo o defeito de propósito, o mesmo teste acusa 3
faixas no cenário relatado e 15 no estresse — ou seja, o teste detecta a falha.

### 14.2 Validação da aba Fornecedores

| Item | Resultado |
|---|---|
| KPIs (fornecedores distintos, valor contratado, concentração top 5, com contrato vencido) | conferem |
| Tabela "Ranking de fornecedores" | 58 linhas, 7 colunas |
| Soma da coluna "Contratos" | igual ao total de contratos |
| Coluna "Unidades" (fornecedor que atende várias secretarias) | lista todas corretamente |
| Ordenação por qualquer coluna | funcional |
| Filtro por unidade e por fornecedor | recalculam a aba |
| Erros de console | nenhum |

### 14.3 "Top 20 fornecedores": o título agora corresponde ao gráfico

O cartão selecionava os 20 maiores fornecedores, mas a função genérica de
desenho cortava em 15 — cinco ficavam de fora sem aviso. Passa a exibir os 20,
com rolagem vertical dentro do cartão.

### 14.4 Verificação automática ampliada

`testes/verificar_sistema.py` passou a conferir, além das âncoras dos novos
gráficos, que **nenhuma** função de gráfico resolve o contêiner por
`cv.parentElement` — a causa raiz do empilhamento — e que todas usam
`prepararFaixa`.

---

## 15. Novidades da v9

### 15.1 Atalho na Área de Trabalho

`Criar atalho na Area de Trabalho.bat` cria o atalho **SIGO — Gestão de
Contratos**, com ícone gerado a partir do brasão do Município (`sigo.ico`).
No dia a dia, um duplo clique sobe o servidor e abre o navegador no painel.

O iniciador (`abrir_sigo.py`, chamado por `Abrir SIGO.bat` no Windows e por
`abrir_sigo.sh` no Linux/macOS) resolve o que antes era manual:

- localiza o Python instalado e avisa, com orientação, se não houver;
- instala as bibliotecas que faltarem (apenas na primeira execução);
- escolhe uma porta livre a partir da 8000 — se o SIGO já estiver aberto, a
  segunda janela sobe na 8001 em vez de falhar;
- **espera a porta responder antes de abrir o navegador**, evitando a página de
  "não foi possível conectar" que apareceria ao abrir cedo demais;
- mostra na janela a pasta de pacotes e qual pacote está carregado.

### 15.2 Teto de escala no gráfico por unidade

Quando uma secretaria tem orçamento muito acima das demais, o eixo se estica
para caber a maior barra e todas as outras encolhem até desaparecer.

O eixo passa a ter **teto fixo de R$ 500 milhões**. As barras que ultrapassam
são cortadas na borda; a unidade recebe a marca **"+++"** no rótulo, o topo do
eixo mostra `R$ 500M +++`, e o valor real continua no tooltip. Verificado com
uma unidade de R$ 2,4 bilhões contra outras de R$ 12 a 58 milhões: as menores
voltaram a ter altura legível.

### 15.3 Botão "Expandir"

Botão pequeno (75 × 24 px) no cartão do gráfico, ao lado da legenda. Abre o
gráfico **sem teto**, com **escala fixa de 1 pixel por R$ 1 milhão** — a altura
decorre do valor, não do espaço disponível —, permitindo rolagem horizontal e
vertical para ler todas as barras.

Dois cuidados: a janela abre **na base do eixo**, onde estão os rótulos das
unidades e as barras menores (rolar para cima mostra até onde vai a maior); e a
altura é limitada a 20.000 px para não estourar o tamanho máximo de canvas dos
navegadores — nesse caso a escala é recalculada e informada na própria janela.

### 15.4 Validação da aba Painel de Alertas

Com dados cobrindo todos os alertas simultaneamente (vencidos, vencendo em 90
dias, saldo < 20%, execução > 90%, sem empenho):

| Item | Resultado |
|---|---|
| Cinco KPIs | conferem com o cálculo do backend |
| Seis cartões de alerta | contadores corretos |
| Contador × itens listados em cada cartão | coincidem |
| "Vencem em até 90 dias" | exclui corretamente os já vencidos |
| Cartão sem dados | exibe a orientação de preenchimento |
| Clique no item abre a ficha do contrato | funcional (5 grupos de campos) |
| Coerência com o filtro de alerta da barra superior | os quatro filtros batem |
| Filtro por unidade | recalcula os cartões |
| Erros de console | nenhum |

Nenhum defeito encontrado nesta aba.

---

## 16. Novidades da v10 — aba Relatórios

### 16.1 Por que os relatórios coincidiam

**02 e 03 iguais ao 07.** Não era duplicidade de código. Os relatórios 02 e 03
agrupam por *elemento de despesa* e *fonte de recurso*; esses campos vêm em
branco nas planilhas, e a função de agrupamento lançava todos os contratos em
um único grupo "Não informado". O relatório degenerava em uma lista corrida de
todos os contratos — exatamente o conteúdo do relatório 07. O agrupamento
colapsava por falta de dado.

**04 e 11 iguais entre si.** Aqui o problema era de critério: ambos
selecionavam `vencido ou vencendo em 90 dias`, com a mesma ordenação. As
finalidades são distintas — acompanhamento de prazo e planejamento de licitação
—, mas o conjunto de contratos era idêntico; só as colunas mudavam.

### 16.2 A secretaria de cada contrato

Correção comum a todos os relatórios de nível contrato (02, 03, 04, 05, 06, 07,
10 e 11): a coluna antes rotulada "Unid." passou a se chamar **"Secretaria"** e
recebe destaque visual. Além disso:

- **faixa de distribuição por secretaria** no topo dos relatórios em lista,
  informando quantos contratos e que valor cada unidade representa naquele
  recorte;
- **relatório 07 agrupado por secretaria**, com subtotal em cada uma e total
  geral ao final.

### 16.3 Diferenciação dos relatórios

**02 e 03 — campo vazio deixou de gerar lista duplicada.** Quando o campo de
agrupamento não está preenchido em nenhum contrato do recorte, o relatório não
lista mais todos os contratos: emite um **quadro de pendência de preenchimento**,
indicando por secretaria quantos contratos estão sem o campo. É o que
efetivamente falta resolver, e não duplica nenhum outro relatório. Com o campo
parcialmente preenchido, o agrupamento funciona normalmente e os contratos sem o
dado são sinalizados.

**11 — horizonte próprio de planejamento.** O relatório de licitações passou a
adotar horizonte de **180 dias**, mais largo que o alerta de 90 dias do
relatório 04, por considerar o tempo de instrução de um novo processo. Também
**exclui os contratos com nova vigência já registrada**, cuja continuidade está
resolvida. Ganhou as colunas *Modalidade atual* e *Valor no exercício*, úteis ao
planejamento da contratação.

Verificado com dados cobrindo os dois horizontes: o relatório 04 traz contratos
que o 11 exclui (já prorrogados) e o 11 traz contratos além dos 90 dias.

> Os relatórios 01, 02, 03 e 07 abrangem, por definição, toda a base do recorte
> — o que os distingue é a organização (por unidade, por elemento, por fonte e
> por secretaria com subtotais), verificada automaticamente.

### 16.4 Validação da aba Relatórios

| Item | Resultado |
|---|---|
| Doze relatórios emitem sem erro | conferem |
| Identificação da secretaria em todos os relatórios de contrato | conferem |
| 04 e 11 deixaram de coincidir | conferem |
| 01, 02, 03 e 07 organizam a base de formas distintas | conferem |
| Subtotais por secretaria e total geral no relatório 07 | conferem |
| Cabeçalho institucional (brasão e logo) | conferem |
| Relatórios respeitam os filtros ativos | conferem |
| Erros de console | nenhum |
