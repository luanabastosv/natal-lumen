const API_URL = import.meta.env.VITE_API_URL ?? "/acesso/api";

const METODOS_QUE_ALTERAM = ["POST", "PUT", "PATCH", "DELETE"];

/** Erro vindo da API, com o status para quem chamou decidir o que fazer. */
export class ErroApi extends Error {
  constructor(mensagem, status) {
    super(mensagem);
    this.name = "ErroApi";
    this.status = status;
  }
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

  const resposta = await fetch(`${API_URL}${caminho}`, {
    ...resto,
    method,
    headers: cabecalhos,
    // Sem isto o cookie da sessao nao viaja.
    credentials: "include",
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (resposta.status === 204) return null;

  const corpo = await resposta.json().catch(() => null);

  if (!resposta.ok) {
    throw new ErroApi(
      corpo?.detail ?? `Erro ${resposta.status} ao falar com o servidor.`,
      resposta.status,
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
  const resposta = await fetch(`${API_URL}${caminho}`, { credentials: "include" });

  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null);
    throw new ErroApi(
      corpo?.detail ?? `Erro ${resposta.status} ao baixar o arquivo.`,
      resposta.status,
    );
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
 * (boundary) que separa as partes.
 */
async function enviarArquivo(caminho, formData) {
  const csrf = lerCookie("nl_csrf");

  const resposta = await fetch(`${API_URL}${caminho}`, {
    method: "POST",
    credentials: "include",
    headers: csrf ? { "X-CSRF-Token": csrf } : {},
    body: formData,
  });

  const corpo = await resposta.json().catch(() => null);

  if (!resposta.ok) {
    throw new ErroApi(
      corpo?.detail ?? `Erro ${resposta.status} ao enviar o arquivo.`,
      resposta.status,
    );
  }

  return corpo;
}

async function baixar(caminho) {
  const { blob, nomeArquivo } = await pegarBlob(caminho);
  salvarBlob(blob, nomeArquivo);
}

export const api = {
  get: (caminho) => pedir(caminho),
  baixar,
  blob: pegarBlob,
  enviarArquivo,
  post: (caminho, body) => pedir(caminho, { method: "POST", body }),
  put: (caminho, body) => pedir(caminho, { method: "PUT", body }),
  patch: (caminho, body) => pedir(caminho, { method: "PATCH", body }),
  delete: (caminho) => pedir(caminho, { method: "DELETE" }),
};
