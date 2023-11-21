import threading
from typing import Dict, List
import time
from db import order_books, option_sum, tickers_container, mark_px_container
from market_data_service.model.OrderBook import OrderBook, OrderBookLevel
from market_data_service.model.Option import Option
from market_data_service.model.Tickers import Tickers
from market_data_service.model.MarkPx import MarkPxCache
from okx.websocket.WsPublic import WsPublic


class WssMarketDataService(WsPublic):
    def __init__(self, url, inst_id, channel="books5", inst_list=[], ticker_cb=None, mark_cb=None):
        super().__init__(url)
        self.inst_id = inst_id
        self.inst_list = inst_list
        self.channel = channel
        order_books[self.inst_id] = OrderBook(inst_id=inst_id)
        self.args = []
        self.ticker_cb = ticker_cb
        self.mark_cb = mark_cb
        if not mark_px_container:
            mark_px_container.append(MarkPxCache())

    def _callback(self, message):
        arg = message.get("arg")
        # print(message)
        if not arg or not arg.get("channel"):
            return
        if message.get("event") == "subscribe":
            return
        if arg.get("channel") in ["books5", "books", "bbo-tbt", "books50-l2-tbt", "books-l2-tbt"]:
            on_orderbook_snapshot_or_update(message)
            # print(order_books)
        elif arg.get("channel") == "estimated-price":
            # print("exercise", message)
            pass
        elif arg.get("channel") == "option-trades":
            # print("opt-trades", message)
            pass
        elif arg.get("channel") == "opt-summary":
            on_option_sum_update(message)
        elif arg.get("channel") == "tickers":
            self.on_ticker_sub(message)
        elif arg.get("channel") == "mark-price":
            self.on_mark_price(message)
        else:
            print("------------ unknown sub market", message)
    def run_service(self):
        args = self._prepare_args()
        self.subscribe(args, self._callback)
        self.args += args

    def sub_more(self, inst_list: list, channel:str):
        args = []
        for i in inst_list:
            if channel == "mark-price":
                mark_price = {
                "channel": "mark-price",
                "instId": i
                }
                args.append(mark_price)
            elif channel == "tickers":
                ticker = {
                    "channel": "tickers",
                    "instId": i
                }
                args.append(ticker)
            else:
                raise "invalid channel name"

        self.subscribe(args, self._callback)

    def stop_service(self):
        self.unsubscribe(self.args, lambda message: print(message))
        self.close()

    def _prepare_args(self) -> List[Dict]:
        args = []
        # books
        # books5_sub = {
        #     "channel": self.channel,
        #     "instId": self.inst_id
        # }
        # args.append(books5_sub)

        #tickers
        for i in self.inst_list:
            ticker = {
                "channel": "tickers",
                "instId": i
            }
            args.append(ticker)
        print("sub bbo", len(args))

        # option trades
        option_trades = {
        "channel": "option-trades",
        "instType": "OPTION",
        "instFamily": "BTC-USD"
        }
        args.append(option_trades)
        option_trades = {
        "channel": "option-trades",
        "instType": "OPTION",
        "instFamily": "ETH-USD"
        }
        args.append(option_trades)

        # 期权定价信息
        option_summary = {
        "channel": "opt-summary",
        "instFamily": "BTC-USD"
        }
        args.append(option_summary)
        option_summary = {
        "channel": "opt-summary",
        "instFamily": "ETH-USD"
        }
        args.append(option_summary)

        # mark-price
        mark_price = {
        "channel": "mark-price",
        "instId": "BTC-USD-231201-38000-C"
        }
        args.append(mark_price)

        # 行权价格
        opt_execise = {
        "channel": "estimated-price",
        "instType": "OPTION",
        "instFamily": "BTC-USD"
        }
        args.append(opt_execise)
        opt_execise = {
        "channel": "estimated-price",
        "instType": "OPTION",
        "instFamily": "ETH-USD"
        }
        args.append(opt_execise)
        print("market data sub list", args)
        return args




    def on_mark_price(self, message):
        message["code"] = "0"
        mark_px_cache: MarkPxCache = mark_px_container[0]
        mark_px_cache.update_from_json(message)
        if self.mark_cb:
            self.mark_cb(message["data"])

    # bbo
    def on_ticker_sub(self, message):
        # {'arg': {'channel': 'tickers', 'instId': 'ETH-USD-231108-1800-P'}, 'data': [{'instType': 'OPTION', 'instId': 'ETH-USD-231108-1800-P', 'last': '0.0022', 'lastSz': '1', 'askPx': '0.0019', 'askSz': '2555', 'bidPx': '0.0015', 'bidSz': '240', 'open24h': '0.0021', 'high24h': '0.0022', 'low24h': '0.0021', 'sodUtc0': '0.0022', 'sodUtc8': '0.0021', 'volCcy24h': '9.1', 'vol24h': '91', 'ts': '1699258576767'}]}
        message["code"] =  "0" # make up a rest code
        tickers: Tickers = tickers_container[0]
        tickers.update_from_json(message)
        if self.ticker_cb:
            self.ticker_cb()

def on_option_sum_update(message):
    """
    {'arg': {'channel': 'opt-summary', 'instFamily': 'ETH-USD'}, 'data': [{'instType': 'OPTION', 'instId': 'ETH-USD-231229-1900-C', 'uly': 'ETH-USD', 'delta': '0.3848931471', 'gamma': '1.1952430617', 'vega': '0.0015720557', 'theta': '-0.0006847207', 'lever': '16.7583934742', 'markVol': '0.504641955', 'bidVol': '0.5035490319', 'askVol': '0.5099577105', 'realVol': '', 'deltaBS': '0.444564738', 'gammaBS': '0.0010937793', 'thetaBS': '-1.325279716', 'vegaBS': '2.8242766863', 'ts': '1698837351931', 'fwdPx': '1810.920922285', 'volLv': '0.497243295'}
    """
    arg = message.get('arg')
    inst = arg.get('instFamily')
    data = message.get('data')
    for d in data:
        inst_id = d.get('instId')
        o = Option(
            inst_id=inst_id,
            mark_vol=float(d.get('markVol')),
                               bid_vol=float(d.get('bidVol')),
                               ask_vol=float(d.get('askVol')),
                               delta=float(d.get('deltaBS')),
                               gamma=float(d.get('gammaBS')),
                               theta=float(d.get('thetaBS')),
                               vega=float(d.get('vegaBS')),
                               vol_lv=float(d.get('volLv')),
                               )
        option_sum[inst_id] = o

def on_orderbook_snapshot_or_update(message):
    """
    :param message:
    {
    "arg": {
        "channel": "books",
        "instId": "BTC-USDT"
    },
    "action": "snapshot",
    "data": [{
        "asks": [
            ["8476.98", "415", "0", "13"],
            ["8477", "7", "0", "2"],
            ["8477.34", "85", "0", "1"],
            ["8477.56", "1", "0", "1"],
            ["8505.84", "8", "0", "1"],
            ["8506.37", "85", "0", "1"],
            ["8506.49", "2", "0", "1"],
            ["8506.96", "100", "0", "2"]
        ],
        "bids": [
            ["8476.97", "256", "0", "12"],
            ["8475.55", "101", "0", "1"],
            ["8475.54", "100", "0", "1"],
            ["8475.3", "1", "0", "1"],
            ["8447.32", "6", "0", "1"],
            ["8447.02", "246", "0", "1"],
            ["8446.83", "24", "0", "1"],
            ["8446", "95", "0", "3"]
        ],
        "ts": "1597026383085",
        "checksum": -855196043
    }]
}
    :return:
    """
    arg = message.get("arg")
    inst_id = arg.get("instId")
    action = message.get("action")
    if inst_id not in order_books:
        order_books[inst_id] = OrderBook(inst_id=inst_id)
    data = message.get("data")[0]
    if data.get("asks"):
        if action == "snapshot" or not action:
            ask_list = [OrderBookLevel(price=float(level_info[0]),
                                       quantity=float(level_info[1]),
                                       order_count=int(level_info[3]),
                                       price_string=level_info[0],
                                       quantity_string=level_info[1],
                                       order_count_string=level_info[3],
                                       ) for level_info in data["asks"]]
            order_books[inst_id].set_asks_on_snapshot(ask_list)
        if action == "update":
            for level_info in data["asks"]:
                order_books[inst_id].set_asks_on_update(
                    OrderBookLevel(price=float(level_info[0]),
                                   quantity=float(level_info[1]),
                                   order_count=int(level_info[3]),
                                   price_string=level_info[0],
                                   quantity_string=level_info[1],
                                   order_count_string=level_info[3],
                                   )
                )
    if data.get("bids"):
        if action == "snapshot" or not action:
            bid_list = [OrderBookLevel(price=float(level_info[0]),
                                       quantity=float(level_info[1]),
                                       order_count=int(level_info[3]),
                                       price_string=level_info[0],
                                       quantity_string=level_info[1],
                                       order_count_string=level_info[3],
                                       ) for level_info in data["bids"]]
            order_books[inst_id].set_bids_on_snapshot(bid_list)
        if action == "update":
            for level_info in data["bids"]:
                order_books[inst_id].set_bids_on_update(
                    OrderBookLevel(price=float(level_info[0]),
                                   quantity=float(level_info[1]),
                                   order_count=int(level_info[3]),
                                   price_string=level_info[0],
                                   quantity_string=level_info[1],
                                   order_count_string=level_info[3],
                                   )
                )
    if data.get("ts"):
        order_books[inst_id].set_timestamp(int(data["ts"]))
    if data.get("checksum"):
        order_books[inst_id].set_exch_check_sum(data["checksum"])


class ChecksumThread(threading.Thread):
    def __init__(self, wss_mds: WssMarketDataService):
        self.wss_mds = wss_mds
        super().__init__()

    def run(self) -> None:
        while 1:
            try:
                for inst_id, order_book in order_books.items():
                    order_book: OrderBook
                    if order_book.do_check_sum():
                        continue
                    self.wss_mds.stop_service()
                    time.sleep(3)
                    self.wss_mds.run_service()
                    break
                time.sleep(5)
            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    # url = "wss://ws.okx.com:8443/ws/v5/public"
    url = "wss://ws.okx.com:8443/ws/v5/public?brokerId=9999"
    market_data_service = WssMarketDataService(url=url, inst_id="BTC-USDT-SWAP", channel="books")
    market_data_service.start()
    market_data_service.run_service()
    check_sum = ChecksumThread(market_data_service)
    check_sum.start()
    time.sleep(30)

