from typing import List

# from data import LIMITS
from datamodel import Order, OrderDepth, TradingState

LIMITS = {
    "EMERALDS": 80,
    "TOMATOES": 80,
}

import json
from typing import Any

from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        # We truncate state.traderData, trader_data, and self.logs to the same max. length to fit the log limit
        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [
                        trade.symbol,
                        trade.price,
                        trade.quantity,
                        trade.buyer,
                        trade.seller,
                        trade.timestamp,
                    ]
                )

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""

        while lo <= hi:
            mid = (lo + hi) // 2

            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."

            encoded_candidate = json.dumps(candidate)

            if len(encoded_candidate) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        return out


logger = Logger()


class Trader:
    STATIC_FAIR_VALUES = {
        "EMERALDS": 10000,
    }
    EMERALDS_POSITION_STEP = 10
    EMERALDS_QUOTE_SIZE = 5

    def run(self, state: TradingState):
        """Create orders for each product at the current timestamp."""

        logger.print("traderData: " + state.traderData)
        logger.print("Observations: " + str(state.observations))

        result = {}
        for product, order_depth in state.order_depths.items():
            orders: List[Order] = []
            position = state.position.get(product, 0)
            limit = LIMITS.get(product, 0)

            best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
            best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None

            logger.print(
                f"{product} position={position} "
                f"best_bid={best_bid} best_ask={best_ask}"
            )

            if product == "TOMATOES":
                sell_capacity = max(0, limit + position)
                if best_bid is not None and sell_capacity > 0:
                    bid_volume = order_depth.buy_orders[best_bid]
                    sell_quantity = min(bid_volume, sell_capacity)
                    logger.print("SELL", str(sell_quantity) + "x", best_bid)
                    orders.append(Order(product, best_bid, -sell_quantity))

                result[product] = orders
                continue

            if product != "EMERALDS":
                result[product] = orders
                continue

            fair_value = self.STATIC_FAIR_VALUES["EMERALDS"]
            position_skew = position // self.EMERALDS_POSITION_STEP
            buy_quote = fair_value - 1 - position_skew
            sell_quote = fair_value + 1 - position_skew

            buy_capacity = max(0, limit - position)
            sell_capacity = max(0, limit + position)

            logger.print(
                f"EMERALDS fair_value={fair_value} buy_quote={buy_quote} "
                f"sell_quote={sell_quote}"
            )

            if best_ask is not None and buy_capacity > 0:
                ask_volume = -order_depth.sell_orders[best_ask]
                if best_ask <= fair_value:
                    buy_quantity = min(ask_volume, buy_capacity)
                    logger.print("BUY", str(buy_quantity) + "x", best_ask)
                    orders.append(Order(product, best_ask, buy_quantity))
                    buy_capacity -= buy_quantity
                elif best_ask > buy_quote and best_bid is not None and buy_quote > best_bid:
                    buy_quantity = min(self.EMERALDS_QUOTE_SIZE, buy_capacity)
                    if buy_quantity > 0:
                        logger.print("BID", str(buy_quantity) + "x", buy_quote)
                        orders.append(Order(product, buy_quote, buy_quantity))

            if best_bid is not None and sell_capacity > 0:
                bid_volume = order_depth.buy_orders[best_bid]
                if best_bid >= fair_value:
                    sell_quantity = min(bid_volume, sell_capacity)
                    logger.print("SELL", str(sell_quantity) + "x", best_bid)
                    orders.append(Order(product, best_bid, -sell_quantity))
                    sell_capacity -= sell_quantity
                elif best_ask is not None and sell_quote < best_ask and sell_quote > best_bid:
                    sell_quantity = min(self.EMERALDS_QUOTE_SIZE, sell_capacity)
                    if sell_quantity > 0:
                        logger.print("ASK", str(sell_quantity) + "x", sell_quote)
                        orders.append(Order(product, sell_quote, -sell_quantity))

        traderData = ""
        conversions = 0

        logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData