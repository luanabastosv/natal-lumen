import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import LayoutSistema from "./components/layout/LayoutSistema.jsx";
import { ITENS_MENU } from "./components/layout/menu.js";
import { ProvedorSessao } from "./contexts/SessaoContexto.jsx";
import DefinirSenha from "./pages/DefinirSenha.jsx";
import EmBreve from "./pages/EmBreve.jsx";
import EsqueciSenha from "./pages/EsqueciSenha.jsx";
import Login from "./pages/Login.jsx";
import NaoEncontrada from "./pages/NaoEncontrada.jsx";
import Criancas from "./pages/Criancas.jsx";
import Padrinhos from "./pages/Padrinhos.jsx";
import Pagamentos from "./pages/Pagamentos.jsx";
import CidadesEdicoes from "./pages/CidadesEdicoes.jsx";
import Instituicoes from "./pages/Instituicoes.jsx";
import Painel from "./pages/Painel.jsx";
import Usuarios from "./pages/Usuarios.jsx";
import RotaProtegida from "./routes/RotaProtegida.jsx";

// Telas ja construidas. O resto do menu ainda mostra "em construcao".
const PRONTAS = {
  "/criancas": <Criancas />,
  "/padrinhos": <Padrinhos />,
  "/pagamentos": <Pagamentos />,
  "/usuarios": <Usuarios />,
  "/instituicoes": <Instituicoes />,
  "/cidades-edicoes": <CidadesEdicoes />,
};

const SECOES = ITENS_MENU.filter((i) => i.para !== "/painel");

export default function App() {
  return (
    // basename: as rotas sao escritas sem o prefixo, e o /acesso entra aqui.
    <BrowserRouter basename="/acesso">
      <ProvedorSessao>
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
                  <RotaProtegida permissao={item.permissao} apenasAdmin={item.apenasAdmin}>
                    {PRONTAS[item.para] ?? <EmBreve />}
                  </RotaProtegida>
                }
              />
            ))}

            <Route path="*" element={<NaoEncontrada />} />
          </Route>
        </Routes>
      </ProvedorSessao>
    </BrowserRouter>
  );
}
