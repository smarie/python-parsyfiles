

class GlobalConfig:
    """ The global configuration object used module-wide. Last-resort option to provide customizability
    (RootParser is preferred)"""
    def __init__(self, multiple_errors_tb_limit: int = 3, full_paths_in_logs: bool = False, 
                 dict_to_object_subclass_limit: int = 50):
        self.multiple_errors_tb_limit = multiple_errors_tb_limit
        self.full_paths_in_logs = full_paths_in_logs
        self.dict_to_object_subclass_limit = dict_to_object_subclass_limit


GLOBAL_CONFIG = GlobalConfig()


# TODO it would actually be much better to revise the exceptions object model to make all details available. This would almost remove the need for option multiple_errors_tb_limit
def parsyfiles_global_config(multiple_errors_tb_limit: int = None, full_paths_in_logs: bool = None, 
                             dict_to_object_subclass_limit: int = None):
    """
    This is the method you should use to configure the parsyfiles library

    :param multiple_errors_tb_limit: the traceback size (default is 3) of individual parsers exceptions displayed when
    parsyfiles tries several parsing chains and all of them fail.
    :param full_paths_in_logs: if True, full file paths will be displayed in logs. Otherwise only the parent path will
    be displayed and children paths will be indented (default is False)
    :param dict_to_object_subclass_limit: the number of subclasses that the <dict_to_object> converter will try, when 
    instantiating an object from a dictionary. Default is 50
    :return:
    """
    if multiple_errors_tb_limit is not None:
        GLOBAL_CONFIG.multiple_errors_tb_limit = multiple_errors_tb_limit
    if full_paths_in_logs is not None:
        GLOBAL_CONFIG.full_paths_in_logs = full_paths_in_logs
    if dict_to_object_subclass_limit is not None:
        GLOBAL_CONFIG.dict_to_object_subclass_limit = dict_to_object_subclass_limit
