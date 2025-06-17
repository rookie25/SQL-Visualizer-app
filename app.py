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

def generate_execution_trace(query: str, conn) -> tuple[list, pd.DataFrame]:
    # 1) Split SQL into lines
    lines = query.strip().split('\n')
    trace = []
    # 2) Clause events: highlight each clause line
    for idx, line in enumerate(lines):
        for kw in ['SELECT','FROM','WHERE','JOIN','GROUP BY','ORDER BY','COUNT','SUM','AVG','MIN','MAX']:
            if re.search(rf'\b{kw}\b', line, flags=re.IGNORECASE):
                trace.append({'type':'clause','line':idx})
                break
    # 3) Execute query into DataFrame
    df = pd.read_sql_query(query, conn)
    # 4) Row/cell events
    for i, row in enumerate(df.values.tolist()):
        trace.append({'type':'row_start','row':i})
        for j in range(len(row)):
            trace.append({'type':'cell','row':i,'col':j})
        trace.append({'type':'row_end','row':i})
    # 5) Completion event
    trace.append({'type':'complete'})
    return trace, df

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

# Create two columns for the main layout
col1, col2 = st.columns(2)

# Left column: SQL editor
with col1:
    query = st.text_area("Enter your SQL query:", "SELECT * FROM students;")
    run_button = st.button("Run Query")

# Right column: Code and table panels
with col2:
    code_ph = st.empty()
    table_ph = st.empty()

# Execute query when button is clicked
if run_button:
    try:
        # Generate trace and data
        trace, df = generate_execution_trace(query, conn)

        # Step through events
        for event in trace:
            typ = event['type']
            if typ == 'clause':
                # Highlight the SQL line
                code_ph.markdown(
                    render_query_code(query, highlight_line=event['line']),
                    unsafe_allow_html=True
                )
            elif typ == 'row_start':
                # Highlight the current row
                table_ph.markdown(
                    render_table_html(df, highlight_row=event['row']),
                    unsafe_allow_html=True
                )
            elif typ == 'cell':
                # Highlight a specific cell
                table_ph.markdown(
                    render_table_html(df, highlight_row=event['row'], highlight_col=event['col']),
                    unsafe_allow_html=True
                )
            # (You can add special logic on 'row_end' if desired)
            time.sleep(0.5)

        # Final display (un-highlighted)
        code_ph.markdown(render_query_code(query), unsafe_allow_html=True)
        table_ph.markdown(render_table_html(df), unsafe_allow_html=True)
        st.success("Execution complete")
        
    except Exception as e:
        st.error(f"Error executing query: {str(e)}")

# Close the database connection when the app is closed
conn.close() 