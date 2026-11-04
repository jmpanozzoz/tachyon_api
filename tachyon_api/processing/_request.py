"""Request stream ownership for bounded forms and incomplete multipart files."""
from starlette.datastructures import FormData, UploadFile
from ..files import UploadFile as TachyonUploadFile
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import Request


class ManagedRequest(Request):
    async def _get_form(self, *, max_files=1000, max_fields=1000, max_part_size=1024 * 1024):
        if self._form is not None:
            return self._form
        # Read through the bounded receive once. This also lets Body/Request
        # dependencies reuse the original bytes after a form has been parsed.
        await self.body()
        options = dict(max_files=max_files, max_fields=max_fields, max_part_size=max_part_size)
        content_type = self.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "multipart/form-data":
            return await super()._get_form(**options)
        parser = MultiPartParser(self.headers, self.stream(), **options)
        try:
            parsed = await parser.parse()
            self._form = FormData([
                (key, TachyonUploadFile.from_starlette(value) if isinstance(value, UploadFile) else value)
                for key, value in parsed.multi_items()
            ])
            return self._form
        except MultiPartException as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc
        finally:
            retained = set()
            if self._form is not None:
                retained = {value.file for _, value in self._form.multi_items() if isinstance(value, UploadFile)}
            # Starlette tracks handles before it can construct FormData. Close
            # every unreturned handle on malformed input, disconnect or cancel.
            for handle in parser._files_to_close_on_error:
                if handle not in retained and not handle.closed:
                    handle.close()
