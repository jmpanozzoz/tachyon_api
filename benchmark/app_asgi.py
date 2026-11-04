"""ASGI floor: same valid-request work, without framework validation or DI machinery.

This is a lower-bound reference, not a claim of equivalent error handling.
"""
import json
from urllib.parse import parse_qs


class Database:
    def query(self, user_id):
        return {'id': user_id, 'source': 'db'}


async def app(scope, receive, send):
    path = scope['path']
    query = parse_qs(scope['query_string'].decode())
    if path == '/hello':
        payload = {'message': 'Hello, World!'}
    elif path == '/items' or path == '/orders':
        body = b''
        while True:
            message = await receive()
            body += message.get('body', b'')
            if not message.get('more_body', False):
                break
        value = json.loads(body)
        if path == '/items':
            payload = {'created': value['name'], 'price': float(value['price'])}
        else:
            payload = {'customer': value['customer'], 'total_items': sum(line['qty'] for line in value['lines'])}
    elif path.startswith('/items/'):
        payload = {'item_id': int(path.split('/')[2]), 'q': query.get('q', [None])[0], 'limit': int(query.get('limit', [10])[0])}
    elif path.endswith('/profile'):
        payload = Database().query(int(path.split('/')[2]))
    elif path.startswith('/users/'):
        user_id = int(path.split('/')[2])
        payload = {'id': user_id, 'username': f'user_{user_id}', 'email': f'user_{user_id}@example.com'}
    elif path == '/auth':
        payload = {'authenticated': dict(scope['headers']).get(b'x-api-key') == b'secret'}
    elif path == '/search':
        payload = {'q': query['q'][0], 'tags': [], 'page': int(query.get('page', [1])[0]), 'size': int(query.get('size', [20])[0]), 'active': query.get('active', ['true'])[0] == 'true'}
    else:
        raise ValueError(f'Unknown benchmark path {path}')
    body = json.dumps(payload, separators=(',', ':')).encode()
    await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', b'application/json'), (b'content-length', str(len(body)).encode())]})
    await send({'type': 'http.response.body', 'body': body})
