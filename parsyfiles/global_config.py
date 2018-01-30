

class GlobalConfig:
    """ The global configuration object used module-wide. Last-resort option to provide customizability
    (RootParser is preferred)"""
    def __init__(self, multiple_errors_tb_limit: int = 3):
        self.multiple_errors_tb_limit = multiple_errors_tb_limit


GLOBAL_CONFIG = GlobalConfig()


# TODO it would actually be much better to revise the exceptions object model to make all details available. This would almost remove the need for option multiple_errors_tb_limit
def parsyfiles_global_config(multiple_errors_tb_limit: int = None):
    """
    This is the method you should use to configure the parsyfiles library

    :param multiple_errors_tb_limit: the traceback size (default is 3) of individual parsers exceptions displayed when
    parsyfiles tries several parsing chains and all of them fail.
    :return:
    """
    if multiple_errors_tb_limit is not None:
        GLOBAL_CONFIG.multiple_errors_tb_limit = multiple_errors_tb_limit
