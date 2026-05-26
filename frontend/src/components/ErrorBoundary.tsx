import { Component, ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

type Props = { children: ReactNode };
type State = { error: Error | null };

/**
 * Catches render-time crashes in any child page so one bad component can't
 * white-screen the entire app (e.g. a null field in a freshly-created work
 * order). Shows a recoverable fallback that keeps the surrounding chrome.
 *
 * `key` is reset on route change by the caller so navigating away clears the
 * error without a full reload.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: unknown) {
    // Surfaced in the console for debugging; the UI stays usable.
    // eslint-disable-next-line no-console
    console.error("Page crash caught by ErrorBoundary:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="p-8">
          <div className="max-w-lg mx-auto card-pad text-center">
            <div className="w-12 h-12 rounded-full bg-danger-50 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-6 h-6 text-danger-700" />
            </div>
            <h2 className="font-display text-lg font-semibold text-ink-900 mt-4">
              Something went wrong on this page
            </h2>
            <p className="text-sm text-ink-500 mt-1">
              The rest of LODE is still running — use the sidebar to navigate, or reload.
            </p>
            <p className="text-xs text-ink-400 mt-3 font-mono break-all">
              {this.state.error.message}
            </p>
            <button
              onClick={() => this.setState({ error: null })}
              className="btn-primary mt-5 mx-auto"
            >
              <RotateCcw className="w-4 h-4" /> Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
