// Registro de empresa y primer usuario (HU-1): empresa, usuario y contraseña.
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { register } from "../../lib/api/auth";
import { formErrors } from "./formErrors";
import { TextField } from "./TextField";
import { useSessionMutation } from "./useSessionMutation";

// Los 409 no traen `fields`: cada código señala su campo (plan §5).
const CAMPO_DEL_CONFLICTO = {
  COMPANY_NAME_TAKEN: "company_name",
  USERNAME_TAKEN: "username",
};

export function RegisterPage() {
  const [companyName, setCompanyName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const envio = useSessionMutation(register);
  const errores = formErrors(envio.error, CAMPO_DEL_CONFLICTO);

  function enviar(event: FormEvent) {
    event.preventDefault();
    // Sin validaciones propias: el backend decide y la UI refleja (sdd/frontend.md).
    envio.mutate({ company_name: companyName, username, password });
  }

  return (
    <main>
      <h1>Registrar empresa</h1>
      <form aria-label="Registrar empresa" onSubmit={enviar} noValidate>
        <TextField
          label="Empresa"
          name="company_name"
          value={companyName}
          onChange={setCompanyName}
          error={errores.fields.company_name}
          autoComplete="organization"
        />
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
          autoComplete="new-password"
        />
        {errores.general ? <p role="alert">{errores.general}</p> : null}
        <button type="submit" disabled={envio.isPending}>
          {envio.isPending ? "Registrando…" : "Registrar"}
        </button>
      </form>
      <p>
        ¿Ya tienes cuenta? <Link to="/login">Inicia sesión</Link>
      </p>
    </main>
  );
}
