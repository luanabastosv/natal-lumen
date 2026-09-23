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

export const api = {
  get: (caminho) => pedir(caminho),
  post: (caminho, body) => pedir(caminho, { method: "POST", body }),
  put: (caminho, body) => pedir(caminho, { method: "PUT", body }),
  patch: (caminho, body) => pedir(caminho, { method: "PATCH", body }),
  delete: (caminho) => pedir(caminho, { method: "DELETE" }),
};
