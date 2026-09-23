import { useCallback, useEffect, useMemo, useState } from "react";
import * as auth from "../services/auth.js";
import { SessaoContexto } from "./sessao-contexto.js";

const CHAVE_EDICAO = "nl_edicao_ativa";

function lerEdicaoGuardada() {
  try {
    const valor = Number(localStorage.getItem(CHAVE_EDICAO));
    return Number.isFinite(valor) && valor > 0 ? valor : null;
  } catch {
    // Navegador com armazenamento bloqueado: segue sem lembrar a escolha.
    return null;
  }
}

export function ProvedorSessao({ children }) {
  const [usuario, definirUsuario] = useState(null);
  const [carregando, definirCarregando] = useState(true);
  const [edicaoEscolhida, definirEdicaoEscolhida] = useState(lerEdicaoGuardada);

  // Ao abrir a pagina, pergunta ao backend quem esta na sessao. O cookie e
  // httpOnly: o JavaScript nao consegue ler o token, so perguntar.
  useEffect(() => {
    let vivo = true;

    auth
      .quemSouEu()
      .then((dados) => vivo && definirUsuario(dados))
      .catch(() => vivo && definirUsuario(null))
      .finally(() => vivo && definirCarregando(false));

    return () => {
      vivo = false;
    };
  }, []);

  const escolherEdicao = useCallback((id) => {
    definirEdicaoEscolhida(id);
    try {
      localStorage.setItem(CHAVE_EDICAO, String(id));
    } catch {
      // sem problema: a escolha vale so para esta visita
    }
  }, []);

  const entrar = useCallback(async (email, senha) => {
    const dados = await auth.entrar(email, senha);
    definirUsuario(dados);
    return dados;
  }, []);

  const sair = useCallback(async () => {
    try {
      await auth.sair();
    } finally {
      // Mesmo que o pedido falhe, a tela volta ao login.
      definirUsuario(null);
      try {
        localStorage.removeItem(CHAVE_EDICAO);
      } catch {
        // sem problema
      }
    }
  }, []);

  const valor = useMemo(() => {
    const permissoes = new Set(usuario?.permissoes ?? []);
    const vinculos = usuario?.vinculos ?? [];
    const ids = vinculos.map((v) => v.edicao_id);

    // Derivada durante o render, e nao por efeito: a escolha guardada so vale
    // se o usuario ainda tiver vinculo com aquela edicao.
    const edicaoAtiva = ids.includes(edicaoEscolhida)
      ? edicaoEscolhida
      : (ids[0] ?? null);

    return {
      usuario,
      carregando,
      autenticado: usuario !== null,
      entrar,
      sair,
      edicaoAtiva,
      escolherEdicao,
      vinculoAtivo: vinculos.find((v) => v.edicao_id === edicaoAtiva) ?? null,
      // So esconde menus. Quem decide de verdade e o backend, em cada rota.
      pode: (permissao) => Boolean(usuario?.admin_geral) || permissoes.has(permissao),
    };
  }, [usuario, carregando, entrar, sair, edicaoEscolhida, escolherEdicao]);

  return <SessaoContexto.Provider value={valor}>{children}</SessaoContexto.Provider>;
}
