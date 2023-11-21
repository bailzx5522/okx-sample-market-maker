from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import traceback
import os
import math
import time,datetime
from decimal import Decimal
from typing import Any, Tuple, List
from threading import Thread
import enum
import asyncio
from queue import Queue

from db import instruments, option_sum, mark_px_container, orders_container
from market_data_service.WssMarketDataService import WssMarketDataService
from market_data_service.model.Instrument import Instrument
from market_data_service.model.OrderBook import OrderBook
from market_data_service.model.Option import Option
from market_data_service.model.MarkPx import MarkPx
from market_data_service.model.Tickers import Ticker
from order_management_service.model.Order import Order, Orders
from order_management_service.model.OrderRequest import PlaceOrderRequest, AmendOrderRequest, \
    CancelOrderRequest
from strategy.BaseStrategy import BaseStrategy, StrategyOrder, TRADING_INSTRUMENT_ID
from utils.InstrumentUtil import InstrumentUtil
from utils.OkxEnum import TdMode, OrderSide, OrderType, PosSide, InstType
from utils.WsOrderUtil import get_request_uuid
from strategy.logger import logger

@dataclass
class OptionOrder:
    # {'accFillSz': '0', 'algoClOrdId': '', 'algoId': '', 'attachAlgoClOrdId': '', 'avgPx': '', 'cTime': '1699352322327', 'cancelSource': '', 'cancelSourceReason': '', 'category': 'normal', 'ccy': '', 'clOrdId': 'themis288230377353797526', 'fee': '0', 'feeCcy': 'ETH', 'fillPx': '', 'fillSz': '0', 'fillTime': '', 'instId': 'ETH-USD-231108-1920-C', 'instType': 'OPTION', 'lever': '', 'ordId': '642065408258080771', 'ordType': 'limit', 'pnl': '0', 'posSide': 'net', 'px': '0.01', 'pxType': 'px', 'pxUsd': '18.78', 'pxVol': '0.969', 'quickMgnType': '', 'rebate': '0', 'rebateCcy': 'ETH', 'reduceOnly': 'false', 'side': 'sell', 'slOrdPx': '', 'slTriggerPx': '', 'slTriggerPxType': '', 'source': '', 'state': 'live', 'stpId': '', 'stpMode': '', 'sz': '10', 'tag': 'b755055475acBCDE', 'tdMode': 'isolated', 'tgtCcy': '', 'tpOrdPx': '', 'tpTriggerPx': '', 'tpTriggerPxType': '', 'tradeId': '', 'uTime': '1699352322327'}
    inst_id: str = ""
    inst_type: str = ""
    fee: float = 0
    fee_ccy: str = ""
    px: float = 0
    avg_px: float = 0
    sz: float = 0
    side: OrderSide = None
    c_time: int = 0 
    client_order_id: str = ""


    @classmethod
    def init_from_json(cls, json_response):
        order = OptionOrder()
        order.client_order_id = json_response["clOrdId"]
        order.inst_id = json_response["instId"]
        order.px = float(json_response["px"])
        order.avg_px = float(json_response.get("avgPx", 0) if json_response.get("avgPx", 0) else 0)
        order.c_time = int(json_response.get("cTime", 0))
        order.sz = float(json_response.get("sz", 0))
        order.inst_type = json_response.get("instType")
        # order.ccy = json_response["ccy"]
        order.fee = float(json_response.get("fee", 0))
        order.fee_ccy = json_response.get("feeCcy", "")
        return order

    def __eq__(self, other):
        return (self.side == other.side) and (self.inst_id == other.inst_id) \
               and (self.size == other.size) and (self.price == other.price) and (self.ord_type == other.ord_type)

    def get_id(self):
        return f"{self.inst_id}-{self.ord_type.value}-{self.side.value}-{self.size}@{self.price}"

class PlaceOrderType(enum.Enum):
    Mark = 0 # 买单使用max(bid, mark), 卖单使用min(ask, mark), 动态挂单
    Market = 1 # 使用市价挂单
    Spot_price = 2 # 当underlying价格达到某个价格时，使用market下单

class StrategyOrder:
    place_order_type: PlaceOrderType
    sz: int #单位张
    px: float = 0 # 订单价格
    side: OrderSide = None # 订单方向
    inst_id: str = "" # 交易品种id
    inst_type: str = ""  # 交易品种类型


class CommandQueue(Queue):
    def __init__(self):
        super().__init__()


cmd_queue = CommandQueue()

class OptionBot(BaseStrategy):
    def __init__(self, ak, sk, pas):
        super().__init__(api_key=ak, api_key_secret=sk, api_passphrase=pas)
        WSEndpoint2 = "wss://ws.okex.com:8443/ws/v5/"
        self.mds = WssMarketDataService(
            url=WSEndpoint2+"public",
            inst_id=TRADING_INSTRUMENT_ID,
            inst_list=[],
            channel="tickers",
            mark_cb=self.mark_cb,
            ticker_cb=self.ticker_cb
        )

        # CONFIG
        self.strategy_orders = ["buy,btc-usd-231108-1880-c".upper()]
        self.place_order_type = PlaceOrderType.Mark

    def mark_cb(self, mark: dict):
        # mark_px:MarkPx = mark_px_container[0].get_mark_px(o.inst_id)
        logger.debug(f"new mark:{mark}")
        pass

    def ticker_cb(self, ticker: dict):
        # logger.debug("new ticker")
        pass

    def check_placed_orders(self):
        tickers = self.get_tickers()
        # logger.debug(f"mark price {tickers.get_ticker_by_inst_id()}")
        # logger.debug(f"mark price {tickers.get_ticker_by_inst_id()}")

    def order_operation_decision(self):
        if not cmd_queue.empty():
            cmd = cmd_queue.get()
            logger.debug(f"got cmd from tg {cmd}")
        order_book = self.get_order_book()
        tickers = self.get_tickers()
        self.get_mark_price()
        activate_orders =  self.get_orders().get_active_orders()
        logger.info(f"activate orders : {len(activate_orders)}")
        mark_px_cache = mark_px_container[0]

        to_place_orders = self.strategy_orders.copy()
        for oid, o in activate_orders.items():
            mark_px:MarkPx = mark_px_cache.get_mark_px(o.inst_id)
            ticker = tickers.get_ticker_by_inst_id(o.inst_id)
            if ticker:
                logger.debug(f"inst_id:{o.inst_id}, ask:{ticker.ask_px}, bid:{ticker.bid_px}, mark:{mark_px.mark_px}, order:{o.px}")
            elif o.inst_id not in self.mds.inst_list:
                self.mds.inst_list.append(o.inst_id)
                self.mds.sub_more([o.inst_id], "mark-price")
                self.mds.sub_more([o.inst_id], "tickers")
                logger.info(f"sub more mark-price inst_id {o.inst_id}")
            continue
            if mark_px != o.px:
                print("amend order ", o.px, mark_px)

            to_place_orders.append(OptionOrder(inst_id=o.inst_id))
        # print("tickers", tickers)
        # print(order_book.best_ask_price())
        # print(order_book.best_ask())
        return None, None, None

    def _get_sub_inst(self):
        date_now = datetime.date.today()
        sub_inst = []
        eth_uly = 'ETH-USD'
        ins = self.rest_mds.public_api.get_instruments(instType="OPTION",uly=eth_uly)
        def get_inst_list(ins):
            ret = []
            for i in ins.get('data'):
                inst_id = i.get('instId')
                _, _, ex_date, px, opt_type = inst_id.split("-")
                # print(inst_id, date, px, opt_type)
                ex_date = datetime.datetime.strptime(ex_date, '%y%m%d')
                if ex_date.date() - date_now > datetime.timedelta(days=31):
                    continue
                ret.append(inst_id)
            return ret
        eth_inst_list = get_inst_list(ins)
        sub_inst.extend(eth_inst_list)

        eth_uly = 'BTC-USD'
        ins = self.rest_mds.public_api.get_instruments(instType="OPTION",uly=eth_uly)
        sub_inst.extend(get_inst_list(ins))

        sub_inst = []

        WSEndpoint2 = "wss://ws.okex.com:8443/ws/v5/"
        self.mds = WssMarketDataService(
            url=WSEndpoint2+"public",
            inst_id=TRADING_INSTRUMENT_ID,
            inst_list=sub_inst,
            channel="tickers"
        )
        return sub_inst

    def _init_orders(self,):
        to_cancel = []
        orders = self.trade_api.get_order_list()
        for o in orders['data']:
            oo = OptionOrder.init_from_json(o)
            if oo.inst_type != InstType.OPTION or "ss" not in oo.client_order_id:
                continue
            inst_id = oo.inst_id
            cancel_req = CancelOrderRequest(inst_id=inst_id, client_order_id=oo.client_order_id)
            to_cancel.append(cancel_req)
 
            self.cancel_orders(to_cancel)
            print("cancel client option orders", oo)

    def _run_commander(self):
        _thread = Thread(target=start_bot, args=())
        _thread.start()

    def run(self):
        self._set_account_config()
        self.trading_instrument_type = self.trading_instrument_type()
        ins = InstrumentUtil.get_instrument(TRADING_INSTRUMENT_ID, self.trading_instrument_type)
        self.set_strategy_measurement(trading_instrument=TRADING_INSTRUMENT_ID,
                                      trading_instrument_type=self.trading_instrument_type)
        # inst_to_sub = self._get_sub_inst()
        self._init_orders()
        self._run_exchange_connection()
        self._run_commander()
        while 1:
            try:
                # exchange_normal = self.check_status()
                # if not exchange_normal:
                #     raise ValueError("There is a ongoing maintenance in OKX.")
                # self.get_params()
                # result = self._health_check()
                # # self.risk_summary()
                # if not result:
                #     print(f"Health Check result is {result}")
                #     time.sleep(5)
                #     continue
                # summary
                # self._update_strategy_order_status()
                place_order_list, amend_order_list, cancel_order_list = self.order_operation_decision()
                # print(place_order_list)
                # print(amend_order_list)
                # print(cancel_order_list)

                # self.place_orders(place_order_list)
                # self.amend_orders(amend_order_list)
                # self.cancel_orders(cancel_order_list)

                time.sleep(1)
            except:
                print(traceback.format_exc())
                try:
                    self.cancel_all()
                except:
                    print(f"Failed to cancel orders: {traceback.format_exc()}")
                time.sleep(20)



from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = {"msg": update.effective_message.text}
    print("-----------------------got hello", data)
    cmd_queue.put(data)
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

async def make_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = {"msg": update.effective_message.text}
    cmd_queue.put(data)
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

async def order_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    orders = OptionBot.get_orders()
    print(orders)
    await update.message.reply_text(f'order {update.effective_user.first_name}')


def start_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        print("-----------------------start bot callback")
        token = "1487299749:AAHwGvOysVg4bA3ltzccV68U7EmFJdLp7Mo"
        app = ApplicationBuilder().token(token).build()
        app.add_handler(CommandHandler("hello", hello))
        app.add_handler(CommandHandler("list", order_list))
        app.add_handler(CommandHandler("order", make_order))
        app.add_handler(CommandHandler("order", make_order))

        loop.run_until_complete(app.initialize())
        loop.run_until_complete(app.updater.start_polling())
        loop.run_until_complete(app.start())
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.debug("Application received stop signal. Shutting down.")
    except Exception as exc:
        # In case the coroutine wasn't awaited, we don't need to bother the user with a warning
        # updater_coroutine.close()
        raise exc
    finally:
        # We arrive here either by catching the exceptions above or if the loop gets stopped
        try:
            # Mypy doesn't know that we already check if updater is None
            if app.updater.running:  # type: ignore[union-attr]
                loop.run_until_complete(self.updater.stop())  # type: ignore[union-attr]
            # if self.running:
            #     loop.run_until_complete(self.stop())
            # if self.post_stop:
            #     loop.run_until_complete(self.post_stop(self))
            # loop.run_until_complete(self.shutdown())
            # if self.post_shutdown:
            #     loop.run_until_complete(self.post_shutdown(self))
        finally:
            # if close_loop:
            loop.close()