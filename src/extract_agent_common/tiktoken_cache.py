"""tiktoken 离线缓存管理

预下载的编码文件存放在 extract_agent_common/data/tiktoken/ 下，
文件名为 URL 的 SHA1 hash（tiktoken 内部缓存格式）。

调用 ensure_tiktoken_cache() 即可设置 TIKTOKEN_CACHE_DIR 环境变量，
避免运行时从 openaipublic.blob.core.windows.net 下载（可能因网络/SSL 失败）。
"""

import os
from importlib.resources import files


def ensure_tiktoken_cache() -> None:
    """设置 TIKTOKEN_CACHE_DIR 指向包内预下载的编码文件。

    使用 setdefault，不会覆盖用户已有的设置。
    """
    data_dir = files("extract_agent_common") / "data" / "tiktoken"
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(data_dir))
