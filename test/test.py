from test_engine import *

import sys
sys.path.append("..")
sys.path.append("src")
from mysql_mapping import *

db_config["host"] = "127.0.0.1"
db_config["user"] = "root"
db_config["password"] = "empty"
db_config["database"] = "python_mysql_mapping_test"
enable_sql_logging()

@test
@uses_db
def insert_test():
    try:
        @resource
        class MyTable():
            name=VARCHAR(128)
            enum_val = ENUM("HELLO", "BYE")
            def __str__(self):
                return "(name={})".format(self.name)
        @resource
        class MyOtherTable():
            name=VARCHAR(128)
            ref=MyTable
            def __str__(self):
                return "(name={}, ref={})".format(self.name, self.ref)
        MyOtherTable(
            name="hola",
            ref=MyTable(
                enum_val="HELLO",
                name="hello"
            )
        ).insert()
        MyTable.delete_table()
        MyOtherTable.delete_table()
    except Exception as e:
        MyTable.delete_table()
        MyOtherTable.delete_table()
        raise e

@test
@uses_db
def select_test():
    try:
        @resource
        class MyTable():
            name=VARCHAR(128)
            def __str__(self):
                return "(name={})".format(self.name)
        @resource
        class MyOtherTable():
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
        MyTable.delete_table()
        MyOtherTable.delete_table()
    except Exception as e:
        MyTable.delete_table()
        MyOtherTable.delete_table()
        raise e

@test
@uses_db
def enum_set_test():
    try:
        @resource
        class MyTable():
            enum_val = ENUM("HELLO", "BYE")
            set_val = SET("WRITE", "READ")
            def __str__(self):
                return "(enum_val={}, set_val={})".format(self.enum_val, self.set_val)

        ref=MyTable(
            enum_val = "HELLO",
            set_val = "WRITE,READ"
        ).insert()
        select_result = MyTable.select("FIND_IN_SET('READ', set_val) > 0")
        assert_true(len(select_result) > 0)
        assert_equal(select_result[0].enum_val, "HELLO")
        MyTable.delete_table()
    except Exception as e:
        MyTable.delete_table()
        raise e

@test
@uses_db
def update_test():
    try:
        @resource
        class MyTable():
            name = VARCHAR(128)

        ref=MyTable().insert()
        ref.name = "Fred"
        assert_equal(ref.name, "Fred")
        assert_equal(MyTable.select()[0].name, "Fred")
        ref = MyTable.select()[0]
        assert_equal(ref.name, "Fred")
        ref.name = "Hanna"
        assert_equal(ref.name, "Hanna")
        assert_equal(MyTable.select()[0].name, "Hanna")
        MyTable.delete_table()
    except Exception as e:
        MyTable.delete_table()
        raise e

run_test()