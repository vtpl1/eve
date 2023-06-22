import ast
import decimal
import itertools
from collections import OrderedDict
from copy import copy
from datetime import datetime
import simplejson as json
from bson import ObjectId, decimal128
from bson.dbref import DBRef
from flask import abort, g, request
from werkzeug.exceptions import HTTPException

from ...versioning import versioned_id_field
from eve.io.mysql.parser import ParseError, parse
from eve.auth import resource_auth
from eve.io.base import BaseJSONEncoder, ConnectionException, DataLayer
from eve.utils import (
    config,
    debug_error_message,
    str_to_date,
    str_type,
    validate_filters,
)
from .flask_pymysql import PyMySql


class MySql(DataLayer):
    """MySql data access layer for Eve REST API."""
    serializers = {
        'datetime': str_to_date,
        'number': lambda val: json.loads(val) if val is not None else None,
    }

    def init_app(self, app):
        self.driver = PyMySqls(self)
        self.mysql_prefix = None

    def find(self, resource, req, sub_resource_lookup, perform_count=True):
        """Retrieves a set of documents matching a given request. Queries can
        be expressed in two different formats: the mongo query syntax, and the
        python syntax. The first kind of query would look like: ::

            ?where={"name": "john doe"}

        while the second would look like: ::

            ?where=name=="john doe"

        The resultset if paginated.

        :param resource: resource name.
        :param req: a :class:`ParsedRequest`instance.
        :param sub_resource_lookup: sub-resource lookup from the endpoint url.

        """
        args = {}

        if req and req.max_results:
            args["limit"] = req.max_results

        if req and req.page > 1:
            args["skip"] = (req.page - 1) * req.max_results

        # TODO sort syntax should probably be coherent with 'where': either
        # mongo-like # or python-like. Currently accepts only mongo-like sort
        # syntax.

        # TODO should validate on unknown sort fields (mongo driver doesn't
        # return an error)

        client_sort = self._convert_sort_request_to_dict(req)
        spec = self._convert_where_request_to_dict(resource, req)

        bad_filter = validate_filters(spec, resource)
        if bad_filter:
            abort(400, bad_filter)

        if sub_resource_lookup:
            spec = self.combine_queries(spec, sub_resource_lookup)

        if (
            config.DOMAIN[resource]["soft_delete"]
            and not (req and req.show_deleted)
            and not self.query_contains_field(spec, config.DELETED)
        ):
            # Soft delete filtering applied after validate_filters call as
            # querying against the DELETED field must always be allowed when
            # soft_delete is enabled
            spec = self.combine_queries(spec, {config.DELETED: {"$ne": True}})

        spec = self._mongotize(spec, resource)

        client_projection = self._client_projection(req)

        datasource, spec, projection, sort = self._datasource_ex(
            resource, spec, client_projection, client_sort
        )

        if req and req.if_modified_since:
            spec[config.LAST_UPDATED] = {"$gt": req.if_modified_since}

        if len(spec) > 0:
            args["filter"] = spec

        if sort is not None:
            args["sort"] = sort

        if projection:
            args["projection"] = projection

        target = self.pymysql(resource).db
        try:
            query = "SELECT channel_id, event_type, event_starttime FROM v_event"
            print("query:------ {}".format(query))
            s = target.execute(query)
            print("+++++++++++ {}".format(s))
            # result = target.find(**args)
            result = s
        except TypeError as e:
            # pymysql raises ValueError when invalid query paramenters are
            # included. We do our best to catch them beforehand but, especially
            # with key/value sort syntax, invalid ones might still slip in.
            self.app.logger.exception(e)
            abort(400, description=debug_error_message(str(e)))

        if perform_count:
            try:
                count = 0  # target.count_documents(spec)
            except Exception:
                # fallback to deprecated method. this might happen when the query
                # includes operators not supported by count_documents(). one
                # documented use-case is when we're running on mongo 3.4 and below,
                # which does not support $expr ($expr must replace $where # in
                # count_documents()).

                # 1. Mongo 3.6+; $expr: pass
                # 2. Mongo 3.6+; $where: pass (via fallback)
                # 3. Mongo 3.4; $where: pass (via fallback)
                # 4. Mongo 3.4; $expr: fail (operator not supported by db)

                # See: http://api.mongodb.com/python/current/api/pymongo/collection.html#pymongo.collection.Collection.count
                count = target.count()
        else:
            count = None

        return result, count

    def _convert_sort_request_to_dict(self, req):
        """Converts the contents of a `ParsedRequest`'s `sort` property to
        a dict
        """
        client_sort = {}
        if req and req.sort:
            try:
                # assume it's mongo syntax (ie. ?sort=[("name", 1)])
                client_sort = ast.literal_eval(req.sort)
            except ValueError:
                # it's not mongo so let's see if it's a comma delimited string
                # instead (ie. "?sort=-age, name").
                sort = []
                for sort_arg in [s.strip() for s in req.sort.split(",")]:
                    if sort_arg[0] == "-":
                        sort.append((sort_arg[1:], -1))
                    else:
                        sort.append((sort_arg, 1))
                if len(sort) > 0:
                    client_sort = sort
            except Exception as e:
                self.app.logger.exception(e)
                abort(400, description=debug_error_message(str(e)))
        return client_sort

    def _convert_where_request_to_dict(self, resource, req):
        """Converts the contents of a `ParsedRequest`'s `where` property to
        a dict
        """
        query = {}
        if req and req.where:
            try:
                query = self._sanitize(resource, json.loads(req.where))
            except HTTPException:
                # _sanitize() is raising an HTTP exception; let it fire.
                raise
            except Exception:
                # couldn't parse as mongo query; give the python parser a shot.
                try:
                    query = parse(req.where)
                except ParseError:
                    abort(
                        400,
                        description=debug_error_message(
                            "Unable to parse `where` clause"
                        ),
                    )
        return query

    def _mongotize(self, source, resource, parse_objectid=False):
        """Recursively iterates a JSON dictionary, turning RFC-1123 strings
        into datetime values and ObjectId-link strings into ObjectIds.

        .. versionchanged:: 0.3
           'query_objectid_as_string' allows to bypass casting string types
           to objectids.

        .. versionchanged:: 0.1.1
           Renamed from _jsondatetime to _mongotize, as it now handles
           ObjectIds too.

        .. versionchanged:: 0.1.0
           Datetime conversion was failing on Py2, since 0.0.9 :P

        .. versionchanged:: 0.0.9
           support for Python 3.3.

        .. versionadded:: 0.0.4
        """
        resource_def = config.DOMAIN[resource]
        schema = resource_def.get("schema")
        id_field = resource_def["id_field"]
        id_field_versioned = versioned_id_field(resource_def)
        query_objectid_as_string = resource_def.get("query_objectid_as_string", False)
        parse_objectid = parse_objectid or not query_objectid_as_string

        def try_cast(k, v, should_parse_objectid):
            try:
                return datetime.strptime(v, config.DATE_FORMAT)
            except Exception:
                if k in (id_field, id_field_versioned) or should_parse_objectid:
                    try:
                        # Convert to unicode because ObjectId() interprets
                        # 12-character strings (but not unicode) as binary
                        # representations of ObjectId's.  See
                        # https://github.com/pyeve/eve/issues/508
                        try:
                            r = ObjectId(unicode(v))
                        except NameError:
                            # We're on Python 3 so it's all unicode already.
                            r = ObjectId(v)
                        return r
                    except Exception:
                        return v
                else:
                    return v

        def get_schema_type(keys, schema):
            def dict_sub_schema(base):
                if base.get("type") == "dict":
                    return base.get("schema")
                return base

            if not isinstance(schema, dict):
                return None
            if not keys:
                return schema.get("type")

            k = keys[0]
            keys = keys[1:]
            schema_type = schema[k].get("type") if k in schema else None
            if schema_type == "list":
                if "items" in schema[k]:
                    items = schema[k].get("items") or []
                    possible_types = [get_schema_type(keys, item) for item in items]
                    if "objectid" in possible_types:
                        return "objectid"
                    return next((t for t in possible_types if t), None)
                if "schema" in schema[k]:
                    # recursively check the schema
                    return get_schema_type(keys, dict_sub_schema(schema[k]["schema"]))
            elif schema_type == "dict":
                if "schema" in schema[k]:
                    return get_schema_type(keys, dict_sub_schema(schema[k]["schema"]))
            else:
                return schema_type

        for k, v in source.items():
            keys = k.split(".")
            schema_type = get_schema_type(keys, schema)
            is_objectid = (schema_type == "objectid") or parse_objectid
            if isinstance(v, dict):
                self._mongotize(v, resource, is_objectid)
            elif isinstance(v, list):
                for i, v1 in enumerate(v):
                    if isinstance(v1, dict):
                        source[k][i] = self._mongotize(v1, resource)
                    else:
                        source[k][i] = try_cast(k, v1, is_objectid)
            elif isinstance(v, str_type):
                source[k] = try_cast(k, v, is_objectid)

        return source

    def current_mysql_prefix(self, resource=None):
        auth = None
        try:
            if resource is None and request and request.endpoint:
                resource = request.endpoint[: request.endpoint.index("|")]
            if request and request.endpoint:
                auth = resource_auth(resource)
        except ValueError:
            pass
        px = auth.get_mysql_prefix() if auth else None

        if px is None:
            px = g.get("mysql_prefix", None)

        if px is None:
            if resource:
                px = config.DOMAIN[resource].get("mysql_prefix", "MYSQL")
            else:
                px = "MYSQL"

        return px

    def pymysql(self, resource=None, prefix=None):
        px = prefix if prefix else self.current_mysql_prefix(resource=resource)
        if px not in self.driver:
            # instantiate and add to cache
            self.driver[px] = PyMySql(self.app, px)
        # important, we don't want to preserve state between requests
        self.mysql_prefix = None
        try:
            return self.driver[px]
        except Exception as e:
            raise ConnectionException(e)


class PyMySqls(dict):
    def __init__(self, mysql, *args):
        self.mysql = mysql
        dict.__init__(self, args)

    @property
    def db(self):
        """Returns the 'default' PyMySql instance, which is either the
        'MySql.mysql_prefix' value or 'MYSQL'. This property is useful for
        backward compatibility as many custom Auth classes use the now obsolete
        'self.data.driver.db[collection]' pattern.
        """
        return self.mysql.pymysql().db
