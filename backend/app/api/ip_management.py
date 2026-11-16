from ipaddress import ip_address
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.config import now, settings
from app.security.authentication import auth, limit

router = APIRouter(prefix='/api/v1/ip-management')


def public_address(value: str):
    try:
        address = ip_address(value)
    except ValueError:
        return None
    if not address.is_global or address.is_multicast or getattr(address, 'scope_id', None):
        return None
    return address


@router.get('/current')
def current_connection(request: Request, response: Response, user=Depends(auth)):
    response.headers['Cache-Control'] = 'no-store'
    address = public_address(request.client.host) if request.client else None
    return {
        'public_ip': str(address) if address else None,
        'ip_version': address.version if address else None,
        'detected_at': now(),
        'egress_status': 'configured_unverified' if public_address(settings.broker_egress_ip) else 'not_configured',
    }


class AddressLookup(BaseModel):
    value: str = Field(min_length=1, max_length=253)


@router.post('/verify-address')
def verify_address(data: AddressLookup, request: Request, response: Response, user=Depends(auth)):
    import re
    import socket

    limit(request, 'ip_address_lookup', user.id)
    response.headers['Cache-Control'] = 'no-store'
    value = data.value.strip()
    try:
        ip_address(value)
    except ValueError:
        hostname = value.removesuffix('.')
        labels = hostname.split('.')
        if len(labels) < 2 or not re.fullmatch(r'[A-Za-z]{2,63}', labels[-1]) or not all(
            re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in labels
        ):
            raise HTTPException(422, 'Enter a public IP address or a fully qualified hostname.')
        try:
            records = socket.getaddrinfo(hostname + '.', None, type=socket.SOCK_STREAM)
        except OSError:
            raise HTTPException(422, 'The hostname could not be resolved.') from None
        addresses = {address for record in records if (address := public_address(record[4][0]))}
    else:
        address = public_address(value)
        addresses = {address} if address else set()
    if not addresses:
        raise HTTPException(422, 'No public IPv4 or IPv6 address was found.')
    return {'addresses': [str(address) for address in sorted(addresses, key=lambda a: (a.version, int(a)))][:16]}
