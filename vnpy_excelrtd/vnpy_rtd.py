"""供 Excel RTD 调用的行情客户端。"""
from collections import defaultdict
from typing import Any

from pyxll import RTD, xl_func

from vnpy.rpc import RpcClient
from vnpy.trader.object import TickData


REQ_ADDRESS = "tcp://localhost:9001"
SUB_ADDRESS = "tcp://localhost:9002"


rtd_client: "RtdClient" | None = None


class ObjectRtd(RTD):
    """
    Python 对象的 RTD 代理。
    """

    def __init__(self, engine: "RtdClient", name: str, field: str) -> None:
        """构造函数。"""
        super().__init__(value=0)

        self.engine: RtdClient = engine
        self.name: str = name
        self.field: str = field
        self.value: Any = 0

    def connect(self) -> None:
        """
        Excel 单元格 RTD 连接时的回调。
        """
        self.engine.add_rtd(self)

    def disconnect(self) -> None:
        """
        Excel 单元格 RTD 断开时的回调。
        """
        self.engine.remove_rtd(self)

    def update(self, data: object) -> None:
        """
        更新 Excel 单元格中的值。
        """
        new_value = getattr(data, self.field, "N/A")

        if new_value != self.value:
            self.value = new_value


class RtdClient(RpcClient):
    """
    管理 RTD 对象和数据更新的引擎。
    """

    def __init__(self) -> None:
        """初始化 RTD 集合并把自身登记为全局客户端。"""
        super().__init__()

        self.rtds: dict[str, set[ObjectRtd]] = defaultdict(set)

        global rtd_client
        rtd_client = self

    def callback(self, topic: str, data: object) -> None:
        """按 Tick 的本地代码更新已登记的 RTD。"""
        tick: TickData = data
        buf: set[ObjectRtd] = self.rtds[tick.vt_symbol]

        for rtd in buf:
            rtd.update(tick)

    def add_rtd(self, rtd: ObjectRtd) -> None:
        """
        把新的 RTD 加入引擎。
        """
        buf: set[ObjectRtd] = self.rtds[rtd.name]
        buf.add(rtd)
        self.write_log(f"新增RTD连接：{rtd.name} {rtd.field}")

        # Auto subscribe tick data
        self.subscribe(rtd.name)

    def remove_rtd(self, rtd: ObjectRtd) -> None:
        """
        从引擎移除已有 RTD。
        """
        buf: set[ObjectRtd] = self.rtds[self.name]
        if self in buf:
            buf.remove(rtd)
            self.write_log(f"移除RTD连接：{rtd.name} {rtd.field}")


def init_client() -> None:
    """初始化 VeighNa RTD 客户端。"""
    global rtd_client
    rtd_client = RtdClient()
    rtd_client.subscribe_topic("")
    rtd_client.start(REQ_ADDRESS, SUB_ADDRESS)


@xl_func("string vt_symbol, string field: rtd")    # type: ignore
def rtd_tick_data(vt_symbol: str, field: str) -> ObjectRtd:
    """
    返回 Tick 字段的实时值。
    """
    if not rtd_client:
        init_client()

    rtd = ObjectRtd(rtd_client, vt_symbol, field)  # type: ignore
    return rtd
