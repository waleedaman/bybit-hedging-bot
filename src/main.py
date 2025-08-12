from pybit.unified_trading import HTTP
import logging
import threading
import time
from bybit_client import BybitClient
from hedging_strategy import HedgingStrategy
from config import API_KEY, API_SECRET

# Configure logging to write to a file ONLY. The console will be used for interaction.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8')
    ]
)

# We'll use a separate logger for clean console output during setup.
console = logging.getLogger('console')
console.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(message)s'))
console.addHandler(console_handler)


def input_handler(strategy: HedgingStrategy):
    """Runs in a separate thread to handle user input for modifying strategy parameters at runtime."""
    time.sleep(1) # Allow the main thread to print its startup messages.
    while not strategy.is_stopped():
        try:
            # --- Clean Status Display ---
            mode_str = "Manage Long" if strategy.mode == 'L' else "Manage Short"
            pos_status = "OPEN" if strategy.managed_position_open else "CLOSED"
            pos_size = strategy.managed_position_size
            last_price = strategy.last_price or "N/A"

            print("\n" + "="*50)
            print(f"STATUS | Mode: {mode_str} | Position: {pos_status} ({pos_size}) | Last Price: {last_price}")
            print(f"PARAMS | Long Target: {strategy.long_price} | Short Target: {strategy.short_price} | Delay: {strategy.trade_delay}s")
            print("--- Runtime Commands ---")
            print("1. Change Long Price")
            print("2. Change Short Price")
            print("3. Change Trade Delay (seconds)")
            print("Type 'exit' to stop the bot.")
            
            command = input("Enter command: ").strip()

            if command == '1':
                new_price = float(input("Enter new long price: "))
                strategy.long_price = new_price
                logging.info(f"Long price updated to: {strategy.long_price}")
                console.info(f"-> Long price updated to: {strategy.long_price}")
            elif command == '2':
                new_price = float(input("Enter new short price: "))
                strategy.short_price = new_price
                logging.info(f"Short price updated to: {strategy.short_price}")
                console.info(f"-> Short price updated to: {strategy.short_price}")
            elif command == '3':
                new_delay = int(input("Enter new trade delay (seconds): "))
                strategy.trade_delay = new_delay
                logging.info(f"Trade delay updated to: {strategy.trade_delay}s")
                console.info(f"-> Trade delay updated to: {strategy.trade_delay}s")
            elif command == 'exit':
                console.info("Exit command received. Stopping bot...")
                logging.info("Exit command received. Stopping bot...")
                strategy.stop()
                break
            else:
                console.info("Invalid command.")
        except ValueError:
            console.info("Invalid input. Please enter a valid number.")
        except Exception as e:
            logging.error(f"Error in input handler: {e}")
            console.error(f"An error occurred: {e}")

if __name__ == "__main__":
    if not API_KEY or not API_SECRET:
        logging.error("API_KEY and API_SECRET must be set in a .env file.")
    else:
        try:
            # --- Initial Setup from User ---
            while True:
                mode_choice = input("Select mode: (1) Demo mode, (2) Live trading mode: ")
                if mode_choice in ['1', '2']:
                    break
                else:
                    console.warning("Invalid choice. Please enter 1 or 2.")
            
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
                console.info(f"Existing short position of size {short_pos['size']} detected.")
                console.info("Starting in 'Manage Long' mode.")
                mode = 'L'
                long_price = float(input("Enter the LONG price to monitor against: "))
            elif long_pos['size'] > 0:
                console.info(f"Existing long position of size {long_pos['size']} detected.")
                console.info("Starting in 'Manage Short' mode.")
                mode = 'S'
                short_price = float(input("Enter the SHORT price to monitor against: "))
            else:
                console.warning("No existing positions found for this symbol.")
                console.info("Defaulting to 'Manage Long' mode. A new short hedge will be created.")
                mode = 'L'
                long_price = float(input("Enter the LONG price to open a managed position: "))

            hedge_amount_usdt = float(input("Enter the amount to hedge in USDT: "))
            leverage = int(input("Enter leverage (0-100, 0 for no change): "))
            trade_delay = int(input("Enter delay in seconds between opening and closing a trade: "))

            if not 0 <= leverage <= 100:
                raise ValueError("Leverage must be between 0 and 100.")

            strategy = HedgingStrategy(
                client, symbol, long_price, short_price, hedge_amount_usdt, leverage, mode, trade_delay
            )
            
            strategy.initial_setup()

            # --- Start Threads ---
            main_thread = threading.Thread(target=strategy.manage_positions, name="TradingThread")
            input_thread = threading.Thread(target=input_handler, args=(strategy,), name="InputThread", daemon=True)

            console.info("\n" + "="*50)
            console.info("Bot is running. Detailed logs are in 'bot.log'.")
            console.info("To see live logs, open a new terminal and run:")
            console.info("PowerShell: Get-Content bot.log -Wait")
            console.info("CMD: powershell -command \"Get-Content bot.log -Wait\"")
            console.info("="*50)

            main_thread.start()
            input_thread.start()

            main_thread.join()
            console.info("Bot has been shut down.")

        except ValueError as e:
            logging.error(f"Invalid input: {e}")
            console.error(f"Invalid input: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during startup: {e}")
            console.error(f"An unexpected error occurred: {e}")