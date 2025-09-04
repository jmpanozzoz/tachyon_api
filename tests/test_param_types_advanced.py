from starlette.testclient import TestClient
from typing import Optional, List

from tachyon_api import Tachyon, Query


def test_optional_query_param_absent_and_present():
    app = Tachyon()

    @app.get("/opt")
    def opt(q: Optional[str] = Query(None)):
        return {"q": q}

    client = TestClient(app._router)

    r1 = client.get("/opt").json()
    assert r1 == {"q": None}

    r2 = client.get("/opt?q=hello").json()
    assert r2 == {"q": "hello"}


def test_list_query_param_csv_and_repeated():
    app = Tachyon()

    @app.get("/ids")
    def ids(ids: List[int] = Query(...)):
        return {"ids": ids}

    client = TestClient(app._router)

    r1 = client.get("/ids?ids=1,2,3").json()
    assert r1 == {"ids": [1, 2, 3]}

    # Repeated params
    r2 = client.get("/ids?ids=4&ids=5").json()
    assert r2 == {"ids": [4, 5]}
