import pymysql
import pandas as pd
import streamlit as st
import plotly.express as px

# --- DATABASE CONNECTION ---
@st.cache_resource # Keep using cache_resource for the connection
def get_connection():
    # Ensure you handle potential connection errors in a real app
    try:
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password='',        # Use environment variables for sensitive info in production
            database='Tennis_Game',
            cursorclass=pymysql.cursors.DictCursor # Optional: Easier to work with results
        )
        return conn
    except pymysql.Error as e:
        st.error(f"Database connection error: {e}")
        return None # Return None if connection fails

# --- FETCH DATA FROM SQL ---
@st.cache_data # Keep using cache_data for query results
def fetch_table(query):
    conn = get_connection()
    if conn: # Check if connection was successful
        try:
            # Using 'with' ensures the cursor is closed automatically
            with conn.cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchall()
            # Create DataFrame from the list of dictionaries (if using DictCursor)
            # If not using DictCursor, pd.read_sql might be simpler,
            # but manual fetching gives more control over errors.
            df = pd.DataFrame(result)
            # conn.close() # Don't close here if using @st.cache_resource
            return df
        except pymysql.Error as e:
            st.error(f"Error fetching data: {e}")
            return pd.DataFrame() # Return empty DataFrame on error
        # Note: pd.read_sql might implicitly handle cursor/connection closure differently
        # return pd.read_sql(query, conn) # Original way also works
    else:
        return pd.DataFrame() # Return empty DataFrame if no connection

# --- Initialize Session State ---
# This ensures these variables exist across script reruns for the user session
if 'filters_applied' not in st.session_state:
    st.session_state.filters_applied = False
    st.session_state.submitted_country = None
    st.session_state.submitted_category = None

# --- Load Data ---
# Put data loading inside a function or check to avoid reloading constantly if possible
# For simplicity here, we load it once. Use caching effectively.
conn = get_connection()
if conn: # Only proceed if connection is established
    df_competitors = fetch_table("SELECT * FROM competitors")
    df_rankings = fetch_table("SELECT * FROM competitor_rankings")
    df_complexes = fetch_table("SELECT * FROM complexes")
    df_venues = fetch_table("SELECT * FROM venues")
    df_category = fetch_table("SELECT * FROM categories")
    df_competition = fetch_table("SELECT * FROM competitions")

    # Check if DataFrames are empty before proceeding
    if not df_competitors.empty and not df_rankings.empty:
        df_merged = pd.merge(df_rankings, df_competitors, on="competitor_id", how="left")
    else:
        df_merged = pd.DataFrame() # Create empty if data missing

    if not df_venues.empty and not df_complexes.empty:
        venue_info = pd.merge(df_venues, df_complexes, on="complex_id", how="left")
    else:
        venue_info = pd.DataFrame()

    if not df_competition.empty and not df_category.empty:
        comp_info = pd.merge(df_competition, df_category, on="category_id", how="left")
    else:
        comp_info = pd.DataFrame()

else: # Handle case where initial connection failed
    st.error("Failed to connect to the database. Cannot load data.")
    # Assign empty dataframes to prevent errors later
    df_competitors = df_rankings = df_complexes = df_venues = df_category = df_competition = pd.DataFrame()
    df_merged = venue_info = comp_info = pd.DataFrame()


# --- SIDEBAR FILTERS ---
st.sidebar.header("🔍 Filters")

# Use st.form to group inputs and submit button
with st.sidebar.form("filter_form"):
    # Get unique values, handle potential errors if df is empty
    country_list = sorted(df_competitors['country'].dropna().unique()) if not df_competitors.empty else []
    category_list = sorted(df_category['category_name'].dropna().unique()) if not df_category.empty else []

    # Set default index based on previous submission if available
    default_country_index = 0
    if st.session_state.filters_applied and st.session_state.submitted_country in country_list:
       try:
           default_country_index = country_list.index(st.session_state.submitted_country)
       except ValueError:
           default_country_index = 0 # Fallback if value not found

    default_category_index = 0
    if st.session_state.filters_applied and st.session_state.submitted_category in category_list:
        try:
            default_category_index = category_list.index(st.session_state.submitted_category)
        except ValueError:
            default_category_index = 0 # Fallback

    # Selectboxes inside the form
    selected_country = st.selectbox(
        "Select Country",
        options=country_list,
        index=default_country_index,
        disabled=not country_list # Disable if list is empty
        )
    selected_category = st.selectbox(
        "Select Category",
        options=category_list,
        index=default_category_index,
        disabled=not category_list # Disable if list is empty
        )

    # Submit button for the form
    submitted = st.form_submit_button("Apply Filters")

    if submitted:
        # Store the selected values in session state when form is submitted
        st.session_state.filters_applied = True
        st.session_state.submitted_country = selected_country
        st.session_state.submitted_category = selected_category
        st.sidebar.success("Filters Applied!") # User feedback

# Cancel/Clear button OUTSIDE the form
clear_filters = st.sidebar.button("Clear Filters / Show All")
if clear_filters:
    st.session_state.filters_applied = False
    st.session_state.submitted_country = None
    st.session_state.submitted_category = None
    st.sidebar.info("Filters Cleared. Showing all data.")
    # st.experimental_rerun() # Optional: Force rerun to immediately reset selectbox index

# --- MAIN LAYOUT ---
st.title("🎾Tennis Game Dashboard")

# Determine current filter status for display
display_country = st.session_state.submitted_country if st.session_state.filters_applied else "All"
display_category = st.session_state.submitted_category if st.session_state.filters_applied else "All"

st.info(f"Displaying data for Country: **{display_country}**, Category: **{display_category}**")


# --- Apply Filters based on Session State ---
# Only filter if 'filters_applied' is True and the corresponding state variable has a value
filtered_df = df_merged.copy() # Start with a copy of the full data
if st.session_state.filters_applied and st.session_state.submitted_country and not filtered_df.empty:
    filtered_df = filtered_df[filtered_df['country'] == st.session_state.submitted_country]

filtered_comp = comp_info.copy() # Start with a copy
if st.session_state.filters_applied and st.session_state.submitted_category and not filtered_comp.empty:
    filtered_comp = filtered_comp[filtered_comp['category_name'] == st.session_state.submitted_category]


# --- Display Data ---
col1, col2 = st.columns(2)

with col1:
    st.subheader(f"📊 Competitor Rankings")
    st.dataframe(filtered_df) # Display the potentially filtered df

with col2:
    st.subheader("🏆 Top 10 Players (Overall)")
    # Usually Top 10 is based on the overall data, not the filtered one, unless specified otherwise
    if not df_merged.empty:
        top10 = df_merged.sort_values("rank").head(10)
        st.dataframe(top10)
    else:
        st.write("No ranking data available.")


st.markdown("---")
st.header("📍 Venues & Complexes")
st.dataframe(venue_info) # Venue info usually isn't filtered by player country/category

st.markdown("---")
st.header(f"📅 Competitions")
st.dataframe(filtered_comp) # Display the potentially filtered competition info

# --- VISUALIZATION ---
st.markdown("---")
st.header("📈 Analysis")

# Histogram - Show overall distribution unless filters are applied
if not df_merged.empty:
    # Decide if histogram should be filtered or always show all countries
    # Option 1: Always show all countries
    hist_data = df_merged
    hist_title = "Number of Players per Country (Overall)"
    # # Option 2: Show only filtered country in histogram (might not be very useful for histogram)
    # if st.session_state.filters_applied and st.session_state.submitted_country:
    #     hist_data = filtered_df
    #     hist_title = f"Players in {st.session_state.submitted_country}"
    # else:
    #     hist_data = df_merged
    #     hist_title = "Number of Players per Country (Overall)"

    fig = px.histogram(hist_data, x="country", title=hist_title, color_discrete_sequence=['#EF553B'])
    st.plotly_chart(fig, use_container_width=True)
else:
    st.write("No data for player distribution plot.")


# Bar Chart - Show Overall Top 10
if 'top10' in locals() and not top10.empty: # Check if top10 exists and is not empty
    fig2 = px.bar(top10, x='name', y='points', color='points', title='Top 10 Players by Points (Overall)')
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.write("No data for top 10 players plot.")

# Add a placeholder if connection failed initially
if not conn:
     st.warning("Application running with limited functionality due to database connection failure.")

     # --- FOOTER ---
st.markdown("---")
st.markdown("Done by [DEVAKUMAR SUGUMARAN]")