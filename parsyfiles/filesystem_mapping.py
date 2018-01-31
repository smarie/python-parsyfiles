from abc import abstractmethod, ABCMeta
from logging import Logger
from os import listdir, sep
from os.path import isfile, join, isdir, dirname, basename, exists, splitext
from typing import Dict, List, Any, Tuple, Union

from parsyfiles.global_config import GLOBAL_CONFIG
from parsyfiles.var_checker import check_var

EXT_SEPARATOR = '.'
MULTIFILE_EXT = '<multifile>'


class ObjectPresentMultipleTimesOnFileSystemError(Exception):
    """
    Raised whenever a given attribute is present several times in the filesystem (with multiple extensions)
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
    def create(location: str, extensions_found: List[str] = None):  # -> NoParserFoundForObject:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param location:
        :param extensions_found:
        :return:
        """
        if not extensions_found:
            return ObjectPresentMultipleTimesOnFileSystemError('Object : ' + location + ' is present multiple '
                                                               'times on the file system.')
        else:
            return ObjectPresentMultipleTimesOnFileSystemError('Object : ' + location + ' is present multiple '
                                                               'times on the file system , with extensions : ' +
                                                               str(extensions_found) + '. Only one version of each '
                                                               'object should be provided. If you need multiple files'
                                                               ' to create this object, you should create a multifile'
                                                               ' object instead (with each file having its own name and'
                                                               ' a shared prefix)')


class ObjectNotFoundOnFileSystemError(FileNotFoundError):
    """
    Raised whenever a given object is missing on the filesystem (no singlefile nor multifile found)
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
    def create(location: str, simpleobjects_found = None, complexobject_attributes_found = None):  # -> ObjectNotFoundOnFileSystemError:
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param location:
        :return:
        """
        if len(complexobject_attributes_found) > 0 or len(simpleobjects_found) > 0:
            return ObjectNotFoundOnFileSystemError('Mandatory object : ' + location + ' could not be found on the file'
                                                   ' system, either as a multifile or as a singlefile with any '
                                                   'extension, but it seems that this is because you have left the '
                                                   'extension in the location name. Please remove the file extension '
                                                   'from the location name and try again')
        else:
            return ObjectNotFoundOnFileSystemError('Mandatory object : ' + location + ' could not be found on the file'
                                                   ' system, either as a multifile or as a singlefile with any '
                                                   'extension.')


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


class AbstractFileMappingConfiguration(metaclass=ABCMeta):
    """
    Represents a file mapping configuration. It should be able to find singlefile and multifile objects at specific
    locations. Note that this class does not know the concept of PersistedObject, it just manipulates locations.
    """

    def __init__(self, encoding: str = None):
        """
        Constructor, with the encoding registered to open the singlefiles.

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
        * IllegalContentNameError if a multifile child name is None or empty string.

        It relies on the abstract methods of this class (find_simpleobject_file_occurrences and
        find_multifile_object_children) to find the various files present.

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
            # a singlefile object > create the output
            is_single_file = True
            ext = list(simpleobjects_found.keys())[0]
            singlefile_object_file_path = simpleobjects_found[ext]
            return is_single_file, ext, singlefile_object_file_path

        elif len(complexobject_attributes_found) > 0:
            # a multifile object > create the output
            is_single_file = False
            ext = MULTIFILE_EXT
            if '' in complexobject_attributes_found.keys() or None in complexobject_attributes_found.keys():
                raise IllegalContentNameError.create(location, complexobject_attributes_found[MULTIFILE_EXT])
            return is_single_file, ext, complexobject_attributes_found

        else:
            # handle special case of multifile object with no children (if applicable)
            if self.is_multifile_object_without_children(location):
                is_single_file = False
                ext = MULTIFILE_EXT
                return is_single_file, ext, dict()
            else:
                # try if by any chance the issue is that location has an extension
                loc_without_ext = splitext(location)[0]
                simpleobjects_found = self.find_simpleobject_file_occurrences(loc_without_ext)
                complexobject_attributes_found = self.find_multifile_object_children(loc_without_ext, no_errors=True)

                # the object was not found in a form that can be parsed
                raise ObjectNotFoundOnFileSystemError.create(location, simpleobjects_found,
                                                             complexobject_attributes_found)

    def is_present_as_singlefile_object(self, location, sep_for_flat):
        """
        Utility method to check if an item is present as a simple object - that means, if there is any file matching
        this prefix with any extension

        :param location:
        :param sep_for_flat:
        :return:
        """
        return len(self.find_simpleobject_file_occurrences(location, sep_for_flat)) > 0

    @abstractmethod
    def find_simpleobject_file_occurrences(self, location) -> Dict[str, str]:
        """
        Implementing classes should return a dict of <ext, file_path> that match the given simple object, with any
        extension. If the object is found several times all extensions should be returned

        :param location:
        :return: a dictionary of {ext : file_path}
        """
        pass

    # def is_present_as_multifile_object(self, location: str) -> bool:
    #     """
    #     Returns True if an item with this location is present as a multifile object with children, or False otherwise
    #
    #     :param location:
    #     :return:
    #     """
    #     return len(self.find_multifile_object_children(location)) > 0

    @abstractmethod
    def is_multifile_object_without_children(self, location: str) -> bool:
        """
        Returns True if an item with this location is present as a multifile object without children
        :param location:
        :return:
        """

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


class PersistedObject(metaclass=ABCMeta):
    """
    Contains all information about an object persisted at a given location. It may be a multifile (in which case it has
    extension MULTIFILE) or a single file (in which cse it has an extension such as .txt, .cfg, etc.
    """

    def __init__(self, location: str, is_singlefile: bool, ext: str):
        """
        Constructor. A persisted object has a given filesystem location, is a singlefile or not (in which case it has
        children), and has an extension such as .txt, .cfg, etc. Multifile objects have

        :param location:
        :param is_singlefile:
        :param ext:
        """
        # -- location
        check_var(location, var_types=str, var_name='location')
        self.location = location
        # -- single file
        check_var(is_singlefile, var_types=bool, var_name='is_singlefile')
        self.is_singlefile = is_singlefile
        # -- ext
        check_var(ext, var_types=str, var_name='ext')
        self.ext = ext
        # -- sanity check
        if (is_singlefile and self.ext is MULTIFILE_EXT) or (not is_singlefile and self.ext is not MULTIFILE_EXT):
            raise ValueError('Inconsistent object definition : is_singlefile and self.ext should be consistent')

    def __str__(self) -> str:
        return self.get_pretty_location()

    def get_pretty_file_mode(self):
        """
        Utility method to return a string representing the mode of this file, 'singlefile' or 'multifile'
        :return:
        """
        return 'singlefile' if self.is_singlefile else 'multifile'

    def get_pretty_file_ext(self):
        """
        Utility method to return a string representing the mode and extension of this file,
        e.g 'singlefile, .txt' or 'multifile'
        :return:
        """
        return ('singlefile, ' + self.ext) if self.is_singlefile else 'multifile'

    def get_pretty_location(self, blank_parent_part: bool = False, append_file_ext: bool = True,
                            compact_file_ext: bool = False):
        """
        Utility method to return a string representing the location, mode and extension of this file.
        :return:
        """
        if append_file_ext:
            if compact_file_ext:
                suffix = self.ext if self.is_singlefile else ''
            else:
                suffix = ' (' + self.get_pretty_file_ext() + ')'
        else:
            suffix = ''
        if blank_parent_part:
            # TODO sep should be replaced with the appropriate separator in flat mode
            idx = self.location.rfind(sep)
            return (' ' * (idx-1-len(sep))) + '|--' + self.location[(idx+1):] + suffix
        else:
            return self.location + suffix

    def get_pretty_child_location(self, child_name, blank_parent_part: bool = False):
        """
        Utility method to return a string representation of the location of a child
        :param child_name:
        :param blank_parent_part:
        :return:
        """
        if blank_parent_part:
            idx = len(self.location)
            return (' ' * (idx-3)) + '|--' + child_name
        else:
            # TODO sep should be replaced with the appropriate separator in flat mode
            return self.location + sep + child_name

    @abstractmethod
    def get_singlefile_path(self):
        """
        Implementing classes should return the path of this file, in case of a singlefile. If multifile, they should 
        return an exception
        :return:
        """
        pass

    @abstractmethod
    def get_singlefile_encoding(self):
        """
        Implementing classes should return the file encoding, in case of a singlefile. If multifile, they should 
        return an exception
        :return: 
        """
        pass

    @abstractmethod
    def get_multifile_children(self) -> Dict[str, Any]: # actually, not Any but PersistedObject
        """
        Implementing classes should return a dictionary of PersistedObjects, for each named child of this object.
        :return: 
        """
        pass


class FolderAndFilesStructureError(Exception):
    """
    Raised whenever the folder and files structure does not match with the one expected
    """
    def __init__(self, contents):
        super(FolderAndFilesStructureError, self).__init__(contents)

    @staticmethod
    def create_for_multifile_tuple(obj_on_fs: PersistedObject, expected_size: int, found_size: int):
        return FolderAndFilesStructureError('Error trying to find a tuple of length ' + expected_size + ' at location '
                                            + str(obj_on_fs) + '. Nb of child files found is not correct, found '
                                            + found_size + ' files')


class FileMappingConfiguration(AbstractFileMappingConfiguration):
    """
    Abstract class for all file mapping configurations. In addition to be an AbstractFileMappingConfiguration (meaning
    that it can find objects at locations), it is able to create instances of PersistedObject, recursively.
    """

    class RecursivePersistedObject(PersistedObject):
        """
        Represents an object on the filesystem. It may be multifile or singlefile. When this object is created it
        recursively scans all of its children if any, and builds the corresponding PersistedObjects. All of this is
        logged on the provided logger if any.
        """

        def __init__(self, location: str, file_mapping_conf: AbstractFileMappingConfiguration = None,
                     logger: Logger = None, log_only_last: bool = False):
            """
            Creates a PersistedObject representing an object on the filesystem at location 'location'. It may be
            multifile or singlefile. When this object is created it recursively scans all of its children if any, and
            builds the corresponding PersistedObjects. All of this is logged on the provided logger if any.

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
                # -- check single file or multifile thanks to the filemapping
                is_singlefile, ext, self._contents_or_path = self.file_mapping_conf.get_unique_object_contents(location)

                # -- store all information in the container(parent class)
                super(FileMappingConfiguration.RecursivePersistedObject, self).__init__(location, is_singlefile, ext)

                # -- log this for easy debug
                if logger is not None:
                    logger.debug('(C) ' + self.get_pretty_location(
                        blank_parent_part=(log_only_last and not GLOBAL_CONFIG.full_paths_in_logs)))

                # -- create and attach all the self.children if multifile
                if not self.is_singlefile:
                    self.children = {name: FileMappingConfiguration.RecursivePersistedObject(loc,
                                     file_mapping_conf=self.file_mapping_conf, logger=self.logger, log_only_last=True)
                                     for name, loc in sorted(self._contents_or_path.items())}

            except (ObjectNotFoundOnFileSystemError, ObjectPresentMultipleTimesOnFileSystemError,
                    IllegalContentNameError) as e:
                # -- log the object that was being built, just for consistency of log messages
                if logger is not None:
                    logger.debug(location)
                raise e.with_traceback(e.__traceback__)

        def get_singlefile_path(self):
            """
            Implementation of the parent method
            :return:
            """
            if self.is_singlefile:
                return self._contents_or_path
            else:
                raise NotImplementedError(
                    'get_file_path_no_ext does not make any sense on a multifile object. Use object.location'
                    ' to get the file prefix')

        def get_singlefile_encoding(self):
            """
            Implementation of the parent method
            :return:
            """
            if self.is_singlefile:
                return self.file_mapping_conf.encoding
            else:
                raise NotImplementedError('get_file_encoding does not make any sense on a multifile object. Check this '
                                          'object\'s children to know their encoding')

        def get_multifile_children(self) -> Dict[str, PersistedObject]:
            """
            Implementation of the parent method
            :return:
            """
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

    def create_persisted_object(self, location: str, logger: Logger) -> PersistedObject:
        """
        Creates a PersistedObject representing the object at location 'location', and recursively creates all of its
        children

        :param location:
        :param logger:
        :return:
        """
        #print('Checking all files under ' + location)
        logger.debug('Checking all files under [{loc}]'.format(loc=location))
        obj = FileMappingConfiguration.RecursivePersistedObject(location=location, file_mapping_conf=self,
                                                                logger=logger)
        #print('File checks done')
        logger.debug('File checks done')
        return obj


class WrappedFileMappingConfiguration(FileMappingConfiguration):
    """
    A file mapping where multifile objects are represented by folders
    """
    def __init__(self, encoding:str = None):
        """
        Constructor, with the encoding registered to open the files.
        :param encoding: the encoding used to open the files default is 'utf-8'
        """
        super(WrappedFileMappingConfiguration, self).__init__(encoding=encoding)

    def find_multifile_object_children(self, parent_location, no_errors: bool = False) -> Dict[str, str]:
        """
        Implementation of the parent abstract method.

        In this mode, root_path should be a valid folder, and each item is a subfolder (multifile) or a file
        (singlefile):

            location/
            |-singlefile_sub_item1.<ext>
            |-singlefile_sub_item2.<ext>
            |-multifile_sub_item3/
              |- ...

        :param parent_location: the absolute file prefix of the parent item. it may be a folder (non-flat mode)
        or a folder + a file name prefix (flat mode)
        :param no_errors: a boolean used in internal recursive calls in order to catch errors. Should not be changed by
        users.
        :return: a dictionary of {item_name : item_prefix}
        """

        # (1) Assert that folder_path is a folder
        if not isdir(parent_location):
            if no_errors:
                return dict()
            else:
                raise ValueError('Cannot find a multifileobject at location \'' + parent_location + '\' : location is '
                                 'not a valid folder')

        else:
            # (2) List folders (multifile objects or collections)
            all_subfolders = [dir_ for dir_ in listdir(parent_location) if isdir(join(parent_location, dir_))]
            items = {item_name: join(parent_location, item_name) for item_name in all_subfolders}

            # (3) List singlefiles *without* their extension
            items.update({
                          item_name: join(parent_location, item_name)
                          for item_name in [file_name[0:file_name.rindex(EXT_SEPARATOR)]
                                            for file_name in listdir(parent_location)
                                            if isfile(join(parent_location, file_name))
                                            and EXT_SEPARATOR in file_name]
                         })
        # (4) return all
        return items

    def is_multifile_object_without_children(self, location: str) -> bool:
        """
        Returns True if an item with this location is present as a multifile object without children.
        For this implementation, this means that there is a folder without any files in it

        :param location:
        :return:
        """
        return isdir(location) and len(self.find_multifile_object_children(location)) == 0

    def get_multifile_object_child_location(self, parent_item_prefix: str, child_name: str) -> str:
        """
        Implementation of the parent abstract method.
        In this mode the attribute is a file inside the parent object folder

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

    def find_simpleobject_file_occurrences(self, location) -> Dict[str, str]:
        """
        Implementation of the parent abstract method.

        :param location:
        :return: a dictionary of {ext : file_path}
        """
        parent_dir = dirname(location)
        if parent_dir is '':
            parent_dir = '.'
        base_prefix = basename(location)

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
    A file mapping where multifile objects are group of files located in the same folder than their parent,
    with their parent name as the prefix, followed by a configurable separator.
    """

    def __init__(self, separator: str = None, encoding:str = None):
        """
        :param separator: the character sequence used to separate an item name from an item attribute name. Only
        used in flat mode. Default is '.'
        :param encoding: encoding used to open the files. Default is 'utf-8'
        """
        super(FlatFileMappingConfiguration, self).__init__(encoding=encoding)

        # -- check separator
        check_var(separator, var_types=str, var_name='sep_for_flat', enforce_not_none=False, min_len=1)
        self.separator = separator or '.'
        if '/' in self.separator or '\\' in self.separator:
            raise ValueError('Separator cannot contain a folder separation character')

    def find_multifile_object_children(self, parent_location, no_errors: bool = False) -> Dict[str, str]:
        """
        Implementation of the parent abstract method.

        In this mode, each item is a set of files with the same prefix than location, separated from the
        attribute name by the character sequence <self.separator>. The location may also be directly a folder,
        in which case the sub items dont have a prefix.

        example if location = '<parent_folder>/<file_prefix>'

        parent_folder/
        |-file_prefix<sep>singlefile_sub_item1.<ext>
        |-file_prefix<sep>singlefile_sub_item2.<ext>
        |-file_prefix<sep>multifile_sub_item3<sep>singlesub1.<ext>
        |-file_prefix<sep>multifile_sub_item3<sep>singlesub2.<ext>

        example if location = '<parent_folder>/

        parent_folder/
        |-singlefile_sub_item1.<ext>
        |-singlefile_sub_item2.<ext>
        |-multifile_sub_item3<sep>singlesub1.<ext>
        |-multifile_sub_item3<sep>singlesub2.<ext>

        :param parent_location: the absolute file prefix of the parent item. It may be a folder (special case of the
         root folder) but typically is just a file prefix
        :param no_errors:
        :return: a dictionary of <item_name>, <item_path>
        """
        if parent_location == '':
            parent_location = '.'

        # (1) Find the base directory and base name
        if isdir(parent_location):  # special case: parent location is the root folder where all the files are.
            parent_dir = parent_location
            base_prefix = ''
            start_with = ''
        else:
            parent_dir = dirname(parent_location)
            if parent_dir is '':
                parent_dir = '.'
            # TODO one day we'll rather want to have a uniform definition of 'location' across filemappings
            # Indeed as of today, location is not abstract from the file mapping implementation, since we
            # "just" use basename() rather than replacing os separators with our separator:
            base_prefix = basename(parent_location)  # --> so it should already include self.separator to be valid
            start_with = self.separator

        # (2) list children files that are singlefiles
        content_files = [content_file for content_file in listdir(parent_dir)
                         # -> we are in flat mode : should be a file not a folder :
                         if isfile(join(parent_dir,content_file))
                         # -> we are looking for children of a specific item :
                         and content_file.startswith(base_prefix)
                         # -> we are looking for multifile child items only :
                         and content_file != base_prefix
                         # -> they should start with the separator (or with nothing in case of the root folder) :
                         and (content_file[len(base_prefix):]).startswith(start_with)
                         # -> they should have a valid extension :
                         and (content_file[len(base_prefix + start_with):]).count(EXT_SEPARATOR) >= 1
                         ]
        # (3) build the resulting dictionary of item_name > item_prefix
        item_prefixes = dict()
        for item_file in content_files:
            end_name = item_file.find(self.separator, len(base_prefix + start_with))
            if end_name == -1:
                end_name = item_file.find(EXT_SEPARATOR, len(base_prefix + start_with))
            item_name = item_file[len(base_prefix + start_with):end_name]
            item_prefixes[item_name] = join(parent_dir, base_prefix + start_with + item_name)

        return item_prefixes

    def is_multifile_object_without_children(self, location: str) -> bool:
        """
        Returns True if an item with this location is present as a multifile object without children.
        For this implementation, this means that there is a file with the appropriate name but without extension

        :param location:
        :return:
        """
        # (1) Find the base directory and base name
        if isdir(location):  # special case: parent location is the root folder where all the files are.
            return len(self.find_multifile_object_children(location)) == 0
        else:
            # TODO same comment than in find_multifile_object_children
            if exists(location):
                # location is a file without extension. We can accept that as being a multifile object without children
                return True
            else:
                return False

    def get_multifile_object_child_location(self, parent_location: str, child_name: str):
        """
        Implementation of the parent abstract method.

        In this mode the attribute is a file with the same prefix, separated from the parent object name by
        the character sequence <self.separator>

        :param parent_location: the absolute file prefix of the parent item.
        :param child_name:
        :return: the file prefix for this attribute
        """
        check_var(parent_location, var_types=str, var_name='parent_path')
        check_var(child_name, var_types=str, var_name='item_name')

        # a child location is built by adding the separator between the child name and the parent location
        return parent_location + self.separator + child_name

    def find_simpleobject_file_occurrences(self, location) -> Dict[str, str]:
        """
        Implementation of the parent abstract method.

        :param location:
        :return: a dictionary{ext : file_path}
        """
        parent_dir = dirname(location)
        if parent_dir is '':
            parent_dir = '.'
        base_prefix = basename(location)

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


