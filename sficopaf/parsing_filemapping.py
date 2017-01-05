from os import listdir
from os.path import isfile, join, isdir, dirname, basename
from typing import Dict, List

from sficopaf import check_var

EXT_SEPARATOR = '.'

class FolderAndFilesStructureError(Exception):
    """
    Raised whenever the folder and files structure does not match with the one expected
    """
    def __init__(self, contents):
        super(FolderAndFilesStructureError, self).__init__(contents)
        

class MultipleFilesError(Exception):
    """
    Raised whenever a given attribute is provided several times in the filesystem (with multiple extensions)
    """
    def __init__(self, contents:str):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(MultipleFilesError, self).__init__(contents)

    @staticmethod
    def create(item_name: str, item_file_prefix: str, extensions_found: List[str] = None):  # -> UnsupportedObjectTypeError:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_name:
        :param item_file_prefix:
        :param extensions_found:
        :return:
        """
        if not extensions_found:
            return MultipleFilesError('Attribute : ' + item_name + ' is present multiple times in the file '
                                      'system under path ' + item_file_prefix + ', as files AND folder.')
        else:
            return MultipleFilesError('Attribute : ' + item_name + ' is present multiple times in the file '
                                                 'system under path ' + item_file_prefix + ', with '
                                                 'extensions : ' + str(extensions_found) + '. Only one version of each'
                                                 ' attribute should be provided')


class MandatoryFileNotFoundError(FileNotFoundError):
    """
    Raised whenever a given attribute is missing in the filesystem (no supported extensions found)
    """

    def __init__(self, contents: str):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(MandatoryFileNotFoundError, self).__init__(contents)

    @staticmethod
    def create(item_name: str, item_file_prefix: str, extensions_found: List[str] = None):  # -> MandatoryFileNotFoundError:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_name:
        :param item_file_prefix:
        :param extensions_found: if None, that means that we did not even check the available extensions : the file
        was just not there
        :return:
        """
        if not extensions_found:
            return MandatoryFileNotFoundError('Mandatory attribute : ' + item_name + ' could not be found on the file '
                                              'system under path ' + item_file_prefix + ', either as a folder or as a '
                                                                                        'file with any extension')
        else:
            return MandatoryFileNotFoundError('Mandatory attribute : ' + item_name + ' could not be found on the file '
                                          'system under path ' + item_file_prefix + ' with one of the supported '
                                          'extensions ' + str(extensions_found))


class FileMappingConfiguration(object):
    """
    Utility class to hold all configuration related to the file system mapping
    """
    def __init__(self, flat_mode: bool = False, sep_for_flat: str = None, encoding:str = None):
        """
        :param flat_mode: true to indicate flat file mode, false to indicate folder wrapping mode
        :param sep_for_flat: the character sequence used to separate an item name from an item attribute name. Only
        used in flat mode. Default is '.'
        :param encoding: encoding used to open the files. Default is 'utf-8'
        """
        check_var(flat_mode, var_types=bool, var_name='flat_mode')
        check_var(sep_for_flat, var_types=str, var_name='sep_for_flat', enforce_not_none=False)
        check_var(encoding, var_types=str, var_name='encoding', enforce_not_none=False)

        self.flat_mode = flat_mode
        if not flat_mode and sep_for_flat:
            raise ValueError('sep_for_flat must only be provided in flat mode')
        self.sep_for_flat = sep_for_flat or '.'
        self.encoding = encoding or 'utf-8'


def _find_collectionobject_file_prefixes(parent_item_prefix: str,
                                         flat_mode: bool = False, sep_for_flat: str = '.',
                                         item_name_for_log: str = None) -> Dict[str, str]:
    """
    Utility method to list all sub-items of a given parent item.
    * If flat_mode = False, root_path should be a valid folder, and each item is a subfolder.
    * If flat_mode = True, root_path may be a folder or an absolute file prefix, and each item is a set of files
    with the same prefix separated from the attribute name by the character sequence <sep_for_flat>

    :param parent_item_prefix: the absolute file prefix of the parent item. it may be a folder (non-flat mode)
    or a folder + a file name prefix (flat mode)
    :param flat_mode: a boolean indicating if items should be represented by folders or a file name
     prefix
    :param sep_for_flat: the character sequence used to separate an item name from an item attribute name. Only
    used in flat mode
    :return: a dictionary of <item_name>, <item_path>
    """
    if not flat_mode:
        # assert that folder_path is a folder
        if not isdir(parent_item_prefix):
            # try to check if this is a missing item or a structure problem
            files_with_that_prefix = [f for f in listdir(dirname(parent_item_prefix)) if
                                      f.startswith(basename(parent_item_prefix))]
            if len(files_with_that_prefix) > 0:
                raise FolderAndFilesStructureError('Cannot parse collection object ' + (item_name_for_log or '')
                                                   + ' : we are in non-flat (=folders) mode, and item path is not a'
                                                     ' folder : ' + parent_item_prefix + '. Either change the data '
                                                                                         'type to a non-iterable one, or create a folder to contain the '
                                                                                         'various items in the iteration. Alternatively you may wish to '
                                                                                         'use the flat mode to make all files stay in the same root '
                                                                                         'folder')
            else:
                raise MandatoryFileNotFoundError.create('', parent_item_prefix, list())

        # List folders
        onlyfolders = [f for f in listdir(parent_item_prefix) if isdir(join(parent_item_prefix, f))]
        item_paths = {item: join(parent_item_prefix, item) for item in onlyfolders}
        # Add files without their extension(collections of simple types are files
        item_paths.update({f[0:f.rindex(EXT_SEPARATOR)]: join(parent_item_prefix, f[0:f.rindex(
            EXT_SEPARATOR)])
                           for f in listdir(parent_item_prefix) if
                           isfile(join(parent_item_prefix, f)) and EXT_SEPARATOR in f})
    else:
        # List files
        if isdir(parent_item_prefix):  # this is for special case of root folder
            parent_dir = parent_item_prefix
            base_name = ''
        else:
            parent_dir = dirname(parent_item_prefix)
            base_name = basename(parent_item_prefix) + sep_for_flat

        # list all files that are under the parent_item
        all_file_suffixes_under_parent = [f[len(base_name):] for f in listdir(parent_dir)
                                          if isfile(join(parent_dir, f)) and f.startswith(base_name)]

        # find the set of file prefixes that exist under this parent item
        prefixes = {file_name_suffix[0:file_name_suffix.index(sep_for_flat)]: file_name_suffix
                    for file_name_suffix in all_file_suffixes_under_parent if
                    (sep_for_flat in file_name_suffix)}
        prefixes.update({file_name_suffix[0:file_name_suffix.rindex(EXT_SEPARATOR)]: file_name_suffix
                         for file_name_suffix in all_file_suffixes_under_parent if
                         (sep_for_flat not in file_name_suffix)})
        item_paths = {}
        for prefix, file_name_suffix in prefixes.items():
            if len(prefix) == 0:
                raise ValueError(
                    'Error while trying to read item ' + parent_item_prefix + ' as a collection: a '
                                                                              'file already exist with this name and an extension : ' + base_name +
                    sep_for_flat + file_name_suffix)
            if prefix not in item_paths.keys():
                if isdir(parent_item_prefix):
                    item_paths[prefix] = join(parent_item_prefix, prefix)
                else:
                    item_paths[prefix] = parent_item_prefix + sep_for_flat + prefix

    return item_paths


def check_complex_object_on_filesystem(item_file_prefix, file_mapping_conf, item_name_for_log):
    if not file_mapping_conf.flat_mode:
        # ****** FOLDER MODE *******
        if _is_present_as_simpleobject(item_file_prefix, file_mapping_conf.sep_for_flat):
            # We are looking for a complex object (without registered parser) so this is a problem
            if isdir(item_file_prefix):
                raise MultipleFilesError.create(item_name_for_log, item_file_prefix)
            else:
                raise FolderAndFilesStructureError(
                    'Cannot parse complex object : we are in non-flat (=folders) mode, '
                    'but object is present as a file : ' + item_file_prefix)
        elif not isdir(item_file_prefix):
            # item not found at all
            raise MandatoryFileNotFoundError.create(item_name_for_log, item_file_prefix)
        else:
            # -- there is a folder : we can parse
            pass
    else:
        # ****** FLAT MODE ******
        if isdir(item_file_prefix):
            raise FolderAndFilesStructureError('Cannot parse complex object : we are in flat mode, and item path is'
                                               'a folder, it should be a file prefix followed by ' +
                                               file_mapping_conf.sep_for_flat + ' : ' + item_file_prefix)
        elif _is_present_as_simpleobject(item_file_prefix, file_mapping_conf.sep_for_flat):
            raise FolderAndFilesStructureError('Cannot parse complex object : we are in flat mode, and item path is'
                                               ' already a file, it should be a file *prefix* followed by '
                                               + file_mapping_conf.sep_for_flat + ' : ' + item_file_prefix)
        else:
            if not _is_present_as_complex_object_flat_mode(item_file_prefix, file_mapping_conf.sep_for_flat):
                raise MandatoryFileNotFoundError.create(item_name_for_log, item_file_prefix, list())
            else:
                # -- there is at least one file that looks like a field : we can parse
                # Note: weird case of an object that would not require any constructor arguments, is not supported.
                pass


def _get_attribute_item_file_prefix(parent_path: str, item_name: str, flat_mode: bool = False,
                                    sep_for_flat: str = '.'):
    """
    Utility method to get the file prefix of an item that is an attribute of a parent item.
    * If flat_mode = False, the sub item is a folder in the parent folder
    * if flat_mode = True, the sub item is a file with the same prefix, separated from the attribute name by
    the character sequence <sep_for_flat>

    :param parent_path:
    :param item_name:
    :param flat_mode:
    :param sep_for_flat:
    :return:
    """
    check_var(parent_path, var_types=str, var_name='parent_path')
    check_var(item_name, var_types=str, var_name='item_name')
    check_var(flat_mode, var_types=bool, var_name='flat_mode')
    check_var(sep_for_flat, var_types=str, var_name='sep_for_flat')

    if not flat_mode:
        # assert that folder_path is a folder
        if not isdir(parent_path):
            raise ValueError(
                'Cannot get attribute item in non-flat mode, parent item path is not a folder : ' + parent_path)
        return join(parent_path, item_name)

    else:
        return parent_path + sep_for_flat + item_name



def _is_present_as_complex_object_flat_mode(item_file_prefix, sep_for_flat):
    """
    Utility method to check if an item is present as a complex object - that means, if there is any file matching this
    prefix with a suffix + any extension

    :param item_file_prefix:
    :param sep_for_flat:
    :return:
    """
    return len(_find_complexobject_attributefiles_recursive_with_any_extension_flatmode(item_file_prefix, sep_for_flat)) > 0


def _find_complexobject_attributefiles_recursive_with_any_extension_flatmode(item_file_prefix, sep_for_flat):
    """
    Utility method for flat mode only, to find all the attribute files for the given complex object, with any extension.
    It also returns the files that are attributes of attributes (recursive) in the case of attributes that themselves
    are complex objects

    :param item_file_prefix:
    :param sep_for_flat:
    :return:
    """
    parent_dir = dirname(item_file_prefix)
    base_prefix = basename(item_file_prefix)
    # trick : is sep_for_flat is a dot, we have to take into account that there is also a dot for the extension
    min_sep_count = (1 if sep_for_flat == EXT_SEPARATOR else 0)
    possible_attribute_field_files = [attribute_file for attribute_file in listdir(parent_dir) if
                                      attribute_file.startswith(base_prefix)
                                      and (attribute_file[len(base_prefix):]).count(EXT_SEPARATOR) >= 1
                                      and (attribute_file[len(base_prefix):]).count(sep_for_flat) > min_sep_count]
    return possible_attribute_field_files


#@staticmethod
def _is_present_as_simpleobject(item_file_prefix, sep_for_flat):
    """
    Utility method to check if an item is present as a simple object - that means, if there is any file matching this
    prefix with any extension

    :param item_file_prefix:
    :param sep_for_flat:
    :return:
    """
    return len(_find_simpleobject_files_with_any_extension(item_file_prefix, sep_for_flat)) > 0


def _find_simpleobject_files_with_any_extension(item_file_prefix, sep_for_flat):
    """
    Utility method to find all the files for the given simple object, with any extension.

    :param item_file_prefix:
    :param sep_for_flat:
    :return:
    """
    parent_dir = dirname(item_file_prefix)
    base_prefix = basename(item_file_prefix)
    # trick : is sep_for_flat is a dot, we have to take into account that there is also a dot for the extension
    min_sep_count = (1 if sep_for_flat == EXT_SEPARATOR else 0)
    possible_attribute_files = [attribute_file for attribute_file in listdir(parent_dir) if
                                attribute_file.startswith(base_prefix)
                                and (attribute_file[len(base_prefix):]).count(EXT_SEPARATOR) == 1
                                and (attribute_file[len(base_prefix):]).count(sep_for_flat) == min_sep_count]

    return possible_attribute_files