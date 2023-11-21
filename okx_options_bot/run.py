import os
from dotenv import load_dotenv

from strategy.OptionBot import OptionBot

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

if __name__ == "__main__":
    strategy = OptionBot(os.environ["API_KEY"], os.environ["API_KEY_SECRET"], os.environ["API_PASSPHRASE"])
    strategy.run()

