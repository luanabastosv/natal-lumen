import { useState } from "react";
import Button from "../components/core/Button.jsx";
import { Selecao } from "../components/core/Campo.jsx";
import Carregando from "../components/feedback/Carregando.jsx";
import Mensagem from "../components/feedback/Mensagem.jsx";
import { analisarPlanilha, confirmarImportacao } from "../services/criancas.js";

const NOMES_DOS_CAMPOS = {
  codigo: "Código",
  nome: "Nome",
  idade: "Idade",
  sexo: "Sexo",
  instituicao: "Instituição",
  observacoes: "Observações",
};

export default function ImportarLista({ edicao, instituicoes, aoTerminar }) {
  const [arquivo, definirArquivo] = useState(null);
  const [instituicaoId, definirInstituicaoId] = useState("");
  const [previa, definirPrevia] = useState(null);
  const [erro, definirErro] = useState("");
  const [analisando, definirAnalisando] = useState(false);
  const [confirmando, definirConfirmando] = useState(false);
  const [mostrarTodas, definirMostrarTodas] = useState(false);

  async function analisar(evento) {
    evento.preventDefault();
    definirErro("");
    definirAnalisando(true);
    try {
      definirPrevia(
        await analisarPlanilha({
          arquivo,
          edicaoId: edicao.id,
          instituicaoId: instituicaoId || null,
        }),
      );
    } catch (e) {
      definirErro(e.message);
    } finally {
      definirAnalisando(false);
    }
  }

  async function confirmar() {
    definirErro("");
    definirConfirmando(true);
    try {
      const resultado = await confirmarImportacao(previa.id);
      aoTerminar(resultado.importadas);
    } catch (e) {
      definirErro(e.message);
      definirConfirmando(false);
    }
  }

  // Sem erro nem aviso, mostrar as 1500 linhas nao ajuda ninguem.
  const linhasMostradas = previa
    ? mostrarTodas
      ? previa.linhas
      : previa.linhas.filter((l) => l.erros.length || l.avisos.length)
    : [];

  return (
    <div>
      <div className="pagina__eyebrow">Crianças</div>
      <h1 className="pagina__titulo">Importar lista</h1>
      <p className="pagina__lede">
        Envie a planilha que a instituição mandou. Nada é gravado até você conferir e
        confirmar.
      </p>

      <Mensagem tipo="erro">{erro}</Mensagem>

      {!previa && (
        <form className="painel" onSubmit={analisar}>
          <h2 className="painel__titulo">{edicao?.nome}</h2>

          <label className="campo">
            <span className="campo__rotulo">Planilha</span>
            <input
              type="file"
              accept=".xlsx,.xls,.csv"
              className="campo__controle"
              onChange={(e) => definirArquivo(e.target.files?.[0] ?? null)}
              required
            />
            <span className="campo__dica">
              Aceita .xlsx e .csv. Precisa ter pelo menos as colunas de código e nome —
              idade, sexo e instituição entram se estiverem lá.
            </span>
          </label>

          <Selecao
            rotulo="Instituição"
            value={instituicaoId}
            onChange={(e) => definirInstituicaoId(e.target.value)}
            dica="Use quando a planilha não tiver uma coluna de instituição."
          >
            <option value="">A planilha diz qual é</option>
            {instituicoes.map((i) => (
              <option key={i.id} value={i.id}>{i.nome}</option>
            ))}
          </Selecao>

          <div className="barra-acoes barra-acoes--fim">
            <Button type="submit" carregando={analisando} disabled={!arquivo}>
              {analisando ? "Lendo a planilha..." : "Analisar"}
            </Button>
            <Button variant="ghost" onClick={() => aoTerminar(0)} disabled={analisando}>
              Voltar
            </Button>
          </div>
        </form>
      )}

      {analisando && <Carregando>Lendo e conferindo as linhas...</Carregando>}

      {previa && (
        <>
          <div className="painel">
            <h2 className="painel__titulo">Conferência</h2>
            <p style={{ margin: "0 0 var(--space-4)", fontSize: "var(--size-body-sm)" }}>
              <strong>{previa.total}</strong> linha(s) lida(s) ·{" "}
              <strong>{previa.validas}</strong> pronta(s) para importar ·{" "}
              <strong>{previa.com_erro}</strong> com erro ·{" "}
              <strong>{previa.com_aviso}</strong> com aviso
            </p>

            <p className="campo__dica" style={{ marginTop: 0 }}>
              Colunas reconhecidas:{" "}
              {Object.entries(previa.colunas_reconhecidas)
                .map(([campo, coluna]) => `${NOMES_DOS_CAMPOS[campo] ?? campo} = "${coluna}"`)
                .join(" · ")}
              {previa.colunas_ignoradas.length > 0 && (
                <>
                  <br />
                  Colunas ignoradas: {previa.colunas_ignoradas.join(", ")}
                </>
              )}
            </p>

            {previa.com_erro > 0 && (
              <Mensagem tipo="aviso">
                As linhas com erro <strong>não serão importadas</strong>. Corrija a
                planilha e envie de novo, ou siga sem elas.
              </Mensagem>
            )}

            <div className="barra-acoes barra-acoes--fim">
              <Button
                onClick={confirmar}
                carregando={confirmando}
                disabled={previa.validas === 0}
              >
                {confirmando
                  ? "Importando..."
                  : `Importar ${previa.validas} criança(s)`}
              </Button>
              <Button variant="ghost" onClick={() => definirPrevia(null)} disabled={confirmando}>
                Escolher outra planilha
              </Button>
            </div>
          </div>

          <div className="barra-acoes">
            <Button size="sm" variant="ghost" onClick={() => definirMostrarTodas((v) => !v)}>
              {mostrarTodas ? "Mostrar só o que precisa de atenção" : "Mostrar todas as linhas"}
            </Button>
          </div>

          {linhasMostradas.length === 0 ? (
            <Mensagem tipo="sucesso">
              Nenhum problema encontrado. Todas as linhas estão prontas.
            </Mensagem>
          ) : (
            <div className="tabela-rolagem">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Linha</th>
                    <th>Código</th>
                    <th>Nome</th>
                    <th>Idade</th>
                    <th>Sexo</th>
                    <th>Instituição</th>
                    <th>Situação</th>
                  </tr>
                </thead>
                <tbody>
                  {linhasMostradas.map((l) => (
                    <tr key={l.linha}>
                      <td>{l.linha}</td>
                      <td>{l.codigo || "—"}</td>
                      <td>{l.nome || "—"}</td>
                      <td>{l.idade ?? "—"}</td>
                      <td>{l.sexo ?? "—"}</td>
                      <td>{l.instituicao ?? "—"}</td>
                      <td>
                        {l.erros.map((e) => (
                          <div key={e}>
                            <span className="etiqueta etiqueta--parado">{e}</span>
                          </div>
                        ))}
                        {l.avisos.map((a) => (
                          <div key={a}>
                            <span className="etiqueta etiqueta--espera">{a}</span>
                          </div>
                        ))}
                        {!l.erros.length && !l.avisos.length && (
                          <span className="etiqueta etiqueta--ok">ok</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
