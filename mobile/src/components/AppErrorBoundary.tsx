import React from 'react';

import { reportError } from '../lib/errorReporter';
import StandaloneNoticeScreen from './StandaloneNoticeScreen';

interface State {
  error: Error | null;
}

/**
 * Root error boundary: an uncaught render error anywhere below shows a friendly
 * recovery screen (and is reported once) instead of a white screen / hard crash.
 * "Try again" remounts the whole subtree via a key bump so poisoned state is
 * discarded. Never shows the raw error message to the user.
 */
export default class AppErrorBoundary extends React.Component<{ children: React.ReactNode }, State & { attempt: number }> {
  state = { error: null as Error | null, attempt: 0 };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    reportError(error, { source: 'error_boundary', componentStack: info.componentStack ?? '' });
  }

  private retry = () => this.setState((s) => ({ error: null, attempt: s.attempt + 1 }));

  render() {
    if (this.state.error) {
      return (
        <StandaloneNoticeScreen
          title="Something went wrong"
          body="FantasyDesk hit an unexpected problem. Your data is safe. Try again, and if it keeps happening, restart the app."
          actionLabel="Try again"
          onAction={this.retry}
        />
      );
    }
    return <React.Fragment key={this.state.attempt}>{this.props.children}</React.Fragment>;
  }
}
