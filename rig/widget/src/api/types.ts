/** Prices are one indicative amount. Never a cost, duty, VAT, or margin. */
export type Price = {
  amount: number;
  currency: string;
  indicative: true;
};

export type Product = {
  id: string;
  name: string;
  brand: string;
  category: string;
  image: string;
  price: Price;
  attributes: Record<string, unknown>;
};

export type SearchResponse = {
  results: Product[];
};

export type ProductDetail = Product & {
  categories_that_fit: { category: string; count: number }[];
};

export type SetupPart = {
  role: string;
  product: Product;
};

/**
 * `badge` is optional display text (for example "Most chosen").
 * The contract's required fields are tier, label, parts, total, and why.
 * `why` may use line breaks: fit line, then a short explanation, then a longer note.
 */
export type Setup = {
  tier: string;
  label: string;
  parts: SetupPart[];
  total: Price;
  why: string;
  badge?: string;
};

export type SetupsResponse = {
  setups: Setup[];
};

export type SwapResponse = {
  options: Product[];
};

export type GraphBranch = {
  category: string;
  count: number;
  products: Product[];
};

export type GraphResponse = {
  centre: Product;
  branches: GraphBranch[];
};

export type AskRequest = {
  product_id: string;
  setup?: Setup;
  question: string;
};

export type AskResponse = {
  answer: string;
  cites: string[];
};

export type LinkQuoteRequest = {
  url: string;
  note: string;
};

export type Contact = {
  name: string;
  email: string;
  phone?: string;
};

export type QuoteRequest = {
  setup?: Setup;
  product_id?: string;
  contact: Contact;
};

export type RequestAck = {
  request_id: string;
};

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
  };
};

export class RigError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "RigError";
    this.code = code;
    this.status = status;
  }
}
