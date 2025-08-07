import logging
import time
import queue

class HedgingStrategy:
    def __init__(self, client, symbol, long_price, short_price, hedge_amount_usdt, leverage, mode):
        self.client = client
        self.symbol = symbol
        self.long_price = long_price
        self.short_price = short_price
        self.hedge_amount_usdt = hedge_amount_usdt
        self.leverage = leverage
        self.mode = mode
        self.qty = 0
        self.price_queue = queue.Queue()
        self.managed_position_open = False # Generic flag for the position being managed
        self.managed_position_size = 0.0   # Generic size for the managed position

    def _ws_price_handler(self, message):
        """Callback function to handle incoming WebSocket price updates."""
        try:
            if 'data' in message and 'lastPrice' in message['data']:
                price = float(message['data']['lastPrice'])
                self.price_queue.put(price)
        except Exception as e:
            logging.error(f"Error processing WebSocket message: {e}")

    def initial_setup(self):
        """Sets up WebSocket, leverage, quantity, and initial positions based on mode."""
        logging.info(f"Performing initial setup for mode: {'Manage Long' if self.mode == 'L' else 'Manage Short'}")
        
        self.client.start_websocket(self.symbol, self._ws_price_handler)
        logging.info("Waiting for first price update from WebSocket...")
        time.sleep(5)

        if 1 <= self.leverage <= 100:
            self.client.set_leverage(self.symbol, self.leverage)
        else:
            logging.info("Leverage is 0, skipping leverage setting.")
        
        initial_price = self.client.get_market_price(self.symbol)
        if not (initial_price and initial_price > 0):
            raise Exception("Could not retrieve initial market price to calculate quantity.")
        
        self.qty = round((self.hedge_amount_usdt * self.leverage) / initial_price, 3)
        logging.info(f"Initial quantity calculated: {self.qty} {self.symbol}")

        if self.mode == 'L':
            # --- Manage Long Mode: Open Short Hedge ---
            hedge_pos = self.client.get_position_info(self.symbol, positionIdx=2) # Short position
            if hedge_pos['size'] == 0:
                logging.info("No short hedge found. Opening initial short position.")
                self.client.open_short_position(self.symbol, str(self.qty), initial_price)
            else:
                logging.info(f"Existing short hedge of size {hedge_pos['size']} found.")
            
            managed_pos = self.client.get_position_info(self.symbol, positionIdx=1) # Long position
            self.managed_position_open = managed_pos['size'] > 0
            self.managed_position_size = managed_pos['size']
            logging.info(f"Initial check: Managed Long position is {'OPEN' if self.managed_position_open else 'CLOSED'} with size {self.managed_position_size}.")

        elif self.mode == 'S':
            # --- Manage Short Mode: Open Long Hedge ---
            hedge_pos = self.client.get_position_info(self.symbol, positionIdx=1) # Long position
            if hedge_pos['size'] == 0:
                logging.info("No long hedge found. Opening initial long position.")
                self.client.open_long_position(self.symbol, str(self.qty), initial_price)
            else:
                logging.info(f"Existing long hedge of size {hedge_pos['size']} found.")

            managed_pos = self.client.get_position_info(self.symbol, positionIdx=2) # Short position
            self.managed_position_open = managed_pos['size'] > 0
            self.managed_position_size = managed_pos['size']
            logging.info(f"Initial check: Managed Short position is {'OPEN' if self.managed_position_open else 'CLOSED'} with size {self.managed_position_size}.")

    def manage_positions(self):
        """The main loop to manage trading logic, driven by the price queue and mode."""
        logging.info("Starting position management...")
        while True:
            try:
                current_price = self.price_queue.get()
                while not self.price_queue.empty():
                    try:
                        current_price = self.price_queue.get_nowait()
                    except queue.Empty:
                        break

                if self.mode == 'L':
                    self._manage_long_logic(current_price)
                elif self.mode == 'S':
                    self._manage_short_logic(current_price)

            except queue.Empty:
                time.sleep(1)
            except Exception as e:
                logging.error(f"An error occurred in the main loop: {e}")
                time.sleep(30)

    def _manage_long_logic(self, current_price):
        """Handles the logic for opening/closing the managed LONG position."""
        logging.info(f"Price: {current_price} | Long Target: {self.long_price} | Long Pos Open: {self.managed_position_open}")
        current_qty = round((self.hedge_amount_usdt * self.leverage) / current_price, 3)

        if not self.managed_position_open and current_price > self.long_price:
            if current_qty > 0:
                response = self.client.open_long_position(self.symbol, str(current_qty), current_price)
                if response and response.get('retCode') == 0:
                    self.managed_position_open = True
                    self.managed_position_size = current_qty
                    logging.info(f"Managed LONG position opened. Size: {self.managed_position_size}.")

        elif self.managed_position_open and current_price <= self.long_price:
            response = self.client.close_long_position(self.symbol, str(self.managed_position_size), current_price)
            if response and response.get('retCode') == 0:
                self.managed_position_open = False
                self.managed_position_size = 0.0
                logging.info("Managed LONG position closed.")

    def _manage_short_logic(self, current_price):
        """Handles the logic for opening/closing the managed SHORT position."""
        logging.info(f"Price: {current_price} | Short Target: {self.short_price} | Short Pos Open: {self.managed_position_open}")
        current_qty = round((self.hedge_amount_usdt * self.leverage) / current_price, 3)

        if not self.managed_position_open and current_price < self.short_price:
            if current_qty > 0:
                response = self.client.open_short_position(self.symbol, str(current_qty), current_price)
                if response and response.get('retCode') == 0:
                    self.managed_position_open = True
                    self.managed_position_size = current_qty
                    logging.info(f"Managed SHORT position opened. Size: {self.managed_position_size}.")

        elif self.managed_position_open and current_price >= self.short_price:
            response = self.client.close_short_position(self.symbol, str(self.managed_position_size), current_price)
            if response and response.get('retCode') == 0:
                self.managed_position_open = False
                self.managed_position_size = 0.0
                logging.info("Managed SHORT position closed.")