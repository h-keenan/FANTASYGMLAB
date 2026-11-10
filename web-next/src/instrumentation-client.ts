// Next.js client instrumentation: runs before the app hydrates, so global
// errors / unhandled rejections are captured. No-op without NEXT_PUBLIC_SENTRY_DSN.
import { initErrorReporter } from "@/lib/errorReporter";

void initErrorReporter();
