import type {
  AskRequest,
  AskResponse,
  GraphResponse,
  LinkQuoteRequest,
  ProductDetail,
  QuoteRequest,
  RequestAck,
  SearchResponse,
  Setup,
  SetupsResponse,
  SwapResponse,
} from "./types";
import { RigError, type ApiErrorBody } from "./types";
import * as mock from "../mock/index";

export type RigClientOptions = {
  apiBase: string;
  key: string;
  fetchImpl?: typeof fetch;
};

export class RigClient {
  private readonly apiBase: string;
  private readonly key: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: RigClientOptions) {
    this.apiBase = options.apiBase.replace(/\/$/, "");
    this.key = options.key;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  get usesMock(): boolean {
    return this.apiBase === "mock";
  }

  search(q: string, limit = 12): Promise<SearchResponse> {
    if (this.usesMock) return Promise.resolve(mock.search(q, limit));
    const params = new URLSearchParams({ q, limit: String(limit) });
    return this.request<SearchResponse>(`/v1/rig/search?${params.toString()}`);
  }

  product(id: string): Promise<ProductDetail> {
    if (this.usesMock) return Promise.resolve(mock.product(id));
    return this.request<ProductDetail>(`/v1/rig/products/${encodeURIComponent(id)}`);
  }

  setups(productId: string): Promise<SetupsResponse> {
    if (this.usesMock) return Promise.resolve(mock.setups(productId));
    return this.request<SetupsResponse>("/v1/rig/setups", {
      method: "POST",
      body: JSON.stringify({ product_id: productId }),
    });
  }

  swap(setup: Setup, role: string): Promise<SwapResponse> {
    if (this.usesMock) return Promise.resolve(mock.swap(setup, role));
    return this.request<SwapResponse>("/v1/rig/swap", {
      method: "POST",
      body: JSON.stringify({ setup: contractSetup(setup), role }),
    });
  }

  graph(productId: string): Promise<GraphResponse> {
    if (this.usesMock) return Promise.resolve(mock.graph(productId));
    return this.request<GraphResponse>(`/v1/rig/graph/${encodeURIComponent(productId)}`);
  }

  ask(body: AskRequest): Promise<AskResponse> {
    if (this.usesMock) return Promise.resolve(mock.ask(body));
    return this.request<AskResponse>("/v1/rig/ask", {
      method: "POST",
      body: JSON.stringify({
        product_id: body.product_id,
        ...(body.setup ? { setup: contractSetup(body.setup) } : {}),
        question: body.question,
      }),
    });
  }

  linkQuote(body: LinkQuoteRequest): Promise<RequestAck> {
    if (this.usesMock) return Promise.resolve(mock.linkQuote(body));
    return this.request<RequestAck>("/v1/rig/link-quote", {
      method: "POST",
      body: JSON.stringify({ url: body.url, note: body.note }),
    });
  }

  quote(body: QuoteRequest): Promise<RequestAck> {
    if (this.usesMock) return Promise.resolve(mock.quote(body));
    const payload: QuoteRequest = {
      contact: body.contact,
      ...(body.setup ? { setup: contractSetup(body.setup) } : {}),
      ...(body.product_id ? { product_id: body.product_id } : {}),
    };
    return this.request<RequestAck>("/v1/rig/quote", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    headers.set("X-Rig-Key", this.key);
    if (init.body) headers.set("Content-Type", "application/json");
    const response = await this.fetchImpl(`${this.apiBase}${path}`, { ...init, headers });
    if (!response.ok) {
      let parsed: ApiErrorBody | null = null;
      try {
        parsed = (await response.json()) as ApiErrorBody;
      } catch {
        // The body was not JSON.
      }
      if (parsed?.error?.code) {
        throw new RigError(parsed.error.code, parsed.error.message, response.status);
      }
      throw new RigError("http_error", "The request failed.", response.status);
    }
    return (await response.json()) as T;
  }
}

function contractSetup(setup: Setup): Setup {
  return {
    tier: setup.tier,
    label: setup.label,
    parts: setup.parts,
    total: setup.total,
    why: setup.why,
  };
}
