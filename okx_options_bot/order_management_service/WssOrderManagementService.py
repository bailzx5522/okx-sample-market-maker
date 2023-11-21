import json
import time
from typing import List, Dict

from order_management_service.model.Order import Order, Orders
from okx.websocket.WsPrivate import WsPrivate
from db import orders_container


class WssOrderManagementService(WsPrivate):
    def __init__(self, url: str, api_key: str , passphrase: str ,
                 secret_key: str , useServerTime: bool = False):
        super().__init__(api_key, passphrase, secret_key, url, useServerTime)
        self.args = []

    def run_service(self):
        args = self._prepare_args()
        # print(args)
        # print("subscribing")
        orders_container.append(Orders())
        self.subscribe(args, _callback)
        self.args += args

    def stop_service(self):
        self.unsubscribe(self.args, lambda message: print(message))
        self.close()

    @staticmethod
    def _prepare_args() -> List[Dict]:
        args = []
        orders_sub = {
            "channel": "orders",
            "instType": "ANY",
        }
        args.append(orders_sub)
        # print("order manager sub list", orders_sub)
        return args


def _callback(message):
    arg = message.get("arg")
    # print("------------------ order callback")
    # print(message)
    if not arg or not arg.get("channel"):
        return
    if message.get("event") == "subscribe":
        return
    if arg.get("channel") == "orders":
        on_orders_update(message)
        print(orders_container)


def on_orders_update(message):
    if not orders_container:
        orders_container.append(Orders.init_from_json(message))
    else:
        orders_container[0].update_from_json(message)


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    os.path.join(BASE_DIR)
    print(BASE_DIR)
    url = "wss://ws.okx.com:8443/ws/v5/private"
    # url = "wss://ws.okx.com:8443/ws/v5/private?brokerId=9999"
    order_management_service = WssOrderManagementService(url=url, api_key=os.environ["API_KEY"], secret_key=os.environ["API_KEY_SECRET"], passphrase=os.environ["API_PASSPHRASE"])
    order_management_service.start()
    order_management_service.run_service()
    time.sleep(30)
