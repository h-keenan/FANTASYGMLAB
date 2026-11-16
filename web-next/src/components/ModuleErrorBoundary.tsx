"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

import { ErrorState } from "@/components/ErrorState";
import { trackClientError } from "@/lib/analytics";
import { reportError } from "@/lib/errorReporter";

/**
 * Per-module error boundary: a render error in one module shows a compact
 * inline "Couldn't load this · Retry" card in that module's place instead of
 * sending the whole route to the "Something went wrong" screen. The error is
 * reported through the shared reporter. Retry remounts the subtree (key bump)
 * so poisoned state is dropped. Mirrors mobile/src/components/ModuleErrorBoundary.tsx.
 * `CompactModule` wraps its body in one; wrap any other risky section directly.
 */
export class ModuleErrorBoundary extends Component<{ children: ReactNode; name?: string }, { error: Error | null; attempt: number }> {
  state = { error: null as Error | null, attempt: 0 };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    trackClientError("application_error", error);
    reportError(error, { source: "module_error_boundary", module: this.props.name ?? "", componentStack: info.componentStack ?? "" });
  }

  private retry = () => this.setState((s) => ({ error: null, attempt: s.attempt + 1 }));

  render() {
    if (this.state.error) {
      return <ErrorState compact message="Couldn't load this" onRetry={this.retry} />;
    }
    return (
      <div key={this.state.attempt} className="contents">
        {this.props.children}
      </div>
    );
  }
}
