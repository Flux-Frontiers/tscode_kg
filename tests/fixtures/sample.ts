/**
 * sample.ts — fixture for TypeScriptKG extractor tests.
 *
 * Covers: class, interface, type alias, enum, function, arrow function,
 *         import, CALLS, INHERITS, IMPLEMENTS, EXTENDS.
 */

import { EventEmitter } from "events";
import * as path from "path";
import { readFileSync } from "./utils";

// ---------------------------------------------------------------------------
// Enum
// ---------------------------------------------------------------------------

/** HTTP status codes used throughout the application. */
export enum HttpStatus {
  OK = 200,
  NOT_FOUND = 404,
  SERVER_ERROR = 500,
}

// ---------------------------------------------------------------------------
// Type alias
// ---------------------------------------------------------------------------

/** A key-value record with string keys. */
export type StringMap<T> = Record<string, T>;

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

/** Common options shared by all request handlers. */
export interface HandlerOptions {
  timeout: number;
  retries: number;
}

/** Extended options for authenticated handlers. */
export interface AuthHandlerOptions extends HandlerOptions {
  token: string;
  refreshToken?: string;
}

// ---------------------------------------------------------------------------
// Base class
// ---------------------------------------------------------------------------

/** Abstract base for all request handlers. */
export class BaseHandler extends EventEmitter {
  protected options: HandlerOptions;

  constructor(options: HandlerOptions) {
    super();
    this.options = options;
  }

  /** Emit a timeout event. */
  protected emitTimeout(): void {
    this.emit("timeout");
  }
}

// ---------------------------------------------------------------------------
// Concrete class
// ---------------------------------------------------------------------------

/** Handles authenticated API requests with retry logic. */
export class AuthHandler extends BaseHandler implements AuthHandlerOptions {
  token: string;
  refreshToken?: string;
  timeout: number;
  retries: number;

  constructor(opts: AuthHandlerOptions) {
    super(opts);
    this.token = opts.token;
    this.refreshToken = opts.refreshToken;
    this.timeout = opts.timeout;
    this.retries = opts.retries;
  }

  /**
   * Execute a request with the stored auth token.
   *
   * @param url - Target URL
   * @returns Response data or null on failure
   */
  execute(url: string): string | null {
    validateUrl(url);
    return fetchData(url);
  }

  /** Refresh the auth token. */
  refresh(): void {
    this.emitTimeout();
  }
}

// ---------------------------------------------------------------------------
// Module-level functions
// ---------------------------------------------------------------------------

/** Validate that a URL is well-formed. */
export function validateUrl(url: string): boolean {
  return url.startsWith("http://") || url.startsWith("https://");
}

/**
 * Fetch data from a URL (stub).
 *
 * @param url - The URL to fetch
 */
export function fetchData(url: string): string {
  validateUrl(url);
  return "";
}

/** Build a full URL from base and path components. */
export const buildUrl = (base: string, ...parts: string[]): string => {
  return [base, ...parts].join("/");
};

// ---------------------------------------------------------------------------
// Generic utility
// ---------------------------------------------------------------------------

/** Identity function — returns its input unchanged. */
export function identity<T>(value: T): T {
  return value;
}
