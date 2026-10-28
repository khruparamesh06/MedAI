import { Component, type ErrorInfo, type ReactNode } from 'react'

interface State { error: Error | null }

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled UI error', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="fullpage-message">
        <h1>Something went wrong</h1>
        <p className="muted">An unexpected error occurred while displaying this page. Your data has not been changed.</p>
        <div className="row">
          <button className="btn btn-primary" onClick={() => window.location.reload()}>Reload page</button>
          <a className="btn btn-secondary" href="/">Go to start page</a>
        </div>
      </div>
    )
  }
}
