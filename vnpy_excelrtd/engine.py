from typing import Set, Optional

from vnpy.event import Event, EventEngine
from vnpy.rpc import RpcServer
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.object import TickData, ContractData, LogData, SubscribeRequest
from vnpy.trader.event import EVENT_TICK


APP_NAME = "ExcelRtd"

EVENT_RTD_LOG = "eRtdLog"

REP_ADDRESS = "tcp://*:9001"
PUB_ADDRESS = "tcp://*:9002"


class RtdEngine(BaseEngine):
    """
    The engine for managing RTD objects and data update.
    """

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """"""
        super().__init__(main_engine, event_engine, APP_NAME)

        self.server: RpcServer = RpcServer()
        self.server.register(self.subscribe)
        self.server.register(self.write_log)
        self.server.start(REP_ADDRESS, PUB_ADDRESS)

        self.subscribed: Set[str] = set()

        self.register_event()

    def register_event(self) -> None:
        """
        Register event handler.
        """
        self.event_engine.register(EVENT_TICK, self.process_tick_event)

    def process_tick_event(self, event: Event) -> None:
        """
        Process tick event and update related RTD value.
        """
        tick: TickData = event.data
        self.server.publish("tick", tick)

    def write_log(self, msg: str) -> None:
        """
        Output RTD related log message.
        """
        log: LogData = LogData(msg=msg, gateway_name=APP_NAME)
        event: Event = Event(EVENT_RTD_LOG, log)
        self.event_engine.put(event)

    def subscribe(self, vt_symbol: str) -> None:
        """
        Subscribe tick data update.
        """
        contract: Optional[ContractData] = self.main_engine.get_contract(vt_symbol)
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
        """"""
        self.server.stop()
        self.server.join()
