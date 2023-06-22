from eve import Eve
from eve.io.mongo.mongo import Mongo
from eve.io.mysql import MySql
from settings import SETTINGS
# settings = {
#     "MYSQL_HOST": "172.16.4.24",
#     "MYSQL_PORT": "3309",
#     "MYSQL_DBNAME": "ivms_30",
#     "MYSQL_USERNAME": "root",
#     "MYSQL_PASSWORD": "root",
#     "DOMAIN": {"people": {}, "v_event": {}},
# }

app = Eve(settings=SETTINGS, data=MySql)
app.run()
# import mysql.connector
# import datetime

# config = {
#     "user": "root",
#     "password": "root",
#     "host": "172.16.4.24",
#     "port": 3309,
#     "database": "ivms_30",
#     "raise_on_warnings": True,
#     "use_pure": False,
# }


# with mysql.connector.connect(**config) as cnx:
#     cursor = cnx.cursor()

#     query = (
#         "SELECT channel_id, event_type, event_starttime FROM v_event "
#         "WHERE event_starttime BETWEEN %s AND %s"
#     )

#     start = datetime.datetime(2023, 5, 1).timestamp() * 1000
#     end = datetime.datetime(2023, 6, 30).timestamp() * 1000
#     print("start time: {}, end time: {}".format(start, end))

#     cursor.execute(query, (start, end))

#     for channel_id, event_type, event_starttime in cursor:
#         print(
#             "{}, {} fff {:%d %b %Y}".format(
#                 channel_id, event_type, datetime.datetime.fromtimestamp(event_starttime/1000)
#             )
#         )

#     cursor.close()
