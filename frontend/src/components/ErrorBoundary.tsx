import { Component, type ReactNode } from "react";

/**
 * Last line of defence. Without this, one unexpected null in a render turns the
 * whole page white, which is a poor thing for a stranger to run into. A crash
 * now shows something readable and offers a reload.
 */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("Unhandled UI error:", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-6 text-center">
        <h1 className="text-2xl font-bold">Something broke on this page</h1>
        <p className="mt-2 text-fog">
          Sorry about that. Reloading usually fixes it — if it doesn't, the console has the details.
        </p>
        <button onClick={() => window.location.reload()}
          className="mt-6 rounded-lg bg-amber px-5 py-2.5 font-semibold text-ink">Reload</button>
      </div>
    );
  }
}
