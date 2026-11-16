import React from 'react';

import ErrorState from './ErrorState';
import { reportError } from '../lib/errorReporter';

/**
 * Per-module error boundary: a render error in one module shows a compact
 * inline "Couldn't load this" + Retry card in its place instead of taking the
 * whole screen down to the root recovery screen. Reported through the shared
 * reporter; Retry remounts the subtree. Mirrors web-next's ModuleErrorBoundary.
 * `CompactModule` wraps its body in one; wrap any other risky section directly.
 */
export default class ModuleErrorBoundary extends React.Component<
  { children: React.ReactNode; name?: string },
  { error: Error | null; attempt: number }
> {
  state = { error: null as Error | null, attempt: 0 };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    reportError(error, { source: 'module_error_boundary', module: this.props.name ?? '', componentStack: info.componentStack ?? '' });
  }

  private retry = () => this.setState((s) => ({ error: null, attempt: s.attempt + 1 }));

  render() {
    if (this.state.error) {
      return <ErrorState compact onRetry={this.retry} />;
    }
    return <React.Fragment key={this.state.attempt}>{this.props.children}</React.Fragment>;
  }
}
