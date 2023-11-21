import logging


logger = logging.getLogger("oo")
logger.setLevel(logging.DEBUG)
# fh = logging.FileHandler()
# fh.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
sh.setFormatter(formatter)
logger.addHandler(sh)