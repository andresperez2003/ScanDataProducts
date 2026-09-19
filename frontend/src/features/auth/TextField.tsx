import { useId } from "react";

interface TextFieldProps {
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  type?: "text" | "password";
  autoComplete?: string;
}

/** Campo con su etiqueta y el error que devuelve el backend para él. */
export function TextField({
  label,
  name,
  value,
  onChange,
  error,
  type = "text",
  autoComplete,
}: TextFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div className="campo">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        name={name}
        type={type}
        value={value}
        autoComplete={autoComplete}
        aria-invalid={error ? true : false}
        aria-describedby={error ? errorId : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? <p id={errorId}>{error}</p> : null}
    </div>
  );
}
