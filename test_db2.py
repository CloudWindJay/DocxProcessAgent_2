import pymysql
import sys

try:
    c = pymysql.connect(
        host='127.0.0.1', 
        port=3306, 
        user='root', 
        password='rootpass', 
        database='docx_agent',
        auth_plugin='caching_sha2_password'
    )
    print("SUCCESS")
    c.close()
except Exception as ex:
    print("ERROR:", repr(ex))
