# SIGO — Guia de uso e solução de problemas

Documento prático para quem prepara e envia os pacotes de planilhas.

---

## 0. Abrindo o sistema (atalho na Área de Trabalho)

**Uma vez só:** abra a pasta do sistema e dê duplo clique em
**`Criar atalho na Area de Trabalho.bat`**. O atalho
**SIGO — Gestão de Contratos**, com o brasão do Município, aparece na Área de
Trabalho.

**No dia a dia:** duplo clique no atalho. Uma janela preta abre (é o servidor —
deixe-a aberta) e o navegador abre sozinho no painel. Para encerrar, feche a
janela preta.

O iniciador cuida sozinho de:
- localizar o Python instalado;
- instalar as bibliotecas necessárias, se faltarem (só na primeira vez);
- escolher outra porta se a 8000 estiver ocupada — útil se o SIGO já estiver
  aberto em outra janela;
- esperar o servidor responder antes de abrir o navegador, evitando a página de
  "não foi possível conectar".

Se preferir não usar o atalho, `Abrir SIGO.bat` faz o mesmo. Em Linux ou macOS,
use `abrir_sigo.sh`.

> Se o Python não estiver instalado, o iniciador avisa e indica o endereço de
> download. Na instalação, marque **"Add Python to PATH"**.

---

## 1. Preparando o pacote — lista de conferência

**1. Recalcule cada planilha antes de compactar.** É o item mais importante,
e a causa mais comum de uma secretaria não aparecer no painel.

> Abra a planilha no Excel, pressione **F9**, salve (**Ctrl+S**) e feche.

A aba "Base de Dados" não é digitada: ela é montada por fórmulas que espelham
a aba do ano. Uma fórmula guarda duas coisas — a fórmula e o último resultado
calculado. O sistema lê o resultado. Se a planilha foi salva sem recalcular,
esse resultado não existe e a aba é lida como vazia.

*A partir da versão atual o sistema contorna isso sozinho, lendo a aba do ano.
Ainda assim, recalcular é o caminho mais seguro: é o único que garante os
valores exatamente como a secretaria os vê.*

**2. Confira o nome dos arquivos.**

```
SEMAD_Controle_Contratos_2027.xlsx
└─┬──┘ └────────┬───────┘ └─┬──┘
sigla    texto fixo        ano
```

**3. Monte a estrutura de pastas.**

```
Contratos_Municipio_2027/          ← nome livre
   └── CONTRATOS_2027/             ← este nome define o exercício do painel
         ├── SEMAD_Controle_Contratos_2027.xlsx
         ├── SEMEC_Controle_Contratos_2027.xlsx
         └── ...
```

**4. Compacte a pasta de fora.** Clique com o botão direito sobre
`Contratos_Municipio_2027` → **Enviar para** → **Pasta compactada**.
Compacte a pasta, não os arquivos soltos.

**5. Feche as planilhas no Excel** antes de enviar. Um arquivo aberto pode
ficar bloqueado pelo sistema operacional.

---

## 2. Enviando

1. Abra o painel (`http://127.0.0.1:8000/`).
2. Clique em **Atualizar dados (.zip)**.
3. Escolha o pacote.
4. Aguarde — o processamento leva alguns segundos por secretaria.
5. Leia o relatório e clique em **Atualizar painel**.

### Conferir antes de publicar

Para testar um pacote sem trocar os dados em uso, envie-o para
`POST /api/verificar`. O sistema responde com o mesmo relatório, mas **não**
altera o que está no ar.

---

## 3. Consultando o relatório depois

O relatório de cada atualização fica **gravado**. Para reabrir, clique em
**Relatório de dados**, ao lado do botão de atualização. A janela mostra a
carga mais recente e, quando há mais de uma, uma lista para escolher cargas
anteriores.

**Abrir em texto** gera uma versão simples, que pode ser impressa, salva ou
encaminhada à secretaria responsável.

Os arquivos também ficam na pasta `relatorios/` do projeto, em duas formas:
`.json` (usado pelo painel) e `.txt` (leitura direta). O sistema guarda as 60
atualizações mais recentes.

---

## 4. Como ler o relatório

O relatório traz uma tabela com uma linha por secretaria:

| | Secretaria | Contratos | Situação |
|---|---|---|---|
| **✔** (verde) | SEMAD | 21 | lido de aba 'Base de Dados' |
| **✘** (vermelho) | SEMJUV | 0 | Nenhuma aba trouxe contratos preenchidos |

- **✔ verde** — a secretaria entrou no painel.
- **✘ vermelho** — nenhum contrato foi carregado. **Isso normalmente não é
  falha do sistema:** significa que a planilha ainda não foi preenchida pela
  equipe daquela secretaria. A coluna "Situação" esclarece o caso.
- **Situação** — para quem entrou, de qual aba os dados vieram
  (`Base de Dados` é o caminho normal; `aba '2027' (por cabeçalho)` indica que
  a Base de Dados estava vazia e o sistema recorreu à aba do ano). Para quem
  não entrou, o motivo e as abas encontradas no arquivo.
- **Arquivos ignorados** — o que estava no pacote mas não é planilha válida.
- **Avisos** — divergências que não impediram a carga.

---

## 5. Mensagens e o que fazer

| Mensagem | Causa | Solução |
|---|---|---|
| *"...salvo sem recálculo (N fórmulas sem valor)"* | Planilha salva sem recalcular | Abra no Excel, F9, salve |
| *"Nenhuma aba trouxe contratos preenchidos"* | A planilha está realmente em branco | Confirme com a secretaria |
| *"Nenhuma aba foi reconhecida como base de contratos"* | Abas renomeadas ou cabeçalho alterado | Use o modelo padrão; a aba precisa das colunas "Contratada" e "Objeto do Contrato" |
| *"está fora do padrão ... foi carregado assim mesmo"* | Nome do arquivo diferente | Renomeie para `<Sigla>_Controle_Contratos_<Ano>.xlsx` |
| *"refere-se a AAAA, mas o exercício do pacote é BBBB"* | Ano do arquivo ≠ ano da pasta | Confirme se é o arquivo certo |
| *"formato .xls antigo"* | Planilha em formato antigo | Salvar como → Pasta de Trabalho do Excel (*.xlsx) |
| *"não contém a pasta 'CONTRATOS_&lt;ano&gt;'"* | Estrutura de pastas diferente | Recrie a estrutura da seção 1 |
| *"não é um arquivo .zip válido"* | Arquivo .rar/.7z ou corrompido | Compacte com o próprio Windows |
| *"Um arquivo da carga anterior está aberto"* | Planilha aberta no Excel | Feche o Excel e envie de novo |
| *"Não foi possível falar com o servidor"* | Servidor encerrado | Reabra o terminal e execute `uvicorn servidor:app` |

---

## 6. Perguntas frequentes

**Uma secretaria não apareceu. O que faço primeiro?**
Leia o motivo no relatório. Ele nomeia as abas testadas e quantos contratos
cada uma trouxe — isso distingue "planilha em branco" de "planilha preenchida
mas com aba ou cabeçalho fora do padrão".

**Preciso enviar todas as secretarias juntas?**
Cada envio substitui a base inteira pelo conteúdo do pacote. Envie sempre o
pacote completo; secretarias ausentes do pacote somem do painel.

**Posso enviar uma planilha avulsa?**
Sim — o botão continua aceitando `.xlsx` individual, que atualiza apenas
aquela unidade. Para trocar a base inteira, use o `.zip`.

**O ano do painel mudou sozinho.**
O exercício vem do nome da pasta `CONTRATOS_<ano>`. Para o painel exibir 2027,
a pasta precisa se chamar `CONTRATOS_2027`.

**Apareceu no terminal: "Data Validation extension is not supported and will
be removed". É grave?**
Não, e não afeta nada. As planilhas usam listas suspensas que buscam as opções
na aba "Listas"; o Excel grava essa validação num formato de extensão que a
biblioteca de leitura não interpreta, e por isso ela avisa. O "will be removed"
vale apenas para a cópia em memória: se o arquivo fosse *salvo* por ela, as
listas se perderiam. O sistema apenas **lê** as planilhas, nunca as grava — o
arquivo da secretaria permanece intacto. O aviso foi silenciado.

**Uma secretaria aparece com ✘ vermelho. Preciso fazer algo?**
Se a planilha ainda não foi preenchida pela equipe responsável, não — é o
resultado esperado, e ela passará a aparecer quando os contratos forem
lançados. A coluna "Situação" distingue esse caso de um problema real
(planilha sem recálculo, aba renomeada, arquivo fora do padrão).

**O KPI "A suplementar" mostra um valor altíssimo. Está errado?**
O cálculo está correto, mas depende de uma coluna que costuma vir vazia. Na
planilha, *Valor a Suplementar* = *Saldo a Empenhar* − *Saldo Orçamentário da
Unidade*. Se o saldo orçamentário não for preenchido, ele vale zero e a
suplementação repete o saldo a empenhar. Preencha a coluna *Saldo Orçamentário
da Unidade* na aba do ano. O relatório de atualização sinaliza esse caso.

**No gráfico "Previsto × Empenhado × Pago por unidade" aparece "+++" em uma
secretaria. O que significa?**
Que o valor dela ultrapassa o teto do gráfico (R$ 500 milhões). O teto existe
para que as demais secretarias continuem visíveis — sem ele, uma unidade muito
grande faz todas as outras encolherem até sumir. O valor real aparece ao passar
o mouse, e o botão **Expandir**, no canto do cartão, abre o gráfico sem teto,
com rolagem horizontal e vertical para ler todas as barras.

**Os gráficos não aparecem.**
O painel busca as bibliotecas de gráfico na internet. Se a rede bloquear,
mantenha a pasta `frontend/libs/` no projeto — com ela, o sistema serve as
bibliotecas localmente.

---

## 7. Para quem administra o sistema

Antes de publicar uma versão nova:

```bash
cd testes
python verificar_sistema.py
```

Confere a integridade do HTML institucional, as âncoras dos ajustes, a sintaxe
do JavaScript injetado, o fechamento das planilhas após a leitura e o
funcionamento de duas cargas consecutivas.

Diagnóstico da carga em uso, com todo o detalhamento por arquivo:
`GET /api/diagnostico`.
