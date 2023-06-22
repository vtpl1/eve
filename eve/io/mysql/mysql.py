import ast
import collections
from copy import copy
from http.client import HTTPException

import simplejson as json
from flask import abort, g, request

from eve.auth import resource_auth
from eve.io.base import ConnectionException, DataLayer
from eve.io.mysql.parser import ParseError, parse
from eve.utils import config, debug_error_message, str_to_date, validate_filters

string_type = str

from .flask_pymysql import PyMySql
from .parser import ParseError, parse, parse_dictionary, parse_sorting, sqla_op
from .structures import SQLAResultCollection
from .utils import (
    rename_relationship_fields_in_dict,
    rename_relationship_fields_in_sort_args,
    rename_relationship_fields_in_str,
    sqla_object_to_dict,
    validate_filters,
)


class MySql(DataLayer):
    """MySql data access layer for Eve REST API."""

    serializers = {
        "datetime": str_to_date,
        "number": lambda val: json.loads(val) if val is not None else None,
    }

    def init_app(self, app):
        self.driver = PyMySqls(self)
        self.mysql_prefix = None

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

        client_projection = self._client_projection(req)

        client_embedded = self._client_embedded(req)

        datasource, spec, projection, sort = self._datasource_ex(
            resource, spec, client_projection, client_sort
        )
        print("++++++++++++++" + datasource)
        if len(spec) > 0:
            args["filter"] = spec

        if sort is not None:
            args["sort"] = sort

        if projection:
            args["projection"] = projection

        model = datasource

        if req.where:
            try:
                where = rename_relationship_fields_in_str(model, req.where)
                args["spec"] = self.combine_queries(args["spec"], parse(where, model))
            except ParseError:
                try:
                    spec = rename_relationship_fields_in_dict(
                        model, json.loads(req.where)
                    )
                    args["spec"] = self.combine_queries(
                        args["spec"], parse_dictionary(spec, model)
                    )
                except (AttributeError, TypeError):
                    # if parse failed and json loads fails - raise 400
                    abort(400)

        bad_filter = validate_filters(args["spec"], resource)
        if bad_filter:
            abort(400, bad_filter)

        if sub_resource_lookup:
            sub_resource_lookup = rename_relationship_fields_in_dict(
                model, sub_resource_lookup
            )
            args["spec"] = self.combine_queries(
                args["spec"], parse_dictionary(sub_resource_lookup, model)
            )

        if req.if_modified_since:
            updated_filter = sqla_op.gt(
                getattr(model, self.app.config.LAST_UPDATED), req.if_modified_since
            )
            args["spec"].append(updated_filter)

        query = self.driver.db.session.query(model)

        if args["sort"]:
            args["sort"] = [parse_sorting(model, *a) for a in args["sort"]]

        if req.max_results:
            args["max_results"] = req.max_results
        if req.page > 1:
            args["page"] = req.page
        fields = projection
        return SQLAResultCollection(query, fields, **args)

    def find_one(
        self,
        resource,
        req,
        check_auth_value=True,
        force_auth_field_projection=False,
        mongo_options=None,
        **lookup
    ):
        client_projection = self._client_projection(req)
        client_embedded = self._client_embedded(req)
        model, filter_, fields, _ = self._datasource_ex(
            resource, [], client_projection, None, client_embedded
        )

        lookup = rename_relationship_fields_in_dict(model, lookup)
        id_field = self._id_field(resource)
        if isinstance(lookup.get(id_field), dict) or isinstance(
            lookup.get(id_field), list
        ):
            # very dummy way to get the related object
            # that commes from embeddable parameter
            return lookup
        else:
            filter_ = self.combine_queries(filter_, parse_dictionary(lookup, model))
            query = self.driver.db.session.query(model)
            document = query.filter(*filter_).first()

        return sqla_object_to_dict(document, fields) if document else None

    def find_one_raw(self, resource, **lookup):
        id_field = config.DOMAIN[resource]["id_field"]
        _id = lookup.get(id_field)

        model, filter_, fields, _ = self._datasource_ex(resource, [], None, None, None)
        id_field = self._id_field(resource)
        lookup = {id_field: _id}
        filter_ = self.combine_queries(filter_, parse_dictionary(lookup, model))
        document = self.driver.db.session.query(model).filter(*filter_).first()
        return sqla_object_to_dict(document, fields) if document else None

    def find_list_of_ids(self, resource, ids, client_projection=None):
        raise NotImplementedError

    def insert(self, resource, doc_or_docs):
        rv = []
        for document in doc_or_docs:
            model_instance = self._create_model_instance(resource, document)
            self.driver.db.session.add(model_instance)
            self.driver.db.session.commit()
            id_field = self._id_field(resource)
            document[id_field] = getattr(model_instance, id_field)
            rv.append(document[id_field])
        return rv

    def _create_model_instance(self, resource, dict_):
        model, _, _, _ = self._datasource_ex(resource)
        attrs = self._get_model_attributes(resource, dict_)
        return model(**attrs)

    def _get_model_attributes(self, resource, dict_):
        schema = self.app.config["DOMAIN"][resource]["schema"]
        fields = {}
        for field, value in dict_.items():
            if field in schema and "data_relation" in schema[field]:
                if isinstance(value, collections.Mapping):
                    fields[field] = self._create_model_instance(
                        schema[field]["data_relation"]["resource"], value
                    )
                elif "local_id_field" in schema[field]:
                    fields[schema[field]["local_id_field"]] = value
            elif field in schema and schema[field]["type"] in ("list", "set"):
                if (
                    "schema" in schema[field]
                    and "data_relation" in schema[field]["schema"]
                ):
                    sub_schema = schema[field]["schema"]
                    related_resource = sub_schema["data_relation"]["resource"]
                    contains_ids = False
                    list_ = []
                    for v in value:
                        if isinstance(v, collections.Mapping):
                            list_.append(
                                self._create_model_instance(related_resource, v)
                            )
                        else:
                            contains_ids = True
                            list_.append(v)
                    collection = set(list_) if schema[field]["type"] == "set" else list_
                    if contains_ids and "local_id_field" in schema[field]:
                        fields[schema[field]["local_id_field"]] = collection
                    elif contains_ids:
                        related_model = self._datasource_ex(related_resource)[0]
                        lookup = {sub_schema["data_relation"]["field"]: list(value)}
                        filter_ = parse_dictionary(lookup, related_model)
                        fields[field] = (
                            self.driver.db.session.query(related_model)
                            .filter(*filter_)
                            .all()
                        )
                        if schema[field]["type"] == "set":
                            fields[field] = set(fields[field])
                    else:
                        fields[field] = collection
                else:
                    fields[field] = value
            else:
                fields[field] = value
        return fields

    def replace(self, resource, id_, document, original):
        model, filter_, fields_, _ = self._datasource_ex(resource, [])
        id_field = self._id_field(resource)
        filter_ = self.combine_queries(
            filter_, parse_dictionary({id_field: id_}, model)
        )
        query = self.driver.db.session.query(model)

        # Find and delete the old object
        old_model_instance = query.filter(*filter_).first()
        if old_model_instance is None:
            abort(500, description=debug_error_message("Object not existent"))
        self._handle_immutable_id(id_field, old_model_instance, document)
        self.driver.db.session.delete(old_model_instance)

        # create and insert the new one
        model_instance = self._create_model_instance(resource, document)
        id_field = self._id_field(resource)
        setattr(model_instance, id_field, id_)
        self.driver.db.session.add(model_instance)
        self.driver.db.session.commit()

    def update(self, resource, id_, updates, original):
        model, filter_, _, _ = self._datasource_ex(resource, [])
        id_field = self._id_field(resource)
        filter_ = self.combine_queries(
            filter_, parse_dictionary({id_field: id_}, model)
        )
        query = self.driver.db.session.query(model)
        model_instance = query.filter(*filter_).first()
        if model_instance is None:
            abort(500, description=debug_error_message("Object not existent"))
        self._handle_immutable_id(id_field, model_instance, updates)
        attrs = self._get_model_attributes(resource, updates)
        for k, v in attrs.items():
            setattr(model_instance, k, v)
        self.driver.db.session.commit()

    def _handle_immutable_id(self, id_field, original_instance, updates):
        if (
            id_field in updates
            and getattr(original_instance, id_field) != updates[id_field]
        ):
            description = (
                "Attempt to update an immutable field. Usually happens "
                "when PATCH or PUT include a '%s' field, "
                "which is immutable (PUT can include it as long as "
                "it is unchanged)." % id_field
            )
            abort(400, description=description)

    def remove(self, resource, lookup):
        model, filter_, _, _ = self._datasource_ex(resource, [])
        lookup = rename_relationship_fields_in_dict(model, lookup)
        filter_ = self.combine_queries(filter_, parse_dictionary(lookup, model))
        query = self.driver.db.session.query(model)
        if len(filter_):
            query = query.filter(*filter_)
        for item in query:
            self.driver.db.session.delete(item)

        self.driver.db.session.commit()

    def _source(self, resource):
        return self.driver.app.config["SOURCES"][resource]["source"]

    def _id_field(self, resource):
        return self.driver.app.config["DOMAIN"][resource]["id_field"]

    def _model(self, resource):
        return self.driver.Model._decl_class_registry[self._source(resource)]

    def _parse_filter(self, model, filter):
        """
        Convert from Mongo/JSON style filters to SQLAlchemy expressions.
        """
        if filter is None or len(filter) == 0:
            filter = []
        elif isinstance(filter, string_type):
            filter = parse(filter, model)
        elif isinstance(filter, dict):
            filter = parse_dictionary(filter, model)
        elif not isinstance(filter, list):
            filter = []
        return filter

    def datasource(self, resource):
        """
        Overridden from super to return the actual model class of the database
        table instead of the name of it. We also parse the filter coming from
        the schema definition into a SQL compatible filter
        """
        model = self._model(resource)

        resource_def = self.driver.app.config["SOURCES"][resource]
        filter_ = resource_def["filter"]
        filter_ = self._parse_filter(model, filter_)
        projection_ = copy(resource_def["projection"])
        sort_ = copy(resource_def["default_sort"])
        return model, filter_, projection_, sort_

    # NOTE(Gonéri): preserve the _datasource method for compatibiliy with
    # pre 0.6 Eve release (See: commit 87742343fd0362354b9f75c749651f92d6e4a9c8
    # from the Eve repository)
    def _datasource(self, resource):
        return self.datasource(resource)

    def _datasource_ex(
        self,
        resource,
        query=None,
        client_projection=None,
        client_sort=None,
        client_embedded=None,
    ):
        model, filter_, fields_, sort_ = super(MySql, self)._datasource_ex(
            resource, query, client_projection, client_sort
        )
        filter_ = self._parse_filter(model, filter_)
        fields = [field for field in fields_.keys() if fields_[field]]
        if sort_ is not None:
            sort_ = rename_relationship_fields_in_sort_args(model, sort_)
        return model, filter_, fields, sort_

    def combine_queries(self, query_a, query_b):
        # TODO: dumb concatenation of query lists.
        #       We really need to check for duplicate queries
        query_a.extend(query_b)
        return query_a

    def is_empty(self, resource):
        model, filter_, _, _ = self.datasource(resource)
        query = self.driver.db.session.query(model)
        if len(filter_):
            return query.filter_by(*filter_).count() == 0
        else:
            return query.count() == 0

    def _client_embedded(self, req):
        """Returns a properly parsed client embeddable if available.

        :param req: a :class:`ParsedRequest` instance.

        .. versionadded:: 0.4
        """
        client_embedded = {}
        if req and req.embedded:
            try:
                client_embedded = json.loads(req.embedded)
            except json.JSONDecodeError:
                abort(
                    400,
                    description=debug_error_message(
                        "Unable to parse `embedded` clause"
                    ),
                )
        return client_embedded

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
