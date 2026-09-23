import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import LayoutSistema from "./components/layout/LayoutSistema.jsx";
import { ITENS_MENU } from "./components/layout/menu.js";
import { ProvedorSessao } from "./contexts/SessaoContexto.jsx";
import DefinirSenha from "./pages/DefinirSenha.jsx";
import EmBreve from "./pages/EmBreve.jsx";
import EsqueciSenha from "./pages/EsqueciSenha.jsx";
import Login from "./pages/Login.jsx";
import NaoEncontrada from "./pages/NaoEncontrada.jsx";
import Painel from "./pages/Painel.jsx";
import RotaProtegida from "./routes/RotaProtegida.jsx";

// As secoes que ainda nao existem: entram nas fases seguintes, uma a uma.
const EM_CONSTRUCAO = ITENS_MENU.filter((i) => i.para !== "/painel");

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

            {EM_CONSTRUCAO.map((item) => (
              <Route
                key={item.para}
                path={item.para}
                element={
                  <RotaProtegida permissao={item.permissao}>
                    <EmBreve />
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
