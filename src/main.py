from pybit.unified_trading import HTTP
import logging
from bybit_client import BybitClient
from hedging_strategy import HedgingStrategy
from config import API_KEY, API_SECRET

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    if not API_KEY or not API_SECRET:
        logging.error("API_KEY and API_SECRET must be set in a .env file.")
    else:
        try:
            while True:
                mode_choice = input("Select mode: (1) Demo mode, (2) Live trading mode: ")
                if mode_choice in ['1', '2']:
                    break
                else:
                    logging.warning("Invalid choice. Please enter 1 or 2.")
            
            demo = mode_choice == '1'

            symbol = input("Enter the coin to hedge against (e.g., 'BTCUSDT'): ").upper()
            
            # --- Auto-detection logic ---
            client = BybitClient(api_key=API_KEY, api_secret=API_SECRET, testnet=False, demo=demo)
            long_pos = client.get_position_info(symbol, positionIdx=1)
            short_pos = client.get_position_info(symbol, positionIdx=2)

            mode = None
            long_price = 0
            short_price = 0

            if short_pos['size'] > 0:
                logging.info(f"Existing short position of size {short_pos['size']} detected.")
                logging.info("Starting in 'Manage Long' mode.")
                mode = 'L'
                long_price = float(input("Enter the LONG price to monitor against: "))
            elif long_pos['size'] > 0:
                logging.info(f"Existing long position of size {long_pos['size']} detected.")
                logging.info("Starting in 'Manage Short' mode.")
                mode = 'S'
                short_price = float(input("Enter the SHORT price to monitor against: "))
            else:
                logging.warning("No existing positions found for this symbol.")
                # If no positions, default to starting a short hedge and managing a long position
                logging.info("Defaulting to 'Manage Long' mode. A new short hedge will be created.")
                mode = 'L'
                long_price = float(input("Enter the LONG price to open a managed position: "))

            hedge_amount_usdt = float(input("Enter the amount to hedge in USDT: "))
            leverage = int(input("Enter leverage (0-100, 0 for no change): "))
            trade_delay = int(input("Enter delay in seconds between opening and closing a trade: "))

            if not 0 <= leverage <= 100:
                raise ValueError("Leverage must be between 0 and 100.")

            strategy = HedgingStrategy(
                client, 
                symbol, 
                long_price, 
                short_price, 
                hedge_amount_usdt, 
                leverage,
                mode,
                trade_delay
            )
            
            # Initial setup
            strategy.initial_setup()

            # Start managing positions
            strategy.manage_positions()

        except ValueError as e:
            logging.error(f"Invalid input: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")