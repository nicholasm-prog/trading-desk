import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, getQuote, placeOrder, type BrokerOrder, type OrderSide, type OrderType } from "./api";

const SIDES: { value: OrderSide; label: string }[] = [
  { value: "buy", label: "Buy" },
  { value: "sell", label: "Sell" },
  { value: "sell_short", label: "Sell short" },
  { value: "buy_to_cover", label: "Buy to cover" },
];

const TICKER_PATTERN = /^[A-Za-z][A-Za-z0-9.\-]{0,14}$/;

const fieldClass =
  "mt-1.5 w-full rounded-lg border border-[#d5cdbf] bg-white px-2.5 py-2 text-base text-[#1c1915]";

function isValidTicker(value: string): boolean {
  const ticker = value.trim();
  return ticker.length > 0 && TICKER_PATTERN.test(ticker);
}

function formatQuotePrice(price: string): string {
  const amount = Number(price);
  if (!Number.isFinite(amount)) {
    return price;
  }
  return amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
}

type OrderFormProps = {
  onPlaced: (order: BrokerOrder) => void;
};

export function OrderForm({ onPlaced }: OrderFormProps) {
  const [symbol, setSymbol] = useState("AAPL");
  const [side, setSide] = useState<OrderSide>("buy");
  const [qty, setQty] = useState("1");
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [limitPrice, setLimitPrice] = useState("");
  const [extendedHours, setExtendedHours] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [quotePrice, setQuotePrice] = useState<string | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const quoteRequestId = useRef(0);

  function selectOrderType(next: OrderType) {
    setOrderType(next);
    if (next !== "limit") {
      setExtendedHours(false);
    }
  }

  async function loadQuote(ticker: string) {
    const requestId = ++quoteRequestId.current;
    setQuoteLoading(true);
    setQuoteError(null);
    try {
      const quote = await getQuote(ticker);
      if (requestId !== quoteRequestId.current) {
        return;
      }
      setQuotePrice(quote.price);
    } catch (caught) {
      if (requestId !== quoteRequestId.current) {
        return;
      }
      setQuotePrice(null);
      const message =
        caught instanceof ApiError ? caught.message : "Could not load the market price.";
      setQuoteError(message);
    } finally {
      if (requestId === quoteRequestId.current) {
        setQuoteLoading(false);
      }
    }
  }

  useEffect(() => {
    const ticker = symbol.trim().toUpperCase();
    if (!isValidTicker(symbol)) {
      setQuotePrice(null);
      setQuoteError(null);
      setQuoteLoading(false);
      return;
    }
    const handle = window.setTimeout(() => {
      void loadQuote(ticker);
    }, 400);
    return () => window.clearTimeout(handle);
  }, [symbol]);

  function onSymbolBlur() {
    const ticker = symbol.trim().toUpperCase();
    if (!isValidTicker(symbol)) {
      return;
    }
    void loadQuote(ticker);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    const ticker = symbol.trim().toUpperCase();
    if (!ticker) {
      setError("Enter a symbol.");
      return;
    }
    const quantity = Number(qty);
    if (!qty.trim() || !Number.isFinite(quantity) || quantity <= 0) {
      setError("Quantity must be greater than zero.");
      return;
    }
    if (orderType === "limit" && (!limitPrice.trim() || Number(limitPrice) <= 0)) {
      setError("Enter a limit price greater than zero.");
      return;
    }
    if (extendedHours && orderType !== "limit") {
      setError("Extended hours requires a limit order.");
      return;
    }

    setSubmitting(true);
    try {
      const order = await placeOrder({
        symbol: ticker,
        side,
        qty: qty.trim(),
        order_type: orderType,
        limit_price: orderType === "limit" ? limitPrice.trim() : undefined,
        extended_hours: extendedHours,
      });
      const session = order.extended_hours ? " extended hours" : "";
      setSuccess(
        `Order accepted: ${order.symbol} ${order.side.replaceAll("_", " ")} ${order.qty}${session} (${order.status}, ${order.id}).`,
      );
      onPlaced(order);
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Could not place the order.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  const showQuoteLine = isValidTicker(symbol);

  return (
    <form
      className="mb-4 rounded-xl border border-[#e2d9cb] bg-[#fffdf8] p-4 font-sans"
      onSubmit={onSubmit}
    >
      <div className="mb-3">
        <h2 className="text-xl font-semibold text-[#1c1915]">Order entry</h2>
        <p className="mt-1 text-sm text-[#5c564c]">
          Market and limit orders. Sell short and buy to cover stay on the same form.
        </p>
      </div>
      <div className="mb-3.5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="text-[13px] text-[#1c1915]">
          <div className="flex items-baseline justify-between gap-2">
            <span>Symbol</span>
            {showQuoteLine ? (
              <span className="text-xs text-[#5c564c]" aria-live="polite">
                {quoteLoading ? (
                  "Loading price…"
                ) : quoteError ? (
                  <span className="text-[#8a3b32]">{quoteError}</span>
                ) : quotePrice ? (
                  <>
                    Last{" "}
                    <span className="font-medium text-[#1c1915]">${formatQuotePrice(quotePrice)}</span>
                  </>
                ) : null}
              </span>
            ) : null}
          </div>
          <input
            className={fieldClass}
            name="symbol"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
            onBlur={onSymbolBlur}
            autoComplete="off"
            required
          />
        </div>
        <label className="text-[13px] text-[#1c1915]">
          Side
          <select
            className={fieldClass}
            name="side"
            value={side}
            onChange={(event) => setSide(event.target.value as OrderSide)}
          >
            {SIDES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-[13px] text-[#1c1915]">
          Quantity
          <input
            className={fieldClass}
            name="qty"
            inputMode="decimal"
            value={qty}
            onChange={(event) => setQty(event.target.value)}
            required
          />
        </label>
        <label className="text-[13px] text-[#1c1915]">
          Order type
          <select
            className={fieldClass}
            name="order_type"
            value={orderType}
            onChange={(event) => selectOrderType(event.target.value as OrderType)}
          >
            <option value="market">Market</option>
            <option value="limit">Limit</option>
          </select>
        </label>
        {orderType === "limit" ? (
          <label className="text-[13px] text-[#1c1915]">
            Limit price
            <input
              className={fieldClass}
              name="limit_price"
              inputMode="decimal"
              value={limitPrice}
              onChange={(event) => setLimitPrice(event.target.value)}
              required
            />
          </label>
        ) : null}
        <label className="flex items-end gap-2 pb-2 text-[13px] text-[#1c1915]">
          <input
            className="size-4 accent-[#1c1915] disabled:opacity-40"
            name="extended_hours"
            type="checkbox"
            checked={extendedHours}
            disabled={orderType !== "limit"}
            onChange={(event) => setExtendedHours(event.target.checked)}
          />
          Extended hours
        </label>
      </div>
      <p className="mb-3 text-sm text-[#5c564c]">
        Extended hours is pre-market and after-hours. Alpaca accepts it on day limit orders.
      </p>
      <button
        className="rounded-lg bg-[#1c1915] px-3.5 py-2 text-sm text-[#f7f3ea] disabled:cursor-wait disabled:opacity-60"
        type="submit"
        disabled={submitting}
      >
        {submitting ? "Submitting…" : "Place order"}
      </button>
      {error ? (
        <p className="mt-3 rounded-lg bg-[#fde8e4] px-3 py-2.5 text-sm text-[#6e241c]" role="alert">
          {error}
        </p>
      ) : null}
      {success ? (
        <p className="mt-3 rounded-lg bg-[#e5f4ec] px-3 py-2.5 text-sm text-[#0f5132]" role="status">
          {success}
        </p>
      ) : null}
    </form>
  );
}
