import attr
from attr import fields
from attr.validators import _OptionalValidator, _InstanceOfValidator


def guess_type_from_validators(validator):
    if isinstance(validator, _OptionalValidator):
        # Optional : look inside
        return guess_type_from_validators(validator.validator)

    elif isinstance(validator, _AndValidator):
        # Sequence : try each of them
        for v in validator.validators:
            typ = guess_type_from_validators(v)
            if typ is not None:
                return typ
        return None

    elif isinstance(validator, _InstanceOfValidator):
        # InstanceOf validator : found it !
        return validator.type

    else:
        # we could not find the type
        return None


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
        is_mandatory = not isinstance(attr.validator, _OptionalValidator)

        # -- get and check the attribute type
        typ = guess_type_from_validators(attr.validator)

        # -- store both info in result dict
        res[attr_name] = (typ, is_mandatory)

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