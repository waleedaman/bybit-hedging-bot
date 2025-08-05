import unittest
from unittest.mock import MagicMock
from src.bybit_client import BybitClient

class TestBybitClient(unittest.TestCase):

    def setUp(self):
        self.client = BybitClient(api_key='test_api_key', api_secret='test_api_secret')
        self.client.api = MagicMock()

    def test_initialize_client(self):
        self.assertIsNotNone(self.client)
        self.assertEqual(self.client.api_key, 'test_api_key')
        self.assertEqual(self.client.api_secret, 'test_api_secret')

    def test_get_wallet_balance(self):
        self.client.api.get_wallet_balance.return_value = {'result': {'USDT': {'available_balance': 100}}}
        balance = self.client.get_wallet_balance()
        self.assertEqual(balance['result']['USDT']['available_balance'], 100)

    def test_get_market_data(self):
        self.client.api.get_market_data.return_value = {'result': {'price': 50000}}
        market_data = self.client.get_market_data('BTCUSDT')
        self.assertEqual(market_data['result']['price'], 50000)

if __name__ == '__main__':
    unittest.main()