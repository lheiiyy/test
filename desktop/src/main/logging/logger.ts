/**
 * Centralized logging for the main process. See docs/ARCHITECTURE.md "Logging".
 *
 * Rules (non-negotiable, enforced by convention + redactField below):
 *  - Never log auth tokens, pairing tokens/codes, device file contents, or
 *    anything that looks like a credential.
 *  - Every log line is structured (scope + message + optional data) so
 *    connection-failure troubleshooting doesn't require grepping free text.
 */

export type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

export interface LogEntry {
  level: LogLevel;
  scope: string;
  message: string;
  timestamp: string;
  data?: Record<string, unknown>;
}

export type LogSink = (entry: LogEntry) => void;

const LEVEL_ORDER: Record<LogLevel, number> = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,
};

/** Field names that must never appear in a log line's data payload. */
const SENSITIVE_FIELD_NAMES = new Set([
  'token',
  'pairingcode',
  'password',
  'secret',
  'authorization',
  'credential',
]);

function redact(data: Record<string, unknown> | undefined): Record<string, unknown> | undefined {
  if (!data) return data;
  const clean: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    clean[key] = SENSITIVE_FIELD_NAMES.has(key.toLowerCase()) ? '[redacted]' : value;
  }
  return clean;
}

export class Logger {
  private minLevel: LogLevel;
  private sinks: LogSink[];

  constructor(options: { minLevel?: LogLevel; sinks?: LogSink[] } = {}) {
    this.minLevel = options.minLevel ?? 'INFO';
    this.sinks = options.sinks ?? [consoleSink];
  }

  private write(level: LogLevel, scope: string, message: string, data?: Record<string, unknown>) {
    if (LEVEL_ORDER[level] < LEVEL_ORDER[this.minLevel]) return;
    const entry: LogEntry = {
      level,
      scope,
      message,
      timestamp: new Date().toISOString(),
      data: redact(data),
    };
    for (const sink of this.sinks) sink(entry);
  }

  debug(scope: string, message: string, data?: Record<string, unknown>) {
    this.write('DEBUG', scope, message, data);
  }
  info(scope: string, message: string, data?: Record<string, unknown>) {
    this.write('INFO', scope, message, data);
  }
  warn(scope: string, message: string, data?: Record<string, unknown>) {
    this.write('WARN', scope, message, data);
  }
  error(scope: string, message: string, data?: Record<string, unknown>) {
    this.write('ERROR', scope, message, data);
  }

  child(scope: string): ScopedLogger {
    return {
      debug: (message, data) => this.debug(scope, message, data),
      info: (message, data) => this.info(scope, message, data),
      warn: (message, data) => this.warn(scope, message, data),
      error: (message, data) => this.error(scope, message, data),
    };
  }
}

export interface ScopedLogger {
  debug(message: string, data?: Record<string, unknown>): void;
  info(message: string, data?: Record<string, unknown>): void;
  warn(message: string, data?: Record<string, unknown>): void;
  error(message: string, data?: Record<string, unknown>): void;
}

function consoleSink(entry: LogEntry): void {
  const line = `[${entry.timestamp}] ${entry.level} (${entry.scope}) ${entry.message}`;
  const payload = entry.data ? [line, entry.data] : [line];
  switch (entry.level) {
    case 'ERROR':
      console.error(...payload);
      break;
    case 'WARN':
      console.warn(...payload);
      break;
    default:
      // eslint-disable-next-line no-console -- this is the one sanctioned console sink
      console.log(...payload);
  }
}

export const rootLogger = new Logger({
  minLevel: process.env.DROIDBRIDGE_LOG_LEVEL as LogLevel | undefined,
});
