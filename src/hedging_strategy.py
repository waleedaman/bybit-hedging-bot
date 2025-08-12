import logging
import time
import queue
import threading

class HedgingStrategy:
    def __init__(self, client, symbol, long_price, short_price, hedge_amount_usdt, leverage, mode, trade_delay):
        self.client = client
        self.symbol = symbol
        # --- These parameters are now mutable at runtime ---
        self.long_price = long_price
        self.short_price = short_price
        self.trade_delay = trade_delay
        # ---
        self.hedge_amount_usdt = hedge_amount_usdt
        self.leverage = leverage
        self.mode = mode
        self.qty = 0
        self.price_queue = queue.Queue()
        self.managed_position_open = False
        self.managed_position_size = 0.0
        # --- State variables for dynamic delay and shutdown ---
        self.trade_open_time = None # Timestamp when the position was opened
        self.last_price = None
        self._stop_event = threading.Event()

    def stop(self):
        """Signals the trading loop to stop."""
        self._stop_event.set()
        self.price_queue.put(None) # Unblock the queue.get()
    
    def is_stopped(self):
        """Checks if the stop signal has been sent."""
        return self._stop_event.is_set()

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
            # --- Manage Long Mode: Ensure Short Hedge Exists ---
            hedge_pos = self.client.get_position_info(self.symbol, positionIdx=2) # Short position
            if hedge_pos['size'] == 0:
                logging.info("No short hedge found. Opening initial short position.")
                self.client.open_short_position(self.symbol, str(self.qty), initial_price)
            
            managed_pos = self.client.get_position_info(self.symbol, positionIdx=1) # Long position
            self.managed_position_open = managed_pos['size'] > 0
            self.managed_position_size = managed_pos['size']
            if self.managed_position_open:
                self.trade_open_time = time.time() # Assume existing position was just opened for delay purposes
            logging.info(f"Initial check: Managed Long position is {'OPEN' if self.managed_position_open else 'CLOSED'} with size {self.managed_position_size}.")

        elif self.mode == 'S':
            # --- Manage Short Mode: Ensure Long Hedge Exists ---
            hedge_pos = self.client.get_position_info(self.symbol, positionIdx=1) # Long position
            if hedge_pos['size'] == 0:
                logging.info("No long hedge found. Opening initial long position.")
                self.client.open_long_position(self.symbol, str(self.qty), initial_price)

            managed_pos = self.client.get_position_info(self.symbol, positionIdx=2) # Short position
            self.managed_position_open = managed_pos['size'] > 0
            self.managed_position_size = managed_pos['size']
            if self.managed_position_open:
                self.trade_open_time = time.time()
            logging.info(f"Initial check: Managed Short position is {'OPEN' if self.managed_position_open else 'CLOSED'} with size {self.managed_position_size}.")

    def manage_positions(self):
        """The main loop to manage trading logic, driven by the price queue and mode."""
        logging.info("Starting position management...")
        while not self._stop_event.is_set():
            try:
                current_price = self.price_queue.get()
                self.last_price = current_price # Update last price for display
                if current_price is None: # Check for stop signal
                    continue

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
        logging.info("Position management loop has stopped.")

    def _manage_long_logic(self, current_price):
        """Handles the logic for opening/closing the managed LONG position."""
        logging.info(f"Price: {current_price} | Long Target: {self.long_price} | Long Pos Open: {self.managed_position_open}")
        
        # Dynamic delay check
        if self.trade_open_time and time.time() < self.trade_open_time + self.trade_delay:
            remaining = (self.trade_open_time + self.trade_delay) - time.time()
            logging.info(f"Trade cool-down active. Cannot close for another {remaining:.2f}s.")
            if self.managed_position_open and current_price <= self.long_price:
                return

        current_qty = round((self.hedge_amount_usdt * self.leverage) / current_price, 3)

        if not self.managed_position_open and current_price > self.long_price:
            if current_qty > 0:
                response = self.client.open_long_position(self.symbol, str(current_qty), current_price)
                if response and response.get('retCode') == 0:
                    self.managed_position_open = True
                    self.managed_position_size = current_qty
                    self.trade_open_time = time.time()
                    logging.info(f"Managed LONG position opened. Size: {self.managed_position_size}. Cool-down started.")

        elif self.managed_position_open and current_price <= self.long_price:
            response = self.client.close_long_position(self.symbol, str(self.managed_position_size), current_price)
            if response and response.get('retCode') == 0:
                self.managed_position_open = False
                self.managed_position_size = 0.0
                self.trade_open_time = None
                logging.info("Managed LONG position closed.")

    def _manage_short_logic(self, current_price):
        """Handles the logic for opening/closing the managed SHORT position."""
        logging.info(f"Price: {current_price} | Short Target: {self.short_price} | Short Pos Open: {self.managed_position_open}")

        # Dynamic delay check
        if self.trade_open_time and time.time() < self.trade_open_time + self.trade_delay:
            remaining = (self.trade_open_time + self.trade_delay) - time.time()
            logging.info(f"Trade cool-down active. Cannot close for another {remaining:.2f}s.")
            if self.managed_position_open and current_price >= self.short_price:
                return

        current_qty = round((self.hedge_amount_usdt * self.leverage) / current_price, 3)

        if not self.managed_position_open and current_price < self.short_price:
            if current_qty > 0:
                response = self.client.open_short_position(self.symbol, str(current_qty), current_price)
                if response and response.get('retCode') == 0:
                    self.managed_position_open = True
                    self.managed_position_size = current_qty
                    self.trade_open_time = time.time()
                    logging.info(f"Managed SHORT position opened. Size: {self.managed_position_size}. Cool-down started.")

        elif self.managed_position_open and current_price >= self.short_price:
            response = self.client.close_short_position(self.symbol, str(self.managed_position_size), current_price)
            if response and response.get('retCode') == 0:
                self.managed_position_open = False
                self.managed_position_size = 0.0
                self.trade_open_time = None
                logging.info("Managed SHORT position closed.")