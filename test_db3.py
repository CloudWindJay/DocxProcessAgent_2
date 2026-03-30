import pymysql

try:
    c = pymysql.connect(
        host='127.0.0.1', 
        port=3306, 
        user='root', 
        password='rootpass', 
        database='docx_agent',
        client_flag=0
    )
    print("SUCCESS")
    c.close()
except Exception as ex:
    print("ERROR:", repr(ex))
