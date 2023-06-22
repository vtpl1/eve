import ast
import sys
from datetime import datetime  # noqa
import operator as sqla_op
from sqlalchemy.sql import expression as sqla_exp
from bson import ObjectId

from eve.utils import str_to_date  # noqa

class ParseError(ValueError):
    pass

def parse(expression, model):
    """
    Given a python-like conditional statement, returns the equivalent
    SQLAlchemy-like query expression. Conditional and boolean operators
    (==, <=, >=, !=, >, <) are supported.
    """
    v = MySqlVisitor(model)
    try:
        v.visit(ast.parse(expression))
    except SyntaxError as e:
        e = ParseError(e)
        e.__traceback__ = sys.exc_info()[2]
        raise e
    return v.sqla_query

def parse_sorting(model, key, order=1, expression=None):
    """Sorting parser that works with embedded resources and sql expressions.
    Returns a tuple containing the argument for `order_by` and a list of
    conditions to be used with `filter`, e.g.:
    order_by, conditions = parse_sorting(...)
    query = query.filter(*conditions).order_by(order_by)
    """
    attr, conditions = _parse_attribute_name(model, key)
    if order == -1:
        attr = attr.desc()
    if expression:  # sql expressions
        expression = getattr(attr, expression)
        attr = expression()
    return (attr, conditions)

def _parse_attribute_name(model, name):
    """Parses a (probably) nested attribute name.
    Returns a tuple containing an `InstrumentedAttribute` and a list of
    conditions to be used with `filter`.
    """
    parts = iter(name.split('.'))
    attr = getattr(model, next(parts))
    joins = []
    for part in parts:
        rel = attr.property
        rel_class = rel.mapper.class_
        if rel.primaryjoin is not None:
            joins.append(rel.primaryjoin)
        if rel.secondaryjoin is not None:
            joins.append(rel.secondaryjoin)
        attr = getattr(rel_class, part)
    return (attr, joins)

class MySqlVisitor(ast.NodeVisitor):
    """Implements the python-to-sql parser. Only Python conditional
    statements are supported, however nested, combined with most common compare
    and boolean operators (And and Or).
    Supported compare operators: ==, >, <, !=, >=, <=
    Supported boolean operators: And, Or
    """
    op_mapper = {
        ast.Eq: sqla_op.eq,
        ast.Gt: sqla_op.gt,
        ast.GtE: sqla_op.ge,
        ast.Lt: sqla_op.lt,
        ast.LtE: sqla_op.le,
        ast.NotEq: sqla_op.ne,
        ast.Or: sqla_exp.or_,
        ast.And: sqla_exp.and_
    }
    def __init__(self, model):
        self.model = model
        self.sqla_query = []
        self.ops = []
        self.current_value = None

    def visit_Module(self, node):
        """Module handler, our entry point."""
        self.sqla_query  = {}
        self.ops = []
        self.current_value = None

        # perform the magic.
        self.generic_visit(node)

        # if we didn't obtain a query, it is likely that an unsupported
        # python expression has been passed.
        if not self.sqla_query:
            raise ParseError(
                "Only conditional statements with boolean "
                "(and, or) and comparison operators are "
                "supported."
            )

    def visit_Expr(self, node):
        """Make sure that we are parsing compare or boolean operators"""
        if not (
            isinstance(node.value, ast.Compare) or isinstance(node.value, ast.BoolOp)
        ):
            raise ParseError("Will only parse conditional statements")
        self.generic_visit(node)

    def visit_Compare(self, node):
        """Compare operator handler."""
        self.visit(node.left)
        
        left, joins = _parse_attribute_name(self.model, self.current_value)
        for join in joins:
            self.sqla_query.append(join)

        operation = self.op_mapper[node.ops[0].__class__] if node.ops else None

        if node.comparators:
            comparator = node.comparators[0]
            self.visit(comparator)

        value = self.current_value

        if (False):
            pass

        # Relations:
        elif (hasattr(left, 'property') and
              hasattr(left.property, 'remote_side')):
            relationship = left.property
            if relationship.primaryjoin is not None:
                self.sqla_query.append(relationship.primaryjoin)
            if relationship.secondaryjoin is not None:
                self.sqla_query.append(relationship.secondaryjoin)
            remote_column = list(relationship.remote_side)[0]
            if relationship.uselist:
                if callable(relationship.argument):
                    mapper = relationship.argument().__mapper__
                else:
                    mapper = relationship.argument
                remote_column = list(mapper.primary_key)[0]
            left = remote_column

        if self.ops:
            self.ops[-1]['args'].append(operation(left, value))
        else:
            self.sqla_query.append(operation(left, value))

    def visit_BoolOp(self, node):
        """Boolean operator handler."""
        op = self.op_mapper[node.op.__class__]
        self.ops.append({'op': op, 'args': []})
        for value in node.values:
            self.visit(value)

        tops = self.ops.pop()
        if self.ops:
            self.ops[-1]['args'].append(tops['op'](*tops['args']))
        else:
            self.sqla_query.append(tops['op'](*tops['args']))

    def visit_Call(self, node):
        # TODO ?
        pass

    def visit_Attribute(self, node):
        """Attribute handler ('Contact.Id')."""
        self.visit(node.value)
        self.current_value += "." + node.attr

    def visit_Name(self, node):
        """Names handler."""
        if node.id.lower() in ['none', 'null']:
            self.current_value = None
        else:
            self.current_value = node.id

    def visit_Num(self, node):
        """Numbers handler."""
        self.current_value = node.n

    def visit_Str(self, node):
        """Strings handler."""
        try:
            value = str_to_date(node.s)
            self.current_value = value if value is not None else node.s
        except ValueError:
            self.current_value = node.s
