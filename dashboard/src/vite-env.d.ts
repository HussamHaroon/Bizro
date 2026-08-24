/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Live server base URL (e.g. http://localhost:8000). Unset → mock fixtures. */
  readonly VITE_API_BASE_URL?: string;
  /** Dev proxy target for /api and /webhook (defaults to http://localhost:8000). */
  readonly VITE_API_PROXY_TARGET?: string;
  /** Merchant scope for live mode. */
  readonly VITE_MERCHANT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
