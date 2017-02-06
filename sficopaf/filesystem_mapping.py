from abc import abstractmethod, ABCMeta
from logging import Logger
from os import listdir
from os.path import isfile, join, isdir, dirname, basename
from typing import Dict, List, Any, Tuple, Union

from sficopaf.var_checker import check_var

EXT_SEPARATOR = '.'
MULTIFILE_EXT = '<multifile>'


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
    def create(item_file_prefix: str, extensions_found: List[str] = None):  # -> NoParserFoundForObject:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_file_prefix:
        :param extensions_found:
        :return:
        """
        if not extensions_found:
            return ObjectPresentMultipleTimesOnFileSystemError('Object : ' + item_file_prefix + ' is present multiple '
                                                               'times on the file system.')
        else:
            return ObjectPresentMultipleTimesOnFileSystemError('Object : ' + item_file_prefix + ' is present multiple '
                                                               'times on the file system , with extensions : ' +
                                                               str(extensions_found) + '. Only one version of each '
                                                               'object should be provided. If you need multiple files'
                                                               ' to create this object, you should create a multifile'
                                                               ' object instead (with each file having its own name and'
                                                               ' a shared prefix)')


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
    def create(location: str):  # -> ObjectNotFoundOnFileSystemError:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param location:
        :return:
        """
        return ObjectNotFoundOnFileSystemError('Mandatory object : ' + location + ' could not be found on the file'
                                               ' system, either as a multifile or as a singlefile with any extension.')


class IllegalContentNameError(Exception):
    """
    Raised whenever a attribute of a multifile object or collection has an empty name
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(IllegalContentNameError, self).__init__(contents)

    @staticmethod
    def create(location: str, child_location: str):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param location:
        :param
        :return:
        """
        return IllegalContentNameError('The object \'' + location + '\' is present on file system as a multifile object'
                                       ' but contains a child object with an empty name at path \'' + child_location
                                       + '\'')


class PersistedObject(metaclass=ABCMeta):
    """
    Represents an object persisted at a given location
    """

    def __init__(self, location: str, is_singlefile: bool, ext: str):
        # -- location
        check_var(location, var_types=str, var_name='location')
        self.location = location
        # -- single file
        check_var(is_singlefile, var_types=bool, var_name='is_singlefile')
        self.is_singlefile = is_singlefile
        # -- ext
        check_var(ext, var_types=str, var_name='ext')
        self.ext = ext

    def __str__(self) -> str:
        return self.location + ' (' + self.get_pretty_file_ext() + ')'

    def get_pretty_file_mode(self):
        return 'singlefile' if self.is_singlefile else 'multifile'

    def get_pretty_file_ext(self):
        return ('singlefile, ' + self.ext) if self.is_singlefile else 'multifile'

    def get_pretty_location(self):
        return self.location + ' (' + self.get_pretty_file_ext() + ')'

    @abstractmethod
    def get_singlefile_path(self):
        pass

    @abstractmethod
    def get_singlefile_encoding(self):
        pass

    @abstractmethod
    def get_multifile_children(self) -> Dict[str, Any]: # actually, not Any but PersistedObject
        pass


class AbstractFileMappingConfiguration(metaclass=ABCMeta):
    """
    Represents a file mapping configuration. It should be able to find singlefile and multifile objects at specific
    locations.
    """

    def __init__(self, encoding:str = None):
        """
        Constructor, with the encoding registered to open the files.
        :param encoding: the encoding used to open the files default is 'utf-8'
        """
        check_var(encoding, var_types=str, var_name='encoding', enforce_not_none=False)
        self.encoding = encoding or 'utf-8'

    def get_unique_object_contents(self, location: str) -> Tuple[bool, str, Union[str, Dict[str, str]]]:
        """
        Utility method to find a unique singlefile or multifile object.
        This method throws
        * ObjectNotFoundOnFileSystemError if no file is found
        * ObjectPresentMultipleTimesOnFileSystemError if the object is found multiple times (for example with
        several file extensions, or as a file AND a folder)

        :param location: a location identifier compliant with the provided file mapping configuration
        :return: [True, singlefile_ext, singlefile_path] if a unique singlefile object is present ;
        False, MULTIFILE_EXT, complexobject_attributes_found] if a unique multifile object is present, with
        complexobject_attributes_found being a dictionary {name: location}
        """

        # First check what is present on the filesystem according to the filemapping
        simpleobjects_found = self.find_simpleobject_file_occurrences(location)
        complexobject_attributes_found = self.find_multifile_object_children(location, no_errors=True)

        # Then handle the various cases
        if len(simpleobjects_found) > 1 \
                or (len(simpleobjects_found) == 1 and len(complexobject_attributes_found) > 0):
            # the object is present several times > error
            u = simpleobjects_found
            u.update(complexobject_attributes_found)
            raise ObjectPresentMultipleTimesOnFileSystemError.create(location, list(u.keys()))
        elif len(simpleobjects_found) == 1:
            # create the output
            is_single_file = True
            ext = list(simpleobjects_found.keys())[0]
            singlefile_object_file_path = simpleobjects_found[ext]
            return is_single_file, ext, singlefile_object_file_path

        elif len(complexobject_attributes_found) > 0:
            # create the output
            is_single_file = False
            ext = MULTIFILE_EXT
            if '' in complexobject_attributes_found.keys() or None in complexobject_attributes_found.keys():
                raise IllegalContentNameError.create(location, complexobject_attributes_found[MULTIFILE_EXT])
            return is_single_file, ext, complexobject_attributes_found

        else:
            # the object was not found in a form that can be parsed
            raise ObjectNotFoundOnFileSystemError.create(location)

    def is_present_as_multifile_object(self, item_file_prefix: str) -> bool:
        """
        Implementing classes should return True if an item with this item_file_prefix is present as a multifile object,
        or False otherwise

        :param item_file_prefix:
        :return:
        """
        return len(self.find_multifile_object_children(item_file_prefix)) > 0

    @abstractmethod
    def find_multifile_object_children(self, parent_location: str, no_errors: bool = False) -> Dict[str, str]:
        """
        Implementing classes should return a dictionary of <item_name>, <item_location> containing the named elements
        in this multifile object.

        :param parent_location: the absolute file prefix of the parent item.
        :return: a dictionary of {item_name : item_prefix}
        """
        pass

    @abstractmethod
    def get_multifile_object_child_location(self, parent_location: str, child_name: str) -> str:
        """
        Implementing classes should return the expected location for the child named 'child_name' of the parent item
        located at 'parent_location'

        :param parent_location:
        :param child_name:
        :return:
        """
        pass

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
        pass


class FileMappingConfiguration(AbstractFileMappingConfiguration):
    """
    Abstract class for all file mapping configurations
    """

    class RecursivePersistedObject(PersistedObject):
        """
        Represents an object on the filesystem. It may be multifile or singlefile.
        When this object is created it performs the required file checks and logs them.
        """

        # flagdata_init = threading.local()

        def __init__(self, location: str, file_mapping_conf: AbstractFileMappingConfiguration = None, logger: Logger = None):
            """
            Creates a PersistedObject representing an object on the filesystem at location 'location'. It may be multifile
            or singlefile. When this object is created it performs the required file checks and logs them.

            :param location:
            :param file_mapping_conf:
            :param logger:
            """

            # -- file mapping
            check_var(file_mapping_conf, var_types=FileMappingConfiguration, var_name='file_mapping_conf')
            self.file_mapping_conf = file_mapping_conf

            # -- logger
            check_var(logger, var_types=Logger, var_name='logger', enforce_not_none=False)
            self.logger = logger

            try:
                # # Initial log message
                # in_root_call = False
                # if logger is not None:
                #     # log only for the root object, not for the children that will be created by the code below
                #
                #     if not hasattr(PersistedObject.flagdata_init, 'flag') or PersistedObject.flagdata_init.flag == 0:
                #         print('Checking all files under ' + self.location)
                #         PersistedObject.flagdata_init.flag = 1
                #         in_root_call = True

                # check single file or multifile
                is_singlefile, ext, self._contents_or_path = self.file_mapping_conf.get_unique_object_contents(location)

                super(FileMappingConfiguration.RecursivePersistedObject, self).__init__(location, is_singlefile, ext)

                # rather log after the get_unique_object, since the type of file will be shown. (a log is also in the
                # 'except' in case of failure)
                if logger is not None:
                    logger.info(str(self))

                # fill the self.children if multifile
                if not self.is_singlefile:
                    self.children = {
                    name: FileMappingConfiguration.RecursivePersistedObject(loc, file_mapping_conf=self.file_mapping_conf,
                                                                            logger=self.logger)
                    for name, loc in sorted(self._contents_or_path.items())}

            except Exception as e:
                if logger is not None:
                    # log the object that was being built, just for consistency of log messages
                    logger.info(location)
                raise e.with_traceback(e.__traceback__)

                # finally:
                #     # remove threadlocal flag if needed
                #     if in_root_call:
                #         PersistedObject.flagdata_init.flag = 0

                # if in_root_call:
                #     print('File checks done')

        def get_singlefile_path(self):
            if self.is_singlefile:
                return self._contents_or_path
            else:
                raise NotImplementedError(
                    'get_file_path does not make any sense on a multifile object. Use object.location'
                    ' to get the file prefix')

        def get_singlefile_encoding(self):
            if self.is_singlefile:
                return self.file_mapping_conf.encoding
            else:
                raise NotImplementedError('get_file_encoding does not make any sense on a multifile object. Check this '
                                          'object\'s children to know their encoding')

        def get_multifile_children(self) -> Dict[str, PersistedObject]:
            if self.is_singlefile:
                raise NotImplementedError(
                    'get_multifile_children does not mean anything on a singlefile object : a single file'
                    'object by definition has no children - check your code')
            else:
                return self.children

    def __init__(self, encoding:str = None):
        """
        Constructor, with the encoding registered to open the files.
        :param encoding: the encoding used to open the files default is 'utf-8'
        """
        super(FileMappingConfiguration, self).__init__(encoding)

    def create_persisted_object(self, item_file_prefix: str, logger: Logger) -> PersistedObject:

        #print('Checking all files under ' + item_file_prefix)
        logger.info('Checking all files under ' + item_file_prefix)
        obj = FileMappingConfiguration.RecursivePersistedObject(location=item_file_prefix, file_mapping_conf=self,
                                                                logger=logger)
        #print('File checks done')
        logger.info('File checks done')
        return obj


class WrappedFileMappingConfiguration(FileMappingConfiguration):
    """
    A file mapping where collection objects and multifile objects are in folders
    """
    def __init__(self, encoding:str = None):
        super(WrappedFileMappingConfiguration, self).__init__(encoding=encoding)


    def find_multifile_object_children(self, parent_location, no_errors: bool = False) -> Dict[str, str]:
        """
        Utility method to list all sub-items of a given parent item.
        In this mode, root_path should be a valid folder, and each item is a subfolder or a file :

            item_file_prefix/
            |-singlefile_sub_item1.<ext>
            |-singlefile_sub_item2.<ext>
            |-multifile_sub_item3/
              |- ...

        :param parent_location: the absolute file prefix of the parent item. it may be a folder (non-flat mode)
        or a folder + a file name prefix (flat mode)
        :param no_errors:
        :return: a dictionary of {item_name : item_prefix}
        """

        # Assert that folder_path is a folder
        if not isdir(parent_location):
            if no_errors:
                return dict()
            else:
                raise ValueError('Cannot find a multifileobject at location \'' + parent_location + '\' : location is '
                                 'not a valid folder')

        else:
            # List folders (multifile objects or collections)
            all_subfolders = [dir_ for dir_ in listdir(parent_location) if isdir(join(parent_location, dir_))]
            items = {item_name: join(parent_location, item_name) for item_name in all_subfolders}

            # List files *without* their extension
            items.update({
                          item_name: join(parent_location, item_name)
                          for item_name in [file_name[0:file_name.rindex(EXT_SEPARATOR)]
                                            for file_name in listdir(parent_location)
                                            if isfile(join(parent_location, file_name))
                                            and EXT_SEPARATOR in file_name]
                         })
        return items


    def get_multifile_object_child_location(self, parent_item_prefix: str, child_name: str) -> str:
        """
        Utility method to get the item_file_prefix corresponding to a parent path and an object.
        In this mode the attribute is a file in the parent object folder

        :param parent_item_prefix: the absolute file prefix of the parent item.
        :return: the file prefix for this attribute
        """
        check_var(parent_item_prefix, var_types=str, var_name='parent_item_prefix')
        check_var(child_name, var_types=str, var_name='item_name')

        # assert that folder_path is a folder
        if not isdir(parent_item_prefix):
            raise ValueError(
                'Cannot get attribute item in non-flat mode, parent item path is not a folder : ' + parent_item_prefix)
        return join(parent_item_prefix, child_name)


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
        :param separator: the character sequence used to separate an item name from an item attribute name. Only
        used in flat mode. Default is '.'
        :param encoding: encoding used to open the files. Default is 'utf-8'
        """
        super(FlatFileMappingConfiguration, self).__init__(encoding=encoding)

        check_var(separator, var_types=str, var_name='sep_for_flat', enforce_not_none=False, min_len=1)

        self.separator = separator or '.'

        if '/' in self.separator or '\\' in self.separator:
            raise ValueError('Separator cannot contain a folder separation character')


    def find_multifile_object_children(self, parent_location, no_errors: bool = False) -> Dict[str, str]:
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

        :param parent_location: the absolute file prefix of the parent item. It may be a folder (special case of the
         root folder) but typically is just a file prefix
        :param no_errors:
        :return: a dictionary of <item_name>, <item_path>
        """

        # Find the base directory and base name
        if isdir(parent_location):  # special case of root folder. maybe TODO be more strict: root_folder = self.root_folder
            parent_dir = parent_location
            base_prefix = ''
            start_with = ''
        else:
            parent_dir = dirname(parent_location)
            base_prefix = basename(parent_location) #+ self.separator
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
            end_name = item_file.find(self.separator, len(base_prefix + start_with))
            if end_name == -1:
                end_name = item_file.find(EXT_SEPARATOR, len(base_prefix + start_with))
            item_name = item_file[len(base_prefix + start_with):end_name]
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


    def get_multifile_object_child_location(self, parent_location: str, child_name: str):
        """
        In this mode the attribute is a file with the same prefix, separated from the parent object name by
        the character sequence <self.separator>

        :param parent_location: the absolute file prefix of the parent item.
        :param child_name:
        :return: the file prefix for this attribute
        """
        check_var(parent_location, var_types=str, var_name='parent_path')
        check_var(child_name, var_types=str, var_name='item_name')

        return parent_location + self.separator + child_name


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


