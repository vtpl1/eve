from flask import current_app
# import mysql.connector
from sqlalchemy import create_engine

class PyMySql:
    """
    Creates MySql connection and database based on Flask configuration.
    """

    def __init__(self, app, config_prefix="MYSQL"):
        if "pymysql" not in app.extensions:
            app.extensions["pymysql"] = {}

        if config_prefix in app.extensions["pymysql"]:
            raise Exception('duplicate config_prefix "%s"' % config_prefix)

        self.config_prefix = config_prefix

        def key(suffix):
            return "%s_%s" % (config_prefix, suffix)

        def config_to_kwargs(mapping):
            """
            Convert config options to kwargs according to provided mapping
            information.
            """
            kwargs = {}
            for option, arg in mapping.items():
                if key(option) in app.config:
                    kwargs[arg] = app.config[key(option)]
            return kwargs

        app.config.setdefault(key("HOST"), "localhost")
        app.config.setdefault(key("PORT"), 3306)
        app.config.setdefault(key("DBNAME"), app.name)
        dbname = app.config[key("DBNAME")]
        host = app.config[key("HOST")]
        port = app.config[key("PORT")]

        client_mapping = {
            "HOST": "host",
            "PORT": "port",
            "DBNAME": "database",
        }
        client_kwargs = config_to_kwargs(client_mapping)
        auth_kwargs = {}
        if key("USERNAME") in app.config:
            app.config.setdefault(key("PASSWORD"), None)
            username = app.config[key("USERNAME")]
            password = app.config[key("PASSWORD")]
            auth = (username, password)
            if any(auth) and not all(auth):
                raise Exception("Must set both USERNAME and PASSWORD or neither")
            if any(auth):
                auth_mapping = {"USERNAME": "user", "PASSWORD": "password"}
                auth_kwargs = config_to_kwargs(auth_mapping)

        cx = create_engine(**{**client_kwargs, **auth_kwargs})
        db = cx.cursor()

        app.extensions["pymysql"][config_prefix] = (cx, db)

    @property
    def cx(self):
        """
        Automatically created :class:`~pymysql.Connection` object corresponding
        to the provided configuration parameters.
        """
        if self.config_prefix not in current_app.extensions["pymysql"]:
            raise Exception("flask_pymysql extensions is not initialized")
        return current_app.extensions["pymysql"][self.config_prefix][0]

    @property
    def db(self):
        """
        Automatically created :class:`~pymysql.Database` object
        corresponding to the provided configuration parameters.
        """
        if self.config_prefix not in current_app.extensions["pymysql"]:
            raise Exception("flask_pymysql extensions is not initialized")
        return current_app.extensions["pymysql"][self.config_prefix][1]
