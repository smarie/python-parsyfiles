

class GlobalConfig:
    """ The global configuration object used module-wide. Last-resort option to provide customizability
    (RootParser is preferred)"""
    def __init__(self, multiple_errors_tb_limit: int = 3, full_paths_in_logs: bool = False):
        self.multiple_errors_tb_limit = multiple_errors_tb_limit
        self.full_paths_in_logs = full_paths_in_logs


GLOBAL_CONFIG = GlobalConfig()


# TODO it would actually be much better to revise the exceptions object model to make all details available. This would almost remove the need for option multiple_errors_tb_limit
def parsyfiles_global_config(multiple_errors_tb_limit: int = None, full_paths_in_logs: bool = None):
    """
    This is the method you should use to configure the parsyfiles library

    :param multiple_errors_tb_limit: the traceback size (default is 3) of individual parsers exceptions displayed when
    parsyfiles tries several parsing chains and all of them fail.
    :param full_paths_in_logs: if True, full file paths will be displayed in logs. Otherwise only the parent path will
    be displayed and children paths will be indented (default is False)
    :return:
    """
    if multiple_errors_tb_limit is not None:
        GLOBAL_CONFIG.multiple_errors_tb_limit = multiple_errors_tb_limit
    if full_paths_in_logs is not None:
        GLOBAL_CONFIG.full_paths_in_logs = full_paths_in_logs
