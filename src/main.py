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
            short_price = float(input("Enter the price to open a short position: "))
            long_price = float(input("Enter the price to open a long position: "))
            hedge_amount_usdt = float(input("Enter the amount to hedge in USDT: "))
            leverage = int(input("Enter leverage (0-100, 0 for no change): "))
            initial_delay = int(input("Enter initial delay in seconds before first position can be closed: "))

            if not 0 <= leverage <= 100:
                raise ValueError("Leverage must be between 0 and 100.")

            while True:
                mode = input("Select mode: (L) Manage Long, (S) Manage Short: ").upper()
                if mode in ['L', 'S']:
                    break
                else:
                    logging.warning("Invalid choice. Please enter L or S.")

            client = BybitClient(api_key=API_KEY, api_secret=API_SECRET, testnet=False, demo=demo)
            strategy = HedgingStrategy(
                client, 
                symbol, 
                long_price, 
                short_price, 
                hedge_amount_usdt, 
                leverage,
                mode,
                initial_delay
            )
            
            # Initial setup
            strategy.initial_setup()

            # Start managing positions
            strategy.manage_positions()

        except ValueError as e:
            logging.error(f"Invalid input: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")