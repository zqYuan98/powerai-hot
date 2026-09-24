"""SQL 小工具。"""


def escape_like(term: str) -> str:
    """转义 LIKE/ILIKE 通配符，配合 `.ilike(pattern, escape="\\\\")` 使用。

    防止用户输入的 % _ 变成通配符（如 q='%' 匹配全库、放大检索成本）。
    """
    return (term or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
