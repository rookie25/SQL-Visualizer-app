import streamlit as st
import sqlite3
import pandas as pd

# Set page title
st.title("SQL Visualizer")

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

# Create a text area for SQL query input
query = st.text_area("Enter your SQL query:", "SELECT * FROM students;")

# Add a button to execute the query
if st.button("Run Query"):
    try:
        # Execute the query and fetch results
        df = pd.read_sql_query(query, conn)
        st.dataframe(df)
    except Exception as e:
        st.error(f"Error executing query: {str(e)}")

# Close the database connection when the app is closed
conn.close() 