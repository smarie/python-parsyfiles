from abc import ABCMeta, abstractmethod
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
        

class ObjectPresentMultipleTimesOnFileSystemError(Exception):
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
        super(ObjectPresentMultipleTimesOnFileSystemError, self).__init__(contents)

    @staticmethod
    def create(item_name: str, item_file_prefix: str, extensions_found: List[str] = None):  # -> ObjectCannotBeParsedError:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_name:
        :param item_file_prefix:
        :param extensions_found:
        :return:
        """
        if not extensions_found:
            return ObjectPresentMultipleTimesOnFileSystemError('Object : ' + item_name + ' is present multiple times on'
                                                               ' the file system under path ' + item_file_prefix + ', '
                                                               'as file AND folder.')
        else:
            return ObjectPresentMultipleTimesOnFileSystemError('Object : ' + item_name + ' is present multiple times on'
                                                               ' the file system under path ' + item_file_prefix + ', '
                                                               'with extensions : ' + str(extensions_found) + '. Only '
                                                               'one version of each attribute should be provided')


class ObjectNotFoundOnFileSystemError(FileNotFoundError):
    """
    Raised whenever a given object is missing on the filesystem (no singlefile or multifile found)
    """

    def __init__(self, contents: str):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(ObjectNotFoundOnFileSystemError, self).__init__(contents)

    @staticmethod
    def create(item_name: str, item_file_prefix: str, extensions_found: List[str] = None):  # -> ObjectNotFoundOnFileSystemError:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_name:
        :param item_file_prefix:
        :param extensions_found: if None, that means that we did not even check the available extensions : the file
        was just not there
        :return:
        """
        if not extensions_found or len(extensions_found) == 0:
            return ObjectNotFoundOnFileSystemError('Mandatory object : ' + item_name + ' could not be found on the file'
                                                   ' system under path ' + item_file_prefix + ', either as a folder or '
                                                   'as a file with any extension')
        else:
            return ObjectNotFoundOnFileSystemError('Mandatory attribute : ' + item_name + ' could not be found on the '
                                                   'file system under path ' + item_file_prefix + ' with one of the '
                                                   'supported extensions ' + str(extensions_found))


class FileMappingConfiguration(metaclass=ABCMeta):
    """
    Abstract class for all file mapping configurations
    """
    def __init__(self, encoding:str = None):
        """
        Constructor, with the encoding registered to open the files.
        :param encoding: the encoding used to open the files default is 'utf-8'
        """
        check_var(encoding, var_types=str, var_name='encoding', enforce_not_none=False)
        self.encoding = encoding or 'utf-8'


    @abstractmethod
    def find_multifileobject_contents(self, item_file_prefix: str) -> Dict[str, str]:
        """
        Implementing classes should return a dictionary of <item_name>, <item_prefix> containing the named elements
        in this collection.

        :param item_file_prefix: the absolute file prefix of the parent item.
        :return: a dictionary of {item_name : item_prefix}
        """
        raise NotImplementedError('Function \'find_collectionobject_contents_file_occurrences\' is not implemented in this '
                                  'abstract base class')


    def is_present_as_multifile_object(self, item_file_prefix: str) -> bool:
        """
        Implementing classes should return True if an item with this item_file_prefix is present as a multifile object,
        or False otherwise

        :param item_file_prefix:
        :return:
        """
        return len(self.find_multifileobject_contents(item_file_prefix)) > 0


    # @abstractmethod
    # def find_multifileobject_attribute_file_occurrences(self, item_file_prefix) -> List[str]:
    #     """
    #     Implementing classes should return a list of attribute <item_file_prefix> for the attributes found
    #
    #     :param item_file_prefix:
    #     :return:
    #     """
    #     raise NotImplementedError('Function \'find_multifileobject_attribute_file_occurrences\' is not implemented in this '
    #                               'abstract base class')


    @abstractmethod
    def get_file_prefix_for_multifile_object_attribute(self, parent_path: str, item_name: str) -> List[str]:
        """
        Implementing classes should return a list of

        :param parent_path:
        :param item_name:
        :return:
        """
        raise NotImplementedError('Function \'_get_multifile_object_attribute_file_prefix\' is not implemented in this '
                                  'abstract base class')


    def is_present_as_singlefile_object(self, item_file_prefix, sep_for_flat):
        """
        Utility method to check if an item is present as a simple object - that means, if there is any file matching this
        prefix with any extension

        :param item_file_prefix:
        :param sep_for_flat:
        :return:
        """
        return len(self.find_simpleobject_file_occurrences(item_file_prefix, sep_for_flat)) > 0


    @abstractmethod
    def find_simpleobject_file_occurrences(self, item_file_prefix) -> Dict[str, str]:
        """
        Implementing classes should return a dict of <ext, file_path> that match the given simple object, with any
        extension.

        :param item_file_prefix:
        :return: a dictionary of {ext : file_path}
        """
        raise NotImplementedError('Function \'find_simpleobject_file_occurrences\' is not implemented in this '
                                  'abstract base class')


class WrappedFileMappingConfiguration(FileMappingConfiguration):
    """
    A file mapping where collection objects and multifile objects are in folders
    """
    def __init__(self, encoding:str = None):
        super(WrappedFileMappingConfiguration, self).__init__(encoding=encoding)


    def find_multifileobject_contents(self, item_file_prefix) -> Dict[str, str]:
        """
        Utility method to list all sub-items of a given parent item.
        In this mode, root_path should be a valid folder, and each item is a subfolder or a file :

            item_file_prefix/
            |-singlefile_sub_item1.<ext>
            |-singlefile_sub_item2.<ext>
            |-multifile_sub_item3/
              |- ...

        :param parent_item_prefix: the absolute file prefix of the parent item. it may be a folder (non-flat mode)
        or a folder + a file name prefix (flat mode)
        :return: a dictionary of {item_name : item_prefix}
        """

        # Assert that folder_path is a folder
        if not isdir(item_file_prefix):
            return dict()

        else:
            # List folders (multifile objects or collections)
            all_subfolders = [dir_ for dir_ in listdir(item_file_prefix) if isdir(join(item_file_prefix, dir_))]
            items = {item_name: join(item_file_prefix, item_name) for item_name in all_subfolders}

            # List files *without* their extension
            items.update({
                          item_name: join(item_file_prefix, item_name)
                          for item_name in [file_name[0:file_name.rindex(EXT_SEPARATOR)]
                                            for file_name in listdir(item_file_prefix)
                                            if isfile(join(item_file_prefix, file_name))
                                            and EXT_SEPARATOR in file_name]
                         })
        return items


    def get_file_prefix_for_multifile_object_attribute(self, parent_item_prefix: str, item_name: str) -> str:
        """
        Utility method to get the item_file_prefix corresponding to a parent path and an object.
        In this mode the attribute is a file in the parent object folder

        :param parent_item_prefix: the absolute file prefix of the parent item.
        :return: the file prefix for this attribute
        """
        check_var(parent_item_prefix, var_types=str, var_name='parent_item_prefix')
        check_var(item_name, var_types=str, var_name='item_name')

        # assert that folder_path is a folder
        if not isdir(parent_item_prefix):
            raise ValueError(
                'Cannot get attribute item in non-flat mode, parent item path is not a folder : ' + parent_item_prefix)
        return join(parent_item_prefix, item_name)


    def find_simpleobject_file_occurrences(self, item_file_prefix) -> Dict[str, str]:
        """
        Utility method to find all the files for the given simple object, with any extension.

        :param item_file_prefix:
        :return: a dictionary of {ext : file_path}
        """
        parent_dir = dirname(item_file_prefix)
        base_prefix = basename(item_file_prefix)

        possible_object_files = {object_file[len(base_prefix):]: join(parent_dir, object_file)
                                 for object_file in listdir(parent_dir) if
                                 isfile(parent_dir + '/' + object_file)
                                 and object_file.startswith(base_prefix)
                                 # file must be named base_prefix.something
                                 and object_file != base_prefix
                                 and object_file[len(base_prefix)] == EXT_SEPARATOR
                                 and (object_file[len(base_prefix):]).count(EXT_SEPARATOR) == 1}

        return possible_object_files


class FlatFileMappingConfiguration(FileMappingConfiguration):
    """
    A file mapping where collection objects and multifile objects are in files in the same folder than their parent,
    with their parent name as the prefix, followed by a configurable separator
    """
    def __init__(self, separator: str = None, encoding:str = None):
        """
        :param flat_mode: true to indicate flat file mode, false to indicate folder wrapping mode
        :param separator: the character sequence used to separate an item name from an item attribute name. Only
        used in flat mode. Default is '.'
        :param encoding: encoding used to open the files. Default is 'utf-8'
        """
        super(FlatFileMappingConfiguration, self).__init__(encoding=encoding)

        check_var(separator, var_types=str, var_name='sep_for_flat', enforce_not_none=False, min_len=1)

        self.separator = separator or '.'

        if '/' in self.separator or '\\' in self.separator:
            raise ValueError('Separator cannot contain a folder separation character')


    def find_multifileobject_contents(self, item_file_prefix) -> Dict[str, str]:
        """
        Utility method to list all sub-items of a given parent item.
        In this mode, each item is a set of files with the same prefix than item_file_prefix, separated from the
        attribute name by the character sequence <self.separator>. The item_file_prefix may also be directly a folder,
        in which case the sub items dont have a prefix.

        example if item_file_prefix = '<parent_folder>/<file_prefix>'

        parent_folder/
        |-file_prefix<sep>singlefile_sub_item1.<ext>
        |-file_prefix<sep>singlefile_sub_item2.<ext>
        |-file_prefix<sep>multifile_sub_item3<sep>singlesub1.<ext>
        |-file_prefix<sep>multifile_sub_item3<sep>singlesub2.<ext>

        example if item_file_prefix = '<parent_folder>/

        item_file_prefix/
        |-singlefile_sub_item1.<ext>
        |-singlefile_sub_item2.<ext>
        |-multifile_sub_item3<sep>singlesub1.<ext>
        |-multifile_sub_item3<sep>singlesub2.<ext>

        :param parent_item_prefix: the absolute file prefix of the parent item. It may be a folder (special case of the
         root folder) but typically is just a file prefix
        :return: a dictionary of <item_name>, <item_path>
        """

        # Find the base directory and base name
        if isdir(item_file_prefix):  # special case of root folder. maybe TODO be more strict: root_folder = self.root_folder
            parent_dir = item_file_prefix
            base_prefix = ''
            start_with = ''
        else:
            parent_dir = dirname(item_file_prefix)
            base_prefix = basename(item_file_prefix) #+ self.separator
            start_with = self.separator

        content_files = [content_file for content_file in listdir(parent_dir)
                         # we are in flat mode : should be a file not a folder
                         if isfile(join(parent_dir,content_file))
                         # we are looking for children of a specific item
                         and content_file.startswith(base_prefix)
                         # we are looking for multifile child items only
                         and content_file != base_prefix
                         # they should start with the separator (or with nothing in case of the root folder)
                         and (content_file[len(base_prefix):]).startswith(start_with)
                         # they should have a valid extension
                         and (content_file[len(base_prefix + start_with):]).count(EXT_SEPARATOR) >= 1
                         ]
        # build the resulting dictionary of item_name > item_prefix
        item_prefixes = dict()
        for item_file in content_files:
            item_name = item_file[len(base_prefix + start_with):item_file.find(self.separator, len(base_prefix +
                                                                                                   start_with))]
            item_prefixes[item_name] = join(parent_dir, base_prefix + start_with + item_name)

        return item_prefixes

        # # list all files that are under the parent_item
        # all_file_suffixes_under_parent = [f[len(base_prefix):] for f in listdir(parent_dir)
        #                                   if isfile(join(parent_dir, f)) and f.startswith(base_prefix)]

        # find the set of file prefixes that exist under this parent item
        # prefixes = {file_name_suffix[0:file_name_suffix.index(self.separator)]: file_name_suffix
        #             for file_name_suffix in all_file_suffixes_under_parent if
        #             (self.separator in file_name_suffix)}
        # prefixes.update({file_name_suffix[0:file_name_suffix.rindex(EXT_SEPARATOR)]: file_name_suffix
        #                  for file_name_suffix in all_file_suffixes_under_parent if
        #                  (self.separator not in file_name_suffix)})
        # item_paths = dict()
        # for prefix, file_name_suffix in prefixes.items():
        #     if len(prefix) == 0:
        #         raise ValueError(
        #             'Error while trying to read item ' + item_file_prefix + ' as a collection: a '
        #                                                                       'file already exist with this name and an extension : ' + base_prefix +
        #             self.separator + file_name_suffix)
        #     if prefix not in item_paths.keys():
        #         if isdir(item_file_prefix):
        #             item_paths[prefix] = join(item_file_prefix, prefix)
        #         else:
        #             item_paths[prefix] = item_file_prefix + self.separator + prefix
        # return item_paths


    # def find_multifileobject_attribute_file_occurrences(self, item_file_prefix) -> List[str]:
    #     """
    #     Utility method for flat mode only, to find all the attribute files for the given complex object, with any extension.
    #     It also returns the files that are attributes of attributes (recursive) in the case of attributes that themselves
    #     are complex objects
    #
    #     :param item_file_prefix:
    #     :param sep_for_flat:
    #     :return:
    #     """
    #     parent_dir = dirname(item_file_prefix)
    #     base_prefix = basename(item_file_prefix)
    #     # trick : is sep_for_flat is a dot, we have to take into account that there is also a dot for the extension
    #     min_sep_count = (1 if self.separator == EXT_SEPARATOR else 0)
    #     possible_attribute_field_files = [attribute_file for attribute_file in listdir(parent_dir) if
    #                                       attribute_file.startswith(base_prefix)
    #                                       and attribute_file != base_prefix
    #                                       and (attribute_file[len(base_prefix):]).count(EXT_SEPARATOR) >= 1
    #                                       and (attribute_file[len(base_prefix):]).count(self.separator) > min_sep_count]
    #     return possible_attribute_field_files


    def get_file_prefix_for_multifile_object_attribute(self, parent_path: str, item_name: str):
        """
        In this mode the attribute is a file with the same prefix, separated from the parent object name by
        the character sequence <self.separator>

        :param parent_item_prefix: the absolute file prefix of the parent item.
        :return: the file prefix for this attribute
        """
        check_var(parent_path, var_types=str, var_name='parent_path')
        check_var(item_name, var_types=str, var_name='item_name')

        return parent_path + self.separator + item_name


    def find_simpleobject_file_occurrences(self, item_file_prefix) -> Dict[str, str]:
        """
        Utility method to find all the files for the given simple object, with any extension.

        :param item_file_prefix:
        :return: a dictionary{ext : file_path}
        """
        parent_dir = dirname(item_file_prefix)
        base_prefix = basename(item_file_prefix)

        # trick : is sep_for_flat is a dot, we have to take into account that there is also a dot for the extension
        min_sep_count = (1 if self.separator == EXT_SEPARATOR else 0)
        possible_object_files = {object_file[len(base_prefix):]: join(parent_dir, object_file)
                                 for object_file in listdir(parent_dir) if isfile(parent_dir + '/' + object_file)
                                 and object_file.startswith(base_prefix)
                                 # file must be named base_prefix.something
                                 and object_file != base_prefix
                                 and object_file[len(base_prefix)] == EXT_SEPARATOR
                                 and (object_file[len(base_prefix):]).count(EXT_SEPARATOR) == 1
                                 # and no other item separator should be present in the something
                                 and (object_file[len(base_prefix):]).count(self.separator) == min_sep_count}

        return possible_object_files

