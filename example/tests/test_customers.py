"""Ownership is tested with two real users, including after cache population."""
from sqlalchemy import select
from example.shared.models import Customer, User
from .conftest import register


def test_create_read_and_repeat_are_persistent(client, customer, auth_headers):
    for route in ("/customers/me", "/customers/" + customer["customer_id"]):
        assert client.get(route, headers=auth_headers).json() == customer
    repeated = client.post("/customers/", headers=auth_headers,
        json={"first_name": "Alice", "last_name": "Other", "email": "another@example.com"})
    assert repeated.json()["customer_id"] == customer["customer_id"]
    async def count():
        async with client.app.state.sessions() as session:
            return len((await session.scalars(select(Customer))).all())
    assert client.portal.call(count) == 1


def test_other_user_cannot_read_customer_even_after_cache_hit(client, customer, auth_headers):
    assert client.get("/customers/" + customer["customer_id"], headers=auth_headers).status_code == 200
    _, other = register(client, "bob")
    for route in ("/customers/" + customer["customer_id"], "/customers/missing", "/customers/me"):
        assert client.get(route, headers=other).status_code == 404
    assert client.get("/customers/recent", headers=other).status_code == 403
    assert client.post("/customers/" + customer["customer_id"] + "/notification-ticket", headers=other).status_code == 404


def test_admin_listing_is_bounded_and_user_role_is_current(client, customer, identity):
    user, headers = identity
    assert client.get("/customers/recent", headers=headers).status_code == 403
    async def promote():
        async with client.app.state.sessions() as session, session.begin():
            (await session.get(User, user["user_id"])).role = "admin"
    client.portal.call(promote)
    assert client.get("/customers/recent?limit=3", headers=headers).json() == [customer]
    for limit in (0, 101, -1):
        assert client.get("/customers/recent?limit=" + str(limit), headers=headers).status_code == 422
