"""generate.py facade 的執行期橋接。

拆出去的流程模組(client / video_* / image_capabilities / tasks / cli)仍要讓舊呼叫端與測試
對 ``generate.<名稱>`` 的打補丁(``mock.patch.object(generate, "submit_and_wait")``)和改值
(``generate.DEVICE = ...``、``generate.ACTIVE_VIDEO_CONFIG``)生效。做法:generate 載入時與每次
``main()`` 開頭呼叫 ``bind(globals())``,這些模組裡「會被覆寫的名稱」一律寫成 ``rt.<名稱>``,
在呼叫當下才去 generate 的命名空間查,行為與函式還放在 generate.py 時一致。

規則:
- 編排層(cli.py、tasks/*)呼叫的協作者一律走 ``rt``。
- 葉節點模組只有「測試或舊呼叫端會覆寫」的名稱與狀態走 ``rt``,其餘直接 import。
"""


class _Facade:
    __slots__ = ()

    def __getattr__(self, name):
        try:
            return _namespace()[name]
        except KeyError:
            raise AttributeError(f"generate facade 沒有 {name!r}") from None

    def __setattr__(self, name, value):
        _namespace()[name] = value


_bound = None


def bind(namespace):
    """登記 facade 的命名空間(傳入 generate 模組的 ``globals()``,會即時反映修改)。"""
    global _bound
    _bound = namespace


def _namespace():
    if _bound is None:
        raise RuntimeError("generate facade 尚未綁定；請透過 generate.py 進入")
    return _bound


facade = _Facade()
