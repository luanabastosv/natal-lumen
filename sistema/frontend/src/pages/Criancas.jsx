import { useCallback, useEffect, useState } from "react";
import Button from "../components/core/Button.jsx";
import { Entrada, Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import EmptyState from "../components/feedback/EmptyState.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { useSessao } from "../contexts/useSessao.js";
import { listarEdicoes, listarInstituicoes } from "../services/cadastros.js";
import { apagarCrianca, criarCrianca, listarCriancas } from "../services/criancas.js";
import ImportarLista from "./ImportarLista.jsx";

const POR_PAGINA = 25;
const NOVA = { instituicao_id: "", codigo: "", nome: "", idade: "", sexo: "F" };

export default function Criancas() {
  const { pode, edicaoAtiva } = useSessao();

  const [criancas, definirCriancas] = useState({ itens: [], total: 0 });
  const [edicoes, definirEdicoes] = useState([]);
  const [instituicoes, definirInstituicoes] = useState([]);

  const [edicaoId, definirEdicaoId] = useState(edicaoAtiva ?? "");
  const [instituicaoId, definirInstituicaoId] = useState("");
  const [busca, definirBusca] = useState("");
  const [codigo, definirCodigo] = useState("");
  const [pagina, definirPagina] = useState(1);

  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");
  const [sucesso, definirSucesso] = useState("");
  const [formAberto, definirFormAberto] = useState(false);
  const [campos, definirCampos] = useState(NOVA);
  const [salvando, definirSalvando] = useState(false);
  const [importando, definirImportando] = useState(false);

  useEffect(() => {
    let vivo = true;
    Promise.all([listarEdicoes(), listarInstituicoes()])
      .then(([eds, insts]) => {
        if (!vivo) return;
        definirEdicoes(eds);
        definirInstituicoes(insts);
        if (!edicaoId && eds.length) definirEdicaoId(eds[0].id);
      })
      .catch((e) => vivo && definirErro(e.message));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const buscar = useCallback(async () => {
    definirCarregando(true);
    definirErro("");
    try {
      definirCriancas(
        await listarCriancas({
          edicao_id: edicaoId,
          instituicao_id: instituicaoId,
          busca,
          codigo,
          pagina,
          por_pagina: POR_PAGINA,
        }),
      );
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirCarregando(false);
    }
  }, [edicaoId, instituicaoId, busca, codigo, pagina]);

  useEffect(() => {
    if (edicaoId) buscar();
  }, [edicaoId, instituicaoId, pagina, buscar]);

  const edicao = edicoes.find((e) => String(e.id) === String(edicaoId));
  const instituicoesDaCidade = instituicoes.filter((i) => i.cidade_id === edicao?.cidade_id);

  function aoFiltrar(evento) {
    evento.preventDefault();
    definirPagina(1);
    buscar();
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirSalvando(true);
    try {
      await criarCrianca({
        edicao_id: Number(edicaoId),
        instituicao_id: Number(campos.instituicao_id),
        codigo: campos.codigo.trim(),
        nome: campos.nome.trim(),
        idade: Number(campos.idade),
        sexo: campos.sexo,
      });
      definirSucesso(`${campos.nome.trim()} cadastrada.`);
      definirFormAberto(false);
      definirCampos(NOVA);
      buscar();
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function remover(crianca) {
    definirErro("");
    try {
      await apagarCrianca(crianca.id);
      definirSucesso(`${crianca.nome} removida.`);
      buscar();
    } catch (e) {
      definirErro(e.message);
    }
  }

  const totalPaginas = Math.max(1, Math.ceil(criancas.total / POR_PAGINA));

  if (importando) {
    return (
      <ImportarLista
        edicao={edicao}
        instituicoes={instituicoesDaCidade}
        aoTerminar={(quantas) => {
          definirImportando(false);
          if (quantas) definirSucesso(`${quantas} criança(s) importada(s).`);
          buscar();
        }}
      />
    );
  }

  return (
    <div>
      <div className="pagina__eyebrow">Dados sensíveis</div>
      <h1 className="pagina__titulo">Crianças</h1>
      <p className="pagina__lede">
        A lista mostra apenas as crianças que o seu perfil alcança. Todo acesso fica
        registrado.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>
      <Mensagem tipo="sucesso">{sucesso}</Mensagem>

      <form className="painel" onSubmit={aoFiltrar}>
        <div className="linha-campos">
          <Selecao
            rotulo="Edição"
            value={edicaoId}
            onChange={(e) => {
              definirEdicaoId(e.target.value);
              definirInstituicaoId("");
              definirPagina(1);
            }}
          >
            {edicoes.map((e) => (
              <option key={e.id} value={e.id}>{e.nome}</option>
            ))}
          </Selecao>
          <Selecao
            rotulo="Instituição"
            value={instituicaoId}
            onChange={(e) => {
              definirInstituicaoId(e.target.value);
              definirPagina(1);
            }}
          >
            <option value="">Todas que eu alcanço</option>
            {instituicoesDaCidade.map((i) => (
              <option key={i.id} value={i.id}>{i.nome}</option>
            ))}
          </Selecao>
          <Entrada
            rotulo="Buscar por nome"
            value={busca}
            onChange={(e) => definirBusca(e.target.value)}
            dica="Procura só dentro do que você alcança."
          />
          <Entrada
            rotulo="Buscar por código exato"
            value={codigo}
            onChange={(e) => definirCodigo(e.target.value)}
            dica="Alcança qualquer instituição da edição. O uso fica registrado."
          />
        </div>
        <div className="barra-acoes barra-acoes--fim">
          <Button type="submit" size="sm">Filtrar</Button>
          {(busca || codigo) && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                definirBusca("");
                definirCodigo("");
                definirPagina(1);
              }}
            >
              Limpar
            </Button>
          )}
        </div>
      </form>

      <div className="barra-acoes">
        {pode("editar_criancas") && (
          <Button
            onClick={() => {
              definirCampos({ ...NOVA, instituicao_id: instituicoesDaCidade[0]?.id ?? "" });
              definirFormAberto(true);
            }}
            disabled={instituicoesDaCidade.length === 0}
          >
            Nova criança
          </Button>
        )}
        {pode("importar_listas") && (
          <Button variant="ghost" onClick={() => definirImportando(true)} disabled={!edicao}>
            Importar lista
          </Button>
        )}
        <span className="campo__dica" style={{ marginTop: 0 }}>
          {criancas.total} criança(s)
        </span>
      </div>

      {formAberto && (
        <form className="painel" onSubmit={salvar}>
          <h2 className="painel__titulo">Nova criança</h2>
          <div className="linha-campos">
            <Selecao
              rotulo="Instituição"
              value={campos.instituicao_id}
              onChange={(e) => definirCampos({ ...campos, instituicao_id: e.target.value })}
              required
            >
              {instituicoesDaCidade.map((i) => (
                <option key={i.id} value={i.id}>{i.nome}</option>
              ))}
            </Selecao>
            <Entrada
              rotulo="Código"
              value={campos.codigo}
              onChange={(e) => definirCampos({ ...campos, codigo: e.target.value })}
              required
            />
            <Entrada
              rotulo="Nome"
              value={campos.nome}
              onChange={(e) => definirCampos({ ...campos, nome: e.target.value })}
              required
            />
            <Entrada
              rotulo="Idade"
              tipo="number"
              min="0"
              max="21"
              value={campos.idade}
              onChange={(e) => definirCampos({ ...campos, idade: e.target.value })}
              required
            />
            <Selecao
              rotulo="Sexo"
              value={campos.sexo}
              onChange={(e) => definirCampos({ ...campos, sexo: e.target.value })}
            >
              <option value="F">Feminino</option>
              <option value="M">Masculino</option>
            </Selecao>
          </div>
          <div className="barra-acoes barra-acoes--fim">
            <Button type="submit" carregando={salvando}>Salvar</Button>
            <Button variant="ghost" onClick={() => definirFormAberto(false)}>Cancelar</Button>
          </div>
        </form>
      )}

      {carregando ? (
        <Carregando>Carregando crianças...</Carregando>
      ) : criancas.itens.length === 0 ? (
        <EmptyState
          titulo="Nenhuma criança encontrada"
          corpo={
            busca || codigo
              ? "Nenhum resultado para esta busca."
              : "Importe a lista enviada pela instituição ou cadastre uma a uma."
          }
        />
      ) : (
        <>
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Código</th>
                  <th>Idade</th>
                  <th>Sexo</th>
                  <th>Instituição</th>
                  {pode("editar_criancas") && <th />}
                </tr>
              </thead>
              <tbody>
                {criancas.itens.map((c) => (
                  <tr key={c.id}>
                    <td>{c.nome}</td>
                    <td>{c.codigo}</td>
                    <td>{c.idade}</td>
                    <td>{c.sexo === "F" ? "Feminino" : "Masculino"}</td>
                    <td>{c.instituicao}</td>
                    {pode("editar_criancas") && (
                      <td>
                        <Button size="sm" variant="ghost" onClick={() => remover(c)}>
                          Remover
                        </Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPaginas > 1 && (
            <div className="barra-acoes" style={{ marginTop: "var(--space-5)" }}>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => definirPagina((p) => p - 1)}
                disabled={pagina <= 1}
              >
                Anterior
              </Button>
              <span className="campo__dica" style={{ marginTop: 0 }}>
                Página {pagina} de {totalPaginas}
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => definirPagina((p) => p + 1)}
                disabled={pagina >= totalPaginas}
              >
                Próxima
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
