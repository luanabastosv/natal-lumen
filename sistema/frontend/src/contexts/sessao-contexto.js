import { createContext } from "react";

/** Em arquivo proprio: um modulo que exporta contexto e componente quebra o
 *  fast refresh do Vite. */
export const SessaoContexto = createContext(null);
