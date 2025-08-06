import logging
import time
import queue

class HedgingStrategy:
    def __init__(self, client, symbol, long_price, short_price, hedge_amount_usdt, leverage):
        self.client = client
        self.symbol = symbol
        self.long_price = long_price
        self.short_price = short_price
        self.hedge_amount_usdt = hedge_amount_usdt
        self.leverage = leverage
        self.qty = 0
        self.price_queue = queue.Queue()
        self.long_position_open = False # Internal state tracking flag
        self.long_position_size = 0.0   # Internal size tracking

    def _ws_price_handler(self, message):
        """Callback function to handle incoming WebSocket price updates."""
        try:
            if 'data' in message and 'lastPrice' in message['data']:
                price = float(message['data']['lastPrice'])
                self.price_queue.put(price)
        except Exception as e:
            logging.error(f"Error processing WebSocket message: {e}")

    def initial_setup(self):
        """Sets up WebSocket, leverage, quantity, and initial positions."""
        logging.info("Performing initial setup...")
        
        # Start WebSocket stream in a background thread
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

        # Check and set initial state for short position
        short_pos = self.client.get_position_info(self.symbol, positionIdx=2)
        if short_pos['size'] == 0:
            logging.info("No short position found. Opening initial short position.")
            self.client.open_short_position(self.symbol, str(self.qty), initial_price)
        else:
            logging.info(f"Existing short position of size {short_pos['size']} found.")

        # Check and set initial state for long position
        long_pos = self.client.get_position_info(self.symbol, positionIdx=1)
        if long_pos['size'] > 0:
            self.long_position_open = True
            self.long_position_size = long_pos['size']
        logging.info(f"Initial check: Long position is {'OPEN' if self.long_position_open else 'CLOSED'} with size {self.long_position_size}.")

    def manage_positions(self):
        """The main loop to manage trading logic, driven by the price queue."""
        logging.info("Starting position management...")
        while True:
            try:
                # Block until a new price is received, then drain queue for the latest price
                current_price = self.price_queue.get()
                while not self.price_queue.empty():
                    try:
                        current_price = self.price_queue.get_nowait()
                    except queue.Empty:
                        break

                logging.info(
                    f"Price: {current_price} | "
                    f"Long Target: {self.long_price} | "
                    f"Long Pos Open: {self.long_position_open} | "
                    f"Long Pos Size: {self.long_position_size}"
                )

                # Recalculate quantity for potential new orders
                current_qty = round((self.hedge_amount_usdt * self.leverage) / current_price, 3)

                # --- Trading Logic using internal state ---
                if not self.long_position_open and current_price > self.long_price:
                    if current_qty > 0:
                        logging.info(f"Price above long target. Attempting to open long position with qty {current_qty}.")
                        response = self.client.open_long_position(self.symbol, str(current_qty), current_price)
                        if response and response.get('retCode') == 0:
                            self.long_position_open = True
                            self.long_position_size = current_qty # Store the size
                            logging.info(f"Long position opened successfully. New size: {self.long_position_size}. State updated.")
                    else:
                        logging.warning(f"Calculated quantity is {current_qty}. Skipping order.")

                elif self.long_position_open and current_price <= self.long_price:
                    logging.info(f"Price below long target. Attempting to close long position of size {self.long_position_size}.")
                    response = self.client.close_long_position(self.symbol, str(self.long_position_size), current_price)
                    if response and response.get('retCode') == 0:
                        self.long_position_open = False
                        self.long_position_size = 0.0 # Reset size
                        logging.info("Long position closed successfully. State updated.")

            except queue.Empty:
                time.sleep(1) # Wait if queue is empty
            except Exception as e:
                logging.error(f"An error occurred in the main loop: {e}")
                time.sleep(30)