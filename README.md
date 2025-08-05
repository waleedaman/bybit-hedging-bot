# bybit-hedging-bot

## Overview
The Bybit Hedging Bot is a Python-based trading bot designed to interact with the Bybit exchange using the pybit library. This bot allows users to hedge against price movements of a specified cryptocurrency by managing short positions based on user-defined price limits.

## Features
- User prompts for selecting a cryptocurrency to hedge against.
- Ability to set price limits for opening and closing short positions.
- Automated management of short positions based on market price movements.

## Project Structure
```
bybit-hedging-bot
├── src
│   ├── __init__.py
│   ├── main.py                # Entry point for the hedging bot
│   ├── bybit_client.py        # Bybit client setup and API interactions
│   ├── hedging_strategy.py    # Implementation of the hedging strategy
│   └── config.py             # Configuration settings and environment variables
├── tests
│   ├── __init__.py
│   ├── test_bybit_client.py   # Unit tests for Bybit client functionality
│   └── test_hedging_strategy.py # Unit tests for the hedging strategy
├── .env.example               # Template for environment variables
├── .gitignore                 # Files and directories to ignore in version control
├── requirements.txt           # Project dependencies
└── README.md                  # Project documentation
```

## Installation
1. Clone the repository:
   ```
   git clone https://github.com/yourusername/bybit-hedging-bot.git
   cd bybit-hedging-bot
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up your environment variables by copying `.env.example` to `.env` and filling in your Bybit API credentials.

## Usage
To run the hedging bot, execute the following command:
```
python src/main.py
```
Follow the prompts to enter the cryptocurrency you wish to hedge against and the price limit.

## Contributing
Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for details.