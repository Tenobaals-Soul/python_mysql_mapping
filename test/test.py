from test_framework import *

import sys
sys.path.append("..")
sys.path.append("src")
from mysql_mapping import *

config["host"] = "127.0.0.1"
config["user"] = "root"
config["password"] = "empty"
config["database"] = "python_mysql_mapping_test"

tables = []

@test
@uses_db
def example_test():
    #enable_sql_logging()
    class MyTable(Resource):
        name=VARCHAR(128)
        def __str__(self):
            return "(name={})".format(self.name)
    tables.append(MyTable)
    class MyOtherTable(Resource):
        name=VARCHAR(128)
        ref=MyTable
        def __str__(self):
            return "(name={}, ref={})".format(self.name, self.ref)
    tables.append(MyOtherTable)
    MyOtherTable(
        name="hola",
        ref=MyTable(
            name="hello"
        )
    ).insert()

    selector = Select(MyOtherTable).leftjoin(MyTable)
    item0 = MyOtherTable.select(auto_join=False)[0]
    assert_equal(item0.name, "hola")
    item1 = selector.fetch(auto_join=True)[0].MyTable
    item2 = selector.fetch(auto_join=True)[0].MyOtherTable
    assert_equal(item1.name, "hello")
    assert_equal(item2.name, "hola")
    assert_type(item0.ref, int)
    assert_equal(item0.ref, item1.id)
    assert_equal(item2.ref, item1)
    assert_equal(id(item1), id(item2.ref))

run_test()

for table in tables:
    table.delete_table()