export default function Mensagem({ tipo = "erro", children }) {
  if (!children) return null;

  return (
    <div
      className={`mensagem mensagem--${tipo}`}
      role={tipo === "erro" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}
