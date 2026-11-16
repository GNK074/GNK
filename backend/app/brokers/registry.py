from app.brokers.upstox.adapter import UpstoxAdapter

AUTH_ADAPTERS = {'upstox': UpstoxAdapter}
BROKER_IDS = {'dhan', 'zerodha', 'upstox', 'angelone', 'fyers', '5paisa', 'icici'}

# Stable GNK identifiers and display names for the public broker catalog.
BROKER_NAMES = {
    'dhan': 'Dhan',
    'zerodha': 'Zerodha',
    'upstox': 'Upstox',
    'angelone': 'Angel One',
    'fyers': 'FYERS',
    '5paisa': '5paisa',
    'icici': 'ICICI Direct',
    'kotak-neo': 'Kotak Neo',
    'alice-blue': 'Alice Blue',
    'shoonya': 'Shoonya',
    'motilal-oswal': 'Motilal Oswal',
    'sharekhan': 'Sharekhan',
    'groww': 'Groww',
    'hdfc-securities': 'HDFC Securities',
    'share-market': 'Share.Market',
    'indmoney': 'INDmoney',
}

BROKER_ALIASES = {'angel-one': 'angelone', 'icici-direct': 'icici'}
