export type OrderSide = "buy" | "sell" | "sell_short" | "buy_to_cover";
export type OrderType = "market" | "limit";

export type BrokerOrder = {
  id: string;
  symbol: string;
  side: OrderSide;
  qty: string;
  order_type: OrderType;
  status: string;
  broker: string;
  limit_price: string | null;
  filled_qty: string;
  time_in_force: "day" | "gtc";
  extended_hours: boolean;
};

export type BrokerAccount = {
  id: string;
  equity: string;
  cash: string;
  buying_power: string;
  shorting_enabled: boolean;
  broker: string;
};

export type BrokerPosition = {
  symbol: string;
  qty: string;
  avg_entry_price: string;
  side: string;
  broker: string;
  current_price: string | null;
  unrealized_pl: string | null;
};

export type BrokerQuote = {
  symbol: string;
  price: string;
  broker: string;
};

export type PlaceOrderInput = {
  symbol: string;
  side: OrderSide;
  qty: string;
  order_type: OrderType;
  limit_price?: string;
  extended_hours?: boolean;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function endpoint(path: string): string {
  return `${base}${path}`;
}

function detailMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object" || !("detail" in body)) {
    return fallback;
  }
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg: unknown }).msg);
      }
      return String(item);
    });
    const text = messages.filter(Boolean).join(" ");
    if (text) {
      return text;
    }
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(endpoint(path), {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      "Could not reach the trading API. Start the backend on port 8000.",
      0,
    );
  }
  const text = await response.text();
  const body: unknown = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new ApiError(detailMessage(body, response.statusText || "Request failed"), response.status);
  }
  return body as T;
}

export function placeOrder(input: PlaceOrderInput): Promise<BrokerOrder> {
  const payload: Record<string, string | boolean> = {
    symbol: input.symbol,
    side: input.side,
    qty: input.qty,
    order_type: input.order_type,
    time_in_force: "day",
    extended_hours: input.extended_hours === true,
  };
  if (input.order_type === "limit" && input.limit_price) {
    payload.limit_price = input.limit_price;
  }
  return request<BrokerOrder>("/api/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listOrders(): Promise<BrokerOrder[]> {
  return request<BrokerOrder[]>("/api/orders?status=open");
}

export function listOrderHistory(): Promise<BrokerOrder[]> {
  return request<BrokerOrder[]>("/api/orders?status=closed");
}

export function cancelOrder(orderId: string): Promise<BrokerOrder> {
  return request<BrokerOrder>(`/api/orders/${encodeURIComponent(orderId)}`, {
    method: "DELETE",
  });
}

export function getAccount(): Promise<BrokerAccount> {
  return request<BrokerAccount>("/api/account");
}

export function listPositions(): Promise<BrokerPosition[]> {
  return request<BrokerPosition[]>("/api/positions");
}

export function getQuote(symbol: string): Promise<BrokerQuote> {
  const ticker = symbol.trim().toUpperCase();
  return request<BrokerQuote>(`/api/quotes/${encodeURIComponent(ticker)}`);
}
