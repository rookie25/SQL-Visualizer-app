import streamlit as st
import sqlalchemy
import pandas as pd
import re
import sqlparse
import time
from html import escape
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from sqlalchemy import text
import json

st.set_page_config(layout="wide", page_title="SQL Visualizer")

st.markdown("""
<style>
  .section-container {
    border: 1px solid #ddd;
    padding: 16px;
    margin-bottom: 16px;
    border-radius: 8px;
    background-color: #fafafa;
  }
</style>
""", unsafe_allow_html=True)

def get_schema(conn):
    cur = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
    tables = [row[0] for row in cur.fetchall()]
    schema = {}
    for t in tables:
        cur = conn.execute(text(f"PRAGMA table_info({t});"))
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

def render_table_html(df, highlight_row=None, highlight_col=None, highlight_class=None):
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
    if highlight_class:
        style += f'{highlight_class} {{ background-color: #ffecec; }}'
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

def generate_execution_trace(query: str, conn):
    lines = query.strip().split('\n')
    trace = []
    # Clause events
    for idx, line in enumerate(lines):
        for kw in ['SELECT','FROM','WHERE','JOIN','GROUP BY','ORDER BY','COUNT','SUM','AVG','MIN','MAX']:
            if re.search(rf'\b{kw}\b', line, flags=re.IGNORECASE):
                trace.append({'type':'clause','line':idx})
                break

    # Detect aggregate, allowing optional AS alias
    m = re.search(
        r'\b(AVG|SUM|COUNT|MIN|MAX)\((\w+)\)(?:\s+AS\s+\w+)?\s+FROM\s+(\w+)',
        query, flags=re.IGNORECASE
    )
    # Always scan full base table cells
    if m:
        fn, col, tbl = m.group(1).upper(), m.group(2), m.group(3)
    else:
        # fallback: use first FROM clause to find table name
        from_match = re.search(r'\bFROM\s+(\w+)', query, flags=re.IGNORECASE)
        tbl = from_match.group(1) if from_match else None
        col = None

    df_base = pd.read_sql_query(f"SELECT * FROM {tbl}", conn)
    for i, row in enumerate(df_base.values.tolist()):
        for j in range(len(row)):
            trace.append({'type':'cell','mode':'base','row':i,'col':j})

    # If aggregate detected, animate its final result cell
    df_agg = None
    if m:
        df_agg = pd.read_sql_query(query, conn)
        trace.append({'type':'cell','mode':'agg','row':0,'col':0})

    trace.append({'type':'complete'})
    return trace, df_base, df_agg

# Sidebar Connection Profile
st.sidebar.header("Connection Profile")
mode = st.sidebar.selectbox("SQLite Mode", ["In-Memory", "File-Based"])
if mode == "In-Memory":
    engine = sqlalchemy.create_engine("sqlite:///:memory:")
else:
    db_path = st.sidebar.text_input("SQLite file path", "data.db")
    engine = sqlalchemy.create_engine(f"sqlite:///{db_path}")
conn = engine.connect()

# Ensure sample table exists
conn.execute(text("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY,
        name TEXT,
        grade TEXT
    )
"""))
conn.execute(text("""
    INSERT OR IGNORE INTO students (id,name,grade) VALUES
    (1,'Alice','A'),(2,'Bob','B'),(3,'Charlie','C')
"""))

# Add Schema Explorer to sidebar
st.sidebar.header("Schema Explorer")
schema = get_schema(conn)
for table, cols in schema.items():
    st.sidebar.subheader(table)
    st.sidebar.write(", ".join(cols))

# Object Explorer sidebar tree (immediately after Schema Explorer)
st.sidebar.header("Object Explorer")
schema = get_schema(conn)
for table, cols in schema.items():
    with st.sidebar.expander(table):
        # Button to load the table
        if st.button(f"Select * from {table}", key=f"btn_{table}"):
            st.session_state["query"] = f"SELECT * FROM {table};"
        # List columns
        st.write("Columns: " + ", ".join(cols))

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
st.markdown("A web tool to visualize SQL execution step-by-step.", unsafe_allow_html=True)

# Editor section
st.markdown('<div class="section-container">', unsafe_allow_html=True)
query = st.text_area(
    "Enter your SQL query:",
    value=st.session_state.get("query", "SELECT * FROM students;"),
    key="query"
)
run_button = st.button("Run Query")
st.markdown('</div>', unsafe_allow_html=True)

if run_button:
    # capture start time
    start = time.time()

    # generate execution trace
    trace, df_base, df_agg = generate_execution_trace(query, conn)

    # placeholders for animation
    code_ph  = st.empty()
    table_ph = st.empty()

    # animation loop
    for ev in trace:
        if ev["type"] == "clause":
            code_ph.markdown(
                render_query_code(query, highlight_line=ev["line"]),
                unsafe_allow_html=True
            )
        elif ev["type"] == "cell":
            mode = ev['mode']
            css  = 'base-highlight' if mode == 'base' else 'agg-highlight'
            df   = df_base if mode == 'base' else df_agg

            table_html = render_table_html(
                df,
                highlight_row=ev['row'],
                highlight_col=ev['col'],
                highlight_class=css
            )
            table_ph.markdown(table_html, unsafe_allow_html=True)
        # ignore any other event types
        time.sleep(0.5)

    # final display of code + table
    code_ph.markdown(render_query_code(query), unsafe_allow_html=True)
    final_df   = df_agg if df_agg is not None else df_base
    table_ph.markdown(render_table_html(final_df), unsafe_allow_html=True)

    # query summary & results grid
    duration = time.time() - start
    st.subheader("Query Results")
    st.markdown(f"**{len(final_df)} rows returned in {duration:.2f}s**")
    st.dataframe(final_df)

    st.success("Execution complete")

# Close the database connection when the app is closed
conn.close() 