import { Component, type ReactNode } from 'react'

interface State {
  error: Error | null
}

/**
 * A mistake in one screen stays in that screen.
 *
 * Without this, React takes the whole page down on an error while drawing, and what is left
 * is a white window with nothing to click. Here the rest of the app stays, and the screen
 * that broke says what happened and how to get back.
 */
export default class Mishap extends Component<{ children: ReactNode; onReset?: () => void }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error) {
    console.error(error)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children
    return (
      <div className="error mishap" role="alert">
        <strong>Dit scherm liep vast.</strong> Sluit het zwarte venster en start de app opnieuw als dit na
        een update gebeurt. Blijft het, stuur dan een melding via het gereedheidspaneel.
        <div className="tc">{error.message}</div>
        <button className="small" onClick={() => {
          this.setState({ error: null })
          this.props.onReset?.()
        }}>
          Terug
        </button>
      </div>
    )
  }
}
