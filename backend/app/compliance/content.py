"""Versioned disclosure content. Changes automatically invalidate previous receipts."""
import hashlib
import json
from app.core.config import settings
DISCLOSURE_ID = 'equity-fo-risk'
CONTENT = {
    'heading': 'Trade Responsibly in Futures & Options',
    'subheading': 'Risk Disclosures on Derivatives:',
    'points': [
        '9 out of 10 individual traders in Equity, Futures and Options segment, incurred net losses.',
        'On an average, loss makers registered net trading loss close to ₹50,000.',
        'Over and above the net trading losses incurred, loss makers expended an additional 28% of net trading losses as transaction costs.',
        'Those making net trading profits, incurred between 15% to 50% of such profits as transaction cost.',
    ],
    'awareness_heading': 'SEBI presents "Samajh Se Investing Simple"',
    'awareness_messages': ['Understand Before You Invest.', 'Choose Regulated Investment Products.', 'Start Early, Stay Invested.', 'Beware of Investment Frauds.'],
    'source': 'SEBI study dated January 25, 2023 on "Analysis of Profit and Loss of Individual Traders dealing in equity Futures and Options (F&O) Segment", wherein Aggregate Level findings are based on annual Profit/Loss incurred by individual traders in equity F&O during FY 2021-22.',
    'historical_note': 'Historical study: equity F&O, FY 2021–22. These figures are not current-year estimates and do not describe all equity-market investing.',
    'source_url': 'https://www.sebi.gov.in/media/press-releases/jan-2023/sebi-underlines-the-need-for-analysis-and-disclosure-of-risks-of-trading-in-fando_67542.html',
    'awareness_url': 'https://investor.sebi.gov.in/',
    'platform_note': 'Acknowledgment does not authorize real-money execution. Live trading remains disabled.',
}
def document():
    fingerprint = hashlib.sha256(json.dumps(CONTENT, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {**CONTENT, 'id': DISCLOSURE_ID, 'version': settings.disclosure_version + '-' + fingerprint[:16], 'content_sha256': fingerprint, 'frequency': 'each_login', 'max_age_hours': settings.disclosure_max_age_hours}
