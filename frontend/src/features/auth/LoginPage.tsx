// Inicio de sesión: solo usuario y contraseña, nunca la empresa (RN-3, §7).
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { login } from "../../lib/api/auth";
import { formErrors } from "./formErrors";
import { TextField } from "./TextField";
import { useSessionMutation } from "./useSessionMutation";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const envio = useSessionMutation(login);
  const errores = formErrors(envio.error);

  function enviar(event: FormEvent) {
    event.preventDefault();
    // Sin validaciones propias: el backend decide y la UI refleja (sdd/frontend.md).
    envio.mutate({ username, password });
  }

  return (
    <main>
      <h1>Iniciar sesión</h1>
      <form aria-label="Iniciar sesión" onSubmit={enviar} noValidate>
        <TextField
          label="Usuario"
          name="username"
          value={username}
          onChange={setUsername}
          error={errores.fields.username}
          autoComplete="username"
        />
        <TextField
          label="Contraseña"
          name="password"
          type="password"
          value={password}
          onChange={setPassword}
          error={errores.fields.password}
          autoComplete="current-password"
        />
        {errores.general ? <p role="alert">{errores.general}</p> : null}
        <button type="submit" disabled={envio.isPending}>
          {envio.isPending ? "Entrando…" : "Entrar"}
        </button>
      </form>
      <p>
        ¿Tu empresa aún no está registrada? <Link to="/register">Regístrala</Link>
      </p>
    </main>
  );
}
