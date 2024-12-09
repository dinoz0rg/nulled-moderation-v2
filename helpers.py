import logging
import os
from logging.handlers import TimedRotatingFileHandler


def init_all_loggers(log_level):
    os.makedirs("log", exist_ok=True)

    formatter = logging.Formatter(u'%(asctime)s %(levelname)s %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

    cmd_logger = logging.getLogger()
    hdlr = TimedRotatingFileHandler("log/logmain.log", when="W0", interval=1, backupCount=4, encoding="utf-8")
    hdlr.setFormatter(formatter)
    cmd_logger.setLevel(log_level)
    cmd_logger.addHandler(hdlr)

    hdlr2 = logging.StreamHandler()
    hdlr2.setFormatter(formatter)
    cmd_logger.addHandler(hdlr2)

    init_error_logger(log_level)
    init_ban_logger(log_level)


def init_error_logger(log_level):
    formatter = logging.Formatter(u'%(asctime)s %(levelname)s %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
    cmd_logger = logging.getLogger("AppErrorLogger")
    hdlr_3 = TimedRotatingFileHandler("log/logerror.log", when="W0", interval=1, backupCount=4, encoding="utf-8")
    hdlr_3.setFormatter(formatter)
    cmd_logger.setLevel(log_level)
    cmd_logger.addHandler(hdlr_3)
    return cmd_logger


def init_ban_logger(log_level):
    formatter = logging.Formatter(u'%(asctime)s %(levelname)s %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
    cmd_logger = logging.getLogger("AppBanLogger")
    hdlr_3 = TimedRotatingFileHandler("log/logban.log", when="W0", interval=1, backupCount=4, encoding="utf-8")
    hdlr_3.setFormatter(formatter)
    cmd_logger.setLevel(log_level)
    cmd_logger.addHandler(hdlr_3)
    return cmd_logger


def get_main_bot_logger():
    return logging.getLogger()


def get_error_logger():
    return logging.getLogger("AppErrorLogger")


def get_ban_logger():
    return logging.getLogger("AppBanLogger")
