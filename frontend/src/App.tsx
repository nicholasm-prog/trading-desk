import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  cancelOrder,
  getAccount,
  listOrderHistory,
  listOrders,
  listPositions,
  type BrokerAccount,
  type BrokerOrder,
  type BrokerPosition,
} from "./api";
import { OrderForm } from "./OrderForm";

function sideLabel(side: string): string {
  return side.replaceAll("_", " ");
}

export function App() {
  const [orders, setOrders] = useState<BrokerOrder[]>([]);
  const [ordersError, setOrdersError] = useState<string | null>(null);
  const [history, setHistory] = useState<BrokerOrder[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [account, setAccount] = useState<BrokerAccount | null>(null);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [positions, setPositions] = useState<BrokerPosition[]>([]);
  const [positionsError, setPositionsError] = useState<string | null>(null);
  const [cancelingId, setCancelingId] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [orderResult, historyResult, accountResult, positionResult] = await Promise.allSettled([
      listOrders(),
      listOrderHistory(),
      getAccount(),
      listPositions(),
    ]);

    if (orderResult.status === "fulfilled") {
      setOrders(orderResult.value);
      setOrdersError(null);
    } else {
      setOrdersError(messageFrom(orderResult.reason));
    }

    if (historyResult.status === "fulfilled") {
      setHistory(historyResult.value);
      setHistoryError(null);
    } else {
      setHistoryError(messageFrom(historyResult.reason));
    }

    if (accountResult.status === "fulfilled") {
      setAccount(accountResult.value);
      setAccountError(null);
    } else {
      setAccount(null);
      setAccountError(messageFrom(accountResult.reason));
    }

    if (positionResult.status === "fulfilled") {
      setPositions(positionResult.value);
      setPositionsError(null);
    } else {
      setPositionsError(messageFrom(positionResult.reason));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onCancel(orderId: string) {
    setCancelError(null);
    setCancelingId(orderId);
    try {
      await cancelOrder(orderId);
      await refresh();
    } catch (caught) {
      setCancelError(messageFrom(caught));
    } finally {
      setCancelingId(null);
    }
  }

  return (
    <main>
      <header className="page-header">
        <div>
          <p className="eyebrow">Paper trading</p>
          <h1>Trading desk</h1>
        </div>
        <p className="lede">
          Orders go through a broker interface. Alpaca paper trading is the live adapter.
          Sell short and buy to cover are on this form; TradeZero can take over native short sales later.
        </p>
      </header>

      <OrderForm
        onPlaced={() => {
          void refresh();
        }}
      />

      <section className="card">
        <div className="card-heading row">
          <h2>Account</h2>
        </div>
        {accountError ? (
          <p className="banner error" role="alert">
            {accountError}
          </p>
        ) : null}
        {account ? (
          <dl className="stats">
            <div>
              <dt>Broker</dt>
              <dd>{account.broker}</dd>
            </div>
            <div>
              <dt>Equity</dt>
              <dd>{account.equity}</dd>
            </div>
            <div>
              <dt>Cash</dt>
              <dd>{account.cash}</dd>
            </div>
            <div>
              <dt>Buying power</dt>
              <dd>{account.buying_power}</dd>
            </div>
            <div>
              <dt>Shorting</dt>
              <dd>{account.shorting_enabled ? "Enabled" : "Disabled"}</dd>
            </div>
          </dl>
        ) : null}
      </section>

      <section className="card">
        <div className="card-heading row">
          <h2>Open orders</h2>
          <button type="button" className="ghost" onClick={() => void refresh()}>
            Refresh
          </button>
        </div>
        {ordersError ? (
          <p className="banner error" role="alert">
            {ordersError}
          </p>
        ) : null}
        {cancelError ? (
          <p className="banner error" role="alert">
            {cancelError}
          </p>
        ) : null}
        {orders.length === 0 && !ordersError ? <p className="muted">No open orders.</p> : null}
        {orders.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Type</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td>{order.symbol}</td>
                  <td>{sideLabel(order.side)}</td>
                  <td>{order.qty}</td>
                  <td>
                    {order.order_type}
                    {order.extended_hours ? " · extended" : ""}
                  </td>
                  <td>{order.status}</td>
                  <td>
                    <button
                      type="button"
                      className="ghost"
                      disabled={cancelingId === order.id}
                      onClick={() => void onCancel(order.id)}
                    >
                      {cancelingId === order.id ? "Canceling…" : "Cancel"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>

      <section className="card">
        <div className="card-heading row">
          <h2>Recent order history</h2>
          <button type="button" className="ghost" onClick={() => void refresh()}>
            Refresh
          </button>
        </div>
        <p className="muted">Filled and canceled orders from the broker (most recent first).</p>
        {historyError ? (
          <p className="banner error" role="alert">
            {historyError}
          </p>
        ) : null}
        {history.length === 0 && !historyError ? <p className="muted">No recent closed orders.</p> : null}
        {history.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Filled</th>
                <th>Type</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {history.map((order) => (
                <tr key={order.id}>
                  <td>{order.symbol}</td>
                  <td>{sideLabel(order.side)}</td>
                  <td>{order.qty}</td>
                  <td>{order.filled_qty}</td>
                  <td>
                    {order.order_type}
                    {order.extended_hours ? " · extended" : ""}
                  </td>
                  <td>{order.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>

      <section className="card">
        <div className="card-heading">
          <h2>Positions</h2>
          <p>A negative quantity is a short.</p>
        </div>
        {positionsError ? (
          <p className="banner error" role="alert">
            {positionsError}
          </p>
        ) : null}
        {positions.length === 0 && !positionsError ? <p className="muted">No open positions.</p> : null}
        {positions.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Avg price</th>
                <th>Current</th>
                <th>Unrealized P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => (
                <tr key={position.symbol}>
                  <td>{position.symbol}</td>
                  <td>{position.side}</td>
                  <td>{position.qty}</td>
                  <td>{position.avg_entry_price}</td>
                  <td>{position.current_price ?? "—"}</td>
                  <td>{position.unrealized_pl ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>
    </main>
  );
}

function messageFrom(reason: unknown): string {
  if (reason instanceof ApiError) {
    return reason.message;
  }
  return "Request failed.";
}
