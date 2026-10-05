import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(
    "mysql+pymysql://root:raghul*99@localhost/smarta"
)

df = pd.read_sql(
    "SELECT * FROM maintenance_logs",
    engine
)

print(df)