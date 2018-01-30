# only these two are the 'first-level' api.
# allow users to do
#     from parsyfiles import xxx
# from these.
from parsyfiles.filesystem_mapping import *
from parsyfiles.parsing_fw import *
from parsyfiles.global_config import parsyfiles_global_config

# For the rest, allow user to do
#    import parsyfiles as pf
# and then pf.xxx
__all__ = ['converting_core',
           'filesystem_mapping'
           'parsing_combining_parsers',
           'parsing_core',
           'parsing_core_api',
           'parsing_fw',
           'parsing_registries',
           'type_inspection_tools',
           # dont insert the various support_xxx files here
           'var_checker']