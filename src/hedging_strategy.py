import logging
import time
import queue

class HedgingStrategy:
    def __init__(self, client, symbol, long_price, short_price, hedge_amount_usdt, leverage, mode, initial_delay):
        self.client = client
        self.symbol = symbol
        self.long_price = long_price
        self.short_price = short_price
        self.hedge_amount_usdt = hedge_amount_usdt
        self.leverage = leverage
        self.mode = mode
        self.initial_delay = initial_delay
        self.qty = 0
        self.price_queue = queue.Queue()
        self.managed_position_open = False
        self.managed_position_size = 0.0
        # --- New state variables for the one-time delay ---
        self.initial_delay_end_time = None # Timestamp when the delay ends
        self.first_managed_position_opened = False # Flag to ensure delay only happens once

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
        
        # Check if the initial delay is active
        if self.initial_delay_end_time and time.time() < self.initial_delay_end_time:
            logging.info(f"Initial delay active. Position cannot be closed until {time.ctime(self.initial_delay_end_time)}.")
            # If price is below target during delay, we just log and do nothing
            if self.managed_position_open and current_price <= self.long_price:
                return # Skip closing logic

        current_qty = round((self.hedge_amount_usdt * self.leverage) / current_price, 3)

        if not self.managed_position_open and current_price > self.long_price:
            if current_qty > 0:
                response = self.client.open_long_position(self.symbol, str(current_qty), current_price)
                if response and response.get('retCode') == 0:
                    self.managed_position_open = True
                    self.managed_position_size = current_qty
                    logging.info(f"Managed LONG position opened. Size: {self.managed_position_size}.")
                    # --- Trigger the one-time delay ---
                    if not self.first_managed_position_opened:
                        self.initial_delay_end_time = time.time() + self.initial_delay
                        self.first_managed_position_opened = True
                        logging.info(f"FIRST managed position opened. Initial delay timer started for {self.initial_delay} seconds.")

        elif self.managed_position_open and current_price <= self.long_price:
            response = self.client.close_long_position(self.symbol, str(self.managed_position_size), current_price)
            if response and response.get('retCode') == 0:
                self.managed_position_open = False
                self.managed_position_size = 0.0
                logging.info("Managed LONG position closed.")
                # Once closed, we can nullify the delay timer so it doesn't interfere
                if self.initial_delay_end_time:
                    self.initial_delay_end_time = None

    def _manage_short_logic(self, current_price):
        """Handles the logic for opening/closing the managed SHORT position."""
        logging.info(f"Price: {current_price} | Short Target: {self.short_price} | Short Pos Open: {self.managed_position_open}")

        # Check if the initial delay is active
        if self.initial_delay_end_time and time.time() < self.initial_delay_end_time:
            logging.info(f"Initial delay active. Position cannot be closed until {time.ctime(self.initial_delay_end_time)}.")
            if self.managed_position_open and current_price >= self.short_price:
                return # Skip closing logic

        current_qty = round((self.hedge_amount_usdt * self.leverage) / current_price, 3)

        if not self.managed_position_open and current_price < self.short_price:
            if current_qty > 0:
                response = self.client.open_short_position(self.symbol, str(current_qty), current_price)
                if response and response.get('retCode') == 0:
                    self.managed_position_open = True
                    self.managed_position_size = current_qty
                    logging.info(f"Managed SHORT position opened. Size: {self.managed_position_size}.")
                    # --- Trigger the one-time delay ---
                    if not self.first_managed_position_opened:
                        self.initial_delay_end_time = time.time() + self.initial_delay
                        self.first_managed_position_opened = True
                        logging.info(f"FIRST managed position opened. Initial delay timer started for {self.initial_delay} seconds.")

        elif self.managed_position_open and current_price >= self.short_price:
            response = self.client.close_short_position(self.symbol, str(self.managed_position_size), current_price)
            if response and response.get('retCode') == 0:
                self.managed_position_open = False
                self.managed_position_size = 0.0
                logging.info("Managed SHORT position closed.")
                # Once closed, we can nullify the delay timer so it doesn't interfere
                if self.initial_delay_end_time:
                    self.initial_delay_end_time = None