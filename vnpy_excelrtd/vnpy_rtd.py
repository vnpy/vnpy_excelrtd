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
    RTD proxy for object in Python.
    """

    def __init__(self, engine: "RtdClient", name: str, field: str) -> None:
        """Constructor"""
        super().__init__(value=0)

        self.engine: RtdClient = engine
        self.name: str = name
        self.field: str = field
        self.value: Any = 0

    def connect(self) -> None:
        """
        Callback when excel cell rtd is connected.
        """
        self.engine.add_rtd(self)

    def disconnect(self) -> None:
        """
        Callback when excel cell rtd is disconncted.
        """
        self.engine.remove_rtd(self)

    def update(self, data: object) -> None:
        """
        Update value in excel cell.
        """
        new_value = getattr(data, self.field, "N/A")

        if new_value != self.value:
            self.value = new_value


class RtdClient(RpcClient):
    """
    The engine for managing RTD objects and data update.
    """

    def __init__(self) -> None:
        """"""
        super().__init__()

        self.rtds: dict[str, set[ObjectRtd]] = defaultdict(set)

        global rtd_client
        rtd_client = self

    def callback(self, topic: str, data: object) -> None:
        """"""
        tick: TickData = data
        buf: set[ObjectRtd] = self.rtds[tick.vt_symbol]

        for rtd in buf:
            rtd.update(tick)

    def add_rtd(self, rtd: ObjectRtd) -> None:
        """
        Add a new RTD into the engine..
        """
        buf: set[ObjectRtd] = self.rtds[rtd.name]
        buf.add(rtd)
        self.write_log(f"新增RTD连接：{rtd.name} {rtd.field}")

        # Auto subscribe tick data
        self.subscribe(rtd.name)

    def remove_rtd(self, rtd: ObjectRtd) -> None:
        """
        Remove an existing RTD from the engine.
        """
        buf: set[ObjectRtd] = self.rtds[self.name]
        if self in buf:
            buf.remove(rtd)
            self.write_log(f"移除RTD连接：{rtd.name} {rtd.field}")


def init_client() -> None:
    """Initialize vnpy rtd client"""
    global rtd_client
    rtd_client = RtdClient()
    rtd_client.subscribe_topic("")
    rtd_client.start(REQ_ADDRESS, SUB_ADDRESS)


@xl_func("string vt_symbol, string field: rtd")    # type: ignore
def rtd_tick_data(vt_symbol: str, field: str) -> ObjectRtd:
    """
    Return the streaming value of the tick data field.
    """
    if not rtd_client:
        init_client()

    rtd = ObjectRtd(rtd_client, vt_symbol, field)  # type: ignore
    return rtd
