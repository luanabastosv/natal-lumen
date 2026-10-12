import { useEffect, useState } from "react";
import { Entrada, Selecao } from "../core/Campo.jsx";
import { padrinhosParecidos } from "../../services/padrinhos.js";

/* O formulario do padrinho, dividido entre a janela do computador (novo e
   editar) e a pagina de cadastro do celular. Um lugar so para os campos e as
   regras deles, para os dois caminhos nao divergirem. */

/** `avisoNome`, `avisoWhatsapp`, `avisoEmail`: o que aparece logo abaixo de
 *  cada campo — o aviso de padrinho ja cadastrado (AvisoParecidos), quando
 *  houver. */
export function CamposPadrinho({
  campos,
  definirCampos,
  avisoNome = null,
  avisoWhatsapp = null,
  avisoEmail = null,
}) {
  const mudar = (campo) => (e) => definirCampos({ ...campos, [campo]: e.target.value });
  return (
    <div className="linha-campos">
      <Entrada
        rotulo="Nome"
        value={campos.nome}
        onChange={mudar("nome")}
        dica={avisoNome}
        obrigatorio
      />
      {/* WhatsApp e email obrigatorios: e por eles que o agradecimento chega,
          e um padrinho sem contato e um padrinho que ninguem consegue cobrar
          nem agradecer. So a observacao e opcional. */}
      <Entrada
        rotulo="WhatsApp"
        tipo="tel"
        inputMode="tel"
        value={campos.whatsapp}
        onChange={mudar("whatsapp")}
        placeholder="(85) 99999-0000"
        dica={avisoWhatsapp}
        obrigatorio
      />
      <Entrada
        rotulo="Email"
        tipo="email"
        value={campos.email}
        onChange={mudar("email")}
        dica={avisoEmail}
        obrigatorio
      />
      <Entrada rotulo="Observações" value={campos.observacoes} onChange={mudar("observacoes")} />
      <Selecao
        rotulo="Já é membro Ser Feliz?"
        value={campos.membro_ser_feliz}
        onChange={mudar("membro_ser_feliz")}
        obrigatorio
      >
        <option value="" disabled>
          Selecione
        </option>
        <option value="sim">Sim</option>
        <option value="nao">Não</option>
      </Selecao>
      <Selecao
        rotulo="Tem interesse em contribuir mensalmente?"
        value={campos.interesse_mensal}
        onChange={mudar("interesse_mensal")}
        obrigatorio
      >
        <option value="" disabled>
          Selecione
        </option>
        <option value="sim">Sim</option>
        <option value="nao">Não</option>
        <option value="ja_contribui">Já contribuo</option>
      </Selecao>
    </div>
  );
}

/** Quando cada campo ja da para comparar: nome com sobrenome (um nome so
 *  seria parecido com metade da lista), WhatsApp com DDD, email com @ e
 *  dominio. */
const PRONTO = {
  nome: (v) => v.split(/\s+/).length >= 2,
  whatsapp: (v) => v.replace(/\D/g, "").length >= 10,
  email: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v),
};

const FRASE = {
  nome: (p) => (
    <>
      <strong>{p.nome}</strong> já está cadastrado no sistema.
    </>
  ),
  whatsapp: (p) => (
    <>
      Este WhatsApp já é de <strong>{p.nome}</strong>, cadastrado no sistema.
    </>
  ),
  email: (p) => (
    <>
      Este email já é de <strong>{p.nome}</strong>, cadastrado no sistema.
    </>
  ),
};

/** "Fulano ja esta cadastrado": o aviso de padrinho repetido, enquanto se
 *  digita o nome, o WhatsApp ou o email (`campo`).
 *
 *  O mesmo doador volta semanas depois, outro comissario o cadastra de novo,
 *  e ele vira dois padrinhos — com dois pagamentos e dois agradecimentos. O
 *  aviso aparece antes de salvar e oferece o caminho certo: apadrinhar pelo
 *  cadastro que ja existe. Nao impede salvar: homonimo existe, e o mesmo
 *  telefone as vezes e o da familia.
 *
 *  Pergunta ao servidor so depois de uma pausa na digitacao, e so quando o
 *  campo ja da para comparar (ver PRONTO). */
export function AvisoParecidos({ campo = "nome", valor, edicaoId, aoEscolher }) {
  const [parecidos, definirParecidos] = useState([]);
  const termo = (valor ?? "").trim();
  const pronto = PRONTO[campo](termo);

  useEffect(() => {
    if (!edicaoId || !pronto) return undefined;
    let valido = true;
    const espera = setTimeout(() => {
      padrinhosParecidos(edicaoId, { [campo]: termo })
        .then((achados) => valido && definirParecidos(achados))
        // O aviso e uma ajuda: se a consulta falhar, o cadastro segue.
        .catch(() => valido && definirParecidos([]));
    }, 400);
    return () => {
      valido = false;
      clearTimeout(espera);
    };
  }, [edicaoId, campo, termo, pronto]);

  if (!pronto || parecidos.length === 0) return null;

  // So o mais parecido, numa linha: e um lembrete embaixo do campo, e nao um
  // bloco que empurra o formulario enquanto se digita.
  const p = parecidos[0];
  return (
    <span className="aviso-parecidos">
      {FRASE[campo](p)}{" "}
      <button type="button" className="aviso-parecidos__acao" onClick={() => aoEscolher(p)}>
        Ir para padrinho
      </button>
    </span>
  );
}
