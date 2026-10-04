import sys
import types
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace

from vnpy.trader.constant import Exchange, Product
from vnpy.trader.object import ContractData, SubscribeRequest

from vnpy_excelrtd.engine import RtdEngine


RTD_PATH: Path = Path(__file__).resolve().parent.parent.joinpath("vnpy_excelrtd", "vnpy_rtd.py")


class FakeMainEngine:
    def __init__(self, contract: ContractData) -> None:
        self.contract: ContractData = contract
        self.requests: list[tuple[SubscribeRequest, str]] = []

    def get_contract(self, vt_symbol: str) -> ContractData | None:
        if vt_symbol == self.contract.vt_symbol:
            return self.contract
        return None

    def subscribe(self, req: SubscribeRequest, gateway_name: str) -> None:
        self.requests.append((req, gateway_name))


def load_rtd_module() -> ModuleType:
    # vnpy_rtd.py 导入时依赖 pyxll。按文件路径加载，并用桩替换 pyxll，这样不启动 Excel。
    # 源文件里的 rtd_client 注解会在导入时求值并抛出 TypeError。这里只在内存副本前插入
    # future 注解，不改源码，以便继续调用 ObjectRtd.update。
    fake: ModuleType = types.ModuleType("pyxll")

    class RTD:
        def __init__(self, value: object = None) -> None:
            self.value: object = value

    def xl_func(signature: str) -> Callable[[Callable], Callable]:
        def decorate(func: Callable) -> Callable:
            return func

        return decorate

    fake.RTD = RTD  # type: ignore[attr-defined]
    fake.xl_func = xl_func  # type: ignore[attr-defined]

    previous: ModuleType | None = sys.modules.get("pyxll")
    sys.modules["pyxll"] = fake
    source: str = RTD_PATH.read_text(encoding="utf-8")
    docstring: str = '"""供 Excel RTD 调用的行情客户端。"""'
    if not source.startswith(docstring):
        raise AssertionError(source.splitlines()[0])
    source = source.replace(
        docstring,
        docstring + "\nfrom __future__ import annotations\n",
        1,
    )
    module: ModuleType = types.ModuleType("vnpy_rtd_offline")
    module.__file__ = str(RTD_PATH)
    try:
        exec(compile(source, str(RTD_PATH), "exec"), module.__dict__)
    finally:
        if previous is None:
            sys.modules.pop("pyxll", None)
        else:
            sys.modules["pyxll"] = previous
    return module


def test_subscribe_converts_contract_symbol() -> None:
    # 不调用 RtdEngine()：__init__ 会绑定 tcp://*:9001 和 tcp://*:9002。
    contract: ContractData = ContractData(
        gateway_name="TEST",
        symbol="rb2510",
        exchange=Exchange.SHFE,
        name="rb2510",
        product=Product.FUTURES,
        size=10,
        pricetick=1,
    )
    main: FakeMainEngine = FakeMainEngine(contract)
    engine: RtdEngine = RtdEngine.__new__(RtdEngine)
    engine.main_engine = main
    engine.subscribed = set()

    engine.subscribe("rb2510.SHFE")

    assert engine.subscribed == {"rb2510.SHFE"}
    assert len(main.requests) == 1
    req, gateway_name = main.requests[0]
    assert req.symbol == "rb2510"
    assert req.exchange == Exchange.SHFE
    assert req.vt_symbol == "rb2510.SHFE"
    assert gateway_name == "TEST"

    engine.subscribe("rb2510.SHFE")
    assert len(main.requests) == 1

    engine.subscribe("ag2506.SHFE")
    assert engine.subscribed == {"rb2510.SHFE"}
    assert len(main.requests) == 1


def test_object_rtd_update_reads_named_field() -> None:
    module: ModuleType = load_rtd_module()
    rtd: object = module.ObjectRtd(None, "rb2510.SHFE", "last_price")

    assert rtd.name == "rb2510.SHFE"
    assert rtd.field == "last_price"
    assert rtd.value == 0

    rtd.update(SimpleNamespace(last_price=3510.5))
    assert rtd.value == 3510.5

    rtd.update(SimpleNamespace(last_price=3510.5))
    assert rtd.value == 3510.5

    rtd.update(SimpleNamespace(last_price=3512))
    assert rtd.value == 3512

    missing: object = module.ObjectRtd(None, "rb2510.SHFE", "bid_price_1")
    missing.update(SimpleNamespace(last_price=3510.5))
    assert missing.value == "N/A"
