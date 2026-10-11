const API_URL = import.meta.env.VITE_API_URL ?? "/acesso/api";

const METODOS_QUE_ALTERAM = ["POST", "PUT", "PATCH", "DELETE"];

/** Erro vindo da API, com o status para quem chamou decidir o que fazer.
 *
 * `status` 0 quer dizer que a resposta nunca chegou: sem internet, ou o pedido
 * passou do tempo. Nesse caso `incerto` diz se o pedido ALTERAVA dados — e ai
 * nao da para saber se o servidor gravou antes de a conexao cair.
 */
export class ErroApi extends Error {
  constructor(mensagem, status, { incerto = false } = {}) {
    super(mensagem);
    this.name = "ErroApi";
    this.status = status;
    this.incerto = incerto;
  }
}

// Quanto esperar antes de desistir. Sem limite, num celular com sinal ruim o
// botao ficava em "Salvando..." por minutos, e a pessoa fechava a aba sem saber
// se tinha gravado. Arquivo e download ganham mais tempo: a foto do cartao e o
// ZIP de agradecimentos demoram de verdade numa conexao lenta.
const ESPERA_MS = 60_000;
const ESPERA_ARQUIVO_MS = 180_000;

const SEM_CONEXAO =
  "Sem conexão com o servidor. Confira a internet e tente de novo.";
const SEM_CONEXAO_AO_SALVAR =
  "A conexão caiu antes da resposta. Recarregue a página e confira antes de tentar de novo.";

/** fetch com tempo limite, e falha de rede traduzida.
 *
 * O navegador avisa falta de internet com um TypeError em ingles ("Failed to
 * fetch", "Load failed" no iPhone), que aparecia cru na tela. Aqui ele vira
 * ErroApi com status 0 e uma frase que diz o que fazer.
 */
async function buscar(url, opcoes, esperaMs) {
  const controle = new AbortController();
  const relogio = setTimeout(() => controle.abort(), esperaMs);
  try {
    return await fetch(url, { ...opcoes, signal: controle.signal });
  } catch {
    const altera = METODOS_QUE_ALTERAM.includes(opcoes.method ?? "GET");
    throw new ErroApi(altera ? SEM_CONEXAO_AO_SALVAR : SEM_CONEXAO, 0, {
      incerto: altera,
    });
  } finally {
    clearTimeout(relogio);
  }
}

/** A frase para um erro que nao veio da aplicacao, e sim do caminho ate ela. */
function mensagemPorStatus(status, metodo, padrao) {
  if (status === 429) {
    return "Muitos pedidos ao mesmo tempo. Espere alguns segundos e tente de novo.";
  }
  // 502/503/504 sao do nginx: a API esta reiniciando (numa publicacao) ou caiu.
  // No 504 o pedido pode ter chegado e estar gravando quando o nginx desistiu.
  if (status === 504 && METODOS_QUE_ALTERAM.includes(metodo)) {
    return SEM_CONEXAO_AO_SALVAR;
  }
  if (status === 502 || status === 503 || status === 504) {
    return "O servidor está fora do ar por um instante. Tente de novo em um minuto.";
  }
  return padrao;
}

/** Erro de uma resposta que chegou, com a frase do servidor quando ha. */
function erroDaResposta(resposta, corpo, metodo, padrao) {
  // O FastAPI responde {detail: "..."}; o nginx (429, 502...) responde HTML,
  // e ai corpo e null.
  const detalhe = typeof corpo?.detail === "string" ? corpo.detail : null;
  return new ErroApi(
    detalhe ?? mensagemPorStatus(resposta.status, metodo, padrao),
    resposta.status,
    { incerto: resposta.status === 504 && METODOS_QUE_ALTERAM.includes(metodo) },
  );
}

function lerCookie(nome) {
  const achado = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${nome}=`));
  return achado ? decodeURIComponent(achado.split("=").slice(1).join("=")) : null;
}

async function pedir(caminho, { method = "GET", body, ...resto } = {}) {
  const cabecalhos = { ...resto.headers };

  if (body !== undefined) {
    cabecalhos["Content-Type"] = "application/json";
  }

  // O cookie da sessao e httpOnly e vai sozinho; o do CSRF e legivel de
  // proposito, para ser copiado para o cabecalho nos metodos que alteram dados.
  if (METODOS_QUE_ALTERAM.includes(method)) {
    const csrf = lerCookie("nl_csrf");
    if (csrf) cabecalhos["X-CSRF-Token"] = csrf;
  }

  const resposta = await buscar(
    `${API_URL}${caminho}`,
    {
      ...resto,
      method,
      headers: cabecalhos,
      // Sem isto o cookie da sessao nao viaja.
      credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    ESPERA_MS,
  );

  if (resposta.status === 204) return null;

  const corpo = await resposta.json().catch(() => null);

  if (!resposta.ok) {
    throw erroDaResposta(
      resposta, corpo, method, `Erro ${resposta.status} ao falar com o servidor.`,
    );
  }

  return corpo;
}

/** Busca um arquivo da API como blob, com o nome que o servidor mandou.
 *
 * Nao da para usar um <a download> apontando para a API: o link nao sabe
 * tratar erro (uma sessao expirada viraria um arquivo com JSON de erro
 * dentro). Assim o erro chega como ErroApi, igual ao resto do sistema.
 */
async function pegarBlob(caminho) {
  const resposta = await buscar(
    `${API_URL}${caminho}`,
    { credentials: "include" },
    ESPERA_ARQUIVO_MS,
  );

  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null);
    throw erroDaResposta(resposta, corpo, "GET", `Erro ${resposta.status} ao baixar o arquivo.`);
  }

  const disposicao = resposta.headers.get("Content-Disposition") ?? "";
  const nomeArquivo = disposicao.match(/filename="?([^"]+)"?/)?.[1] ?? "arquivo";

  return { blob: await resposta.blob(), nomeArquivo };
}

/** Dispara o "salvar como" do navegador para um blob ja em maos. */
export function salvarBlob(blob, nomeArquivo) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Sem revogar, o blob fica na memoria ate a aba fechar.
  URL.revokeObjectURL(url);
}

/** POST de multipart/form-data.
 *
 * Nao da para reusar `pedir`: ele forca Content-Type JSON, e num FormData
 * quem tem de escrever o cabecalho e o navegador — so ele sabe a fronteira
 * (boundary) que separa as partes. `padrao` e a frase para quando o servidor
 * nao manda uma.
 */
async function enviarArquivo(caminho, formData, padrao) {
  const csrf = lerCookie("nl_csrf");

  const resposta = await buscar(
    `${API_URL}${caminho}`,
    {
      method: "POST",
      credentials: "include",
      headers: csrf ? { "X-CSRF-Token": csrf } : {},
      body: formData,
    },
    ESPERA_ARQUIVO_MS,
  );

  const corpo = await resposta.json().catch(() => null);

  if (!resposta.ok) {
    throw erroDaResposta(
      resposta, corpo, "POST", padrao ?? `Erro ${resposta.status} ao enviar o arquivo.`,
    );
  }

  return corpo;
}

async function baixar(caminho) {
  const { blob, nomeArquivo } = await pegarBlob(caminho);
  salvarBlob(blob, nomeArquivo);
}

/* ---------- Pedido que nao pode gravar duas vezes ----------
 *
 * A conexao cai DEPOIS de o servidor gravar e ANTES de a resposta chegar: a
 * tela mostra erro, a pessoa clica de novo, e o mesmo padrinho (ou o mesmo
 * pagamento) chegava duas vezes. Cada envio leva uma `chave_envio`; o servidor
 * reconhece a chave repetida e devolve o que ja gravou.
 *
 * A chave pertence ao CONTEUDO do envio: repetir o mesmo formulario reaproveita
 * a mesma chave, e so um envio que deu certo a descarta. Assim nenhuma tela
 * precisa guardar chave nenhuma — basta chamar `api.postUmaVez`. Cadastrar de
 * proposito outro padrinho igual depois de um sucesso gera chave nova.
 */
const chavesEmAberto = new Map();

function novaChave() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

async function postUmaVez(caminho, body) {
  const assinatura = `${caminho} ${JSON.stringify(body)}`;
  let chave = chavesEmAberto.get(assinatura);
  if (!chave) {
    chave = novaChave();
    chavesEmAberto.set(assinatura, chave);
  }
  const resposta = await pedir(caminho, {
    method: "POST",
    body: { ...body, chave_envio: chave },
  });
  chavesEmAberto.delete(assinatura);
  return resposta;
}

export const api = {
  get: (caminho) => pedir(caminho),
  baixar,
  blob: pegarBlob,
  enviarArquivo,
  post: (caminho, body) => pedir(caminho, { method: "POST", body }),
  postUmaVez,
  put: (caminho, body) => pedir(caminho, { method: "PUT", body }),
  patch: (caminho, body) => pedir(caminho, { method: "PATCH", body }),
  // O corpo e opcional: so o apagar que pede a senha de novo manda um.
  delete: (caminho, body) => pedir(caminho, { method: "DELETE", body }),
};
