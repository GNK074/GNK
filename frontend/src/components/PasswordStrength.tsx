export function PasswordStrength({ value }: { value: string }) {
  const score = [
    value.length >= 12,
    /[a-z]/.test(value) && /[A-Z]/.test(value),
    /[0-9]/.test(value),
    /[^a-zA-Z0-9]/.test(value),
  ].filter(Boolean).length;
  return (
    <div className="password-strength" aria-live="polite">
      <div>
        {[1, 2, 3, 4].map((n) => (
          <i key={n} className={score >= n && value ? "filled" : ""} />
        ))}
      </div>
      <small>
        {!value
          ? "Use 12+ characters, uppercase, lowercase, a number and a symbol."
          : score === 4
            ? "Strong · meets password requirements"
            : "Add 12+ characters, upper/lowercase, a number and a symbol."}
      </small>
    </div>
  );
}
