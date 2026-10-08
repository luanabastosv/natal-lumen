import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import LayoutSistema from "./components/layout/LayoutSistema.jsx";
import { ROTAS } from "./components/layout/menu.js";
import { ProvedorNotificacoes } from "./contexts/NotificacoesContexto.jsx";
import { ProvedorSessao } from "./contexts/SessaoContexto.jsx";
import DefinirSenha from "./pages/DefinirSenha.jsx";
import EmBreve from "./pages/EmBreve.jsx";
import EsqueciSenha from "./pages/EsqueciSenha.jsx";
import Login from "./pages/Login.jsx";
import NaoEncontrada from "./pages/NaoEncontrada.jsx";
import Cartoes from "./pages/Cartoes.jsx";
import Checkin from "./pages/Checkin.jsx";
import Apadrinhar from "./pages/Apadrinhar.jsx";
import EnvioCartoes from "./pages/EnvioCartoes.jsx";
import Financeiro from "./pages/Financeiro.jsx";
import Kits from "./pages/Kits.jsx";
import Criancas from "./pages/Criancas.jsx";
import Padrinhos from "./pages/Padrinhos.jsx";
import CidadesEdicoes from "./pages/CidadesEdicoes.jsx";
import Instituicoes from "./pages/Instituicoes.jsx";
import Painel from "./pages/Painel.jsx";
import Usuarios from "./pages/Usuarios.jsx";
import RotaProtegida from "./routes/RotaProtegida.jsx";

// Telas ja construidas. O resto do menu ainda mostra "em construcao".
const PRONTAS = {
  "/criancas": <Criancas />,
  "/cartoes": <Cartoes />,
  "/kits": <Kits />,
  "/financeiro": <Financeiro />,
  "/checkin": <Checkin />,
  "/padrinhos": <Padrinhos />,
  "/usuarios": <Usuarios />,
  "/instituicoes": <Instituicoes />,
  "/cidades-edicoes": <CidadesEdicoes />,
};

const SECOES = ROTAS.filter((i) => i.para !== "/painel");

export default function App() {
  return (
    // basename: as rotas sao escritas sem o prefixo, e o /acesso entra aqui.
    <BrowserRouter basename="/acesso">
      <ProvedorSessao>
        <ProvedorNotificacoes>
          <Routes>
            {/* Fora da sessao */}
            <Route path="/entrar" element={<Login />} />
            <Route path="/definir-senha" element={<DefinirSenha />} />
            <Route path="/esqueci-senha" element={<EsqueciSenha />} />

            {/* Dentro da sessao */}
            <Route
              element={
                <RotaProtegida>
                  <LayoutSistema />
                </RotaProtegida>
              }
            >
              {/* /acesso sem sessao cai no login; com sessao, no painel. */}
              <Route index element={<Navigate to="/painel" replace />} />
              <Route path="/painel" element={<Painel />} />

              {SECOES.map((item) => (
                <Route
                  key={item.para}
                  path={item.para}
                  element={
                    <RotaProtegida
                      permissao={item.permissao}
                      permissoes={item.permissoes}
                      apenasAdmin={item.apenasAdmin}
                    >
                      {PRONTAS[item.para] ?? <EmBreve />}
                    </RotaProtegida>
                  }
                />
              ))}

              {/* Fora do menu: chega-se pelo botao da tela de padrinhos, de
                  onde o envio parte. O backend ainda exige a coordenacao
                  geral do evento — ver routers/lembretes.py. */}
              <Route
                path="/padrinhos/envio-de-cartoes"
                element={
                  <RotaProtegida permissao="enviar_cartoes">
                    <EnvioCartoes />
                  </RotaProtegida>
                }
              />

              {/* O passo a passo de apadrinhar como pagina, para o celular. No
                  computador ele abre por cima da ficha do padrinho. */}
              <Route
                path="/padrinhos/:id/apadrinhar"
                element={
                  <RotaProtegida permissao="editar_padrinhos">
                    <Apadrinhar />
                  </RotaProtegida>
                }
              />

              {/* Os enderecos antigos. Compras virou Financeiro, e a tela de
                  pagamentos/comprovantes virou a aba Recebimentos dele — quem
                  tem o link guardado no navegador chega no lugar certo em vez
                  de num 404. */}
              <Route path="/compras" element={<Navigate to="/financeiro" replace />} />
              <Route path="/pagamentos" element={<Navigate to="/financeiro" replace />} />
              <Route path="/comprovantes" element={<Navigate to="/financeiro" replace />} />

              <Route path="*" element={<NaoEncontrada />} />
            </Route>
          </Routes>
        </ProvedorNotificacoes>
      </ProvedorSessao>
    </BrowserRouter>
  );
}
