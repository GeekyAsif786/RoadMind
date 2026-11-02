import { LogIn, RefreshCw, TrafficCone } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../services/api.js";

export function loginErrorMessage(error) {
  if (error?.isNetworkError) {
    return `Cannot reach the RoadMind backend at ${api.baseUrl}. Check that the backend is running and try again.`;
  }
  if (error?.status === 401) return "Incorrect username/email or password.";
  if (error?.status === 422) return "Enter your username or email and password.";
  if (error?.status === 429) return "Too many sign-in attempts. Wait a minute and try again.";
  if (error?.status >= 500) return "The backend could not complete sign-in. Try again shortly.";
  return error?.message || "Sign-in failed.";
}

export default function LoginScreen({ onLogin, message, onRetry, retrying = false }) {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // A new message from the session check replaces any earlier sign-in error,
  // so only one alert is ever shown.
  useEffect(() => {
    setError(null);
  }, [message]);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onLogin(identifier.trim(), password);
    } catch (loginError) {
      setPassword("");
      setError(loginErrorMessage(loginError));
      setSubmitting(false);
    }
  }

  const alert = error ? { type: "error", message: error } : message;

  return (
    <main className="auth-shell">
      <section className="control-panel login-panel" aria-labelledby="login-title">
        <div className="panel-heading">
          <TrafficCone size={20} aria-hidden="true" />
          <h2 id="login-title">Sign in to RoadMind</h2>
        </div>
        <p className="login-subtitle">Smart Traffic Optimization</p>

        {alert && (
          <div className={`notice inline ${alert.type}`} role={alert.type === "error" ? "alert" : "status"}>
            {alert.message}
          </div>
        )}

        <form className="compact-form" onSubmit={handleSubmit}>
          <label>
            Username or email
            <input
              name="username"
              autoComplete="username"
              autoFocus
              required
              maxLength={255}
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              maxLength={128}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button className="primary-button" type="submit" disabled={submitting}>
            <LogIn size={18} aria-hidden="true" />
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        {onRetry && (
          <button className="login-retry" type="button" onClick={onRetry} disabled={submitting || retrying}>
            <RefreshCw size={16} aria-hidden="true" />
            {retrying ? "Retrying…" : "Retry"}
          </button>
        )}
      </section>
    </main>
  );
}
