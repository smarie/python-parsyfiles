import attr
from attr import fields
from attr.validators import _OptionalValidator, _InstanceOfValidator


def _guess_type_from_validator(validator):
    """
    Utility method to return the declared type of an attribute or None. It handles _OptionalValidator and _AndValidator
    in order to unpack the validators.

    :param validator:
    :return: the type of attribute declared in an inner 'instance_of' validator (if any is found, the first one is used)
    or None if no inner 'instance_of' validator is found
    """
    if isinstance(validator, _OptionalValidator):
        # Optional : look inside
        return _guess_type_from_validator(validator.validator)

    elif isinstance(validator, _AndValidator):
        # Sequence : try each of them
        for v in validator.validators:
            typ = _guess_type_from_validator(v)
            if typ is not None:
                return typ
        return None

    elif isinstance(validator, _InstanceOfValidator):
        # InstanceOf validator : found it !
        return validator.type

    else:
        # we could not find the type
        return None


def guess_type_from_validators(attr):
    """
    Utility method to return the declared type of an attribute or None. It handles _OptionalValidator and _AndValidator
    in order to unpack the validators.

    :param attr:
    :return: the type of attribute declared in an inner 'instance_of' validator (if any is found, the first one is used)
    or None if no inner 'instance_of' validator is found
    """
    return _guess_type_from_validator(attr.validator)


def is_mandatory(attr):
    """
    Helper method to find if an attribute is mandatory

    :param attr:
    :return:
    """
    return not isinstance(attr.validator, _OptionalValidator)


def get_attrs_declarations(item_type):
    """
    Helper method to return a dictionary of tuples. Each key is attr_name, and value is (attr_type, attr_is_optional)

    :param item_type:
    :return:
    """

    # this will raise an error if the type is not an attr-created type
    attribs = fields(item_type)

    res = dict()
    for attr in attribs:
        attr_name = attr.name

        # -- is the attribute mandatory ?
        mandatory = is_mandatory(attr)

        # -- get and check the attribute type
        typ = guess_type_from_validators(attr)

        # -- store both info in result dict
        res[attr_name] = (typ, mandatory)

    return res


@attr.s(repr=False, slots=True)
class _AndValidator(object):
    validators = attr.ib()

    def __call__(self, inst, attr, value):
        for v in self.validators:
            v(inst, attr, value)
        return

    def __repr__(self):
        return (
            "<validator sequence : {seq}>".format(seq=repr(self.validators))
        )


def chain(*validators):
    """
    A validator that applies several validators in order

    :param validators: A sequence of validators
    """
    return _AndValidator(validators)