"""Decode only the pinned official Upstox V3 schema; unknown fields remain compatible."""
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError
from .MarketDataFeed_pb2 import FeedResponse
from app.market_data.providers.base import ProviderError

def decode(raw):
    if not isinstance(raw,bytes) or len(raw)>4*1024*1024:raise ProviderError('INVALID_PROTOBUF_FRAME')
    try:
        response=FeedResponse();response.ParseFromString(raw)
        data=MessageToDict(response,preserving_proto_field_name=True)
        if not data or (not response.feeds and not response.HasField('marketInfo')):raise ValueError()
        # proto3 initial_feed is enum zero and is legitimately omitted by MessageToDict.
        data.setdefault('type','initial_feed')
        return data
    except (DecodeError,ValueError):raise ProviderError('INVALID_PROTOBUF_FRAME') from None
