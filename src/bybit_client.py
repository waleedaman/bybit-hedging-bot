import logging
from pybit.unified_trading import HTTP

class BybitClient:
    def __init__(self, api_key, api_secret, testnet=False):
        self.client = HTTP(demo=True, testnet=testnet, api_key=api_key, api_secret=api_secret, recv_window=10000)
        self.is_leverage = False
        
    def set_leverage(self, symbol, leverage):
        try:
            response = self.client.set_leverage(
                category='linear',
                symbol=symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            )
            # Bybit returns retCode 0 even if leverage is not modified.
            # We check retMsg to confirm the action.
            if response.get('retCode') == 0:
                logging.info(f"Leverage set/confirmed for {symbol}: {response.get('retMsg')}")
                self.is_leverage = True
                return True
            else:
                logging.error(f"Failed to set leverage for {symbol}: {response.get('retMsg', 'Unknown error')}")
                return False
        except Exception as e:
            # If the error is that leverage was not modified, it's not a critical failure.
            if "leverage not modified" in str(e) or "110043" in str(e):
                logging.info(f"Leverage for {symbol} is already set to the desired value.")
                self.is_leverage = True
                return True
            else:
                logging.error(f"Exception when setting leverage for {symbol}: {e}")
                return False

    def open_long_position(self, symbol, qty, price):
        logging.info(f"Placing LONG order for {qty} {symbol} at price {price}.")
        return self._place_order(symbol, 'Buy', qty, 1, price)

    def close_long_position(self, symbol, qty, price):
        logging.info(f"CLOSING LONG order for {qty} {symbol} at price {price}.")
        return self._place_order(symbol, 'Sell', qty, 1, price)

    def open_short_position(self, symbol, qty, price):
        logging.info(f"Placing SHORT order for {qty} {symbol} at price {price}.")
        return self._place_order(symbol, 'Sell', qty, 2, price)

    def close_short_position(self, symbol, qty, price):
        logging.info(f"CLOSING SHORT order for {qty} {symbol} at price {price}.")
        return self._place_order(symbol, 'Buy', qty, 2, price)

    def _place_order(self, symbol, side, qty, positionIdx, price):
        try:
            response = self.client.place_order(
                category='linear',
                symbol=symbol,
                side=side,
                order_type='Market',
                qty=qty,
                price=str(price),
                isLeverage=1 if self.is_leverage else 0,
                positionIdx=positionIdx
            )
            logging.info(f"Order response: {response}")
            return response
        except Exception as e:
            logging.error(f"Error placing order for {symbol}: {e}")
            return None

    def get_market_price(self, symbol):
        try:
            response = self.client.get_tickers(category="linear", symbol=symbol)
            if response.get('retCode') == 0 and response.get('result', {}).get('list'):
                return float(response['result']['list'][0]['lastPrice'])
            else:
                logging.error(f"Error getting market price from Bybit: {response.get('retMsg', 'Unknown error')}")
                return None
        except Exception as e:
            logging.error(f"Exception when retrieving market price for {symbol}: {e}")
            return None

    def get_position_info(self, symbol, positionIdx):
        try:
            response = self.client.get_positions(category="linear", symbol=symbol)
            if response.get('retCode') == 0 and response.get('result', {}).get('list'):
                for position in response['result']['list']:
                    if position.get('positionIdx') == positionIdx:
                        return {'size': float(position.get('size', 0)), 'side': position.get('side')}
            return {'size': 0, 'side': 'None'}
        except Exception as e:
            logging.error(f"Exception when retrieving position for {symbol}: {e}")
            return {'size': 0, 'side': 'None'}