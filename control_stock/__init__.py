"""Project package init.

Install PyMySQL as a drop-in replacement for MySQLdb when using MySQL
so Django can import the DB backend without requiring compiled mysqlclient.
"""

try:
	import pymysql
	pymysql.install_as_MySQLdb()
except Exception:
	# If PyMySQL is not available or fails to install, let the import error
	# surface elsewhere (e.g., when user chooses to install mysqlclient).
	pass
