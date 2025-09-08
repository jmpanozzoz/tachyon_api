def test_struct_is_reexported_from_msgspec():
    try:
        from tachyon_api.schemas.models import Struct as TachyonStruct
    except ImportError:
        assert False, "TachyonStruct should be imported from tachyon_api.models"

    from msgspec import Struct as MsgspecStruct

    assert TachyonStruct is MsgspecStruct, (
        "TachyonStruct should be the same as msgspec.Struct"
    )
