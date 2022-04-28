from test_framework import *

import sys
sys.path.append("..")
from src.mysql_mapping import *

config["host"] = "127.0.0.1"
config["user"] = "root"
config["password"] = "empty"
config["database"] = "python_mysql_mapping_test"

@test
@uses_db
def example_test():
    #enable_sql_logging()
    class MyTable(Resource):
        name=VARCHAR(128)
        def __str__(self):
            return "(name={})".format(self.name)
    
    class MyOtherTable(Resource):
        name=VARCHAR(128)
        ref=MyTable
        def __str__(self):
            return "(name={}, ref={})".format(self.name, self.ref)

    MyOtherTable(
        name="hola",
        ref=MyTable(
            name="hello"
        )
    ).insert()

    selector = Select(MyOtherTable).leftjoin(MyTable)
    print(MyOtherTable.select()[0])
    print(selector.fetch()[0].MyOtherTable)
    print(selector.fetch()[0].MyTable)

    MyTable.delete_table()
    MyOtherTable.delete_table()

run_test()