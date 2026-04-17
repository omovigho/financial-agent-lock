import { Link } from 'react-router-dom'

const trustSignals = ['Auth0 Token Vault', 'Real-Time Policy Controls', 'AI Security Intelligence']

export default function WelcomePage() {
  return (
    <div className="welcome-shell">
      <div className="welcome-aurora welcome-aurora-one" aria-hidden="true" />
      <div className="welcome-aurora welcome-aurora-two" aria-hidden="true" />
      <div className="welcome-aurora welcome-aurora-three" aria-hidden="true" />
      <div className="welcome-grid" aria-hidden="true" />

      <main className="welcome-main">
        <section className="welcome-panel">
          <p className="welcome-kicker welcome-fade-up">Enterprise-Grade Financial AI Platform</p>

          <h1 className="welcome-title welcome-fade-up welcome-delay-1">
            Welcome to Financial Agent Lock
          </h1>

          <p className="welcome-subtitle welcome-fade-up welcome-delay-2">
            A secure financial agent that keeps your system safe using Auth0 Token Vault.
          </p>

          <div className="welcome-fade-up welcome-delay-3">
            <Link to="/login" className="welcome-login-btn">
              Login
            </Link>
          </div>

          <ul className="welcome-signals welcome-fade-up welcome-delay-4" aria-label="Security trust signals">
            {trustSignals.map((signal) => (
              <li key={signal} className="welcome-signal-item">
                {signal}
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  )
}
