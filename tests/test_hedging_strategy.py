import pytest
from src.hedging_strategy import HedgingStrategy

def test_open_short_position():
    strategy = HedgingStrategy()
    result = strategy.open_short_position('BTC', 30000)
    assert result is not None
    assert result['side'] == 'sell'
    assert result['symbol'] == 'BTC'
    assert result['price'] == 30000

def test_close_short_position():
    strategy = HedgingStrategy()
    strategy.open_short_position('BTC', 30000)
    result = strategy.close_short_position('BTC', 29000)
    assert result is not None
    assert result['side'] == 'buy'
    assert result['symbol'] == 'BTC'
    assert result['price'] == 29000

def test_price_movement_logic():
    strategy = HedgingStrategy()
    strategy.open_short_position('ETH', 2000)
    price_movement = strategy.check_price_movement('ETH', 1950)
    assert price_movement is True  # Assuming it triggers a close on price drop

    price_movement = strategy.check_price_movement('ETH', 2050)
    assert price_movement is False  # No action should be taken on price rise