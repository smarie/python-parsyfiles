from typing import Type, Any, Tuple, List, Set, Dict


def get_pretty_type_str(object_type):
    """
    Utility method to check if a type is a subclass of typing.{List,Dict,Set,Tuple}. In that case returns a
    user-friendly character string with the inner item types, such as Dict[str, int].

    :param object_type:
    :return: type.__name__ if type is not a subclass of typing.{List,Dict,Set,Tuple}, otherwise
    type__name__[list of inner_types.__name__]
    """

    try:
        contents_item_type, contents_key_type = _extract_collection_base_type(object_type)
        if contents_key_type is not None:
            return object_type.__name__ + '[' + contents_key_type.__name__ + ', ' + contents_item_type.__name__ + ']'
        elif contents_item_type is not None:
            object_type.__name__ + '[' + contents_item_type.__name__ + ']'
    except Exception as e:
        pass

    try:
        return object_type.__name__
    except:
        return str(object_type)


def is_collection(object_type):
    """
    Utility method to check if a type is a subclass of typing.{List,Dict,Set,Tuple}
    or of list, dict, set, tuple

    :param object_type:
    :return:
    """
    return issubclass(object_type, Dict) \
           or issubclass(object_type, List) \
           or issubclass(object_type, Set) \
           or issubclass(object_type, Tuple) \
           or issubclass(object_type, dict) \
           or issubclass(object_type, list) \
           or issubclass(object_type, tuple) \
           or issubclass(object_type, set)


def _extract_collection_base_type(collection_object_type: Type[Any], item_name_for_errors: str = None):
    """
    Utility method to extract the base item type from a collection/iterable item type.
    Throws
    * a TypeError if the collection_object_type a Dict with non-string keys.
    * a TypeError if the collection_object_type is a Tuple (not handled yet)
    * an AttributeError if the collection_object_type is actually not a collection
    * a TypeInformationRequiredError if somehow the inner type can't be found from the collection type (either if dict,
    list, set, tuple were used instead of their typing module equivalents (Dict, List, Set, Tuple), or if the latter
    were specified without inner content types (as in Dict[str, Foo])

    :param collection_object_type:
    :param item_name_for_errors:
    :return:
    """
    item_name_for_errors = item_name_for_errors or '<item>'
    contents_item_type = None
    contents_key_type = None

    if issubclass(collection_object_type, Dict):
        # Dictionary
        # noinspection PyUnresolvedReferences
        if hasattr(collection_object_type, '__args__'):
            contents_key_type, contents_item_type = collection_object_type.__args__
            if not issubclass(contents_key_type, str):
                raise TypeError('Item ' + item_name_for_errors + ' has type Dict, but its PEP484 type hints declare '
                                'keys as being of type ' + str(contents_key_type) + ' which is not supported. Only str '
                                'keys are supported at the moment, since we use them as item names')

    elif issubclass(collection_object_type, List) or issubclass(collection_object_type, Set):
        # List or Set
        # noinspection PyUnresolvedReferences
        if hasattr(collection_object_type, '__args__'):
            contents_item_type = collection_object_type.__args__[0]

    elif issubclass(collection_object_type, Tuple):
        # Tuple
        # noinspection PyUnresolvedReferences
        if hasattr(collection_object_type, '__args__'):
            contents_item_type = collection_object_type.__args__[0]
            raise TypeError('Tuple attributes are not supported yet')

    elif issubclass(collection_object_type, dict) or issubclass(collection_object_type, list) \
            or issubclass(collection_object_type, tuple) or issubclass(collection_object_type, set):
        # unsupported collection types
        # raise TypeError('Found attribute type <' + get_pretty_type_str(collection_object_type) + '>. Please use one of '
        #                 'typing.Dict, typing.Set, typing.List, or typing.Tuple instead, in order to enable '
        #                 'type discovery for collection items')

        # the error is now handled below with the other under-specified types situations
        pass

    else:
        # Not a collection
        raise AttributeError('Cannot extract collection base type for item ' + item_name_for_errors + ', object type <'
                             + str(collection_object_type) + '> is not a collection')

    # Finally return if something was found, otherwise tell it
    if contents_item_type is None:
        raise TypeInformationRequiredError.create_for_collection_items(collection_object_type)
    else:
        return contents_item_type, contents_key_type


class TypeInformationRequiredError(Exception):
    """
    Raised whenever an object can not be parsed - but there is a file present
    """
    def __init__(self, contents):
        """
        We actually can't put more than 1 argument in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725
        That's why we have a helper static method create()

        :param contents:
        """
        super(TypeInformationRequiredError, self).__init__(contents)

    @staticmethod
    def create_for_collection_items(item_type: Type[Any]):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return TypeInformationRequiredError('Cannot parse object of type <' + str(item_type) + '> as a'
                                            ' collection: this type has no valid PEP484 type hint about its contents.'
                                            ' Please use a full declaration such as Dict[str, Foo] or List[Foo]')

    @staticmethod
    def create_for_object_attributes(item_type: Type[Any], faulty_attribute_name: str):
        """
        Helper method provided because we actually can't put that in the constructor, it creates a bug in Nose tests
        https://github.com/nose-devs/nose/issues/725

        :param item_type:
        :return:
        """
        return TypeInformationRequiredError('Cannot parse object of type <' + str(item_type) + '> using a '
                                            'configuration file as a \'dictionary of dictionaries\': '
                                            'attribute \'' + faulty_attribute_name + '\' has no valid '
                                            'PEP484 type hint.')