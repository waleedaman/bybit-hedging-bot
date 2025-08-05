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

    def initial_setup(self):
        """Sets leverage, calculates order quantity, and opens initial short position."""
        logging.info("Performing initial setup...")
        if 1 <= self.leverage <= 100:
            self.client.set_leverage(self.symbol, self.leverage)
        else:
            logging.info("Leverage is 0, skipping leverage setting.")
        
        # Use an initial price to calculate quantity. This will be recalculated on order placement.
        initial_price = self.client.get_market_price(self.symbol)
        if not (initial_price and initial_price > 0):
            raise Exception("Could not retrieve initial market price to calculate quantity.")
        
        self.qty = round((self.hedge_amount_usdt * self.leverage) / initial_price, 3)
        logging.info(f"Initial quantity calculated: {self.qty} {self.symbol}")

        # Open initial short position if it doesn't exist
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
                    time.sleep(10)
                    continue

                # Get current position status
                long_pos = self.client.get_position_info(self.symbol, positionIdx=1)

                logging.info(
                    f"Price: {current_price} | "
                    f"Long Target: {self.long_price} | "
                    f"Long Pos: {long_pos['size']}"
                )

                # Recalculate quantity based on current price before placing an order
                self.qty = round((self.hedge_amount_usdt * self.leverage) / current_price, 3)

                # --- Trading Logic ---
                # 1. Open long position if price is above long_price and no long is open
                if long_pos['size'] == 0 and current_price > self.long_price:
                    self.client.open_long_position(self.symbol, str(self.qty), current_price)

                # 2. Close long position if price drops to long_price and a long is open
                elif long_pos['size'] > 0 and current_price <= self.long_price:
                    self.client.close_long_position(self.symbol, str(long_pos['size']), current_price)

            except Exception as e:
                logging.error(f"An error occurred in the main loop: {e}")
                time.sleep(30) # Wait longer after an error