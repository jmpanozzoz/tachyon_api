"""Shared valid requests and exact expected JSON for all benchmark targets."""
SCENARIOS = [
    ('hello', 'GET', '/hello', None, {}, {'message': 'Hello, World!'}),
    ('path_query', 'GET', '/items/42?q=test&limit=5', None, {}, {'item_id': 42, 'q': 'test', 'limit': 5}),
    ('body', 'POST', '/items', {'name': 'Widget', 'price': 9.99}, {}, {'created': 'Widget', 'price': 9.99}),
    ('nested_body', 'POST', '/orders', {'customer': 'Alice', 'lines': [{'item_id': 1, 'qty': 2}, {'item_id': 2, 'qty': 3}]}, {}, {'customer': 'Alice', 'total_items': 5}),
    ('response_model', 'GET', '/users/42', None, {}, {'id': 42, 'username': 'user_42', 'email': 'user_42@example.com'}),
    ('header', 'GET', '/auth', None, {'x-api-key': 'secret'}, {'authenticated': True}),
    ('dependency', 'GET', '/users/42/profile', None, {}, {'id': 42, 'source': 'db'}),
    ('query', 'GET', '/search?q=test&page=2&size=5&active=true', None, {}, {'q': 'test', 'tags': [], 'page': 2, 'size': 5, 'active': True}),
]
