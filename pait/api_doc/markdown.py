import json
from types import CodeType
from typing import Any, Dict, List, Optional

from pydantic.fields import Undefined

from ..model import PaitStatus
from .base_parse import PaitBaseParse


json_type_default_value_dict: Dict[str, Any] = {
    "null": None,
    "bool": True,
    "string": "",
    "float": 0.0,
    "integer": 0,
    "object": {},
    "array": [],
}


class PaitMd(PaitBaseParse):
    def __init__(self, title: str = "Pait Doc", use_html_details: bool = True, filename: Optional[str] = None):
        self._use_html_details: bool = use_html_details  # some not support markdown in html
        self._title: str = title
        super().__init__()

        markdown_text: str = self.gen_markdown_text()
        self.output(filename, markdown_text, ".md")

    @staticmethod
    def gen_example_json(field_dict_list: List[dict], blank_num: int) -> str:
        example_dict: dict = {}
        for field_dict in field_dict_list:
            sub_dict: dict = example_dict
            key: str = field_dict["param_name"]
            if '.' in key:
                key_list: List[str] = key.split(".")
                for sub_key in key_list:
                    key = sub_key
                    if sub_key == key_list[-1]:
                        continue
                    if sub_key not in sub_dict:
                        sub_dict[sub_key] = {}
                    sub_dict = sub_dict[sub_key]
            type_: str = field_dict["type"]
            sub_dict[key] = json_type_default_value_dict[type_]
        json_str: str = f"\n".join(
            [" " * blank_num + i for i in json.dumps(example_dict, indent=2).split('\n')]
        )
        return f"{' ' * blank_num}```json\n" \
               f"{json_str}\n" \
               f"{' ' * blank_num}```\n\n"

    @staticmethod
    def gen_md_param_table(field_dict_list: List[dict], blank_num: int = 8) -> str:
        markdown_text: str = f"{' ' * blank_num}|param name|type|default value|description|other|\n"
        markdown_text += f"{' ' * blank_num}|---|---|---|---|---|\n"
        field_dict_list = sorted(field_dict_list, key=lambda x: x["param_name"])
        for field_info_dict in field_dict_list:
            default = field_info_dict["default"]
            if default is Undefined:
                default = "**`Required`**"
            description = field_info_dict["description"]
            markdown_text += (
                f"{' ' * blank_num}|{field_info_dict['param_name']}"
                f"|{field_info_dict['type']}"
                f"|{default}"
                f"|{description}"
                f"|{field_info_dict['other']}"
                f"|\n"
            )
        return markdown_text

    def gen_markdown_text(self) -> str:
        markdown_text: str = f"# {self._title}\n"
        for group in self._group_list:
            # group
            if self._use_html_details:
                markdown_text += f"<details><summary>Group: {group}</summary>\n\n"
            else:
                markdown_text += f"## Group: {group}\n\n"
            for pait_model in self._group_pait_dict[group]:
                # func info
                markdown_text += f"### Name: {pait_model.operation_id}\n\n"
                status_text: str = ""
                if pait_model.status in (PaitStatus.test, PaitStatus.design, PaitStatus.dev, PaitStatus.integration):
                    status_text = f"<font color=#00BFFF>{pait_model.status.value}</font>"
                elif pait_model.status in (PaitStatus.release, PaitStatus.complete):
                    status_text = f"<font color=#32CD32>{pait_model.status.value}</font>"
                elif pait_model.status in (PaitStatus.abandoned, PaitStatus.abnormal):
                    status_text = f"<font color=#DC143C>{pait_model.status.value}</font>"
                elif pait_model.status:
                    status_text = f"{pait_model.status.value}"

                func_code: CodeType = pait_model.func.__code__
                markdown_text += f"|Author|Status|func|description|\n"
                markdown_text += f"|---|---|---|---|\n"
                markdown_text += (
                    f"|{','.join(pait_model.author)}"
                    f"|{status_text}"
                    f'|<abbr title="file:{func_code.co_filename};line: {func_code.co_firstlineno}">'
                    f'{pait_model.func.__qualname__}</abbr>'
                    f"|{pait_model.desc}|\n"
                )

                # request info
                markdown_text += f"- Path: {pait_model.path}\n"
                markdown_text += f"- Method: {','.join(pait_model.method_set)}\n"
                markdown_text += f"- Request:\n"

                field_dict: Dict[str, List[Dict[str, Any]]] = self._parse_func_param(pait_model.func)
                field_key_list: List[str] = sorted(field_dict.keys())
                # request body info
                for field in field_key_list:
                    field_dict_list = field_dict[field]
                    markdown_text += f"{' ' * 4}- {field.capitalize()} Param\n\n"
                    markdown_text += self.gen_md_param_table(field_dict_list)

                # response info
                markdown_text += f"- Response:\n\n"
                if pait_model.response_model_list:
                    for resp_model_class in pait_model.response_model_list:
                        resp_model = resp_model_class()
                        markdown_text += f"{' ' * 4}- {resp_model.name}\n\n"
                        markdown_text += f"{' ' * 8}|status code|media type|description|\n"
                        markdown_text += f"{' ' * 8}|---|---|---|\n"
                        markdown_text += (
                            f"{' ' * 8}|{','.join([str(i) for i in resp_model.status_code])}"
                            f"|{resp_model.media_type}"
                            f"|{resp_model.description}"
                            f"|\n"
                        )
                        if resp_model.header:
                            markdown_text += f"{' ' * 8}- Header\n"
                            markdown_text += f"{' ' * 12}{resp_model.header}\n"
                        if resp_model.response_data:
                            markdown_text += f"{' ' * 8}- Data\n\n"
                            schema_dict: dict = resp_model.response_data.schema()
                            field_dict_list = self._parse_schema(schema_dict)
                            markdown_text += self.gen_md_param_table(field_dict_list, blank_num=12)
                            markdown_text += f"{' ' * 8}- Example Response Data Json\n\n"
                            markdown_text += self.gen_example_json(field_dict_list, blank_num=12)
                markdown_text += "\n"
            if self._use_html_details:
                markdown_text += "</details>"
        return markdown_text
