"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file
"""
import builtins
import google.protobuf.descriptor
import google.protobuf.descriptor_pb2
import google.protobuf.internal.containers
import google.protobuf.internal.extension_dict
import google.protobuf.message
import typing
import typing_extensions

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor

class ApiRule(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor
    GET_FIELD_NUMBER: builtins.int
    PUT_FIELD_NUMBER: builtins.int
    POST_FIELD_NUMBER: builtins.int
    DELETE_FIELD_NUMBER: builtins.int
    PATCH_FIELD_NUMBER: builtins.int
    CUSTOM_FIELD_NUMBER: builtins.int
    ANY_FIELD_NUMBER: builtins.int
    BODY_FIELD_NUMBER: builtins.int
    RESPONSE_BODY_FIELD_NUMBER: builtins.int
    ADDITIONAL_BINDINGS_FIELD_NUMBER: builtins.int
    GROUP_FIELD_NUMBER: builtins.int
    TAG_FIELD_NUMBER: builtins.int
    SUMMARY_FIELD_NUMBER: builtins.int
    DESC_FIELD_NUMBER: builtins.int
    NOT_ENABLE_FIELD_NUMBER: builtins.int
    AUTHOR_FIELD_NUMBER: builtins.int
    @property
    def get(self) -> global___HttpMethod:
        """Maps to HTTP GET. Used for listing and getting information about
        resources.
        """
        pass
    @property
    def put(self) -> global___HttpMethod:
        """Maps to HTTP PUT. Used for replacing a resource."""
        pass
    @property
    def post(self) -> global___HttpMethod:
        """Maps to HTTP POST. Used for creating a resource or performing an action."""
        pass
    @property
    def delete(self) -> global___HttpMethod:
        """Maps to HTTP DELETE. Used for deleting a resource."""
        pass
    @property
    def patch(self) -> global___HttpMethod:
        """Maps to HTTP PATCH. Used for updating a resource."""
        pass
    @property
    def custom(self) -> global___CustomHttpPattern:
        """The custom pattern is used for specifying an HTTP method that is not
        included in the `pattern` field, such as HEAD, or "*" to leave the
        HTTP method unspecified for this rule. The wild-card rule is useful
        for services that provide content to Web (HTML) clients.
        """
        pass
    @property
    def any(self) -> global___HttpMethod:
        """Automatically generated by gRPC Gateway"""
        pass
    body: typing.Text
    """The name of the request field whose value is mapped to the HTTP request
    body, or `*` for mapping all request fields not captured by the path
    pattern to the HTTP body, or omitted for not having any HTTP request body.

    NOTE: the referred field must be present at the top-level of the request
    message type.
    """

    response_body: typing.Text
    """Optional. The name of the response field whose value is mapped to the HTTP
    response body. When omitted, the entire response message will be used
    as the HTTP response body.

    NOTE: The referred field must be present at the top-level of the response
    message type.
    """

    @property
    def additional_bindings(self) -> google.protobuf.internal.containers.RepeatedCompositeFieldContainer[global___ApiRule]:
        """Additional HTTP bindings for the selector. Nested bindings must
        not contain an `additional_bindings` field themselves (that is,
        the nesting may only be one level deep).
        """
        pass
    group: typing.Text
    """the group to which the method belongs"""

    @property
    def tag(self) -> google.protobuf.internal.containers.RepeatedCompositeFieldContainer[global___Tag]:
        """The tag corresponding to this method and the description of the tag"""
        pass
    summary: typing.Text
    """a summary of the method"""

    desc: typing.Text
    """documentation for the use of this method"""

    not_enable: builtins.bool
    """whether to map the method"""

    @property
    def author(self) -> google.protobuf.internal.containers.RepeatedScalarFieldContainer[typing.Text]:
        """Write the author of the API"""
        pass
    def __init__(self,
        *,
        get: typing.Optional[global___HttpMethod] = ...,
        put: typing.Optional[global___HttpMethod] = ...,
        post: typing.Optional[global___HttpMethod] = ...,
        delete: typing.Optional[global___HttpMethod] = ...,
        patch: typing.Optional[global___HttpMethod] = ...,
        custom: typing.Optional[global___CustomHttpPattern] = ...,
        any: typing.Optional[global___HttpMethod] = ...,
        body: typing.Text = ...,
        response_body: typing.Text = ...,
        additional_bindings: typing.Optional[typing.Iterable[global___ApiRule]] = ...,
        group: typing.Text = ...,
        tag: typing.Optional[typing.Iterable[global___Tag]] = ...,
        summary: typing.Text = ...,
        desc: typing.Text = ...,
        not_enable: builtins.bool = ...,
        author: typing.Optional[typing.Iterable[typing.Text]] = ...,
        ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["any",b"any","custom",b"custom","delete",b"delete","get",b"get","http_method",b"http_method","patch",b"patch","post",b"post","put",b"put"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["additional_bindings",b"additional_bindings","any",b"any","author",b"author","body",b"body","custom",b"custom","delete",b"delete","desc",b"desc","get",b"get","group",b"group","http_method",b"http_method","not_enable",b"not_enable","patch",b"patch","post",b"post","put",b"put","response_body",b"response_body","summary",b"summary","tag",b"tag"]) -> None: ...
    def WhichOneof(self, oneof_group: typing_extensions.Literal["http_method",b"http_method"]) -> typing.Optional[typing_extensions.Literal["get","put","post","delete","patch","custom","any"]]: ...
global___ApiRule = ApiRule

class CustomHttpPattern(google.protobuf.message.Message):
    """A custom pattern is used for defining custom HTTP verb."""
    DESCRIPTOR: google.protobuf.descriptor.Descriptor
    KIND_FIELD_NUMBER: builtins.int
    PATH_FIELD_NUMBER: builtins.int
    @property
    def kind(self) -> global___HttpMethod:
        """The name of this custom HTTP verb."""
        pass
    @property
    def path(self) -> global___HttpMethod:
        """The path matched by this custom verb."""
        pass
    def __init__(self,
        *,
        kind: typing.Optional[global___HttpMethod] = ...,
        path: typing.Optional[global___HttpMethod] = ...,
        ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["kind",b"kind","path",b"path"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["kind",b"kind","path",b"path"]) -> None: ...
global___CustomHttpPattern = CustomHttpPattern

class Tag(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor
    NAME_FIELD_NUMBER: builtins.int
    DESC_FIELD_NUMBER: builtins.int
    name: typing.Text
    desc: typing.Text
    def __init__(self,
        *,
        name: typing.Text = ...,
        desc: typing.Text = ...,
        ) -> None: ...
    def ClearField(self, field_name: typing_extensions.Literal["desc",b"desc","name",b"name"]) -> None: ...
global___Tag = Tag

class HttpMethod(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor
    URL_FIELD_NUMBER: builtins.int
    DEFAULT_FIELD_NUMBER: builtins.int
    url: typing.Text
    """The specified http url, if empty, it will be generated by gRPC Gateway
    example: /api/user/create
             /api/user/delete
    """

    default: builtins.bool
    """If the value is True, the url is the url corresponding to the rpc method"""

    def __init__(self,
        *,
        url: typing.Text = ...,
        default: builtins.bool = ...,
        ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal["default",b"default","http_url",b"http_url","url",b"url"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal["default",b"default","http_url",b"http_url","url",b"url"]) -> None: ...
    def WhichOneof(self, oneof_group: typing_extensions.Literal["http_url",b"http_url"]) -> typing.Optional[typing_extensions.Literal["url","default"]]: ...
global___HttpMethod = HttpMethod

HTTP_FIELD_NUMBER: builtins.int
http: google.protobuf.internal.extension_dict._ExtensionFieldDescriptor[google.protobuf.descriptor_pb2.MethodOptions, global___ApiRule]
"""design like google.api.http"""
