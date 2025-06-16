import streamlit as st
import sqlite3
import pandas as pd
import re
import sqlparse

def get_schema(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]
    schema = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t});")
        cols = [col[1] for col in cur.fetchall()]
        schema[t] = cols
    return schema

# Create an in-memory SQLite database
conn = sqlite3.connect(':memory:')
cursor = conn.cursor()

# Create the students table
cursor.execute('''
    CREATE TABLE students (
        id INTEGER PRIMARY KEY,
        name TEXT,
        grade TEXT
    )
''')

# Insert sample data
sample_data = [
    (1, 'Alice', 'A'),
    (2, 'Bob', 'B'),
    (3, 'Charlie', 'C')
]
cursor.executemany('INSERT INTO students VALUES (?, ?, ?)', sample_data)
conn.commit()

# Add Schema Explorer to sidebar
st.sidebar.header("Schema Explorer")
schema = get_schema(conn)
for table, cols in schema.items():
    st.sidebar.subheader(table)
    st.sidebar.write(", ".join(cols))

# Set page title
st.title("SQL Visualizer")

def parse_sql_steps(query: str) -> list[str]:
    # Split on common SQL clauses
    parts = re.split(
        r'(\bSELECT\b|\bFROM\b|\bWHERE\b|\bJOIN\b|\bGROUP BY\b|\bORDER BY\b)',
        query, flags=re.IGNORECASE
    )
    steps = []
    i = 1
    while i < len(parts) - 1:
        clause = parts[i].strip().upper()
        content = parts[i+1].strip().rstrip(';')
        if clause == 'SELECT':
            desc = f"Select columns → {content}"
        elif clause == 'FROM':
            desc = f"Load table → {content}"
        elif clause == 'WHERE':
            desc = f"Apply filter → {content}"
        else:
            desc = f"{clause} → {content}"
        steps.append(desc)
        i += 2
    return steps

# Create a text area for SQL query input
query = st.text_area("Enter your SQL query:", "SELECT * FROM students;")

# Add a button to execute the query
if st.button("Run Query"):
    steps = parse_sql_steps(query)
    for idx, desc in enumerate(steps, start=1):
        with st.expander(f"🔹 Step {idx}"):
            # Display clause icon + description
            if desc.lower().startswith("select"):
                st.info(desc)       # blue
            elif desc.lower().startswith("load table"):
                st.success(desc)    # green
            elif desc.lower().startswith("apply filter"):
                st.warning(desc)    # yellow
            else:
                st.write(desc)
        
    try:
        # Execute the query and fetch results
        df = pd.read_sql_query(query, conn)
        st.dataframe(df)
    except Exception as e:
        st.error(f"Error executing query: {str(e)}")

# Close the database connection when the app is closed
conn.close() 