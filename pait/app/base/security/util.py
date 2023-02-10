from typing import Optional, Tuple

from pait.field import BaseField


def set_and_check_field(pait_field: BaseField, alias: str, not_authenticated_exc: Optional[Exception] = None) -> None:
    if pait_field.alias is not None:
        raise ValueError("Custom alias parameters are not allowed")
    if pait_field.not_value_exception is not None:
        raise ValueError("Custom not_value_exception parameters are not allowed")
    pait_field.set_alias(alias)
    if not_authenticated_exc:
        pait_field.not_value_exception = not_authenticated_exc


def get_authorization_scheme_param(authorization_header_value: str) -> Tuple[str, str]:
    if not authorization_header_value:
        return "", ""
    scheme, _, param = authorization_header_value.partition(" ")
    return scheme, param
