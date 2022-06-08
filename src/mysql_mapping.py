from __future__ import annotations
import MySQLdb
import MySQLdb.connections
from typing import *
import weakref

OperationalError = MySQLdb.connections.OperationalError
ProgrammingError = MySQLdb.connections.ProgrammingError

cursor = None
_sql_query_log = False

db_config = {}

def enable_sql_logging():
    global _sql_query_log
    _sql_query_log = True

def disable_sql_logging():
    global _sql_query_log
    _sql_query_log = False

def uses_db(func):
    global cursor
    def manage_cursor(*args, **kwargs):
        global cursor
        if cursor is None:
            connection = MySQLdb.connect(**db_config)
            cursor = connection.cursor()
            return_val = func(*args, **kwargs)
            cursor.close()
            connection.commit()
            connection.close()
            cursor = None
        else:
            return_val = func(*args, **kwargs)
        return return_val
    return manage_cursor

def _smort_decode(src):
    return src.decode("utf-8") if isinstance(src, bytes) else src

def _format(query, *args):
    format_list = tuple([_smort_decode(cursor.connection.escape(arg)) for arg in args])
    return query % format_list

@uses_db
def _db_execute(query: str, *args):
    global _sql_query_log
    query = query.rstrip(" ").rstrip(";").rstrip(" ") + ";"
    args = tuple([(item.id if getattr(item, "__sql_table", None) is not None else item) for item in args])
    cursor.execute(query, args)
    if _sql_query_log:
        try:
            print("[SQLLOG]", cursor._last_executed.decode("utf-8"))
        except Exception:
            print("[SQLLOG]", _format(query, *args))
    data = cursor.fetchall()
    return data

class Select():
    class _JoinResult:
        pass

    def _immutable_err(self, field, val):
        raise Exception("Select is immutable")

    def __init__(self, resource: resource | Select, join_as: str = None, select_columns: str = None):
        if isinstance(resource, Select):
            self.__outputs = resource.__outputs
            self.__select_str = resource.__select_str
            self.__join_str = resource.__join_str
            self.__limit = resource.__limit
            self.__order_string = resource.__order_string
            self.__group_str = resource.__group_str
        else:
            if join_as is None:
                join_as = resource.__name__
            self.__group_str = ""
            self.__order_string = ""
            self.__outputs = [(resource, join_as)]
            if select_columns is None:
                self.__select_str = "{}.*".format(join_as)
            else:
                self.__select_str = select_columns
            self.__join_str = "FROM {table} AS {name}".format(table=resource.__name__, name=join_as)
            self.__setattr__ = self._immutable_err
            self.__limit = ""

    def join(self, resource: resource, join_as: str = None, join_on: str = "TRUE", select_columns: str = None):
        return self._join("JOIN", resource, join_as, join_on, select_columns)

    def leftjoin(self, resource: resource, join_as: str = None, join_on: str = "TRUE", select_columns: str = None):
        return self._join("LEFT JOIN", resource, join_as, join_on, select_columns)

    def rightjoin(self, resource: resource, join_as: str = None, join_on: str = "TRUE", select_columns: str = None):
        return self._join("RIGHT JOIN", resource, join_as, join_on, select_columns)

    def _join(self, join_type: str, resource: resource, join_as: str, join_on: str, select_columns: str = None):
        if join_as is None:
            join_as = resource.__name__
        new_select = Select(self)
        for item in new_select.__outputs:
            if join_as == item[0]:
                raise MySQLdb.ProgrammingError("could not join two tables as the same")
        if select_columns is None:
            new_select.__select_str += ", {}.*".format(join_as)
        else:
            new_select.__select_str += ", {}".format(select_columns)
        if select_columns is None:
            new_select.__outputs.append((resource, join_as))
        else:
            new_select.__outputs.append((len(select_columns.split(",")), join_as))
        new_select.__join_str += " {join_type} {table} AS {name} ON {join_on}"\
            .format(join_type=join_type, table=resource.__name__, name=join_as, join_on=join_on)
        new_select.__setattr__ = self._immutable_err
        return new_select

    def _pack_object(self, data_row, auto_join):
        write_output_index = 0
        current_index = 0
        output = self._JoinResult()
        for j in range(len(self.__outputs)):
            if isinstance(self.__outputs[j][0], int):
                out_count = self.__outputs[j][0]
                out_name = self.__outputs[j][1]
                item = []
                for l in range(out_count):
                    item.append(data_row[current_index + l])
                output.__setattr__(out_name, item)
            else:
                out_type = self.__outputs[j][0]
                out_name = self.__outputs[j][1]
                item_id = data_row[0]
                current_index += 1
                item = out_type()
                val_access_list = out_type.get_val_access_fields()
                for i in range(len(val_access_list)):
                    if auto_join and isinstance(out_type._column_list[i][1], type) and getattr(out_type._column_list[i][1], "__sql_table", None) is not None:
                        data = out_type._column_list[i][1]._loaded_items.get(data_row[current_index])
                        if data is None:
                            data = out_type._column_list[i][1].select("id = %s", data_row[current_index])
                            if (len(data) > 0):
                                data = data[0]
                            else:
                                data = None
                    else:
                        data = data_row[current_index]
                    item.__setattr__("__" + val_access_list[i], data)
                    current_index += 1
                item._set_id(item_id)
                output.__setattr__(out_name, item)
                out_type._loaded_items[item_id] = item
                write_output_index += 1
        return output

    def fetch(self, where_clause: str = "TRUE", *args, auto_join=False) -> List(Any):
        data = _db_execute("SELECT {} {} WHERE {} {} {} {};".format(
            self.__select_str,
            self.__join_str,
            where_clause,
            self.__group_str,
            self.__order_string,
            self.__limit
        ), *args)
        output = [None for _ in data]
        for i in range(len(data)):
            output[i] = self._pack_object(data[i], auto_join)
        return output

    def fetchone(self, where_clause: str = "TRUE", *args):
        data = self.limit(1).fetch(where_clause, *args)
        if len(data) > 0:
            return data[0]
        else:
            return None

    def count(self, where_clause: str = "TRUE", *args):
        return _db_execute("{0} WHERE {1};".format(
            self.__join_str.replace("*", "COUNT(*)", 1
        ), where_clause), *args)[0][0]

    def limit(self, lim: int):
        if not isinstance(lim, int):
            raise TypeError()
        new_select = Select(self)
        new_select.__limit = "LIMIT {0}".format(lim)
        new_select.__setattr__ = self._immutable_err
        return new_select

    def group_by(self, by: str = "id"):
        new_select = Select(self)
        new_select.__group_str = "GROUP BY {0}".format(by)
        new_select.__setattr__ = self._immutable_err
        return new_select

    def asc(self, order_by: str):
        new_select = Select(self)
        new_select.__order_string = "ORDER BY {0} ASC".format(order_by)
        new_select.__setattr__ = self._immutable_err
        return new_select

    def desc(self, order_by: str):
        new_select = Select(self)
        new_select.__order_string = "ORDER BY {0} DESC".format(order_by)
        new_select.__setattr__ = self._immutable_err
        return new_select

def _make_table(head, entry):
    out_str = ""
    if len(entry) == 0:
        return "empty table"
    sizes = [len(str(item)) for item in head]
    for i in range(len(sizes)):
        for row in entry:
            if sizes[i] < len(str(row[i])):
                sizes[i] = len(str(row[i]))
    br_line = "+"
    for i in range(len(sizes)):
        br_line += ("-" * (sizes[i] + 2)) + "+"
    out_str += br_line + "\n"
    line = "| "
    for i in range(len(head)):
        c_str = str(head[i])
        if c_str is None:
            c_str = "Null"
        else:
            c_str = str(c_str)
        line += str(c_str) + (" " * (sizes[i] - len(c_str))) + " | "
    out_str += line + "\n"
    out_str += br_line + "\n"
    for item in entry:
        line = "| "
        for i in range(len(item)):
            c_str = item[i]
            if c_str is None:
                c_str = "Null"
            else:
                c_str = str(c_str)
            line += str(c_str) + (" " * (sizes[i] - len(c_str))) + " | "
        out_str += line + "\n"
    out_str += br_line
    return out_str

def _t_missing(table, items):
    kwargs = dict()
    for item in table:
        kwargs[item[0]] = str(item[1]).casefold
    to_ret = []
    for key, val in items:
        if isinstance(val, _SQLtype) and key not in kwargs.keys():
            to_ret.append((str(key), str(val).lower(), "YES", "", None, ""))
        elif isinstance(val, type) and getattr(val, "__sql_table", None) is not None:
            to_ret.append((str(key), str(PRIMARY_KEY()).lower(), "YES", "", None, ""))
    return to_ret

def _t_type(table, items):
    kwargs = dict()
    for item in table:
        kwargs[item[0]] = str(item[1]).lower()
    to_ret = []
    for key, val in items:
        if isinstance(val, _SQLtype) and key in kwargs.keys() and not _compare_type(kwargs[key], val):
            to_ret.append((str(key), str(val).lower(), "YES", "", None, ""))
        elif isinstance(val, type) and getattr(val, "__sql_table", None) is not None and key in kwargs.keys() and not _compare_type(kwargs[key], PRIMARY_KEY()):
            to_ret.append((str(key), str(PRIMARY_KEY()).lower(), "YES", "", None, ""))
    return to_ret

def resource(cls: type):
    column_list = []
    for key, val in cls.__dict__.items():
        if isinstance(val, _SQLtype) or (isinstance(val, type) and getattr(val, "__sql_table", None) is not None):
            column_list.append((key, val))
    cls._column_list = column_list
    table_name = cls.__name__
    try:
        table = _db_execute("DESCRIBE {0};".format(table_name))
        if not _table_equal(table, column_list):
            print("\033[91mTable \"{table_name}\" does not match definition of class:".format(table_name=table_name))
            print(_make_table(("Field", "Type", "Null", "Key", "Default", "Extra"), table))
            print("missing columns:")
            print(_make_table(("Field", "Type", "Null", "Key", "Default", "Extra"), _t_missing(table, cls.__dict__.items())))
            print("columns with wrong type:")
            print(_make_table(("Field", "Type", "Null", "Key", "Default", "Extra"), _t_type(table, cls.__dict__.items())))
            print("recreate table \"{0}\"? (this will delete its content)\033[0m [Y/n] ".format(table_name), end="")
            inp = input()
            if inp == "n":
                print("Programm terminated. It is not safe to work with an unknown database table.")
                exit(0)
            _db_execute("DROP TABLE {0};".format(table_name))
            _create_table(table_name, column_list)
            table = _db_execute("DESCRIBE {0};".format(table_name))
    except ProgrammingError:
        _create_table(table_name, column_list)
        table = _db_execute("DESCRIBE {0};".format(table_name))
    _make_type_from_desc(table, cls)
    setattr(cls, "__sql_table", cls.__name__)
    return cls

def _add_accessors(cls_dict, name):
    @uses_db
    def setter(self, name, val):
        self.__setattr__("__" + name, val)
        if self.id != 0:
            _db_execute("UPDATE `{0}` SET `{1}` = %s WHERE `id` = %s;".format(type(self).__name__, name), val, self.id)
    prop = property(lambda self: self.__getattribute__("__" + name))
    cls_dict["__" + name] = None
    cls_dict[name] = prop.setter(lambda self, val: setter(self, name, val))

def _add_statements(class_dict, table_name, val_list, val_access_list):
    @classmethod
    @uses_db
    def select(cls, where_clause = "TRUE", *args, auto_join=False):
        data = cls._selector.fetch(where_clause, *args, auto_join=auto_join)
        out_list = [item.__getattribute__(cls.__name__) for item in data]
        return out_list
    insert_string = "INSERT INTO {0}({1}) VALUES(%s{2});".format(table_name, val_list, ", %s" * (len(val_access_list) - 1))
    @uses_db
    def insert(self):
        values = [None] * len(val_access_list)
        for i in range(len(val_access_list)):
            values[i] = self.__getattribute__("__" + val_access_list[i])
            if getattr(values[i], "__sql_table", None) is not None:
                if values[i].id == 0:
                    values[i].insert()
                values[i] = values[i].id
        _db_execute(insert_string, *tuple(values))
        self._id = _db_execute("SELECT LAST_INSERT_ID();")[0][0]
        type(self)._loaded_items[self._id] = self
        return self
    @uses_db
    def delete(self):
        _db_execute("DELETE FROM {0} WHERE id = %s;".format(table_name), self.id)
        self._id = 0
        del type(self)._loaded_items[self._id]
    """
    @uses_db
    def push (self, push_on=("id")):
        for item in push_on:
            if item not in self.selector().:
                raise TypeError("push_on can only contain ")
        if len(select (type(self), "{}".format())):
            pass
    """
    class_dict["select"] = select
    class_dict["insert"] = insert
    class_dict["delete"] = delete
    class_dict["_id"] = 0
    class_dict["_set_id"] = lambda self, val : setattr(self, "_id", val)
    class_dict["id"] = property(lambda self : self._id)
    class_dict["_loaded_items"] = weakref.WeakValueDictionary()
    #class_dict["push"] = push 

def _create_table(table_name, column_list):
    field_str = "id BIGINT PRIMARY KEY AUTO_INCREMENT"
    for name, datatype in column_list:
        if name == "id":
            raise Exception("\"id\" is a reserved field name")
        if isinstance(datatype, type) and getattr(datatype, "__sql_table", None) is not None:
            datatype = PRIMARY_KEY()
        if datatype.virtual_col is not None:
            field_str += ", `{name}` {datatype} AS({extra})".format(name=name, datatype=datatype, extra=datatype.virtual_col)
        else:
            field_str += ", `{name}` {datatype}".format(name=name, datatype=datatype)
    _db_execute("CREATE TABLE " + table_name + "(" + field_str + ");")

def _compare_type(t1, t2):
    return str(t1).casefold().replace("\"", "\'").replace(", ", ",") == str(t2).casefold().replace("\"", "\'").replace(", ", ",")

def _table_equal(table, column_list):
    kwargs = dict()
    for item in column_list:
        kwargs[item[0]] = item[1]
    if len(table) != len(kwargs) + 1:
        return False
    for row in table:
        if row[0] == 'id':
            if (row[1].casefold() != "BIGINT".casefold() and row[1].casefold().startswith("BIGINT(20)")) or \
                row[2] != "NO" or \
                row[3] != "PRI" or \
                row[4] != None or \
                row[5] != "auto_increment":
                return False
        else:
            if row[0] not in kwargs:
                return False
            if type(kwargs[row[0]]) == type:
                if not getattr(kwargs[row[0]], "__sql_table", None) is not None:
                    return False
            elif not _compare_type(row[1], kwargs[row[0]]):
                return False
            if row[2] != "YES" or row[3] != "" or row[4] != None:
                return False
    return True

@uses_db
def _make_type_from_desc(table, cls):
    class_dict = dict()
    val_list = None
    val_access_list = []
    for name, _, _, _, _, extra in table:
        if extra.strip() == "VIRTUAL GENERATED":
            continue
        if name == "id":
            continue
        _add_accessors(class_dict, name)
        if val_list is None:
            val_list = "`{name}`".format(name=name)
        else:
            val_list += ", `{name}`".format(name=name)
        val_access_list.append(name)
    _add_statements(class_dict, cls.__name__, val_list, val_access_list)
    def __init__(self, **kwargs):
        resource.__init__(self)
        for key, value in kwargs.items():
            if not key in val_access_list:
                raise KeyError("{0} is not a valid table column name".format(key))
            if isinstance(value, type) and getattr(value, "__sql_table", None) is not None:
                self.__setattr__("__" + key, value.id)
            else:
                self.__setattr__("__" + key, value)
    @classmethod
    @uses_db
    def wipe(cls, where_clause=None, *args):
        if where_clause is None:
            cls._loaded_items.clear()
            _db_execute("DELETE FROM {0};".format(cls.__name__))
            _db_execute("ALTER TABLE {0} AUTO_INCREMENT = 1;".format(cls.__name__))
        else:
            _db_execute("DELETE FROM {0} WHERE {1};".format(cls.__name__, where_clause), *args)
            for item in cls._loaded_items.items():
                if cls.selector().fetchone("id = %s", item) is None:
                    del cls._loaded_items[item.id]
    def __eq__(self, item):
        if type(self) != type(item):
            return False
        for access in val_access_list:
            if self.__getattribute__("__" + access) != item.__getattribute__("__" + access):
                return False
        return True
    @classmethod
    @uses_db
    def delete_table(cls):
        _db_execute("DROP TABLE {}".format(cls.__name__))
    class_dict["__init__"] = __init__
    class_dict["wipe"] = classmethod(wipe )
    class_dict["get_val_access_fields"] = lambda : tuple(val_access_list)
    class_dict["_selector"] = Select(cls)
    class_dict["__eq__"] = __eq__
    class_dict["delete_table"] = delete_table
    for key, val in resource.__dict__.items():
        if not key.startswith("__"):
            setattr(cls, key, val)
    for key, val in class_dict.items():
        setattr(cls, key, val)


class _SQLtype():
    def __init__(self, type_name, extra=None):
        self.__type_name = type_name
        self.__amount = extra
        self.virtual_col = None
    def __str__(self):
        if self.__amount is not None:
            return "{0}({1})".format(self.__type_name, self.__amount)
        else:
            return self.__type_name
    def virtual_column(self, extra):
        self.virtual_col = extra
        return self

def CHAR(len):
    assert(isinstance(len, int))
    return _SQLtype("CHAR", len)
def VARCHAR(len):
    assert(isinstance(len, int))
    return _SQLtype("VARCHAR", len)

def BINARY(len):
    assert(isinstance(len, int))
    return _SQLtype("BINARY", len)
def VARBINARY(len):
    assert(isinstance(len, int))
    return _SQLtype("VARBINARY", len)

def TINYBLOB():
    return _SQLtype("TINYBLOB")
def BLOB(len=None):
    assert(isinstance(len, int) or len is None)
    return _SQLtype("BLOB", len)
def MEDIUMBLOB():
    return _SQLtype("MEDIUMBLOB")
def LONGBLOB():
    return _SQLtype("LONGBLOB")

def TINYTEXT():
    return _SQLtype("TINYTEXT")
def TEXT(len=None):
    assert(isinstance(len, int) or len is None)
    return _SQLtype("TEXT", len)
def MEDIUMTEXT():
    return _SQLtype("MEDIUMTEXT")
def LONGTEXT():
    return _SQLtype("LONGTEXT")

def ENUM(*args):
    full_arg = None
    for arg in args:
        assert(isinstance(arg, str))
        if full_arg is None:
            full_arg = '"{}"'.format(arg)
        else:
            full_arg += ', "{}"'.format(arg)
    return _SQLtype("ENUM", full_arg)

def SET(*args):
    full_arg = None
    for arg in args:
        assert(isinstance(arg, str))
        if full_arg is None:
            full_arg = '"{}"'.format(arg)
        else:
            full_arg += ', "{}"'.format(arg)
    return _SQLtype("SET", full_arg)

def BIT():
    return _SQLtype("BIT")
def TINYINT():
    return _SQLtype("TINYINT")
def BOOL():
    return _SQLtype("TINYINT(1)")
def BOOLEAN():
    return _SQLtype("TINYINT(1)")
def SMALLINT():
    return _SQLtype("SMALLINT")
def MEDIUMINT():
    return _SQLtype("MEDIUMINT")
def INT():
    return _SQLtype("INT")
def INTEGER():
    return _SQLtype("INTEGER")
def BIGINT():
    return _SQLtype("BIGINT")
def FLOAT():
    return _SQLtype("FLOAT")

def DATE():
    return _SQLtype("DATE")
def DATETIME():
    return _SQLtype("DATETIME")
def TIMESTAMP():
    return _SQLtype("TIMESTAMP")
def TIME():
    return _SQLtype("TIME")
def YEAR():
    return _SQLtype("YEAR")
def PRIMARY_KEY():
    return _SQLtype("BIGINT")
