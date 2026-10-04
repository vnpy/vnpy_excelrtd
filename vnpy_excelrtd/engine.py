"""通过 RPC 发布行情和日志的 Excel RTD 引擎。"""

from vnpy.event import Event, EventEngine
from vnpy.rpc import RpcServer
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.object import TickData, ContractData, LogData, SubscribeRequest
from vnpy.trader.event import EVENT_TICK


APP_NAME: str = "ExcelRtd"

EVENT_RTD_LOG: str = "eRtdLog"

REP_ADDRESS: str = "tcp://*:9001"
PUB_ADDRESS: str = "tcp://*:9002"


class RtdEngine(BaseEngine):
    """
    管理 RTD 对象和数据更新的引擎。
    """

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """启动 RPC 服务并注册行情订阅、日志和 Tick 事件。"""
        super().__init__(main_engine, event_engine, APP_NAME)

        self.server: RpcServer = RpcServer()
        self.server.register(self.subscribe)
        self.server.register(self.write_log)
        self.server.start(REP_ADDRESS, PUB_ADDRESS)

        self.subscribed: set[str] = set()

        self.register_event()

    def register_event(self) -> None:
        """
        注册事件处理函数。
        """
        self.event_engine.register(EVENT_TICK, self.process_tick_event)

    def process_tick_event(self, event: Event) -> None:
        """
        处理 Tick 事件并更新相关 RTD 值。
        """
        tick: TickData = event.data
        self.server.publish("tick", tick)

    def write_log(self, msg: str) -> None:
        """
        输出 RTD 相关日志。
        """
        log: LogData = LogData(msg=msg, gateway_name=APP_NAME)
        event: Event = Event(EVENT_RTD_LOG, log)
        self.event_engine.put(event)

    def subscribe(self, vt_symbol: str) -> None:
        """
        订阅 Tick 数据更新。
        """
        contract: ContractData | None = self.main_engine.get_contract(vt_symbol)
        if not contract:
            return

        if vt_symbol in self.subscribed:
            return
        self.subscribed.add(vt_symbol)

        req: SubscribeRequest = SubscribeRequest(
            contract.symbol,
            contract.exchange
        )
        self.main_engine.subscribe(req, contract.gateway_name)

    def close(self) -> None:
        """停止 RPC 服务并等待其结束。"""
        self.server.stop()
        self.server.join()
