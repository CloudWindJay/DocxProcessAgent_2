import sqlalchemy
from sqlalchemy import create_engine
import sys

URL = 'mysql+pymysql://root:rootpass@127.0.0.1:3306/docx_agent'

try:
    e = create_engine(URL)
    with e.connect() as c:
        print("SUCCESS! Connected.")
except Exception as ex:
    print("FAILED TO CONNECT:")
    print(ex)
    sys.exit(1)
