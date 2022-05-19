# mysql_mapping.py:

## setup

To get started, put the file "mysql_mapping.py" next to your python file and import it. It is recommended to import everything:

```python
from mysql_mapping import *
```

The next step is, to set important setup data. When importing, a dictionary called "db_setup" is imported. Here you can set the database name, the user and the password.
```python
db_config["host"] = "127.0.0.1"
db_config["user"] = "my_user"
db_config["password"] = "my_original_passwort_that_I_totally_not_pushed_to_github"
db_config["database"] = "my_database"
```
For more information about this setup dictionary, look at the [MySQLdb documentation](https://mysqlclient.readthedocs.io/user_guide.html#mysqldb).

## Create a table or make a existing table usable

Create a class with the name of the desired table, deriving from Resource. The class can have methods and variables like a normal class, but every variable initialized with a SQL type or an other Resource deriving class will appear as a column.

Example:
```python
class Employee(Resource):
    fname = VARCHAR(128)
    lname = VARCHAR(128)
    wage = INT()
```

This class will create a Table upon being created. A primary key will be added automatically.
|name|type|extra|
|----|----|----|
|id|BIGINT|PRIMARY KEY AUTO_INCREMENT|
|fname|VARCHAR(128)||
|lname|VARCHAR(128)||
|wage|INT||

You can also pass Resource deriving classes. They will be converted to `PRIMARY_KEY()`.
When running the code, the table will be created in the database specified in the db_config dictionary. If a table with that name already exists, the program will ask you if you want to override it. Data contained will be deleted, so make sure you have a copy of that data or just change the tables manually.

## Inserting values

To insert a value you first have to create an instance of the class, representing the table. On this `.insert()` can be called. The constructor can also take keyword arguments for the columns in case it is not overridden.

Example:

```python
class Employee(Resource):
    fname = VARCHAR(128)
    lname = VARCHAR(128)
    wage = INT()

fred = Employee(fname="Fred")
fred.lname = "Lee"
fred.insert()
fred.wage = 2000
```
Make sure that all these operations are done in a functon wrapped with `@uses_db`.
After inserting, changing a value on the inserted object, will trigger an update statement, updating the row in the database. So it is recommendable to change those before inserting into the database.

## Select values

There are two ways of selecting from a table. The easier one, is to to use the `.select()` method.
It takes an optionak argument. A string, representing the where clause.

Returned is a list with all resulting rows. For example:
```python
data = Employee.select("name = 'Fred'")
print(data[0].fname) #Fred
print(data[0].lname) #Lee
print(data[0].wage) #2000
```
This variant has a little problem. It does not support joins. To fix this, the other, more complicated variant can be used.

## Joins

To join tables it is important to know the other way to join.
```python
data = Select(Employee).fetch("fname = %s", name)
```
This type of select involves a class called `Select`.  The constructor takes the table class to select from and an optional name for the table. The name is important in case you need to join a table to itself. Always make sure, that you use formatting with %s to insert variables. It is the only safe way. You also can use the Select object multiple times:
```python
selector = Select(Employee)
data = selector.fetch()
fred = selector.fetch("fname = 'Fred"')[0].Employee
```
In difference to the direct select method, this method does not return a list containing the rows. It returns a list with the join results. The variable `data` from the example looks like this:
```python
print(data) # [<_JoinResult ...>]
print(data[0].Employee) # <Employee ...>
print(data[0].Employee.fname) # Fred
```
The reason for this behaviour is, that rows after a join might share names and have to be splitted between two objects because of that.

Now, how do we join? A Select object knows methods like `.leftjoin()`. It will return a new selector, that will join tables. It needs one arguments. The table that should be joined. Two optional arguments can be given, the ON clause and the name for the joined table.

An example could look like this:
```python
class Employee(Resource):
    fname = VARCHAR(128)
    lname = VARCHAR(128)
    wage = INT()

class Order(Resource):
    status = ENUM("PENDING", "DELIVERED", "DONE")
    handling_employee = Employee

fred = Employee(
    fname = "Fred",
    lname = "Lee",
)

fred.insert()

Order(
    status = "PENDING",
    handling_employee = fred
).insert()

selector = Select(Order, "o")
selector = selector.leftjoin(Employee, "handling_employee_id = e.id", "e")
data = selector.fetch()
print(data[0].o.status) # PENDING
print(data[0].e.fname) # Fred
```

## automatic joins

When creating a table, it is possible to use an other table as a column.
```python
class User(Resource):
    # here goes your data
    def __str__(self):
        return "<a user object with id %s>" % self.id

class Chat(Resource):
    # here goes your data
    def __str__(self):
        return "<a chat object with id %s>" % self.id

class UserChatRelation(Resource):
    user=User
    chat=Chat
    def __str__(self):
        return "<a user chat relation object with id %s and %s %s>" % (self.id, self.user, self.chat)
```
The table `UserChatRelation` now has three columns, the first one is the id of the relation and the primary key. The second and third are the primary keys of the `User` and `Chat` table.  
Usually to join them, a selector had to be constructed:
```python
my_selector = Select(UserChatRelation)\
    .join(User, "User.id = UserChatRelation.user")\
    .join(User, "Chat.id = UserChatRelation.chat")
data = my_selector.fetch()[0]
print(data.User) # <a user object with id 11>
print(data.Chat) # <a chat object with id 12>
print(data.UserChatRelation) 
# <a user chat relation object with id 1 and 11 12>"
```
As a result we get a list of `mysql_mapping._JoinResult` objects. Every item has the fields `.UserChatRelation`, `.User` and `.Char`. That is a bit complicated to work with. But there is an other way to join such a thing. The `Select.fetch()` as well as the `Resource.select()` method, have an option called "auto_join". It is a keyword only argument and should be a boolean. It is set to False by standart.
```python
data = UserChatRelation.select(auto_join=True)[0]

print(data) # <a user chat relation object with id 1 and <a user object with id 11> <a chat object with id 12>>
```
Now instead of the ids of the other objects, the objects themself are in the fields.
