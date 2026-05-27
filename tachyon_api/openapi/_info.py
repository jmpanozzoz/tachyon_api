# OpenAPI `info` block — Contact, License, and Info dataclasses.

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Contact:
    name: Optional[str] = None
    url: Optional[str] = None
    email: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v
            for k, v in {"name": self.name, "url": self.url, "email": self.email}.items()
            if v
        }


@dataclass
class License:
    name: str
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"name": self.name}
        if self.url:
            result["url"] = self.url
        return result


@dataclass
class Info:
    title: str = "Tachyon API"
    description: Optional[str] = "A fast API built with Tachyon"
    version: str = "0.1.0"
    terms_of_service: Optional[str] = None
    contact: Optional[Contact] = None
    license: Optional[License] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"title": self.title, "version": self.version}
        if self.description:
            result["description"] = self.description
        if self.terms_of_service:
            result["termsOfService"] = self.terms_of_service
        if self.contact:
            result["contact"] = self.contact.to_dict()
        if self.license:
            result["license"] = self.license.to_dict()
        return result
