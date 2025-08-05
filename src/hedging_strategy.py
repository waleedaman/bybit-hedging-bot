import logging
import time

class HedgingStrategy:
    def __init__(self, client, symbol, long_price, short_price, hedge_amount_usdt, leverage):
        self.client = client
        self.symbol = symbol
        self.long_price = long_price
        self.short_price = short_price
        self.hedge_amount_usdt = hedge_amount_usdt
        self.leverage = leverage
        self.qty = 0

    def _ws_price_handler(self, message):
        """Callback function to handle incoming WebSocket price updates."""
        logging.info(f"Received WebSocket message: {message}")
        try:
            if 'data' in message and 'lastPrice' in message['data']:
                self.client.last_price = float(message['data']['lastPrice'])
        except Exception as e:
            logging.error(f"Error processing WebSocket message: {e}")

    def initial_setup(self):
        """Sets up WebSocket, leverage, quantity, and initial short position."""
        logging.info("Performing initial setup...")
        
        # Start WebSocket stream
        self.client.start_websocket(self.symbol, self._ws_price_handler)
        logging.info("Waiting for first price update from WebSocket...")
        time.sleep(5) # Give WebSocket time to connect and receive first message

        if 1 <= self.leverage <= 100:
            self.client.set_leverage(self.symbol, self.leverage)
        else:
            logging.info("Leverage is 0, skipping leverage setting.")
        
        initial_price = self.client.get_market_price(self.symbol)
        if not (initial_price and initial_price > 0):
            raise Exception("Could not retrieve initial market price to calculate quantity.")
        
        self.qty = round((self.hedge_amount_usdt * self.leverage) / initial_price, 3)
        logging.info(f"Initial quantity calculated: {self.qty} {self.symbol}")

        short_pos = self.client.get_position_info(self.symbol, positionIdx=2)
        if short_pos['size'] == 0:
            logging.info("No short position found. Opening initial short position.")
            self.client.open_short_position(self.symbol, str(self.qty), initial_price)
        else:
            logging.info(f"Existing short position of size {short_pos['size']} found.")

    def manage_positions(self):
        """The main loop to manage trading logic."""
        logging.info("Starting position management...")
        while True:
            try:
                current_price = self.client.get_market_price(self.symbol)
                if current_price is None:
                    logging.warning("No price data available. Waiting...")
                    time.sleep(10)
                    continue

                long_pos = self.client.get_position_info(self.symbol, positionIdx=1)

                logging.info(
                    f"Price: {current_price} | "
                    f"Long Target: {self.long_price} | "
                    f"Long Pos: {long_pos['size']}"
                )

                self.qty = round((self.hedge_amount_usdt * self.leverage) / current_price, 3)

                if long_pos['size'] == 0 and current_price > self.long_price:
                    self.client.open_long_position(self.symbol, str(self.qty), current_price)
                elif long_pos['size'] > 0 and current_price <= self.long_price:
                    self.client.close_long_position(self.symbol, str(long_pos['size']), current_price)

                time.sleep(10)

            except Exception as e:
                logging.error(f"An error occurred in the main loop: {e}")
                time.sleep(30)