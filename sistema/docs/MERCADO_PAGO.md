# Link de pagamento do Mercado Pago

Quando o padrinho quer pagar no cartão, o comissário escolhe **Cartão (link)**
no passo "Pagamento" do apadrinhar. O sistema gera um link do Mercado Pago, o
comissário manda pelo WhatsApp, e o pagamento entra sozinho quando é aprovado.

## Como funciona

1. O comissário escolhe as crianças e a forma **Cartão (link)**. Não há data
   nem comprovante.
2. O sistema reserva as crianças para o padrinho e pede o link ao Mercado Pago.
   Se o Mercado Pago falhar, nada fica gravado.
3. A tela mostra o link, com **Mandar no WhatsApp**, **Copiar link**,
   **Conferir pagamento** e **Cancelar link**. O mesmo bloco fica na ficha do
   padrinho enquanto o link vale.
4. Quando o Mercado Pago aprova, o sistema cria o pagamento (forma "Cartão",
   com o número da transação no lugar do comprovante) e liga as crianças a ele.
   A tela vai para o agradecimento, como no Pix.

### Aviso de pagamento aprovado

O padrinho paga minutos depois, e quem gerou o link já pode estar em outra
tela. O sistema pergunta de tempos em tempos (a cada 20 segundos enquanto há
link esperando) e, quando o pagamento cai, mostra no canto da tela de quem
gerou o link: "Fulano pagou R$ 130,00 no cartão. Falta mandar o
agradecimento." O botão **Agradecer agora** abre os dois passos de sempre
(baixar a imagem, abrir o WhatsApp). **Depois** esconde até a próxima vez que
a pessoa abrir o sistema. O aviso só some de vez quando ela abre o
agradecimento.

O pagamento entra como **A conferir**, igual aos outros: quem confere continua
sendo a coordenação.

### Prazo da reserva

- O link vale `MERCADOPAGO_LINK_MINUTOS` (30 minutos por padrão). Enquanto vale, a
  criança aparece como "reservada, a pagar" para os outros comissários.
- Vencido sem pagamento, a criança volta a ficar livre. Antes de soltar, o
  sistema pergunta ao Mercado Pago uma última vez. Se o pagamento estiver em
  análise, a reserva continua até sair a resposta.
- Se o padrinho pagar depois de o link vencer ou ser cancelado, o dinheiro
  entra assim mesmo, **sem criança**, com uma observação para a coordenação
  decidir o destino.
- O link aceita **só cartão** (crédito e débito). Pix, boleto e lotérica estão
  desligados: o Pix o padrinho já faz direto, com comprovante, e boleto e
  lotérica demoram dias para compensar. O único que o Mercado Pago não deixa
  desligar é o saldo da conta Mercado Pago do próprio padrinho, que cai na hora.

### O que vai para o Mercado Pago

O valor, a descrição "Natal Lumen: 2 cestas + 1 festa" e o nome e o email do
padrinho (para o formulário vir preenchido). **Nome de criança não sai do
sistema.**

### Segurança do aviso

O Mercado Pago avisa o sistema em `/acesso/api/mercadopago/notificacoes`. O
sistema não acredita no aviso: tira dele só o número do pagamento e lê o
pagamento na API do Mercado Pago com o próprio token. Com
`MERCADOPAGO_SEGREDO_WEBHOOK` preenchido, aviso com assinatura errada é
recusado.

---

## Configurar

### 1. Criar a aplicação (conta de verdade, a mesma da lojinha)

1. Entre em <https://www.mercadopago.com.br/developers/panel/app> com a conta
   do Mercado Pago que recebe da lojinha.
2. **Criar aplicação**. Nome: "Sistema Natal Lumen". Tipo de solução:
   **Pagamentos online**. Produto: **Checkout Pro**. Não é preciso marcar
   plataforma de e-commerce.
3. Dentro da aplicação, em **Credenciais de produção**, ative as credenciais
   (o Mercado Pago pede ramo de atividade e site: `https://natallumen.com`).
4. Copie o **Access Token** de produção. É ele que vai no `.env` do servidor.
   Não mande por WhatsApp nem email: cole direto no servidor.

Criar essa aplicação não muda nada na lojinha. O Shopify usa a integração
dele, e os dois recebem na mesma conta.

### 2. Testar no seu computador (contas de teste)

Atenção: quem paga o link é a conta **Comprador** de teste. Logada como a
conta Vendedor (a dona do token), o botão "Pagar" fica travado, porque seria
pagar a si mesma. O Mastercard 5031… dos exemplos antigos não é mais aceito
no Brasil; use o Visa abaixo. Testado em 07/11/2026.

O Mercado Pago testa com **contas de teste**, que não mexem em dinheiro real.

1. Na aplicação, abra **Contas de teste** e crie duas: uma **Vendedor** e uma
   **Comprador** (país Brasil). Anote usuário e senha de cada uma.
2. Abra uma janela anônima, entre no Mercado Pago com a conta **Vendedor de
   teste**, vá em <https://www.mercadopago.com.br/developers/panel/app>, crie
   uma aplicação igual à do passo 1 e copie o **Access Token de produção dela**
   (é da conta de teste, então não cobra de verdade).
3. No `backend/.env` do seu computador:

   ```
   MERCADOPAGO_ACCESS_TOKEN=APP_USR-...   # o da conta Vendedor de teste
   ```

   Deixe `URL_PUBLICA` vazio. Reinicie o backend.
4. Apadrinhe pela tela com **Cartão (link)**. Abra o link numa janela anônima,
   entre com a conta **Comprador de teste** e pague com um cartão de teste:

   | | |
   | --- | --- |
   | Visa | 4235 6477 2802 5682 |
   | Validade / CVV | 11/30 / 123 |
   | Nome no cartão | `APRO` (aprova), `OTHE` (recusa), `CONT` (fica pendente) |
   | CPF | 12345678909 |

5. A tela do sistema confere sozinha a cada 15 segundos (ou aperte
   **Conferir pagamento**). Aprovado, as crianças viram apadrinhadas e o
   pagamento aparece no Financeiro como "Mercado Pago".

Os cartões de teste mudam de vez em quando. A lista atual fica em
<https://www.mercadopago.com.br/developers/pt/docs/checkout-pro/integration-test/test-cards>.

### 3. Ligar na produção

1. No `.env` do servidor:

   ```
   MERCADOPAGO_ACCESS_TOKEN=APP_USR-...   # o de produção da conta de verdade
   URL_PUBLICA=https://acesso.natallumen.com
   ```

2. Na aplicação do Mercado Pago, em **Webhooks → Configurar notificações**:
   - URL de produção: `https://acesso.natallumen.com/acesso/api/mercadopago/notificacoes`
   - Evento: **Pagamentos**
   - Salve e copie a **assinatura secreta** para `MERCADOPAGO_SEGREDO_WEBHOOK`.
3. Rode a migration e reinicie (o `publicar.sh` já faz as duas coisas).
4. Faça um pagamento real pequeno de ponta a ponta antes de avisar o time.

O nginx precisa deixar passar `POST /acesso/api/mercadopago/notificacoes` sem
login. Hoje ele repassa todo `/acesso/api/` ao backend, então não há o que
mudar.
