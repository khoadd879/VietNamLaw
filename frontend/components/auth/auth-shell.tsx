'use client'

import { AuthHero } from './auth-hero'
import { AuthPanel } from './auth-panel'

// AuthShell is a thin wrapper that composes the two-column auth layout.
// It forwards all AuthPanel props directly.
export function AuthShell(props: React.ComponentProps<typeof AuthPanel>) {
  return (
    <div className="auth-layout">
      <AuthHero />
      <div className="auth-panel-wrap">
        <AuthPanel {...props} />
      </div>
    </div>
  )
}