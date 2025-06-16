import streamlit as st
import sqlite3
import pandas as pd
import re
import sqlparse
import time
from html import escape

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

def render_query_code(query, highlight_line=None):
    # Split query into lines
    lines = query.strip().split('\n')
    html_lines = []
    for i, line in enumerate(lines):
        text = escape(line)
        if i == highlight_line:
            html_lines.append(f'<div style="background-color:#fffbcc;padding:2px"><code>{text}</code></div>')
        else:
            html_lines.append(f'<div><code>{text}</code></div>')
    return '<div style="border:1px solid #ddd;padding:4px;">' + ''.join(html_lines) + '</div>'

def render_table_html(df, highlight_row=None, highlight_col=None):
    # Convert df to html table
    html = df.to_html(index=False, escape=False)
    # Inject CSS to highlight
    style = '<style>'
    if highlight_row is not None:
        # highlight entire row
        style += f'tr:nth-child({highlight_row+1}) td {{ background-color: #ffecec; }}'
    if highlight_col is not None:
        # highlight entire column
        style += f'td:nth-child({highlight_col+1}) {{ background-color: #ecffecec; }}'
    style += '</style>'
    return style + html

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

# Add Create New Table section to sidebar
st.sidebar.header("Create New Table")
new_table = st.sidebar.text_input("Table Name")
cols_input = st.sidebar.text_area(
    "Columns (SQL syntax, e.g. id INTEGER, name TEXT, grade TEXT)"
)
if st.sidebar.button("Create Table"):
    try:
        conn.execute(f"CREATE TABLE {new_table} ({cols_input});")
        conn.commit()
        st.sidebar.success(f"Table '{new_table}' created.")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")
    # Refresh and re-display schema
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
    # Parse steps as before
    steps = parse_sql_steps(query)

    # Detect COUNT
    if re.search(r'\bCOUNT\(', query, flags=re.IGNORECASE):
        # Extract column and table from the query
        m = re.search(r'COUNT\((\w+)\).*FROM\s+(\w+)', query, flags=re.IGNORECASE)
        if m:
            col = m.group(1)
            table = m.group(2)
        else:
            # Fallback: use the first FROM step
            table = steps[1].split('→')[1].strip()
            col = '*'
        # Animate counting
        rows = conn.execute(f"SELECT {col} FROM {table}").fetchall()
        placeholder_metric = st.empty()
        progress_bar = st.progress(0)

        for idx, _ in enumerate(rows, start=1):
            # update metric and progress
            placeholder_metric.metric(
                label=f"Counting `{col}` in `{table}`",
                value=idx,
                delta=f"/ {len(rows)}"
            )
            progress_bar.progress(idx / len(rows))
            time.sleep(0.5)

        # cleanup and show final result
        progress_bar.empty()
        st.success(f"COUNT result: {len(rows)}")
    else:
        # Existing timeline animation
        timeline_placeholder = st.empty()
        stages = [s.split('→')[0].strip().upper() for s in steps] + ['RESULT']
        for i in range(len(stages)):
            cols = timeline_placeholder.columns(len(stages))
            for j, name in enumerate(stages):
                if j == i:
                    cols[j].markdown(f"**🔵 {name}**")
                else:
                    cols[j].markdown(name)
            time.sleep(0.5)
        timeline_placeholder.empty()
        
        # New code + table highlight animation
        df = pd.read_sql_query(query, conn)
        code_ph = st.empty()
        table_ph = st.empty()
        for idx in range(len(df)):
            # Highlight code: first clause line (0), then second (1), etc.
            code_ph.markdown(render_query_code(query, highlight_line=min(idx, len(query.split('\n'))-1)), unsafe_allow_html=True)
            # Highlight the idx-th row
            table_ph.markdown(render_table_html(df, highlight_row=idx), unsafe_allow_html=True)
            time.sleep(0.5)
        # Final: show full code+table
        code_ph.markdown(render_query_code(query), unsafe_allow_html=True)
        table_ph.markdown(render_table_html(df), unsafe_allow_html=True)
        st.success("Done!")

# Close the database connection when the app is closed
conn.close() 